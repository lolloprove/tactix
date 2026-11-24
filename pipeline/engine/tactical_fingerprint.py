"""Deterministic tactical fingerprint computation (ZERO AI).

Computes per (match, team):
  - avg_def_line_y: median Y of starting centre-backs (0-100), or calibrated
    territorial Opta proxy when provider only supplies static formation layout.
  - back_line_count: 3, 4, or 5
  - ppda: provider PPDA (Understat), event-level PPDA, or calibrated Opta/FotMob
    pressing-intensity proxy (opponent own-half passes / weighted high-zone
    tackles + interceptions + fouls).
  - field_tilt: share of final-third / opposition-half actions (0-100)
  - attack_bias_left / center / right: flank distribution summing to 100
  - xga_zones_json: opponent shots mapped into 8 shot zones + 5/3 corridors
  - dribbles_zones_json: 5 corridors x 3 height bands of dribbles conceded & produced
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median
from typing import Literal

from db.models import (
    DribblesZones,
    DribbleZoneCell,
    DribbleZonePlayer,
    PlayerMatchStatsUpsert,
    PlayerPosition,
    TeamMatchTacticsUpsert,
    XgaZones,
    ZoneCorridor,
)
from engine.pitch import (
    ShotPoint,
    build_xga_zones,
    corridor_from_x,
    position_default_corridor,
)

_FORMATION_RE = re.compile(r"^\d(-\d){2,4}$")

DEFENSIVE_ACTION_TYPES = frozenset({"tackle", "interception", "foul", "challenge", "recovery", "duel"})
ATTACK_EVENT_TYPES = frozenset({"shot", "pass", "carry", "dribble", "touch", "cross", "key_pass"})


@dataclass(frozen=True)
class PlayerPositionSample:
    position: PlayerPosition | None
    minutes: int
    is_starter: bool
    avg_x: float | None
    avg_y: float | None
    progressive_actions: int | None = None
    tackles: int | None = None
    interceptions: int | None = None
    fouls: int | None = None
    recoveries: int | None = None


@dataclass(frozen=True)
class TeamMatchOptaStats:
    """Team-level Opta match counters (from FotMob `content.stats` & `attackingZones`)."""

    own_half_passes: int | None = None
    opp_half_passes: int | None = None
    tackles: int | None = None
    interceptions: int | None = None
    fouls: int | None = None
    touches_opp_box: int | None = None
    attack_bias_left: float | None = None
    attack_bias_center: float | None = None
    attack_bias_right: float | None = None


@dataclass(frozen=True)
class PitchEventSample:
    team_id: int
    event_type: str
    x: float
    y: float
    xg: float | None = None
    is_goal: bool = False


def _finite(val: float | None) -> float | None:
    if val is None or not math.isfinite(val):
        return None
    return val


def normalize_formation(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = raw.strip().replace(" ", "")
    return cleaned if _FORMATION_RE.match(cleaned) else None


def _is_static_formation_grid(players: Sequence[PlayerPositionSample]) -> bool:
    """Detect FotMob's static formation grid where all back-line starters share identical Y."""
    defs = [
        float(p.avg_y)
        for p in players
        if (p.is_starter or p.minutes >= 45)
        and p.position in ("CB", "LB", "RB")
        and p.avg_y is not None
    ]
    if len(defs) < 2:
        return False
    return (max(defs) - min(defs)) < 0.5 and abs(defs[0] - 29.2) < 1.5


def compute_defensive_line_y(
    players: Sequence[PlayerPositionSample],
    *,
    field_tilt: float | None = None,
    possession: float | None = None,
    ppda: float | None = None,
    team_opta: TeamMatchOptaStats | None = None,
) -> float | None:
    """Median Y of starting CBs (0-100), or calibrated Opta territorial proxy when only
    static formation coordinates (e.g. FotMob verticalLayout y=29.2) are available.
    """
    starters = [p for p in players if (p.is_starter or p.minutes >= 45) and p.avg_y is not None]

    # Use direct CB median Y whenever real tracking average positions exist
    if starters and not _is_static_formation_grid(starters):
        cbs = [float(p.avg_y) for p in starters if p.position == "CB" and p.avg_y is not None]
        if cbs:
            return round(max(0.0, min(100.0, float(median(cbs)))), 2)

        defs = [
            float(p.avg_y)
            for p in starters
            if p.position in ("CB", "LB", "RB") and p.avg_y is not None
        ]
        if defs:
            return round(max(0.0, min(100.0, float(median(defs)))), 2)

        outfield_ys = sorted(
            float(p.avg_y) for p in starters if p.position != "GK" and p.avg_y is not None
        )
        if len(outfield_ys) >= 3:
            return round(max(0.0, min(100.0, float(median(outfield_ys[:3])))), 2)

    # Calibrated Opta territorial proxy (Serie A distribution: mean ~41.5, range 32..54)
    has_opta = any(v is not None for v in (field_tilt, possession, ppda)) or (
        team_opta is not None
        and team_opta.own_half_passes is not None
        and team_opta.opp_half_passes is not None
    )
    if has_opta:
        ft = field_tilt if (field_tilt is not None and math.isfinite(field_tilt)) else 50.0
        poss = possession if (possession is not None and math.isfinite(possession)) else 50.0
        p_val = ppda if (ppda is not None and math.isfinite(ppda)) else 11.2
        opp_share = 0.42
        if (
            team_opta is not None
            and team_opta.own_half_passes is not None
            and team_opta.opp_half_passes is not None
        ):
            tot_p = team_opta.own_half_passes + team_opta.opp_half_passes
            if tot_p > 0:
                opp_share = team_opta.opp_half_passes / tot_p
        proxy = 24.0 + 0.16 * ft + 0.10 * poss + 10.5 * opp_share - 0.35 * (p_val - 11.0)
        return round(max(28.0, min(58.0, proxy)), 2)

    # Last fallback if static grid exists without Opta team counters
    if starters:
        cbs = [float(p.avg_y) for p in starters if p.position == "CB" and p.avg_y is not None]
        if cbs:
            return round(max(0.0, min(100.0, float(median(cbs)))), 2)
    return None


def infer_back_line_count(
    formation: str | None,
    players: Sequence[PlayerPositionSample],
) -> Literal[3, 4, 5] | None:
    """Extract back line count (3, 4, or 5) from formation string or defender layout."""
    clean = normalize_formation(formation)
    if clean:
        first_line = int(clean.split("-", 1)[0])
        if first_line <= 3:
            return 3
        if first_line == 4:
            return 4
        return 5

    starters = [p for p in players if p.is_starter or p.minutes >= 45]
    if not starters:
        return None

    cb_count = sum(1 for p in starters if p.position == "CB")
    fb_count = sum(1 for p in starters if p.position in ("LB", "RB"))
    wb_count = sum(1 for p in starters if p.position in ("LWB", "RWB"))

    if cb_count >= 3:
        return 5 if wb_count >= 2 and fb_count == 0 else 3
    if cb_count == 2 and fb_count >= 2:
        return 4
    total_back = cb_count + fb_count
    if total_back == 3:
        return 3
    if total_back == 4:
        return 4
    if total_back >= 5:
        return 5
    return None


def compute_ppda(
    *,
    team_id: int,
    events: Sequence[PitchEventSample],
    provider_ppda: float | None = None,
    team_opta: TeamMatchOptaStats | None = None,
    opp_opta: TeamMatchOptaStats | None = None,
    team_players: Sequence[PlayerPositionSample] = (),
) -> float | None:
    """Compute pressing intensity (PPDA — lower = more aggressive press).

    Priority:
      1. Direct provider PPDA (e.g. Understat).
      2. Event-level PPDA (opponent passes in y<=60 / team defensive actions in y>=40).
      3. Deterministic FotMob/Opta pressing-intensity proxy:
         (opp_own_half_passes + 0.20 * opp_opp_half_passes)
         / weighted high-zone defensive actions (tackles + interceptions + fouls).
    """
    if provider_ppda is not None and math.isfinite(provider_ppda) and provider_ppda >= 0:
        return round(float(provider_ppda), 2)

    # 2. Event-level PPDA when pass + defensive action events exist
    if events:
        opp_passes = sum(
            1 for e in events if e.team_id != team_id and e.event_type == "pass" and e.y <= 60.0
        )
        def_actions = sum(
            1
            for e in events
            if e.team_id == team_id and e.event_type in DEFENSIVE_ACTION_TYPES and e.y >= 40.0
        )
        if def_actions > 0 and opp_passes > 0:
            return round(opp_passes / def_actions, 2)

    # 3. Deterministic FotMob/Opta PPDA proxy
    if opp_opta is not None and opp_opta.own_half_passes is not None:
        opp_def60_passes = float(opp_opta.own_half_passes) + 0.20 * float(
            opp_opta.opp_half_passes or 0
        )

        # Prefer player-weighted high-zone defensive actions when individual counters exist
        weighted_def = 0.0
        has_player_def = False
        for p in team_players:
            if p.position == "GK" or p.minutes <= 0:
                continue
            t = p.tackles or 0
            i = p.interceptions or 0
            f = p.fouls or 0
            if p.tackles is not None or p.interceptions is not None or p.fouls is not None:
                has_player_def = True
            actions = float(t + i + f)
            if actions <= 0:
                continue
            y = p.avg_y if p.avg_y is not None else 50.0
            if y >= 55.0 or p.position in ("ST", "LW", "RW", "AM"):
                w = 1.00
            elif y >= 40.0 or p.position in ("DM", "CM", "LWB", "RWB"):
                w = 0.78
            else:
                w = 0.35
            weighted_def += w * actions

        if (not has_player_def or weighted_def < 1.0) and team_opta is not None:
            tot_def = (
                (team_opta.tackles or 0)
                + (team_opta.interceptions or 0)
                + (team_opta.fouls or 0)
            )
            weighted_def = 0.62 * float(tot_def)

        if weighted_def >= 1.0 and opp_def60_passes >= 0.0:
            ppda = opp_def60_passes / weighted_def
            if math.isfinite(ppda):
                return round(max(3.5, min(35.0, ppda)), 2)

    return None


def compute_field_tilt(
    *,
    team_id: int,
    events: Sequence[PitchEventSample],
    team_opta: TeamMatchOptaStats | None = None,
    opp_opta: TeamMatchOptaStats | None = None,
    team_players: Sequence[PlayerPositionSample] = (),
    opp_players: Sequence[PlayerPositionSample] = (),
) -> float | None:
    """Share of final-third / opposition-half territory in [0, 100]."""
    # 1. Opta opposition-half passes + box touches (exact from FotMob)
    if (
        team_opta is not None
        and opp_opta is not None
        and team_opta.opp_half_passes is not None
        and opp_opta.opp_half_passes is not None
    ):
        t_val = float(team_opta.opp_half_passes) + 2.0 * float(team_opta.touches_opp_box or 0)
        o_val = float(opp_opta.opp_half_passes) + 2.0 * float(opp_opta.touches_opp_box or 0)
        if t_val + o_val > 0:
            return round(max(0.0, min(100.0, (t_val / (t_val + o_val)) * 100.0)), 2)

    # 2. Event stream final-third share
    team_f3 = sum(
        1
        for e in events
        if e.team_id == team_id and e.event_type in ATTACK_EVENT_TYPES and e.y >= 66.7
    )
    opp_f3 = sum(
        1
        for e in events
        if e.team_id != team_id and e.event_type in ATTACK_EVENT_TYPES and e.y >= 66.7
    )
    total_f3 = team_f3 + opp_f3
    if total_f3 > 0:
        return round(max(0.0, min(100.0, (team_f3 / total_f3) * 100.0)), 2)

    # 3. Proxy from player average Y & progressive actions
    def _territory_weight(players: Sequence[PlayerPositionSample]) -> float:
        score = 0.0
        for p in players:
            if p.position == "GK" or p.minutes <= 0:
                continue
            y = p.avg_y if p.avg_y is not None else 50.0
            prog = float(p.progressive_actions or 0)
            score += (max(0.0, y - 40.0) / 60.0) * (1.0 + prog * 0.35) * (p.minutes / 90.0)
        return score

    tw = _territory_weight(team_players)
    ow = _territory_weight(opp_players)
    if tw + ow > 0:
        return round(max(0.0, min(100.0, (tw / (tw + ow)) * 100.0)), 2)
    return None


def compute_attack_bias(
    *,
    team_id: int,
    events: Sequence[PitchEventSample],
    team_opta: TeamMatchOptaStats | None = None,
    team_players: Sequence[PlayerPositionSample] = (),
) -> tuple[float | None, float | None, float | None]:
    """Compute Left / Center / Right attacking share summing to exactly 100.0."""
    if (
        team_opta is not None
        and team_opta.attack_bias_left is not None
        and team_opta.attack_bias_center is not None
        and team_opta.attack_bias_right is not None
    ):
        total = (
            team_opta.attack_bias_left
            + team_opta.attack_bias_center
            + team_opta.attack_bias_right
        )
        if total > 0:
            l_pct = round((team_opta.attack_bias_left / total) * 100.0, 2)
            c_pct = round((team_opta.attack_bias_center / total) * 100.0, 2)
            r_pct = round(max(0.0, 100.0 - l_pct - c_pct), 2)
            return l_pct, c_pct, r_pct

    left_w = 0.0
    center_w = 0.0
    right_w = 0.0

    attack_events = [
        e
        for e in events
        if e.team_id == team_id and e.event_type in ATTACK_EVENT_TYPES and e.y >= 50.0
    ]
    for e in attack_events:
        weight = 2.0 if e.event_type == "shot" else 1.0
        if e.x < 33.33:
            left_w += weight
        elif e.x <= 66.67:
            center_w += weight
        else:
            right_w += weight

    if left_w + center_w + right_w == 0.0:
        for p in team_players:
            if p.position == "GK" or p.avg_x is None or p.minutes <= 0:
                continue
            if p.avg_y is not None and p.avg_y < 42.0:
                continue
            weight = (1.0 + float(p.progressive_actions or 0) * 0.5) * (p.minutes / 90.0)
            if p.avg_x < 33.33:
                left_w += weight
            elif p.avg_x <= 66.67:
                center_w += weight
            else:
                right_w += weight

    total = left_w + center_w + right_w
    if total <= 0.0:
        return None, None, None

    left_pct = round((left_w / total) * 100.0, 2)
    center_pct = round((center_w / total) * 100.0, 2)
    right_pct = round(max(0.0, 100.0 - left_pct - center_pct), 2)
    return left_pct, center_pct, right_pct


def _band_from_y(y: float) -> Literal[0, 1, 2]:
    if y < 100.0 / 3.0:
        return 0
    if y < 200.0 / 3.0:
        return 1
    return 2


def build_dribbles_zones(
    player_stats: Sequence[PlayerMatchStatsUpsert],
    *,
    team_id: int,
) -> DribblesZones | None:
    """Aggregate dribbles conceded (`dribbles_past`) & produced (`dribbles_won`)
    across the 5 corridors x 3 height bands for `team_match_tactics.dribbles_zones_json`.
    """
    rows = [ps for ps in player_stats if ps.team_id == team_id and ps.minutes > 0]
    if not rows:
        return None

    has_any_dribble_col = any(
        ps.dribbles_past is not None or ps.dribbles_won is not None for ps in rows
    )
    if not has_any_dribble_col:
        return None

    conceded_cells: dict[tuple[ZoneCorridor, Literal[0, 1, 2]], dict[int, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    produced_cells: dict[tuple[ZoneCorridor, Literal[0, 1, 2]], dict[int, int]] = defaultdict(
        lambda: defaultdict(int)
    )

    for ps in rows:
        corridor = (
            ps.zone_corridor
            if ps.zone_corridor is not None
            else (
                corridor_from_x(ps.avg_x)
                if ps.avg_x is not None
                else position_default_corridor(ps.position_played)
            )
        )
        y_val = ps.avg_y if ps.avg_y is not None else 50.0
        band = _band_from_y(y_val)

        if ps.dribbles_past and ps.dribbles_past > 0:
            conceded_cells[(corridor, band)][ps.player_id] += ps.dribbles_past
        if ps.dribbles_won and ps.dribbles_won > 0:
            produced_cells[(corridor, band)][ps.player_id] += ps.dribbles_won

    def _serialize(
        bucket: dict[tuple[ZoneCorridor, Literal[0, 1, 2]], dict[int, int]],
    ) -> tuple[list[DribbleZoneCell], int]:
        cells: list[DribbleZoneCell] = []
        total = 0
        for (corridor, band), pmap in sorted(bucket.items()):
            players_list = [
                DribbleZonePlayer(player_id=pid, count=cnt)
                for pid, cnt in sorted(pmap.items(), key=lambda kv: kv[1], reverse=True)
            ]
            cell_sum = sum(p.count for p in players_list)
            total += cell_sum
            cells.append(
                DribbleZoneCell(
                    corridor=corridor,
                    band=band,
                    count=cell_sum,
                    players=players_list,
                )
            )
        return cells, total

    conceded_list, tot_conc = _serialize(conceded_cells)
    produced_list, tot_prod = _serialize(produced_cells)
    return DribblesZones(
        conceded=conceded_list,
        produced=produced_list,
        total_conceded=tot_conc,
        total_produced=tot_prod,
    )


def build_team_match_fingerprint(
    *,
    match_id: int,
    team_id: int,
    formation: str | None,
    possession: float | None,
    provider_ppda: float | None,
    team_players: Sequence[PlayerPositionSample],
    opp_players: Sequence[PlayerPositionSample],
    events: Sequence[PitchEventSample],
    team_opta: TeamMatchOptaStats | None = None,
    opp_opta: TeamMatchOptaStats | None = None,
    player_stats: Sequence[PlayerMatchStatsUpsert] = (),
) -> TeamMatchTacticsUpsert:
    """Assemble the deterministic tactical fingerprint for one team in one match."""
    clean_form = normalize_formation(formation)
    back_line = infer_back_line_count(clean_form, team_players)
    ppda = compute_ppda(
        team_id=team_id,
        events=events,
        provider_ppda=provider_ppda,
        team_opta=team_opta,
        opp_opta=opp_opta,
        team_players=team_players,
    )
    field_tilt = compute_field_tilt(
        team_id=team_id,
        events=events,
        team_opta=team_opta,
        opp_opta=opp_opta,
        team_players=team_players,
        opp_players=opp_players,
    )
    clean_poss = _finite(possession)
    if clean_poss is not None:
        clean_poss = round(max(0.0, min(100.0, clean_poss)), 2)

    def_line_y = compute_defensive_line_y(
        team_players,
        field_tilt=field_tilt,
        possession=clean_poss,
        ppda=ppda,
        team_opta=team_opta,
    )
    bias_l, bias_c, bias_r = compute_attack_bias(
        team_id=team_id,
        events=events,
        team_opta=team_opta,
        team_players=team_players,
    )

    shots_against = [
        ShotPoint(x=e.x, y=e.y, xg=float(e.xg or 0.0), is_goal=e.is_goal)
        for e in events
        if e.team_id != team_id and e.event_type == "shot"
    ]
    xga_zones: XgaZones | None = build_xga_zones(shots_against) if shots_against else None
    dribbles_zones = build_dribbles_zones(player_stats, team_id=team_id) if player_stats else None

    return TeamMatchTacticsUpsert(
        match_id=match_id,
        team_id=team_id,
        formation=clean_form,
        baseline_formation=None,
        back_line_count=back_line,
        possession=clean_poss,
        ppda=ppda,
        field_tilt=field_tilt,
        avg_def_line_y=def_line_y,
        attack_bias_left=bias_l,
        attack_bias_center=bias_c,
        attack_bias_right=bias_r,
        is_tactical_shift=False,
        shift_reason=None,
        xga_zones_json=xga_zones,
        dribbles_zones_json=dribbles_zones,
    )

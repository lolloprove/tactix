"""Conditional Splits Engine — THE CORE OF TACTIX (ZERO AI).

1. Team Conditional Splits (`compute_team_splits`):
   Delta xG, xGA, and dribbles conceded vs the team's own season baseline across:
     - `vs_formation`: opponent formation (e.g. "3-5-2", "4-3-3")
     - `vs_back_line`: opponent back line count ("3", "4", "5")
     - `vs_high_line`: opponent defensive line height bucket ("high", "mid", "low")
     - `vs_archetype`: opponent offensive / flank archetypes (starting >= 45')

2. Player Conditional Splits (`compute_player_splits`):
   Spatial opposite-corridor pairing (e.g. LW in `left` vs opponent RB/RWB/RCB in
   `right`, falling back to adjacent facing corridor if needed) to compute
   minutes-weighted `rating_delta`, `dribbles_delta`, and `duels_delta` vs:
     - `vs_defender_archetype` (for attackers/wingers/WBs/mids facing opposing defenders)
     - `vs_attacker_archetype` (for defenders/DMs facing opposing attackers/wingers/WBs)
     - `vs_line_height` ("high", "mid", "low" of opponent defensive line)
     - `vs_formation` (opponent formation)

Every split ALWAYS carries a `confidence` badge (`low` / `medium` / `high`)
computed via `engine.confidence`. Missing data stays `None`, never `0` or `NaN`.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from db.models import (
    ConfidenceLevel,
    PlayerArchetype,
    PlayerConditionalSplitUpsert,
    PlayerConditionType,
    PlayerMatchStatsUpsert,
    PlayerPosition,
    TeamConditionalSplitUpsert,
    TeamConditionType,
    TeamMatchTacticsUpsert,
    ZoneCorridor,
)
from engine.confidence import from_matches, from_minutes
from engine.pitch import (
    corridor_from_x,
    facing_corridors,
    line_height,
    position_default_corridor,
)

# Offensive/flank archetypes tracked in team `vs_archetype` splits
OFFENSIVE_ARCHETYPES: frozenset[PlayerArchetype] = frozenset(
    {
        "ala_dribblatrice",
        "ala_inversa",
        "quinto",
        "terzino_spinta",
        "prima_punta",
        "seconda_punta",
        "attaccante_profondita",
        "falso_nove",
        "trequartista",
        "mezzala",
    }
)

DEFENSIVE_POSITIONS: frozenset[PlayerPosition] = frozenset({"CB", "LB", "RB", "LWB", "RWB", "DM"})
ATTACKING_POSITIONS: frozenset[PlayerPosition] = frozenset(
    {"ST", "LW", "RW", "AM", "LWB", "RWB", "CM"}
)
PURE_DEFENDER_POSITIONS: frozenset[PlayerPosition] = frozenset({"CB", "LB", "RB", "DM"})


@dataclass(frozen=True)
class FinishedMatchContext:
    match_id: int
    season: str
    round: int
    home_team_id: int
    away_team_id: int
    home_xg: float | None
    away_xg: float | None


@dataclass(frozen=True)
class TeamSplitResult:
    row: TeamConditionalSplitUpsert
    confidence: ConfidenceLevel


@dataclass(frozen=True)
class PlayerSplitResult:
    row: PlayerConditionalSplitUpsert
    confidence: ConfidenceLevel


def _safe_mean(values: Sequence[float]) -> float | None:
    clean = [float(v) for v in values if v is not None and math.isfinite(v)]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _safe_delta(cond_val: float | None, base_val: float | None) -> float | None:
    if cond_val is None or base_val is None:
        return None
    diff = cond_val - base_val
    return round(diff, 2) if math.isfinite(diff) else None


def _player_corridor(stat: PlayerMatchStatsUpsert) -> ZoneCorridor:
    if stat.zone_corridor is not None:
        return stat.zone_corridor
    if stat.avg_x is not None and math.isfinite(stat.avg_x):
        return corridor_from_x(stat.avg_x)
    return position_default_corridor(stat.position_played)


def compute_team_splits(
    *,
    season: str,
    matches: Sequence[FinishedMatchContext],
    tactics: Sequence[TeamMatchTacticsUpsert],
    player_stats: Sequence[PlayerMatchStatsUpsert],
    player_archetypes: dict[int, PlayerArchetype | None],
) -> list[TeamSplitResult]:
    """Compute all team conditional splits for `season` with confidence badges."""
    tactics_by_key: dict[tuple[int, int], TeamMatchTacticsUpsert] = {
        (t.match_id, t.team_id): t for t in tactics
    }

    # Group player stats by (match_id, team_id)
    stats_by_mt: dict[tuple[int, int], list[PlayerMatchStatsUpsert]] = defaultdict(list)
    for ps in player_stats:
        stats_by_mt[(ps.match_id, ps.team_id)].append(ps)

    # Collect per-team match rows: (match_id, opp_id, xg, xga, dribbles_conceded)
    team_matches: dict[int, list[tuple[int, int, float | None, float | None, float | None]]] = (
        defaultdict(list)
    )

    for m in matches:
        for team_id, opp_id, xg, xga in (
            (m.home_team_id, m.away_team_id, m.home_xg, m.away_xg),
            (m.away_team_id, m.home_team_id, m.away_xg, m.home_xg),
        ):
            team_ps = stats_by_mt.get((m.match_id, team_id), [])
            dp_vals = [ps.dribbles_past for ps in team_ps if ps.dribbles_past is not None]
            dribbles_conceded = float(sum(dp_vals)) if dp_vals else None
            team_matches[team_id].append((m.match_id, opp_id, xg, xga, dribbles_conceded))

    results: list[TeamSplitResult] = []

    for team_id, rows in team_matches.items():
        base_xg = _safe_mean([r[2] for r in rows if r[2] is not None])
        base_xga = _safe_mean([r[3] for r in rows if r[3] is not None])
        base_drib = _safe_mean([r[4] for r in rows if r[4] is not None])

        # condition_key -> list of (xg, xga, dribbles_conceded)
        buckets: dict[
            tuple[TeamConditionType, str],
            list[tuple[float | None, float | None, float | None]],
        ] = defaultdict(list)

        for match_id, opp_id, xg, xga, drib_conc in rows:
            opp_tac = tactics_by_key.get((match_id, opp_id))
            metrics = (xg, xga, drib_conc)

            if opp_tac is not None:
                if opp_tac.formation:
                    buckets[("vs_formation", opp_tac.formation)].append(metrics)
                if opp_tac.back_line_count is not None:
                    buckets[("vs_back_line", str(opp_tac.back_line_count))].append(metrics)
                if opp_tac.avg_def_line_y is not None and math.isfinite(opp_tac.avg_def_line_y):
                    buckets[("vs_high_line", line_height(opp_tac.avg_def_line_y))].append(metrics)

            # Opponent offensive/flank archetypes who played >= 45 min in this match
            opp_ps = stats_by_mt.get((match_id, opp_id), [])
            seen_archs: set[PlayerArchetype] = set()
            for ps in opp_ps:
                if ps.minutes < 45:
                    continue
                arch = player_archetypes.get(ps.player_id)
                if arch is not None and arch in OFFENSIVE_ARCHETYPES:
                    seen_archs.add(arch)
            for arch in seen_archs:
                buckets[("vs_archetype", arch)].append(metrics)

        for (cond_type, cond_value), items in sorted(buckets.items()):
            sample_matches = len(items)
            if sample_matches == 0:
                continue
            cond_xg = _safe_mean([x[0] for x in items if x[0] is not None])
            cond_xga = _safe_mean([x[1] for x in items if x[1] is not None])
            cond_drib = _safe_mean([x[2] for x in items if x[2] is not None])

            upsert = TeamConditionalSplitUpsert(
                team_id=team_id,
                season=season,
                condition_type=cond_type,
                condition_value=cond_value,
                sample_matches=sample_matches,
                xg_delta=_safe_delta(cond_xg, base_xg),
                xga_delta=_safe_delta(cond_xga, base_xga),
                dribbles_conceded_delta=_safe_delta(cond_drib, base_drib),
            )
            results.append(TeamSplitResult(row=upsert, confidence=from_matches(sample_matches)))

    return results


def _weighted_rating(entries: Sequence[PlayerMatchStatsUpsert]) -> float | None:
    num = 0.0
    den = 0
    for e in entries:
        if e.rating is not None and math.isfinite(e.rating) and e.minutes > 0:
            num += e.rating * e.minutes
            den += e.minutes
    if den <= 0:
        return None
    return num / den


def _weighted_p90(entries: Sequence[PlayerMatchStatsUpsert], attr: str) -> float | None:
    total_stat = 0.0
    total_mins = 0
    for e in entries:
        val = getattr(e, attr)
        if val is not None and math.isfinite(val) and e.minutes > 0:
            total_stat += float(val)
            total_mins += e.minutes
    if total_mins <= 0:
        return None
    return (total_stat / total_mins) * 90.0


def _find_direct_opponents(
    player_stat: PlayerMatchStatsUpsert,
    opp_stats: Sequence[PlayerMatchStatsUpsert],
    *,
    want_defenders: bool,
) -> list[PlayerMatchStatsUpsert]:
    """Spatial opposite-corridor matchup pairing.

    Searches first the exact opposite corridor (e.g. `left` vs `right`), then
    adjacent facing corridors if no qualifying opponent is in the exact lane.
    """
    my_corridor = _player_corridor(player_stat)
    target_lanes = facing_corridors(my_corridor)
    role_filter = DEFENSIVE_POSITIONS if want_defenders else ATTACKING_POSITIONS

    qualifying = [
        o
        for o in opp_stats
        if o.minutes >= 30
        and o.position_played != "GK"
        and (o.position_played in role_filter if o.position_played is not None else True)
    ]
    if not qualifying:
        return []

    # Exact opposite corridor first
    exact_lane = target_lanes[0]
    exact = [o for o in qualifying if _player_corridor(o) == exact_lane]
    if exact:
        return exact

    # Adjacent facing corridor fallback
    adj_lanes = set(target_lanes[1:])
    return [o for o in qualifying if _player_corridor(o) in adj_lanes]


def compute_player_splits(
    *,
    season: str,
    tactics: Sequence[TeamMatchTacticsUpsert],
    player_stats: Sequence[PlayerMatchStatsUpsert],
    player_archetypes: dict[int, PlayerArchetype | None],
    min_match_minutes: int = 20,
) -> list[PlayerSplitResult]:
    """Compute player conditional splits via opposite-corridor spatial pairing & tactical context."""
    tactics_by_key: dict[tuple[int, int], TeamMatchTacticsUpsert] = {
        (t.match_id, t.team_id): t for t in tactics
    }
    stats_by_mt: dict[tuple[int, int], list[PlayerMatchStatsUpsert]] = defaultdict(list)
    stats_by_player: dict[int, list[PlayerMatchStatsUpsert]] = defaultdict(list)

    for ps in player_stats:
        stats_by_mt[(ps.match_id, ps.team_id)].append(ps)
        if ps.minutes >= min_match_minutes:
            stats_by_player[ps.player_id].append(ps)

    results: list[PlayerSplitResult] = []

    for player_id, entries in stats_by_player.items():
        if not entries:
            continue

        # Season baselines
        base_rating = _weighted_rating(entries)
        base_drib_won = _weighted_p90(entries, "dribbles_won")
        base_drib_past = _weighted_p90(entries, "dribbles_past")
        base_duels_won = _weighted_p90(entries, "duels_won")

        # Determine if player is primarily defensive (for dribbles_delta convention)
        def_mins = sum(e.minutes for e in entries if e.position_played in PURE_DEFENDER_POSITIONS)
        total_mins = sum(e.minutes for e in entries)
        is_primary_defender = (def_mins / total_mins) >= 0.5 if total_mins > 0 else False

        # condition_key -> list of matching PlayerMatchStatsUpsert (deduplicated per match)
        buckets: dict[tuple[PlayerConditionType, str], dict[int, PlayerMatchStatsUpsert]] = (
            defaultdict(dict)
        )

        for entry in entries:
            opp_tac = tactics_by_key.get((entry.match_id, entry.opponent_id))
            if opp_tac is not None:
                if opp_tac.formation:
                    buckets[("vs_formation", opp_tac.formation)][entry.match_id] = entry
                if opp_tac.avg_def_line_y is not None and math.isfinite(opp_tac.avg_def_line_y):
                    buckets[("vs_line_height", line_height(opp_tac.avg_def_line_y))][
                        entry.match_id
                    ] = entry

            opp_team_stats = stats_by_mt.get((entry.match_id, entry.opponent_id), [])
            if not opp_team_stats or entry.position_played == "GK":
                continue

            # Attacker / wing / wing-back / midfielder vs opposing defender archetype
            if entry.position_played is None or entry.position_played in ATTACKING_POSITIONS:
                def_opps = _find_direct_opponents(entry, opp_team_stats, want_defenders=True)
                for opp in def_opps:
                    arch = player_archetypes.get(opp.player_id)
                    if arch is not None:
                        buckets[("vs_defender_archetype", arch)][entry.match_id] = entry

            # Defender / DM / wing-back vs opposing attacker archetype
            if entry.position_played in DEFENSIVE_POSITIONS:
                att_opps = _find_direct_opponents(entry, opp_team_stats, want_defenders=False)
                for opp in att_opps:
                    arch = player_archetypes.get(opp.player_id)
                    if arch is not None:
                        buckets[("vs_attacker_archetype", arch)][entry.match_id] = entry

        for (cond_type, cond_value), match_map in sorted(buckets.items()):
            cond_entries = list(match_map.values())
            sample_minutes = sum(e.minutes for e in cond_entries)
            if sample_minutes <= 0:
                continue

            cond_rating = _weighted_rating(cond_entries)
            cond_duels = _weighted_p90(cond_entries, "duels_won")

            # Convention aligned with DESIGN.md §1 & mock-data.ts:
            # - vs_attacker_archetype (defenders): dribbles_past/90 delta (+ = more vulnerable)
            # - vs_defender_archetype (attackers): dribbles_won/90 delta (+ = stronger edge)
            if cond_type == "vs_attacker_archetype" or (
                cond_type in ("vs_formation", "vs_line_height") and is_primary_defender
            ):
                cond_drib = _weighted_p90(cond_entries, "dribbles_past")
                drib_delta = _safe_delta(cond_drib, base_drib_past)
            else:
                cond_drib = _weighted_p90(cond_entries, "dribbles_won")
                drib_delta = _safe_delta(cond_drib, base_drib_won)

            upsert = PlayerConditionalSplitUpsert(
                player_id=player_id,
                season=season,
                condition_type=cond_type,
                condition_value=cond_value,
                sample_minutes=sample_minutes,
                rating_delta=_safe_delta(cond_rating, base_rating),
                dribbles_delta=drib_delta,
                duels_delta=_safe_delta(cond_duels, base_duels_won),
            )
            results.append(PlayerSplitResult(row=upsert, confidence=from_minutes(sample_minutes)))

    return results

"""Match events & individual stats adapter using `curl_cffi` (PoliteHttpClient).

Primary source: FotMob (Serie A league_id=55, `/api/data/*`).
Automatic fallback: SofaScore (Serie A unique-tournament=23).

Extracts per-match individual stats (dribbles_won, dribbles_past, duels_won,
duels_lost, progressive_actions, tackles, interceptions, fouls, recoveries,
xg, xa, rating, minutes), starter positions, team Opta passing/pressing totals
(own_half_passes, opp_half_passes, tackles, interceptions, fouls, attackingZones),
and shotmap coordinates normalised into the Tactix 0-100 frame.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

from adapters.base import (
    EventDTO,
    FixtureDTO,
    MatchDTO,
    PlayerLineDTO,
    Source,
    SourceAdapter,
    TeamLineDTO,
)
from adapters.http import BlockedError, PoliteHttpClient
from db.models import MatchStatus, PlayerPosition

log = logging.getLogger(__name__)

FOTMOB_BASE = "https://www.fotmob.com/api/data"
FOTMOB_SERIE_A_ID = 55

SOFASCORE_BASE = "https://api.sofascore.com/api/v1"
SOFASCORE_SERIE_A_ID = 23

_FORMATION_RE = re.compile(r"^\d(-\d){2,4}$")

_POS_MAP: dict[str, PlayerPosition] = {
    "G": "GK",
    "GK": "GK",
    "D": "CB",
    "DC": "CB",
    "CB": "CB",
    "LCB": "CB",
    "RCB": "CB",
    "DL": "LB",
    "LB": "LB",
    "DR": "RB",
    "RB": "RB",
    "LWB": "LWB",
    "RWB": "RWB",
    "M": "CM",
    "DM": "DM",
    "CDM": "DM",
    "CM": "CM",
    "LCM": "CM",
    "RCM": "CM",
    "LM": "LW",
    "RM": "RW",
    "AM": "AM",
    "CAM": "AM",
    "LW": "LW",
    "RW": "RW",
    "F": "ST",
    "ST": "ST",
    "CF": "ST",
    "LS": "ST",
    "RS": "ST",
}

# FotMob specific numeric positionId codes (Opta formation slots)
_FOTMOB_POSITION_ID_MAP: dict[int, PlayerPosition] = {
    11: "GK",
    32: "LB",
    33: "CB",
    34: "CB",
    35: "CB",
    36: "CB",
    37: "CB",
    38: "RB",
    51: "LWB",
    52: "LWB",
    58: "RWB",
    59: "RWB",
    62: "LWB",
    63: "DM",
    64: "DM",
    65: "DM",
    66: "DM",
    67: "DM",
    68: "RWB",
    71: "LW",
    72: "CM",
    73: "CM",
    74: "CM",
    75: "CM",
    76: "CM",
    77: "CM",
    78: "CM",
    79: "RW",
    82: "LW",
    83: "AM",
    84: "AM",
    85: "AM",
    86: "AM",
    87: "AM",
    88: "RW",
    103: "LW",
    104: "ST",
    105: "ST",
    106: "ST",
    107: "RW",
    115: "ST",
}


def _clamp(val: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, val))


def _safe_float(val: Any) -> float | None:
    if val is None or val == "":
        return None
    if isinstance(val, dict):
        val = val.get("value")
    if isinstance(val, str):
        cleaned = val.strip().rstrip("%")
        if "(" in cleaned:
            cleaned = cleaned.split("(", 1)[0].strip()
        if "/" in cleaned:
            cleaned = cleaned.split("/", 1)[0].strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _safe_int(val: Any) -> int | None:
    f = _safe_float(val)
    return round(f) if f is not None else None


def _clean_formation(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = raw.strip().replace(" ", "")
    return cleaned if _FORMATION_RE.match(cleaned) else None


def _infer_position_from_coords(
    x: float | None,
    y: float | None,
    role_hint: str | int | None,
    *,
    position_id: int | None = None,
) -> PlayerPosition:
    if position_id is not None and position_id in _FOTMOB_POSITION_ID_MAP:
        return _FOTMOB_POSITION_ID_MAP[position_id]

    if isinstance(role_hint, str) and role_hint.strip():
        key = role_hint.strip().upper()
        if key in _POS_MAP:
            return _POS_MAP[key]

    # FotMob usualPlayingPositionId: 0=GK, 1=DEF, 2=MID, 3=FWD
    if isinstance(role_hint, int):
        if role_hint == 0:
            return "GK"
        if role_hint == 1:
            if x is not None and x < 24:
                return "LB"
            if x is not None and x > 76:
                return "RB"
            return "CB"
        if role_hint == 2:
            if x is not None and x < 20:
                return "LWB" if (y is not None and y < 55) else "LW"
            if x is not None and x > 80:
                return "RWB" if (y is not None and y < 55) else "RW"
            if y is not None and y < 46:
                return "DM"
            if y is not None and y > 68:
                return "AM"
            return "CM"
        if role_hint == 3:
            if x is not None and x < 26:
                return "LW"
            if x is not None and x > 74:
                return "RW"
            return "ST"

    if x is None or y is None:
        return "CM"
    if y < 14:
        return "GK"
    if y < 38:
        if x < 24:
            return "LB"
        if x > 76:
            return "RB"
        return "CB"
    if y < 52:
        if x < 20:
            return "LWB"
        if x > 80:
            return "RWB"
        return "DM"
    if y < 68:
        return "CM"
    if y < 78:
        if x < 28:
            return "LW"
        if x > 72:
            return "RW"
        return "AM"
    if x < 26:
        return "LW"
    if x > 74:
        return "RW"
    return "ST"


def normalize_sofascore_avg_pos(avg_x: float, avg_y: float) -> tuple[float, float]:
    """SofaScore uses averageX (0..100 own->opp goal) and averageY (100=left, 0=right)."""
    tactix_x = round(_clamp(100.0 - avg_y), 2)
    tactix_y = round(_clamp(avg_x), 2)
    return tactix_x, tactix_y


def normalize_fotmob_layout_pos(layout_x: float, layout_y: float) -> tuple[float, float]:
    """FotMob verticalLayout: x in [0..1] (0=left, 1=right), y in [0..1] (0=own, 1=opp)."""
    sx = layout_x * 100.0 if layout_x <= 1.0 else layout_x
    sy = layout_y * 100.0 if layout_y <= 1.0 else layout_y
    return round(_clamp(sx), 2), round(_clamp(sy), 2)


class FotMobAdapter(SourceAdapter):
    source: Source = "fotmob"

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.fotmob.com/",
            "Origin": "https://www.fotmob.com",
        }

    def fetch_fixtures(self, season: str) -> list[FixtureDTO]:
        data = self.http.get_json(
            f"{FOTMOB_BASE}/leagues",
            params={"id": FOTMOB_SERIE_A_ID, "season": season},
            headers=self._headers(),
        )
        matches_raw = (
            (data.get("fixtures") or {}).get("allMatches")
            or (data.get("matches") or {}).get("allMatches")
            or []
        )
        fixtures: list[FixtureDTO] = []

        for m in matches_raw:
            mid = _safe_int(m.get("id"))
            home = m.get("home") or {}
            away = m.get("away") or {}
            hid = _safe_int(home.get("id"))
            aid = _safe_int(away.get("id"))
            if mid is None or hid is None or aid is None:
                continue

            status_obj = m.get("status") or {}
            if status_obj.get("cancelled"):
                status: MatchStatus = "cancelled"
            elif status_obj.get("finished"):
                status = "finished"
            elif status_obj.get("started"):
                status = "live"
            else:
                status = "scheduled"

            utc_str = status_obj.get("utcTime") or "2026-08-22T18:00:00Z"
            kickoff = datetime.fromisoformat(str(utc_str).replace("Z", "+00:00")).astimezone(UTC)

            score_str = str(status_obj.get("scoreStr") or "")
            h_goals, a_goals = None, None
            if " - " in score_str:
                parts = score_str.split(" - ")
                h_goals = _safe_int(parts[0])
                a_goals = _safe_int(parts[1])

            fixtures.append(
                FixtureDTO(
                    source="fotmob",
                    external_id=mid,
                    season=season,
                    round=max(1, min(38, _safe_int(m.get("round")) or 1)),
                    kickoff_at=kickoff,
                    home_external_id=hid,
                    away_external_id=aid,
                    status=status,
                    home_team_name=home.get("name"),
                    away_team_name=away.get("name"),
                    home_goals=h_goals,
                    away_goals=a_goals,
                )
            )
        return fixtures

    def _extract_team_stats(
        self,
        stats_section: dict[str, Any],
        attacking_zones: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Parse FotMob content.stats.Periods.All + content.attackingZones for (home, away)."""
        home_s: dict[str, Any] = {}
        away_s: dict[str, Any] = {}

        periods = (stats_section.get("Periods") or {}).get("All") or {}
        for block in periods.get("stats") or []:
            for item in block.get("stats") or []:
                key = str(item.get("key") or "").strip()
                vals = item.get("stats") or []
                if len(vals) != 2 or vals[0] is None or vals[1] is None:
                    continue

                if key == "BallPossesion":
                    home_s["possession"] = _safe_float(vals[0])
                    away_s["possession"] = _safe_float(vals[1])
                elif key == "expected_goals":
                    home_s["xg"] = _safe_float(vals[0])
                    away_s["xg"] = _safe_float(vals[1])
                elif key == "own_half_passes":
                    home_s["own_half_passes"] = _safe_int(vals[0])
                    away_s["own_half_passes"] = _safe_int(vals[1])
                elif key == "opposition_half_passes":
                    home_s["opp_half_passes"] = _safe_int(vals[0])
                    away_s["opp_half_passes"] = _safe_int(vals[1])
                elif key == "matchstats.headers.tackles":
                    home_s["tackles"] = _safe_int(vals[0])
                    away_s["tackles"] = _safe_int(vals[1])
                elif key == "interceptions":
                    home_s["interceptions"] = _safe_int(vals[0])
                    away_s["interceptions"] = _safe_int(vals[1])
                elif key == "fouls":
                    home_s["fouls"] = _safe_int(vals[0])
                    away_s["fouls"] = _safe_int(vals[1])
                elif key == "touches_opp_box":
                    home_s["touches_opp_box"] = _safe_int(vals[0])
                    away_s["touches_opp_box"] = _safe_int(vals[1])

        if isinstance(attacking_zones, dict):
            for side_key, dest in (("home", home_s), ("away", away_s)):
                tot = (attacking_zones.get(side_key) or {}).get("total") or {}
                l_val = _safe_float(tot.get("left"))
                c_val = _safe_float(tot.get("center"))
                r_val = _safe_float(tot.get("right"))
                if l_val is not None and c_val is not None and r_val is not None:
                    s_sum = l_val + c_val + r_val
                    if s_sum > 0:
                        l_pct = round((l_val / s_sum) * 100.0, 2)
                        c_pct = round((c_val / s_sum) * 100.0, 2)
                        r_pct = round(max(0.0, 100.0 - l_pct - c_pct), 2)
                        dest["attack_bias_left"] = l_pct
                        dest["attack_bias_center"] = c_pct
                        dest["attack_bias_right"] = r_pct

        return home_s, away_s

    def _extract_player_stats_map(
        self,
        player_stats_section: dict[str, Any],
    ) -> dict[int, dict[str, float | int | None]]:
        """Parse FotMob content.playerStats keyed by player_id."""
        result: dict[int, dict[str, float | int | None]] = {}
        for pid_str, pdata in (player_stats_section or {}).items():
            pid = _safe_int(pid_str)
            if pid is None or not isinstance(pdata, dict):
                continue
            sections = pdata.get("stats") or []
            if not sections:
                continue

            flat: dict[str, Any] = {}
            for section in sections:
                for label, stat_obj in (section.get("stats") or {}).items():
                    if not isinstance(stat_obj, dict):
                        continue
                    key = str(stat_obj.get("key") or label).lower()
                    val = stat_obj.get("stat", stat_obj)
                    flat[key] = val.get("value") if isinstance(val, dict) else val

            mins = _safe_int(flat.get("minutes_played"))
            has_played = (mins or 0) > 0

            # FotMob `duel_won` / `duel_lost` already combine ground + aerial duels.
            duels_won = _safe_int(flat.get("duel_won"))
            duels_lost = _safe_int(flat.get("duel_lost"))
            if duels_won is None and has_played:
                gw = _safe_int(flat.get("ground_duels_won")) or 0
                aw = _safe_int(flat.get("aerials_won")) or 0
                duels_won = gw + aw
            if duels_lost is None and has_played:
                duels_lost = 0

            drib_won = _safe_int(
                flat.get("dribbles_succeeded") or flat.get("successful_dribbles")
            )
            drib_past = _safe_int(flat.get("dribbled_past"))
            if has_played:
                drib_won = drib_won if drib_won is not None else 0
                drib_past = drib_past if drib_past is not None else 0

            passes_f3 = _safe_int(flat.get("passes_into_final_third")) or 0
            line_break = _safe_int(flat.get("line_breaking_passes")) or 0
            chances = _safe_int(flat.get("chances_created")) or 0
            prog_carries = _safe_int(flat.get("progressive_carries")) or 0
            progressive = (passes_f3 + line_break + prog_carries + chances) if has_played else None

            tackles = _safe_int(flat.get("matchstats.headers.tackles") or flat.get("tackles"))
            interceptions = _safe_int(flat.get("interceptions"))
            fouls = _safe_int(flat.get("fouls"))
            recoveries = _safe_int(flat.get("recoveries"))
            def_actions = _safe_int(flat.get("defensive_actions"))

            xg_val = _safe_float(flat.get("expected_goals"))
            xa_val = _safe_float(flat.get("expected_assists"))
            if has_played:
                xg_val = xg_val if xg_val is not None else 0.0
                xa_val = xa_val if xa_val is not None else 0.0

            result[pid] = {
                "minutes": mins,
                "rating": _safe_float(flat.get("rating_title") or flat.get("rating")),
                "dribbles_won": drib_won,
                "dribbles_past": drib_past,
                "duels_won": duels_won,
                "duels_lost": duels_lost,
                "progressive_actions": progressive,
                "tackles": tackles if tackles is not None else (0 if has_played else None),
                "interceptions": interceptions if interceptions is not None else (0 if has_played else None),
                "fouls": fouls if fouls is not None else (0 if has_played else None),
                "recoveries": recoveries if recoveries is not None else (0 if has_played else None),
                "defensive_actions": def_actions if def_actions is not None else (0 if has_played else None),
                "xg": xg_val,
                "xa": xa_val,
            }
        return result

    def fetch_match(
        self,
        external_id: int,
        *,
        season: str = "2026/27",
        round_num: int = 1,
    ) -> MatchDTO | None:
        data = self.http.get_json(
            f"{FOTMOB_BASE}/matchDetails",
            params={"matchId": external_id},
            headers=self._headers(),
        )
        general = data.get("general") or {}
        content = data.get("content") or {}
        lineup = content.get("lineup") or {}
        if not general or not lineup:
            return None

        home_team = general.get("homeTeam") or {}
        away_team = general.get("awayTeam") or {}
        home_id = _safe_int(home_team.get("id")) or 0
        away_id = _safe_int(away_team.get("id")) or 0
        kickoff_str = general.get("matchTimeUTCDate") or "2026-08-22T18:00:00Z"
        kickoff = datetime.fromisoformat(str(kickoff_str).replace("Z", "+00:00")).astimezone(UTC)

        home_tstats, away_tstats = self._extract_team_stats(
            content.get("stats") or {},
            content.get("attackingZones"),
        )
        pstats_map = self._extract_player_stats_map(content.get("playerStats") or {})
        players: list[PlayerLineDTO] = []
        formations: dict[int, str | None] = {home_id: None, away_id: None}

        for side_key, team_ext_id in (("homeTeam", home_id), ("awayTeam", away_id)):
            side_lineup = lineup.get(side_key) or {}
            formations[team_ext_id] = _clean_formation(side_lineup.get("formation"))

            for is_starter, group_key in ((True, "starters"), (False, "subs")):
                for p in side_lineup.get(group_key) or []:
                    pid = _safe_int(p.get("id"))
                    if pid is None:
                        continue
                    layout = p.get("verticalLayout") or p.get("horizontalLayout") or {}
                    lx = _safe_float(layout.get("x"))
                    ly = _safe_float(layout.get("y"))
                    avg_x, avg_y = (
                        normalize_fotmob_layout_pos(lx, ly)
                        if lx is not None and ly is not None
                        else (None, None)
                    )
                    perf = p.get("performance") or {}
                    extra = pstats_map.get(pid) or {}
                    mins = extra.get("minutes")
                    if mins is None:
                        mins = 90 if is_starter else 0
                    rating = _safe_float(perf.get("rating")) or extra.get("rating")
                    pos = _infer_position_from_coords(
                        avg_x,
                        avg_y,
                        p.get("usualPlayingPositionId")
                        if p.get("usualPlayingPositionId") is not None
                        else p.get("positionStringShort"),
                        position_id=_safe_int(p.get("positionId")),
                    )

                    players.append(
                        PlayerLineDTO(
                            player_external_id=pid,
                            team_external_id=team_ext_id,
                            name=str(p.get("name") or ""),
                            position=pos,
                            minutes=max(0, min(130, int(mins))),
                            is_starter=is_starter,
                            avg_x=avg_x,
                            avg_y=avg_y,
                            stats={
                                "dribbles_won": extra.get("dribbles_won"),
                                "dribbles_past": extra.get("dribbles_past"),
                                "duels_won": extra.get("duels_won"),
                                "duels_lost": extra.get("duels_lost"),
                                "progressive_actions": extra.get("progressive_actions"),
                                "tackles": extra.get("tackles"),
                                "interceptions": extra.get("interceptions"),
                                "fouls": extra.get("fouls"),
                                "recoveries": extra.get("recoveries"),
                                "defensive_actions": extra.get("defensive_actions"),
                                "xg": extra.get("xg"),
                                "xa": extra.get("xa"),
                                "rating": round(rating, 1) if rating is not None else None,
                            },
                        )
                    )

        header = data.get("header") or {}
        teams_hdr = header.get("teams") or [{}, {}]
        h_goals = _safe_int(teams_hdr[0].get("score")) if len(teams_hdr) >= 2 else None
        a_goals = _safe_int(teams_hdr[1].get("score")) if len(teams_hdr) >= 2 else None

        # Extract shotmap events (FotMob pitch: x in 0..105 length, y in 0..68 width)
        events: list[EventDTO] = []
        for s in (content.get("shotmap") or {}).get("shots") or []:
            sx = _safe_float(s.get("x"))
            sy = _safe_float(s.get("y"))
            tid = _safe_int(s.get("teamId"))
            if sx is None or sy is None or tid is None:
                continue
            tx = round(_clamp(((68.0 - sy) / 68.0) * 100.0), 2)
            ty = round(_clamp((sx / 105.0) * 100.0), 2)
            events.append(
                EventDTO(
                    team_external_id=tid,
                    player_external_id=_safe_int(s.get("playerId")),
                    minute=max(0, _safe_int(s.get("min")) or 0),
                    type="shot",
                    x=tx,
                    y=ty,
                    outcome=(str(s.get("eventType") or "").lower() == "goal"),
                    xg=_safe_float(s.get("expectedGoals")),
                )
            )

        home_xg = home_tstats.get("xg")
        away_xg = away_tstats.get("xg")
        if home_xg is None and events:
            home_xg = round(sum(e.xg or 0.0 for e in events if e.team_external_id == home_id), 2)
        if away_xg is None and events:
            away_xg = round(sum(e.xg or 0.0 for e in events if e.team_external_id == away_id), 2)

        fixture = FixtureDTO(
            source="fotmob",
            external_id=external_id,
            season=season,
            round=round_num,
            kickoff_at=kickoff,
            home_external_id=home_id,
            away_external_id=away_id,
            status="finished" if (header.get("status") or {}).get("finished") else "scheduled",
            home_team_name=home_team.get("name"),
            away_team_name=away_team.get("name"),
            home_goals=h_goals,
            away_goals=a_goals,
            home_xg=home_xg,
            away_xg=away_xg,
        )

        return MatchDTO(
            fixture=fixture,
            teams=(
                TeamLineDTO(
                    team_external_id=home_id,
                    team_name=home_team.get("name"),
                    goals=h_goals,
                    xg=home_xg,
                    formation=formations[home_id],
                    possession=home_tstats.get("possession"),
                    own_half_passes=home_tstats.get("own_half_passes"),
                    opp_half_passes=home_tstats.get("opp_half_passes"),
                    tackles=home_tstats.get("tackles"),
                    interceptions=home_tstats.get("interceptions"),
                    fouls=home_tstats.get("fouls"),
                    touches_opp_box=home_tstats.get("touches_opp_box"),
                    attack_bias_left=home_tstats.get("attack_bias_left"),
                    attack_bias_center=home_tstats.get("attack_bias_center"),
                    attack_bias_right=home_tstats.get("attack_bias_right"),
                ),
                TeamLineDTO(
                    team_external_id=away_id,
                    team_name=away_team.get("name"),
                    goals=a_goals,
                    xg=away_xg,
                    formation=formations[away_id],
                    possession=away_tstats.get("possession"),
                    own_half_passes=away_tstats.get("own_half_passes"),
                    opp_half_passes=away_tstats.get("opp_half_passes"),
                    tackles=away_tstats.get("tackles"),
                    interceptions=away_tstats.get("interceptions"),
                    fouls=away_tstats.get("fouls"),
                    touches_opp_box=away_tstats.get("touches_opp_box"),
                    attack_bias_left=away_tstats.get("attack_bias_left"),
                    attack_bias_center=away_tstats.get("attack_bias_center"),
                    attack_bias_right=away_tstats.get("attack_bias_right"),
                ),
            ),
            players=players,
            events=events,
        )


class SofaScoreAdapter(SourceAdapter):
    source: Source = "sofascore"

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Referer": "https://www.sofascore.com/",
            "Origin": "https://www.sofascore.com",
        }

    def _resolve_season_id(self, season: str) -> int | None:
        data = self.http.get_json(
            f"{SOFASCORE_BASE}/unique-tournament/{SOFASCORE_SERIE_A_ID}/seasons",
            headers=self._headers(),
        )
        short_year = season.replace("20", "", 1)
        for s in data.get("seasons") or []:
            year_str = str(s.get("year") or "")
            if year_str in (season, short_year):
                return _safe_int(s.get("id"))
        seasons = data.get("seasons") or []
        return _safe_int(seasons[0].get("id")) if seasons else None

    def fetch_fixtures(self, season: str) -> list[FixtureDTO]:
        season_id = self._resolve_season_id(season)
        if season_id is None:
            return []

        fixtures: list[FixtureDTO] = []
        for round_num in range(1, 39):
            try:
                data = self.http.get_json(
                    f"{SOFASCORE_BASE}/unique-tournament/{SOFASCORE_SERIE_A_ID}/season/{season_id}/events/round/{round_num}",
                    headers=self._headers(),
                )
            except Exception as exc:
                log.debug("SofaScore round %d unavailable: %s", round_num, exc)
                break

            for ev in data.get("events") or []:
                eid = _safe_int(ev.get("id"))
                home = ev.get("homeTeam") or {}
                away = ev.get("awayTeam") or {}
                hid = _safe_int(home.get("id"))
                aid = _safe_int(away.get("id"))
                if eid is None or hid is None or aid is None:
                    continue

                st_type = str((ev.get("status") or {}).get("type", "")).lower()
                status: MatchStatus = (
                    "finished"
                    if st_type == "finished"
                    else "live"
                    if st_type == "inprogress"
                    else "postponed"
                    if st_type == "postponed"
                    else "cancelled"
                    if st_type == "canceled"
                    else "scheduled"
                )
                ts = _safe_int(ev.get("startTimestamp")) or 0
                kickoff = datetime.fromtimestamp(ts, tz=UTC)

                fixtures.append(
                    FixtureDTO(
                        source="sofascore",
                        external_id=eid,
                        season=season,
                        round=round_num,
                        kickoff_at=kickoff,
                        home_external_id=hid,
                        away_external_id=aid,
                        status=status,
                        home_team_name=home.get("name"),
                        away_team_name=away.get("name"),
                        home_goals=_safe_int((ev.get("homeScore") or {}).get("current")),
                        away_goals=_safe_int((ev.get("awayScore") or {}).get("current")),
                    )
                )
        return fixtures

    def fetch_match(
        self,
        external_id: int,
        *,
        season: str = "2026/27",
        round_num: int = 1,
    ) -> MatchDTO | None:
        event_resp = self.http.get_json(
            f"{SOFASCORE_BASE}/event/{external_id}",
            headers=self._headers(),
        )
        ev = event_resp.get("event") or {}
        if not ev:
            return None

        home = ev.get("homeTeam") or {}
        away = ev.get("awayTeam") or {}
        home_id = _safe_int(home.get("id")) or 0
        away_id = _safe_int(away.get("id")) or 0
        ts = _safe_int(ev.get("startTimestamp")) or 0
        kickoff = datetime.fromtimestamp(ts, tz=UTC)

        lineups = self.http.get_json(
            f"{SOFASCORE_BASE}/event/{external_id}/lineups",
            headers=self._headers(),
        )
        avg_pos_map: dict[int, tuple[float, float]] = {}
        try:
            avg_resp = self.http.get_json(
                f"{SOFASCORE_BASE}/event/{external_id}/average-positions",
                headers=self._headers(),
            )
            for side_key in ("home", "away"):
                for item in avg_resp.get(side_key) or []:
                    pid = _safe_int((item.get("player") or {}).get("id"))
                    ax = _safe_float(item.get("averageX"))
                    ay = _safe_float(item.get("averageY"))
                    if pid is not None and ax is not None and ay is not None:
                        avg_pos_map[pid] = normalize_sofascore_avg_pos(ax, ay)
        except Exception as exc:
            log.debug("SofaScore average-positions unavailable for %s: %s", external_id, exc)

        home_poss, away_poss = None, None
        try:
            stats_resp = self.http.get_json(
                f"{SOFASCORE_BASE}/event/{external_id}/statistics",
                headers=self._headers(),
            )
            for block in stats_resp.get("statistics") or []:
                if block.get("period") != "ALL":
                    continue
                for group in block.get("groups") or []:
                    for item in group.get("statisticsItems") or []:
                        if item.get("key") == "ballPossession":
                            home_poss = _safe_float(item.get("homeValue") or item.get("home"))
                            away_poss = _safe_float(item.get("awayValue") or item.get("away"))
        except Exception as exc:
            log.debug("SofaScore statistics unavailable for %s: %s", external_id, exc)

        players: list[PlayerLineDTO] = []
        formations: dict[int, str | None] = {home_id: None, away_id: None}

        for side_key, team_ext_id in (("home", home_id), ("away", away_id)):
            side_data = lineups.get(side_key) or {}
            formations[team_ext_id] = _clean_formation(side_data.get("formation"))

            for entry in side_data.get("players") or []:
                pobj = entry.get("player") or {}
                pid = _safe_int(pobj.get("id"))
                if pid is None:
                    continue
                st = entry.get("statistics") or {}
                mins = _safe_int(st.get("minutesPlayed")) or 0
                is_starter = not bool(entry.get("substitute"))
                avg_x, avg_y = avg_pos_map.get(pid, (None, None))
                pos = _infer_position_from_coords(
                    avg_x,
                    avg_y,
                    entry.get("position") or pobj.get("position"),
                )

                duels_won = (_safe_int(st.get("duelWon")) or 0) + (_safe_int(st.get("aerialWon")) or 0)
                duels_lost = (_safe_int(st.get("duelLost")) or 0) + (_safe_int(st.get("aerialLost")) or 0)
                has_duels = any(k in st for k in ("duelWon", "duelLost", "aerialWon", "aerialLost"))

                key_pass = _safe_int(st.get("keyPass")) or 0
                long_balls = _safe_int(st.get("accurateLongBalls")) or 0
                has_prog = any(k in st for k in ("keyPass", "accurateLongBalls", "totalProgression"))
                prog = _safe_int(st.get("totalProgression"))
                if prog is None and has_prog:
                    prog = key_pass + long_balls

                rating = _safe_float(st.get("rating"))
                players.append(
                    PlayerLineDTO(
                        player_external_id=pid,
                        team_external_id=team_ext_id,
                        name=str(pobj.get("name") or ""),
                        position=pos,
                        minutes=max(0, min(130, mins)),
                        is_starter=is_starter,
                        avg_x=avg_x,
                        avg_y=avg_y,
                        stats={
                            "dribbles_won": _safe_int(st.get("wonContest")),
                            "dribbles_past": _safe_int(st.get("challengeLost")),
                            "duels_won": duels_won if has_duels else None,
                            "duels_lost": duels_lost if has_duels else None,
                            "progressive_actions": prog,
                            "xg": _safe_float(st.get("expectedGoals")),
                            "xa": _safe_float(st.get("expectedAssists")),
                            "rating": round(rating, 1) if rating is not None else None,
                        },
                    )
                )

        h_goals = _safe_int((ev.get("homeScore") or {}).get("current"))
        a_goals = _safe_int((ev.get("awayScore") or {}).get("current"))
        fixture = FixtureDTO(
            source="sofascore",
            external_id=external_id,
            season=season,
            round=round_num,
            kickoff_at=kickoff,
            home_external_id=home_id,
            away_external_id=away_id,
            status=(
                "finished"
                if str((ev.get("status") or {}).get("type", "")).lower() == "finished"
                else "scheduled"
            ),
            home_team_name=home.get("name"),
            away_team_name=away.get("name"),
            home_goals=h_goals,
            away_goals=a_goals,
        )
        return MatchDTO(
            fixture=fixture,
            teams=(
                TeamLineDTO(
                    team_external_id=home_id,
                    team_name=home.get("name"),
                    goals=h_goals,
                    formation=formations[home_id],
                    possession=home_poss,
                ),
                TeamLineDTO(
                    team_external_id=away_id,
                    team_name=away.get("name"),
                    goals=a_goals,
                    formation=formations[away_id],
                    possession=away_poss,
                ),
            ),
            players=players,
        )


class MatchEventsAdapter(SourceAdapter):
    """Composite adapter: tries FotMob first, automatically falls back to SofaScore."""

    source: Source = "fotmob"

    def __init__(self, http: PoliteHttpClient) -> None:
        super().__init__(http)
        self.fotmob = FotMobAdapter(http)
        self.sofascore = SofaScoreAdapter(http)
        self.last_used_source: Source = "fotmob"

    def fetch_fixtures(self, season: str) -> list[FixtureDTO]:
        try:
            fixtures = self.fotmob.fetch_fixtures(season)
            if fixtures:
                self.last_used_source = "fotmob"
                return fixtures
        except (BlockedError, Exception) as exc:
            log.warning("FotMob fetch_fixtures failed (%s); falling back to SofaScore", exc)

        self.last_used_source = "sofascore"
        return self.sofascore.fetch_fixtures(season)

    def fetch_match(
        self,
        external_id: int,
        *,
        fallback_sofascore_id: int | None = None,
        season: str = "2026/27",
        round_num: int = 1,
    ) -> MatchDTO | None:
        if external_id:
            try:
                dto = self.fotmob.fetch_match(external_id, season=season, round_num=round_num)
                if dto is not None:
                    self.last_used_source = "fotmob"
                    return dto
            except (BlockedError, Exception) as exc:
                log.warning(
                    "FotMob fetch_match(%s) failed (%s); falling back to SofaScore(%s)",
                    external_id,
                    exc,
                    fallback_sofascore_id,
                )

        if fallback_sofascore_id:
            self.last_used_source = "sofascore"
            return self.sofascore.fetch_match(
                fallback_sofascore_id,
                season=season,
                round_num=round_num,
            )
        return None

"""Understat adapter for Serie A.

Collects fixtures, results, xG/xGA, shot coordinates (normalised to Tactix 0-100
for the 5 pitch corridors & 8 xGA shot zones), rosters/formations, and team PPDA.
Supports both Understat's JSON AJAX endpoints and HTML-embedded JSON payloads.
"""

from __future__ import annotations

import codecs
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from adapters.base import (
    EventDTO,
    FixtureDTO,
    MatchDTO,
    PlayerLineDTO,
    SourceAdapter,
    TeamLineDTO,
)
from db.models import MatchStatus, PlayerPosition

log = logging.getLogger(__name__)

BASE_URL = "https://understat.com"

_POSITION_MAP: dict[str, PlayerPosition] = {
    "GK": "GK",
    "DC": "CB",
    "DCL": "CB",
    "DCR": "CB",
    "DL": "LB",
    "DR": "RB",
    "DML": "LWB",
    "DMR": "RWB",
    "DMC": "DM",
    "DM": "DM",
    "MC": "CM",
    "ML": "CM",
    "MR": "CM",
    "AMC": "AM",
    "AML": "LW",
    "AMR": "RW",
    "FW": "ST",
    "FWL": "LW",
    "FWR": "RW",
    "Sub": "CM",
}


def season_start_year(season: str) -> int:
    """Convert '2026/27' -> 2026."""
    return int(season.split("/")[0])


def _clamp(val: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, val))


def _safe_float(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _safe_int(val: Any) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _extract_embedded_json(html: str, var_name: str) -> Any | None:
    pattern = re.compile(rf"var\s+{re.escape(var_name)}\s*=\s*JSON\.parse\('([^']+)'\)")
    match = pattern.search(html)
    if not match:
        return None
    raw = codecs.decode(match.group(1), "unicode_escape")
    return json.loads(raw)


def normalize_understat_coords(raw_x: float, raw_y: float) -> tuple[float, float]:
    """Convert Understat shot coordinates (X in [0,1] length, Y in [0,1] width)
    into the Tactix acting-team frame (x=width 0..100 left->right, y=length 0..100).

    In Understat's horizontal pitch (attacking left-to-right):
      X = 0..1 (own goal -> opponent goal)
      Y = 0..1 (left touchline facing goal -> right touchline facing goal)
    """
    tactix_x = round(_clamp(raw_y * 100.0), 2)
    tactix_y = round(_clamp(raw_x * 100.0), 2)
    return tactix_x, tactix_y


def _infer_formation_from_roster(roster: dict[str, dict[str, Any]]) -> str | None:
    """Derive a clean formation string (e.g. '3-5-2', '4-2-3-1') from Understat starter positions."""
    starters = [
        p
        for p in roster.values()
        if str(p.get("position", "")) not in ("Sub", "GK", "")
        and (_safe_int(p.get("time")) or 0) > 0
    ]
    if len(starters) < 8:
        return None

    defs = sum(
        1
        for p in starters
        if str(p.get("position", "")).startswith("D")
        and not str(p.get("position", "")).startswith("DM")
    )
    dms = sum(1 for p in starters if str(p.get("position", "")).startswith("DM"))
    cms = sum(1 for p in starters if str(p.get("position", "")) in ("MC", "ML", "MR"))
    ams = sum(1 for p in starters if str(p.get("position", "")).startswith("AM"))
    fws = sum(1 for p in starters if str(p.get("position", "")).startswith("FW"))

    # Clamp defending line to valid 3..5 range
    if defs < 3:
        defs = 3
    elif defs > 5:
        defs = 5

    lines = [n for n in (defs, dms, cms, ams, fws) if n > 0]
    if len(lines) < 3:
        mids = max(1, 10 - defs - max(1, fws))
        lines = [defs, mids, max(1, 10 - defs - mids)]
    if len(lines) > 5:
        lines = [lines[0], lines[1], lines[2], sum(lines[3:])]
    return "-".join(str(n) for n in lines)


def _parse_kickoff(raw: str) -> datetime:
    cleaned = raw.strip().replace(" ", "T")
    if not cleaned.endswith("Z") and "+" not in cleaned[10:]:
        cleaned = f"{cleaned}+00:00"
    return datetime.fromisoformat(cleaned.replace("Z", "+00:00")).astimezone(UTC)


class UnderstatAdapter(SourceAdapter):
    source = "understat"

    def __init__(self, http: Any) -> None:
        super().__init__(http)
        self._ppda_cache: dict[tuple[str, int, str], float] = {}
        self._season_cache: dict[str, dict[str, Any]] = {}

    def _fetch_league_payload(self, season: str) -> dict[str, Any]:
        if season in self._season_cache:
            return self._season_cache[season]

        year = season_start_year(season)
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{BASE_URL}/league/Serie_A/{year}",
        }

        # 1. Try Understat JSON API endpoint first
        try:
            data = self.http.get_json(f"{BASE_URL}/getLeagueData/Serie_A/{year}", headers=headers)
            if isinstance(data, dict) and ("dates" in data or "teams" in data):
                self._season_cache[season] = data
                return data
        except Exception as exc:
            log.debug("Understat getLeagueData fallback to HTML: %s", exc)

        # 2. Fallback to parsing embedded JSON from HTML
        html = self.http.get_text(f"{BASE_URL}/league/Serie_A/{year}")
        dates = _extract_embedded_json(html, "datesData") or []
        teams = _extract_embedded_json(html, "teamsData") or {}
        players = _extract_embedded_json(html, "playersData") or []
        payload = {"dates": dates, "teams": teams, "players": players}
        self._season_cache[season] = payload
        return payload

    def fetch_team_ppda_map(self, season: str) -> dict[tuple[int, str], float]:
        """Return {(understat_team_id, 'YYYY-MM-DD'): ppda} from Understat teamsData."""
        payload = self._fetch_league_payload(season)
        teams_data = payload.get("teams") or {}
        out: dict[tuple[int, str], float] = {}

        for team_id_str, team_obj in teams_data.items():
            team_id = _safe_int(team_id_str) or _safe_int(team_obj.get("id"))
            if team_id is None:
                continue
            for entry in team_obj.get("history") or []:
                date_str = str(entry.get("date", ""))[:10]
                ppda_obj = entry.get("ppda") or {}
                att = _safe_float(ppda_obj.get("att"))
                defn = _safe_float(ppda_obj.get("def"))
                if att is not None and defn is not None and defn > 0:
                    ppda = round(att / defn, 2)
                    out[(team_id, date_str)] = ppda
                    self._ppda_cache[(season, team_id, date_str)] = ppda
        return out

    def fetch_fixtures(self, season: str) -> list[FixtureDTO]:
        payload = self._fetch_league_payload(season)
        dates = payload.get("dates") or []
        self.fetch_team_ppda_map(season)

        # Understat datesData does not include round numbers; infer rounds sequentially
        # by sorting fixtures chronologically (10 matches per round in 20-team Serie A).
        sorted_dates = sorted(dates, key=lambda d: str(d.get("datetime", "")))
        fixtures: list[FixtureDTO] = []

        for idx, item in enumerate(sorted_dates):
            match_id = _safe_int(item.get("id"))
            home = item.get("h") or {}
            away = item.get("a") or {}
            home_id = _safe_int(home.get("id"))
            away_id = _safe_int(away.get("id"))
            if match_id is None or home_id is None or away_id is None:
                continue

            is_result = bool(item.get("isResult"))
            status: MatchStatus = "finished" if is_result else "scheduled"
            goals = item.get("goals") or {}
            xg = item.get("xG") or {}

            round_num = min(38, max(1, (idx // 10) + 1))
            fixtures.append(
                FixtureDTO(
                    source="understat",
                    external_id=match_id,
                    season=season,
                    round=round_num,
                    kickoff_at=_parse_kickoff(str(item.get("datetime", "2026-08-22 18:00:00"))),
                    home_external_id=home_id,
                    away_external_id=away_id,
                    status=status,
                    home_team_name=home.get("title"),
                    away_team_name=away.get("title"),
                    home_goals=_safe_int(goals.get("h")) if is_result else None,
                    away_goals=_safe_int(goals.get("a")) if is_result else None,
                    home_xg=_safe_float(xg.get("h")) if is_result else None,
                    away_xg=_safe_float(xg.get("a")) if is_result else None,
                )
            )
        return fixtures

    def fetch_match(
        self, external_id: int, *, season: str = "2026/27", round_num: int = 1
    ) -> MatchDTO | None:
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{BASE_URL}/match/{external_id}",
        }
        shots_data: dict[str, Any] | None = None
        rosters_data: dict[str, Any] | None = None
        match_info: dict[str, Any] | None = None

        try:
            data = self.http.get_json(f"{BASE_URL}/getMatchData/{external_id}", headers=headers)
            if isinstance(data, dict) and ("shots" in data or "rosters" in data):
                shots_data = data.get("shots")
                rosters_data = data.get("rosters")
                match_info = data.get("match_info")
        except Exception as exc:
            log.debug("Understat getMatchData fallback to HTML for %s: %s", external_id, exc)

        if shots_data is None and rosters_data is None:
            html = self.http.get_text(f"{BASE_URL}/match/{external_id}")
            shots_data = _extract_embedded_json(html, "shotsData")
            rosters_data = _extract_embedded_json(html, "rostersData")
            match_info = _extract_embedded_json(html, "match_info")

        if not shots_data and not rosters_data:
            return None

        info = match_info or {}
        home_id = _safe_int(info.get("team_h_id")) or _safe_int(info.get("h")) or 0
        away_id = _safe_int(info.get("team_a_id")) or _safe_int(info.get("a")) or 0
        kickoff_raw = str(info.get("date", "2026-08-22 18:00:00"))
        kickoff = _parse_kickoff(kickoff_raw)
        date_key = kickoff.strftime("%Y-%m-%d")

        # Parse players from rostersData
        players: list[PlayerLineDTO] = []
        home_roster = (rosters_data or {}).get("h") or {}
        away_roster = (rosters_data or {}).get("a") or {}

        for side_key, team_ext_id, roster in (
            ("h", home_id, home_roster),
            ("a", away_id, away_roster),
        ):
            for row in roster.values():
                pid = _safe_int(row.get("player_id"))
                if pid is None:
                    continue
                pos_raw = str(row.get("position", ""))
                pos = _POSITION_MAP.get(pos_raw)
                mins = _safe_int(row.get("time")) or 0
                is_starter = pos_raw != "Sub" and (_safe_int(row.get("roster_in")) or 0) == 0
                players.append(
                    PlayerLineDTO(
                        player_external_id=pid,
                        team_external_id=_safe_int(row.get("team_id")) or team_ext_id,
                        name=str(row.get("player", "")),
                        position=pos,
                        minutes=max(0, min(130, mins)),
                        is_starter=is_starter,
                        stats={
                            "xg": _safe_float(row.get("xG")),
                            "xa": _safe_float(row.get("xA")),
                            "shots": _safe_int(row.get("shots")),
                            "key_passes": _safe_int(row.get("key_passes")),
                            "xg_chain": _safe_float(row.get("xGChain")),
                            "xg_buildup": _safe_float(row.get("xGBuildup")),
                        },
                    )
                )
            _ = side_key

        # Parse shot events normalized into Tactix coordinates
        events: list[EventDTO] = []
        for side_key, team_ext_id in (("h", home_id), ("a", away_id)):
            for shot in (shots_data or {}).get(side_key) or []:
                raw_x = _safe_float(shot.get("X"))
                raw_y = _safe_float(shot.get("Y"))
                if raw_x is None or raw_y is None:
                    continue
                tx, ty = normalize_understat_coords(raw_x, raw_y)
                result_str = str(shot.get("result", ""))
                events.append(
                    EventDTO(
                        team_external_id=team_ext_id,
                        player_external_id=_safe_int(shot.get("player_id")),
                        minute=max(0, _safe_int(shot.get("minute")) or 0),
                        type="shot",
                        x=tx,
                        y=ty,
                        outcome=(result_str == "Goal"),
                        xg=_safe_float(shot.get("xG")),
                    )
                )

        home_xg = _safe_float(info.get("h_xg"))
        away_xg = _safe_float(info.get("a_xg"))
        if home_xg is None:
            home_xg = round(sum(e.xg or 0.0 for e in events if e.team_external_id == home_id), 2)
        if away_xg is None:
            away_xg = round(sum(e.xg or 0.0 for e in events if e.team_external_id == away_id), 2)

        home_ppda = _safe_float(info.get("h_ppda")) or self._ppda_cache.get(
            (season, home_id, date_key)
        )
        away_ppda = _safe_float(info.get("a_ppda")) or self._ppda_cache.get(
            (season, away_id, date_key)
        )

        fixture = FixtureDTO(
            source="understat",
            external_id=external_id,
            season=season,
            round=round_num,
            kickoff_at=kickoff,
            home_external_id=home_id,
            away_external_id=away_id,
            status="finished",
            home_team_name=info.get("team_h"),
            away_team_name=info.get("team_a"),
            home_goals=_safe_int(info.get("h_goals")),
            away_goals=_safe_int(info.get("a_goals")),
            home_xg=home_xg,
            away_xg=away_xg,
        )
        home_line = TeamLineDTO(
            team_external_id=home_id,
            team_name=info.get("team_h"),
            goals=_safe_int(info.get("h_goals")),
            xg=home_xg,
            formation=_infer_formation_from_roster(home_roster),
            ppda=home_ppda,
        )
        away_line = TeamLineDTO(
            team_external_id=away_id,
            team_name=info.get("team_a"),
            goals=_safe_int(info.get("a_goals")),
            xg=away_xg,
            formation=_infer_formation_from_roster(away_roster),
            ppda=away_ppda,
        )
        return MatchDTO(
            fixture=fixture,
            teams=(home_line, away_line),
            players=players,
            events=events,
        )

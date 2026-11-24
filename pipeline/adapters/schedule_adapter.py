"""Official Serie A schedule & kickoff adapter using FOOTBALL_API_KEY.

Supports:
  - football-data.org v4 (`FOOTBALL_API_PROVIDER=football_data`, default)
  - API-Football v3 (`FOOTBALL_API_PROVIDER=api_football`)

Includes deterministic + controlled fuzzy reconciliation of teams, fixtures, and
players against Understat / FotMob / SofaScore identifiers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from adapters.base import FixtureDTO, MatchDTO, Source, SourceAdapter
from adapters.http import PoliteHttpClient
from adapters.reconciliation import (
    CanonicalTeam,
    match_player_name,
    resolve_canonical_team,
)
from config import get_settings
from db.models import MatchStatus

log = logging.getLogger(__name__)

FOOTBALL_DATA_URL = "https://api.football-data.org/v4/competitions/SA/matches"
API_FOOTBALL_URL = "https://v3.football.api-sports.io/fixtures"
API_FOOTBALL_SERIE_A_ID = 135

_FOOTBALL_DATA_STATUS: dict[str, MatchStatus] = {
    "SCHEDULED": "scheduled",
    "TIMED": "scheduled",
    "IN_PLAY": "live",
    "PAUSED": "live",
    "FINISHED": "finished",
    "POSTPONED": "postponed",
    "SUSPENDED": "postponed",
    "CANCELLED": "cancelled",
}

_API_FOOTBALL_STATUS: dict[str, MatchStatus] = {
    "TBD": "scheduled",
    "NS": "scheduled",
    "1H": "live",
    "HT": "live",
    "2H": "live",
    "ET": "live",
    "P": "live",
    "FT": "finished",
    "AET": "finished",
    "PEN": "finished",
    "PST": "postponed",
    "SUSP": "postponed",
    "CANC": "cancelled",
    "ABD": "cancelled",
}


@dataclass(frozen=True)
class ReconciledFixture:
    season: str
    round: int
    kickoff_at: datetime
    home_team: CanonicalTeam
    away_team: CanonicalTeam
    status: MatchStatus
    home_goals: int | None = None
    away_goals: int | None = None
    home_xg: float | None = None
    away_xg: float | None = None
    understat_id: int | None = None
    fotmob_id: int | None = None
    sofascore_id: int | None = None
    home_understat_id: int | None = None
    away_understat_id: int | None = None
    home_fotmob_id: int | None = None
    away_fotmob_id: int | None = None
    home_sofascore_id: int | None = None
    away_sofascore_id: int | None = None


class ScheduleAdapter(SourceAdapter):
    source: Source = "football_data"

    def __init__(
        self,
        http: PoliteHttpClient,
        *,
        api_key: str | None = None,
        provider: str | None = None,
    ) -> None:
        super().__init__(http)
        settings = get_settings()
        self.api_key = api_key or (
            settings.football_api_key.get_secret_value() if settings.football_api_key else None
        )
        self.provider = provider or settings.football_api_provider
        self.source = "api_football" if self.provider == "api_football" else "football_data"

    def fetch_fixtures(self, season: str) -> list[FixtureDTO]:
        if not self.api_key:
            log.warning("FOOTBALL_API_KEY not set; ScheduleAdapter returning empty fixture list")
            return []
        start_year = int(season.split("/")[0])
        if self.provider == "api_football":
            return self._fetch_api_football(season, start_year)
        return self._fetch_football_data(season, start_year)

    def _fetch_football_data(self, season: str, start_year: int) -> list[FixtureDTO]:
        data = self.http.get_json(
            FOOTBALL_DATA_URL,
            params={"season": start_year},
            headers={"X-Auth-Token": self.api_key or ""},
        )
        fixtures: list[FixtureDTO] = []
        for m in data.get("matches") or []:
            mid = m.get("id")
            home = m.get("homeTeam") or {}
            away = m.get("awayTeam") or {}
            hid = home.get("id")
            aid = away.get("id")
            if mid is None or hid is None or aid is None:
                continue
            utc_str = str(m.get("utcDate") or "2026-08-22T18:00:00Z")
            kickoff = datetime.fromisoformat(utc_str.replace("Z", "+00:00")).astimezone(UTC)
            full_time = (m.get("score") or {}).get("fullTime") or {}
            fixtures.append(
                FixtureDTO(
                    source="football_data",
                    external_id=int(mid),
                    season=season,
                    round=max(1, min(38, int(m.get("matchday") or 1))),
                    kickoff_at=kickoff,
                    home_external_id=int(hid),
                    away_external_id=int(aid),
                    status=_FOOTBALL_DATA_STATUS.get(str(m.get("status") or ""), "scheduled"),
                    home_team_name=home.get("shortName") or home.get("name"),
                    away_team_name=away.get("shortName") or away.get("name"),
                    home_goals=full_time.get("home"),
                    away_goals=full_time.get("away"),
                )
            )
        return fixtures

    def _fetch_api_football(self, season: str, start_year: int) -> list[FixtureDTO]:
        data = self.http.get_json(
            API_FOOTBALL_URL,
            params={"league": API_FOOTBALL_SERIE_A_ID, "season": start_year},
            headers={"x-apisports-key": self.api_key or ""},
        )
        fixtures: list[FixtureDTO] = []
        for row in data.get("response") or []:
            fx = row.get("fixture") or {}
            league = row.get("league") or {}
            teams = row.get("teams") or {}
            goals = row.get("goals") or {}
            home = teams.get("home") or {}
            away = teams.get("away") or {}
            mid = fx.get("id")
            hid = home.get("id")
            aid = away.get("id")
            if mid is None or hid is None or aid is None:
                continue

            round_raw = str(league.get("round") or "1")
            digits = "".join(ch for ch in round_raw if ch.isdigit())
            round_num = max(1, min(38, int(digits))) if digits else 1
            utc_str = str(fx.get("date") or "2026-08-22T18:00:00+00:00")
            kickoff = datetime.fromisoformat(utc_str.replace("Z", "+00:00")).astimezone(UTC)
            short_status = str((fx.get("status") or {}).get("short") or "NS")
            fixtures.append(
                FixtureDTO(
                    source="api_football",
                    external_id=int(mid),
                    season=season,
                    round=round_num,
                    kickoff_at=kickoff,
                    home_external_id=int(hid),
                    away_external_id=int(aid),
                    status=_API_FOOTBALL_STATUS.get(short_status, "scheduled"),
                    home_team_name=home.get("name"),
                    away_team_name=away.get("name"),
                    home_goals=goals.get("home"),
                    away_goals=goals.get("away"),
                )
            )
        return fixtures

    def fetch_match(self, external_id: int) -> MatchDTO | None:
        # Official schedule APIs on free tier do not provide event/xy telemetry.
        return None


def reconcile_fixtures(
    *,
    schedule_fixtures: list[FixtureDTO],
    understat_fixtures: list[FixtureDTO],
    events_fixtures: list[FixtureDTO],
    season: str,
) -> list[ReconciledFixture]:
    """Merge fixtures from official schedule + Understat + FotMob/SofaScore using
    deterministic canonical `(home_slug, away_slug)` keys.
    """
    by_pair: dict[tuple[str, str], dict[str, Any]] = {}

    def _upsert_slot(fx: FixtureDTO, source_tag: str) -> None:
        if not fx.home_team_name or not fx.away_team_name:
            return
        home_canon = resolve_canonical_team(fx.home_team_name)
        away_canon = resolve_canonical_team(fx.away_team_name)
        if home_canon.slug == away_canon.slug:
            return
        key = (home_canon.slug, away_canon.slug)
        slot = by_pair.setdefault(
            key,
            {
                "season": season,
                "round": fx.round,
                "kickoff_at": fx.kickoff_at,
                "home_team": home_canon,
                "away_team": away_canon,
                "status": fx.status,
                "home_goals": fx.home_goals,
                "away_goals": fx.away_goals,
                "home_xg": fx.home_xg,
                "away_xg": fx.away_xg,
                "understat_id": None,
                "fotmob_id": None,
                "sofascore_id": None,
                "home_understat_id": None,
                "away_understat_id": None,
                "home_fotmob_id": None,
                "away_fotmob_id": None,
                "home_sofascore_id": None,
                "away_sofascore_id": None,
            },
        )
        # Official schedule takes priority for kickoff_at, round, and official status/score
        if source_tag == "schedule":
            slot["round"] = fx.round
            slot["kickoff_at"] = fx.kickoff_at
            slot["status"] = fx.status
            if fx.home_goals is not None:
                slot["home_goals"] = fx.home_goals
            if fx.away_goals is not None:
                slot["away_goals"] = fx.away_goals
        elif source_tag == "understat":
            slot["understat_id"] = fx.external_id
            slot["home_understat_id"] = fx.home_external_id
            slot["away_understat_id"] = fx.away_external_id
            if fx.home_xg is not None:
                slot["home_xg"] = fx.home_xg
            if fx.away_xg is not None:
                slot["away_xg"] = fx.away_xg
            if slot["home_goals"] is None and fx.home_goals is not None:
                slot["home_goals"] = fx.home_goals
                slot["away_goals"] = fx.away_goals
                slot["status"] = fx.status
        elif fx.source == "fotmob":
            slot["fotmob_id"] = fx.external_id
            slot["home_fotmob_id"] = fx.home_external_id
            slot["away_fotmob_id"] = fx.away_external_id
            if slot["home_goals"] is None and fx.home_goals is not None:
                slot["home_goals"] = fx.home_goals
                slot["away_goals"] = fx.away_goals
                slot["status"] = fx.status
        elif fx.source == "sofascore":
            slot["sofascore_id"] = fx.external_id
            slot["home_sofascore_id"] = fx.home_external_id
            slot["away_sofascore_id"] = fx.away_external_id
            if slot["home_goals"] is None and fx.home_goals is not None:
                slot["home_goals"] = fx.home_goals
                slot["away_goals"] = fx.away_goals
                slot["status"] = fx.status

    for fx in schedule_fixtures:
        _upsert_slot(fx, "schedule")
    for fx in understat_fixtures:
        _upsert_slot(fx, "understat")
    for fx in events_fixtures:
        _upsert_slot(fx, "events")

    return sorted(
        (ReconciledFixture(**slot) for slot in by_pair.values()),
        key=lambda r: (r.round, r.kickoff_at),
    )


def reconcile_player_ids(
    *,
    source_players: list[tuple[int, str]],
    target_players: list[tuple[int, str]],
) -> dict[int, int]:
    """Map `{source_external_id: target_external_id}` within the same team."""
    mapping: dict[int, int] = {}
    used_targets: set[int] = set()
    for src_id, src_name in source_players:
        remaining = [(tid, tname) for tid, tname in target_players if tid not in used_targets]
        matched = match_player_name(src_name, remaining)
        if matched is not None:
            mapping[src_id] = matched
            used_targets.add(matched)
    return mapping

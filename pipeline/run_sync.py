"""Tactix Serie A 2026/27 Pipeline Orchestrator.

Usage (from `pipeline/`):
    python run_sync.py --mode=post_match
    python run_sync.py --mode=pre_match
    python run_sync.py --mode=full
    python run_sync.py --mode=dry_run
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any, Literal

from adapters.base import FixtureDTO, MatchDTO, PlayerLineDTO
from adapters.http import PoliteHttpClient
from adapters.match_events_adapter import MatchEventsAdapter
from adapters.reconciliation import make_team_upsert, match_player_name
from adapters.schedule_adapter import ReconciledFixture, ScheduleAdapter, reconcile_fixtures
from adapters.understat_adapter import UnderstatAdapter
from ai.gemini_analyst import GeminiAnalyst
from config import get_settings
from db.client import fetch_table, get_client, ping_db, upsert_rows
from db.models import (
    MatchUpsert,
    PlayerArchetype,
    PlayerMatchStatsUpsert,
    PlayerPosition,
    PlayerUpsert,
    TeamHowToBeatUpsert,
    TeamMatchTacticsUpsert,
    TeamUpsert,
)
from engine.archetype_classifier import PlayerSeasonAggregate, classify_players
from engine.chameleon_detector import (
    TeamMatchRecord,
    compute_league_tiers,
    detect_chameleon_shifts,
)
from engine.conditional_splits import (
    FinishedMatchContext,
    compute_player_splits,
    compute_team_splits,
)
from engine.how_to_beat import extract_team_vulnerabilities
from engine.matchup_scorer import infer_probable_starters, score_upcoming_matchup
from engine.pitch import corridor_from_x, position_default_corridor
from engine.tactical_fingerprint import (
    PitchEventSample,
    PlayerPositionSample,
    TeamMatchOptaStats,
    build_dribbles_zones,
    build_team_match_fingerprint,
)

SyncMode = Literal["post_match", "pre_match", "full", "dry_run"]

log = logging.getLogger("run_sync")


def _safe_parse_dt(raw: Any) -> datetime | None:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw
    return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))


def _fetch_all_fixtures(http: PoliteHttpClient, season: str) -> list[ReconciledFixture]:
    sched_fx: list[FixtureDTO] = []
    understat_fx: list[FixtureDTO] = []
    events_fx: list[FixtureDTO] = []

    try:
        sched_fx = ScheduleAdapter(http).fetch_fixtures(season)
        log.info("ScheduleAdapter fetched %d fixtures", len(sched_fx))
    except Exception as exc:
        log.warning("ScheduleAdapter failed (%s); continuing with remaining sources", exc)

    try:
        understat_fx = UnderstatAdapter(http).fetch_fixtures(season)
        log.info("UnderstatAdapter fetched %d fixtures", len(understat_fx))
    except Exception as exc:
        log.warning("UnderstatAdapter failed (%s); continuing with remaining sources", exc)

    try:
        events_adapter = MatchEventsAdapter(http)
        events_fx = events_adapter.fetch_fixtures(season)
        log.info(
            "MatchEventsAdapter (%s) fetched %d fixtures",
            events_adapter.last_used_source,
            len(events_fx),
        )
    except Exception as exc:
        log.warning("MatchEventsAdapter failed (%s); continuing with remaining sources", exc)

    reconciled = reconcile_fixtures(
        schedule_fixtures=sched_fx,
        understat_fixtures=understat_fx,
        events_fixtures=events_fx,
        season=season,
    )
    log.info("Reconciled %d unique fixtures for season %s", len(reconciled), season)
    return reconciled


def sync_teams_and_matches(
    reconciled: list[ReconciledFixture],
) -> tuple[dict[str, int], dict[tuple[int, int], dict[str, Any]]]:
    """Idempotently upsert teams & matches and return lookup maps."""
    team_upserts_by_slug: dict[str, dict[str, Any]] = {}
    for fx in reconciled:
        for canon, u_id, f_id, s_id in (
            (fx.home_team, fx.home_understat_id, fx.home_fotmob_id, fx.home_sofascore_id),
            (fx.away_team, fx.away_understat_id, fx.away_fotmob_id, fx.away_sofascore_id),
        ):
            entry = team_upserts_by_slug.setdefault(
                canon.slug,
                {
                    "raw_name": canon.name,
                    "understat_id": None,
                    "fotmob_id": None,
                    "sofascore_id": None,
                },
            )
            if u_id is not None:
                entry["understat_id"] = u_id
            if f_id is not None:
                entry["fotmob_id"] = f_id
            if s_id is not None:
                entry["sofascore_id"] = s_id

    team_rows: list[TeamUpsert] = [
        make_team_upsert(
            v["raw_name"],
            understat_id=v["understat_id"],
            fotmob_id=v["fotmob_id"],
            sofascore_id=v["sofascore_id"],
        )
        for v in team_upserts_by_slug.values()
    ]
    upsert_rows("teams", team_rows, on_conflict="slug")

    db_teams = fetch_table("teams")
    slug_to_id = {str(t["slug"]): int(t["id"]) for t in db_teams}

    match_rows: list[MatchUpsert] = []
    for fx in reconciled:
        hid = slug_to_id.get(fx.home_team.slug)
        aid = slug_to_id.get(fx.away_team.slug)
        if hid is None or aid is None or hid == aid:
            continue
        match_rows.append(
            MatchUpsert(
                season=fx.season,
                round=fx.round,
                kickoff_at=fx.kickoff_at,
                home_team_id=hid,
                away_team_id=aid,
                home_goals=fx.home_goals,
                away_goals=fx.away_goals,
                home_xg=fx.home_xg,
                away_xg=fx.away_xg,
                status=fx.status,
                understat_id=fx.understat_id,
                fotmob_id=fx.fotmob_id,
                sofascore_id=fx.sofascore_id,
            )
        )
    upsert_rows("matches", match_rows)

    db_matches = fetch_table("matches", eq={"season": reconciled[0].season} if reconciled else None)
    match_map = {(int(m["home_team_id"]), int(m["away_team_id"])): m for m in db_matches}
    return slug_to_id, match_map


def _merge_player_lines(
    *,
    understat_dto: MatchDTO | None,
    events_dto: MatchDTO | None,
    team_id: int,
    team_understat_id: int | None,
    team_events_id: int | None,
) -> list[dict[str, Any]]:
    """Merge Understat + FotMob/SofaScore player match lines for one team."""
    u_players: list[PlayerLineDTO] = []
    if understat_dto and team_understat_id is not None:
        u_players = [p for p in understat_dto.players if p.team_external_id == team_understat_id]

    e_players: list[PlayerLineDTO] = []
    if events_dto and team_events_id is not None:
        e_players = [p for p in events_dto.players if p.team_external_id == team_events_id]

    merged: list[dict[str, Any]] = []
    used_u_ids: set[int] = set()
    u_candidates = [(p.player_external_id, p.name) for p in u_players]
    u_by_id = {p.player_external_id: p for p in u_players}

    events_source = events_dto.fixture.source if events_dto else None

    for ep in e_players:
        matched_uid = match_player_name(
            ep.name, [c for c in u_candidates if c[0] not in used_u_ids]
        )
        up = u_by_id.get(matched_uid) if matched_uid is not None else None
        if matched_uid is not None:
            used_u_ids.add(matched_uid)

        merged.append(
            {
                "team_id": team_id,
                "name": ep.name or (up.name if up else "Unknown"),
                "position": ep.position or (up.position if up else "CM"),
                "minutes": ep.minutes if ep.minutes > 0 else (up.minutes if up else 0),
                "is_starter": ep.is_starter or (up.is_starter if up else False),
                "avg_x": ep.avg_x,
                "avg_y": ep.avg_y,
                "dribbles_won": ep.stats.get("dribbles_won"),
                "dribbles_past": ep.stats.get("dribbles_past"),
                "duels_won": ep.stats.get("duels_won"),
                "duels_lost": ep.stats.get("duels_lost"),
                "progressive_actions": ep.stats.get("progressive_actions"),
                "tackles": ep.stats.get("tackles"),
                "interceptions": ep.stats.get("interceptions"),
                "fouls": ep.stats.get("fouls"),
                "recoveries": ep.stats.get("recoveries"),
                "xg": ep.stats.get("xg")
                if ep.stats.get("xg") is not None
                else (up.stats.get("xg") if up else None),
                "xa": ep.stats.get("xa")
                if ep.stats.get("xa") is not None
                else (up.stats.get("xa") if up else None),
                "rating": ep.stats.get("rating"),
                "understat_id": up.player_external_id if up else None,
                "fotmob_id": ep.player_external_id if events_source == "fotmob" else None,
                "sofascore_id": ep.player_external_id if events_source == "sofascore" else None,
            }
        )

    # Include any Understat players not present in FotMob/SofaScore
    for up in u_players:
        if up.player_external_id in used_u_ids:
            continue
        merged.append(
            {
                "team_id": team_id,
                "name": up.name,
                "position": up.position or "CM",
                "minutes": up.minutes,
                "is_starter": up.is_starter,
                "avg_x": None,
                "avg_y": None,
                "dribbles_won": None,
                "dribbles_past": None,
                "duels_won": None,
                "duels_lost": None,
                "progressive_actions": up.stats.get("key_passes"),
                "tackles": None,
                "interceptions": None,
                "fouls": None,
                "recoveries": None,
                "xg": up.stats.get("xg"),
                "xa": up.stats.get("xa"),
                "rating": None,
                "understat_id": up.player_external_id,
                "fotmob_id": None,
                "sofascore_id": None,
            }
        )
    return merged


def _resolve_or_create_player(
    *,
    pinfo: dict[str, Any],
    existing_players: list[dict[str, Any]],
) -> int:
    """Resolve an internal `players.id` by external ID or team+name, inserting if new."""
    for ext_col in ("fotmob_id", "understat_id", "sofascore_id"):
        ext_val = pinfo.get(ext_col)
        if ext_val is not None:
            for row in existing_players:
                if row.get(ext_col) == ext_val:
                    return int(row["id"])

    team_cands = [
        (int(row["id"]), str(row["name"]))
        for row in existing_players
        if row.get("team_id") == pinfo["team_id"]
    ]
    matched_id = match_player_name(str(pinfo["name"]), team_cands)
    if matched_id is not None:
        # Backfill missing external IDs on the matched player
        updates = {
            k: pinfo[k]
            for k in ("understat_id", "fotmob_id", "sofascore_id")
            if pinfo.get(k) is not None
        }
        if updates:
            get_client().table("players").update(updates).eq("id", matched_id).execute()
        return matched_id

    row_model = PlayerUpsert(
        team_id=pinfo["team_id"],
        name=str(pinfo["name"]),
        primary_position=pinfo["position"] or "CM",
        understat_id=pinfo.get("understat_id"),
        fotmob_id=pinfo.get("fotmob_id"),
        sofascore_id=pinfo.get("sofascore_id"),
    )
    res = get_client().table("players").insert(row_model.to_db()).execute()
    inserted = res.data[0]
    existing_players.append(inserted)
    return int(inserted["id"])


def sync_match_telemetry(
    http: PoliteHttpClient, season: str, target_round: int | None = None
) -> int:
    """Fetch match-level shots/PPDA/positions/stats for finished matches missing tactics."""
    understat = UnderstatAdapter(http)
    events_adapter = MatchEventsAdapter(http)
    try:
        understat.fetch_team_ppda_map(season)
    except Exception as exc:
        log.warning("Could not warm Understat PPDA cache: %s", exc)

    db_matches = fetch_table("matches", eq={"season": season, "status": "finished"}, order="round")
    existing_tactics = fetch_table(
        "team_match_tactics", columns="match_id,team_id,ppda,avg_def_line_y,dribbles_zones_json"
    )
    tactics_rows_by_match: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for t in existing_tactics:
        tactics_rows_by_match[int(t["match_id"])].append(t)
    covered_matches = {
        mid
        for mid, rows in tactics_rows_by_match.items()
        if len(rows) >= 2
        and all(
            r.get("ppda") is not None
            and r.get("avg_def_line_y") is not None
            and r.get("dribbles_zones_json") is not None
            for r in rows
        )
    }
    existing_players = fetch_table("players")
    db_teams = {int(t["id"]): t for t in fetch_table("teams")}

    synced = 0
    for m in db_matches:
        mid = int(m["id"])
        if target_round is not None and int(m["round"]) != target_round:
            continue
        if (
            mid in covered_matches
            and m.get("home_xg") is not None
            and m.get("away_xg") is not None
        ):
            continue

        home_id = int(m["home_team_id"])
        away_id = int(m["away_team_id"])
        home_team = db_teams.get(home_id, {})
        away_team = db_teams.get(away_id, {})

        u_dto: MatchDTO | None = None
        if m.get("understat_id"):
            try:
                u_dto = understat.fetch_match(
                    int(m["understat_id"]),
                    season=season,
                    round_num=int(m["round"]),
                )
            except Exception as exc:
                log.warning("Understat match %s failed: %s", m["understat_id"], exc)

        e_dto: MatchDTO | None = None
        if m.get("fotmob_id") or m.get("sofascore_id"):
            try:
                e_dto = events_adapter.fetch_match(
                    int(m["fotmob_id"] or 0),
                    fallback_sofascore_id=int(m["sofascore_id"]) if m.get("sofascore_id") else None,
                    season=season,
                    round_num=int(m["round"]),
                )
            except Exception as exc:
                log.warning("MatchEvents match %d failed: %s", mid, exc)

        if u_dto is None and e_dto is None:
            continue

        e_src = e_dto.fixture.source if e_dto else None
        home_e_id = (
            home_team.get("fotmob_id") if e_src == "fotmob" else home_team.get("sofascore_id")
        )
        away_e_id = (
            away_team.get("fotmob_id") if e_src == "fotmob" else away_team.get("sofascore_id")
        )

        home_merged = _merge_player_lines(
            understat_dto=u_dto,
            events_dto=e_dto,
            team_id=home_id,
            team_understat_id=home_team.get("understat_id"),
            team_events_id=home_e_id,
        )
        away_merged = _merge_player_lines(
            understat_dto=u_dto,
            events_dto=e_dto,
            team_id=away_id,
            team_understat_id=away_team.get("understat_id"),
            team_events_id=away_e_id,
        )

        # Upsert player_match_stats
        pms_rows: list[PlayerMatchStatsUpsert] = []
        pos_samples: dict[int, list[PlayerPositionSample]] = {home_id: [], away_id: []}

        for tid, opp_id, plist in (
            (home_id, away_id, home_merged),
            (away_id, home_id, away_merged),
        ):
            for pinfo in plist:
                if int(pinfo["minutes"]) <= 0:
                    continue
                pid = _resolve_or_create_player(pinfo=pinfo, existing_players=existing_players)
                ax, ay = pinfo["avg_x"], pinfo["avg_y"]
                corridor = (
                    corridor_from_x(ax)
                    if ax is not None
                    else position_default_corridor(pinfo["position"])
                )
                pms_rows.append(
                    PlayerMatchStatsUpsert(
                        match_id=mid,
                        player_id=pid,
                        team_id=tid,
                        opponent_id=opp_id,
                        position_played=pinfo["position"],
                        minutes=int(pinfo["minutes"]),
                        avg_x=ax,
                        avg_y=ay,
                        zone_corridor=corridor,
                        dribbles_won=pinfo["dribbles_won"],
                        dribbles_past=pinfo["dribbles_past"],
                        duels_won=pinfo["duels_won"],
                        duels_lost=pinfo["duels_lost"],
                        progressive_actions=pinfo["progressive_actions"],
                        xg=pinfo["xg"],
                        xa=pinfo["xa"],
                        rating=pinfo["rating"],
                    )
                )
                pos_samples[tid].append(
                    PlayerPositionSample(
                        position=pinfo["position"],
                        minutes=int(pinfo["minutes"]),
                        is_starter=bool(pinfo["is_starter"]),
                        avg_x=ax,
                        avg_y=ay,
                        progressive_actions=pinfo["progressive_actions"],
                        tackles=pinfo.get("tackles"),
                        interceptions=pinfo.get("interceptions"),
                        fouls=pinfo.get("fouls"),
                        recoveries=pinfo.get("recoveries"),
                    )
                )

        upsert_rows("player_match_stats", pms_rows)

        # Convert Understat shots (or FotMob shotmap fallback) to PitchEventSamples
        u_ext_to_internal: dict[int, int] = {}
        if home_team.get("understat_id"):
            u_ext_to_internal[int(home_team["understat_id"])] = home_id
        if away_team.get("understat_id"):
            u_ext_to_internal[int(away_team["understat_id"])] = away_id

        e_ext_to_internal: dict[int, int] = {}
        if home_e_id is not None:
            e_ext_to_internal[int(home_e_id)] = home_id
        if away_e_id is not None:
            e_ext_to_internal[int(away_e_id)] = away_id

        pitch_events: list[PitchEventSample] = []
        if u_dto and u_dto.events:
            for ev in u_dto.events:
                tid = u_ext_to_internal.get(ev.team_external_id)
                if tid is None:
                    continue
                pitch_events.append(
                    PitchEventSample(
                        team_id=tid,
                        event_type=ev.type,
                        x=ev.x,
                        y=ev.y,
                        xg=ev.xg,
                        is_goal=bool(ev.outcome),
                    )
                )
        elif e_dto and e_dto.events:
            for ev in e_dto.events:
                tid = e_ext_to_internal.get(ev.team_external_id)
                if tid is None:
                    continue
                pitch_events.append(
                    PitchEventSample(
                        team_id=tid,
                        event_type=ev.type,
                        x=ev.x,
                        y=ev.y,
                        xg=ev.xg,
                        is_goal=bool(ev.outcome),
                    )
                )

        # Backfill match-level xG from FotMob/Understat when missing on `matches`
        fetched_home_xg = (
            u_dto.fixture.home_xg
            if (u_dto and u_dto.fixture.home_xg is not None)
            else (e_dto.fixture.home_xg if e_dto else None)
        )
        fetched_away_xg = (
            u_dto.fixture.away_xg
            if (u_dto and u_dto.fixture.away_xg is not None)
            else (e_dto.fixture.away_xg if e_dto else None)
        )
        if (m.get("home_xg") is None and fetched_home_xg is not None) or (
            m.get("away_xg") is None and fetched_away_xg is not None
        ):
            xg_patch: dict[str, Any] = {}
            if fetched_home_xg is not None:
                xg_patch["home_xg"] = round(float(fetched_home_xg), 3)
            if fetched_away_xg is not None:
                xg_patch["away_xg"] = round(float(fetched_away_xg), 3)
            if xg_patch:
                get_client().table("matches").update(xg_patch).eq("id", mid).execute()

        # Build Opta team stats objects when FotMob/events telemetry is available
        opta_by_idx: dict[int, TeamMatchOptaStats | None] = {0: None, 1: None}
        if e_dto is not None:
            for idx in (0, 1):
                tl = e_dto.teams[idx]
                opta_by_idx[idx] = TeamMatchOptaStats(
                    own_half_passes=tl.own_half_passes,
                    opp_half_passes=tl.opp_half_passes,
                    tackles=tl.tackles,
                    interceptions=tl.interceptions,
                    fouls=tl.fouls,
                    touches_opp_box=tl.touches_opp_box,
                    attack_bias_left=tl.attack_bias_left,
                    attack_bias_center=tl.attack_bias_center,
                    attack_bias_right=tl.attack_bias_right,
                )

        # Build tactical fingerprints for both teams
        tactics_rows: list[TeamMatchTacticsUpsert] = []
        for idx, (tid, opp_id) in enumerate(((home_id, away_id), (away_id, home_id))):
            opp_idx = 1 - idx
            form = (e_dto.teams[idx].formation if e_dto else None) or (
                u_dto.teams[idx].formation if u_dto else None
            )
            poss = e_dto.teams[idx].possession if e_dto else None
            ppda = u_dto.teams[idx].ppda if u_dto else None

            tactics_rows.append(
                build_team_match_fingerprint(
                    match_id=mid,
                    team_id=tid,
                    formation=form,
                    possession=poss,
                    provider_ppda=ppda,
                    team_players=pos_samples[tid],
                    opp_players=pos_samples[opp_id],
                    events=pitch_events,
                    team_opta=opta_by_idx[idx],
                    opp_opta=opta_by_idx[opp_idx],
                    player_stats=pms_rows,
                )
            )

        upsert_rows("team_match_tactics", tactics_rows)
        synced += 1

    log.info("Synced telemetry for %d finished matches", synced)
    return synced


def run_deterministic_engine_on_db(season: str) -> dict[str, Any]:
    """Recompute chameleon shifts, archetypes, conditional splits, and how-to-beat rows."""
    db_matches = fetch_table("matches", eq={"season": season, "status": "finished"}, order="round")
    if not db_matches:
        log.info("No finished matches in DB for season %s yet", season)
        return {"finished_matches": 0}

    match_ids = {int(m["id"]) for m in db_matches}
    match_by_id = {int(m["id"]): m for m in db_matches}

    raw_tactics = [
        TeamMatchTacticsUpsert.model_validate(t)
        for t in fetch_table("team_match_tactics")
        if int(t["match_id"]) in match_ids
    ]
    raw_pms = [
        PlayerMatchStatsUpsert.model_validate(ps)
        for ps in fetch_table("player_match_stats")
        if int(ps["match_id"]) in match_ids
    ]
    db_players = fetch_table("players")
    db_teams = fetch_table("teams")

    # 1. Chameleon Detector
    tiers = compute_league_tiers(
        [
            (
                int(m["home_team_id"]),
                int(m["away_team_id"]),
                m.get("home_goals"),
                m.get("away_goals"),
                float(m["home_xg"]) if m.get("home_xg") is not None else None,
                float(m["away_xg"]) if m.get("away_xg") is not None else None,
            )
            for m in db_matches
        ]
    )

    records_by_team: dict[int, list[TeamMatchRecord]] = defaultdict(list)
    for tac in raw_tactics:
        m = match_by_id.get(tac.match_id)
        if not m:
            continue
        is_home = tac.team_id == int(m["home_team_id"])
        opp_id = int(m["away_team_id"]) if is_home else int(m["home_team_id"])
        xg = m.get("home_xg") if is_home else m.get("away_xg")
        xga = m.get("away_xg") if is_home else m.get("home_xg")
        gf = m.get("home_goals") if is_home else m.get("away_goals")
        ga = m.get("away_goals") if is_home else m.get("home_goals")
        records_by_team[tac.team_id].append(
            TeamMatchRecord(
                match_id=tac.match_id,
                round=int(m["round"]),
                team_id=tac.team_id,
                opponent_id=opp_id,
                xg=float(xg) if xg is not None else None,
                xga=float(xga) if xga is not None else None,
                goals_for=gf,
                goals_against=ga,
                tactics=tac,
            )
        )

    pms_by_match_team: dict[tuple[int, int], list[PlayerMatchStatsUpsert]] = defaultdict(list)
    for ps in raw_pms:
        pms_by_match_team[(ps.match_id, ps.team_id)].append(ps)

    enriched_tactics: list[TeamMatchTacticsUpsert] = []
    for tid, recs in records_by_team.items():
        report = detect_chameleon_shifts(tid, recs, tiers)
        for tac in report.updated_tactics:
            if tac.dribbles_zones_json is None:
                m_pms = pms_by_match_team.get((tac.match_id, tac.team_id), [])
                if m_pms:
                    tac = tac.model_copy(
                        update={
                            "dribbles_zones_json": build_dribbles_zones(
                                m_pms, team_id=tac.team_id
                            )
                        }
                    )
            enriched_tactics.append(tac)

    upsert_rows("team_match_tactics", enriched_tactics)

    # 2. Archetype Classifier (>= 180 minutes)
    tactics_by_mt = {(t.match_id, t.team_id): t for t in enriched_tactics}
    pms_by_player: dict[int, list[PlayerMatchStatsUpsert]] = defaultdict(list)
    for ps in raw_pms:
        pms_by_player[ps.player_id].append(ps)

    aggregates: list[PlayerSeasonAggregate] = []
    for p in db_players:
        pid = int(p["id"])
        entries = pms_by_player.get(pid, [])
        mins = sum(e.minutes for e in entries)
        xs = [e.avg_x for e in entries if e.avg_x is not None]
        ys = [e.avg_y for e in entries if e.avg_y is not None]
        b3_mins = sum(
            e.minutes
            for e in entries
            if (tactics_by_mt.get((e.match_id, e.team_id)) is not None)
            and (tactics_by_mt[(e.match_id, e.team_id)].back_line_count in (3, 5))
        )
        aggregates.append(
            PlayerSeasonAggregate(
                player_id=pid,
                primary_position=p["primary_position"],
                minutes_total=mins,
                dribbles_won=sum(e.dribbles_won or 0 for e in entries),
                dribbles_past=sum(e.dribbles_past or 0 for e in entries),
                duels_won=sum(e.duels_won or 0 for e in entries),
                duels_lost=sum(e.duels_lost or 0 for e in entries),
                progressive_actions=sum(e.progressive_actions or 0 for e in entries),
                xg=sum(e.xg or 0.0 for e in entries),
                xa=sum(e.xa or 0.0 for e in entries),
                avg_x=(sum(xs) / len(xs)) if xs else None,
                avg_y=(sum(ys) / len(ys)) if ys else None,
                back_three_minutes=b3_mins,
            )
        )

    classifications = classify_players(aggregates)
    player_archetypes: dict[int, PlayerArchetype | None] = {}
    client = get_client()
    for agg in aggregates:
        cls = classifications[agg.player_id]
        player_archetypes[agg.player_id] = cls.archetype_primary
        radar_payload = (
            [ax.model_dump(mode="json") for ax in cls.radar_percentiles_json]
            if cls.radar_percentiles_json is not None
            else None
        )
        client.table("players").update(
            {
                "minutes_total": agg.minutes_total,
                "archetype_primary": cls.archetype_primary,
                "archetype_secondary": cls.archetype_secondary,
                "archetype_scores_json": cls.archetype_scores_json,
                "radar_percentiles_json": radar_payload,
            }
        ).eq("id", agg.player_id).execute()

    # 3. Conditional Splits (Team & Player)
    finished_contexts = [
        FinishedMatchContext(
            match_id=int(m["id"]),
            season=season,
            round=int(m["round"]),
            home_team_id=int(m["home_team_id"]),
            away_team_id=int(m["away_team_id"]),
            home_xg=float(m["home_xg"]) if m.get("home_xg") is not None else None,
            away_xg=float(m["away_xg"]) if m.get("away_xg") is not None else None,
        )
        for m in db_matches
    ]

    team_splits = compute_team_splits(
        season=season,
        matches=finished_contexts,
        tactics=enriched_tactics,
        player_stats=raw_pms,
        player_archetypes=player_archetypes,
    )
    player_splits = compute_player_splits(
        season=season,
        tactics=enriched_tactics,
        player_stats=raw_pms,
        player_archetypes=player_archetypes,
    )

    upsert_rows("team_conditional_splits", [s.row for s in team_splits])
    upsert_rows("player_conditional_splits", [s.row for s in player_splits])

    # 4. How-To-Beat Top 3 Vulnerabilities per team
    latest_round = max(int(m["round"]) for m in db_matches)
    htb_by_team: dict[int, list[Any]] = {}
    for t in db_teams:
        tid = int(t["id"])
        vulns = extract_team_vulnerabilities(
            team_id=tid,
            team_splits=team_splits,
            team_tactics=enriched_tactics,
            top_k=3,
        )
        htb_by_team[tid] = vulns

    return {
        "finished_matches": len(db_matches),
        "latest_round": latest_round,
        "db_matches": db_matches,
        "db_teams": db_teams,
        "db_players": db_players,
        "enriched_tactics": enriched_tactics,
        "player_stats": raw_pms,
        "player_archetypes": player_archetypes,
        "team_splits": team_splits,
        "player_splits": player_splits,
        "htb_by_team": htb_by_team,
    }


def run_post_match_ai(
    season: str, engine_state: dict[str, Any], *, target_round: int | None = None
) -> None:
    if not engine_state.get("finished_matches"):
        return
    settings = get_settings()
    if settings.gemini_api_key is None:
        log.info("GEMINI_API_KEY not set; persisting deterministic how_to_beat without AI prose")
        htb_rows = [
            TeamHowToBeatUpsert(
                team_id=tid,
                season=season,
                through_round=engine_state["latest_round"],
                vulnerabilities_json=vulns,
                ai_playbook_text=None,
            )
            for tid, vulns in engine_state["htb_by_team"].items()
        ]
        upsert_rows("team_how_to_beat", htb_rows)
        return

    analyst = GeminiAnalyst()
    team_names = {int(t["id"]): str(t["name"]) for t in engine_state["db_teams"]}
    player_names = {int(p["id"]): str(p["name"]) for p in engine_state["db_players"]}
    tactics_map = {(t.match_id, t.team_id): t for t in engine_state["enriched_tactics"]}

    round_to_brief = target_round or engine_state["latest_round"]
    for m in engine_state["db_matches"]:
        if int(m["round"]) != round_to_brief:
            continue
        mid = int(m["id"])
        hid, aid = int(m["home_team_id"]), int(m["away_team_id"])
        score_str = f"{m.get('home_goals', '?')}-{m.get('away_goals', '?')}"
        try:
            analyst.generate_post_match_brief(
                match_id=mid,
                home_team_id=hid,
                away_team_id=aid,
                home_team_name=team_names.get(hid, str(hid)),
                away_team_name=team_names.get(aid, str(aid)),
                score_str=score_str,
                home_tactics=tactics_map.get((mid, hid)),
                away_tactics=tactics_map.get((mid, aid)),
                player_stats=engine_state["player_stats"],
                player_names=player_names,
                player_archetypes=engine_state["player_archetypes"],
                source_updated_at=_safe_parse_dt(m.get("updated_at")),
            )
        except Exception as exc:
            log.warning("Post-match AI brief failed for match_id=%d: %s", mid, exc)

    # Team How-To-Beat playbooks
    for t in engine_state["db_teams"]:
        tid = int(t["id"])
        vulns = engine_state["htb_by_team"].get(tid, [])
        team_forms = [
            tac.formation
            for tac in engine_state["enriched_tactics"]
            if tac.team_id == tid and tac.formation
        ]
        base_form = Counter(team_forms).most_common(1)[0][0] if team_forms else None
        try:
            analyst.generate_how_to_beat_playbook(
                team_id=tid,
                team_name=team_names.get(tid, str(tid)),
                season=season,
                through_round=engine_state["latest_round"],
                vulnerabilities=vulns,
                baseline_formation=base_form,
            )
        except Exception as exc:
            log.warning("How-to-beat AI playbook failed for team_id=%d: %s", tid, exc)


def run_pre_match_pipeline(
    season: str,
    *,
    target_round: int | None = None,
    skip_ai: bool = False,
) -> int:
    """Compute upcoming matchup scores, X-factors, and pre-match AI briefs."""
    scheduled = fetch_table("matches", eq={"season": season, "status": "scheduled"}, order="round")
    if not scheduled:
        log.info("No scheduled matches found for season %s", season)
        return 0

    next_round = target_round or min(int(m["round"]) for m in scheduled)
    upcoming = [m for m in scheduled if int(m["round"]) == next_round]
    log.info("Running pre-match analysis for round %d (%d matches)", next_round, len(upcoming))

    db_teams = {int(t["id"]): str(t["name"]) for t in fetch_table("teams")}
    db_players = fetch_table("players")
    finished = fetch_table("matches", eq={"season": season, "status": "finished"}, order="round")
    fin_ids = [int(m["id"]) for m in finished]

    tactics = [
        TeamMatchTacticsUpsert.model_validate(t)
        for t in fetch_table("team_match_tactics")
        if int(t["match_id"]) in set(fin_ids)
    ]
    pms = [
        PlayerMatchStatsUpsert.model_validate(ps)
        for ps in fetch_table("player_match_stats")
        if int(ps["match_id"]) in set(fin_ids)
    ]

    # Reconstruct TeamSplitResult & PlayerSplitResult from DB rows
    from db.models import PlayerConditionalSplitUpsert, TeamConditionalSplitUpsert
    from engine.conditional_splits import PlayerSplitResult, TeamSplitResult

    team_splits = [
        TeamSplitResult(
            row=TeamConditionalSplitUpsert(
                team_id=int(r["team_id"]),
                season=r["season"],
                condition_type=r["condition_type"],
                condition_value=r["condition_value"],
                sample_matches=int(r["sample_matches"]),
                xg_delta=float(r["xg_delta"]) if r.get("xg_delta") is not None else None,
                xga_delta=float(r["xga_delta"]) if r.get("xga_delta") is not None else None,
                dribbles_conceded_delta=(
                    float(r["dribbles_conceded_delta"])
                    if r.get("dribbles_conceded_delta") is not None
                    else None
                ),
            ),
            confidence=r["confidence"],
        )
        for r in fetch_table("team_conditional_splits", eq={"season": season})
    ]
    player_splits = [
        PlayerSplitResult(
            row=PlayerConditionalSplitUpsert(
                player_id=int(r["player_id"]),
                season=r["season"],
                condition_type=r["condition_type"],
                condition_value=r["condition_value"],
                sample_minutes=int(r["sample_minutes"]),
                rating_delta=float(r["rating_delta"])
                if r.get("rating_delta") is not None
                else None,
                dribbles_delta=float(r["dribbles_delta"])
                if r.get("dribbles_delta") is not None
                else None,
                duels_delta=float(r["duels_delta"]) if r.get("duels_delta") is not None else None,
            ),
            confidence=r["confidence"],
        )
        for r in fetch_table("player_conditional_splits", eq={"season": season})
    ]

    players_by_team: dict[int, list[tuple[int, str, PlayerPosition, PlayerArchetype | None]]] = (
        defaultdict(list)
    )
    for p in db_players:
        if p.get("team_id") is not None:
            players_by_team[int(p["team_id"])].append(
                (int(p["id"]), str(p["name"]), p["primary_position"], p.get("archetype_primary"))
            )

    settings = get_settings()
    analyst = GeminiAnalyst() if (not skip_ai and settings.gemini_api_key is not None) else None

    processed = 0
    for m in upcoming:
        mid = int(m["id"])
        hid, aid = int(m["home_team_id"]), int(m["away_team_id"])
        home_recent_ids = [
            int(fm["id"])
            for fm in finished
            if hid in (int(fm["home_team_id"]), int(fm["away_team_id"]))
        ]
        away_recent_ids = [
            int(fm["id"])
            for fm in finished
            if aid in (int(fm["home_team_id"]), int(fm["away_team_id"]))
        ]

        home_starters = infer_probable_starters(
            team_id=hid,
            team_players=players_by_team.get(hid, []),
            recent_stats=pms,
            recent_match_ids=home_recent_ids,
        )
        away_starters = infer_probable_starters(
            team_id=aid,
            team_players=players_by_team.get(aid, []),
            recent_stats=pms,
            recent_match_ids=away_recent_ids,
        )
        analysis = score_upcoming_matchup(
            match_id=mid,
            home_team_id=hid,
            away_team_id=aid,
            home_starters=home_starters,
            away_starters=away_starters,
            tactics_history=tactics,
            team_splits=team_splits,
            player_splits=player_splits,
        )
        log.info(
            "Match %d (%s vs %s): %d key duels, %d X-factors, %d starter obs",
            mid,
            db_teams.get(hid, hid),
            db_teams.get(aid, aid),
            len(analysis.key_duels),
            len(analysis.x_factors),
            len(analysis.starter_observations),
        )
        if analyst is not None:
            try:
                analyst.generate_pre_match_brief(
                    home_team_name=db_teams.get(hid, str(hid)),
                    away_team_name=db_teams.get(aid, str(aid)),
                    analysis=analysis,
                    source_updated_at=_safe_parse_dt(m.get("updated_at")),
                )
            except Exception as exc:
                log.warning("Pre-match AI brief failed for match_id=%d: %s", mid, exc)
        processed += 1

    return processed


def run_dry_run(season: str) -> int:
    """Zero-write, zero-AI validation run over live fixtures (or synthetic fallback)."""
    log.info("Starting DRY RUN for season %s (0 DB writes, 0 Gemini calls)", season)
    with PoliteHttpClient(min_interval_s=1.0, timeout_s=15.0) as http:
        reconciled = _fetch_all_fixtures(http, season)

    log.info("DRY RUN summary: %d reconciled fixtures fetched", len(reconciled))
    for fx in reconciled[:5]:
        log.info(
            "  R%02d %s vs %s [%s] kickoff=%s (u=%s f=%s s=%s)",
            fx.round,
            fx.home_team.short_name,
            fx.away_team.short_name,
            fx.status,
            fx.kickoff_at.isoformat(),
            fx.understat_id,
            fx.fotmob_id,
            fx.sofascore_id,
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Tactix Serie A ETL & Tactical Engine Runner")
    parser.add_argument(
        "--mode",
        choices=("post_match", "pre_match", "full", "dry_run"),
        required=True,
    )
    parser.add_argument("--season", default=get_settings().season)
    parser.add_argument("--round", type=int, default=None, dest="target_round")
    parser.add_argument("--skip-ai", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    mode: SyncMode = args.mode
    season: str = args.season

    if mode == "dry_run":
        return run_dry_run(season)

    # Always ping Supabase first (health check + keeps Free tier awake)
    log.info("Pinging Supabase at %s UTC...", datetime.now(UTC).isoformat())
    ping_db()

    with PoliteHttpClient() as http:
        reconciled = _fetch_all_fixtures(http, season)
        if reconciled:
            sync_teams_and_matches(reconciled)

        if mode in ("post_match", "full"):
            sync_match_telemetry(http, season, target_round=args.target_round)
            engine_state = run_deterministic_engine_on_db(season)
            if not args.skip_ai:
                run_post_match_ai(season, engine_state, target_round=args.target_round)

        if mode in ("pre_match", "full"):
            run_pre_match_pipeline(season, target_round=args.target_round, skip_ai=args.skip_ai)

    log.info("Sync completed successfully (mode=%s, season=%s)", mode, season)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Batch AI Analyst using official `google-genai` SDK with Structured Outputs.

Responsibilities:
  - Reads deterministic JSON computed by `engine/` (or loaded from Supabase).
  - Generates in dry, technical, non-cliché Italian:
      1. `MatchAiBriefUpsert` (`pre_match` and `post_match`):
         - tactical_summary: clash of tactical ideas
         - key_edges_json: 3 non-obvious tactical keys (all metrics from engine)
         - x_factors_json: 3 most impactful players
         - player_observations_json: 1-2 sentence observation for EVERY starter
      2. `TeamHowToBeatUpsert`:
         - ai_playbook_text: "Come battere [Squadra]" grounded in top 3 vulnerabilities
  - Anti-waste guard: skips Gemini calls when an existing brief/playbook is already
    fresh and underlying data has not changed.
  - Rate-limit guard: spaces API calls via `GEMINI_DELAY_S` to stay within Google AI
    Studio free-tier RPM limits.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from ai.client import generate_structured
from ai.schemas import HowToBeatNarrative, MatchBriefNarrative
from config import get_settings
from db.client import brief_is_fresh, how_to_beat_is_fresh, upsert_rows
from db.models import (
    BriefType,
    EvidenceTeamMatch,
    KeyEdge,
    MatchAiBriefUpsert,
    MatchupDuelRow,
    PlayerMatchStatsUpsert,
    PlayerObservation,
    SampleSize,
    TeamHowToBeatUpsert,
    TeamMatchTacticsUpsert,
    Vulnerability,
    XFactor,
)
from engine.archetype_classifier import ARCHETYPE_LABELS_IT
from engine.matchup_scorer import (
    EdgeCandidate,
    MatchupAnalysis,
    StarterObservationCandidate,
    XFactorCandidate,
    duels_to_matchup_rows,
)

log = logging.getLogger(__name__)


def _pre_match_payload(
    *,
    home_team_name: str,
    away_team_name: str,
    analysis: MatchupAnalysis,
) -> dict[str, Any]:
    return {
        "brief_type": "pre_match",
        "match_id": analysis.match_id,
        "home_team": {
            "id": analysis.home_team_id,
            "name": home_team_name,
            "probable_formation": analysis.home_probable_formation,
            "defensive_line_height": analysis.home_line_height,
        },
        "away_team": {
            "id": analysis.away_team_id,
            "name": away_team_name,
            "probable_formation": analysis.away_probable_formation,
            "defensive_line_height": analysis.away_line_height,
        },
        "edge_candidates": [
            {
                "edge_key": e.edge_key,
                "team_id": e.team_id,
                "against_team_id": e.against_team_id,
                "metric_key": e.metric_key,
                "metric_value": e.metric_value,
                "zone": e.zone,
                "sample": e.sample.to_db(),
                "confidence": e.confidence,
                "fact": e.fact,
            }
            for e in analysis.edge_candidates[:6]
        ],
        "x_factor_candidates": [
            {
                "candidate_key": xf.candidate_key,
                "player_id": xf.player_id,
                "player_name": xf.player_name,
                "team_id": xf.team_id,
                "archetype": ARCHETYPE_LABELS_IT.get(xf.archetype, "") if xf.archetype else None,
                "mismatch_score": xf.mismatch_score,
                "metric_key": xf.metric_key,
                "metric_value": xf.metric_value,
                "confidence": xf.confidence,
                "fact": xf.fact,
            }
            for xf in analysis.x_factors[:5]
        ],
        "starter_candidates": [
            {
                "candidate_key": ob.candidate_key,
                "player_id": ob.player_id,
                "player_name": ob.player_name,
                "team_id": ob.team_id,
                "position": ob.position,
                "archetype": ARCHETYPE_LABELS_IT.get(ob.archetype, "") if ob.archetype else None,
                "matchup_player_name": ob.matchup_player_name,
                "matchup_archetype": (
                    ARCHETYPE_LABELS_IT.get(ob.matchup_archetype, "")
                    if ob.matchup_archetype
                    else None
                ),
                "metric_key": ob.metric_key,
                "metric_value": ob.metric_value,
                "sentiment_hint": ob.sentiment_hint,
                "fact": ob.fact,
            }
            for ob in analysis.starter_observations
        ],
    }


def _merge_brief_narrative(
    *,
    match_id: int,
    brief_type: BriefType,
    narrative: MatchBriefNarrative,
    edge_candidates: Sequence[EdgeCandidate],
    xf_candidates: Sequence[XFactorCandidate],
    starter_candidates: Sequence[StarterObservationCandidate],
    model_name: str,
    matchups: Sequence[MatchupDuelRow] = (),
) -> MatchAiBriefUpsert:
    """Merge Gemini prose with engine-verified numeric metrics, samples, and evidence."""
    edge_map = {e.edge_key: e for e in edge_candidates}
    xf_map = {x.candidate_key: x for x in xf_candidates}
    obs_map = {o.candidate_key: o for o in starter_candidates}

    key_edges: list[KeyEdge] = []
    used_edges: set[str] = set()
    for item in narrative.key_edges:
        cand = edge_map.get(item.edge_key)
        if cand is None or item.edge_key in used_edges:
            continue
        used_edges.add(item.edge_key)
        key_edges.append(
            KeyEdge(
                team_id=cand.team_id,
                against_team_id=cand.against_team_id,
                title=item.title.strip(),
                rationale=item.rationale.strip(),
                metric_key=cand.metric_key,
                metric_value=cand.metric_value,
                zone=cand.zone,
                player_ids=cand.player_ids,
                sample=cand.sample,
                confidence=cand.confidence,
                evidence=cand.evidence,
            )
        )

    x_factors: list[XFactor] = []
    used_xf: set[str] = set()
    for item in narrative.x_factors:
        cand = xf_map.get(item.candidate_key)
        if cand is None or item.candidate_key in used_xf:
            continue
        used_xf.add(item.candidate_key)
        x_factors.append(
            XFactor(
                player_id=cand.player_id,
                team_id=cand.team_id,
                title=item.title.strip(),
                rationale=item.rationale.strip(),
                metric_key=cand.metric_key,
                metric_value=cand.metric_value,
                confidence=cand.confidence,
            )
        )

    observations: list[PlayerObservation] = []
    covered_keys: set[str] = set()
    for item in narrative.player_observations:
        cand = obs_map.get(item.candidate_key)
        if cand is None or item.candidate_key in covered_keys:
            continue
        covered_keys.add(item.candidate_key)
        observations.append(
            PlayerObservation(
                player_id=cand.player_id,
                team_id=cand.team_id,
                observation=item.observation.strip(),
                sentiment=item.sentiment,
                matchup_player_id=cand.matchup_player_id,
                metric_key=cand.metric_key,
                metric_value=cand.metric_value,
            )
        )

    # Guarantee every starter has a grounded observation even if the model skipped one
    for cand in starter_candidates:
        if cand.candidate_key in covered_keys:
            continue
        sentiment = (
            cand.sentiment_hint
            if cand.sentiment_hint in ("positive", "negative", "neutral")
            else "neutral"
        )
        observations.append(
            PlayerObservation(
                player_id=cand.player_id,
                team_id=cand.team_id,
                observation=cand.fact,
                sentiment=sentiment,  # type: ignore[arg-type]
                matchup_player_id=cand.matchup_player_id,
                metric_key=cand.metric_key,
                metric_value=cand.metric_value,
            )
        )

    return MatchAiBriefUpsert(
        match_id=match_id,
        brief_type=brief_type,
        tactical_summary=narrative.tactical_summary.strip(),
        key_edges_json=key_edges[:3],
        x_factors_json=x_factors[:3],
        player_observations_json=observations,
        matchups_json=list(matchups),
        model=model_name,
    )


def build_post_match_candidates(
    *,
    match_id: int,
    home_team_id: int,
    away_team_id: int,
    home_tactics: TeamMatchTacticsUpsert | None,
    away_tactics: TeamMatchTacticsUpsert | None,
    player_stats: Sequence[PlayerMatchStatsUpsert],
    player_names: dict[int, str],
    player_archetypes: dict[int, Any],
) -> tuple[list[EdgeCandidate], list[XFactorCandidate], list[StarterObservationCandidate]]:
    """Build deterministic post-match edge, X-factor, and starter observation candidates."""
    match_stats = [ps for ps in player_stats if ps.match_id == match_id]
    starters = sorted(
        (ps for ps in match_stats if ps.minutes >= 45),
        key=lambda ps: (ps.team_id, -(ps.rating or 0.0)),
    )[:22]

    edge_candidates: list[EdgeCandidate] = []
    # Tactical shift / field tilt / xGA corridor edges
    for my_tac, opp_tac, my_id, opp_id in (
        (home_tactics, away_tactics, home_team_id, away_team_id),
        (away_tactics, home_tactics, away_team_id, home_team_id),
    ):
        if my_tac is None:
            continue
        if my_tac.field_tilt is not None and my_tac.field_tilt >= 58.0:
            edge_candidates.append(
                EdgeCandidate(
                    edge_key=f"post_tilt_{my_id}",
                    team_id=my_id,
                    against_team_id=opp_id,
                    metric_key="field_tilt",
                    metric_value=my_tac.field_tilt,
                    zone=None,
                    player_ids=[],
                    sample=SampleSize(unit="matches", value=1),
                    confidence="low",
                    evidence=EvidenceTeamMatch(
                        table="team_match_tactics", match_id=match_id, team_id=my_id
                    ),
                    score=my_tac.field_tilt,
                    fact=f"Dominio territoriale: field tilt {my_tac.field_tilt:.1f}%, PPDA {my_tac.ppda or 'n/d'}.",
                )
            )
        if opp_tac is not None and opp_tac.xga_zones_json is not None:
            oc = opp_tac.xga_zones_json.origin_corridors
            worst_side, worst_val = max(
                (("left", oc.left), ("center", oc.center), ("right", oc.right)),
                key=lambda kv: kv[1],
            )
            if worst_val >= 0.45:
                edge_candidates.append(
                    EdgeCandidate(
                        edge_key=f"post_xga_{my_id}_{worst_side}",
                        team_id=my_id,
                        against_team_id=opp_id,
                        metric_key="xga_origin",
                        metric_value=worst_val,
                        zone=worst_side,  # type: ignore[arg-type]
                        player_ids=[],
                        sample=SampleSize(unit="matches", value=1),
                        confidence="low",
                        evidence=EvidenceTeamMatch(
                            table="team_match_tactics", match_id=match_id, team_id=opp_id
                        ),
                        score=worst_val * 60.0,
                        fact=f"Prodotti {worst_val:.2f} xG dal lato difensivo {worst_side} avversario.",
                    )
                )

    # Top individual match performances -> X-Factors
    ranked_players = sorted(
        (ps for ps in match_stats if ps.minutes >= 30),
        key=lambda ps: (
            (ps.rating or 6.0)
            + (ps.xg or 0.0) * 1.5
            + (ps.xa or 0.0) * 1.5
            + (ps.dribbles_won or 0) * 0.25
        ),
        reverse=True,
    )
    xf_candidates: list[XFactorCandidate] = []
    for ps in ranked_players[:5]:
        pname = player_names.get(ps.player_id, f"Player {ps.player_id}")
        arch = player_archetypes.get(ps.player_id)
        metric_key = "rating"
        metric_val: float | None = ps.rating
        if (ps.xg or 0.0) >= 0.45:
            metric_key, metric_val = "xg", ps.xg
        elif (ps.xa or 0.0) >= 0.35:
            metric_key, metric_val = "xa", ps.xa
        elif (ps.dribbles_won or 0) >= 4:
            metric_key, metric_val = "dribbles_won", float(ps.dribbles_won or 0)

        xf_candidates.append(
            XFactorCandidate(
                candidate_key=f"xf_{ps.player_id}",
                player_id=ps.player_id,
                team_id=ps.team_id,
                player_name=pname,
                archetype=arch,
                metric_key=metric_key,
                metric_value=metric_val,
                confidence="low",
                mismatch_score=75.0,
                fact=(
                    f"{pname}: rating {ps.rating or 'n/d'}, xG {ps.xg or 0:.2f}, xA {ps.xa or 0:.2f}, "
                    f"{ps.dribbles_won or 0} dribbling riusciti, {ps.progressive_actions or 0} azioni progressive ({ps.minutes}')."
                ),
            )
        )

    starter_obs: list[StarterObservationCandidate] = []
    for ps in starters:
        pname = player_names.get(ps.player_id, f"Player {ps.player_id}")
        arch = player_archetypes.get(ps.player_id)
        arch_label = (
            ARCHETYPE_LABELS_IT.get(arch, ps.position_played or "")
            if arch
            else (ps.position_played or "")
        )

        sentiment = "neutral"
        m_key: str | None = "rating"
        m_val: float | None = ps.rating
        if (ps.dribbles_past or 0) >= 3:
            sentiment, m_key, m_val = "negative", "dribbles_past", float(ps.dribbles_past or 0)
        elif (ps.rating or 6.5) >= 7.2:
            sentiment = "positive"
        elif (ps.rating or 6.5) <= 5.9:
            sentiment = "negative"

        starter_obs.append(
            StarterObservationCandidate(
                candidate_key=f"obs_{ps.player_id}",
                player_id=ps.player_id,
                team_id=ps.team_id,
                player_name=pname,
                position=ps.position_played or "CM",
                archetype=arch,
                matchup_player_id=None,
                matchup_player_name=None,
                matchup_archetype=None,
                metric_key=m_key,
                metric_value=m_val,
                sentiment_hint=sentiment,
                fact=(
                    f"{pname} ({arch_label}, {ps.minutes}'): rating {ps.rating or 'n/d'}, "
                    f"duelli {ps.duels_won or 0}/{(ps.duels_won or 0) + (ps.duels_lost or 0)}, "
                    f"dribbling vinti {ps.dribbles_won or 0}, saltato {ps.dribbles_past or 0}."
                ),
            )
        )

    return edge_candidates, xf_candidates, starter_obs


class GeminiAnalyst:
    """Batch Gemini analyst with anti-waste caching and rate-limit pacing."""

    def __init__(self, *, delay_s: float | None = None, dry_run: bool = False) -> None:
        self.settings = get_settings()
        self.delay_s = self.settings.gemini_delay_s if delay_s is None else delay_s
        self.dry_run = dry_run

    def generate_pre_match_brief(
        self,
        *,
        home_team_name: str,
        away_team_name: str,
        analysis: MatchupAnalysis,
        source_updated_at: datetime | None = None,
        persist: bool = True,
    ) -> MatchAiBriefUpsert | None:
        if not self.dry_run and brief_is_fresh(analysis.match_id, "pre_match", source_updated_at):
            log.info("Skipping pre_match brief for match_id=%d (already fresh)", analysis.match_id)
            return None

        payload = _pre_match_payload(
            home_team_name=home_team_name,
            away_team_name=away_team_name,
            analysis=analysis,
        )
        task = (
            f"Produci il brief tattico PRE-PARTITA per {home_team_name} vs {away_team_name}. "
            "Restituisci: (1) tactical_summary sullo scontro di idee tattiche; "
            "(2) le 3 key_edges meno scontate usando gli edge_key forniti; "
            "(3) i 3 x_factors più incisivi usando i candidate_key forniti; "
            "(4) una player_observation sintetica (1-2 frasi) per OGNI titolare in starter_candidates "
            "agganciata ai suoi split e archetipi."
        )
        narrative = generate_structured(MatchBriefNarrative, payload, task, delay_s=self.delay_s)
        matchups = duels_to_matchup_rows(analysis.key_duels, home_team_id=analysis.home_team_id)
        brief = _merge_brief_narrative(
            match_id=analysis.match_id,
            brief_type="pre_match",
            narrative=narrative,
            edge_candidates=analysis.edge_candidates,
            xf_candidates=analysis.x_factors,
            starter_candidates=analysis.starter_observations,
            model_name=self.settings.gemini_model,
            matchups=matchups,
        )
        if persist and not self.dry_run:
            upsert_rows("match_ai_briefs", [brief])
        return brief

    def generate_post_match_brief(
        self,
        *,
        match_id: int,
        home_team_id: int,
        away_team_id: int,
        home_team_name: str,
        away_team_name: str,
        score_str: str,
        home_tactics: TeamMatchTacticsUpsert | None,
        away_tactics: TeamMatchTacticsUpsert | None,
        player_stats: Sequence[PlayerMatchStatsUpsert],
        player_names: dict[int, str],
        player_archetypes: dict[int, Any],
        source_updated_at: datetime | None = None,
        persist: bool = True,
    ) -> MatchAiBriefUpsert | None:
        if not self.dry_run and brief_is_fresh(match_id, "post_match", source_updated_at):
            log.info("Skipping post_match brief for match_id=%d (already fresh)", match_id)
            return None

        edges, xfs, starters = build_post_match_candidates(
            match_id=match_id,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            home_tactics=home_tactics,
            away_tactics=away_tactics,
            player_stats=player_stats,
            player_names=player_names,
            player_archetypes=player_archetypes,
        )
        payload = {
            "brief_type": "post_match",
            "match_id": match_id,
            "match": f"{home_team_name} vs {away_team_name} ({score_str})",
            "home_tactics": home_tactics.to_db() if home_tactics else None,
            "away_tactics": away_tactics.to_db() if away_tactics else None,
            "edge_candidates": [
                {
                    "edge_key": e.edge_key,
                    "team_id": e.team_id,
                    "metric_key": e.metric_key,
                    "metric_value": e.metric_value,
                    "fact": e.fact,
                }
                for e in edges[:6]
            ],
            "x_factor_candidates": [
                {"candidate_key": x.candidate_key, "player_name": x.player_name, "fact": x.fact}
                for x in xfs[:5]
            ],
            "starter_candidates": [
                {
                    "candidate_key": s.candidate_key,
                    "player_name": s.player_name,
                    "position": s.position,
                    "fact": s.fact,
                }
                for s in starters
            ],
        }
        task = (
            f"Produci l'analisi tattica POST-PARTITA per {home_team_name} vs {away_team_name} ({score_str}). "
            "Evidenzia eventuali cambi tattici (`is_tactical_shift`), le 3 chiavi decisive, "
            "i 3 giocatori più incisivi e una player_observation sintetica (1-2 frasi) per OGNI titolare."
        )
        narrative = generate_structured(MatchBriefNarrative, payload, task, delay_s=self.delay_s)
        brief = _merge_brief_narrative(
            match_id=match_id,
            brief_type="post_match",
            narrative=narrative,
            edge_candidates=edges,
            xf_candidates=xfs,
            starter_candidates=starters,
            model_name=self.settings.gemini_model,
        )
        if persist and not self.dry_run:
            upsert_rows("match_ai_briefs", [brief])
        return brief

    def generate_how_to_beat_playbook(
        self,
        *,
        team_id: int,
        team_name: str,
        season: str,
        through_round: int | None,
        vulnerabilities: Sequence[Vulnerability],
        baseline_formation: str | None = None,
        persist: bool = True,
    ) -> TeamHowToBeatUpsert | None:
        vuln_dicts = [v.to_db() for v in vulnerabilities]
        if not self.dry_run and how_to_beat_is_fresh(team_id, season, through_round, vuln_dicts):
            log.info("Skipping how_to_beat playbook for team_id=%d (unchanged)", team_id)
            return None

        if not vulnerabilities:
            row = TeamHowToBeatUpsert(
                team_id=team_id,
                season=season,
                through_round=through_round,
                vulnerabilities_json=[],
                ai_playbook_text=None,
            )
            if persist and not self.dry_run:
                upsert_rows("team_how_to_beat", [row])
            return row

        payload = {
            "team_name": team_name,
            "season": season,
            "through_round": through_round,
            "baseline_formation": baseline_formation,
            "vulnerabilities": vuln_dicts,
        }
        task = (
            f"Scrivi il playbook 'Come battere {team_name}' in 3-4 frasi asciutte e imperative "
            "(come un match analyst che prepara il piano gara per lo staff tecnico), "
            "basandoti esclusivamente sulle 3 vulnerabilità statistiche fornite."
        )
        narrative = generate_structured(HowToBeatNarrative, payload, task, delay_s=self.delay_s)
        row = TeamHowToBeatUpsert(
            team_id=team_id,
            season=season,
            through_round=through_round,
            vulnerabilities_json=list(vulnerabilities),
            ai_playbook_text=narrative.ai_playbook_text.strip(),
        )
        if persist and not self.dry_run:
            upsert_rows("team_how_to_beat", [row])
        return row

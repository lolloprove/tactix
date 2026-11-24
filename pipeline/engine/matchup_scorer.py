"""Upcoming Matchup Scorer & X-Factor Selector (ZERO AI).

For every scheduled match of the upcoming round:
  1. Infers probable starting XIs + average zones/corridors from recent matches.
  2. Crosses opposite corridors to identify direct key duels.
  3. Computes a bounded deterministic Mismatch Score (0-100) for every duel,
     weighted by sample confidence (`low`/`medium`/`high`).
  4. Selects the top 3 potential X-Factors (`XFactorCandidate`).
  5. Produces deterministic `EdgeCandidate`s and per-starter `ObservationCandidate`s
     for EVERY probable starter so the Gemini layer writes prose grounded strictly
     in verified engine numbers.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from db.models import (
    ConfidenceLevel,
    EvidencePlayerSplit,
    EvidenceRef,
    EvidenceTeamSplit,
    MatchupDuelRow,
    PlayerArchetype,
    PlayerMatchStatsUpsert,
    PlayerPosition,
    SampleSize,
    TeamMatchTacticsUpsert,
    ZoneCorridor,
)
from engine.archetype_classifier import ARCHETYPE_LABELS_IT
from engine.conditional_splits import (
    ATTACKING_POSITIONS,
    DEFENSIVE_POSITIONS,
    PlayerSplitResult,
    TeamSplitResult,
)
from engine.pitch import (
    corridor_from_x,
    facing_corridors,
    line_height,
    position_default_corridor,
)

CONFIDENCE_WEIGHT: dict[ConfidenceLevel, float] = {
    "high": 1.0,
    "medium": 0.75,
    "low": 0.45,
}


@dataclass(frozen=True)
class ProbableStarter:
    player_id: int
    team_id: int
    name: str
    position: PlayerPosition
    archetype_primary: PlayerArchetype | None
    avg_x: float
    avg_y: float
    corridor: ZoneCorridor
    recent_minutes: int
    recent_rating: float | None


@dataclass(frozen=True)
class KeyDuel:
    duel_key: str
    attacker_id: int
    attacker_team_id: int
    attacker_name: str
    attacker_archetype: PlayerArchetype | None
    defender_id: int
    defender_team_id: int
    defender_name: str
    defender_archetype: PlayerArchetype | None
    zone: ZoneCorridor
    mismatch_score: float  # 0-100 (50 = neutral, >50 favours attacker, <50 favours defender)
    protagonist_id: int
    protagonist_team_id: int
    against_team_id: int
    metric_key: str
    metric_value: float | None
    sample: SampleSize
    confidence: ConfidenceLevel
    evidence: EvidenceRef | None
    summary_fact: str


@dataclass(frozen=True)
class EdgeCandidate:
    edge_key: str
    team_id: int
    against_team_id: int
    metric_key: str
    metric_value: float | None
    zone: ZoneCorridor | None
    player_ids: list[int]
    sample: SampleSize
    confidence: ConfidenceLevel
    evidence: EvidenceRef | None
    score: float
    fact: str


@dataclass(frozen=True)
class XFactorCandidate:
    candidate_key: str
    player_id: int
    team_id: int
    player_name: str
    archetype: PlayerArchetype | None
    metric_key: str
    metric_value: float | None
    confidence: ConfidenceLevel
    mismatch_score: float
    fact: str


@dataclass(frozen=True)
class StarterObservationCandidate:
    candidate_key: str
    player_id: int
    team_id: int
    player_name: str
    position: PlayerPosition
    archetype: PlayerArchetype | None
    matchup_player_id: int | None
    matchup_player_name: str | None
    matchup_archetype: PlayerArchetype | None
    metric_key: str | None
    metric_value: float | None
    sentiment_hint: str  # "positive" | "negative" | "neutral"
    fact: str


@dataclass(frozen=True)
class MatchupAnalysis:
    match_id: int
    home_team_id: int
    away_team_id: int
    home_probable_formation: str | None
    away_probable_formation: str | None
    home_line_height: str | None
    away_line_height: str | None
    home_starters: list[ProbableStarter]
    away_starters: list[ProbableStarter]
    key_duels: list[KeyDuel]
    edge_candidates: list[EdgeCandidate]
    x_factors: list[XFactorCandidate]
    starter_observations: list[StarterObservationCandidate]


def _clamp_score(raw: float) -> float:
    if not math.isfinite(raw):
        return 50.0
    return round(max(0.0, min(100.0, raw)), 1)


def infer_probable_starters(
    *,
    team_id: int,
    team_players: Sequence[tuple[int, str, PlayerPosition, PlayerArchetype | None]],
    recent_stats: Sequence[PlayerMatchStatsUpsert],
    recent_match_ids: Sequence[int],
) -> list[ProbableStarter]:
    """Select the 11 most probable starters from recent appearances and estimate their avg X/Y."""
    recent_set = set(recent_match_ids[-5:]) if recent_match_ids else None
    by_player: dict[int, list[PlayerMatchStatsUpsert]] = defaultdict(list)

    for s in recent_stats:
        if s.team_id != team_id:
            continue
        if recent_set is not None and s.match_id not in recent_set:
            continue
        by_player[s.player_id].append(s)

    candidates: list[tuple[float, ProbableStarter]] = []
    for pid, name, pos, arch in team_players:
        p_stats = by_player.get(pid, [])
        mins = sum(s.minutes for s in p_stats)
        xs = [s.avg_x for s in p_stats if s.avg_x is not None and math.isfinite(s.avg_x)]
        ys = [s.avg_y for s in p_stats if s.avg_y is not None and math.isfinite(s.avg_y)]
        ratings = [s.rating for s in p_stats if s.rating is not None and math.isfinite(s.rating)]

        avg_x = sum(xs) / len(xs) if xs else _default_x_for_pos(pos)
        avg_y = sum(ys) / len(ys) if ys else _default_y_for_pos(pos)
        corridor = corridor_from_x(avg_x) if xs else position_default_corridor(pos)
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

        starter = ProbableStarter(
            player_id=pid,
            team_id=team_id,
            name=name,
            position=pos,
            archetype_primary=arch,
            avg_x=round(avg_x, 2),
            avg_y=round(avg_y, 2),
            corridor=corridor,
            recent_minutes=mins,
            recent_rating=avg_rating,
        )
        # Rank by recent minutes, prioritizing 1 GK + 10 outfielders
        candidates.append((float(mins), starter))

    gks = sorted((c for c in candidates if c[1].position == "GK"), key=lambda x: x[0], reverse=True)
    outfield = sorted(
        (c for c in candidates if c[1].position != "GK"), key=lambda x: x[0], reverse=True
    )

    selected: list[ProbableStarter] = []
    if gks:
        selected.append(gks[0][1])
    selected.extend(s for _, s in outfield[: 11 - len(selected)])
    return selected


def _default_x_for_pos(pos: PlayerPosition) -> float:
    return {
        "GK": 50.0,
        "CB": 50.0,
        "LB": 15.0,
        "LWB": 14.0,
        "LW": 18.0,
        "RB": 85.0,
        "RWB": 86.0,
        "RW": 82.0,
        "DM": 50.0,
        "CM": 50.0,
        "AM": 50.0,
        "ST": 50.0,
    }.get(pos, 50.0)


def _default_y_for_pos(pos: PlayerPosition) -> float:
    return {
        "GK": 6.0,
        "CB": 34.0,
        "LB": 42.0,
        "RB": 42.0,
        "LWB": 55.0,
        "RWB": 55.0,
        "DM": 48.0,
        "CM": 56.0,
        "AM": 68.0,
        "LW": 72.0,
        "RW": 72.0,
        "ST": 78.0,
    }.get(pos, 50.0)


def _team_baseline_profile(
    team_id: int,
    tactics: Sequence[TeamMatchTacticsUpsert],
) -> tuple[str | None, str | None, int | None]:
    rows = [t for t in tactics if t.team_id == team_id]
    forms = [t.formation for t in rows if t.formation]
    prob_form = Counter(forms).most_common(1)[0][0] if forms else None

    line_ys = [
        t.avg_def_line_y
        for t in rows
        if t.avg_def_line_y is not None and math.isfinite(t.avg_def_line_y)
    ]
    avg_line = line_height(sum(line_ys) / len(line_ys)) if line_ys else None

    backs = [t.back_line_count for t in rows if t.back_line_count is not None]
    prob_back = Counter(backs).most_common(1)[0][0] if backs else None
    return prob_form, avg_line, prob_back


def score_upcoming_matchup(
    *,
    match_id: int,
    home_team_id: int,
    away_team_id: int,
    home_starters: Sequence[ProbableStarter],
    away_starters: Sequence[ProbableStarter],
    tactics_history: Sequence[TeamMatchTacticsUpsert],
    team_splits: Sequence[TeamSplitResult],
    player_splits: Sequence[PlayerSplitResult],
) -> MatchupAnalysis:
    """Cross probable starter zones, compute 0-100 Mismatch Scores, top 3 X-Factors,
    and per-starter observation candidates.
    """
    home_form, home_line, home_back = _team_baseline_profile(home_team_id, tactics_history)
    away_form, away_line, away_back = _team_baseline_profile(away_team_id, tactics_history)

    t_split_idx: dict[tuple[int, str, str], TeamSplitResult] = {
        (s.row.team_id, s.row.condition_type, s.row.condition_value): s for s in team_splits
    }
    p_split_idx: dict[tuple[int, str, str], PlayerSplitResult] = {
        (s.row.player_id, s.row.condition_type, s.row.condition_value): s for s in player_splits
    }

    duels: list[KeyDuel] = []
    starter_best_duel: dict[int, tuple[float, KeyDuel]] = {}

    def _pair_side(
        att_starters: Sequence[ProbableStarter],
        def_starters: Sequence[ProbableStarter],
        opp_form: str | None,
        opp_line: str | None,
    ) -> None:
        attackers = [s for s in att_starters if s.position in ATTACKING_POSITIONS]
        defenders = [s for s in def_starters if s.position in DEFENSIVE_POSITIONS]

        for att in attackers:
            lanes = facing_corridors(att.corridor)
            opp_def = next((d for d in defenders if d.corridor == lanes[0]), None)
            if opp_def is None:
                opp_def = next((d for d in defenders if d.corridor in lanes[1:]), None)
            if opp_def is None:
                continue

            score = 50.0
            best_metric_key = "rating_delta"
            best_metric_val: float | None = None
            best_sample = SampleSize(unit="minutes", value=att.recent_minutes)
            best_conf: ConfidenceLevel = "low"
            best_evidence: EvidenceRef | None = None
            reasons: list[str] = []

            # 1. Attacker vs defender archetype split
            if opp_def.archetype_primary is not None:
                sp = p_split_idx.get(
                    (att.player_id, "vs_defender_archetype", opp_def.archetype_primary)
                )
                if sp is not None:
                    w = CONFIDENCE_WEIGHT[sp.confidence]
                    if sp.row.rating_delta is not None:
                        score += sp.row.rating_delta * 26.0 * w
                        best_metric_key = "rating_delta"
                        best_metric_val = sp.row.rating_delta
                        best_sample = SampleSize(unit="minutes", value=sp.row.sample_minutes)
                        best_conf = sp.confidence
                        best_evidence = EvidencePlayerSplit(
                            table="player_conditional_splits",
                            player_id=att.player_id,
                            condition_type="vs_defender_archetype",
                            condition_value=opp_def.archetype_primary,
                        )
                        reasons.append(
                            f"{att.name} {sp.row.rating_delta:+.2f} rating vs {ARCHETYPE_LABELS_IT[opp_def.archetype_primary]} ({sp.row.sample_minutes}')"
                        )
                    if sp.row.dribbles_delta is not None:
                        score += sp.row.dribbles_delta * 6.0 * w
                    if sp.row.duels_delta is not None:
                        score += sp.row.duels_delta * 4.5 * w

            # 2. Attacker vs opponent defensive line height
            if opp_line is not None:
                sp_line = p_split_idx.get((att.player_id, "vs_line_height", opp_line))
                if sp_line is not None and sp_line.row.rating_delta is not None:
                    w = CONFIDENCE_WEIGHT[sp_line.confidence]
                    score += sp_line.row.rating_delta * 14.0 * w
                    reasons.append(f"vs linea {opp_line}: {sp_line.row.rating_delta:+.2f} rating")

            # 3. Defender vulnerability vs attacker archetype
            if att.archetype_primary is not None:
                sp_def = p_split_idx.get(
                    (opp_def.player_id, "vs_attacker_archetype", att.archetype_primary)
                )
                if sp_def is not None:
                    w = CONFIDENCE_WEIGHT[sp_def.confidence]
                    if sp_def.row.rating_delta is not None:
                        # Negative defender rating delta increases attacker's mismatch score
                        score -= sp_def.row.rating_delta * 22.0 * w
                        if best_metric_val is None or abs(sp_def.row.rating_delta) > abs(
                            best_metric_val
                        ):
                            best_metric_key = "rating_delta"
                            best_metric_val = sp_def.row.rating_delta
                            best_sample = SampleSize(
                                unit="minutes", value=sp_def.row.sample_minutes
                            )
                            best_conf = sp_def.confidence
                            best_evidence = EvidencePlayerSplit(
                                table="player_conditional_splits",
                                player_id=opp_def.player_id,
                                condition_type="vs_attacker_archetype",
                                condition_value=att.archetype_primary,
                            )
                        reasons.append(
                            f"{opp_def.name} {sp_def.row.rating_delta:+.2f} rating vs {ARCHETYPE_LABELS_IT[att.archetype_primary]}"
                        )
                    if sp_def.row.dribbles_delta is not None:
                        # Positive dribbles_past delta for defender favours attacker
                        score += sp_def.row.dribbles_delta * 6.5 * w

                # 4. Defending team vulnerability vs attacker archetype
                ts = t_split_idx.get((opp_def.team_id, "vs_archetype", att.archetype_primary))
                if ts is not None and ts.row.xga_delta is not None:
                    w = CONFIDENCE_WEIGHT[ts.confidence]
                    score += ts.row.xga_delta * 24.0 * w
                    if best_evidence is None:
                        best_metric_key = "xga_delta"
                        best_metric_val = ts.row.xga_delta
                        best_sample = SampleSize(unit="matches", value=ts.row.sample_matches)
                        best_conf = ts.confidence
                        best_evidence = EvidenceTeamSplit(
                            table="team_conditional_splits",
                            team_id=opp_def.team_id,
                            condition_type="vs_archetype",
                            condition_value=att.archetype_primary,
                        )
                    reasons.append(
                        f"squadra difendente {ts.row.xga_delta:+.2f} xGA vs {ARCHETYPE_LABELS_IT[att.archetype_primary]} ({ts.row.sample_matches}P)"
                    )

            # 5. Attacker vs opponent formation
            if opp_form is not None:
                sp_f = p_split_idx.get((att.player_id, "vs_formation", opp_form))
                if sp_f is not None and sp_f.row.rating_delta is not None:
                    score += sp_f.row.rating_delta * 10.0 * CONFIDENCE_WEIGHT[sp_f.confidence]

            bounded = _clamp_score(score)
            favours_attacker = bounded >= 50.0
            protag_id = att.player_id if favours_attacker else opp_def.player_id
            protag_team = att.team_id if favours_attacker else opp_def.team_id
            against_team = opp_def.team_id if favours_attacker else att.team_id

            duel = KeyDuel(
                duel_key=f"duel_{att.player_id}_vs_{opp_def.player_id}",
                attacker_id=att.player_id,
                attacker_team_id=att.team_id,
                attacker_name=att.name,
                attacker_archetype=att.archetype_primary,
                defender_id=opp_def.player_id,
                defender_team_id=opp_def.team_id,
                defender_name=opp_def.name,
                defender_archetype=opp_def.archetype_primary,
                zone=att.corridor,
                mismatch_score=bounded,
                protagonist_id=protag_id,
                protagonist_team_id=protag_team,
                against_team_id=against_team,
                metric_key=best_metric_key,
                metric_value=best_metric_val,
                sample=best_sample,
                confidence=best_conf,
                evidence=best_evidence,
                summary_fact="; ".join(reasons)
                if reasons
                else f"Duello di zona {att.name} vs {opp_def.name} ({att.corridor})",
            )
            duels.append(duel)

            # Track strongest duel per player for starter observations
            strength = abs(bounded - 50.0)
            for pid in (att.player_id, opp_def.player_id):
                prev = starter_best_duel.get(pid)
                if prev is None or strength > prev[0]:
                    starter_best_duel[pid] = (strength, duel)

    _pair_side(home_starters, away_starters, away_form, away_line)
    _pair_side(away_starters, home_starters, home_form, home_line)

    # Sort duels by distance from neutral 50 (strongest mismatches first)
    duels.sort(
        key=lambda d: (abs(d.mismatch_score - 50.0), CONFIDENCE_WEIGHT[d.confidence]), reverse=True
    )

    # Build EdgeCandidates from both team splits & top duels
    edge_candidates: list[EdgeCandidate] = []
    for d in duels[:6]:
        edge_strength = abs(d.mismatch_score - 50.0) * CONFIDENCE_WEIGHT[d.confidence]
        edge_candidates.append(
            EdgeCandidate(
                edge_key=d.duel_key,
                team_id=d.protagonist_team_id,
                against_team_id=d.against_team_id,
                metric_key=d.metric_key,
                metric_value=d.metric_value,
                zone=d.zone,
                player_ids=[d.attacker_id, d.defender_id],
                sample=d.sample,
                confidence=d.confidence,
                evidence=d.evidence,
                score=round(edge_strength, 2),
                fact=d.summary_fact,
            )
        )

    # Add team-level structural splits (vs_formation, vs_back_line, vs_high_line)
    for def_tid, att_tid, att_form, att_back, att_line in (
        (home_team_id, away_team_id, away_form, away_back, away_line),
        (away_team_id, home_team_id, home_form, home_back, home_line),
    ):
        checks: list[tuple[str, str | None]] = [
            ("vs_formation", att_form),
            ("vs_back_line", str(att_back) if att_back is not None else None),
            ("vs_high_line", att_line),
        ]
        for ctype, cval in checks:
            if not cval:
                continue
            ts = t_split_idx.get((def_tid, ctype, cval))
            if ts is None:
                continue
            if ts.row.xga_delta is not None and ts.row.xga_delta > 0.12:
                edge_candidates.append(
                    EdgeCandidate(
                        edge_key=f"team_{def_tid}_{ctype}_{cval}",
                        team_id=att_tid,
                        against_team_id=def_tid,
                        metric_key="xga_delta",
                        metric_value=ts.row.xga_delta,
                        zone=None,
                        player_ids=[],
                        sample=SampleSize(unit="matches", value=ts.row.sample_matches),
                        confidence=ts.confidence,
                        evidence=EvidenceTeamSplit(
                            table="team_conditional_splits",
                            team_id=def_tid,
                            condition_type=ctype,  # type: ignore[arg-type]
                            condition_value=cval,
                        ),
                        score=round(ts.row.xga_delta * 55.0 * CONFIDENCE_WEIGHT[ts.confidence], 2),
                        fact=f"Squadra {def_tid} concede {ts.row.xga_delta:+.2f} xGA in condizione {ctype}={cval} ({ts.row.sample_matches}P)",
                    )
                )

    edge_candidates.sort(key=lambda e: e.score, reverse=True)

    # Select top 3 unique X-Factors
    x_factors: list[XFactorCandidate] = []
    seen_xf_players: set[int] = set()
    starter_map: dict[int, ProbableStarter] = {
        s.player_id: s for s in (*home_starters, *away_starters)
    }

    for d in duels:
        if len(x_factors) >= 3:
            break
        pid = d.protagonist_id
        if pid in seen_xf_players:
            continue
        st = starter_map.get(pid)
        if st is None:
            continue
        seen_xf_players.add(pid)
        x_factors.append(
            XFactorCandidate(
                candidate_key=f"xf_{pid}",
                player_id=pid,
                team_id=st.team_id,
                player_name=st.name,
                archetype=st.archetype_primary,
                metric_key=d.metric_key,
                metric_value=d.metric_value,
                confidence=d.confidence,
                mismatch_score=d.mismatch_score,
                fact=d.summary_fact,
            )
        )

    # Pad to 3 X-Factors if fewer than 3 duels existed (e.g. early season)
    if len(x_factors) < 3:
        remaining = sorted(
            (
                s
                for s in (*home_starters, *away_starters)
                if s.player_id not in seen_xf_players and s.position != "GK"
            ),
            key=lambda s: (s.recent_rating or 0.0, s.recent_minutes),
            reverse=True,
        )
        for st in remaining:
            if len(x_factors) >= 3:
                break
            seen_xf_players.add(st.player_id)
            x_factors.append(
                XFactorCandidate(
                    candidate_key=f"xf_{st.player_id}",
                    player_id=st.player_id,
                    team_id=st.team_id,
                    player_name=st.name,
                    archetype=st.archetype_primary,
                    metric_key="rating",
                    metric_value=st.recent_rating,
                    confidence="low",
                    mismatch_score=50.0,
                    fact=f"Forma recente {st.name}: rating medio {st.recent_rating or 'n/d'} su {st.recent_minutes}'",
                )
            )

    # Build StarterObservationCandidate for EVERY probable starter (up to 22)
    starter_obs: list[StarterObservationCandidate] = []
    for st in (*home_starters, *away_starters):
        best_pair = starter_best_duel.get(st.player_id)
        matchup_id: int | None = None
        matchup_name: str | None = None
        matchup_arch: PlayerArchetype | None = None
        metric_key: str | None = None
        metric_val: float | None = None
        sentiment = "neutral"
        arch_label = (
            ARCHETYPE_LABELS_IT[st.archetype_primary] if st.archetype_primary else st.position
        )

        if best_pair is not None:
            _, duel = best_pair
            is_att = duel.attacker_id == st.player_id
            matchup_id = duel.defender_id if is_att else duel.attacker_id
            matchup_name = duel.defender_name if is_att else duel.attacker_name
            matchup_arch = duel.defender_archetype if is_att else duel.attacker_archetype
            metric_key = duel.metric_key
            metric_val = duel.metric_value
            if duel.protagonist_id == st.player_id and abs(duel.mismatch_score - 50.0) >= 6.0:
                sentiment = "positive"
            elif duel.protagonist_id != st.player_id and abs(duel.mismatch_score - 50.0) >= 6.0:
                sentiment = "negative"
            fact = f"{st.name} ({arch_label}) vs {matchup_name}: {duel.summary_fact}"
        else:
            # Check team-level formation/line split for this player
            opp_form = away_form if st.team_id == home_team_id else home_form
            sp_f = p_split_idx.get((st.player_id, "vs_formation", opp_form)) if opp_form else None
            if sp_f is not None and sp_f.row.rating_delta is not None:
                metric_key = "rating_delta"
                metric_val = sp_f.row.rating_delta
                sentiment = (
                    "positive"
                    if sp_f.row.rating_delta >= 0.15
                    else "negative"
                    if sp_f.row.rating_delta <= -0.15
                    else "neutral"
                )
                fact = f"{st.name} ({arch_label}) vs {opp_form}: {sp_f.row.rating_delta:+.2f} rating ({sp_f.row.sample_minutes}')"
            else:
                metric_key = "rating" if st.recent_rating is not None else None
                metric_val = st.recent_rating
                fact = f"{st.name} ({arch_label}), corridoio {st.corridor}, {st.recent_minutes}' recenti."

        starter_obs.append(
            StarterObservationCandidate(
                candidate_key=f"obs_{st.player_id}",
                player_id=st.player_id,
                team_id=st.team_id,
                player_name=st.name,
                position=st.position,
                archetype=st.archetype_primary,
                matchup_player_id=matchup_id,
                matchup_player_name=matchup_name,
                matchup_archetype=matchup_arch,
                metric_key=metric_key,
                metric_value=metric_val,
                sentiment_hint=sentiment,
                fact=fact,
            )
        )

    return MatchupAnalysis(
        match_id=match_id,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        home_probable_formation=home_form,
        away_probable_formation=away_form,
        home_line_height=home_line,
        away_line_height=away_line,
        home_starters=list(home_starters),
        away_starters=list(away_starters),
        key_duels=duels,
        edge_candidates=edge_candidates,
        x_factors=x_factors,
        starter_observations=starter_obs,
    )


def duels_to_matchup_rows(
    duels: Sequence[KeyDuel],
    *,
    home_team_id: int,
    limit: int = 8,
) -> list[MatchupDuelRow]:
    """Serialize `KeyDuel` objects into DB `match_ai_briefs.matchups_json` rows.

    Always places the home-team player on side `a` and the away-team player on side `b`,
    deduplicating reversed pairs and computing `advantage` ("a" | "b" | None).
    """
    rows: list[MatchupDuelRow] = []
    seen_pairs: set[tuple[int, int]] = set()

    for d in duels:
        if d.attacker_team_id == home_team_id:
            pa, ta = d.attacker_id, d.attacker_team_id
            pb, tb = d.defender_id, d.defender_team_id
            raw_tilt = d.mismatch_score - 50.0  # > 0 favours side a (home)
        else:
            pa, ta = d.defender_id, d.defender_team_id
            pb, tb = d.attacker_id, d.attacker_team_id
            raw_tilt = 50.0 - d.mismatch_score  # > 0 favours side a (home)

        pair_key = (pa, pb)
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        has_evidence = d.evidence is not None
        if not has_evidence or abs(raw_tilt) < 2.0:
            score_val: float | None = round(50.0 + abs(raw_tilt), 1) if has_evidence else None
            advantage = None
        else:
            score_val = round(min(100.0, 50.0 + abs(raw_tilt)), 1)
            advantage = "a" if raw_tilt > 0 else "b"

        rows.append(
            MatchupDuelRow(
                id=f"{pa}-{pb}",
                player_a_id=pa,
                team_a_id=ta,
                player_b_id=pb,
                team_b_id=tb,
                zone=d.zone,
                mismatch_score=score_val,
                advantage=advantage,
                sample=d.sample,
                confidence=d.confidence,
                evidence=[d.evidence] if d.evidence is not None else [],
            )
        )
        if len(rows) >= limit:
            break

    return rows


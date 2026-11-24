"""Chameleon Detector (ZERO AI).

Compares every match for a team against its prior rolling season baseline:
  - Flags `is_tactical_shift = True` if:
      1) base formation changed vs rolling mode `baseline_formation`, OR
      2) `ppda` deviates by > 1.5 standard deviations from prior rolling mean, OR
      3) `avg_def_line_y` deviates by > 1.5 standard deviations from prior rolling mean.
  - Always writes a factual Italian `shift_reason` when `is_tactical_shift = True`.
  - Computes team efficiency (xG - xGA differential) against Top 6, Mid-table,
    and Zona Salvezza opponents (overall, during shifts, and on baseline).
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from db.models import ConfidenceLevel, TeamMatchTacticsUpsert
from engine.confidence import from_matches

OpponentTier = Literal["top_6", "mid_table", "relegation"]

Z_SHIFT_THRESHOLD = 1.5
MIN_PRIOR_FOR_Z = 2


@dataclass(frozen=True)
class TeamMatchRecord:
    match_id: int
    round: int
    team_id: int
    opponent_id: int
    xg: float | None
    xga: float | None
    goals_for: int | None
    goals_against: int | None
    tactics: TeamMatchTacticsUpsert


@dataclass(frozen=True)
class TierEfficiency:
    tier: OpponentTier
    sample_matches: int
    shift_matches: int
    xg_diff_overall: float | None
    xg_diff_on_shift: float | None
    xg_diff_on_baseline: float | None
    confidence: ConfidenceLevel


@dataclass(frozen=True)
class ChameleonReport:
    team_id: int
    updated_tactics: list[TeamMatchTacticsUpsert]
    shift_rate: float | None
    tier_efficiency: dict[OpponentTier, TierEfficiency]


def _mean_std(values: Sequence[float]) -> tuple[float | None, float | None]:
    clean = [float(v) for v in values if v is not None and math.isfinite(v)]
    n = len(clean)
    if n == 0:
        return None, None
    mean = sum(clean) / n
    if n < 2:
        return mean, None
    var = sum((v - mean) ** 2 for v in clean) / (n - 1)
    std = math.sqrt(var)
    return mean, std


def compute_league_tiers(
    matches: Sequence[tuple[int, int, int | None, int | None, float | None, float | None]],
) -> dict[int, OpponentTier]:
    """Rank teams by points (then GD, then xGD) and assign Top 6 / Mid-table / Zona Salvezza.

    Input items: `(home_team_id, away_team_id, home_goals, away_goals, home_xg, away_xg)`.
    """
    pts: dict[int, int] = {}
    gd: dict[int, int] = {}
    xgd: dict[int, float] = {}

    for hid, aid, hg, ag, hxg, axg in matches:
        for tid in (hid, aid):
            pts.setdefault(tid, 0)
            gd.setdefault(tid, 0)
            xgd.setdefault(tid, 0.0)
        if hg is not None and ag is not None:
            gd[hid] += hg - ag
            gd[aid] += ag - hg
            if hg > ag:
                pts[hid] += 3
            elif ag > hg:
                pts[aid] += 3
            else:
                pts[hid] += 1
                pts[aid] += 1
        if hxg is not None and axg is not None:
            xgd[hid] += hxg - axg
            xgd[aid] += axg - hxg

    ordered = sorted(
        pts.keys(),
        key=lambda tid: (pts[tid], gd[tid], xgd[tid]),
        reverse=True,
    )
    n = len(ordered)
    if n == 0:
        return {}

    # Scale cutoffs gracefully when testing on smaller synthetic leagues
    top_cut = min(6, max(1, round(n * 0.30)))
    rel_start = max(top_cut + 1, n - min(6, max(1, round(n * 0.30)))) if n >= 3 else n

    tiers: dict[int, OpponentTier] = {}
    for rank_idx, tid in enumerate(ordered):
        if rank_idx < top_cut:
            tiers[tid] = "top_6"
        elif rank_idx < rel_start:
            tiers[tid] = "mid_table"
        else:
            tiers[tid] = "relegation"
    return tiers


def detect_chameleon_shifts(
    team_id: int,
    records: Sequence[TeamMatchRecord],
    opponent_tiers: dict[int, OpponentTier],
) -> ChameleonReport:
    """Detect tactical shifts over a team's chronological match sequence and compute tier efficiency."""
    ordered = sorted(records, key=lambda r: (r.round, r.match_id))

    prior_formations: list[str] = []
    prior_ppda: list[float] = []
    prior_line_y: list[float] = []

    updated: list[TeamMatchTacticsUpsert] = []
    tier_buckets: dict[OpponentTier, dict[str, list[float]]] = {
        "top_6": {"all": [], "shift": [], "base": []},
        "mid_table": {"all": [], "shift": [], "base": []},
        "relegation": {"all": [], "shift": [], "base": []},
    }
    shift_count = 0

    for rec in ordered:
        tac = rec.tactics
        baseline_form: str | None = (
            Counter(prior_formations).most_common(1)[0][0] if prior_formations else tac.formation
        )

        reasons: list[str] = []

        # 1. Formation change vs rolling baseline
        if (
            prior_formations
            and tac.formation is not None
            and baseline_form is not None
            and tac.formation != baseline_form
        ):
            reasons.append(f"Cambio modulo ({baseline_form} → {tac.formation})")

        # 2. PPDA deviation > 1.5 sigma
        if tac.ppda is not None and len(prior_ppda) >= MIN_PRIOR_FOR_Z:
            mean_p, std_p = _mean_std(prior_ppda)
            if mean_p is not None and std_p is not None and std_p > 1e-6:
                z_ppda = (tac.ppda - mean_p) / std_p
                if abs(z_ppda) > Z_SHIFT_THRESHOLD:
                    direction = "pressing più passivo" if z_ppda > 0 else "pressing più aggressivo"
                    reasons.append(
                        f"PPDA {z_ppda:+.1f}SD ({tac.ppda:.1f} vs media {mean_p:.1f}, {direction})"
                    )

        # 3. Defensive line height deviation > 1.5 sigma
        if tac.avg_def_line_y is not None and len(prior_line_y) >= MIN_PRIOR_FOR_Z:
            mean_y, std_y = _mean_std(prior_line_y)
            if mean_y is not None and std_y is not None and std_y > 1e-6:
                z_line = (tac.avg_def_line_y - mean_y) / std_y
                if abs(z_line) > Z_SHIFT_THRESHOLD:
                    direction = "linea più alta" if z_line > 0 else "baricentro più basso"
                    reasons.append(
                        f"Linea difensiva {z_line:+.1f}SD ({tac.avg_def_line_y:.1f} vs media {mean_y:.1f}, {direction})"
                    )

        is_shift = bool(reasons)
        shift_reason = "; ".join(reasons) if is_shift else None
        if is_shift:
            shift_count += 1

        new_tac = tac.model_copy(
            update={
                "baseline_formation": baseline_form,
                "is_tactical_shift": is_shift,
                "shift_reason": shift_reason,
            }
        )
        updated.append(new_tac)

        # Track tier xG - xGA efficiency
        tier = opponent_tiers.get(rec.opponent_id, "mid_table")
        if (
            rec.xg is not None
            and rec.xga is not None
            and math.isfinite(rec.xg)
            and math.isfinite(rec.xga)
        ):
            diff = rec.xg - rec.xga
            tier_buckets[tier]["all"].append(diff)
            if is_shift:
                tier_buckets[tier]["shift"].append(diff)
            else:
                tier_buckets[tier]["base"].append(diff)

        # Update rolling history AFTER evaluating the current match (zero lookahead leakage)
        if tac.formation is not None:
            prior_formations.append(tac.formation)
        if tac.ppda is not None and math.isfinite(tac.ppda):
            prior_ppda.append(tac.ppda)
        if tac.avg_def_line_y is not None and math.isfinite(tac.avg_def_line_y):
            prior_line_y.append(tac.avg_def_line_y)

    tier_efficiency: dict[OpponentTier, TierEfficiency] = {}
    for tier, buckets in tier_buckets.items():
        all_vals = buckets["all"]
        shift_vals = buckets["shift"]
        base_vals = buckets["base"]
        tier_efficiency[tier] = TierEfficiency(
            tier=tier,
            sample_matches=len(all_vals),
            shift_matches=len(shift_vals),
            xg_diff_overall=round(sum(all_vals) / len(all_vals), 2) if all_vals else None,
            xg_diff_on_shift=round(sum(shift_vals) / len(shift_vals), 2) if shift_vals else None,
            xg_diff_on_baseline=round(sum(base_vals) / len(base_vals), 2) if base_vals else None,
            confidence=from_matches(len(all_vals)),
        )

    shift_rate = round(shift_count / len(ordered), 3) if ordered else None
    return ChameleonReport(
        team_id=team_id,
        updated_tactics=updated,
        shift_rate=shift_rate,
        tier_efficiency=tier_efficiency,
    )

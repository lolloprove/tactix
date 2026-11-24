"""Deterministic player archetype classifier & role-percentile radar builder (ZERO AI).

Classifies every player with `minutes_total >= 180` into primary & optional
secondary `PlayerArchetype` (1:1 with the 20 Postgres `player_archetype` enum
values) using within-position-group per-90 percentiles and cosine similarity to
tactical archetype centroids, and produces the 6-axis `radar_percentiles_json`
(0-100 league percentiles within role group) for `PlayerConditionalPanel`.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from db.models import PlayerArchetype, PlayerPosition, RadarAxis

MIN_MINUTES_FOR_ARCHETYPE = 180
SECONDARY_THRESHOLD = 0.55

# Human-readable Italian labels for deterministic text & AI prompt grounding
ARCHETYPE_LABELS_IT: dict[PlayerArchetype, str] = {
    "portiere_classico": "Portiere Classico",
    "portiere_libero": "Portiere Libero",
    "braccetto": "Braccetto",
    "centrale_marcatore": "Centrale Aggressivo / Marcatore",
    "centrale_impostazione": "Centrale di Posizione / Impostazione",
    "terzino_difensivo": "Terzino Bloccato",
    "terzino_spinta": "Terzino Offensivo",
    "terzino_invertito": "Terzino Invertito",
    "quinto": "Quinto a Tutta Fascia",
    "regista": "Regista",
    "mediano_incontrista": "Mediano Incontrista",
    "mezzala": "Mezzala d'Inserimento",
    "box_to_box": "Centrocampista Box-to-Box",
    "trequartista": "Trequartista",
    "ala_dribblatrice": "Ala da 1v1 Puro",
    "ala_inversa": "Esterno Associativo / Ala Inversa",
    "prima_punta": "Punta d'Area",
    "falso_nove": "Attaccante di Manovra / Falso Nove",
    "attaccante_profondita": "Attaccante di Profondità",
    "seconda_punta": "Seconda Punta",
}

RoleGroup = str

POSITION_TO_GROUP: dict[PlayerPosition, RoleGroup] = {
    "GK": "GK",
    "CB": "CB",
    "LB": "FB_WB",
    "RB": "FB_WB",
    "LWB": "FB_WB",
    "RWB": "FB_WB",
    "DM": "MID",
    "CM": "MID",
    "AM": "MID",
    "LW": "WING",
    "RW": "WING",
    "ST": "FWD",
}

# Feature vector order (8 dimensions in [0, 1] percentile space):
# 0: dribbles_won_p90
# 1: duels_won_p90
# 2: duel_win_rate
# 3: progressive_actions_p90
# 4: xg_p90
# 5: xa_p90
# 6: depth_y       (higher = further up the pitch)
# 7: centrality_x  (higher = closer to x=50 center; lower = wide touchline)
FEATURE_NAMES = (
    "dribbles_won_p90",
    "duels_won_p90",
    "duel_win_rate",
    "progressive_actions_p90",
    "xg_p90",
    "xa_p90",
    "depth_y",
    "centrality_x",
)

# 6-axis radar specification per role group (DESIGN.md §6: max 6 axes).
# Tuple: (axis_key, italian_label, feature_index_or_special)
# Special indices: -1 = 1v1 defensive solidity (inverse of dribbles_past_p90).
RADAR_SPECS: dict[RoleGroup, tuple[tuple[str, str, int], ...]] = {
    "GK": (
        ("progression", "Impostazione", 3),
        ("depth", "Uscite / Baricentro", 6),
        ("duel_rate", "% Duelli", 2),
        ("duels", "Duelli vinti", 1),
        ("def_1v1", "Solidità 1v1", -1),
        ("creativity", "Lanci chiave", 5),
    ),
    "CB": (
        ("duels", "Duelli vinti", 1),
        ("duel_rate", "% Duelli", 2),
        ("def_1v1", "Solidità 1v1", -1),
        ("progression", "Progressione", 3),
        ("depth", "Altezza linea", 6),
        ("dribbles", "Conduzioni", 0),
    ),
    "FB_WB": (
        ("def_1v1", "Solidità 1v1", -1),
        ("duels", "Duelli vinti", 1),
        ("progression", "Progressione", 3),
        ("xa", "Rifinitura (xA)", 5),
        ("dribbles", "Dribbling", 0),
        ("depth", "Spinta", 6),
    ),
    "MID": (
        ("progression", "Progressione", 3),
        ("xa", "Rifinitura (xA)", 5),
        ("xg", "Inserimenti (xG)", 4),
        ("dribbles", "Dribbling", 0),
        ("duels", "Duelli vinti", 1),
        ("def_1v1", "Tenuta 1v1", -1),
    ),
    "WING": (
        ("dribbles", "Dribbling 1v1", 0),
        ("xg", "Pericolosità (xG)", 4),
        ("xa", "Rifinitura (xA)", 5),
        ("progression", "Progressione", 3),
        ("duels", "Duelli vinti", 1),
        ("depth", "Profondità", 6),
    ),
    "FWD": (
        ("xg", "Volume xG", 4),
        ("xa", "Rifinitura (xA)", 5),
        ("dribbles", "Dribbling 1v1", 0),
        ("duels", "Duelli vinti", 1),
        ("duel_rate", "% Duelli", 2),
        ("progression", "Manovra", 3),
    ),
}

# Centroids per position group (values in [0, 1] representing ideal percentile profile)
GROUP_CENTROIDS: dict[RoleGroup, dict[PlayerArchetype, tuple[float, ...]]] = {
    "GK": {
        "portiere_classico": (0.20, 0.50, 0.65, 0.25, 0.10, 0.10, 0.20, 0.55),
        "portiere_libero": (0.55, 0.55, 0.60, 0.90, 0.10, 0.25, 0.85, 0.60),
    },
    "CB": {
        "braccetto": (0.70, 0.65, 0.60, 0.80, 0.45, 0.65, 0.78, 0.20),
        "centrale_marcatore": (0.25, 0.90, 0.88, 0.35, 0.45, 0.20, 0.45, 0.72),
        "centrale_impostazione": (0.50, 0.45, 0.62, 0.92, 0.30, 0.55, 0.55, 0.82),
    },
    "FB_WB": {
        "terzino_difensivo": (0.25, 0.82, 0.85, 0.38, 0.20, 0.28, 0.22, 0.40),
        "terzino_spinta": (0.75, 0.55, 0.52, 0.82, 0.60, 0.86, 0.76, 0.22),
        "terzino_invertito": (0.62, 0.55, 0.58, 0.88, 0.45, 0.70, 0.62, 0.88),
        "quinto": (0.78, 0.62, 0.55, 0.80, 0.78, 0.82, 0.92, 0.18),
    },
    "MID": {
        "regista": (0.42, 0.42, 0.58, 0.94, 0.22, 0.76, 0.28, 0.88),
        "mediano_incontrista": (0.30, 0.92, 0.88, 0.38, 0.22, 0.24, 0.25, 0.78),
        "mezzala": (0.66, 0.58, 0.55, 0.76, 0.78, 0.72, 0.75, 0.45),
        "box_to_box": (0.62, 0.85, 0.76, 0.74, 0.66, 0.55, 0.64, 0.58),
        "trequartista": (0.80, 0.35, 0.45, 0.84, 0.82, 0.92, 0.90, 0.72),
    },
    "WING": {
        "ala_dribblatrice": (0.94, 0.58, 0.55, 0.78, 0.62, 0.76, 0.76, 0.22),
        "ala_inversa": (0.62, 0.45, 0.52, 0.76, 0.86, 0.80, 0.82, 0.78),
    },
    "FWD": {
        "prima_punta": (0.28, 0.88, 0.84, 0.30, 0.92, 0.30, 0.88, 0.82),
        "falso_nove": (0.68, 0.42, 0.52, 0.92, 0.52, 0.90, 0.32, 0.74),
        "attaccante_profondita": (0.76, 0.55, 0.54, 0.60, 0.84, 0.52, 0.86, 0.42),
        "seconda_punta": (0.82, 0.52, 0.55, 0.78, 0.72, 0.84, 0.55, 0.60),
    },
}


@dataclass(frozen=True)
class PlayerSeasonAggregate:
    player_id: int
    primary_position: PlayerPosition
    minutes_total: int
    dribbles_won: int
    dribbles_past: int
    duels_won: int
    duels_lost: int
    progressive_actions: int
    xg: float
    xa: float
    avg_x: float | None
    avg_y: float | None
    back_three_minutes: int = 0


@dataclass(frozen=True)
class ArchetypeClassification:
    player_id: int
    archetype_primary: PlayerArchetype | None
    archetype_secondary: PlayerArchetype | None
    archetype_scores_json: dict[PlayerArchetype, float]
    radar_percentiles_json: list[RadarAxis] | None = None


def _per90(value: float, minutes: int) -> float:
    if minutes <= 0 or not math.isfinite(value):
        return 0.0
    return (value / minutes) * 90.0


def _raw_features(p: PlayerSeasonAggregate) -> tuple[float, ...]:
    duels_total = p.duels_won + p.duels_lost
    duel_rate = (p.duels_won / duels_total) if duels_total > 0 else 0.5
    depth_y = float(p.avg_y) if (p.avg_y is not None and math.isfinite(p.avg_y)) else 50.0
    centrality_x = (
        100.0 - 2.0 * abs(float(p.avg_x) - 50.0)
        if (p.avg_x is not None and math.isfinite(p.avg_x))
        else 50.0
    )
    return (
        _per90(float(p.dribbles_won), p.minutes_total),
        _per90(float(p.duels_won), p.minutes_total),
        duel_rate,
        _per90(float(p.progressive_actions), p.minutes_total),
        _per90(float(p.xg), p.minutes_total),
        _per90(float(p.xa), p.minutes_total),
        depth_y,
        centrality_x,
    )


def _empirical_percentiles(values: Sequence[float]) -> list[float]:
    """Compute mid-rank empirical percentiles in [0.05, 0.95] without NaNs."""
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [0.5]
    sorted_vals = sorted(values)
    out: list[float] = []
    for v in values:
        below = sum(1 for s in sorted_vals if s < v)
        equal = sum(1 for s in sorted_vals if s == v)
        rank = (below + 0.5 * equal) / n
        out.append(max(0.05, min(0.95, rank)))
    return out


def _cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=True))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a <= 1e-12 or norm_b <= 1e-12:
        return 0.0
    sim = dot / (norm_a * norm_b)
    if not math.isfinite(sim):
        return 0.0
    return max(0.0, min(1.0, sim))


def classify_players(
    aggregates: Sequence[PlayerSeasonAggregate],
    *,
    min_minutes: int = MIN_MINUTES_FOR_ARCHETYPE,
) -> dict[int, ArchetypeClassification]:
    """Classify all players and compute 6-axis role-percentile radars."""
    results: dict[int, ArchetypeClassification] = {}

    eligible_by_group: dict[RoleGroup, list[PlayerSeasonAggregate]] = {}
    for p in aggregates:
        if p.minutes_total < min_minutes:
            results[p.player_id] = ArchetypeClassification(
                player_id=p.player_id,
                archetype_primary=None,
                archetype_secondary=None,
                archetype_scores_json={},
                radar_percentiles_json=None,
            )
            continue
        group = POSITION_TO_GROUP.get(p.primary_position, "MID")
        eligible_by_group.setdefault(group, []).append(p)

    for group, players in eligible_by_group.items():
        raw_matrix = [_raw_features(p) for p in players]
        num_dims = len(FEATURE_NAMES)
        pct_cols = [
            _empirical_percentiles([row[d] for row in raw_matrix]) for d in range(num_dims)
        ]
        # Defensive 1v1 solidity: lower dribbles_past/90 = higher percentile
        neg_drib_past = [-_per90(float(p.dribbles_past), p.minutes_total) for p in players]
        def_1v1_pcts = _empirical_percentiles(neg_drib_past)

        centroids = GROUP_CENTROIDS[group]
        radar_spec = RADAR_SPECS[group]

        for idx, player in enumerate(players):
            pct_vec = [pct_cols[d][idx] for d in range(num_dims)]
            scores: dict[PlayerArchetype, float] = {}

            for arch, centroid in centroids.items():
                sim = _cosine_similarity(pct_vec, centroid)

                back3_share = (
                    player.back_three_minutes / player.minutes_total
                    if player.minutes_total > 0
                    else 0.0
                )
                if arch == "braccetto" and back3_share >= 0.45:
                    sim = min(1.0, sim + 0.08 * back3_share)
                elif arch == "quinto" and (
                    player.primary_position in ("LWB", "RWB") or back3_share >= 0.50
                ):
                    sim = min(1.0, sim + 0.09)
                elif arch == "terzino_difensivo" and player.primary_position in ("LWB", "RWB"):
                    sim = max(0.0, sim - 0.08)

                scores[arch] = round(sim, 3)

            ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
            primary: PlayerArchetype | None = ranked[0][0] if ranked else None
            secondary: PlayerArchetype | None = None
            if len(ranked) >= 2 and ranked[1][1] >= SECONDARY_THRESHOLD and ranked[1][0] != primary:
                secondary = ranked[1][0]

            radar_axes: list[RadarAxis] = []
            for axis_key, axis_label, feat_idx in radar_spec:
                raw_pct = def_1v1_pcts[idx] if feat_idx == -1 else pct_vec[feat_idx]
                radar_axes.append(
                    RadarAxis(
                        key=axis_key,
                        label=axis_label,
                        percentile=round(raw_pct * 100.0),
                    )
                )

            top_scores = dict(ranked[:4])
            results[player.player_id] = ArchetypeClassification(
                player_id=player.player_id,
                archetype_primary=primary,
                archetype_secondary=secondary,
                archetype_scores_json=top_scores,
                radar_percentiles_json=radar_axes,
            )

    return results

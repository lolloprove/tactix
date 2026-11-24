"""How-To-Beat Vulnerability Extractor (ZERO AI).

Extracts the 3 statistically most solid vulnerabilities for every Serie A team,
ranking candidate signals by `effect_size * confidence_weight` across:
  1. Defensive conditional splits (`xga_delta > 0`, `dribbles_conceded_delta > 0`)
  2. Offensive conditional splits (`xg_delta < 0`, e.g. sterility vs low blocks)
  3. Aggregated spatial `xga_zones_json` (corridor or shot-zone concentration)
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence

from db.models import (
    ConfidenceLevel,
    SampleSize,
    TeamMatchTacticsUpsert,
    Vulnerability,
    XgaShotZone,
    ZoneCorridor,
)
from engine.archetype_classifier import ARCHETYPE_LABELS_IT
from engine.conditional_splits import TeamSplitResult
from engine.confidence import from_matches

_CONF_WEIGHT: dict[ConfidenceLevel, float] = {
    "high": 1.0,
    "medium": 0.78,
    "low": 0.40,
}

_ZONE_LABELS_IT: dict[str, str] = {
    "left": "fascia sinistra",
    "center": "corridoio centrale",
    "right": "fascia destra",
    "six_yard": "area piccola",
    "box_left": "lato sinistro dell'area",
    "box_center": "cuore dell'area di rigore",
    "box_right": "lato destro dell'area",
    "edge_left": "limite sinistro",
    "edge_center": "lunetta del limite",
    "edge_right": "limite destro",
    "long_range": "tiro dalla distanza",
}

_LINE_LABELS_IT: dict[str, str] = {
    "high": "linee difensive alte",
    "mid": "blocchi medi",
    "low": "blocchi bassi",
}


def _severity_from_score(score: float, conf: ConfidenceLevel) -> int:
    if score >= 0.30 and conf in ("medium", "high"):
        return 3
    if score >= 0.16:
        return 2
    return 1


def _describe_split_vulnerability(
    split: TeamSplitResult,
    metric_key: str,
    delta: float,
) -> tuple[str, str, str]:
    ct = split.row.condition_type
    cv = split.row.condition_value
    key = f"{ct}_{cv}_{metric_key}"
    n = split.row.sample_matches
    low_note = " (campione ridotto, tendenza da confermare)" if split.confidence == "low" else ""

    if ct == "vs_archetype":
        arch_it = ARCHETYPE_LABELS_IT.get(cv, cv.replace("_", " "))  # type: ignore[arg-type]
        if metric_key == "xga_delta":
            title = f"Vulnerabile contro {arch_it}"
            desc = f"Concede {delta:+.2f} xGA rispetto alla media quando affronta un profilo {arch_it} ({n} partite){low_note}."
        elif metric_key == "dribbles_conceded_delta":
            title = f"Dribbling concessi contro {arch_it}"
            desc = f"Subisce {delta:+.2f} dribbling in più a partita contro profili {arch_it} ({n} partite){low_note}."
        else:
            title = f"Produzione frenata contro {arch_it}"
            desc = f"Crea {delta:+.2f} xG rispetto alla media contro avversari con {arch_it} ({n} partite){low_note}."
    elif ct == "vs_formation":
        if metric_key == "xga_delta":
            title = f"Soffre il modulo {cv}"
            desc = f"Contro il {cv} concede {delta:+.2f} xGA in più rispetto al proprio baseline stagionale ({n} partite){low_note}."
        else:
            title = f"Sterilità offensiva contro il {cv}"
            desc = f"Contro il {cv} la produzione cala di {delta:+.2f} xG a partita ({n} partite){low_note}."
    elif ct == "vs_back_line":
        if metric_key == "xga_delta":
            title = f"In difficoltà contro difese a {cv}"
            desc = f"Contro linee a {cv} concede {delta:+.2f} xGA oltre la media stagionale ({n} partite){low_note}."
        else:
            title = f"Fatica a creare contro difese a {cv}"
            desc = f"Contro difese a {cv} la produzione offensiva scende di {delta:+.2f} xG ({n} partite){low_note}."
    else:  # vs_high_line
        line_it = _LINE_LABELS_IT.get(cv, cv)
        if metric_key == "xga_delta":
            title = f"Esposta contro {line_it}"
            desc = f"Contro {line_it} concede {delta:+.2f} xGA rispetto alla propria media ({n} partite){low_note}."
        else:
            title = f"Calo offensivo contro {line_it}"
            desc = f"Contro {line_it} produce {delta:+.2f} xG in meno rispetto al baseline ({n} partite){low_note}."

    return key, title, desc


def extract_team_vulnerabilities(
    *,
    team_id: int,
    team_splits: Sequence[TeamSplitResult],
    team_tactics: Sequence[TeamMatchTacticsUpsert],
    top_k: int = 3,
) -> list[Vulnerability]:
    """Extract the top `top_k` (default 3) statistically most solid vulnerabilities for `team_id`."""
    candidates: list[tuple[float, str, Vulnerability]] = []

    # 1. Conditional splits (defensive leaks & offensive drop-offs)
    for sp in team_splits:
        if sp.row.team_id != team_id or sp.row.sample_matches <= 0:
            continue
        w = _CONF_WEIGHT[sp.confidence]
        theme = f"{sp.row.condition_type}:{sp.row.condition_value}"

        # Higher xGA = vulnerability
        if (
            sp.row.xga_delta is not None
            and math.isfinite(sp.row.xga_delta)
            and sp.row.xga_delta >= 0.12
        ):
            score = sp.row.xga_delta * w
            key, title, desc = _describe_split_vulnerability(sp, "xga_delta", sp.row.xga_delta)
            candidates.append(
                (
                    score,
                    theme,
                    Vulnerability(
                        key=key,
                        title=title,
                        description=desc,
                        condition_type=sp.row.condition_type,
                        condition_value=sp.row.condition_value,
                        metric_key="xga_delta",
                        delta=round(sp.row.xga_delta, 2),
                        zone=None,
                        severity=_severity_from_score(score, sp.confidence),  # type: ignore[arg-type]
                        sample=SampleSize(unit="matches", value=sp.row.sample_matches),
                        confidence=sp.confidence,
                    ),
                )
            )

        # Lower xG = offensive vulnerability
        if (
            sp.row.xg_delta is not None
            and math.isfinite(sp.row.xg_delta)
            and sp.row.xg_delta <= -0.18
        ):
            effect = abs(sp.row.xg_delta) * 0.85
            score = effect * w
            key, title, desc = _describe_split_vulnerability(sp, "xg_delta", sp.row.xg_delta)
            candidates.append(
                (
                    score,
                    theme,
                    Vulnerability(
                        key=key,
                        title=title,
                        description=desc,
                        condition_type=sp.row.condition_type,
                        condition_value=sp.row.condition_value,
                        metric_key="xg_delta",
                        delta=round(sp.row.xg_delta, 2),
                        zone=None,
                        severity=_severity_from_score(score, sp.confidence),  # type: ignore[arg-type]
                        sample=SampleSize(unit="matches", value=sp.row.sample_matches),
                        confidence=sp.confidence,
                    ),
                )
            )

        # Higher dribbles conceded = 1v1 defensive vulnerability
        if (
            sp.row.dribbles_conceded_delta is not None
            and math.isfinite(sp.row.dribbles_conceded_delta)
            and sp.row.dribbles_conceded_delta >= 0.8
        ):
            effect = (sp.row.dribbles_conceded_delta / 5.0) * 0.75
            score = effect * w
            key, title, desc = _describe_split_vulnerability(
                sp, "dribbles_conceded_delta", sp.row.dribbles_conceded_delta
            )
            candidates.append(
                (
                    score,
                    theme,
                    Vulnerability(
                        key=key,
                        title=title,
                        description=desc,
                        condition_type=sp.row.condition_type,
                        condition_value=sp.row.condition_value,
                        metric_key="dribbles_conceded_delta",
                        delta=round(sp.row.dribbles_conceded_delta, 2),
                        zone=None,
                        severity=_severity_from_score(score, sp.confidence),  # type: ignore[arg-type]
                        sample=SampleSize(unit="matches", value=sp.row.sample_matches),
                        confidence=sp.confidence,
                    ),
                )
            )

    # 2. Spatial xGA concentration from team_match_tactics.xga_zones_json
    team_rows = [t for t in team_tactics if t.team_id == team_id and t.xga_zones_json is not None]
    if team_rows:
        n_matches = len(team_rows)
        conf = from_matches(n_matches)
        w = _CONF_WEIGHT[conf]

        corridor_totals: dict[ZoneCorridor, float] = {"left": 0.0, "center": 0.0, "right": 0.0}
        shot_zone_totals: dict[XgaShotZone, float] = defaultdict(float)

        for row in team_rows:
            xz = row.xga_zones_json
            if xz is None:
                continue
            corridor_totals["left"] += xz.origin_corridors.left
            corridor_totals["center"] += xz.origin_corridors.center
            corridor_totals["right"] += xz.origin_corridors.right
            for sz in xz.shot_zones:
                shot_zone_totals[sz.zone] += sz.xga

        total_xga = sum(corridor_totals.values())
        if total_xga > 0.0:
            worst_corridor, worst_val = max(corridor_totals.items(), key=lambda kv: kv[1])
            share = worst_val / total_xga
            # Equal 3-way split is 0.333; > 0.42 indicates structural flank/central leak
            if share >= 0.42:
                excess = share - (1.0 / 3.0)
                score = excess * 1.4 * w
                zone_it = _ZONE_LABELS_IT[worst_corridor]
                candidates.append(
                    (
                        score,
                        f"spatial_corridor:{worst_corridor}",
                        Vulnerability(
                            key=f"xga_corridor_{worst_corridor}",
                            title=f"Lato esposto: {zone_it}",
                            description=(
                                f"Il {share * 100:.1f}% degli xGA concessi ({worst_val:.2f} su {total_xga:.2f} in {n_matches} partite) "
                                f"nasce sul lato {zone_it}."
                            ),
                            condition_type=None,
                            condition_value=None,
                            metric_key="xga_corridor_share",
                            delta=round(excess * 100.0, 1),
                            zone=worst_corridor,
                            severity=_severity_from_score(score, conf),  # type: ignore[arg-type]
                            sample=SampleSize(unit="matches", value=n_matches),
                            confidence=conf,
                        ),
                    )
                )

            # Worst box shot zone if high concentration
            if shot_zone_totals:
                worst_sz, sz_val = max(shot_zone_totals.items(), key=lambda kv: kv[1])
                sz_share = sz_val / total_xga
                if sz_share >= 0.35:
                    score = (sz_share - 0.20) * 0.9 * w
                    candidates.append(
                        (
                            score,
                            f"spatial_zone:{worst_sz}",
                            Vulnerability(
                                key=f"xga_zone_{worst_sz}",
                                title=f"Fragilità in {_ZONE_LABELS_IT.get(worst_sz, worst_sz)}",
                                description=(
                                    f"Concede {sz_val:.2f} xGA ({sz_share * 100:.1f}% del totale) "
                                    f"dalla zona {_ZONE_LABELS_IT.get(worst_sz, worst_sz)} su {n_matches} partite."
                                ),
                                condition_type=None,
                                condition_value=None,
                                metric_key="xga_zone_share",
                                delta=round(sz_share * 100.0, 1),
                                zone=worst_sz,
                                severity=_severity_from_score(score, conf),  # type: ignore[arg-type]
                                sample=SampleSize(unit="matches", value=n_matches),
                                confidence=conf,
                            ),
                        )
                    )

    # Deduplicate by theme (keeping strongest metric per theme) and select top_k
    candidates.sort(key=lambda item: item[0], reverse=True)
    selected: list[Vulnerability] = []
    seen_themes: set[str] = set()

    for _, theme, vuln in candidates:
        if theme in seen_themes:
            continue
        seen_themes.add(theme)
        selected.append(vuln)
        if len(selected) >= top_k:
            break

    return selected

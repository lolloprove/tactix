"""Unit tests for Tactix deterministic tactical engine & reconciliation.

Covers every engine module with realistic synthetic Serie A data plus adversarial
edge cases (0 minutes, empty events, zero-variance series, sparse stats) to ensure
ZERO NaNs, ZERO ZeroDivisionErrors, and 1:1 compliance with DB constraints.
"""

from __future__ import annotations

import math

import pytest

from adapters.reconciliation import match_player_name, resolve_canonical_team
from db.models import (
    PlayerMatchStatsUpsert,
    TeamMatchTacticsUpsert,
)
from engine.archetype_classifier import (
    PlayerSeasonAggregate,
    classify_players,
)
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
from engine.confidence import from_matches, from_minutes
from engine.how_to_beat import extract_team_vulnerabilities
from engine.matchup_scorer import (
    duels_to_matchup_rows,
    infer_probable_starters,
    score_upcoming_matchup,
)
from engine.pitch import (
    ShotPoint,
    build_xga_zones,
    classify_shot_zone,
    corridor_from_x,
    flip,
    line_height,
    opposite_corridor,
    shots_by_five_corridors,
)
from engine.tactical_fingerprint import (
    PitchEventSample,
    PlayerPositionSample,
    TeamMatchOptaStats,
    build_dribbles_zones,
    build_team_match_fingerprint,
    compute_ppda,
)

# ---------------------------------------------------------------------------
# Confidence & Pitch primitives
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("minutes", "expected"),
    [(0, "low"), (269, "low"), (270, "medium"), (540, "medium"), (541, "high")],
)
def test_confidence_from_minutes_matches_sql(minutes: int, expected: str) -> None:
    assert from_minutes(minutes) == expected


@pytest.mark.parametrize(
    ("matches", "expected"),
    [(0, "low"), (2, "low"), (3, "medium"), (6, "medium"), (7, "high")],
)
def test_confidence_from_matches_matches_sql(matches: int, expected: str) -> None:
    assert from_matches(matches) == expected


@pytest.mark.parametrize(
    ("x", "expected"),
    [
        (0, "left"),
        (19.9, "left"),
        (20, "left_half"),
        (50, "center"),
        (60, "right_half"),
        (100, "right"),
    ],
)
def test_corridor_from_x(x: float, expected: str) -> None:
    assert corridor_from_x(x) == expected


def test_line_height_buckets() -> None:
    assert line_height(46.5) == "high"
    assert line_height(40.3) == "mid"
    assert line_height(35.0) == "low"


def test_flip_and_opposite_corridor() -> None:
    assert flip(*flip(12.5, 63.0)) == (12.5, 63.0)
    assert opposite_corridor("left") == "right"
    assert opposite_corridor("left_half") == "right_half"
    assert opposite_corridor("center") == "center"


def test_xga_zones_sum_equals_total_xg_and_maps_5_corridors() -> None:
    shots = [
        ShotPoint(x=50.0, y=96.0, xg=0.45, is_goal=True),  # defending: (50, 4) -> six_yard
        ShotPoint(
            x=75.0, y=90.0, xg=0.22, is_goal=False
        ),  # defending: (25, 10) -> box_left / left_half
        ShotPoint(
            x=15.0, y=80.0, xg=0.09, is_goal=False
        ),  # defending: (85, 20) -> edge_right / right
        ShotPoint(x=50.0, y=68.0, xg=0.04, is_goal=False),  # defending: (50, 32) -> long_range
    ]
    assert classify_shot_zone(50.0, 4.0) == "six_yard"
    assert classify_shot_zone(25.0, 10.0) == "box_left"
    assert classify_shot_zone(85.0, 20.0) == "edge_right"
    assert classify_shot_zone(50.0, 32.0) == "long_range"

    five = shots_by_five_corridors(shots)
    assert math.isclose(sum(five.values()), 0.80, abs_tol=1e-3)

    xga_zones = build_xga_zones(shots)
    total_zones = sum(z.xga for z in xga_zones.shot_zones)
    total_corr = (
        xga_zones.origin_corridors.left
        + xga_zones.origin_corridors.center
        + xga_zones.origin_corridors.right
    )
    assert math.isclose(total_zones, 0.80, abs_tol=1e-3)
    assert math.isclose(total_corr, 0.80, abs_tol=1e-3)


# ---------------------------------------------------------------------------
# Tactical Fingerprint (including zero-event / sparse edge cases)
# ---------------------------------------------------------------------------


def test_tactical_fingerprint_full_and_sparse_no_nan() -> None:
    players = [
        PlayerPositionSample("GK", 90, True, 50.0, 7.0, 1),
        PlayerPositionSample("CB", 90, True, 30.0, 44.0, 5),
        PlayerPositionSample("CB", 90, True, 50.0, 42.0, 6),
        PlayerPositionSample("CB", 90, True, 70.0, 46.0, 7),
        PlayerPositionSample("LWB", 90, True, 12.0, 60.0, 9),
        PlayerPositionSample("RWB", 90, True, 88.0, 58.0, 6),
        PlayerPositionSample("ST", 90, True, 48.0, 76.0, 4),
    ]
    opp_players = [
        PlayerPositionSample("CB", 90, True, 45.0, 34.0, 2),
        PlayerPositionSample("ST", 90, True, 52.0, 66.0, 2),
    ]
    events = [
        PitchEventSample(1, "pass", 20.0, 72.0),
        PitchEventSample(1, "pass", 25.0, 75.0),
        PitchEventSample(1, "shot", 80.0, 88.0, xg=0.31, is_goal=True),
        PitchEventSample(1, "tackle", 40.0, 55.0),
        PitchEventSample(2, "pass", 50.0, 30.0),
        PitchEventSample(2, "pass", 40.0, 35.0),
        PitchEventSample(2, "pass", 60.0, 40.0),
        PitchEventSample(2, "shot", 50.0, 86.0, xg=0.25, is_goal=False),
    ]

    fp = build_team_match_fingerprint(
        match_id=10,
        team_id=1,
        formation="3-5-2",
        possession=58.4,
        provider_ppda=None,
        team_players=players,
        opp_players=opp_players,
        events=events,
    )
    assert fp.back_line_count == 3
    assert fp.avg_def_line_y == 44.0
    assert fp.ppda == 3.0  # 3 opp passes in y<=60 / 1 def action in y>=40
    assert fp.field_tilt is not None and 0.0 <= fp.field_tilt <= 100.0
    assert (
        fp.attack_bias_left is not None
        and fp.attack_bias_center is not None
        and fp.attack_bias_right is not None
    )
    assert abs((fp.attack_bias_left + fp.attack_bias_center + fp.attack_bias_right) - 100.0) <= 0.05
    assert fp.xga_zones_json is not None

    # Sparse / empty edge case: must never raise ZeroDivisionError or produce NaN
    empty_fp = build_team_match_fingerprint(
        match_id=11,
        team_id=1,
        formation=None,
        possession=None,
        provider_ppda=None,
        team_players=[],
        opp_players=[],
        events=[],
    )
    assert empty_fp.ppda is None
    assert empty_fp.field_tilt is None
    assert empty_fp.avg_def_line_y is None
    assert empty_fp.attack_bias_left is None
    assert empty_fp.xga_zones_json is None


# ---------------------------------------------------------------------------
# Chameleon Detector
# ---------------------------------------------------------------------------


def test_chameleon_detector_flags_formation_and_zscore_shifts_without_div0() -> None:
    tiers = compute_league_tiers(
        [
            (1, 2, 2, 0, 2.0, 0.5),
            (1, 3, 3, 1, 2.5, 0.9),
            (2, 3, 1, 1, 1.1, 1.0),
            (4, 5, 0, 2, 0.4, 1.8),
            (5, 6, 1, 0, 1.3, 0.6),
            (4, 6, 0, 0, 0.5, 0.5),
        ]
    )
    assert set(tiers.values()).issubset({"top_6", "mid_table", "relegation"})

    # 3 steady 4-2-3-1 matches, then 1 formation shift, then 1 PPDA/line spike
    base_records = [
        TeamMatchRecord(
            match_id=1,
            round=1,
            team_id=2,
            opponent_id=3,
            xg=1.4,
            xga=0.9,
            goals_for=1,
            goals_against=1,
            tactics=TeamMatchTacticsUpsert(
                match_id=1,
                team_id=2,
                formation="4-2-3-1",
                back_line_count=4,
                ppda=9.5,
                avg_def_line_y=45.0,
            ),
        ),
        TeamMatchRecord(
            match_id=2,
            round=2,
            team_id=2,
            opponent_id=5,
            xg=1.8,
            xga=0.8,
            goals_for=2,
            goals_against=0,
            tactics=TeamMatchTacticsUpsert(
                match_id=2,
                team_id=2,
                formation="4-2-3-1",
                back_line_count=4,
                ppda=10.1,
                avg_def_line_y=46.0,
            ),
        ),
        TeamMatchRecord(
            match_id=3,
            round=3,
            team_id=2,
            opponent_id=6,
            xg=1.5,
            xga=1.0,
            goals_for=1,
            goals_against=0,
            tactics=TeamMatchTacticsUpsert(
                match_id=3,
                team_id=2,
                formation="4-2-3-1",
                back_line_count=4,
                ppda=9.8,
                avg_def_line_y=45.5,
            ),
        ),
        # Match 4: shifts formation to 3-4-2-1 AND drops line + passive PPDA
        TeamMatchRecord(
            match_id=4,
            round=4,
            team_id=2,
            opponent_id=1,
            xg=0.8,
            xga=2.1,
            goals_for=1,
            goals_against=2,
            tactics=TeamMatchTacticsUpsert(
                match_id=4,
                team_id=2,
                formation="3-4-2-1",
                back_line_count=3,
                ppda=15.0,
                avg_def_line_y=36.0,
            ),
        ),
    ]

    report = detect_chameleon_shifts(2, base_records, tiers)
    assert len(report.updated_tactics) == 4
    assert report.updated_tactics[0].is_tactical_shift is False
    assert report.updated_tactics[3].is_tactical_shift is True
    assert report.updated_tactics[3].baseline_formation == "4-2-3-1"
    assert report.updated_tactics[3].shift_reason is not None
    assert "4-2-3-1 → 3-4-2-1" in report.updated_tactics[3].shift_reason

    # Zero-variance edge case (identical PPDA & line_y across prior rounds -> std == 0, no ZeroDivisionError)
    const_recs = [
        TeamMatchRecord(
            match_id=10 + r,
            round=r,
            team_id=9,
            opponent_id=1,
            xg=1.0,
            xga=1.0,
            goals_for=1,
            goals_against=1,
            tactics=TeamMatchTacticsUpsert(
                match_id=10 + r,
                team_id=9,
                formation="4-3-3",
                back_line_count=4,
                ppda=10.0,
                avg_def_line_y=42.0,
            ),
        )
        for r in range(1, 5)
    ]
    const_report = detect_chameleon_shifts(9, const_recs, tiers)
    assert all(not t.is_tactical_shift for t in const_report.updated_tactics)


# ---------------------------------------------------------------------------
# Archetype Classifier
# ---------------------------------------------------------------------------


def test_archetype_classifier_respects_180_min_and_valid_scores() -> None:
    players = [
        # < 180 min -> must NOT be classified
        PlayerSeasonAggregate(1, "LW", 120, 4, 1, 5, 5, 6, 0.4, 0.3, 15.0, 75.0),
        # Pure 1v1 wide dribbler
        PlayerSeasonAggregate(2, "LW", 720, 38, 4, 48, 30, 52, 2.2, 3.6, 12.0, 74.0),
        # Inverted winger (central, high xG)
        PlayerSeasonAggregate(3, "LW", 720, 12, 3, 25, 25, 34, 5.1, 2.8, 36.0, 82.0),
        # Braccetto in back 3
        PlayerSeasonAggregate(
            4, "CB", 900, 14, 4, 58, 28, 72, 0.9, 1.4, 20.0, 48.0, back_three_minutes=900
        ),
        # Aggressive marker CB
        PlayerSeasonAggregate(
            5, "CB", 900, 2, 3, 85, 16, 18, 0.8, 0.1, 48.0, 36.0, back_three_minutes=0
        ),
        # Ball-playing CB
        PlayerSeasonAggregate(
            6, "CB", 900, 7, 5, 38, 22, 95, 0.3, 0.8, 50.0, 42.0, back_three_minutes=0
        ),
        # Single GK in group (n=1 percentile edge case -> must not produce NaN)
        PlayerSeasonAggregate(7, "GK", 900, 0, 0, 5, 1, 40, 0.0, 0.0, 50.0, 12.0),
    ]
    classified = classify_players(players)

    assert classified[1].archetype_primary is None
    assert classified[1].archetype_scores_json == {}

    assert classified[2].archetype_primary == "ala_dribblatrice"
    assert classified[3].archetype_primary == "ala_inversa"
    assert classified[4].archetype_primary == "braccetto"
    assert classified[5].archetype_primary == "centrale_marcatore"
    assert classified[6].archetype_primary == "centrale_impostazione"
    assert classified[7].archetype_primary in ("portiere_classico", "portiere_libero")

    for cls in classified.values():
        if cls.archetype_secondary is not None:
            assert cls.archetype_secondary != cls.archetype_primary
        for score in cls.archetype_scores_json.values():
            assert math.isfinite(score) and 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Conditional Splits + Matchup Scorer + How-To-Beat End-to-End Synthetic Test
# ---------------------------------------------------------------------------


def test_conditional_splits_matchup_scorer_and_how_to_beat_end_to_end() -> None:
    season = "2026/27"
    # 4 teams (1=Inter, 2=Juventus, 3=Napoli, 4=Milan), 6 finished matches
    matches = [
        FinishedMatchContext(101, season, 1, 1, 2, 2.2, 0.9),
        FinishedMatchContext(102, season, 2, 3, 1, 1.1, 1.7),
        FinishedMatchContext(103, season, 3, 1, 4, 1.5, 1.3),
        FinishedMatchContext(104, season, 4, 2, 3, 1.6, 1.4),
        FinishedMatchContext(105, season, 5, 4, 2, 1.8, 0.8),
        FinishedMatchContext(106, season, 6, 3, 4, 1.9, 1.2),
    ]

    tactics = [
        # Match 101: Inter (3-5-2, high) vs Juve (4-2-3-1, mid)
        TeamMatchTacticsUpsert(
            match_id=101,
            team_id=1,
            formation="3-5-2",
            back_line_count=3,
            avg_def_line_y=47.0,
            ppda=8.5,
            xga_zones_json=build_xga_zones([ShotPoint(20, 88, 0.9, False)]),
        ),
        TeamMatchTacticsUpsert(
            match_id=101,
            team_id=2,
            formation="4-2-3-1",
            back_line_count=4,
            avg_def_line_y=39.0,
            ppda=12.5,
            xga_zones_json=build_xga_zones(
                [ShotPoint(15, 90, 1.4, True), ShotPoint(50, 86, 0.8, True)]
            ),
        ),
        # Match 102: Napoli (4-3-3, high) vs Inter (3-5-2, high)
        TeamMatchTacticsUpsert(
            match_id=102,
            team_id=3,
            formation="4-3-3",
            back_line_count=4,
            avg_def_line_y=46.0,
            ppda=9.2,
            xga_zones_json=build_xga_zones(
                [ShotPoint(15, 90, 1.2, True), ShotPoint(50, 85, 0.5, False)]
            ),
        ),
        TeamMatchTacticsUpsert(
            match_id=102,
            team_id=1,
            formation="3-5-2",
            back_line_count=3,
            avg_def_line_y=46.0,
            ppda=9.0,
            xga_zones_json=build_xga_zones([ShotPoint(80, 90, 1.1, True)]),
        ),
        # Match 103: Inter (3-5-2) vs Milan (3-5-2)
        TeamMatchTacticsUpsert(
            match_id=103,
            team_id=1,
            formation="3-5-2",
            back_line_count=3,
            avg_def_line_y=45.5,
            ppda=9.4,
        ),
        TeamMatchTacticsUpsert(
            match_id=103,
            team_id=4,
            formation="3-5-2",
            back_line_count=3,
            avg_def_line_y=41.0,
            ppda=11.0,
        ),
        # Match 104: Juve (4-2-3-1) vs Napoli (4-3-3)
        TeamMatchTacticsUpsert(
            match_id=104,
            team_id=2,
            formation="4-2-3-1",
            back_line_count=4,
            avg_def_line_y=40.0,
            ppda=11.5,
        ),
        TeamMatchTacticsUpsert(
            match_id=104,
            team_id=3,
            formation="4-3-3",
            back_line_count=4,
            avg_def_line_y=46.5,
            ppda=9.5,
        ),
        # Match 105: Milan (3-5-2) vs Juve (4-2-3-1)
        TeamMatchTacticsUpsert(
            match_id=105,
            team_id=4,
            formation="3-5-2",
            back_line_count=3,
            avg_def_line_y=42.0,
            ppda=10.2,
        ),
        TeamMatchTacticsUpsert(
            match_id=105,
            team_id=2,
            formation="4-2-3-1",
            back_line_count=4,
            avg_def_line_y=34.5,
            ppda=13.5,
            xga_zones_json=build_xga_zones(
                [ShotPoint(12, 91, 1.3, True), ShotPoint(50, 88, 0.5, True)]
            ),
        ),
        # Match 106: Napoli (4-3-3) vs Milan (3-5-2)
        TeamMatchTacticsUpsert(
            match_id=106,
            team_id=3,
            formation="4-3-3",
            back_line_count=4,
            avg_def_line_y=45.0,
            ppda=9.8,
        ),
        TeamMatchTacticsUpsert(
            match_id=106,
            team_id=4,
            formation="3-5-2",
            back_line_count=3,
            avg_def_line_y=35.0,
            ppda=12.0,
        ),
    ]

    # Key players across opposing corridors:
    # 11 = Inter LWB (left, quinto), 12 = Inter ST (center, prima_punta)
    # 21 = Juve RB (right, terzino_difensivo), 22 = Juve LW (left, ala_dribblatrice)
    # 31 = Napoli RB (right, terzino_difensivo), 32 = Napoli LW (left, ala_dribblatrice)
    # 41 = Milan LW (left, ala_dribblatrice), 42 = Milan RCB (right, braccetto)
    archetypes = {
        11: "quinto",
        12: "prima_punta",
        21: "terzino_difensivo",
        22: "ala_dribblatrice",
        31: "terzino_difensivo",
        32: "ala_dribblatrice",
        41: "ala_dribblatrice",
        42: "braccetto",
    }

    pms = [
        # Match 101: Inter (11 left) vs Juve (21 right) -> 11 dominates 21
        PlayerMatchStatsUpsert(
            match_id=101,
            player_id=11,
            team_id=1,
            opponent_id=2,
            position_played="LWB",
            minutes=90,
            avg_x=14.0,
            avg_y=64.0,
            zone_corridor="left",
            dribbles_won=5,
            dribbles_past=0,
            duels_won=9,
            duels_lost=2,
            progressive_actions=10,
            xg=0.2,
            xa=0.5,
            rating=8.2,
        ),
        PlayerMatchStatsUpsert(
            match_id=101,
            player_id=12,
            team_id=1,
            opponent_id=2,
            position_played="ST",
            minutes=90,
            avg_x=50.0,
            avg_y=78.0,
            zone_corridor="center",
            dribbles_won=1,
            dribbles_past=0,
            duels_won=7,
            duels_lost=3,
            progressive_actions=3,
            xg=0.8,
            xa=0.1,
            rating=7.6,
        ),
        PlayerMatchStatsUpsert(
            match_id=101,
            player_id=21,
            team_id=2,
            opponent_id=1,
            position_played="RB",
            minutes=90,
            avg_x=86.0,
            avg_y=38.0,
            zone_corridor="right",
            dribbles_won=0,
            dribbles_past=5,
            duels_won=3,
            duels_lost=8,
            progressive_actions=2,
            xg=0.0,
            xa=0.0,
            rating=5.4,
        ),
        PlayerMatchStatsUpsert(
            match_id=101,
            player_id=22,
            team_id=2,
            opponent_id=1,
            position_played="LW",
            minutes=90,
            avg_x=16.0,
            avg_y=70.0,
            zone_corridor="left",
            dribbles_won=3,
            dribbles_past=1,
            duels_won=6,
            duels_lost=4,
            progressive_actions=6,
            xg=0.3,
            xa=0.2,
            rating=6.9,
        ),
        # Match 102: Napoli (31 right) vs Inter (11 left)
        PlayerMatchStatsUpsert(
            match_id=102,
            player_id=11,
            team_id=1,
            opponent_id=3,
            position_played="LWB",
            minutes=90,
            avg_x=15.0,
            avg_y=62.0,
            zone_corridor="left",
            dribbles_won=4,
            dribbles_past=1,
            duels_won=8,
            duels_lost=3,
            progressive_actions=8,
            xg=0.1,
            xa=0.4,
            rating=7.8,
        ),
        PlayerMatchStatsUpsert(
            match_id=102,
            player_id=31,
            team_id=3,
            opponent_id=1,
            position_played="RB",
            minutes=90,
            avg_x=85.0,
            avg_y=40.0,
            zone_corridor="right",
            dribbles_won=0,
            dribbles_past=4,
            duels_won=4,
            duels_lost=7,
            progressive_actions=3,
            xg=0.0,
            xa=0.1,
            rating=5.8,
        ),
        PlayerMatchStatsUpsert(
            match_id=102,
            player_id=32,
            team_id=3,
            opponent_id=1,
            position_played="LW",
            minutes=90,
            avg_x=14.0,
            avg_y=72.0,
            zone_corridor="left",
            dribbles_won=4,
            dribbles_past=0,
            duels_won=7,
            duels_lost=3,
            progressive_actions=5,
            xg=0.4,
            xa=0.2,
            rating=7.2,
        ),
        # Match 103: Inter (11 left) vs Milan (42 right)
        PlayerMatchStatsUpsert(
            match_id=103,
            player_id=11,
            team_id=1,
            opponent_id=4,
            position_played="LWB",
            minutes=90,
            avg_x=14.0,
            avg_y=58.0,
            zone_corridor="left",
            dribbles_won=1,
            dribbles_past=2,
            duels_won=4,
            duels_lost=6,
            progressive_actions=5,
            xg=0.05,
            xa=0.1,
            rating=6.2,
        ),
        PlayerMatchStatsUpsert(
            match_id=103,
            player_id=42,
            team_id=4,
            opponent_id=1,
            position_played="CB",
            minutes=90,
            avg_x=84.0,
            avg_y=40.0,
            zone_corridor="right",
            dribbles_won=1,
            dribbles_past=1,
            duels_won=7,
            duels_lost=2,
            progressive_actions=6,
            xg=0.0,
            xa=0.0,
            rating=7.3,
        ),
        PlayerMatchStatsUpsert(
            match_id=103,
            player_id=41,
            team_id=4,
            opponent_id=1,
            position_played="LW",
            minutes=90,
            avg_x=18.0,
            avg_y=74.0,
            zone_corridor="left",
            dribbles_won=4,
            dribbles_past=0,
            duels_won=7,
            duels_lost=3,
            progressive_actions=6,
            xg=0.5,
            xa=0.2,
            rating=7.5,
        ),
        # Match 104: Juve (22 left, 21 right) vs Napoli (31 right, 32 left)
        PlayerMatchStatsUpsert(
            match_id=104,
            player_id=22,
            team_id=2,
            opponent_id=3,
            position_played="LW",
            minutes=90,
            avg_x=16.0,
            avg_y=72.0,
            zone_corridor="left",
            dribbles_won=5,
            dribbles_past=0,
            duels_won=8,
            duels_lost=2,
            progressive_actions=7,
            xg=0.4,
            xa=0.3,
            rating=7.9,
        ),
        PlayerMatchStatsUpsert(
            match_id=104,
            player_id=31,
            team_id=3,
            opponent_id=2,
            position_played="RB",
            minutes=90,
            avg_x=86.0,
            avg_y=41.0,
            zone_corridor="right",
            dribbles_won=0,
            dribbles_past=5,
            duels_won=3,
            duels_lost=7,
            progressive_actions=2,
            xg=0.0,
            xa=0.0,
            rating=5.6,
        ),
        PlayerMatchStatsUpsert(
            match_id=104,
            player_id=21,
            team_id=2,
            opponent_id=3,
            position_played="RB",
            minutes=90,
            avg_x=86.0,
            avg_y=42.0,
            zone_corridor="right",
            dribbles_won=1,
            dribbles_past=2,
            duels_won=6,
            duels_lost=4,
            progressive_actions=4,
            xg=0.0,
            xa=0.1,
            rating=6.6,
        ),
        PlayerMatchStatsUpsert(
            match_id=104,
            player_id=32,
            team_id=3,
            opponent_id=2,
            position_played="LW",
            minutes=90,
            avg_x=16.0,
            avg_y=70.0,
            zone_corridor="left",
            dribbles_won=2,
            dribbles_past=1,
            duels_won=5,
            duels_lost=5,
            progressive_actions=4,
            xg=0.2,
            xa=0.2,
            rating=6.5,
        ),
        # Match 105: Milan (41 left, 42 right) vs Juve (21 right, 22 left)
        PlayerMatchStatsUpsert(
            match_id=105,
            player_id=41,
            team_id=4,
            opponent_id=2,
            position_played="LW",
            minutes=90,
            avg_x=16.0,
            avg_y=74.0,
            zone_corridor="left",
            dribbles_won=6,
            dribbles_past=0,
            duels_won=9,
            duels_lost=2,
            progressive_actions=8,
            xg=0.6,
            xa=0.3,
            rating=8.1,
        ),
        PlayerMatchStatsUpsert(
            match_id=105,
            player_id=21,
            team_id=2,
            opponent_id=4,
            position_played="RB",
            minutes=90,
            avg_x=86.0,
            avg_y=36.0,
            zone_corridor="right",
            dribbles_won=0,
            dribbles_past=6,
            duels_won=2,
            duels_lost=9,
            progressive_actions=2,
            xg=0.0,
            xa=0.0,
            rating=5.1,
        ),
        PlayerMatchStatsUpsert(
            match_id=105,
            player_id=22,
            team_id=2,
            opponent_id=4,
            position_played="LW",
            minutes=90,
            avg_x=15.0,
            avg_y=68.0,
            zone_corridor="left",
            dribbles_won=2,
            dribbles_past=1,
            duels_won=5,
            duels_lost=5,
            progressive_actions=4,
            xg=0.2,
            xa=0.1,
            rating=6.4,
        ),
        PlayerMatchStatsUpsert(
            match_id=105,
            player_id=42,
            team_id=4,
            opponent_id=2,
            position_played="CB",
            minutes=90,
            avg_x=84.0,
            avg_y=41.0,
            zone_corridor="right",
            dribbles_won=1,
            dribbles_past=1,
            duels_won=7,
            duels_lost=3,
            progressive_actions=5,
            xg=0.0,
            xa=0.0,
            rating=7.1,
        ),
        # Match 106: Napoli (31 right) vs Milan (41 left)
        PlayerMatchStatsUpsert(
            match_id=106,
            player_id=41,
            team_id=4,
            opponent_id=3,
            position_played="LW",
            minutes=90,
            avg_x=15.0,
            avg_y=73.0,
            zone_corridor="left",
            dribbles_won=4,
            dribbles_past=0,
            duels_won=8,
            duels_lost=3,
            progressive_actions=7,
            xg=0.4,
            xa=0.2,
            rating=7.6,
        ),
        PlayerMatchStatsUpsert(
            match_id=106,
            player_id=31,
            team_id=3,
            opponent_id=4,
            position_played="RB",
            minutes=90,
            avg_x=85.0,
            avg_y=42.0,
            zone_corridor="right",
            dribbles_won=0,
            dribbles_past=4,
            duels_won=4,
            duels_lost=6,
            progressive_actions=2,
            xg=0.0,
            xa=0.0,
            rating=5.9,
        ),
    ]

    team_splits = compute_team_splits(
        season=season,
        matches=matches,
        tactics=tactics,
        player_stats=pms,
        player_archetypes=archetypes,
    )
    player_splits = compute_player_splits(
        season=season,
        tactics=tactics,
        player_stats=pms,
        player_archetypes=archetypes,
    )

    assert len(team_splits) > 0
    assert len(player_splits) > 0

    # Verify zero NaNs and valid confidence badges
    for ts in team_splits:
        assert ts.confidence in ("low", "medium", "high")
        for val in (ts.row.xg_delta, ts.row.xga_delta, ts.row.dribbles_conceded_delta):
            assert val is None or math.isfinite(val)

    for ps in player_splits:
        assert ps.confidence in ("low", "medium", "high")
        for val in (ps.row.rating_delta, ps.row.dribbles_delta, ps.row.duels_delta):
            assert val is None or math.isfinite(val)

    # Verify spatial opposite-corridor pairing worked:
    # Inter LWB (11) faced terzino_difensivo (21, 31) and outperformed his baseline!
    p11_vs_td = next(
        (
            s
            for s in player_splits
            if s.row.player_id == 11
            and s.row.condition_type == "vs_defender_archetype"
            and s.row.condition_value == "terzino_difensivo"
        ),
        None,
    )
    assert p11_vs_td is not None
    assert p11_vs_td.row.rating_delta is not None and p11_vs_td.row.rating_delta > 0

    # Upcoming Matchup Scorer: Juventus (2) vs Napoli (3)
    juve_starters = infer_probable_starters(
        team_id=2,
        team_players=[
            (21, "Di Marco-Opp", "RB", "terzino_difensivo"),
            (22, "Yildiz", "LW", "ala_dribblatrice"),
        ],
        recent_stats=pms,
        recent_match_ids=[101, 104, 105],
    )
    napoli_starters = infer_probable_starters(
        team_id=3,
        team_players=[
            (31, "Di Lorenzo", "RB", "terzino_difensivo"),
            (32, "Neres", "LW", "ala_dribblatrice"),
        ],
        recent_stats=pms,
        recent_match_ids=[102, 104, 106],
    )
    analysis = score_upcoming_matchup(
        match_id=201,
        home_team_id=2,
        away_team_id=3,
        home_starters=juve_starters,
        away_starters=napoli_starters,
        tactics_history=tactics,
        team_splits=team_splits,
        player_splits=player_splits,
    )
    assert len(analysis.key_duels) >= 1
    for d in analysis.key_duels:
        assert 0.0 <= d.mismatch_score <= 100.0
    assert 1 <= len(analysis.x_factors) <= 3
    assert len(analysis.starter_observations) == len(juve_starters) + len(napoli_starters)

    # How-To-Beat for Juventus (2)
    juve_vulns = extract_team_vulnerabilities(
        team_id=2,
        team_splits=team_splits,
        team_tactics=tactics,
        top_k=3,
    )
    assert 1 <= len(juve_vulns) <= 3
    for v in juve_vulns:
        assert v.severity in (1, 2, 3)
        assert v.confidence in ("low", "medium", "high")


# ---------------------------------------------------------------------------
# Reconciliation tests
# ---------------------------------------------------------------------------


def test_team_and_player_reconciliation() -> None:
    assert resolve_canonical_team("FC Internazionale Milano").slug == "inter"
    assert resolve_canonical_team("Inter Milan").slug == "inter"
    assert resolve_canonical_team("AC Milan").slug == "milan"
    assert resolve_canonical_team("Hellas Verona FC").slug == "verona"
    assert resolve_canonical_team("Como 1907").slug == "como"

    candidates = [
        (10, "Lautaro Martínez"),
        (11, "Hakan Çalhanoğlu"),
        (12, "Gleison Bremer"),
    ]
    assert match_player_name("L. Martinez", candidates) == 10
    assert match_player_name("Hakan Calhanoglu", candidates) == 11
    assert match_player_name("Bremer", candidates) == 12
    assert match_player_name("Completely Different Player", candidates) is None


# ---------------------------------------------------------------------------
# FotMob Opta PPDA Proxy, Calibrated Def Line, Dribbles Zones, Radar & Matchups
# ---------------------------------------------------------------------------


def test_fotmob_opta_ppda_proxy_without_understat() -> None:
    """When Understat is unavailable (provider_ppda=None), compute deterministic PPDA from FotMob Opta stats."""
    # High-pressing team (Como-like): opponent plays 170 own-half + 140 opp-half passes;
    # pressing team makes 22 tackles, 12 interceptions, 14 fouls (with high-positioned players)
    high_press_players = [
        PlayerPositionSample("ST", 90, True, 50.0, 82.0, tackles=2, interceptions=1, fouls=2),
        PlayerPositionSample("LW", 90, True, 18.0, 72.0, tackles=3, interceptions=2, fouls=2),
        PlayerPositionSample("RW", 90, True, 82.0, 72.0, tackles=2, interceptions=1, fouls=1),
        PlayerPositionSample("CM", 90, True, 40.0, 56.0, tackles=5, interceptions=3, fouls=3),
        PlayerPositionSample("CM", 90, True, 60.0, 56.0, tackles=4, interceptions=2, fouls=2),
        PlayerPositionSample("CB", 90, True, 40.0, 29.2, tackles=3, interceptions=2, fouls=2),
        PlayerPositionSample("CB", 90, True, 60.0, 29.2, tackles=3, interceptions=1, fouls=2),
    ]
    low_block_players = [
        PlayerPositionSample("ST", 90, True, 50.0, 70.0, tackles=0, interceptions=0, fouls=1),
        PlayerPositionSample("CM", 90, True, 40.0, 44.0, tackles=2, interceptions=1, fouls=2),
        PlayerPositionSample("CM", 90, True, 60.0, 44.0, tackles=1, interceptions=1, fouls=1),
        PlayerPositionSample("CB", 90, True, 35.0, 29.2, tackles=3, interceptions=2, fouls=1),
        PlayerPositionSample("CB", 90, True, 50.0, 29.2, tackles=3, interceptions=2, fouls=1),
        PlayerPositionSample("CB", 90, True, 65.0, 29.2, tackles=2, interceptions=1, fouls=1),
    ]

    high_opta = TeamMatchOptaStats(
        own_half_passes=210,
        opp_half_passes=260,
        tackles=22,
        interceptions=12,
        fouls=14,
        touches_opp_box=34,
        attack_bias_left=28.0,
        attack_bias_center=40.0,
        attack_bias_right=32.0,
    )
    low_opta = TeamMatchOptaStats(
        own_half_passes=170,
        opp_half_passes=140,
        tackles=11,
        interceptions=7,
        fouls=7,
        touches_opp_box=12,
        attack_bias_left=40.0,
        attack_bias_center=25.0,
        attack_bias_right=35.0,
    )

    ppda_high = compute_ppda(
        team_id=1,
        events=[],
        provider_ppda=None,
        team_opta=high_opta,
        opp_opta=low_opta,
        team_players=high_press_players,
    )
    ppda_low = compute_ppda(
        team_id=2,
        events=[],
        provider_ppda=None,
        team_opta=low_opta,
        opp_opta=high_opta,
        team_players=low_block_players,
    )
    assert ppda_high is not None and ppda_low is not None
    assert 3.0 <= ppda_high < ppda_low <= 30.0

    # Also verify calibrated defensive line replaces static FotMob 29.2 grid
    pms_high = [
        PlayerMatchStatsUpsert(
            match_id=99,
            player_id=100 + i,
            team_id=1,
            opponent_id=2,
            position_played=p.position or "CM",
            minutes=90,
            avg_x=p.avg_x,
            avg_y=p.avg_y,
            zone_corridor=corridor_from_x(p.avg_x or 50.0),
            dribbles_won=2 if p.position in ("LW", "RW") else 0,
            dribbles_past=1 if p.position == "CB" else 0,
            duels_won=4,
            duels_lost=2,
            progressive_actions=5,
            xg=0.2,
            xa=0.1,
            rating=7.1,
        )
        for i, p in enumerate(high_press_players)
    ]
    fp_high = build_team_match_fingerprint(
        match_id=99,
        team_id=1,
        formation="4-2-3-1",
        possession=61.0,
        provider_ppda=None,
        team_players=high_press_players,
        opp_players=low_block_players,
        events=[],
        team_opta=high_opta,
        opp_opta=low_opta,
        player_stats=pms_high,
    )
    fp_low = build_team_match_fingerprint(
        match_id=99,
        team_id=2,
        formation="3-5-2",
        possession=39.0,
        provider_ppda=None,
        team_players=low_block_players,
        opp_players=high_press_players,
        events=[],
        team_opta=low_opta,
        opp_opta=high_opta,
        player_stats=[],
    )
    assert fp_high.ppda is not None and fp_low.ppda is not None
    assert fp_high.avg_def_line_y is not None and fp_low.avg_def_line_y is not None
    assert fp_high.avg_def_line_y > fp_low.avg_def_line_y
    assert fp_high.field_tilt is not None and fp_high.field_tilt > 55.0
    assert fp_high.dribbles_zones_json is not None
    assert fp_high.dribbles_zones_json.total_produced == 4
    assert fp_high.dribbles_zones_json.total_conceded == 2
    assert sum(c.count for c in fp_high.dribbles_zones_json.produced) == 4
    assert sum(c.count for c in fp_high.dribbles_zones_json.conceded) == 2


def test_radar_percentiles_and_matchup_rows() -> None:
    """Radar percentiles require >= 180 min (6 axes 0..100); duels_to_matchup_rows orients home=a."""
    players = [
        PlayerSeasonAggregate(1, "LW", 120, 4, 1, 5, 5, 6, 0.4, 0.3, 15.0, 75.0),
        PlayerSeasonAggregate(2, "LW", 720, 38, 4, 48, 30, 52, 2.2, 3.6, 12.0, 74.0),
        PlayerSeasonAggregate(3, "LW", 720, 12, 3, 25, 25, 34, 5.1, 2.8, 36.0, 82.0),
    ]
    classified = classify_players(players)
    assert classified[1].radar_percentiles_json is None
    assert classified[2].radar_percentiles_json is not None
    assert len(classified[2].radar_percentiles_json) == 6
    for ax in classified[2].radar_percentiles_json:
        assert 0.0 <= ax.percentile <= 100.0

    # Empty build_dribbles_zones returns None
    assert build_dribbles_zones([], team_id=1) is None

    # duels_to_matchup_rows on synthetic duels
    juve_starters = infer_probable_starters(
        team_id=2,
        team_players=[(21, "Cambiaso", "RB", "terzino_difensivo")],
        recent_stats=[],
        recent_match_ids=[],
    )
    napoli_starters = infer_probable_starters(
        team_id=3,
        team_players=[(32, "Neres", "LW", "ala_dribblatrice")],
        recent_stats=[],
        recent_match_ids=[],
    )
    analysis = score_upcoming_matchup(
        match_id=300,
        home_team_id=2,
        away_team_id=3,
        home_starters=juve_starters,
        away_starters=napoli_starters,
        tactics_history=[],
        team_splits=[],
        player_splits=[],
    )
    rows = duels_to_matchup_rows(analysis.key_duels, home_team_id=2)
    assert len(rows) == 1
    assert rows[0].team_a_id == 2
    assert rows[0].team_b_id == 3
    assert rows[0].confidence in ("low", "medium", "high")


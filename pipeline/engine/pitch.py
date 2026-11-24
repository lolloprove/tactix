"""Tactix pitch frame: 0-100, x = width (left → right facing the attack),
y = length (own goal → opponent goal). Shared with DESIGN.md §6."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from db.models import (
    OriginCorridors,
    PlayerPosition,
    XgaShotZone,
    XgaShotZoneValue,
    XgaZones,
    ZoneCorridor,
)

LineHeight = Literal["high", "mid", "low"]

CORRIDOR_EDGES: tuple[tuple[float, ZoneCorridor], ...] = (
    (20.0, "left"),
    (40.0, "left_half"),
    (60.0, "center"),
    (80.0, "right_half"),
)

ALL_CORRIDORS: tuple[ZoneCorridor, ...] = ("left", "left_half", "center", "right_half", "right")

ALL_SHOT_ZONES: tuple[XgaShotZone, ...] = (
    "six_yard",
    "box_left",
    "box_center",
    "box_right",
    "edge_left",
    "edge_center",
    "edge_right",
    "long_range",
)

# Buckets for `avg_def_line_y`; tune once a full round of real data is in.
LINE_HIGH_MIN = 45.0
LINE_LOW_MAX = 36.0

_OPPOSITE_CORRIDOR: dict[ZoneCorridor, ZoneCorridor] = {
    "left": "right",
    "left_half": "right_half",
    "center": "center",
    "right_half": "left_half",
    "right": "left",
}

_ADJACENT_CORRIDORS: dict[ZoneCorridor, tuple[ZoneCorridor, ...]] = {
    "left": ("left", "left_half"),
    "left_half": ("left_half", "left", "center"),
    "center": ("center", "left_half", "right_half"),
    "right_half": ("right_half", "right", "center"),
    "right": ("right", "right_half"),
}

_POSITION_DEFAULT_CORRIDOR: dict[PlayerPosition, ZoneCorridor] = {
    "GK": "center",
    "CB": "center",
    "LB": "left",
    "LWB": "left",
    "LW": "left",
    "RB": "right",
    "RWB": "right",
    "RW": "right",
    "DM": "center",
    "CM": "center",
    "AM": "center",
    "ST": "center",
}


@dataclass(frozen=True)
class ShotPoint:
    """Shot in the SHOOTING team's frame (x=width 0..100, y=length 0..100)."""

    x: float
    y: float
    xg: float
    is_goal: bool = False


def corridor_from_x(x: float) -> ZoneCorridor:
    for edge, corridor in CORRIDOR_EDGES:
        if x < edge:
            return corridor
    return "right"


def position_default_corridor(position: PlayerPosition | None) -> ZoneCorridor:
    if position is None:
        return "center"
    return _POSITION_DEFAULT_CORRIDOR.get(position, "center")


def opposite_corridor(corridor: ZoneCorridor) -> ZoneCorridor:
    """Map an attacking corridor to the defending team's opposing corridor."""
    return _OPPOSITE_CORRIDOR[corridor]


def facing_corridors(corridor: ZoneCorridor) -> tuple[ZoneCorridor, ...]:
    """Primary opposite corridor followed by its immediately adjacent corridors."""
    return _ADJACENT_CORRIDORS[_OPPOSITE_CORRIDOR[corridor]]


def line_height(avg_def_line_y: float) -> LineHeight:
    if avg_def_line_y >= LINE_HIGH_MIN:
        return "high"
    return "low" if avg_def_line_y < LINE_LOW_MAX else "mid"


def flip(x: float, y: float) -> tuple[float, float]:
    """Convert a point to the opponent's frame."""
    return 100.0 - x, 100.0 - y


def classify_shot_zone(x_def: float, y_def: float) -> XgaShotZone:
    """Classify a shot already in the DEFENDING team's frame into DESIGN.md §6 zones."""
    if y_def <= 5.2 and 36.5 <= x_def <= 63.5:
        return "six_yard"
    if y_def <= 15.7:
        if x_def < 36.5:
            return "box_left"
        if x_def <= 63.5:
            return "box_center"
        return "box_right"
    if y_def <= 26.0:
        if x_def < 36.5:
            return "edge_left"
        if x_def <= 63.5:
            return "edge_center"
        return "edge_right"
    return "long_range"


def shots_by_five_corridors(shots_against: Sequence[ShotPoint]) -> dict[ZoneCorridor, float]:
    """Aggregate opponent xGA across the 5 vertical corridors in the DEFENDING team's frame."""
    totals: dict[ZoneCorridor, float] = {c: 0.0 for c in ALL_CORRIDORS}
    for s in shots_against:
        x_def, _ = flip(s.x, s.y)
        xg = max(0.0, float(s.xg))
        totals[corridor_from_x(x_def)] += xg
    return {c: round(v, 3) for c, v in totals.items()}


def build_xga_zones(shots_against: Sequence[ShotPoint]) -> XgaZones:
    """Build `team_match_tactics.xga_zones_json` from opponent shots (shooting frame)."""
    zone_agg: dict[XgaShotZone, list[float | int]] = {z: [0.0, 0, 0] for z in ALL_SHOT_ZONES}
    corridor_xga = shots_by_five_corridors(shots_against)

    for s in shots_against:
        x_def, y_def = flip(s.x, s.y)
        xg = max(0.0, float(s.xg))
        zone = classify_shot_zone(x_def, y_def)
        zone_agg[zone][0] = float(zone_agg[zone][0]) + xg
        zone_agg[zone][1] = int(zone_agg[zone][1]) + 1
        if s.is_goal:
            zone_agg[zone][2] = int(zone_agg[zone][2]) + 1

    shot_zones = [
        XgaShotZoneValue(
            zone=z,
            xga=round(float(zone_agg[z][0]), 3),
            shots=int(zone_agg[z][1]),
            goals=int(zone_agg[z][2]),
        )
        for z in ALL_SHOT_ZONES
    ]
    # Map the 5 corridors cleanly into left (left + left_half), center, right (right_half + right)
    origin_corridors = OriginCorridors(
        left=round(corridor_xga["left"] + corridor_xga["left_half"], 3),
        center=round(corridor_xga["center"], 3),
        right=round(corridor_xga["right_half"] + corridor_xga["right"], 3),
    )
    return XgaZones(shot_zones=shot_zones, origin_corridors=origin_corridors)

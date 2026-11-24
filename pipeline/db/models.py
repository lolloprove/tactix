"""Write models for Supabase upserts — 1:1 with `supabase/migrations/*.sql`
and `src/types/tactics.ts`.

Identity `id` columns and the generated `confidence` columns are never sent.
Coordinates are 0-100 in the Tactix frame (x = width, y = length, from the
row team's perspective); adapters normalise provider coordinates first.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

MatchStatus = Literal["scheduled", "live", "finished", "postponed", "cancelled"]
PlayerPosition = Literal["GK", "CB", "LB", "RB", "LWB", "RWB", "DM", "CM", "AM", "LW", "RW", "ST"]
PlayerArchetype = Literal[
    "portiere_classico",
    "portiere_libero",
    "braccetto",
    "centrale_marcatore",
    "centrale_impostazione",
    "terzino_difensivo",
    "terzino_spinta",
    "terzino_invertito",
    "quinto",
    "regista",
    "mediano_incontrista",
    "mezzala",
    "box_to_box",
    "trequartista",
    "ala_dribblatrice",
    "ala_inversa",
    "prima_punta",
    "falso_nove",
    "attaccante_profondita",
    "seconda_punta",
]
ZoneCorridor = Literal["left", "left_half", "center", "right_half", "right"]
ConfidenceLevel = Literal["low", "medium", "high"]
TeamConditionType = Literal["vs_formation", "vs_back_line", "vs_high_line", "vs_archetype"]
PlayerConditionType = Literal[
    "vs_defender_archetype", "vs_attacker_archetype", "vs_line_height", "vs_formation"
]
BriefType = Literal["pre_match", "post_match"]
XgaShotZone = Literal[
    "six_yard",
    "box_left",
    "box_center",
    "box_right",
    "edge_left",
    "edge_center",
    "edge_right",
    "long_range",
]

Season = Annotated[str, Field(pattern=r"^\d{4}/\d{2}$")]
Formation = Annotated[str, Field(pattern=r"^\d(-\d){2,4}$")]
Pct = Annotated[float, Field(ge=0, le=100)]
Coord = Annotated[float, Field(ge=0, le=100)]
NonNeg = Annotated[int, Field(ge=0)]


class Row(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    def to_db(self) -> dict:
        return self.model_dump(mode="json")


# ---------------------------------------------------------------------------
# JSON column shapes
# ---------------------------------------------------------------------------


class SampleSize(Row):
    unit: Literal["minutes", "matches"]
    value: NonNeg


class RadarAxis(Row):
    key: str
    label: str
    percentile: Annotated[float, Field(ge=0, le=100)] | None


class XgaShotZoneValue(Row):
    zone: XgaShotZone
    xga: Annotated[float, Field(ge=0)]
    shots: NonNeg
    goals: NonNeg


class OriginCorridors(Row):
    left: Annotated[float, Field(ge=0)]
    center: Annotated[float, Field(ge=0)]
    right: Annotated[float, Field(ge=0)]


class XgaZones(Row):
    shot_zones: list[XgaShotZoneValue]
    origin_corridors: OriginCorridors


class DribbleZonePlayer(Row):
    player_id: int
    count: NonNeg


class DribbleZoneCell(Row):
    corridor: ZoneCorridor
    band: Literal[0, 1, 2]
    count: NonNeg
    players: list[DribbleZonePlayer]


class DribblesZones(Row):
    conceded: list[DribbleZoneCell]
    produced: list[DribbleZoneCell]
    total_conceded: NonNeg
    total_produced: NonNeg


class EvidenceTeamSplit(Row):
    table: Literal["team_conditional_splits"]
    team_id: int
    condition_type: TeamConditionType
    condition_value: str


class EvidencePlayerSplit(Row):
    table: Literal["player_conditional_splits"]
    player_id: int
    condition_type: PlayerConditionType
    condition_value: str


class EvidenceTeamMatch(Row):
    table: Literal["team_match_tactics"]
    match_id: int
    team_id: int


class EvidencePlayerMatch(Row):
    table: Literal["player_match_stats"]
    match_id: int
    player_id: int


EvidenceRef = Annotated[
    EvidenceTeamSplit | EvidencePlayerSplit | EvidenceTeamMatch | EvidencePlayerMatch,
    Field(discriminator="table"),
]


class MatchupDuelRow(Row):
    id: str
    player_a_id: int
    team_a_id: int
    player_b_id: int
    team_b_id: int
    zone: ZoneCorridor | None
    mismatch_score: Annotated[float, Field(ge=0, le=100)] | None
    advantage: Literal["a", "b"] | None
    sample: SampleSize
    confidence: ConfidenceLevel
    evidence: list[EvidenceRef] = []


class KeyEdge(Row):
    team_id: int
    against_team_id: int
    title: str
    rationale: str
    metric_key: str
    metric_value: float | None
    zone: ZoneCorridor | None
    player_ids: list[int]
    sample: SampleSize
    confidence: ConfidenceLevel
    evidence: EvidenceRef | None


class XFactor(Row):
    player_id: int
    team_id: int
    title: str
    rationale: str
    metric_key: str
    metric_value: float | None
    confidence: ConfidenceLevel


class PlayerObservation(Row):
    player_id: int
    team_id: int
    observation: str
    sentiment: Literal["positive", "negative", "neutral"]
    matchup_player_id: int | None
    metric_key: str | None
    metric_value: float | None


class Vulnerability(Row):
    key: str
    title: str
    description: str
    condition_type: TeamConditionType | None
    condition_value: str | None
    metric_key: str
    delta: float | None
    zone: ZoneCorridor | XgaShotZone | None
    severity: Literal[1, 2, 3]
    sample: SampleSize
    confidence: ConfidenceLevel


# ---------------------------------------------------------------------------
# Table upserts
# ---------------------------------------------------------------------------


class TeamUpsert(Row):
    name: str
    short_name: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    slug: Annotated[str, Field(pattern=r"^[a-z0-9-]+$")]
    understat_id: int | None = None
    fotmob_id: int | None = None
    sofascore_id: int | None = None
    logo_url: str | None = None


class PlayerUpsert(Row):
    team_id: int | None
    name: str
    primary_position: PlayerPosition
    archetype_primary: PlayerArchetype | None = None
    archetype_secondary: PlayerArchetype | None = None
    archetype_scores_json: dict[PlayerArchetype, Annotated[float, Field(ge=0, le=1)]] = {}
    radar_percentiles_json: list[RadarAxis] | None = None
    minutes_total: NonNeg = 0
    understat_id: int | None = None
    fotmob_id: int | None = None
    sofascore_id: int | None = None


class MatchUpsert(Row):
    season: Season
    round: Annotated[int, Field(ge=1, le=38)]
    kickoff_at: datetime
    home_team_id: int
    away_team_id: int
    home_goals: NonNeg | None = None
    away_goals: NonNeg | None = None
    home_xg: Annotated[float, Field(ge=0)] | None = None
    away_xg: Annotated[float, Field(ge=0)] | None = None
    status: MatchStatus = "scheduled"
    understat_id: int | None = None
    fotmob_id: int | None = None
    sofascore_id: int | None = None


class TeamMatchTacticsUpsert(Row):
    match_id: int
    team_id: int
    formation: Formation | None = None
    baseline_formation: Formation | None = None
    back_line_count: Literal[3, 4, 5] | None = None
    possession: Pct | None = None
    ppda: Annotated[float, Field(ge=0)] | None = None
    field_tilt: Pct | None = None
    avg_def_line_y: Coord | None = None
    attack_bias_left: Pct | None = None
    attack_bias_center: Pct | None = None
    attack_bias_right: Pct | None = None
    is_tactical_shift: bool = False
    shift_reason: str | None = None
    xga_zones_json: XgaZones | None = None
    dribbles_zones_json: DribblesZones | None = None


class PlayerMatchStatsUpsert(Row):
    match_id: int
    player_id: int
    team_id: int
    opponent_id: int
    position_played: PlayerPosition | None = None
    minutes: Annotated[int, Field(ge=0, le=130)]
    avg_x: Coord | None = None
    avg_y: Coord | None = None
    zone_corridor: ZoneCorridor | None = None
    dribbles_won: NonNeg | None = None
    dribbles_past: NonNeg | None = None
    duels_won: NonNeg | None = None
    duels_lost: NonNeg | None = None
    progressive_actions: NonNeg | None = None
    xg: Annotated[float, Field(ge=0)] | None = None
    xa: Annotated[float, Field(ge=0)] | None = None
    rating: Annotated[float, Field(ge=0, le=10)] | None = None


class TeamConditionalSplitUpsert(Row):
    team_id: int
    season: Season
    condition_type: TeamConditionType
    condition_value: str
    sample_matches: NonNeg
    xg_delta: float | None
    xga_delta: float | None
    dribbles_conceded_delta: float | None


class PlayerConditionalSplitUpsert(Row):
    player_id: int
    season: Season
    condition_type: PlayerConditionType
    condition_value: str
    sample_minutes: NonNeg
    rating_delta: float | None
    dribbles_delta: float | None
    duels_delta: float | None


class MatchAiBriefUpsert(Row):
    match_id: int
    brief_type: BriefType
    tactical_summary: str
    key_edges_json: list[KeyEdge]
    x_factors_json: list[XFactor]
    player_observations_json: list[PlayerObservation]
    matchups_json: list[MatchupDuelRow] = []
    model: str | None


class TeamHowToBeatUpsert(Row):
    team_id: int
    season: Season
    through_round: Annotated[int, Field(ge=1, le=38)] | None
    vulnerabilities_json: list[Vulnerability]
    ai_playbook_text: str | None

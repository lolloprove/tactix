/**
 * Tactix shared contracts — 1:1 with the Supabase schema
 * (`supabase/migrations/*.sql`, generated types in `./database.types.ts`).
 * Field names stay snake_case so rows from PostgREST need no mapping.
 * `./schema-alignment.ts` fails the type-check if these drift from the DB.
 *
 * Pitch coordinates are 0-100 from the perspective of the row's team:
 *   x = width  (0 left touchline → 100 right touchline, facing the attack)
 *   y = length (0 own goal line → 100 opponent goal line)
 *
 * Every delta is relative to the subject's own season baseline.
 * `null` means "Dati insufficienti" and must never be rendered as 0.
 */

// ---------------------------------------------------------------------------
// Enums (mirror Postgres enums)
// ---------------------------------------------------------------------------

export const MATCH_STATUSES = ["scheduled", "live", "finished", "postponed", "cancelled"] as const;
export type MatchStatus = (typeof MATCH_STATUSES)[number];

export const PLAYER_POSITIONS = [
  "GK", "CB", "LB", "RB", "LWB", "RWB", "DM", "CM", "AM", "LW", "RW", "ST",
] as const;
export type PlayerPosition = (typeof PLAYER_POSITIONS)[number];

export const PLAYER_ARCHETYPES = [
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
] as const;
export type PlayerArchetype = (typeof PLAYER_ARCHETYPES)[number];

/** Five equal vertical lanes on `x`: [0,20) [20,40) [40,60) [60,80) [80,100]. */
export const ZONE_CORRIDORS = ["left", "left_half", "center", "right_half", "right"] as const;
export type ZoneCorridor = (typeof ZONE_CORRIDORS)[number];

export const CONFIDENCE_LEVELS = ["low", "medium", "high"] as const;
export type ConfidenceLevel = (typeof CONFIDENCE_LEVELS)[number];

/** Mirrors the generated `confidence` columns. Reference only — never recompute in the UI. */
export const CONFIDENCE_THRESHOLDS = {
  minutes: { medium: 270, high: 540 },
  matches: { medium: 3, high: 6 },
} as const;

export const TEAM_CONDITION_TYPES = ["vs_formation", "vs_back_line", "vs_high_line", "vs_archetype"] as const;
export type TeamConditionType = (typeof TEAM_CONDITION_TYPES)[number];

export const PLAYER_CONDITION_TYPES = [
  "vs_defender_archetype",
  "vs_attacker_archetype",
  "vs_line_height",
  "vs_formation",
] as const;
export type PlayerConditionType = (typeof PLAYER_CONDITION_TYPES)[number];

export const BRIEF_TYPES = ["pre_match", "post_match"] as const;
export type BriefType = (typeof BRIEF_TYPES)[number];

// ---------------------------------------------------------------------------
// Scalars
// ---------------------------------------------------------------------------

/** e.g. "2026/27" — DB check `^\d{4}/\d{2}$`. */
export type Season = `${number}/${number}`;

/** ISO-8601 timestamp with offset, as returned by PostgREST for `timestamptz`. */
export type IsoDateTime = string;

/** e.g. "3-5-2", "4-2-3-1" — DB check `^\d(-\d){2,4}$`. */
export type Formation =
  | `${number}-${number}-${number}`
  | `${number}-${number}-${number}-${number}`
  | `${number}-${number}-${number}-${number}-${number}`;

export type BackLineCount = 3 | 4 | 5;

/** Bucket of the opponent's average defensive line (`avg_def_line_y`), set by the engine. */
export const LINE_HEIGHTS = ["high", "mid", "low"] as const;
export type LineHeight = (typeof LINE_HEIGHTS)[number];

export type SampleSize =
  | { unit: "minutes"; value: number }
  | { unit: "matches"; value: number };

// ---------------------------------------------------------------------------
// JSON column shapes
// ---------------------------------------------------------------------------

/** players.archetype_scores_json — similarity 0..1 to each archetype centroid. */
export type ArchetypeScores = Partial<Record<PlayerArchetype, number>>;

/** players.radar_percentiles_json[] — 6 role-tailored percentile axes (0..100). */
export type RadarAxis = {
  key: string;
  label: string;
  percentile: number;
};

/** Fixed shot-origin grid in the defending team's half (see DESIGN.md §6). */
export const XGA_SHOT_ZONES = [
  "six_yard",
  "box_left",
  "box_center",
  "box_right",
  "edge_left",
  "edge_center",
  "edge_right",
  "long_range",
] as const;
export type XgaShotZone = (typeof XGA_SHOT_ZONES)[number];

export type XgaShotZoneValue = {
  zone: XgaShotZone;
  xga: number;
  shots: number;
  goals: number;
};

/** team_match_tactics.xga_zones_json — left/right in the defending team's frame. */
export type XgaZones = {
  shot_zones: XgaShotZoneValue[];
  origin_corridors: { left: number; center: number; right: number };
};

/** Height band on the length axis (0 = own third, 1 = middle third, 2 = attacking third). */
export type DribbleZoneBand = 0 | 1 | 2;

export type DribbleZonePlayer = {
  player_id: number;
  count: number;
};

export type DribbleZoneCell = {
  corridor: ZoneCorridor;
  band: DribbleZoneBand;
  count: number;
  players: DribbleZonePlayer[];
};

/** team_match_tactics.dribbles_zones_json — 5 corridors × 3 height bands precomputed in Python. */
export type DribblesZones = {
  conceded: DribbleZoneCell[];
  produced: DribbleZoneCell[];
  total_conceded: number;
  total_produced: number;
};

/** Pointer to the aggregated row that justifies an AI claim. */
export type EvidenceRef =
  | { table: "team_conditional_splits"; team_id: number; condition_type: TeamConditionType; condition_value: string }
  | { table: "player_conditional_splits"; player_id: number; condition_type: PlayerConditionType; condition_value: string }
  | { table: "team_match_tactics"; match_id: number; team_id: number }
  | { table: "player_match_stats"; match_id: number; player_id: number };

/** match_ai_briefs.key_edges_json[] — an advantage for `team_id` over `against_team_id`. */
export type KeyEdge = {
  team_id: number;
  against_team_id: number;
  title: string;
  rationale: string;
  metric_key: string;
  metric_value: number | null;
  zone: ZoneCorridor | null;
  player_ids: number[];
  sample: SampleSize;
  confidence: ConfidenceLevel;
  evidence: EvidenceRef | null;
};

/** match_ai_briefs.x_factors_json[] */
export type XFactor = {
  player_id: number;
  team_id: number;
  title: string;
  rationale: string;
  metric_key: string;
  metric_value: number | null;
  confidence: ConfidenceLevel;
};

export type ObservationSentiment = "positive" | "negative" | "neutral";

/** match_ai_briefs.player_observations_json[] */
export type PlayerObservation = {
  player_id: number;
  team_id: number;
  observation: string;
  sentiment: ObservationSentiment;
  matchup_player_id: number | null;
  metric_key: string | null;
  metric_value: number | null;
};

/** match_ai_briefs.matchups_json[] — deterministic 1v1 duel mismatch row. */
export type MatchupDuelRow = {
  id: string;
  player_a_id: number;
  team_a_id: number;
  player_b_id: number;
  team_b_id: number;
  zone: ZoneCorridor;
  mismatch_score: number | null;
  advantage: "a" | "b" | null;
  sample: SampleSize;
  confidence: ConfidenceLevel;
  evidence: EvidenceRef[];
};

/** team_how_to_beat.vulnerabilities_json[] — weaknesses of the team the row belongs to. */
export type Vulnerability = {
  key: string;
  title: string;
  description: string;
  condition_type: TeamConditionType | null;
  condition_value: string | null;
  metric_key: string;
  delta: number | null;
  zone: ZoneCorridor | XgaShotZone | null;
  severity: 1 | 2 | 3;
  sample: SampleSize;
  confidence: ConfidenceLevel;
};

// ---------------------------------------------------------------------------
// Table rows
// ---------------------------------------------------------------------------

export type Team = {
  id: number;
  name: string;
  /** Three upper-case letters, e.g. "INT". */
  short_name: string;
  slug: string;
  understat_id: number | null;
  fotmob_id: number | null;
  sofascore_id: number | null;
  logo_url: string | null;
  updated_at: IsoDateTime;
};

export type Player = {
  id: number;
  team_id: number | null;
  name: string;
  primary_position: PlayerPosition;
  archetype_primary: PlayerArchetype | null;
  archetype_secondary: PlayerArchetype | null;
  archetype_scores_json: ArchetypeScores;
  radar_percentiles_json: RadarAxis[] | null;
  minutes_total: number;
  understat_id: number | null;
  fotmob_id: number | null;
  sofascore_id: number | null;
  updated_at: IsoDateTime;
};

export type Match = {
  id: number;
  season: Season;
  round: number;
  kickoff_at: IsoDateTime;
  home_team_id: number;
  away_team_id: number;
  home_goals: number | null;
  away_goals: number | null;
  home_xg: number | null;
  away_xg: number | null;
  status: MatchStatus;
  understat_id: number | null;
  fotmob_id: number | null;
  sofascore_id: number | null;
  updated_at: IsoDateTime;
};

export type TeamMatchTactics = {
  match_id: number;
  team_id: number;
  formation: Formation | null;
  baseline_formation: Formation | null;
  back_line_count: BackLineCount | null;
  /** 0-100 */
  possession: number | null;
  /** Opponent passes allowed per defensive action; lower = more aggressive press. */
  ppda: number | null;
  /** Share of final-third touches, 0-100. */
  field_tilt: number | null;
  /** 0-100 on the length axis. */
  avg_def_line_y: number | null;
  /** attack_bias_* sum to 100 (±1). */
  attack_bias_left: number | null;
  attack_bias_center: number | null;
  attack_bias_right: number | null;
  is_tactical_shift: boolean;
  /** Required when `is_tactical_shift` is true. */
  shift_reason: string | null;
  xga_zones_json: XgaZones | null;
  dribbles_zones_json: DribblesZones | null;
};

export type PlayerMatchStats = {
  match_id: number;
  player_id: number;
  team_id: number;
  opponent_id: number;
  position_played: PlayerPosition | null;
  minutes: number;
  avg_x: number | null;
  avg_y: number | null;
  zone_corridor: ZoneCorridor | null;
  dribbles_won: number | null;
  /** Times the player was dribbled past. */
  dribbles_past: number | null;
  duels_won: number | null;
  duels_lost: number | null;
  progressive_actions: number | null;
  xg: number | null;
  xa: number | null;
  /** 0-10 */
  rating: number | null;
};

type TeamConditionValueMap = {
  vs_formation: Formation;
  vs_back_line: `${BackLineCount}`;
  vs_high_line: LineHeight;
  vs_archetype: PlayerArchetype;
};

type TeamConditionalSplitBase = {
  id: number;
  team_id: number;
  season: Season;
  sample_matches: number;
  xg_delta: number | null;
  xga_delta: number | null;
  dribbles_conceded_delta: number | null;
  /** Generated in Postgres from `sample_matches`. */
  confidence: ConfidenceLevel;
  computed_at: IsoDateTime;
};

export type TeamConditionalSplit = {
  [K in TeamConditionType]: TeamConditionalSplitBase & {
    condition_type: K;
    condition_value: TeamConditionValueMap[K];
  };
}[TeamConditionType];

type PlayerConditionValueMap = {
  vs_defender_archetype: PlayerArchetype;
  vs_attacker_archetype: PlayerArchetype;
  vs_line_height: LineHeight;
  vs_formation: Formation;
};

type PlayerConditionalSplitBase = {
  id: number;
  player_id: number;
  season: Season;
  sample_minutes: number;
  rating_delta: number | null;
  dribbles_delta: number | null;
  duels_delta: number | null;
  /** Generated in Postgres from `sample_minutes`. */
  confidence: ConfidenceLevel;
  computed_at: IsoDateTime;
};

export type PlayerConditionalSplit = {
  [K in PlayerConditionType]: PlayerConditionalSplitBase & {
    condition_type: K;
    condition_value: PlayerConditionValueMap[K];
  };
}[PlayerConditionType];

export type MatchAiBrief = {
  id: number;
  match_id: number;
  brief_type: BriefType;
  tactical_summary: string;
  key_edges_json: KeyEdge[];
  x_factors_json: XFactor[];
  player_observations_json: PlayerObservation[];
  matchups_json: MatchupDuelRow[];
  model: string | null;
  generated_at: IsoDateTime;
};

export type TeamHowToBeat = {
  team_id: number;
  season: Season;
  through_round: number | null;
  updated_at: IsoDateTime;
  vulnerabilities_json: Vulnerability[];
  ai_playbook_text: string | null;
};

// ---------------------------------------------------------------------------
// Analytical SQL views
// ---------------------------------------------------------------------------

export type LeagueTacticalScatterRow = {
  team_id: number | null;
  team_name: string | null;
  short_name: string | null;
  slug: string | null;
  season: Season | null;
  matches_played: number | null;
  sample_matches: number | null;
  avg_def_line_y: number | null;
  avg_ppda: number | null;
  avg_possession: number | null;
  avg_field_tilt: number | null;
  points: number | null;
  expected_points: number | null;
  points_variance: number | null;
  goals_for: number | null;
  goals_against: number | null;
  xg_for: number | null;
  xg_against: number | null;
  goals_minus_xg: number | null;
  ga_minus_xga: number | null;
  confidence: ConfidenceLevel | null;
  league_avg_def_line_y: number | null;
  league_avg_ppda: number | null;
};

export type TeamShiftWindowRow = {
  team_id: number | null;
  season: Season | null;
  match_id: number | null;
  shift_round: number | null;
  formation: Formation | null;
  baseline_formation: Formation | null;
  shift_reason: string | null;
  before_from_round: number | null;
  before_to_round: number | null;
  before_matches: number | null;
  before_xg_diff: number | null;
  after_from_round: number | null;
  after_to_round: number | null;
  after_matches: number | null;
  after_xg_diff: number | null;
  xg_diff_delta: number | null;
  confidence: ConfidenceLevel | null;
};

// ---------------------------------------------------------------------------
// Read models (composed in the data layer, not tables)
// ---------------------------------------------------------------------------

export type MatchBundle = {
  match: Match;
  home: Team;
  away: Team;
  tactics: { home: TeamMatchTactics | null; away: TeamMatchTactics | null };
  player_stats: PlayerMatchStats[];
  briefs: { pre_match: MatchAiBrief | null; post_match: MatchAiBrief | null };
};

export type TeamProfile = {
  team: Team;
  players: Player[];
  splits: TeamConditionalSplit[];
  how_to_beat: TeamHowToBeat | null;
};

/**
 * FICTIONAL DEVELOPMENT DATA — not real statistics. For UI work only while the
 * pipeline is built; never import from production data paths.
 *
 * Serie A 2026/27, round 12 (two finished matches with full tactics, player
 * stats and post-match briefs) and round 13 (two scheduled matches with
 * pre-match briefs). Internally consistent: player xG sums to team xG, xGA zones
 * sum to the opponent's xG, attack biases sum to 100, `confidence` follows the
 * thresholds of the generated DB columns.
 */

import type {
  ArchetypeScores,
  MatchAiBrief,
  Match,
  MatchBundle,
  Player,
  PlayerArchetype,
  PlayerConditionalSplit,
  PlayerMatchStats,
  PlayerPosition,
  Team,
  TeamConditionalSplit,
  TeamHowToBeat,
  TeamMatchTactics,
  TeamProfile,
  ZoneCorridor,
} from "@/types/tactics";

export const MOCK_SEASON = "2026/27" as const;

const ETL_RUN = "2026-11-23T06:00:00+00:00";
const ENGINE_RUN = "2026-11-23T06:10:00+00:00";
const AI_RUN = "2026-11-23T06:30:00+00:00";

// ---------------------------------------------------------------------------
// Teams
// ---------------------------------------------------------------------------

const team = (id: number, name: string, short_name: string, slug: string): Team => ({
  id,
  name,
  short_name,
  slug,
  understat_id: null,
  fotmob_id: null,
  sofascore_id: null,
  logo_url: null,
  updated_at: ETL_RUN,
});

export const INTER = 1;
export const JUVENTUS = 2;
export const NAPOLI = 3;
export const MILAN = 4;

export const mockTeams: Team[] = [
  team(INTER, "Inter", "INT", "inter"),
  team(JUVENTUS, "Juventus", "JUV", "juventus"),
  team(NAPOLI, "Napoli", "NAP", "napoli"),
  team(MILAN, "Milan", "MIL", "milan"),
];

// ---------------------------------------------------------------------------
// Players — 11 per team (ids: team * 100 + n)
// ---------------------------------------------------------------------------

const player = (
  id: number,
  team_id: number,
  name: string,
  primary_position: PlayerPosition,
  archetype_primary: PlayerArchetype,
  archetype_secondary: PlayerArchetype | null,
  archetype_scores_json: ArchetypeScores,
  minutes_total: number,
): Player => ({
  id,
  team_id,
  name,
  primary_position,
  archetype_primary,
  archetype_secondary,
  archetype_scores_json,
  radar_percentiles_json: null,
  minutes_total,
  understat_id: null,
  fotmob_id: null,
  sofascore_id: null,
  updated_at: ETL_RUN,
});

export const mockPlayers: Player[] = [
  // Inter — 3-5-2
  player(101, INTER, "Yann Sommer", "GK", "portiere_classico", "portiere_libero", { portiere_classico: 0.81, portiere_libero: 0.63 }, 1080),
  player(102, INTER, "Benjamin Pavard", "CB", "braccetto", "centrale_impostazione", { braccetto: 0.84, centrale_impostazione: 0.66, terzino_difensivo: 0.41 }, 905),
  player(103, INTER, "Manuel Akanji", "CB", "centrale_impostazione", "centrale_marcatore", { centrale_impostazione: 0.86, centrale_marcatore: 0.69, braccetto: 0.52 }, 1010),
  player(104, INTER, "Alessandro Bastoni", "CB", "braccetto", "centrale_impostazione", { braccetto: 0.91, centrale_impostazione: 0.78, quinto: 0.33 }, 990),
  player(105, INTER, "Denzel Dumfries", "RWB", "quinto", "terzino_spinta", { quinto: 0.88, terzino_spinta: 0.72, ala_dribblatrice: 0.29 }, 870),
  player(106, INTER, "Nicolò Barella", "CM", "mezzala", "box_to_box", { mezzala: 0.89, box_to_box: 0.81, regista: 0.47 }, 1015),
  player(107, INTER, "Hakan Çalhanoğlu", "DM", "regista", "mezzala", { regista: 0.92, mezzala: 0.55, trequartista: 0.38 }, 860),
  player(108, INTER, "Petar Sučić", "CM", "mezzala", "box_to_box", { mezzala: 0.77, box_to_box: 0.7, regista: 0.51 }, 640),
  player(109, INTER, "Federico Dimarco", "LWB", "quinto", "terzino_spinta", { quinto: 0.9, terzino_spinta: 0.76, ala_inversa: 0.31 }, 940),
  player(110, INTER, "Lautaro Martínez", "ST", "seconda_punta", "attaccante_profondita", { seconda_punta: 0.87, attaccante_profondita: 0.74, falso_nove: 0.58 }, 1002),
  player(111, INTER, "Marcus Thuram", "ST", "prima_punta", "attaccante_profondita", { prima_punta: 0.83, attaccante_profondita: 0.79, ala_dribblatrice: 0.4 }, 925),

  // Juventus — baseline 4-2-3-1
  player(201, JUVENTUS, "Michele Di Gregorio", "GK", "portiere_libero", "portiere_classico", { portiere_libero: 0.74, portiere_classico: 0.7 }, 1080),
  player(202, JUVENTUS, "Pierre Kalulu", "CB", "braccetto", "terzino_difensivo", { braccetto: 0.79, terzino_difensivo: 0.71, centrale_marcatore: 0.6 }, 960),
  player(203, JUVENTUS, "Federico Gatti", "CB", "centrale_marcatore", "braccetto", { centrale_marcatore: 0.85, braccetto: 0.58 }, 870),
  player(204, JUVENTUS, "Gleison Bremer", "CB", "centrale_marcatore", "centrale_impostazione", { centrale_marcatore: 0.93, centrale_impostazione: 0.49 }, 1035),
  player(205, JUVENTUS, "Andrea Cambiaso", "LB", "terzino_invertito", "quinto", { terzino_invertito: 0.86, quinto: 0.74, mezzala: 0.45 }, 1001),
  player(206, JUVENTUS, "Manuel Locatelli", "DM", "regista", "mediano_incontrista", { regista: 0.84, mediano_incontrista: 0.63 }, 1060),
  player(207, JUVENTUS, "Khéphren Thuram", "CM", "box_to_box", "mezzala", { box_to_box: 0.88, mezzala: 0.71, mediano_incontrista: 0.55 }, 830),
  player(208, JUVENTUS, "Teun Koopmeiners", "AM", "trequartista", "mezzala", { trequartista: 0.76, mezzala: 0.74, box_to_box: 0.6 }, 720),
  player(209, JUVENTUS, "Francisco Conceição", "RW", "ala_dribblatrice", "ala_inversa", { ala_dribblatrice: 0.91, ala_inversa: 0.69, quinto: 0.22 }, 610),
  player(210, JUVENTUS, "Kenan Yıldız", "LW", "ala_inversa", "trequartista", { ala_inversa: 0.88, trequartista: 0.72, ala_dribblatrice: 0.7 }, 985),
  player(211, JUVENTUS, "Jonathan David", "ST", "attaccante_profondita", "seconda_punta", { attaccante_profondita: 0.84, seconda_punta: 0.73, prima_punta: 0.51 }, 890),

  // Napoli — 4-3-3
  player(301, NAPOLI, "Vanja Milinković-Savić", "GK", "portiere_libero", "portiere_classico", { portiere_libero: 0.79, portiere_classico: 0.68 }, 1080),
  player(302, NAPOLI, "Giovanni Di Lorenzo", "RB", "terzino_difensivo", "braccetto", { terzino_difensivo: 0.82, braccetto: 0.66, terzino_spinta: 0.54 }, 1080),
  player(303, NAPOLI, "Amir Rrahmani", "CB", "centrale_marcatore", "centrale_impostazione", { centrale_marcatore: 0.84, centrale_impostazione: 0.62 }, 990),
  player(304, NAPOLI, "Alessandro Buongiorno", "CB", "centrale_impostazione", "braccetto", { centrale_impostazione: 0.81, braccetto: 0.74, centrale_marcatore: 0.66 }, 900),
  player(305, NAPOLI, "Leonardo Spinazzola", "LB", "terzino_spinta", "quinto", { terzino_spinta: 0.85, quinto: 0.77, ala_dribblatrice: 0.36 }, 520),
  player(306, NAPOLI, "Stanislav Lobotka", "DM", "regista", null, { regista: 0.94, mezzala: 0.42 }, 1040),
  player(307, NAPOLI, "Scott McTominay", "CM", "box_to_box", "mezzala", { box_to_box: 0.86, mezzala: 0.82, seconda_punta: 0.47 }, 1012),
  player(308, NAPOLI, "Kevin De Bruyne", "AM", "trequartista", "mezzala", { trequartista: 0.9, mezzala: 0.79, regista: 0.56 }, 455),
  player(309, NAPOLI, "Matteo Politano", "RW", "ala_inversa", "quinto", { ala_inversa: 0.83, quinto: 0.61, terzino_spinta: 0.58 }, 880),
  player(310, NAPOLI, "Rasmus Højlund", "ST", "attaccante_profondita", "prima_punta", { attaccante_profondita: 0.85, prima_punta: 0.77 }, 905),
  player(311, NAPOLI, "David Neres", "LW", "ala_dribblatrice", "ala_inversa", { ala_dribblatrice: 0.89, ala_inversa: 0.71 }, 430),

  // Milan — 3-5-2
  player(401, MILAN, "Mike Maignan", "GK", "portiere_libero", "portiere_classico", { portiere_libero: 0.88, portiere_classico: 0.8 }, 1080),
  player(402, MILAN, "Fikayo Tomori", "CB", "braccetto", "centrale_marcatore", { braccetto: 0.8, centrale_marcatore: 0.72 }, 875),
  player(403, MILAN, "Matteo Gabbia", "CB", "centrale_marcatore", "centrale_impostazione", { centrale_marcatore: 0.82, centrale_impostazione: 0.64 }, 960),
  player(404, MILAN, "Strahinja Pavlović", "CB", "braccetto", "centrale_marcatore", { braccetto: 0.83, centrale_marcatore: 0.77 }, 945),
  player(405, MILAN, "Alexis Saelemaekers", "RWB", "quinto", "ala_inversa", { quinto: 0.84, ala_inversa: 0.66, terzino_spinta: 0.6 }, 990),
  player(406, MILAN, "Samuele Ricci", "DM", "regista", "mediano_incontrista", { regista: 0.87, mediano_incontrista: 0.64 }, 1000),
  player(407, MILAN, "Youssouf Fofana", "CM", "mediano_incontrista", "box_to_box", { mediano_incontrista: 0.84, box_to_box: 0.8 }, 880),
  player(408, MILAN, "Ruben Loftus-Cheek", "CM", "box_to_box", "trequartista", { box_to_box: 0.83, trequartista: 0.65, mezzala: 0.62 }, 700),
  player(409, MILAN, "Pervis Estupiñán", "LWB", "quinto", "terzino_spinta", { quinto: 0.81, terzino_spinta: 0.79 }, 780),
  player(410, MILAN, "Christian Pulisic", "RW", "seconda_punta", "ala_inversa", { seconda_punta: 0.82, ala_inversa: 0.8, trequartista: 0.63 }, 935),
  player(411, MILAN, "Rafael Leão", "LW", "attaccante_profondita", "ala_dribblatrice", { attaccante_profondita: 0.87, ala_dribblatrice: 0.85, seconda_punta: 0.52 }, 960),
];

// ---------------------------------------------------------------------------
// Matches
// ---------------------------------------------------------------------------

export const INT_JUV = 1201;
export const NAP_MIL = 1202;
export const JUV_NAP = 1301;
export const MIL_INT = 1302;

const match = (m: Pick<Match, "id" | "round" | "kickoff_at" | "home_team_id" | "away_team_id"> & Partial<Match>): Match => ({
  season: MOCK_SEASON,
  home_goals: null,
  away_goals: null,
  home_xg: null,
  away_xg: null,
  status: "scheduled",
  understat_id: null,
  fotmob_id: null,
  sofascore_id: null,
  updated_at: ETL_RUN,
  ...m,
});

export const mockMatches: Match[] = [
  match({ id: INT_JUV, round: 12, kickoff_at: "2026-11-22T19:45:00+00:00", home_team_id: INTER, away_team_id: JUVENTUS, home_goals: 2, away_goals: 1, home_xg: 2.14, away_xg: 0.87, status: "finished" }),
  match({ id: NAP_MIL, round: 12, kickoff_at: "2026-11-22T17:00:00+00:00", home_team_id: NAPOLI, away_team_id: MILAN, home_goals: 1, away_goals: 1, home_xg: 1.62, away_xg: 1.05, status: "finished" }),
  match({ id: MIL_INT, round: 13, kickoff_at: "2026-11-28T19:45:00+00:00", home_team_id: MILAN, away_team_id: INTER }),
  match({ id: JUV_NAP, round: 13, kickoff_at: "2026-11-29T19:45:00+00:00", home_team_id: JUVENTUS, away_team_id: NAPOLI }),
];

// ---------------------------------------------------------------------------
// Team match tactics (round 12)
// ---------------------------------------------------------------------------

export const mockTeamMatchTactics: TeamMatchTactics[] = [
  {
    match_id: INT_JUV,
    team_id: INTER,
    formation: "3-5-2",
    baseline_formation: "3-5-2",
    back_line_count: 3,
    possession: 58.4,
    ppda: 8.9,
    field_tilt: 64.2,
    avg_def_line_y: 46.5,
    attack_bias_left: 41,
    attack_bias_center: 22,
    attack_bias_right: 37,
    is_tactical_shift: false,
    shift_reason: null,
    xga_zones_json: {
      shot_zones: [
        { zone: "six_yard", xga: 0.32, shots: 1, goals: 1 },
        { zone: "box_left", xga: 0.08, shots: 1, goals: 0 },
        { zone: "box_center", xga: 0.29, shots: 3, goals: 0 },
        { zone: "box_right", xga: 0.06, shots: 1, goals: 0 },
        { zone: "edge_left", xga: 0.02, shots: 1, goals: 0 },
        { zone: "edge_center", xga: 0.08, shots: 3, goals: 0 },
        { zone: "edge_right", xga: 0.02, shots: 1, goals: 0 },
        { zone: "long_range", xga: 0, shots: 0, goals: 0 },
      ],
      origin_corridors: { left: 0.3, center: 0.38, right: 0.19 },
    },
    dribbles_zones_json: null,
  },
  {
    match_id: INT_JUV,
    team_id: JUVENTUS,
    formation: "3-4-2-1",
    baseline_formation: "4-2-3-1",
    back_line_count: 3,
    possession: 41.6,
    ppda: 13.8,
    field_tilt: 35.8,
    avg_def_line_y: 38.2,
    attack_bias_left: 33,
    attack_bias_center: 25,
    attack_bias_right: 42,
    is_tactical_shift: true,
    shift_reason:
      "Difesa a tre a specchio sul 3-5-2 dell'Inter: Kalulu braccetto destro, Conceição adattato a quinto destro, Cambiaso quinto sinistro.",
    xga_zones_json: {
      shot_zones: [
        { zone: "six_yard", xga: 0.58, shots: 2, goals: 1 },
        { zone: "box_left", xga: 0.18, shots: 2, goals: 0 },
        { zone: "box_center", xga: 0.92, shots: 5, goals: 1 },
        { zone: "box_right", xga: 0.31, shots: 2, goals: 0 },
        { zone: "edge_left", xga: 0.02, shots: 1, goals: 0 },
        { zone: "edge_center", xga: 0.09, shots: 3, goals: 0 },
        { zone: "edge_right", xga: 0.04, shots: 1, goals: 0 },
        { zone: "long_range", xga: 0, shots: 0, goals: 0 },
      ],
      origin_corridors: { left: 0.38, center: 0.55, right: 1.21 },
    },
    dribbles_zones_json: null,
  },
  {
    match_id: NAP_MIL,
    team_id: NAPOLI,
    formation: "4-3-3",
    baseline_formation: "4-3-3",
    back_line_count: 4,
    possession: 55.3,
    ppda: 9.6,
    field_tilt: 58.1,
    avg_def_line_y: 44.1,
    attack_bias_left: 34,
    attack_bias_center: 24,
    attack_bias_right: 42,
    is_tactical_shift: false,
    shift_reason: null,
    xga_zones_json: {
      shot_zones: [
        { zone: "six_yard", xga: 0.21, shots: 1, goals: 0 },
        { zone: "box_left", xga: 0.06, shots: 1, goals: 0 },
        { zone: "box_center", xga: 0.27, shots: 3, goals: 0 },
        { zone: "box_right", xga: 0.36, shots: 2, goals: 1 },
        { zone: "edge_left", xga: 0.02, shots: 1, goals: 0 },
        { zone: "edge_center", xga: 0.07, shots: 2, goals: 0 },
        { zone: "edge_right", xga: 0.06, shots: 2, goals: 0 },
        { zone: "long_range", xga: 0, shots: 0, goals: 0 },
      ],
      origin_corridors: { left: 0.17, center: 0.3, right: 0.58 },
    },
    dribbles_zones_json: null,
  },
  {
    match_id: NAP_MIL,
    team_id: MILAN,
    formation: "3-5-2",
    baseline_formation: "3-5-2",
    back_line_count: 3,
    possession: 44.7,
    ppda: 12.4,
    field_tilt: 41.9,
    avg_def_line_y: 40.3,
    attack_bias_left: 46,
    attack_bias_center: 20,
    attack_bias_right: 34,
    is_tactical_shift: false,
    shift_reason: null,
    xga_zones_json: {
      shot_zones: [
        { zone: "six_yard", xga: 0.44, shots: 2, goals: 0 },
        { zone: "box_left", xga: 0.29, shots: 2, goals: 0 },
        { zone: "box_center", xga: 0.63, shots: 4, goals: 1 },
        { zone: "box_right", xga: 0.11, shots: 1, goals: 0 },
        { zone: "edge_left", xga: 0.03, shots: 1, goals: 0 },
        { zone: "edge_center", xga: 0.09, shots: 3, goals: 0 },
        { zone: "edge_right", xga: 0.02, shots: 1, goals: 0 },
        { zone: "long_range", xga: 0.01, shots: 1, goals: 0 },
      ],
      origin_corridors: { left: 0.74, center: 0.51, right: 0.37 },
    },
    dribbles_zones_json: null,
  },
];

// ---------------------------------------------------------------------------
// Player match stats (round 12) — one row per starter
// ---------------------------------------------------------------------------

type StatLine = [
  player_id: number,
  position_played: PlayerPosition,
  minutes: number,
  avg_x: number,
  avg_y: number,
  zone_corridor: ZoneCorridor,
  dribbles_won: number,
  dribbles_past: number,
  duels_won: number,
  duels_lost: number,
  progressive_actions: number,
  xg: number,
  xa: number,
  rating: number,
];

const statLines = (match_id: number, team_id: number, opponent_id: number, lines: StatLine[]): PlayerMatchStats[] =>
  lines.map(([player_id, position_played, minutes, avg_x, avg_y, zone_corridor, dribbles_won, dribbles_past, duels_won, duels_lost, progressive_actions, xg, xa, rating]) => ({
    match_id,
    player_id,
    team_id,
    opponent_id,
    position_played,
    minutes,
    avg_x,
    avg_y,
    zone_corridor,
    dribbles_won,
    dribbles_past,
    duels_won,
    duels_lost,
    progressive_actions,
    xg,
    xa,
    rating,
  }));

export const mockPlayerMatchStats: PlayerMatchStats[] = [
  // Inter 2-1 Juventus — Inter (xG 2.14)
  ...statLines(INT_JUV, INTER, JUVENTUS, [
    //  id   pos    min  x   y   corridor      dw dp duw dul prog  xg    xa   rating
    [101, "GK", 90, 50, 6, "center", 0, 0, 1, 0, 2, 0, 0, 6.8],
    [102, "CB", 90, 70, 35, "right_half", 0, 1, 6, 2, 5, 0, 0, 7.0],
    [103, "CB", 90, 50, 32, "center", 0, 0, 5, 1, 8, 0.05, 0, 7.2],
    [104, "CB", 90, 30, 36, "left_half", 1, 0, 4, 2, 9, 0.06, 0.11, 7.4],
    [105, "RWB", 78, 87, 61, "right", 1, 1, 5, 4, 6, 0.18, 0.06, 6.9],
    [106, "CM", 90, 66, 57, "right_half", 2, 0, 7, 5, 10, 0.21, 0.24, 7.6],
    [107, "DM", 84, 50, 47, "center", 0, 1, 3, 3, 12, 0.14, 0.19, 7.3],
    [108, "CM", 71, 35, 55, "left_half", 1, 1, 4, 4, 6, 0.09, 0.05, 6.8],
    [109, "LWB", 90, 11, 63, "left", 3, 0, 6, 2, 11, 0.12, 0.48, 8.1],
    [110, "ST", 90, 56, 79, "center", 2, 0, 5, 6, 5, 0.71, 0.18, 8.0],
    [111, "ST", 82, 43, 80, "center", 1, 0, 9, 5, 4, 0.58, 0.12, 7.7],
  ]),
  // Inter 2-1 Juventus — Juventus (xG 0.87), shifted to 3-4-2-1
  ...statLines(INT_JUV, JUVENTUS, INTER, [
    [201, "GK", 90, 50, 7, "center", 0, 0, 0, 0, 1, 0, 0, 6.1],
    [202, "CB", 90, 72, 30, "right_half", 0, 1, 5, 3, 4, 0, 0, 6.4],
    [204, "CB", 90, 50, 28, "center", 0, 0, 8, 4, 3, 0, 0, 6.6],
    [203, "CB", 90, 29, 31, "left_half", 0, 0, 4, 3, 2, 0.06, 0, 6.5],
    [209, "RWB", 66, 85, 52, "right", 2, 4, 3, 7, 5, 0.04, 0.07, 5.6],
    [205, "LWB", 90, 14, 55, "left", 1, 1, 5, 3, 7, 0, 0.15, 6.7],
    [206, "DM", 90, 47, 44, "center", 0, 1, 4, 3, 8, 0, 0.08, 6.4],
    [207, "CM", 79, 58, 49, "center", 1, 1, 6, 6, 5, 0.06, 0.04, 6.3],
    [208, "AM", 90, 62, 66, "right_half", 0, 0, 3, 4, 4, 0.12, 0.21, 6.5],
    [210, "AM", 90, 33, 69, "left_half", 4, 0, 4, 5, 6, 0.18, 0.24, 7.1],
    [211, "ST", 90, 51, 81, "center", 1, 0, 3, 6, 2, 0.41, 0.05, 7.0],
  ]),
  // Napoli 1-1 Milan — Napoli (xG 1.62)
  ...statLines(NAP_MIL, NAPOLI, MILAN, [
    [301, "GK", 90, 50, 8, "center", 0, 0, 1, 0, 3, 0, 0, 6.6],
    [302, "RB", 90, 82, 38, "right", 0, 4, 4, 6, 5, 0.03, 0.04, 5.8],
    [303, "CB", 90, 62, 30, "right_half", 0, 1, 6, 2, 4, 0.07, 0, 6.7],
    [304, "CB", 90, 38, 31, "left_half", 0, 0, 5, 1, 7, 0, 0, 7.0],
    [305, "LB", 72, 16, 49, "left", 1, 1, 3, 2, 6, 0, 0.09, 6.6],
    [306, "DM", 90, 50, 46, "center", 1, 0, 5, 2, 11, 0, 0.12, 7.3],
    [307, "CM", 90, 60, 60, "right_half", 1, 1, 7, 5, 6, 0.38, 0.06, 7.4],
    [308, "CM", 76, 38, 62, "left_half", 1, 0, 2, 3, 9, 0.17, 0.41, 7.5],
    [309, "RW", 81, 86, 70, "right", 2, 1, 3, 4, 8, 0.21, 0.33, 7.2],
    [310, "ST", 90, 52, 80, "center", 0, 0, 6, 7, 2, 0.62, 0.08, 7.3],
    [311, "LW", 64, 13, 72, "left", 3, 1, 2, 4, 5, 0.14, 0.1, 6.7],
  ]),
  // Napoli 1-1 Milan — Milan (xG 1.05)
  ...statLines(NAP_MIL, MILAN, NAPOLI, [
    [401, "GK", 90, 50, 7, "center", 0, 0, 1, 0, 2, 0, 0, 7.4],
    [402, "CB", 90, 70, 33, "right_half", 0, 1, 5, 3, 4, 0, 0, 6.6],
    [403, "CB", 90, 50, 30, "center", 0, 0, 7, 2, 3, 0.09, 0, 6.9],
    [404, "CB", 90, 30, 33, "left_half", 0, 2, 4, 4, 3, 0, 0, 6.2],
    [405, "RWB", 90, 86, 56, "right", 1, 1, 4, 3, 6, 0.06, 0.08, 6.6],
    [406, "DM", 90, 49, 45, "center", 0, 1, 3, 4, 7, 0, 0.06, 6.4],
    [407, "CM", 85, 63, 50, "right_half", 0, 0, 7, 3, 4, 0.07, 0, 6.7],
    [408, "CM", 74, 38, 56, "left_half", 1, 0, 4, 4, 5, 0.18, 0.11, 6.6],
    [409, "LWB", 90, 13, 52, "left", 0, 3, 3, 5, 5, 0, 0.07, 5.9],
    [410, "ST", 82, 57, 74, "center", 2, 0, 3, 4, 6, 0.29, 0.28, 7.2],
    [411, "ST", 90, 33, 76, "left_half", 5, 0, 4, 3, 9, 0.36, 0.21, 7.8],
  ]),
];

// ---------------------------------------------------------------------------
// Conditional splits (season to date, through round 12)
// ---------------------------------------------------------------------------

const splitMeta = { season: MOCK_SEASON, computed_at: ENGINE_RUN } as const;

export const mockTeamConditionalSplits: TeamConditionalSplit[] = [
  { ...splitMeta, id: 1, team_id: INTER, condition_type: "vs_formation", condition_value: "3-5-2", sample_matches: 3, xg_delta: -0.41, xga_delta: 0.12, dribbles_conceded_delta: 0.4, confidence: "medium" },
  { ...splitMeta, id: 2, team_id: INTER, condition_type: "vs_back_line", condition_value: "4", sample_matches: 8, xg_delta: 0.28, xga_delta: -0.15, dribbles_conceded_delta: -0.3, confidence: "high" },
  { ...splitMeta, id: 3, team_id: INTER, condition_type: "vs_high_line", condition_value: "high", sample_matches: 4, xg_delta: 0.52, xga_delta: 0.08, dribbles_conceded_delta: 0.1, confidence: "medium" },
  { ...splitMeta, id: 4, team_id: INTER, condition_type: "vs_archetype", condition_value: "attaccante_profondita", sample_matches: 6, xg_delta: 0.05, xga_delta: 0.34, dribbles_conceded_delta: 0.9, confidence: "medium" },

  { ...splitMeta, id: 5, team_id: JUVENTUS, condition_type: "vs_formation", condition_value: "3-5-2", sample_matches: 2, xg_delta: -0.38, xga_delta: 0.44, dribbles_conceded_delta: 0.7, confidence: "low" },
  { ...splitMeta, id: 6, team_id: JUVENTUS, condition_type: "vs_back_line", condition_value: "3", sample_matches: 4, xg_delta: -0.31, xga_delta: 0.29, dribbles_conceded_delta: 1.1, confidence: "medium" },
  { ...splitMeta, id: 7, team_id: JUVENTUS, condition_type: "vs_high_line", condition_value: "high", sample_matches: 5, xg_delta: 0.18, xga_delta: 0.05, dribbles_conceded_delta: 0.2, confidence: "medium" },
  { ...splitMeta, id: 8, team_id: JUVENTUS, condition_type: "vs_archetype", condition_value: "quinto", sample_matches: 4, xg_delta: -0.12, xga_delta: 0.36, dribbles_conceded_delta: 1.3, confidence: "medium" },
  { ...splitMeta, id: 9, team_id: JUVENTUS, condition_type: "vs_formation", condition_value: "4-3-3", sample_matches: 4, xg_delta: -0.22, xga_delta: 0.19, dribbles_conceded_delta: 0.4, confidence: "medium" },

  { ...splitMeta, id: 10, team_id: NAPOLI, condition_type: "vs_formation", condition_value: "3-5-2", sample_matches: 6, xg_delta: -0.12, xga_delta: 0.31, dribbles_conceded_delta: 0.5, confidence: "medium" },
  { ...splitMeta, id: 11, team_id: NAPOLI, condition_type: "vs_back_line", condition_value: "4", sample_matches: 6, xg_delta: 0.21, xga_delta: -0.18, dribbles_conceded_delta: -0.4, confidence: "medium" },
  { ...splitMeta, id: 12, team_id: NAPOLI, condition_type: "vs_high_line", condition_value: "high", sample_matches: 3, xg_delta: 0.47, xga_delta: 0.06, dribbles_conceded_delta: 0, confidence: "medium" },
  { ...splitMeta, id: 13, team_id: NAPOLI, condition_type: "vs_archetype", condition_value: "ala_dribblatrice", sample_matches: 7, xg_delta: 0.02, xga_delta: 0.27, dribbles_conceded_delta: 1.6, confidence: "high" },

  { ...splitMeta, id: 14, team_id: MILAN, condition_type: "vs_formation", condition_value: "4-3-3", sample_matches: 5, xg_delta: 0.22, xga_delta: 0.35, dribbles_conceded_delta: 0.8, confidence: "medium" },
  { ...splitMeta, id: 15, team_id: MILAN, condition_type: "vs_back_line", condition_value: "3", sample_matches: 5, xg_delta: -0.29, xga_delta: -0.04, dribbles_conceded_delta: -0.2, confidence: "medium" },
  { ...splitMeta, id: 16, team_id: MILAN, condition_type: "vs_high_line", condition_value: "low", sample_matches: 4, xg_delta: -0.44, xga_delta: -0.1, dribbles_conceded_delta: -0.3, confidence: "medium" },
  { ...splitMeta, id: 17, team_id: MILAN, condition_type: "vs_archetype", condition_value: "seconda_punta", sample_matches: 6, xg_delta: 0.03, xga_delta: 0.38, dribbles_conceded_delta: 0.5, confidence: "medium" },
  // "Dati insufficienti" case
  { ...splitMeta, id: 18, team_id: MILAN, condition_type: "vs_formation", condition_value: "4-2-3-1", sample_matches: 1, xg_delta: null, xga_delta: null, dribbles_conceded_delta: null, confidence: "low" },
];

/** For defenders (`vs_attacker_archetype`) `dribbles_delta` counts times dribbled past: positive is bad. */
export const mockPlayerConditionalSplits: PlayerConditionalSplit[] = [
  { ...splitMeta, id: 1, player_id: 302, condition_type: "vs_attacker_archetype", condition_value: "ala_dribblatrice", sample_minutes: 312, rating_delta: -0.62, dribbles_delta: 1.8, duels_delta: -2.1, confidence: "medium" },
  { ...splitMeta, id: 2, player_id: 411, condition_type: "vs_defender_archetype", condition_value: "terzino_difensivo", sample_minutes: 640, rating_delta: 0.48, dribbles_delta: 1.35, duels_delta: 1.2, confidence: "high" },
  { ...splitMeta, id: 3, player_id: 204, condition_type: "vs_attacker_archetype", condition_value: "prima_punta", sample_minutes: 720, rating_delta: 0.31, dribbles_delta: -0.4, duels_delta: 1.9, confidence: "high" },
  { ...splitMeta, id: 4, player_id: 110, condition_type: "vs_line_height", condition_value: "high", sample_minutes: 560, rating_delta: 0.55, dribbles_delta: 0.2, duels_delta: 0.6, confidence: "high" },
  { ...splitMeta, id: 5, player_id: 310, condition_type: "vs_line_height", condition_value: "high", sample_minutes: 410, rating_delta: 0.42, dribbles_delta: 0.1, duels_delta: 0.8, confidence: "medium" },
  { ...splitMeta, id: 6, player_id: 106, condition_type: "vs_formation", condition_value: "4-3-3", sample_minutes: 270, rating_delta: 0.2, dribbles_delta: 0.3, duels_delta: 0.7, confidence: "medium" },
  { ...splitMeta, id: 7, player_id: 306, condition_type: "vs_formation", condition_value: "3-5-2", sample_minutes: 450, rating_delta: -0.35, dribbles_delta: -0.1, duels_delta: -1.1, confidence: "medium" },
  { ...splitMeta, id: 8, player_id: 203, condition_type: "vs_attacker_archetype", condition_value: "seconda_punta", sample_minutes: 380, rating_delta: -0.41, dribbles_delta: 0.9, duels_delta: -0.9, confidence: "medium" },
  { ...splitMeta, id: 9, player_id: 402, condition_type: "vs_attacker_archetype", condition_value: "prima_punta", sample_minutes: 290, rating_delta: -0.28, dribbles_delta: 0.3, duels_delta: -1.4, confidence: "medium" },
  { ...splitMeta, id: 10, player_id: 210, condition_type: "vs_defender_archetype", condition_value: "terzino_difensivo", sample_minutes: 600, rating_delta: 0.29, dribbles_delta: 0.9, duels_delta: 0.4, confidence: "high" },
  { ...splitMeta, id: 11, player_id: 308, condition_type: "vs_line_height", condition_value: "high", sample_minutes: 230, rating_delta: 0.6, dribbles_delta: 0.2, duels_delta: 0.3, confidence: "low" },
  { ...splitMeta, id: 12, player_id: 305, condition_type: "vs_attacker_archetype", condition_value: "ala_dribblatrice", sample_minutes: 260, rating_delta: -0.5, dribbles_delta: 1.6, duels_delta: -0.8, confidence: "low" },
  // "Dati insufficienti" case
  { ...splitMeta, id: 13, player_id: 202, condition_type: "vs_attacker_archetype", condition_value: "attaccante_profondita", sample_minutes: 45, rating_delta: null, dribbles_delta: null, duels_delta: null, confidence: "low" },
  { ...splitMeta, id: 14, player_id: 109, condition_type: "vs_defender_archetype", condition_value: "ala_dribblatrice", sample_minutes: 330, rating_delta: 0.44, dribbles_delta: 0.8, duels_delta: 0.9, confidence: "medium" },
  { ...splitMeta, id: 15, player_id: 111, condition_type: "vs_defender_archetype", condition_value: "braccetto", sample_minutes: 585, rating_delta: 0.37, dribbles_delta: 0.2, duels_delta: 1.5, confidence: "high" },
  { ...splitMeta, id: 16, player_id: 209, condition_type: "vs_attacker_archetype", condition_value: "quinto", sample_minutes: 95, rating_delta: -0.9, dribbles_delta: 2.6, duels_delta: -2.4, confidence: "low" },
  { ...splitMeta, id: 17, player_id: 102, condition_type: "vs_attacker_archetype", condition_value: "attaccante_profondita", sample_minutes: 410, rating_delta: -0.33, dribbles_delta: 0.7, duels_delta: -0.6, confidence: "medium" },
  { ...splitMeta, id: 18, player_id: 406, condition_type: "vs_formation", condition_value: "3-5-2", sample_minutes: 360, rating_delta: -0.24, dribbles_delta: -0.1, duels_delta: -0.8, confidence: "medium" },
];

// ---------------------------------------------------------------------------
// AI briefs — post-match for round 12, pre-match for round 13
// ---------------------------------------------------------------------------

const AI_MODEL = "gemini-2.5-flash";

export const mockMatchAiBriefs: MatchAiBrief[] = [
  {
    id: 1,
    match_id: INT_JUV,
    brief_type: "post_match",
    tactical_summary:
      "L'Inter ha vinto sul corridoio sinistro. La Juventus ha abbandonato il 4-2-3-1 per specchiarsi a tre, adattando Conceição a quinto destro: Dimarco lo ha saltato 3 volte e ha prodotto 0.48 xA, e il lato destro bianconero ha concesso 1.21 dei 2.14 xGA totali. Senza palla l'Inter ha pressato alto (PPDA 8.9) e ha schiacciato la Juventus al 35.8% di field tilt.",
    key_edges_json: [
      {
        team_id: INTER,
        against_team_id: JUVENTUS,
        title: "Dimarco contro un'ala adattata a quinto",
        rationale:
          "Dimarco rende +0.44 di rating contro difensori di fascia con profilo da ala dribblatrice; Conceição, 66′ da quinto, è stato saltato 4 volte con 7 duelli persi.",
        metric_key: "rating_delta",
        metric_value: 0.44,
        zone: "left",
        player_ids: [109, 104, 209],
        sample: { unit: "minutes", value: 330 },
        confidence: "medium",
        evidence: { table: "player_conditional_splits", player_id: 109, condition_type: "vs_defender_archetype", condition_value: "ala_dribblatrice" },
      },
      {
        team_id: INTER,
        against_team_id: JUVENTUS,
        title: "La Juventus soffre le difese a tre",
        rationale: "Contro linee a tre la Juventus concede +0.29 xGA rispetto alla sua media stagionale.",
        metric_key: "xga_delta",
        metric_value: 0.29,
        zone: null,
        player_ids: [],
        sample: { unit: "matches", value: 4 },
        confidence: "medium",
        evidence: { table: "team_conditional_splits", team_id: JUVENTUS, condition_type: "vs_back_line", condition_value: "3" },
      },
    ],
    x_factors_json: [
      { player_id: 109, team_id: INTER, title: "Fonte primaria di rifinitura", rationale: "0.48 xA e 11 azioni progressive dal corridoio sinistro.", metric_key: "xa", metric_value: 0.48, confidence: "low" },
      { player_id: 110, team_id: INTER, title: "Volume in area", rationale: "0.71 xG, il valore più alto della partita.", metric_key: "xg", metric_value: 0.71, confidence: "low" },
    ],
    player_observations_json: [
      { player_id: 209, team_id: JUVENTUS, observation: "Fuori ruolo da quinto: 4 volte saltato e 7 duelli persi prima della sostituzione al 66′.", sentiment: "negative", matchup_player_id: 109, metric_key: "dribbles_past", metric_value: 4 },
      { player_id: 204, team_id: JUVENTUS, observation: "Ha retto il duello fisico con Thuram: 8 duelli vinti su 12.", sentiment: "positive", matchup_player_id: 111, metric_key: "duels_won", metric_value: 8 },
      { player_id: 210, team_id: JUVENTUS, observation: "Unica fonte di progressione bianconera: 4 dribbling riusciti e 0.24 xA.", sentiment: "positive", matchup_player_id: 102, metric_key: "dribbles_won", metric_value: 4 },
      { player_id: 107, team_id: INTER, observation: "Regia pulita sotto pressione: 12 azioni progressive, massimo della partita.", sentiment: "positive", matchup_player_id: null, metric_key: "progressive_actions", metric_value: 12 },
    ],
    matchups_json: [],
    model: AI_MODEL,
    generated_at: AI_RUN,
  },
  {
    id: 2,
    match_id: NAP_MIL,
    brief_type: "post_match",
    tactical_summary:
      "Pareggio costruito su due fasce speculari. Il Napoli ha spinto a destra (42% delle azioni), dove Politano ha saltato Estupiñán 3 volte: 0.74 xGA concessi dal Milan sul proprio lato sinistro. Il Milan ha risposto con Leão, che partendo dal mezzo spazio sinistro ha battuto Di Lorenzo 4 volte: il Napoli ha concesso 0.58 xGA sulla propria destra. Maignan ha tenuto il Milan in partita contro 1.62 xG.",
    key_edges_json: [
      {
        team_id: MILAN,
        against_team_id: NAPOLI,
        title: "Leão contro terzini bloccati",
        rationale: "Contro terzini difensivi Leão sale di +0.48 di rating e +1.35 dribbling/90; Di Lorenzo è stato saltato 4 volte.",
        metric_key: "rating_delta",
        metric_value: 0.48,
        zone: "left_half",
        player_ids: [411, 302],
        sample: { unit: "minutes", value: 640 },
        confidence: "high",
        evidence: { table: "player_conditional_splits", player_id: 411, condition_type: "vs_defender_archetype", condition_value: "terzino_difensivo" },
      },
      {
        team_id: NAPOLI,
        against_team_id: MILAN,
        title: "Il 4-3-3 sovraccarica Ricci",
        rationale: "Contro il 4-3-3 il Milan concede +0.35 xGA: le mezzali avversarie attaccano i lati del regista.",
        metric_key: "xga_delta",
        metric_value: 0.35,
        zone: null,
        player_ids: [307, 308, 406],
        sample: { unit: "matches", value: 5 },
        confidence: "medium",
        evidence: { table: "team_conditional_splits", team_id: MILAN, condition_type: "vs_formation", condition_value: "4-3-3" },
      },
    ],
    x_factors_json: [
      { player_id: 411, team_id: MILAN, title: "Duello decisivo sulla fascia", rationale: "5 dribbling riusciti e 0.36 xG partendo da sinistra.", metric_key: "dribbles_won", metric_value: 5, confidence: "high" },
      { player_id: 308, team_id: NAPOLI, title: "Rifinitura dal mezzo spazio", rationale: "0.41 xA in 76′ da mezzala sinistra.", metric_key: "xa", metric_value: 0.41, confidence: "low" },
    ],
    player_observations_json: [
      { player_id: 302, team_id: NAPOLI, observation: "In difficoltà nell'uno contro uno: 4 volte saltato e 6 duelli persi.", sentiment: "negative", matchup_player_id: 411, metric_key: "dribbles_past", metric_value: 4 },
      { player_id: 409, team_id: MILAN, observation: "Esposto alle rotazioni Politano–McTominay: 3 volte saltato.", sentiment: "negative", matchup_player_id: 309, metric_key: "dribbles_past", metric_value: 3 },
      { player_id: 306, team_id: NAPOLI, observation: "Metronomo: 11 azioni progressive e nessun dribbling subito.", sentiment: "positive", matchup_player_id: 410, metric_key: "progressive_actions", metric_value: 11 },
      { player_id: 401, team_id: MILAN, observation: "Ha tenuto il Milan a galla: un solo gol concesso su 1.62 xGA.", sentiment: "positive", matchup_player_id: null, metric_key: "rating", metric_value: 7.4 },
    ],
    matchups_json: [],
    model: AI_MODEL,
    generated_at: AI_RUN,
  },
  {
    id: 3,
    match_id: MIL_INT,
    brief_type: "pre_match",
    tactical_summary:
      "Derby tra due 3-5-2, il contesto peggiore della stagione per l'Inter: −0.41 xG contro moduli speculari (3 partite). L'edge nerazzurro passa tra le linee: il Milan concede +0.38 xGA contro le seconde punte e Lautaro è l'archetipo esatto. Il pericolo rossonero è la profondità: l'Inter concede +0.34 xGA contro attaccanti di profondità, e Leão attacca il lato di Pavard.",
    key_edges_json: [
      {
        team_id: INTER,
        against_team_id: MILAN,
        title: "Lautaro tra le linee",
        rationale: "Il Milan concede +0.38 xGA contro seconde punte; Lautaro sale di +0.55 di rating contro linee alte.",
        metric_key: "xga_delta",
        metric_value: 0.38,
        zone: "center",
        player_ids: [110, 406],
        sample: { unit: "matches", value: 6 },
        confidence: "medium",
        evidence: { table: "team_conditional_splits", team_id: MILAN, condition_type: "vs_archetype", condition_value: "seconda_punta" },
      },
      {
        team_id: INTER,
        against_team_id: MILAN,
        title: "Thuram contro Tomori",
        rationale: "Thuram vince +1.5 duelli/90 contro i braccetti; Tomori ne perde 1.4 in più contro le prime punte.",
        metric_key: "duels_delta",
        metric_value: 1.5,
        zone: "left_half",
        player_ids: [111, 402],
        sample: { unit: "minutes", value: 585 },
        confidence: "high",
        evidence: { table: "player_conditional_splits", player_id: 111, condition_type: "vs_defender_archetype", condition_value: "braccetto" },
      },
      {
        team_id: MILAN,
        against_team_id: INTER,
        title: "Leão alle spalle di Pavard",
        rationale: "L'Inter concede +0.34 xGA e +0.9 dribbling/90 contro attaccanti di profondità; Pavard perde 0.33 di rating contro questo profilo.",
        metric_key: "xga_delta",
        metric_value: 0.34,
        zone: "left_half",
        player_ids: [411, 102],
        sample: { unit: "matches", value: 6 },
        confidence: "medium",
        evidence: { table: "team_conditional_splits", team_id: INTER, condition_type: "vs_archetype", condition_value: "attaccante_profondita" },
      },
    ],
    x_factors_json: [
      { player_id: 110, team_id: INTER, title: "Ricezione alle spalle di Ricci", rationale: "Archetipo seconda punta contro la debolezza principale del Milan.", metric_key: "rating_delta", metric_value: 0.55, confidence: "high" },
      { player_id: 411, team_id: MILAN, title: "Profondità sul centro-destra nerazzurro", rationale: "+1.35 dribbling/90 contro difensori bloccati.", metric_key: "dribbles_delta", metric_value: 1.35, confidence: "high" },
      { player_id: 111, team_id: INTER, title: "Duelli aerei e spalle alla porta", rationale: "+1.5 duelli vinti/90 contro i braccetti.", metric_key: "duels_delta", metric_value: 1.5, confidence: "high" },
    ],
    player_observations_json: [
      { player_id: 102, team_id: INTER, observation: "Matchup più esposto: −0.33 di rating contro attaccanti di profondità.", sentiment: "negative", matchup_player_id: 411, metric_key: "rating_delta", metric_value: -0.33 },
      { player_id: 402, team_id: MILAN, observation: "Contro le prime punte perde 1.4 duelli/90 in più della sua media.", sentiment: "negative", matchup_player_id: 111, metric_key: "duels_delta", metric_value: -1.4 },
      { player_id: 406, team_id: MILAN, observation: "Contro il 3-5-2 il rating scende di 0.24: accerchiato da Barella e Sučić.", sentiment: "negative", matchup_player_id: 106, metric_key: "rating_delta", metric_value: -0.24 },
    ],
    matchups_json: [],
    model: AI_MODEL,
    generated_at: AI_RUN,
  },
  {
    id: 4,
    match_id: JUV_NAP,
    brief_type: "pre_match",
    tactical_summary:
      "La Juventus dovrebbe tornare al 4-2-3-1 di base dopo l'esperimento a tre contro l'Inter. Contro il 4-3-3 i bianconeri concedono +0.19 xGA (4 partite), ma hanno l'edge più solido sulle fasce: il Napoli concede +0.27 xGA contro ali dribblatrici (7 partite) e Yıldız rende +0.29 di rating contro terzini difensivi come Di Lorenzo. Conceição contro Spinazzola è un matchup promettente ma con campione ridotto.",
    key_edges_json: [
      {
        team_id: JUVENTUS,
        against_team_id: NAPOLI,
        title: "Yıldız contro Di Lorenzo",
        rationale: "Il Napoli concede +0.27 xGA e +1.6 dribbling/90 contro ali dribblatrici; Yıldız sale di +0.29 contro terzini difensivi.",
        metric_key: "xga_delta",
        metric_value: 0.27,
        zone: "left_half",
        player_ids: [210, 302],
        sample: { unit: "matches", value: 7 },
        confidence: "high",
        evidence: { table: "team_conditional_splits", team_id: NAPOLI, condition_type: "vs_archetype", condition_value: "ala_dribblatrice" },
      },
      {
        team_id: NAPOLI,
        against_team_id: JUVENTUS,
        title: "Mezzali contro il doppio pivot",
        rationale: "Contro il 4-3-3 la Juventus concede +0.19 xGA: McTominay e De Bruyne attaccano gli spazi ai lati di Locatelli.",
        metric_key: "xga_delta",
        metric_value: 0.19,
        zone: null,
        player_ids: [307, 308, 206],
        sample: { unit: "matches", value: 4 },
        confidence: "medium",
        evidence: { table: "team_conditional_splits", team_id: JUVENTUS, condition_type: "vs_formation", condition_value: "4-3-3" },
      },
      {
        team_id: JUVENTUS,
        against_team_id: NAPOLI,
        title: "Conceição contro Spinazzola",
        rationale: "Spinazzola subisce +1.6 dribbling/90 contro ali dribblatrici, ma su soli 260′.",
        metric_key: "dribbles_delta",
        metric_value: 1.6,
        zone: "right",
        player_ids: [209, 305],
        sample: { unit: "minutes", value: 260 },
        confidence: "low",
        evidence: { table: "player_conditional_splits", player_id: 305, condition_type: "vs_attacker_archetype", condition_value: "ala_dribblatrice" },
      },
    ],
    x_factors_json: [
      { player_id: 210, team_id: JUVENTUS, title: "Isolamenti a sinistra", rationale: "+0.9 dribbling/90 contro terzini difensivi.", metric_key: "dribbles_delta", metric_value: 0.9, confidence: "high" },
      { player_id: 307, team_id: NAPOLI, title: "Inserimenti senza palla", rationale: "0.38 xG nell'ultima partita da mezzala destra.", metric_key: "xg", metric_value: 0.38, confidence: "low" },
      { player_id: 204, team_id: JUVENTUS, title: "Argine su Højlund", rationale: "+1.9 duelli vinti/90 contro le prime punte.", metric_key: "duels_delta", metric_value: 1.9, confidence: "high" },
    ],
    player_observations_json: [
      { player_id: 302, team_id: NAPOLI, observation: "Contro ali dribblatrici il rating scende di 0.62 e subisce +1.8 dribbling/90.", sentiment: "negative", matchup_player_id: 210, metric_key: "rating_delta", metric_value: -0.62 },
      { player_id: 204, team_id: JUVENTUS, observation: "Profilo ideale contro un attaccante fisico: +0.31 di rating contro le prime punte.", sentiment: "positive", matchup_player_id: 310, metric_key: "rating_delta", metric_value: 0.31 },
      { player_id: 306, team_id: NAPOLI, observation: "Contro un 4-2-3-1 riceve tra Koopmeiners e David: nessun campione condizionato sufficiente.", sentiment: "neutral", matchup_player_id: 208, metric_key: null, metric_value: null },
    ],
    matchups_json: [],
    model: AI_MODEL,
    generated_at: AI_RUN,
  },
];

// ---------------------------------------------------------------------------
// How to beat
// ---------------------------------------------------------------------------

const howToBeatMeta = { season: MOCK_SEASON, through_round: 12, updated_at: AI_RUN } as const;

export const mockTeamHowToBeat: TeamHowToBeat[] = [
  {
    ...howToBeatMeta,
    team_id: INTER,
    vulnerabilities_json: [
      { key: "space_behind_braccetti", title: "Profondità alle spalle dei braccetti", description: "Gli attaccanti di profondità attaccano lo spazio lasciato da Pavard e Bastoni quando accompagnano l'azione.", condition_type: "vs_archetype", condition_value: "attaccante_profondita", metric_key: "xga_delta", delta: 0.34, zone: "right_half", severity: 3, sample: { unit: "matches", value: 6 }, confidence: "medium" },
      { key: "mirror_352", title: "Moduli speculari a tre", description: "Con duelli a tutto campo il 3-5-2 perde le superiorità numeriche in costruzione.", condition_type: "vs_formation", condition_value: "3-5-2", metric_key: "xg_delta", delta: -0.41, zone: null, severity: 2, sample: { unit: "matches", value: 3 }, confidence: "medium" },
    ],
    ai_playbook_text:
      "Specchiarsi a tre e accettare i duelli individuali: contro i moduli speculari l'Inter crea 0.41 xG in meno. In possesso, attaccare la profondità alle spalle del braccetto destro con un attaccante rapido: è la zona in cui concede di più.",
  },
  {
    ...howToBeatMeta,
    team_id: JUVENTUS,
    vulnerabilities_json: [
      { key: "wing_backs_pinning", title: "Quinti che fissano l'ampiezza", description: "I quinti avversari isolano gli esterni bianconeri e generano dribbling sul lato destro.", condition_type: "vs_archetype", condition_value: "quinto", metric_key: "xga_delta", delta: 0.36, zone: "right", severity: 3, sample: { unit: "matches", value: 4 }, confidence: "medium" },
      { key: "vs_back_three", title: "Difese a tre", description: "Contro linee a tre la Juventus fatica in costruzione e concede di più in transizione.", condition_type: "vs_back_line", condition_value: "3", metric_key: "xga_delta", delta: 0.29, zone: null, severity: 3, sample: { unit: "matches", value: 4 }, confidence: "medium" },
      { key: "mirror_352", title: "3-5-2 avversario", description: "Due sole partite: tendenza forte ma ancora da confermare.", condition_type: "vs_formation", condition_value: "3-5-2", metric_key: "xga_delta", delta: 0.44, zone: null, severity: 2, sample: { unit: "matches", value: 2 }, confidence: "low" },
    ],
    ai_playbook_text:
      "Schierare una linea a tre con quinti alti per fissare gli esterni: la Juventus concede +0.36 xGA contro i quinti, soprattutto sul lato destro. Se risponde a specchio, attaccare l'esterno adattato con il quinto più tecnico.",
  },
  {
    ...howToBeatMeta,
    team_id: NAPOLI,
    vulnerabilities_json: [
      { key: "dribblers_on_the_right", title: "Ali dribblatrici sul lato di Di Lorenzo", description: "Le ali che puntano l'uomo saltano il terzino destro e aprono l'area dal lato forte.", condition_type: "vs_archetype", condition_value: "ala_dribblatrice", metric_key: "xga_delta", delta: 0.27, zone: "right", severity: 3, sample: { unit: "matches", value: 7 }, confidence: "high" },
      { key: "midfield_outnumbered", title: "Inferiorità a centrocampo contro il 3-5-2", description: "Lobotka resta in inferiorità contro tre centrocampisti più due punte strette.", condition_type: "vs_formation", condition_value: "3-5-2", metric_key: "xga_delta", delta: 0.31, zone: "center", severity: 2, sample: { unit: "matches", value: 6 }, confidence: "medium" },
    ],
    ai_playbook_text:
      "Isolare il miglior dribblatore contro Di Lorenzo: è la debolezza più solida della squadra (7 partite, +0.27 xGA). Con un 3-5-2 si chiude Lobotka in mezzo e si toglie al Napoli la prima costruzione centrale.",
  },
  {
    ...howToBeatMeta,
    team_id: MILAN,
    vulnerabilities_json: [
      { key: "between_lines", title: "Spazio tra le linee", description: "Le seconde punte ricevono ai lati di Ricci quando la mezzala esce in pressione.", condition_type: "vs_archetype", condition_value: "seconda_punta", metric_key: "xga_delta", delta: 0.38, zone: "center", severity: 3, sample: { unit: "matches", value: 6 }, confidence: "medium" },
      { key: "vs_433", title: "Mezzali del 4-3-3", description: "Le rotazioni ala–mezzala sovraccaricano il lato di Pavlović ed Estupiñán.", condition_type: "vs_formation", condition_value: "4-3-3", metric_key: "xga_delta", delta: 0.35, zone: "left", severity: 2, sample: { unit: "matches", value: 5 }, confidence: "medium" },
      { key: "low_block_sterility", title: "Sterile contro il blocco basso", description: "Senza profondità per Leão la produzione offensiva crolla.", condition_type: "vs_high_line", condition_value: "low", metric_key: "xg_delta", delta: -0.44, zone: null, severity: 2, sample: { unit: "matches", value: 4 }, confidence: "medium" },
    ],
    ai_playbook_text:
      "Difendere basso togliendo la profondità a Leão: contro le linee basse il Milan crea 0.44 xG in meno. In possesso, cercare la seconda punta tra le linee ai lati di Ricci, dove il Milan concede +0.38 xGA.",
  },
];

// ---------------------------------------------------------------------------
// Read-model helpers (same shapes the Supabase data layer will return)
// ---------------------------------------------------------------------------

const teamById = new Map(mockTeams.map((t) => [t.id, t]));

export function getMockMatchBundle(matchId: number): MatchBundle | null {
  const m = mockMatches.find((x) => x.id === matchId);
  if (!m) return null;
  const home = teamById.get(m.home_team_id);
  const away = teamById.get(m.away_team_id);
  if (!home || !away) return null;
  const tactics = mockTeamMatchTactics.filter((t) => t.match_id === matchId);
  const briefs = mockMatchAiBriefs.filter((b) => b.match_id === matchId);
  return {
    match: m,
    home,
    away,
    tactics: {
      home: tactics.find((t) => t.team_id === home.id) ?? null,
      away: tactics.find((t) => t.team_id === away.id) ?? null,
    },
    player_stats: mockPlayerMatchStats.filter((s) => s.match_id === matchId),
    briefs: {
      pre_match: briefs.find((b) => b.brief_type === "pre_match") ?? null,
      post_match: briefs.find((b) => b.brief_type === "post_match") ?? null,
    },
  };
}

export function getMockTeamProfile(slug: string): TeamProfile | null {
  const t = mockTeams.find((x) => x.slug === slug);
  if (!t) return null;
  return {
    team: t,
    players: mockPlayers.filter((p) => p.team_id === t.id),
    splits: mockTeamConditionalSplits.filter((s) => s.team_id === t.id),
    how_to_beat: mockTeamHowToBeat.find((h) => h.team_id === t.id) ?? null,
  };
}

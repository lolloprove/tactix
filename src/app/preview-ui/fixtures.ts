/**
 * PREVIEW-ONLY FICTIONAL FIXTURES. Values the pipeline will compute but that
 * `src/lib/mock-data.ts` does not carry yet: mismatch scores, a season-long
 * tactics series, shift efficiency windows, role percentiles and the other
 * 16 clubs. Delete together with `/preview-ui`.
 */

import type { Team } from "@/types/tactics";
import type { ShiftComparison, TimelinePoint } from "@/components/ChameleonTimeline";
import type { TeamTacticalPoint } from "@/components/LeagueTacticalScatter";
import type { RadarAxis } from "@/components/PlayerConditionalPanel";
import { INTER, INT_JUV, JUVENTUS, MILAN, NAPOLI, mockTeams } from "@/lib/mock-data";

const t = (id: number, name: string, short_name: string): Team => ({
  id,
  name,
  short_name,
  slug: name.toLowerCase().replace(/\s+/g, "-"),
  understat_id: null,
  fotmob_id: null,
  sofascore_id: null,
  logo_url: null,
  updated_at: "2026-11-23T06:00:00+00:00",
});

export const fixtureTeams: Team[] = [
  t(5, "Atalanta", "ATA"),
  t(6, "Roma", "ROM"),
  t(7, "Lazio", "LAZ"),
  t(8, "Fiorentina", "FIO"),
  t(9, "Bologna", "BOL"),
  t(10, "Como", "COM"),
  t(11, "Torino", "TOR"),
  t(12, "Udinese", "UDI"),
  t(13, "Genoa", "GEN"),
  t(14, "Cagliari", "CAG"),
  t(15, "Lecce", "LEC"),
  t(16, "Parma", "PAR"),
  t(17, "Verona", "VER"),
  t(18, "Sassuolo", "SAS"),
  t(19, "Cremonese", "CRE"),
  t(20, "Pisa", "PIS"),
];

const all = new Map([...mockTeams, ...fixtureTeams].map((x) => [x.id, x]));
const team = (id: number) => all.get(id)!;

/** Season-to-date averages per club (12 matches). */
const SEASON: Array<[id: number, line: number | null, ppda: number | null]> = [
  [INTER, 46.1, 9.2],
  [JUVENTUS, 41.8, 11.4],
  [NAPOLI, 44.6, 9.9],
  [MILAN, 40.7, 12.1],
  [5, 47.9, 8.1],
  [6, 42.3, 10.6],
  [7, 43.5, 10.2],
  [8, 41.2, 11.8],
  [9, 45.2, 8.8],
  [10, 46.8, 9.6],
  [11, 38.4, 13.1],
  [12, 37.6, 13.9],
  [13, 39.8, 11.2],
  [14, 36.9, 14.6],
  [15, 37.2, 12.8],
  [16, 40.1, 12.6],
  [17, 38.9, 10.4],
  [18, 42.0, 12.9],
  [19, 36.4, 15.2],
  [20, null, null],
];

export const scatterPoints: TeamTacticalPoint[] = SEASON.map(([id, line, ppda]) => ({
  team: team(id),
  def_line_y: line,
  ppda,
  sample_matches: line == null ? 0 : 12,
}));

export const leagueReference = { def_line_y: 41.6, ppda: 11.3 };

/** Juventus rounds 1-12; round 12 mirrors `mockTeamMatchTactics` for INT_JUV. */
const JUV_SERIES: Array<[round: number, opp: number, venue: "home" | "away", formation: TimelinePoint["formation"], line: number | null, ppda: number | null, xgDiff: number | null]> = [
  [1, 16, "home", "4-2-3-1", 43.1, 10.4, 0.92],
  [2, 13, "away", "4-2-3-1", 42.6, 11.0, 0.41],
  [3, 5, "home", "4-2-3-1", 40.2, 12.3, -0.38],
  [4, 14, "away", "4-2-3-1", 43.8, 10.1, 0.77],
  [5, 6, "home", "4-2-3-1", 41.9, 11.6, 0.12],
  [6, 9, "away", "4-3-3", 45.7, 8.9, 0.64],
  [7, 15, "home", "4-2-3-1", 42.4, 11.2, 0.58],
  [8, 7, "away", "4-2-3-1", 40.8, 12.0, -0.09],
  [9, 12, "home", "4-2-3-1", null, null, 0.81],
  [10, 8, "away", "4-2-3-1", 41.3, 11.9, 0.22],
  [11, 10, "home", "4-2-3-1", 42.9, 10.7, 0.31],
  [12, INTER, "away", "3-4-2-1", 38.2, 13.8, -1.27],
];

export const juventusTimeline: TimelinePoint[] = JUV_SERIES.map(([round, opp, venue, formation, line, ppda, xgDiff]) => ({
  match_id: round === 12 ? INT_JUV : 9000 + round,
  round,
  opponent: team(opp),
  venue,
  formation,
  baseline_formation: "4-2-3-1",
  ppda,
  avg_def_line_y: line,
  xg_diff: xgDiff,
  is_tactical_shift: formation !== "4-2-3-1",
  shift_reason:
    round === 12
      ? "Difesa a tre a specchio sul 3-5-2 dell'Inter: Kalulu braccetto destro, Conceição adattato a quinto destro, Cambiaso quinto sinistro."
      : formation !== "4-2-3-1"
        ? "Centrocampo a tre per pareggiare i numeri contro il palleggio del Bologna; Koopmeiners da mezzala destra."
        : null,
}));

export const juventusShiftComparisons: ShiftComparison[] = [
  {
    match_id: 9006,
    before: { from_round: 1, to_round: 5, matches: 5, xg_diff: 0.37 },
    after: { from_round: 6, to_round: 6, matches: 1, xg_diff: 0.64 },
    confidence: "low",
  },
  {
    match_id: INT_JUV,
    before: { from_round: 7, to_round: 11, matches: 5, xg_diff: 0.37 },
    after: { from_round: 12, to_round: 12, matches: 1, xg_diff: -1.27 },
    confidence: "low",
  },
];

export const juventusBaseline = { ppda: 11.4, avg_def_line_y: 41.8 };

export const mismatchScores: Record<string, { score: number | null; advantage: "a" | "b" | null }> = {
  "210-302": { score: 74, advantage: "a" },
  "209-305": { score: 61, advantage: "a" },
  "204-310": { score: 58, advantage: "a" },
  "206-307": { score: null, advantage: null },
  "109-209": { score: 81, advantage: "a" },
  "111-204": { score: 57, advantage: "b" },
  "102-210": { score: null, advantage: null },
};

export const radarByPlayer: Record<number, RadarAxis[]> = {
  302: [
    { key: "def_duels", label: "Duelli difensivi", percentile: 41 },
    { key: "tackles", label: "Contrasti", percentile: 58 },
    { key: "progression", label: "Progressione", percentile: 72 },
    { key: "crosses", label: "Cross", percentile: 66 },
    { key: "aerial", label: "Duelli aerei", percentile: 63 },
    { key: "recoveries", label: "Recuperi", percentile: 77 },
  ],
  204: [
    { key: "def_duels", label: "Duelli difensivi", percentile: 91 },
    { key: "aerial", label: "Duelli aerei", percentile: 88 },
    { key: "interceptions", label: "Intercetti", percentile: 74 },
    { key: "progression", label: "Progressione", percentile: 36 },
    { key: "pass_acc", label: "Precisione passaggi", percentile: 62 },
    { key: "recoveries", label: "Recuperi", percentile: 69 },
  ],
};

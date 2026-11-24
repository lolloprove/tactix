// Compile-time guard: `npm run typecheck` fails if `tactics.ts` drifts from the
// generated Supabase types. Every contract must have exactly the DB columns and
// be assignable to the DB row (contracts may only narrow, e.g. typed JSON).

import type { Enums, Tables } from "./database.types";
import type * as T from "./tactics";

type Equals<A, B> =
  (<G>() => G extends A ? 1 : 2) extends <G>() => G extends B ? 1 : 2 ? true : false;
type Fits<A, B> = [A] extends [B] ? true : false;
type Assert<T extends true> = T;

type Aligned<Contract, Row> = Equals<keyof Contract, keyof Row> extends true
  ? Fits<Contract, Row>
  : false;

export type SchemaAlignment = [
  Assert<Aligned<T.Team, Tables<"teams">>>,
  Assert<Aligned<T.Player, Tables<"players">>>,
  Assert<Aligned<T.Match, Tables<"matches">>>,
  Assert<Aligned<T.TeamMatchTactics, Tables<"team_match_tactics">>>,
  Assert<Aligned<T.PlayerMatchStats, Tables<"player_match_stats">>>,
  Assert<Aligned<T.TeamConditionalSplit, Tables<"team_conditional_splits">>>,
  Assert<Aligned<T.PlayerConditionalSplit, Tables<"player_conditional_splits">>>,
  Assert<Aligned<T.MatchAiBrief, Tables<"match_ai_briefs">>>,
  Assert<Aligned<T.TeamHowToBeat, Tables<"team_how_to_beat">>>,
  Assert<Aligned<T.LeagueTacticalScatterRow, Tables<"v_league_tactical_scatter">>>,
  Assert<Aligned<T.TeamShiftWindowRow, Tables<"v_team_shift_windows">>>,

  Assert<Equals<T.MatchStatus, Enums<"match_status">>>,
  Assert<Equals<T.PlayerPosition, Enums<"player_position">>>,
  Assert<Equals<T.PlayerArchetype, Enums<"player_archetype">>>,
  Assert<Equals<T.ZoneCorridor, Enums<"zone_corridor">>>,
  Assert<Equals<T.ConfidenceLevel, Enums<"confidence_level">>>,
  Assert<Equals<T.TeamConditionType, Enums<"team_condition_type">>>,
  Assert<Equals<T.PlayerConditionType, Enums<"player_condition_type">>>,
  Assert<Equals<T.BriefType, Enums<"brief_type">>>,
];

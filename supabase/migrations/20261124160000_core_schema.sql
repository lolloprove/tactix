-- Tactix core schema — Serie A 2026/27
--
-- Pitch coordinate convention (vertical pitch, every value 0-100, always from
-- the perspective of the team the row belongs to):
--   x = width  (0 = left touchline, 100 = right touchline, facing the attack)
--   y = length (0 = own goal line,  100 = opponent goal line)
-- Adapters must normalise provider coordinates (Opta/FotMob/SofaScore use x as
-- length) before writing.

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------
create type public.match_status as enum (
  'scheduled', 'live', 'finished', 'postponed', 'cancelled'
);

create type public.player_position as enum (
  'GK', 'CB', 'LB', 'RB', 'LWB', 'RWB', 'DM', 'CM', 'AM', 'LW', 'RW', 'ST'
);

create type public.player_archetype as enum (
  -- goalkeepers
  'portiere_classico', 'portiere_libero',
  -- centre-backs
  'braccetto', 'centrale_marcatore', 'centrale_impostazione',
  -- full-backs / wing-backs
  'terzino_difensivo', 'terzino_spinta', 'terzino_invertito', 'quinto',
  -- midfielders
  'regista', 'mediano_incontrista', 'mezzala', 'box_to_box', 'trequartista',
  -- wingers
  'ala_dribblatrice', 'ala_inversa',
  -- forwards
  'prima_punta', 'falso_nove', 'attaccante_profondita', 'seconda_punta'
);

create type public.zone_corridor as enum (
  'left', 'left_half', 'center', 'right_half', 'right'
);

-- low < 270 min (< 3 matches), medium 270-540 min (3-6 matches), high > 540 min (> 6 matches)
create type public.confidence_level as enum ('low', 'medium', 'high');

create type public.team_condition_type as enum (
  'vs_formation', 'vs_back_line', 'vs_high_line', 'vs_archetype'
);

create type public.player_condition_type as enum (
  'vs_defender_archetype', 'vs_attacker_archetype', 'vs_line_height', 'vs_formation'
);

create type public.brief_type as enum ('pre_match', 'post_match');

-- ---------------------------------------------------------------------------
-- updated_at helper
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- teams
-- ---------------------------------------------------------------------------
create table public.teams (
  id            bigint generated always as identity primary key,
  name          text not null,
  short_name    text not null check (short_name ~ '^[A-Z]{3}$'),
  slug          text not null unique check (slug ~ '^[a-z0-9-]+$'),
  understat_id  integer unique,
  fotmob_id     integer unique,
  sofascore_id  integer unique,
  logo_url      text,
  updated_at    timestamptz not null default now()
);

create trigger teams_set_updated_at
  before update on public.teams
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- players
-- ---------------------------------------------------------------------------
create table public.players (
  id                    bigint generated always as identity primary key,
  team_id               bigint references public.teams (id) on delete set null,
  name                  text not null,
  primary_position      public.player_position not null,
  archetype_primary     public.player_archetype,
  archetype_secondary   public.player_archetype,
  -- { "<player_archetype>": 0..1 } — cosine similarity to each archetype centroid
  archetype_scores_json jsonb not null default '{}'::jsonb
                          check (jsonb_typeof(archetype_scores_json) = 'object'),
  minutes_total         integer not null default 0 check (minutes_total >= 0),
  understat_id          integer unique,
  fotmob_id             integer unique,
  sofascore_id          integer unique,
  updated_at            timestamptz not null default now(),
  check (archetype_secondary is null or archetype_secondary <> archetype_primary)
);

create index players_team_id_idx on public.players (team_id);

create trigger players_set_updated_at
  before update on public.players
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- matches
-- ---------------------------------------------------------------------------
create table public.matches (
  id            bigint generated always as identity primary key,
  season        text not null check (season ~ '^\d{4}/\d{2}$'),
  round         smallint not null check (round between 1 and 38),
  kickoff_at    timestamptz not null,
  home_team_id  bigint not null references public.teams (id),
  away_team_id  bigint not null references public.teams (id),
  home_goals    smallint check (home_goals >= 0),
  away_goals    smallint check (away_goals >= 0),
  home_xg       numeric(4, 2) check (home_xg >= 0),
  away_xg       numeric(4, 2) check (away_xg >= 0),
  status        public.match_status not null default 'scheduled',
  understat_id  integer unique,
  fotmob_id     integer unique,
  sofascore_id  integer unique,
  updated_at    timestamptz not null default now(),
  check (home_team_id <> away_team_id),
  unique (season, home_team_id, away_team_id)
);

create index matches_season_round_idx on public.matches (season, round);
create index matches_home_team_id_idx on public.matches (home_team_id);
create index matches_away_team_id_idx on public.matches (away_team_id);
create index matches_kickoff_at_idx on public.matches (kickoff_at);

create trigger matches_set_updated_at
  before update on public.matches
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- team_match_tactics
-- ---------------------------------------------------------------------------
create table public.team_match_tactics (
  match_id            bigint not null references public.matches (id) on delete cascade,
  team_id             bigint not null references public.teams (id),
  formation           text check (formation ~ '^\d(-\d){2,4}$'),
  -- most used formation over the previous rounds; compared with `formation` to flag shifts
  baseline_formation  text check (baseline_formation ~ '^\d(-\d){2,4}$'),
  back_line_count     smallint check (back_line_count between 3 and 5),
  possession          numeric(5, 2) check (possession between 0 and 100),
  ppda                numeric(5, 2) check (ppda >= 0),
  field_tilt          numeric(5, 2) check (field_tilt between 0 and 100),
  avg_def_line_y      numeric(5, 2) check (avg_def_line_y between 0 and 100),
  attack_bias_left    numeric(5, 2) check (attack_bias_left between 0 and 100),
  attack_bias_center  numeric(5, 2) check (attack_bias_center between 0 and 100),
  attack_bias_right   numeric(5, 2) check (attack_bias_right between 0 and 100),
  is_tactical_shift   boolean not null default false,
  shift_reason        text,
  -- { "shot_zones": [{ zone, xga, shots, goals }], "origin_corridors": { left, center, right } }
  xga_zones_json      jsonb check (xga_zones_json is null or jsonb_typeof(xga_zones_json) = 'object'),
  primary key (match_id, team_id),
  check (
    attack_bias_left is null or attack_bias_center is null or attack_bias_right is null
    or abs(attack_bias_left + attack_bias_center + attack_bias_right - 100) <= 1
  ),
  check (not is_tactical_shift or shift_reason is not null)
);

create index team_match_tactics_team_id_idx on public.team_match_tactics (team_id);

-- ---------------------------------------------------------------------------
-- player_match_stats
-- ---------------------------------------------------------------------------
create table public.player_match_stats (
  match_id             bigint not null references public.matches (id) on delete cascade,
  player_id            bigint not null references public.players (id) on delete cascade,
  team_id              bigint not null references public.teams (id),
  opponent_id          bigint not null references public.teams (id),
  position_played      public.player_position,
  minutes              smallint not null check (minutes between 0 and 130),
  avg_x                numeric(5, 2) check (avg_x between 0 and 100),
  avg_y                numeric(5, 2) check (avg_y between 0 and 100),
  zone_corridor        public.zone_corridor,
  dribbles_won         smallint check (dribbles_won >= 0),
  dribbles_past        smallint check (dribbles_past >= 0),
  duels_won            smallint check (duels_won >= 0),
  duels_lost           smallint check (duels_lost >= 0),
  progressive_actions  smallint check (progressive_actions >= 0),
  xg                   numeric(4, 2) check (xg >= 0),
  xa                   numeric(4, 2) check (xa >= 0),
  rating               numeric(3, 1) check (rating between 0 and 10),
  primary key (match_id, player_id),
  check (team_id <> opponent_id)
);

create index player_match_stats_player_id_idx on public.player_match_stats (player_id);
create index player_match_stats_team_id_idx on public.player_match_stats (team_id);
create index player_match_stats_opponent_id_idx on public.player_match_stats (opponent_id);

-- ---------------------------------------------------------------------------
-- team_conditional_splits
-- Deltas are vs the team's own season baseline. NULL = insufficient data.
-- ---------------------------------------------------------------------------
create table public.team_conditional_splits (
  id                       bigint generated always as identity primary key,
  team_id                  bigint not null references public.teams (id) on delete cascade,
  season                   text not null check (season ~ '^\d{4}/\d{2}$'),
  condition_type           public.team_condition_type not null,
  condition_value          text not null,
  sample_matches           smallint not null check (sample_matches >= 0),
  xg_delta                 numeric(5, 2),
  xga_delta                numeric(5, 2),
  dribbles_conceded_delta  numeric(5, 2),
  confidence               public.confidence_level generated always as (
    case
      when sample_matches < 3 then 'low'::public.confidence_level
      when sample_matches <= 6 then 'medium'::public.confidence_level
      else 'high'::public.confidence_level
    end
  ) stored,
  computed_at              timestamptz not null default now(),
  unique (team_id, season, condition_type, condition_value)
);

-- ---------------------------------------------------------------------------
-- player_conditional_splits
-- Deltas are vs the player's own season baseline. NULL = insufficient data.
-- ---------------------------------------------------------------------------
create table public.player_conditional_splits (
  id               bigint generated always as identity primary key,
  player_id        bigint not null references public.players (id) on delete cascade,
  season           text not null check (season ~ '^\d{4}/\d{2}$'),
  condition_type   public.player_condition_type not null,
  condition_value  text not null,
  sample_minutes   integer not null check (sample_minutes >= 0),
  rating_delta     numeric(4, 2),
  dribbles_delta   numeric(5, 2),
  duels_delta      numeric(5, 2),
  confidence       public.confidence_level generated always as (
    case
      when sample_minutes < 270 then 'low'::public.confidence_level
      when sample_minutes <= 540 then 'medium'::public.confidence_level
      else 'high'::public.confidence_level
    end
  ) stored,
  computed_at      timestamptz not null default now(),
  unique (player_id, season, condition_type, condition_value)
);

-- ---------------------------------------------------------------------------
-- match_ai_briefs — one brief per (match, type); the row's existence is the cache key
-- ---------------------------------------------------------------------------
create table public.match_ai_briefs (
  id                        bigint generated always as identity primary key,
  match_id                  bigint not null references public.matches (id) on delete cascade,
  brief_type                public.brief_type not null,
  tactical_summary          text not null,
  key_edges_json            jsonb not null default '[]'::jsonb check (jsonb_typeof(key_edges_json) = 'array'),
  x_factors_json            jsonb not null default '[]'::jsonb check (jsonb_typeof(x_factors_json) = 'array'),
  player_observations_json  jsonb not null default '[]'::jsonb check (jsonb_typeof(player_observations_json) = 'array'),
  model                     text,
  generated_at              timestamptz not null default now(),
  unique (match_id, brief_type)
);

-- ---------------------------------------------------------------------------
-- team_how_to_beat
-- ---------------------------------------------------------------------------
create table public.team_how_to_beat (
  team_id               bigint not null references public.teams (id) on delete cascade,
  season                text not null check (season ~ '^\d{4}/\d{2}$'),
  through_round         smallint check (through_round between 1 and 38),
  updated_at            timestamptz not null default now(),
  vulnerabilities_json  jsonb not null default '[]'::jsonb check (jsonb_typeof(vulnerabilities_json) = 'array'),
  ai_playbook_text      text,
  primary key (team_id, season)
);

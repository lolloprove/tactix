-- Tactix UI alignment: extra JSON columns + analytical views for scatter, variance & shift windows

-- 1. players.radar_percentiles_json
alter table public.players
  add column if not exists radar_percentiles_json jsonb
    check (radar_percentiles_json is null or jsonb_typeof(radar_percentiles_json) = 'array');

-- 2. match_ai_briefs.matchups_json
alter table public.match_ai_briefs
  add column if not exists matchups_json jsonb not null default '[]'::jsonb
    check (jsonb_typeof(matchups_json) = 'array');

-- 3. team_match_tactics.dribbles_zones_json
alter table public.team_match_tactics
  add column if not exists dribbles_zones_json jsonb
    check (dribbles_zones_json is null or jsonb_typeof(dribbles_zones_json) = 'object');

-- 4. View: v_league_tactical_scatter
-- Season averages per team of defensive line height & PPDA, plus Variance Index
-- (Points vs Poisson xPts, Goals vs xG, GA vs xGA) and league reference averages.
create or replace view public.v_league_tactical_scatter
with (security_invoker = true) as
with team_matches as (
  select
    m.season,
    m.id as match_id,
    m.round,
    m.home_team_id as team_id,
    m.home_goals as goals_for,
    m.away_goals as goals_against,
    m.home_xg::double precision as xg_for,
    m.away_xg::double precision as xg_against
  from public.matches m
  where m.status = 'finished'
  union all
  select
    m.season,
    m.id as match_id,
    m.round,
    m.away_team_id as team_id,
    m.away_goals as goals_for,
    m.home_goals as goals_against,
    m.away_xg::double precision as xg_for,
    m.home_xg::double precision as xg_against
  from public.matches m
  where m.status = 'finished'
),
fact(k, f) as (
  values
    (0, 1.0::double precision),
    (1, 1.0::double precision),
    (2, 2.0::double precision),
    (3, 6.0::double precision),
    (4, 24.0::double precision),
    (5, 120.0::double precision),
    (6, 720.0::double precision)
),
match_xpts as (
  select
    tm.season,
    tm.match_id,
    tm.team_id,
    tm.goals_for,
    tm.goals_against,
    tm.xg_for,
    tm.xg_against,
    case
      when tm.goals_for is null or tm.goals_against is null then null
      when tm.goals_for > tm.goals_against then 3
      when tm.goals_for = tm.goals_against then 1
      else 0
    end as pts,
    case
      when tm.xg_for is null or tm.xg_against is null then null
      else (
        select sum(
          (exp(-tm.xg_for) * power(tm.xg_for, fa.k) / fa.f)
          * (exp(-tm.xg_against) * power(tm.xg_against, fb.k) / fb.f)
          * case when fa.k > fb.k then 3.0 when fa.k = fb.k then 1.0 else 0.0 end
        )
        from fact fa
        cross join fact fb
      )
    end as xpts
  from team_matches tm
),
agg as (
  select
    mx.season,
    t.id as team_id,
    t.name as team_name,
    t.short_name,
    t.slug,
    count(mx.match_id)::integer as matches_played,
    count(tmt.match_id) filter (where tmt.avg_def_line_y is not null and tmt.ppda is not null)::integer as sample_matches,
    round(avg(tmt.avg_def_line_y)::numeric, 2) as avg_def_line_y,
    round(avg(tmt.ppda)::numeric, 2) as avg_ppda,
    round(avg(tmt.possession)::numeric, 2) as avg_possession,
    round(avg(tmt.field_tilt)::numeric, 2) as avg_field_tilt,
    coalesce(sum(mx.pts), 0)::integer as points,
    round(sum(mx.xpts)::numeric, 2) as expected_points,
    round((coalesce(sum(mx.pts), 0) - sum(mx.xpts))::numeric, 2) as points_variance,
    coalesce(sum(mx.goals_for), 0)::integer as goals_for,
    coalesce(sum(mx.goals_against), 0)::integer as goals_against,
    round(sum(mx.xg_for)::numeric, 2) as xg_for,
    round(sum(mx.xg_against)::numeric, 2) as xg_against,
    round((coalesce(sum(mx.goals_for), 0) - sum(mx.xg_for))::numeric, 2) as goals_minus_xg,
    round((coalesce(sum(mx.goals_against), 0) - sum(mx.xg_against))::numeric, 2) as ga_minus_xga
  from match_xpts mx
  join public.teams t on t.id = mx.team_id
  left join public.team_match_tactics tmt
    on tmt.match_id = mx.match_id and tmt.team_id = mx.team_id
  group by mx.season, t.id, t.name, t.short_name, t.slug
)
select
  a.*,
  case
    when a.sample_matches < 3 then 'low'::public.confidence_level
    when a.sample_matches <= 6 then 'medium'::public.confidence_level
    else 'high'::public.confidence_level
  end as confidence,
  round(avg(a.avg_def_line_y) over (partition by a.season), 2) as league_avg_def_line_y,
  round(avg(a.avg_ppda) over (partition by a.season), 2) as league_avg_ppda
from agg a;

grant select on public.v_league_tactical_scatter to anon, authenticated, service_role;

-- 5. View: v_team_shift_windows
-- Compares xG-xGA efficiency before vs after every match with is_tactical_shift = true.
create or replace view public.v_team_shift_windows
with (security_invoker = true) as
with ordered as (
  select
    m.season,
    tmt.team_id,
    tmt.match_id,
    m.round,
    tmt.formation,
    tmt.baseline_formation,
    tmt.is_tactical_shift,
    tmt.shift_reason,
    case
      when m.home_team_id = tmt.team_id then (m.home_xg - m.away_xg)
      else (m.away_xg - m.home_xg)
    end as xg_diff
  from public.team_match_tactics tmt
  join public.matches m on m.id = tmt.match_id
  where m.status = 'finished'
),
shifts as (
  select
    o.*,
    lag(o.round) over (partition by o.season, o.team_id order by o.round) as prev_shift_round,
    lead(o.round) over (partition by o.season, o.team_id order by o.round) as next_shift_round
  from ordered o
  where o.is_tactical_shift = true
)
select
  s.season,
  s.team_id,
  s.match_id,
  s.round as shift_round,
  s.formation,
  s.baseline_formation,
  s.shift_reason,
  bef.from_round as before_from_round,
  bef.to_round as before_to_round,
  coalesce(bef.matches, 0)::integer as before_matches,
  round(bef.xg_diff::numeric, 2) as before_xg_diff,
  aft.from_round as after_from_round,
  aft.to_round as after_to_round,
  coalesce(aft.matches, 0)::integer as after_matches,
  round(aft.xg_diff::numeric, 2) as after_xg_diff,
  round((aft.xg_diff - bef.xg_diff)::numeric, 2) as xg_diff_delta,
  case
    when least(coalesce(bef.matches, 0), coalesce(aft.matches, 0)) < 3 then 'low'::public.confidence_level
    when least(coalesce(bef.matches, 0), coalesce(aft.matches, 0)) <= 6 then 'medium'::public.confidence_level
    else 'high'::public.confidence_level
  end as confidence
from shifts s
left join lateral (
  select
    min(b.round) as from_round,
    max(b.round) as to_round,
    count(*)::integer as matches,
    avg(b.xg_diff) as xg_diff
  from (
    select o.round, o.xg_diff
    from ordered o
    where o.season = s.season
      and o.team_id = s.team_id
      and o.round < s.round
      and (s.prev_shift_round is null or o.round > s.prev_shift_round)
    order by o.round desc
    limit 5
  ) b
) bef on true
left join lateral (
  select
    min(a.round) as from_round,
    max(a.round) as to_round,
    count(*)::integer as matches,
    avg(a.xg_diff) as xg_diff
  from (
    select o.round, o.xg_diff
    from ordered o
    where o.season = s.season
      and o.team_id = s.team_id
      and o.round >= s.round
      and (s.next_shift_round is null or o.round < s.next_shift_round)
    order by o.round asc
    limit 5
  ) a
) aft on true;

grant select on public.v_team_shift_windows to anon, authenticated, service_role;

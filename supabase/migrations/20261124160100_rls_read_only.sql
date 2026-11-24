-- Public read-only access. Writes happen only from the pipeline with the
-- service role, which bypasses RLS; anon/authenticated get SELECT and nothing else.

do $$
declare
  t text;
begin
  foreach t in array array[
    'teams', 'players', 'matches', 'team_match_tactics', 'player_match_stats',
    'team_conditional_splits', 'player_conditional_splits',
    'match_ai_briefs', 'team_how_to_beat'
  ]
  loop
    execute format('alter table public.%I enable row level security', t);
    execute format('revoke all on table public.%I from anon, authenticated', t);
    execute format('grant select on table public.%I to anon, authenticated', t);
    execute format(
      'create policy %I on public.%I for select to anon, authenticated using (true)',
      t || '_public_read', t
    );
    execute format('grant all on table public.%I to service_role', t);
  end loop;
end;
$$;

revoke execute on function public.set_updated_at() from public, anon, authenticated;

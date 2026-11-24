import type { Metadata } from "next";
import { Suspense, type ReactNode } from "react";
import { AppShell } from "@/components/AppShell";
import { ChameleonTimeline } from "@/components/ChameleonTimeline";
import { LeagueTacticalScatter } from "@/components/LeagueTacticalScatter";
import { MatchupMatrix, type MatchupDuel } from "@/components/MatchupMatrix";
import { PlayerConditionalPanel } from "@/components/PlayerConditionalPanel";
import { VulnerabilityPitch } from "@/components/VulnerabilityPitch";
import { Label } from "@/components/primitives";
import {
  INT_JUV,
  JUVENTUS,
  JUV_NAP,
  MOCK_SEASON,
  getMockMatchBundle,
  mockMatchAiBriefs,
  mockMatches,
  mockPlayerConditionalSplits,
  mockPlayers,
  mockTeams,
} from "@/lib/mock-data";
import type { ConfidenceLevel, SampleSize, ZoneCorridor } from "@/types/tactics";
import {
  fixtureTeams,
  juventusBaseline,
  juventusShiftComparisons,
  juventusTimeline,
  leagueReference,
  mismatchScores,
  radarByPlayer,
  scatterPoints,
} from "./fixtures";

export const metadata: Metadata = { title: "Preview UI · Tactix", robots: { index: false } };

const playerById = new Map(mockPlayers.map((p) => [p.id, p]));
const teamById = new Map(mockTeams.map((t) => [t.id, t]));

/** `evidence` lists `mockPlayerConditionalSplits` ids, as the engine will attach them. */
type DuelSpec = [a: number, b: number, zone: ZoneCorridor | null, sample: SampleSize, confidence: ConfidenceLevel, evidence: number[]];

const DUELS: Record<number, DuelSpec[]> = {
  [JUV_NAP]: [
    [210, 302, "left_half", { unit: "matches", value: 7 }, "high", [10, 1]],
    [209, 305, "right", { unit: "minutes", value: 260 }, "low", [12]],
    [204, 310, "center", { unit: "minutes", value: 720 }, "high", [3]],
    [206, 307, "center", { unit: "matches", value: 4 }, "medium", []],
  ],
  [INT_JUV]: [
    [109, 209, "left", { unit: "minutes", value: 330 }, "medium", [14, 16]],
    [111, 204, "center", { unit: "minutes", value: 720 }, "high", [3]],
    [102, 210, "right_half", { unit: "minutes", value: 45 }, "low", []],
  ],
};

function buildDuels(matchId: number): MatchupDuel[] {
  return (DUELS[matchId] ?? []).map(([a, b, zone, sample, confidence, evidenceIds]) => {
    const pa = playerById.get(a)!;
    const pb = playerById.get(b)!;
    const ms = mismatchScores[`${a}-${b}`];
    return {
      id: `${a}-${b}`,
      a: { player: pa, team: teamById.get(pa.team_id!)! },
      b: { player: pb, team: teamById.get(pb.team_id!)! },
      zone,
      mismatch_score: ms?.score ?? null,
      advantage: ms?.advantage ?? null,
      evidence: mockPlayerConditionalSplits.filter((s) => evidenceIds.includes(s.id)),
      sample,
      confidence,
    };
  });
}

export default function PreviewUiPage(props: PageProps<"/preview-ui">) {
  return (
    <Suspense fallback={<div className="min-h-screen bg-canvas" />}>
      <PreviewUi searchParams={props.searchParams} />
    </Suspense>
  );
}

async function PreviewUi({ searchParams }: { searchParams: PageProps<"/preview-ui">["searchParams"] }) {
  const sp = await searchParams;
  const round = Number(sp.giornata ?? 13) === 12 ? 12 : 13;
  const featuredMatchId = round === 12 ? INT_JUV : JUV_NAP;
  const featured = getMockMatchBundle(featuredMatchId)!;
  const played = getMockMatchBundle(INT_JUV)!;
  const juve = teamById.get(JUVENTUS)!;
  const inter = teamById.get(played.match.home_team_id)!;

  const brief = mockMatchAiBriefs.find((b) => b.match_id === JUV_NAP && b.brief_type === "pre_match")!;
  const juvNap = getMockMatchBundle(JUV_NAP)!;
  const panelPlayers = [302, 204].map((id) => {
    const player = playerById.get(id)!;
    const observation = brief.player_observations_json.find((o) => o.player_id === id) ?? null;
    return {
      player,
      team: teamById.get(player.team_id!)!,
      splits: mockPlayerConditionalSplits.filter((s) => s.player_id === id),
      radar: radarByPlayer[id] ?? null,
      observation,
      matchupPlayer: observation?.matchup_player_id ? (playerById.get(observation.matchup_player_id) ?? null) : null,
    };
  });

  return (
    <AppShell
      season={MOCK_SEASON}
      teams={[...mockTeams, ...fixtureTeams]}
      players={mockPlayers}
      currentRound={round}
      availableRounds={[...new Set(mockMatches.map((m) => m.round))]}
      roundBasePath="/preview-ui"
    >
      <div className="pt-12 pb-8 lg:pt-16">
        <Label>Preview UI · dati di sviluppo fittizi</Label>
        <h1 className="mt-4 text-[40px] leading-[44px] font-medium tracking-[-0.03em] text-ink md:text-display-lg">Design system core</h1>
        <p className="mt-6 max-w-[62ch] text-[18px] leading-[29px] text-ink-2 md:text-lead">
          Sei moduli di data-viz su <span className="font-mono text-ink">mock-data.ts</span>. I valori che la pipeline non espone ancora (mismatch, percentili, serie stagionale) arrivano da fixture locali alla pagina.
        </p>
      </div>

      <Section>
        <VulnerabilityPitch
          team={juve}
          opponent={inter}
          tactics={played.tactics.away}
          opponentTactics={played.tactics.home}
          playerStats={played.player_stats}
          players={mockPlayers}
        />
      </Section>

      <Section>
        <LeagueTacticalScatter points={scatterPoints} reference={leagueReference} defaultSelectedTeamId={JUVENTUS} />
      </Section>

      <Section>
        <MatchupMatrix match={featured.match} home={featured.home} away={featured.away} duels={buildDuels(featuredMatchId)} />
      </Section>

      <Section>
        <ChameleonTimeline team={juve} points={juventusTimeline} comparisons={juventusShiftComparisons} baseline={juventusBaseline} />
      </Section>

      <Section>
        <div className="flex flex-col gap-8">
          {panelPlayers.map((p) => (
            <PlayerConditionalPanel
              key={p.player.id}
              {...p}
              observationContext={{
                match: juvNap.match,
                home: juvNap.home,
                away: juvNap.away,
                brief_type: brief.brief_type,
                model: brief.model,
                generated_at: brief.generated_at,
              }}
            />
          ))}
        </div>
      </Section>
    </AppShell>
  );
}

function Section({ children }: { children: ReactNode }) {
  return <div className="border-t border-line py-24 lg:py-32">{children}</div>;
}

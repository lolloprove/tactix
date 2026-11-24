import type {
  ConfidenceLevel,
  Match,
  Player,
  PlayerConditionalSplit,
  SampleSize,
  Team,
  ZoneCorridor,
} from "@/types/tactics";
import {
  CORRIDOR_LABEL,
  LINE_HEIGHT_LABEL,
  TONE_TEXT,
  archetypeLabel,
  deltaTone,
  fmt,
  fmtSample,
  fmtSigned,
  surname,
  type Polarity,
} from "./format";
import { Chip, ConfidenceChip, Label, ModuleHeader, cx } from "./primitives";

export type DuelSide = { player: Player; team: Team };

export type MatchupDuel = {
  id: string;
  a: DuelSide;
  b: DuelSide;
  zone: ZoneCorridor | null;
  /** 0-100 strength of the tilt, computed by the engine. `null` = Dati insufficienti. */
  mismatch_score: number | null;
  advantage: "a" | "b" | null;
  /** Historical splits of either player in this exact context (opponent archetype / line height). */
  evidence: PlayerConditionalSplit[];
  sample: SampleSize;
  confidence: ConfidenceLevel;
};

export type MatchupMatrixProps = {
  match: Match;
  home: Team;
  away: Team;
  duels: MatchupDuel[];
};

export function MatchupMatrix({ match, home, away, duels }: MatchupMatrixProps) {
  return (
    <section className="flex flex-col">
      <ModuleHeader
        label={`Matrice duelli · G${match.round} · ${home.short_name}–${away.short_name}`}
        title="Duelli chiave"
        description="Ogni duello mette a confronto due archetipi. Il mismatch indica quanto il contesto storico favorisce un lato; in rosso le statistiche negative registrate in questo contesto specifico."
      />

      <div className="hidden grid-cols-[minmax(0,5fr)_minmax(0,3fr)_minmax(0,6fr)] gap-8 border-b border-line py-3 lg:grid">
        <Label>Giocatore A · Giocatore B</Label>
        <Label>Mismatch 0–100</Label>
        <Label>Storico nel contesto</Label>
      </div>

      {duels.length === 0 ? (
        <p className="py-8 text-body-md text-ink-3">Nessun duello con dati sufficienti per questa partita.</p>
      ) : (
        <ol>
          {duels.map((d) => (
            <DuelRow key={d.id} duel={d} />
          ))}
        </ol>
      )}
    </section>
  );
}

function DuelRow({ duel }: { duel: MatchupDuel }) {
  const { a, b } = duel;
  const favoured = duel.advantage === "a" ? a : duel.advantage === "b" ? b : null;
  const nameOf = (id: number) => (id === a.player.id ? surname(a.player.name) : id === b.player.id ? surname(b.player.name) : `#${id}`);

  return (
    <li className="grid grid-cols-1 gap-6 border-b border-line py-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,3fr)_minmax(0,6fr)] lg:gap-8">
      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-start gap-3">
          <PlayerCell side={a} favoured={duel.advantage === "a"} />
          <span className="pt-1 font-mono text-label-sm font-medium uppercase text-ink-4">vs</span>
          <PlayerCell side={b} favoured={duel.advantage === "b"} alignEnd />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ConfidenceChip confidence={duel.confidence} sample={duel.sample} />
          {duel.zone && <Chip>{CORRIDOR_LABEL[duel.zone]}</Chip>}
        </div>
      </div>

      <MismatchBar score={duel.mismatch_score} advantage={duel.advantage} favouredName={favoured ? surname(favoured.player.name) : null} confidence={duel.confidence} />

      <div className="flex flex-col">
        {duel.evidence.length === 0 ? (
          <p className="text-body-md text-ink-3">Dati insufficienti: nessuno split storico in questo contesto.</p>
        ) : (
          duel.evidence.map((s) => <EvidenceRow key={s.id} split={s} name={nameOf(s.player_id)} />)
        )}
      </div>
    </li>
  );
}

function PlayerCell({ side, favoured, alignEnd = false }: { side: DuelSide; favoured: boolean; alignEnd?: boolean }) {
  return (
    <div className={cx("flex min-w-0 flex-col gap-2", alignEnd && "items-end text-right")}>
      <span className="flex items-baseline gap-2">
        {favoured && !alignEnd && <span className="size-1.5 shrink-0 translate-y-[-2px] rounded-full bg-edge" aria-label="Avvantaggiato" />}
        <span className={cx("truncate text-body-lg font-medium", favoured ? "text-ink" : "text-ink-2")}>{surname(side.player.name)}</span>
        {favoured && alignEnd && <span className="size-1.5 shrink-0 translate-y-[-2px] rounded-full bg-edge" aria-label="Avvantaggiato" />}
      </span>
      <span className="font-mono text-label-sm font-medium uppercase text-ink-4">
        {side.team.short_name} · {side.player.primary_position}
      </span>
      <Chip tone={favoured ? "edge" : "neutral"} className={cx("max-w-full overflow-hidden", !alignEnd && "self-start")}>
        <span className="truncate">{archetypeLabel(side.player.archetype_primary)}</span>
      </Chip>
    </div>
  );
}

function MismatchBar({
  score,
  advantage,
  favouredName,
  confidence,
}: {
  score: number | null;
  advantage: "a" | "b" | null;
  favouredName: string | null;
  confidence: ConfidenceLevel;
}) {
  if (score == null) {
    return (
      <div className="flex flex-col gap-2">
        <Label className="lg:hidden">Mismatch</Label>
        <p className="text-body-md text-ink-3">Dati insufficienti</p>
      </div>
    );
  }
  const pct = Math.min(Math.max(score, 0), 100);
  return (
    <div className="flex flex-col gap-3">
      <Label className="lg:hidden">Mismatch</Label>
      <div className="flex items-baseline justify-between gap-4">
        <span className="font-mono text-stat-lg font-medium text-ink">{fmt(pct, 0)}</span>
        <span className="text-right text-caption text-ink-3">{favouredName ? `a favore di ${favouredName}` : "equilibrio"}</span>
      </div>
      <div className="relative h-2 bg-line-soft" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} aria-label="Mismatch score">
        <div
          className={cx("absolute inset-y-0 bg-edge", advantage === "b" ? "right-0" : "left-0")}
          style={{ width: `${pct}%`, opacity: confidence === "low" ? 0.5 : 1 }}
        />
        {[25, 50, 75].map((t) => (
          <span key={t} className="absolute inset-y-0 w-px bg-canvas" style={{ left: `${t}%` }} aria-hidden />
        ))}
      </div>
      <div className="flex justify-between font-mono text-label-sm text-ink-4" aria-hidden>
        <span>A</span>
        <span>B</span>
      </div>
    </div>
  );
}

export function conditionLabel(s: PlayerConditionalSplit): string {
  switch (s.condition_type) {
    case "vs_defender_archetype":
    case "vs_attacker_archetype":
      return `vs ${archetypeLabel(s.condition_value)}`;
    case "vs_line_height":
      return `vs ${LINE_HEIGHT_LABEL[s.condition_value]}`;
    case "vs_formation":
      return `vs ${s.condition_value}`;
  }
}

/** For defenders facing an attacker archetype, `dribbles_delta` counts times dribbled past. */
export function splitMetrics(s: PlayerConditionalSplit): Array<{ key: string; label: string; value: number | null; polarity: Polarity; digits: number }> {
  const asDefender = s.condition_type === "vs_attacker_archetype";
  return [
    { key: "rating", label: "Rating", value: s.rating_delta, polarity: "higher_is_better", digits: 2 },
    {
      key: "dribbles",
      label: asDefender ? "Dribbling subiti/90" : "Dribbling/90",
      value: s.dribbles_delta,
      polarity: asDefender ? "lower_is_better" : "higher_is_better",
      digits: 2,
    },
    { key: "duels", label: "Duelli vinti/90", value: s.duels_delta, polarity: "higher_is_better", digits: 2 },
  ];
}

function EvidenceRow({ split, name }: { split: PlayerConditionalSplit; name: string }) {
  const metrics = splitMetrics(split);
  const allNull = metrics.every((m) => m.value == null);
  const hasNegative = metrics.some((m) => deltaTone(m.value, m.polarity) === "vuln");
  return (
    <div className={cx("border-b border-line-soft py-3 pl-3 first:pt-0 last:border-b-0 last:pb-0", hasNegative ? "border-l border-l-vuln" : "border-l border-l-transparent")}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="text-body-md text-ink">
          <span className="font-medium">{name}</span> <span className="text-ink-3">{conditionLabel(split)}</span>
        </p>
        <span className="font-mono text-stat-sm text-ink-4">
          {fmtSample({ unit: "minutes", value: split.sample_minutes })}
          {split.confidence === "low" && " · bassa conf."}
        </span>
      </div>
      {allNull ? (
        <p className="mt-2 text-body-md text-ink-3">Dati insufficienti</p>
      ) : (
        <dl className="mt-2 grid grid-cols-3 gap-3">
          {metrics.map((m) => {
            const tone = deltaTone(m.value, m.polarity);
            return (
              <div key={m.key} className="flex flex-col gap-1">
                <dt className="truncate text-caption text-ink-3">{m.label}</dt>
                <dd className={cx("font-mono text-stat-md font-medium", m.value == null ? "text-ink-4" : TONE_TEXT[tone])}>{fmtSigned(m.value, m.digits)}</dd>
              </div>
            );
          })}
        </dl>
      )}
    </div>
  );
}

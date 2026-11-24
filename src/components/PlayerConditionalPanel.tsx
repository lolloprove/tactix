import type { BriefType, IsoDateTime, Match, Player, PlayerArchetype, PlayerConditionalSplit, PlayerObservation, Team } from "@/types/tactics";
import { CONDITION_TYPE_LABEL, POSITION_LABEL, TONE_TEXT, archetypeLabel, deltaTone, fmt, fmtSample, fmtSigned, metricLabel, surname } from "./format";
import { conditionLabel, splitMetrics } from "./MatchupMatrix";
import { Chip, ConfidenceChip, Label, cx } from "./primitives";

export type RadarAxis = {
  key: string;
  label: string;
  /** League percentile 0-100 for the player's role, from the pipeline. */
  percentile: number | null;
};

export type ObservationContext = {
  match: Match;
  home: Team;
  away: Team;
  brief_type: BriefType;
  model: string | null;
  generated_at: IsoDateTime;
};

export type PlayerConditionalPanelProps = {
  player: Player;
  team: Team;
  splits: PlayerConditionalSplit[];
  radar: RadarAxis[] | null;
  observation: PlayerObservation | null;
  observationContext: ObservationContext | null;
  matchupPlayer: Player | null;
};

export function PlayerConditionalPanel({ player, team, splits, radar, observation, observationContext, matchupPlayer }: PlayerConditionalPanelProps) {
  const nemesi = splits.filter((s) => deltaTone(s.rating_delta, "higher_is_better") === "vuln");
  const vittime = splits.filter((s) => deltaTone(s.rating_delta, "higher_is_better") === "edge");
  const rest = splits.filter((s) => deltaTone(s.rating_delta, "higher_is_better") === "neutral");
  const scores = (Object.entries(player.archetype_scores_json) as Array<[PlayerArchetype, number]>).sort((x, y) => y[1] - x[1]).slice(0, 3);

  return (
    <article className="flex flex-col border border-line">
      <header className="flex flex-col gap-4 border-b border-line p-4 md:flex-row md:items-end md:justify-between md:p-6">
        <div className="min-w-0">
          <Label>
            {team.name} · {POSITION_LABEL[player.primary_position]}
          </Label>
          <h2 className="mt-2 text-[28px] leading-8 font-medium tracking-[-0.03em] text-ink md:text-headline-lg">{player.name}</h2>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Chip tone="ink" selected>
              {archetypeLabel(player.archetype_primary)}
            </Chip>
            {player.archetype_secondary && <Chip>{archetypeLabel(player.archetype_secondary)}</Chip>}
          </div>
        </div>
        <dl className="flex gap-8">
          <div>
            <Label as="dt">Minuti</Label>
            <dd className="mt-1 font-mono text-stat-lg font-medium text-ink">
              {player.minutes_total}
              <span className="text-[14px] font-normal text-ink-3">′</span>
            </dd>
          </div>
          <div>
            <Label as="dt">Split</Label>
            <dd className="mt-1 font-mono text-stat-lg font-medium text-ink">{splits.length}</dd>
          </div>
        </dl>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <div className="flex flex-col gap-6 border-b border-line p-4 md:p-6 lg:border-r lg:border-b-0">
          <div>
            <Label>Profilo · percentile di ruolo</Label>
            {radar && radar.length >= 3 ? (
              <Radar axes={radar} />
            ) : (
              <p className="mt-4 text-body-md text-ink-3">Dati insufficienti</p>
            )}
          </div>
          <div>
            <Label>Affinità archetipo</Label>
            <dl className="mt-3 flex flex-col gap-2">
              {scores.map(([a, v]) => (
                <div key={a} className="grid grid-cols-[minmax(0,1fr)_96px_40px] items-center gap-3">
                  <dt className="truncate text-caption text-ink-2">{archetypeLabel(a)}</dt>
                  <div className="h-1 bg-line-soft" aria-hidden>
                    <div className={cx("h-full", a === player.archetype_primary ? "bg-ink" : "bg-ink-4")} style={{ width: `${v * 100}%` }} />
                  </div>
                  <dd className="text-right font-mono text-stat-sm font-medium text-ink">{fmt(v, 2)}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>

        <div className="flex flex-col p-4 md:p-6">
          <div className="grid grid-cols-1 gap-8 md:grid-cols-2 md:gap-6">
            <SplitColumn title="Nemesi" tone="vuln" empty="Nessun contesto sfavorevole con campione sufficiente." splits={nemesi} />
            <SplitColumn title="Vittime" tone="edge" empty="Nessun contesto favorevole con campione sufficiente." splits={vittime} />
          </div>
          {rest.length > 0 && (
            <ul className="mt-6 border-t border-line-soft pt-3">
              {rest.map((s) => (
                <li key={s.id} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 py-1">
                  <span className="text-caption text-ink-3">
                    {conditionLabel(s)} · {s.rating_delta == null ? "Dati insufficienti" : "nessuno scostamento"}
                  </span>
                  <span className="font-mono text-stat-sm text-ink-4">{fmtSample({ unit: "minutes", value: s.sample_minutes })}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <ObservationCard observation={observation} context={observationContext} matchupPlayer={matchupPlayer} />
    </article>
  );
}

function SplitColumn({ title, tone, empty, splits }: { title: string; tone: "edge" | "vuln"; empty: string; splits: PlayerConditionalSplit[] }) {
  return (
    <div>
      <div className="flex items-center gap-2 border-b border-line-strong pb-2">
        <span className={cx("size-1.5 rounded-full", tone === "edge" ? "bg-edge" : "bg-vuln")} aria-hidden />
        <Label className={tone === "edge" ? "text-edge" : "text-vuln"}>{title}</Label>
      </div>
      {splits.length === 0 ? (
        <p className="py-4 text-body-md text-ink-3">{empty}</p>
      ) : (
        <ul>
          {splits.map((s) => (
            <li key={s.id} className="flex flex-col gap-3 border-b border-line py-4 last:border-b-0">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-body-lg text-ink">{conditionLabel(s)}</p>
                  <p className="mt-1 text-caption text-ink-3">{CONDITION_TYPE_LABEL[s.condition_type]}</p>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <span className={cx("font-mono text-stat-md font-medium", TONE_TEXT[deltaTone(s.rating_delta, "higher_is_better")])}>{fmtSigned(s.rating_delta, 2)}</span>
                  <span className="font-mono text-label-sm uppercase text-ink-4">Rating</span>
                </div>
              </div>
              <dl className="flex flex-col gap-1">
                {splitMetrics(s)
                  .filter((m) => m.key !== "rating")
                  .map((m) => (
                    <div key={m.key} className="flex items-baseline justify-between gap-2">
                      <dt className="truncate text-caption text-ink-3">{m.label}</dt>
                      <dd className={cx("font-mono text-stat-sm font-medium", m.value == null ? "text-ink-4" : TONE_TEXT[deltaTone(m.value, m.polarity)])}>{fmtSigned(m.value, m.digits)}</dd>
                    </div>
                  ))}
              </dl>
              <ConfidenceChip className="self-start" confidence={s.confidence} sample={{ unit: "minutes", value: s.sample_minutes }} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const SENTIMENT = {
  positive: { label: "Positiva", tone: "edge" },
  negative: { label: "Negativa", tone: "vuln" },
  neutral: { label: "Neutra", tone: "neutral" },
} as const;

function ObservationCard({ observation, context, matchupPlayer }: { observation: PlayerObservation | null; context: ObservationContext | null; matchupPlayer: Player | null }) {
  if (!observation || !context) {
    return (
      <div className="border-t border-line p-4 md:p-6">
        <Label>Osservazione tattica AI</Label>
        <p className="mt-3 text-body-md text-ink-3">Nessuna osservazione per la prossima partita.</p>
      </div>
    );
  }
  const s = SENTIMENT[observation.sentiment];
  const generated = new Date(context.generated_at).toISOString().slice(0, 16).replace("T", " ");
  return (
    <div className="grid grid-cols-1 border-t border-line md:grid-cols-[minmax(0,1fr)_240px]">
      <div className="p-4 md:p-6">
        <div className="flex flex-wrap items-center gap-2">
          <Label>
            Osservazione tattica AI · {context.brief_type === "pre_match" ? "pre-partita" : "post-partita"}
          </Label>
          <Chip tone={s.tone}>{s.label}</Chip>
        </div>
        <p className="mt-4 max-w-[62ch] text-[18px] leading-[29px] text-ink-2 md:text-lead">{observation.observation}</p>
        <p className="mt-4 font-mono text-label-sm uppercase text-ink-4">
          {context.model ?? "modello n.d."} · {generated} UTC
        </p>
      </div>
      <dl className="flex flex-col gap-4 border-t border-line p-4 md:border-t-0 md:border-l md:p-6">
        <div>
          <Label as="dt">Partita</Label>
          <dd className="mt-1 font-mono text-stat-md font-medium text-ink">
            G{context.match.round} · {context.home.short_name}–{context.away.short_name}
          </dd>
        </div>
        <div>
          <Label as="dt">Duello</Label>
          <dd className="mt-1 text-body-lg text-ink">{matchupPlayer ? surname(matchupPlayer.name) : "—"}</dd>
        </div>
        <div>
          <Label as="dt">{metricLabel(observation.metric_key)}</Label>
          <dd className={cx("mt-1 font-mono text-stat-md font-medium", observation.metric_value == null ? "text-ink-4" : "text-ink")}>
            {observation.metric_key?.endsWith("_delta") ? fmtSigned(observation.metric_value, 2) : fmt(observation.metric_value, observation.metric_value != null && Number.isInteger(observation.metric_value) ? 0 : 2)}
          </dd>
        </div>
      </dl>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Radar (DESIGN.md §6): max 6 axes, benchmark = 50th percentile.
// ---------------------------------------------------------------------------

function Radar({ axes }: { axes: RadarAxis[] }) {
  const list = axes.slice(0, 6);
  const W = 520;
  const H = 340;
  const cx0 = W / 2;
  const cy0 = H / 2 + 4;
  const R = 104;
  const angle = (i: number) => -Math.PI / 2 + (i * 2 * Math.PI) / list.length;
  const pt = (i: number, r: number): [number, number] => [cx0 + Math.cos(angle(i)) * r, cy0 + Math.sin(angle(i)) * r];
  const poly = (rs: number[]) => rs.map((r, i) => pt(i, r).map((v) => v.toFixed(2)).join(",")).join(" ");
  const hasAll = list.every((a) => a.percentile != null);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mt-4 block h-auto w-full max-w-[520px]" role="img" aria-label={list.map((a) => `${a.label} ${a.percentile ?? "n.d."}° percentile`).join(", ")}>
      <title>Radar percentili di ruolo</title>
      {[25, 50, 75, 100].map((ring) => (
        <polygon key={ring} points={poly(list.map(() => (R * ring) / 100))} fill="none" className="stroke-line-soft" vectorEffect="non-scaling-stroke" />
      ))}
      {list.map((_, i) => {
        const [x, y] = pt(i, R);
        return <line key={i} x1={cx0} y1={cy0} x2={x} y2={y} className="stroke-line" vectorEffect="non-scaling-stroke" />;
      })}
      <polygon points={poly(list.map(() => R * 0.5))} fill="none" stroke="rgba(255,255,255,0.30)" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />
      {hasAll && (
        <polygon
          points={poly(list.map((a) => (R * (a.percentile ?? 0)) / 100))}
          className="fill-edge/12 stroke-edge"
          strokeWidth={1.5}
          strokeLinejoin="miter"
          vectorEffect="non-scaling-stroke"
        />
      )}
      {list.map((a, i) => {
        if (a.percentile == null) return null;
        const [x, y] = pt(i, (R * a.percentile) / 100);
        return <circle key={a.key} cx={x} cy={y} r={3} className="fill-edge stroke-canvas" strokeWidth={1.5} />;
      })}
      {list.map((a, i) => {
        const [x, y] = pt(i, R + 16);
        const c = Math.cos(angle(i));
        const anchor = Math.abs(c) < 0.2 ? "middle" : c > 0 ? "start" : "end";
        const s = Math.sin(angle(i));
        const dy = s < -0.5 ? -18 : s > 0.5 ? 8 : -6;
        return (
          <text key={a.key} x={x} y={y + dy} textAnchor={anchor} fontSize={16}>
            <tspan className="fill-ink">{a.label}</tspan>
            <tspan x={x} dy={18} className={cx("font-mono", a.percentile == null ? "fill-ink-4" : "fill-edge")} fontSize={15}>
              {a.percentile == null ? "—" : `${fmt(a.percentile, 0)}°`}
            </tspan>
          </text>
        );
      })}
    </svg>
  );
}

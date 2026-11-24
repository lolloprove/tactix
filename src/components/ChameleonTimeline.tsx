"use client";

import { useState } from "react";
import type { ConfidenceLevel, Formation, Team } from "@/types/tactics";
import { useElementWidth } from "./controls";
import { TONE_TEXT, deltaTone, fmt, fmtSigned } from "./format";
import { Chip, ConfidenceChip, Label, ModuleHeader, cx } from "./primitives";

export type TimelinePoint = {
  match_id: number;
  round: number;
  opponent: Team;
  venue: "home" | "away";
  formation: Formation | null;
  baseline_formation: Formation | null;
  ppda: number | null;
  avg_def_line_y: number | null;
  /** Match xG minus xGA for the subject team. */
  xg_diff: number | null;
  is_tactical_shift: boolean;
  shift_reason: string | null;
};

/** Efficiency windows around a shift, aggregated by the pipeline. */
export type ShiftComparison = {
  match_id: number;
  before: { from_round: number; to_round: number; matches: number; xg_diff: number | null };
  after: { from_round: number; to_round: number; matches: number; xg_diff: number | null };
  confidence: ConfidenceLevel;
};

export type ChameleonTimelineProps = {
  team: Team;
  points: TimelinePoint[];
  comparisons: ShiftComparison[];
  /** Season averages from the pipeline, drawn as dashed baselines. */
  baseline?: { ppda: number | null; avg_def_line_y: number | null };
};

const PAD = { left: 40, right: 16 };
const PANEL_H = 128;
const GAP = 40;
const TOP = 28;

export function ChameleonTimeline({ team, points, comparisons, baseline }: ChameleonTimelineProps) {
  const [ref, width] = useElementWidth<HTMLDivElement>();
  const sorted = [...points].sort((a, b) => a.round - b.round);
  const shifts = sorted.filter((p) => p.is_tactical_shift);
  const [selectedShift, setSelectedShift] = useState<number | null>(shifts.at(-1)?.match_id ?? null);
  const [hoverRound, setHoverRound] = useState<number | null>(null);

  const iw = Math.max(width - PAD.left - PAD.right, 0);
  const n = sorted.length;
  const step = n > 1 ? iw / (n - 1) : 0;
  const sx = (i: number) => PAD.left + (n > 1 ? i * step : iw / 2);
  const height = TOP + PANEL_H * 2 + GAP + 32;

  const lineVals = sorted.map((p) => p.avg_def_line_y).filter((v): v is number => v != null);
  const ppdaVals = sorted.map((p) => p.ppda).filter((v): v is number => v != null);
  const lineDom = domain([...lineVals, baseline?.avg_def_line_y ?? NaN], 5);
  const ppdaDom = domain([...ppdaVals, baseline?.ppda ?? NaN], 2);

  const panel1Top = TOP;
  const panel2Top = TOP + PANEL_H + GAP;
  // Line height: higher value at the top. PPDA: inverted, more intense (lower) at the top.
  const syLine = (v: number) => panel1Top + (1 - (v - lineDom[0]) / (lineDom[1] - lineDom[0])) * PANEL_H;
  const syPpda = (v: number) => panel2Top + ((v - ppdaDom[0]) / (ppdaDom[1] - ppdaDom[0])) * PANEL_H;

  const hoverIdx = hoverRound == null ? -1 : sorted.findIndex((p) => p.round === hoverRound);
  const readout = hoverIdx >= 0 ? sorted[hoverIdx] : (sorted.find((p) => p.match_id === selectedShift) ?? sorted.at(-1) ?? null);
  const shiftPoint = sorted.find((p) => p.match_id === selectedShift) ?? null;
  const comparison = comparisons.find((c) => c.match_id === selectedShift) ?? null;

  const labelEvery = width < 520 ? 2 : 1;

  return (
    <section className="flex flex-col gap-6">
      <ModuleHeader
        label={`Camaleonte · ${team.name}`}
        title="Assetto partita per partita"
        description="Altezza della linea difensiva e intensità del pressing, giornata per giornata. I marker segnano le partite in cui l'allenatore ha cambiato sistema."
        aside={
          <span className="flex items-center gap-2 font-mono text-label-sm font-medium uppercase text-ink-3">
            <span className="size-2 bg-shift" aria-hidden />
            Cambio tattico · {shifts.length}
          </span>
        }
      />

      {readout && (
        <div className="grid grid-cols-3 gap-x-6 gap-y-3 border-y border-line py-3 md:grid-cols-5" aria-live="polite">
          <Readout k="Giornata" v={`G${readout.round}`} />
          <Readout k="Avversario" v={`${readout.opponent.short_name} ${readout.venue === "home" ? "(C)" : "(T)"}`} />
          <Readout k="Modulo" v={readout.formation ?? "—"} accent={readout.is_tactical_shift} />
          <Readout k="Linea" v={fmt(readout.avg_def_line_y, 1)} />
          <Readout k="PPDA" v={fmt(readout.ppda, 1)} />
        </div>
      )}

      <div ref={ref} className="relative w-full" style={{ height }} onPointerLeave={() => setHoverRound(null)}>
        {width > 0 && n > 0 && (
          <svg width={width} height={height} role="img" aria-label={`Andamento di linea difensiva e PPDA di ${team.name}`} className="block">
            <title>Linea difensiva e PPDA per giornata</title>

            <PanelAxis top={panel1Top} title="Altezza linea" dom={lineDom} stepV={5} sy={syLine} iw={iw} />
            <PanelAxis top={panel2Top} title="PPDA · più intenso ↑" dom={ppdaDom} stepV={2} sy={syPpda} iw={iw} />

            {baseline?.avg_def_line_y != null && (
              <line x1={PAD.left} x2={PAD.left + iw} y1={syLine(baseline.avg_def_line_y)} y2={syLine(baseline.avg_def_line_y)} className="stroke-ink/30" strokeDasharray="3 3" />
            )}
            {baseline?.ppda != null && (
              <line x1={PAD.left} x2={PAD.left + iw} y1={syPpda(baseline.ppda)} y2={syPpda(baseline.ppda)} className="stroke-ink/30" strokeDasharray="3 3" />
            )}

            {shifts.map((p) => {
              const x = sx(sorted.indexOf(p));
              const active = p.match_id === selectedShift;
              return (
                <line
                  key={`s${p.match_id}`}
                  x1={x}
                  x2={x}
                  y1={TOP - 8}
                  y2={panel2Top + PANEL_H}
                  className="stroke-shift"
                  strokeOpacity={active ? 1 : 0.4}
                  strokeDasharray={active ? undefined : "2 2"}
                />
              );
            })}

            {hoverIdx >= 0 && <line x1={sx(hoverIdx)} x2={sx(hoverIdx)} y1={TOP} y2={panel2Top + PANEL_H} className="stroke-line-strong" />}

            <Series pts={sorted.map((p, i) => (p.avg_def_line_y == null ? null : [sx(i), syLine(p.avg_def_line_y)]))} />
            <Series pts={sorted.map((p, i) => (p.ppda == null ? null : [sx(i), syPpda(p.ppda)]))} />

            {sorted.map((p, i) =>
              i % labelEvery === 0 || p.is_tactical_shift ? (
                <text key={`r${p.round}`} x={sx(i)} y={height - 8} textAnchor="middle" className={cx("font-mono", p.is_tactical_shift ? "fill-shift" : "fill-ink-3")} fontSize={10}>
                  {p.round}
                </text>
              ) : null,
            )}

            {/* Hover columns */}
            {sorted.map((p, i) => (
              <rect
                key={`h${p.round}`}
                x={sx(i) - Math.max(step, 24) / 2}
                y={TOP}
                width={Math.max(step, 24)}
                height={panel2Top + PANEL_H - TOP}
                fill="transparent"
                onPointerEnter={() => setHoverRound(p.round)}
              />
            ))}

            {shifts.map((p) => {
              const x = sx(sorted.indexOf(p));
              const active = p.match_id === selectedShift;
              return (
                <g
                  key={`m${p.match_id}`}
                  role="button"
                  tabIndex={0}
                  aria-pressed={active}
                  aria-label={`Cambio tattico giornata ${p.round}: ${p.baseline_formation} → ${p.formation}`}
                  className="cursor-pointer outline-none"
                  onClick={() => setSelectedShift(p.match_id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelectedShift(p.match_id);
                    }
                  }}
                  onPointerEnter={() => setHoverRound(p.round)}
                >
                  <rect x={x - 12} y={TOP - 26} width={24} height={24} fill="transparent" />
                  <rect x={x - 5} y={TOP - 19} width={10} height={10} className={active ? "fill-shift" : "fill-canvas stroke-shift"} strokeWidth={1} />
                </g>
              );
            })}
          </svg>
        )}
      </div>

      <div className="border border-line">
        {shiftPoint && comparison ? (
          <ShiftBox point={shiftPoint} comparison={comparison} />
        ) : shiftPoint ? (
          <div className="p-4">
            <ShiftHead point={shiftPoint} />
            <p className="mt-4 text-body-md text-ink-3">Dati insufficienti per il confronto prima/dopo.</p>
          </div>
        ) : (
          <p className="p-4 text-body-md text-ink-3">Nessun cambio tattico registrato in questa stagione.</p>
        )}
      </div>
    </section>
  );
}

function domain(values: number[], step: number): [number, number] {
  const v = values.filter((x) => Number.isFinite(x));
  if (v.length === 0) return [0, step * 4];
  let lo = Math.floor(Math.min(...v) / step) * step;
  let hi = Math.ceil(Math.max(...v) / step) * step;
  if (hi - lo < step * 2) {
    lo -= step;
    hi += step;
  }
  return [lo, hi];
}

function PanelAxis({
  top,
  title,
  dom,
  stepV,
  sy,
  iw,
}: {
  top: number;
  title: string;
  dom: [number, number];
  stepV: number;
  sy: (v: number) => number;
  iw: number;
}) {
  const ts: number[] = [];
  for (let v = dom[0]; v <= dom[1] + 1e-9; v += stepV) ts.push(v);
  return (
    <g>
      <text x={PAD.left} y={top - 10} className="fill-ink-3 font-mono uppercase" fontSize={10} letterSpacing="0.1em" fontWeight={500}>
        {title}
      </text>
      {ts.map((t) => (
        <g key={t}>
          <line x1={PAD.left} x2={PAD.left + iw} y1={sy(t)} y2={sy(t)} className="stroke-line-soft" />
          <text x={PAD.left - 8} y={sy(t)} dy="0.32em" textAnchor="end" className="fill-ink-3 font-mono" fontSize={10}>
            {fmt(t, 0)}
          </text>
        </g>
      ))}
    </g>
  );
}

function Series({ pts }: { pts: Array<[number, number] | null> }) {
  const segments: Array<Array<[number, number]>> = [];
  let cur: Array<[number, number]> = [];
  for (const p of pts) {
    if (p == null) {
      if (cur.length) segments.push(cur);
      cur = [];
    } else cur.push(p);
  }
  if (cur.length) segments.push(cur);
  return (
    <g>
      {segments.map((s, i) => (
        <polyline key={i} points={s.map(([x, y]) => `${x},${y}`).join(" ")} fill="none" className="stroke-ink" strokeWidth={1.5} strokeLinejoin="miter" />
      ))}
      {pts.map((p, i) => (p ? <circle key={i} cx={p[0]} cy={p[1]} r={2.5} className="fill-ink" /> : null))}
    </g>
  );
}

function Readout({ k, v, accent = false }: { k: string; v: string; accent?: boolean }) {
  return (
    <div className="flex flex-col gap-1">
      <Label>{k}</Label>
      <span className={cx("font-mono text-stat-md font-medium", accent ? "text-shift" : "text-ink")}>{v}</span>
    </div>
  );
}

function ShiftHead({ point }: { point: TimelinePoint }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Chip tone="shift">Cambio tattico</Chip>
        <span className="font-mono text-stat-md font-medium text-ink">
          {point.baseline_formation ?? "—"} <span className="text-shift">→</span> {point.formation ?? "—"}
        </span>
        <span className="font-mono text-stat-sm text-ink-4">
          G{point.round} · vs {point.opponent.short_name}
        </span>
      </div>
      {point.shift_reason && <p className="max-w-[62ch] text-body-md text-ink-2">{point.shift_reason}</p>}
    </div>
  );
}

function ShiftBox({ point, comparison }: { point: TimelinePoint; comparison: ShiftComparison }) {
  const { before, after } = comparison;
  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr_1fr]">
      <div className="border-b border-line p-4 lg:border-r lg:border-b-0">
        <ShiftHead point={point} />
        <div className="mt-4">
          <ConfidenceChip confidence={comparison.confidence} sample={{ unit: "matches", value: before.matches + after.matches }} />
        </div>
      </div>
      <Window title="Prima" w={before} />
      <Window title="Dopo" w={after} last />
    </div>
  );
}

function Window({ title, w, last = false }: { title: string; w: ShiftComparison["before"]; last?: boolean }) {
  const range = w.from_round === w.to_round ? `G${w.from_round}` : `G${w.from_round}–G${w.to_round}`;
  return (
    <div className={cx("flex flex-col justify-between gap-4 p-4", !last && "border-b border-line lg:border-r lg:border-b-0")}>
      <div className="flex items-baseline justify-between gap-4">
        <Label>{title}</Label>
        <span className="font-mono text-stat-sm text-ink-4">
          {range} · {w.matches} P
        </span>
      </div>
      <div className="flex items-baseline justify-between gap-4">
        <span className="text-caption text-ink-3">xG diff / partita</span>
        {w.xg_diff == null ? (
          <span className="text-body-md text-ink-3">Dati insufficienti</span>
        ) : (
          <span className={cx("font-mono text-stat-lg font-medium", TONE_TEXT[deltaTone(w.xg_diff, "higher_is_better")])}>{fmtSigned(w.xg_diff, 2)}</span>
        )}
      </div>
    </div>
  );
}

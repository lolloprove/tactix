"use client";

import { useState } from "react";
import type { ConfidenceLevel, Team } from "@/types/tactics";
import { useElementWidth } from "./controls";
import { fmt } from "./format";
import { Label, ModuleHeader, cx } from "./primitives";

export type TeamTacticalPoint = {
  team: Team;
  /** Average defensive line height, 0-100 on the length axis. */
  def_line_y: number | null;
  /** Passes allowed per defensive action; lower = more intense press. */
  ppda: number | null;
  sample_matches: number;
  confidence?: ConfidenceLevel;
};

export type LeagueTacticalScatterProps = {
  points: TeamTacticalPoint[];
  /** League reference values that split the quadrants (supplied by the pipeline). Defaults to the axis midpoints. */
  reference?: { def_line_y: number; ppda: number };
  defaultSelectedTeamId?: number;
};

const QUADRANTS = {
  topRight: "Pressing alto",
  bottomRight: "Controllo posizionale",
  topLeft: "Blocco basso & transizione",
  bottomLeft: "Passivo",
} as const;

const PAD = { top: 24, right: 16, bottom: 48, left: 48 };

function niceDomain(values: number[], fallback: [number, number], step: number): [number, number] {
  if (values.length === 0) return fallback;
  const lo = Math.min(fallback[0], ...values);
  const hi = Math.max(fallback[1], ...values);
  return [Math.floor(lo / step) * step, Math.ceil(hi / step) * step];
}

function ticks([lo, hi]: [number, number], step: number): number[] {
  const out: number[] = [];
  for (let v = lo; v <= hi + 1e-9; v += step) out.push(Number(v.toFixed(4)));
  return out;
}

export function LeagueTacticalScatter({ points, reference, defaultSelectedTeamId }: LeagueTacticalScatterProps) {
  const [ref, width] = useElementWidth<HTMLDivElement>();
  const [selected, setSelected] = useState<number | null>(defaultSelectedTeamId ?? null);
  const [hovered, setHovered] = useState<number | null>(null);

  const plotted = points.filter((p): p is TeamTacticalPoint & { def_line_y: number; ppda: number } => p.def_line_y != null && p.ppda != null);
  const missing = points.filter((p) => p.def_line_y == null || p.ppda == null);

  const xDomain = niceDomain(plotted.map((p) => p.def_line_y), [32, 52], 4);
  const yDomain = niceDomain(plotted.map((p) => p.ppda), [7, 15], 2);
  const refX = reference?.def_line_y ?? (xDomain[0] + xDomain[1]) / 2;
  const refY = reference?.ppda ?? (yDomain[0] + yDomain[1]) / 2;

  const height = width === 0 ? 0 : Math.round(width < 560 ? Math.max(width, 320) : Math.min(width * 0.62, 560));
  const iw = Math.max(width - PAD.left - PAD.right, 0);
  const ih = Math.max(height - PAD.top - PAD.bottom, 0);
  const sx = (v: number) => PAD.left + ((v - xDomain[0]) / (xDomain[1] - xDomain[0])) * iw;
  // Inverted: low PPDA (intense press) at the top.
  const sy = (v: number) => PAD.top + ((v - yDomain[0]) / (yDomain[1] - yDomain[0])) * ih;

  const focusId = hovered ?? selected;
  const focus = plotted.find((p) => p.team.id === hovered) ?? null;
  const sel = plotted.find((p) => p.team.id === selected) ?? null;
  const quadrantOf = (p: { def_line_y: number; ppda: number }) =>
    p.def_line_y >= refX ? (p.ppda <= refY ? QUADRANTS.topRight : QUADRANTS.bottomRight) : p.ppda <= refY ? QUADRANTS.topLeft : QUADRANTS.bottomLeft;
  const compact = width < 560;

  // Greedy label placement: focused/selected first, then right or left of the point, else hidden.
  const labels = new Map<number, { x: number; anchor: "start" | "end" }>();
  {
    const boxes = plotted.map((p) => ({ id: p.team.id, x0: sx(p.def_line_y) - 5, x1: sx(p.def_line_y) + 5, y0: sy(p.ppda) - 5, y1: sy(p.ppda) + 5 }));
    const placed: Array<{ x0: number; x1: number; y0: number; y1: number }> = [];
    const hits = (b: { x0: number; x1: number; y0: number; y1: number }, own: number) =>
      placed.some((o) => b.x0 < o.x1 && b.x1 > o.x0 && b.y0 < o.y1 && b.y1 > o.y0) ||
      boxes.some((o) => o.id !== own && b.x0 < o.x1 && b.x1 > o.x0 && b.y0 < o.y1 && b.y1 > o.y0);
    const rank = (id: number) => (id === focusId ? 0 : id === selected ? 1 : 2);
    for (const p of [...plotted].sort((a, b) => rank(a.team.id) - rank(b.team.id))) {
      const x = sx(p.def_line_y);
      const y = sy(p.ppda);
      const w = p.team.short_name.length * 7.5 + 2;
      const options = [
        { x: x + 12, anchor: "start" as const, b: { x0: x + 12, x1: x + 12 + w, y0: y - 6, y1: y + 6 } },
        { x: x - 12, anchor: "end" as const, b: { x0: x - 12 - w, x1: x - 12, y0: y - 6, y1: y + 6 } },
      ].filter((o) => o.b.x0 >= PAD.left && o.b.x1 <= PAD.left + iw);
      const pick = options.find((o) => !hits(o.b, p.team.id)) ?? (rank(p.team.id) < 2 ? options[0] : undefined);
      if (pick) {
        placed.push(pick.b);
        labels.set(p.team.id, { x: pick.x, anchor: pick.anchor });
      }
    }
  }

  return (
    <section className="flex flex-col gap-6">
      <ModuleHeader
        label="Classifica tattica · Serie A"
        title="Identità difensiva delle squadre"
        description="Altezza media della linea difensiva contro intensità del pressing. L'asse PPDA è invertito: più in alto, pressing più aggressivo."
      />

      <div ref={ref} className="relative w-full" style={{ minHeight: 320 }}>
        {width > 0 && (
          <svg width={width} height={height} role="img" aria-label="Scatter: altezza della linea difensiva contro PPDA per squadra" className="block">
            <title>Altezza linea difensiva vs PPDA</title>

            {ticks(yDomain, 2).map((t) => (
              <g key={`y${t}`}>
                <line x1={PAD.left} x2={PAD.left + iw} y1={sy(t)} y2={sy(t)} className="stroke-line-soft" />
                <text x={PAD.left - 8} y={sy(t)} dy="0.32em" textAnchor="end" className="fill-ink-3 font-mono" fontSize={10}>
                  {fmt(t, 0)}
                </text>
              </g>
            ))}
            {ticks(xDomain, 4).map((t) => (
              <text key={`x${t}`} x={sx(t)} y={PAD.top + ih + 18} textAnchor="middle" className="fill-ink-3 font-mono" fontSize={10}>
                {fmt(t, 0)}
              </text>
            ))}

            <line x1={sx(refX)} x2={sx(refX)} y1={PAD.top} y2={PAD.top + ih} className="stroke-line-strong" />
            <line x1={PAD.left} x2={PAD.left + iw} y1={sy(refY)} y2={sy(refY)} className="stroke-line-strong" />

            <g className="fill-ink-4 font-mono uppercase" fontSize={10} letterSpacing="0.1em" fontWeight={500}>
              <text x={PAD.left + iw - 8} y={PAD.top + 16} textAnchor="end">{QUADRANTS.topRight}</text>
              {compact ? (
                <text x={PAD.left + 8} y={PAD.top + 16}>
                  <tspan>Blocco basso &amp;</tspan>
                  <tspan x={PAD.left + 8} dy={13}>
                    transizione
                  </tspan>
                </text>
              ) : (
                <text x={PAD.left + 8} y={PAD.top + 16}>{QUADRANTS.topLeft}</text>
              )}
              <text x={PAD.left + iw - 8} y={PAD.top + ih - 10} textAnchor="end">{QUADRANTS.bottomRight}</text>
              <text x={PAD.left + 8} y={PAD.top + ih - 10}>{QUADRANTS.bottomLeft}</text>
            </g>

            <text x={PAD.left + iw} y={height - 8} textAnchor="end" className="fill-ink-3 font-mono uppercase" fontSize={10} letterSpacing="0.1em" fontWeight={500}>
              Linea difensiva più alta →
            </text>
            <text
              transform={`translate(12 ${PAD.top}) rotate(-90)`}
              textAnchor="end"
              className="fill-ink-3 font-mono uppercase"
              fontSize={10}
              letterSpacing="0.1em"
              fontWeight={500}
            >
              {compact ? "PPDA ↑ pressing" : "PPDA · pressing più intenso ↑"}
            </text>

            {plotted.map((p) => {
              const isSel = p.team.id === selected;
              const isFocus = p.team.id === focusId;
              const low = p.confidence === "low";
              const x = sx(p.def_line_y);
              const y = sy(p.ppda);
              const label = labels.get(p.team.id);
              return (
                <g
                  key={p.team.id}
                  role="button"
                  tabIndex={0}
                  aria-pressed={isSel}
                  aria-label={`${p.team.name}: linea ${fmt(p.def_line_y, 1)}, PPDA ${fmt(p.ppda, 1)}`}
                  className="cursor-pointer outline-none"
                  onPointerEnter={() => setHovered(p.team.id)}
                  onPointerLeave={() => setHovered(null)}
                  onFocus={() => setHovered(p.team.id)}
                  onBlur={() => setHovered(null)}
                  onClick={() => setSelected(isSel ? null : p.team.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelected(isSel ? null : p.team.id);
                    }
                  }}
                >
                  <circle cx={x} cy={y} r={14} fill="transparent" />
                  {isSel && <circle cx={x} cy={y} r={9} fill="none" className="stroke-edge" />}
                  <circle
                    cx={x}
                    cy={y}
                    r={4}
                    className={cx(isSel ? "fill-edge" : low ? "fill-canvas stroke-ink" : "fill-ink", isFocus && !isSel && "stroke-ink")}
                    strokeDasharray={low ? "2 2" : undefined}
                    strokeWidth={low || isFocus ? 1 : 0}
                  />
                  {label && (
                    <text
                      x={label.x}
                      y={y}
                      dy="0.32em"
                      textAnchor={label.anchor}
                      className={cx("font-mono", isSel ? "fill-edge" : isFocus ? "fill-ink" : "fill-ink-3")}
                      fontSize={10}
                      letterSpacing="0.1em"
                      fontWeight={500}
                    >
                      {p.team.short_name}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        )}

        {focus && width > 0 && (
          <div
            role="status"
            className="pointer-events-none absolute border border-ink bg-canvas px-3 py-2"
            style={{
              left: Math.min(Math.max(sx(focus.def_line_y) - 90, 0), width - 180),
              top: sy(focus.ppda) > height / 2 ? sy(focus.ppda) - 108 : sy(focus.ppda) + 16,
              width: 180,
            }}
          >
            <Label>{focus.team.name}</Label>
            <dl className="mt-2 flex flex-col gap-1">
              <Row k="Linea difensiva" v={fmt(focus.def_line_y, 1)} />
              <Row k="PPDA" v={fmt(focus.ppda, 1)} />
              <Row k="Campione" v={`${focus.sample_matches} P`} muted />
            </dl>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-x-6 gap-y-3 border-y border-line py-3 md:grid-cols-4" aria-live="polite">
        {sel ? (
          <>
            <Readout k="Squadra" v={sel.team.name} />
            <Readout k="Linea difensiva" v={fmt(sel.def_line_y, 1)} mono />
            <Readout k="PPDA" v={fmt(sel.ppda, 1)} mono />
            <Readout k="Quadrante" v={quadrantOf(sel)} />
          </>
        ) : (
          <p className="col-span-full text-body-md text-ink-3">Seleziona una squadra per evidenziarla.</p>
        )}
      </div>

      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between md:gap-8">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Seleziona squadra">
          {points.map((p) => {
            const isSel = p.team.id === selected;
            const off = p.def_line_y == null || p.ppda == null;
            return (
              <button
                key={p.team.id}
                type="button"
                disabled={off}
                aria-pressed={isSel}
                onClick={() => setSelected(isSel ? null : p.team.id)}
                className={cx(
                  "h-8 border px-3 font-mono text-label-sm font-medium uppercase",
                  isSel ? "border-edge bg-edge/12 text-edge" : "border-line text-ink-3 hover:border-ink hover:text-ink",
                  off && "cursor-not-allowed opacity-40",
                )}
              >
                {p.team.short_name}
              </button>
            );
          })}
        </div>
        <p className="flex shrink-0 flex-col gap-1 font-mono text-label-sm font-medium uppercase text-ink-4 md:items-end md:pt-2">
          <span>
            Riferimento lega: linea {fmt(refX, 1)} · PPDA {fmt(refY, 1)}
          </span>
          {missing.length > 0 && <span>{missing.length} squadra senza dati</span>}
        </p>
      </div>
    </section>
  );
}

function Readout({ k, v, mono = false }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <Label>{k}</Label>
      <span className={cx("truncate font-medium text-ink", mono ? "font-mono text-stat-md" : "text-body-lg")}>{v}</span>
    </div>
  );
}

function Row({ k, v, muted = false }: { k: string; v: string; muted?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className="text-caption text-ink-3">{k}</dt>
      <dd className={cx("font-mono font-medium", muted ? "text-stat-sm text-ink-4" : "text-stat-md text-ink")}>{v}</dd>
    </div>
  );
}

import type { ReactNode } from "react";
import type { ConfidenceLevel, SampleSize } from "@/types/tactics";
import { CONFIDENCE_LABEL, TONE_TEXT, deltaTone, fmtSample, fmtSigned, type Polarity, type Tone } from "./format";

export function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

export function Label({ children, className, as: Tag = "p" }: { children: ReactNode; className?: string; as?: "p" | "span" | "h3" | "dt" }) {
  return <Tag className={cx("font-mono text-label font-medium uppercase text-ink-3", className)}>{children}</Tag>;
}

const CHIP_TONE: Record<Tone | "shift" | "ink", string> = {
  neutral: "border-line text-ink-3",
  edge: "border-edge text-edge",
  vuln: "border-vuln text-vuln",
  shift: "border-shift text-shift",
  ink: "border-ink text-ink",
};

const CHIP_SELECTED: Record<Tone | "shift" | "ink", string> = {
  neutral: "bg-ink/12",
  edge: "bg-edge/12",
  vuln: "bg-vuln/12",
  shift: "bg-shift/12",
  ink: "bg-ink/12",
};

export function Chip({
  children,
  tone = "neutral",
  selected = false,
  dashed = false,
  className,
}: {
  children: ReactNode;
  tone?: Tone | "shift" | "ink";
  selected?: boolean;
  dashed?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cx(
        "inline-flex h-6 shrink-0 items-center whitespace-nowrap border px-2 font-mono text-label-sm font-medium uppercase",
        dashed && "border-dashed",
        CHIP_TONE[tone],
        selected && CHIP_SELECTED[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/** Transparent sample-confidence chip; `low` is dashed like low-confidence geometry. */
export function ConfidenceChip({ confidence, sample, className }: { confidence: ConfidenceLevel; sample?: SampleSize; className?: string }) {
  return (
    <span
      className={cx(
        "inline-flex h-6 shrink-0 items-center gap-2 whitespace-nowrap border px-2 font-mono text-label-sm font-medium uppercase",
        confidence === "low" ? "border-dashed border-line-strong text-ink-3" : "border-line text-ink-3",
        confidence === "high" && "text-ink-2",
        className,
      )}
      title={`Confidenza ${confidence === "high" ? "alta" : confidence === "medium" ? "media" : "bassa"}`}
    >
      {CONFIDENCE_LABEL[confidence]}
      {sample && <span className="text-ink-4">{fmtSample(sample)}</span>}
    </span>
  );
}

export function Delta({
  value,
  polarity = "higher_is_better",
  digits = 2,
  className,
}: {
  value: number | null | undefined;
  polarity?: Polarity;
  digits?: number;
  className?: string;
}) {
  const tone = deltaTone(value, polarity);
  return (
    <span className={cx("font-mono text-stat-sm font-medium", value == null ? "text-ink-4" : TONE_TEXT[tone], className)}>
      {fmtSigned(value, digits)}
    </span>
  );
}

export function ModuleHeader({
  label,
  title,
  description,
  aside,
}: {
  label: string;
  title: string;
  description?: string;
  aside?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-4 border-b border-line-strong pb-4 md:flex-row md:items-end md:justify-between md:gap-8">
      <div className="min-w-0">
        <Label>{label}</Label>
        <h2 className="mt-2 text-headline-md font-medium text-ink">{title}</h2>
        {description && <p className="mt-2 max-w-[62ch] text-caption text-ink-3">{description}</p>}
      </div>
      {aside && <div className="flex shrink-0 flex-wrap items-center gap-2">{aside}</div>}
    </header>
  );
}

export function Insufficient({ sample, children }: { sample?: SampleSize; children?: ReactNode }) {
  return (
    <p className="text-body-md text-ink-3">
      {children ?? "Dati insufficienti"}
      {sample && <span className="ml-2 font-mono text-stat-sm text-ink-4">{fmtSample(sample)}</span>}
    </p>
  );
}

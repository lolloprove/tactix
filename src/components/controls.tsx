"use client";

import { useEffect, useRef, useState, type RefObject } from "react";
import { cx } from "./primitives";

export function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: ReadonlyArray<{ value: T; label: string }>;
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex border border-line">
      {options.map((o, i) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.value)}
            className={cx(
              "h-8 px-3 font-mono text-label-sm font-medium uppercase outline-none",
              i > 0 && "border-l border-line",
              active ? "bg-ink text-canvas" : "text-ink-3 hover:bg-hover hover:text-ink",
              "focus-visible:outline-1 focus-visible:-outline-offset-2 focus-visible:outline-edge",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

/** Tracks the content-box width of an element; 0 until mounted. */
export function useElementWidth<T extends HTMLElement>(): [RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width];
}

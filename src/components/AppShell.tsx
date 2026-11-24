"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import type { Player, Team } from "@/types/tactics";
import { archetypeLabel } from "./format";
import { cx } from "./primitives";

export type NavKey = "giornata" | "squadre" | "giocatori" | "classifica";

const NAV: Array<{ key: NavKey; label: string; href: string }> = [
  { key: "giornata", label: "Giornata", href: "/giornata" },
  { key: "squadre", label: "Squadre", href: "/squadre" },
  { key: "giocatori", label: "Giocatori", href: "/giocatori" },
  { key: "classifica", label: "Classifica tattica", href: "/classifica-tattica" },
];

export type AppShellProps = {
  children: ReactNode;
  season: string;
  teams: Team[];
  players: Player[];
  currentRound: number;
  /** Rounds that have data; others are shown but disabled. */
  availableRounds: number[];
  /** Path the round selector links to, with `?giornata=N` appended. */
  roundBasePath: string;
  totalRounds?: number;
  active?: NavKey;
};

export function AppShell({ children, season, teams, players, currentRound, availableRounds, roundBasePath, totalRounds = 38, active = "giornata" }: AppShellProps) {
  const [searchOpen, setSearchOpen] = useState(false);

  return (
    <div className="flex min-h-full flex-1 flex-col">
      <header className="border-b border-line">
        <div className="mx-auto w-full max-w-[1400px] px-4 pt-6 sm:px-8 lg:px-14 lg:pt-8">
          <div className="flex items-center justify-between gap-4 lg:grid lg:grid-cols-4">
            <Link href="/" className="flex items-baseline gap-3">
              <span className="text-[17px] font-medium tracking-[-0.03em] text-ink">Tactix</span>
              <span className="font-mono text-label-sm font-medium uppercase text-ink-4">Serie A {season}</span>
            </Link>

            <nav aria-label="Principale" className="hidden justify-center gap-8 lg:col-span-2 lg:flex">
              {NAV.map((n) => (
                <NavLink key={n.key} item={n} active={n.key === active} />
              ))}
            </nav>

            <div className="hidden justify-end lg:flex">
              <SearchBox teams={teams} players={players} />
            </div>

            <button
              type="button"
              aria-expanded={searchOpen}
              onClick={() => setSearchOpen((o) => !o)}
              className="h-8 border border-line px-3 font-mono text-label-sm font-medium uppercase text-ink-3 hover:border-ink hover:text-ink lg:hidden"
            >
              {searchOpen ? "Chiudi" : "Cerca"}
            </button>
          </div>

          {searchOpen && (
            <div className="mt-4 lg:hidden">
              <SearchBox teams={teams} players={players} autoFocus />
            </div>
          )}

          <nav aria-label="Principale" className="-mx-4 mt-4 flex gap-6 overflow-x-auto px-4 pb-1 [scrollbar-width:none] sm:-mx-8 sm:px-8 lg:hidden">
            {NAV.map((n) => (
              <NavLink key={n.key} item={n} active={n.key === active} />
            ))}
          </nav>
        </div>

        <RoundStrip current={currentRound} available={availableRounds} total={totalRounds} basePath={roundBasePath} />
      </header>

      <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 sm:px-8 lg:px-14">{children}</main>

      <footer className="border-t border-line">
        <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-2 px-4 py-8 text-caption text-ink-3 sm:flex-row sm:justify-between sm:px-8 lg:px-14">
          <span>Tactix · Analisi tattica Serie A</span>
          <span className="font-mono text-label-sm uppercase text-ink-4">Campione e confidenza esposti su ogni dato condizionato</span>
        </div>
      </footer>
    </div>
  );
}

function NavLink({ item, active }: { item: (typeof NAV)[number]; active: boolean }) {
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cx(
        "shrink-0 py-1 text-caption whitespace-nowrap underline-offset-4 transition-opacity duration-200",
        active ? "text-ink underline decoration-1" : "text-ink-3 hover:text-ink hover:underline hover:decoration-1",
      )}
    >
      {item.label}
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Round selector
// ---------------------------------------------------------------------------

function RoundStrip({ current, available, total, basePath }: { current: number; available: number[]; total: number; basePath: string }) {
  const listRef = useRef<HTMLOListElement>(null);
  const avail = new Set(available);
  const prev = [...available].filter((r) => r < current).sort((a, b) => b - a)[0];
  const next = [...available].filter((r) => r > current).sort((a, b) => a - b)[0];
  const href = (r: number) => `${basePath}?giornata=${r}`;

  useEffect(() => {
    const list = listRef.current;
    const el = list?.querySelector<HTMLElement>("[aria-current='true']");
    if (!list || !el) return;
    const offset = el.getBoundingClientRect().left - list.getBoundingClientRect().left + list.scrollLeft;
    list.scrollLeft = offset - list.clientWidth / 2 + el.clientWidth / 2;
  }, [current]);

  const stepCls = "flex h-8 w-8 shrink-0 items-center justify-center border border-line font-mono text-stat-md";

  return (
    <div className="mx-auto mt-4 flex w-full max-w-[1400px] items-center gap-3 px-4 pb-4 sm:px-8 lg:mt-6 lg:px-14">
      <span className="hidden shrink-0 font-mono text-label font-medium uppercase text-ink-3 sm:inline">Giornata</span>
      {prev != null ? (
        <Link href={href(prev)} aria-label={`Giornata ${prev}`} className={cx(stepCls, "text-ink hover:border-ink")}>
          ‹
        </Link>
      ) : (
        <span aria-hidden className={cx(stepCls, "text-ink-5")}>
          ‹
        </span>
      )}
      <ol ref={listRef} aria-label="Seleziona giornata" className="flex min-w-0 flex-1 overflow-x-auto [scrollbar-width:none]">
        {Array.from({ length: total }, (_, i) => i + 1).map((r) => {
          const isCur = r === current;
          const cls = cx(
            "flex h-8 min-w-7 items-center justify-center border-y border-r border-line px-1 font-mono text-stat-sm font-medium",
            r === 1 && "border-l",
            isCur && "border-ink bg-ink text-canvas",
          );
          return (
            <li key={r} className="flex shrink-0" aria-current={isCur ? "true" : undefined}>
              {avail.has(r) && !isCur ? (
                <Link href={href(r)} className={cx(cls, "text-ink hover:bg-hover")}>
                  {String(r).padStart(2, "0")}
                </Link>
              ) : (
                <span className={cx(cls, !isCur && "text-ink-5")} aria-disabled={!isCur}>
                  {String(r).padStart(2, "0")}
                </span>
              )}
            </li>
          );
        })}
      </ol>
      {next != null ? (
        <Link href={href(next)} aria-label={`Giornata ${next}`} className={cx(stepCls, "text-ink hover:border-ink")}>
          ›
        </Link>
      ) : (
        <span aria-hidden className={cx(stepCls, "text-ink-5")}>
          ›
        </span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

type Result = { key: string; href: string; title: string; meta: string; group: "Squadre" | "Giocatori" };

const normalize = (s: string) =>
  s
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();

function SearchBox({ teams, players, autoFocus = false }: { teams: Team[]; players: Player[]; autoFocus?: boolean }) {
  const router = useRouter();
  const id = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);

  const teamById = useMemo(() => new Map(teams.map((t) => [t.id, t])), [teams]);

  const results = useMemo<Result[]>(() => {
    const n = normalize(q.trim());
    if (!n) return [];
    const ts = teams
      .filter((t) => normalize(t.name).includes(n) || normalize(t.short_name).includes(n))
      .slice(0, 4)
      .map<Result>((t) => ({ key: `t${t.id}`, href: `/squadre/${t.slug}`, title: t.name, meta: t.short_name, group: "Squadre" }));
    const ps = players
      .filter((p) => normalize(p.name).includes(n))
      .slice(0, 6)
      .map<Result>((p) => ({
        key: `p${p.id}`,
        href: `/giocatori/${p.id}`,
        title: p.name,
        meta: `${teamById.get(p.team_id ?? -1)?.short_name ?? "—"} · ${archetypeLabel(p.archetype_primary)}`,
        group: "Giocatori",
      }));
    return [...ts, ...ps];
  }, [q, teams, players, teamById]);

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (e.key === "/" && t?.tagName !== "INPUT" && t?.tagName !== "TEXTAREA") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [autoFocus]);

  const go = (r: Result) => {
    setOpen(false);
    setQ("");
    router.push(r.href);
  };

  const showList = open && q.trim().length > 0;

  return (
    <div className="relative w-full lg:w-[280px]">
      <label htmlFor={id} className="sr-only">
        Cerca squadra o giocatore
      </label>
      <input
        ref={inputRef}
        id={id}
        type="search"
        role="combobox"
        aria-expanded={showList}
        aria-controls={`${id}-list`}
        aria-activedescendant={showList && results[cursor] ? `${id}-${results[cursor].key}` : undefined}
        autoComplete="off"
        placeholder="Cerca squadra o giocatore"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setCursor(0);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => {
          if (!showList) return;
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setCursor((c) => Math.min(c + 1, results.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setCursor((c) => Math.max(c - 1, 0));
          } else if (e.key === "Enter" && results[cursor]) {
            e.preventDefault();
            go(results[cursor]);
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
        className="h-9 w-full border border-line bg-inset px-3 pr-10 text-caption text-ink outline-none placeholder:text-ink-5 focus:border-ink [&::-webkit-search-cancel-button]:hidden"
      />
      <kbd className="pointer-events-none absolute top-1/2 right-2 hidden -translate-y-1/2 border border-line px-1.5 font-mono text-label-sm text-ink-4 lg:block">/</kbd>

      {showList && (
        <ul id={`${id}-list`} role="listbox" className="absolute top-full right-0 left-0 z-30 mt-1 max-h-[360px] overflow-y-auto border border-ink bg-inset">
          {results.length === 0 ? (
            <li className="px-3 py-3 text-caption text-ink-3">Nessun risultato</li>
          ) : (
            results.map((r, i) => (
              <li key={r.key} role="presentation">
                {(i === 0 || results[i - 1].group !== r.group) && (
                  <p className="border-b border-line-soft px-3 pt-3 pb-2 font-mono text-label-sm font-medium uppercase text-ink-4">{r.group}</p>
                )}
                <button
                  type="button"
                  id={`${id}-${r.key}`}
                  role="option"
                  aria-selected={i === cursor}
                  onMouseDown={(e) => e.preventDefault()}
                  onMouseEnter={() => setCursor(i)}
                  onClick={() => go(r)}
                  className={cx("flex w-full items-baseline justify-between gap-4 px-3 py-2 text-left", i === cursor && "bg-hover")}
                >
                  <span className="truncate text-caption text-ink">{r.title}</span>
                  <span className="shrink-0 font-mono text-label-sm uppercase text-ink-3">{r.meta}</span>
                </button>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}

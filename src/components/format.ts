import type {
  ConfidenceLevel,
  LineHeight,
  PlayerArchetype,
  PlayerConditionType,
  PlayerPosition,
  SampleSize,
  XgaShotZone,
  ZoneCorridor,
} from "@/types/tactics";

/** U+2212: same advance width as "+" in the mono face. */
export const MINUS = "\u2212";
export const MISSING = "—";

export function fmt(value: number | null | undefined, digits: number): string {
  if (value == null || Number.isNaN(value)) return MISSING;
  return value.toFixed(digits).replace("-", MINUS);
}

export function fmtSigned(value: number | null | undefined, digits: number): string {
  if (value == null || Number.isNaN(value)) return MISSING;
  const abs = Math.abs(value).toFixed(digits);
  if (Number(abs) === 0) return abs;
  return `${value > 0 ? "+" : MINUS}${abs}`;
}

export function fmtPct(value: number | null | undefined): string {
  return value == null ? MISSING : `${fmt(value, 1)}%`;
}

export function fmtSample(sample: SampleSize): string {
  return sample.unit === "minutes" ? `N ${sample.value}′` : `N ${sample.value} P`;
}

// ---------------------------------------------------------------------------
// Polarity (DESIGN.md §1): colour follows the subject's point of view.
// ---------------------------------------------------------------------------

export type Tone = "edge" | "vuln" | "neutral";
export type Polarity = "higher_is_better" | "lower_is_better";

export function deltaTone(value: number | null | undefined, polarity: Polarity, neutralBand = 0.05): Tone {
  if (value == null || Math.abs(value) <= neutralBand) return "neutral";
  const good = polarity === "higher_is_better" ? value > 0 : value < 0;
  return good ? "edge" : "vuln";
}

export const TONE_TEXT: Record<Tone, string> = {
  edge: "text-edge",
  vuln: "text-vuln",
  neutral: "text-ink-3",
};

// ---------------------------------------------------------------------------
// Labels
// ---------------------------------------------------------------------------

export const ARCHETYPE_LABEL: Record<PlayerArchetype, string> = {
  portiere_classico: "Portiere classico",
  portiere_libero: "Portiere libero",
  braccetto: "Braccetto",
  centrale_marcatore: "Centrale marcatore",
  centrale_impostazione: "Centrale d'impostazione",
  terzino_difensivo: "Terzino difensivo",
  terzino_spinta: "Terzino di spinta",
  terzino_invertito: "Terzino invertito",
  quinto: "Quinto",
  regista: "Regista",
  mediano_incontrista: "Mediano incontrista",
  mezzala: "Mezzala",
  box_to_box: "Box-to-box",
  trequartista: "Trequartista",
  ala_dribblatrice: "Ala dribblatrice",
  ala_inversa: "Ala inversa",
  prima_punta: "Prima punta",
  falso_nove: "Falso nove",
  attaccante_profondita: "Attaccante di profondità",
  seconda_punta: "Seconda punta",
};

export function archetypeLabel(a: PlayerArchetype | null | undefined): string {
  return a ? ARCHETYPE_LABEL[a] : "Archetipo n.d.";
}

export const POSITION_LABEL: Record<PlayerPosition, string> = {
  GK: "Portiere",
  CB: "Difensore centrale",
  LB: "Terzino sinistro",
  RB: "Terzino destro",
  LWB: "Esterno sinistro",
  RWB: "Esterno destro",
  DM: "Mediano",
  CM: "Centrocampista",
  AM: "Trequartista",
  LW: "Ala sinistra",
  RW: "Ala destra",
  ST: "Attaccante",
};

export const CORRIDOR_LABEL: Record<ZoneCorridor, string> = {
  left: "Corsia sinistra",
  left_half: "Mezzo spazio sinistro",
  center: "Centro",
  right_half: "Mezzo spazio destro",
  right: "Corsia destra",
};

export const CORRIDOR_SHORT: Record<ZoneCorridor, string> = {
  left: "Corsia SX",
  left_half: "Mezzo SX",
  center: "Centro",
  right_half: "Mezzo DX",
  right: "Corsia DX",
};

export const SHOT_ZONE_LABEL: Record<XgaShotZone, string> = {
  six_yard: "Area piccola",
  box_left: "Area, lato sinistro",
  box_center: "Area, centro",
  box_right: "Area, lato destro",
  edge_left: "Limite, sinistra",
  edge_center: "Limite, centro",
  edge_right: "Limite, destra",
  long_range: "Distanza",
};

export const LINE_HEIGHT_LABEL: Record<LineHeight, string> = {
  high: "Linea alta",
  mid: "Linea media",
  low: "Linea bassa",
};

export const CONDITION_TYPE_LABEL: Record<PlayerConditionType, string> = {
  vs_defender_archetype: "Prototipo difensore",
  vs_attacker_archetype: "Prototipo attaccante",
  vs_line_height: "Altezza linea avversaria",
  vs_formation: "Modulo avversario",
};

export const CONFIDENCE_LABEL: Record<ConfidenceLevel, string> = {
  high: "Campione solido",
  medium: "Campione medio",
  low: "Campione ridotto",
};

const METRIC_LABEL: Record<string, string> = {
  rating: "Rating",
  rating_delta: "Δ Rating",
  dribbles_won: "Dribbling riusciti",
  dribbles_past: "Dribbling subiti",
  dribbles_delta: "Δ Dribbling/90",
  duels_won: "Duelli vinti",
  duels_delta: "Δ Duelli vinti/90",
  progressive_actions: "Azioni progressive",
  xg: "xG",
  xa: "xA",
  xg_delta: "Δ xG",
  xga_delta: "Δ xGA",
};

export function metricLabel(key: string | null | undefined): string {
  if (!key) return "Metrica";
  return METRIC_LABEL[key] ?? key.replace(/_/g, " ");
}

export function surname(fullName: string): string {
  const parts = fullName.trim().split(/\s+/);
  return parts.length > 1 ? parts.slice(1).join(" ") : fullName;
}

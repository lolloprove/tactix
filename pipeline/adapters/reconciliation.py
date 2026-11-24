"""Deterministic + controlled fuzzy reconciliation for Serie A teams and players.

Provider names vary wildly ("FC Internazionale Milano", "Inter", "Inter Milan";
"AC Milan", "Milan"; "Hellas Verona FC", "Verona"; "Como 1907", "Como").
Teams resolve first via a deterministic canonical catalog, falling back to strict
fuzzy matching (threshold >= 0.84). Players reconcile strictly within the same
team using normalised full name, surname + initial, and controlled fuzzy match.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher

from db.models import TeamUpsert

_CLUB_NOISE_RE = re.compile(
    r"\b(fc|ac|as|us|ss|ssc|uc|acf|cfc|calcio|club|sportiva|societa|1907|1908|1909|1913|1919|1926)\b"
)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]")
_MULTI_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class CanonicalTeam:
    name: str
    short_name: str
    slug: str
    aliases: tuple[str, ...] = ()


# Covers 2025/26 & 2026/27 Serie A clubs plus common Serie B promotion candidates.
SERIE_A_CATALOG: tuple[CanonicalTeam, ...] = (
    CanonicalTeam("Atalanta", "ATA", "atalanta", ("atalanta bc", "atalanta bergamo")),
    CanonicalTeam("Bologna", "BOL", "bologna", ("bologna fc", "bologna 1909")),
    CanonicalTeam("Cagliari", "CAG", "cagliari", ("cagliari calcio",)),
    CanonicalTeam("Como", "COM", "como", ("como 1907", "calcio como")),
    CanonicalTeam("Cremonese", "CRE", "cremonese", ("us cremonese",)),
    CanonicalTeam("Empoli", "EMP", "empoli", ("empoli fc",)),
    CanonicalTeam("Fiorentina", "FIO", "fiorentina", ("acf fiorentina",)),
    CanonicalTeam("Frosinone", "FRO", "frosinone", ("frosinone calcio",)),
    CanonicalTeam("Genoa", "GEN", "genoa", ("genoa cfc",)),
    CanonicalTeam(
        "Inter",
        "INT",
        "inter",
        ("inter milan", "internazionale", "fc internazionale", "fc internazionale milano"),
    ),
    CanonicalTeam("Juventus", "JUV", "juventus", ("juventus fc", "juve")),
    CanonicalTeam("Lazio", "LAZ", "lazio", ("ss lazio",)),
    CanonicalTeam("Lecce", "LEC", "lecce", ("us lecce",)),
    CanonicalTeam("Milan", "MIL", "milan", ("ac milan",)),
    CanonicalTeam("Monza", "MON", "monza", ("ac monza",)),
    CanonicalTeam("Napoli", "NAP", "napoli", ("ssc napoli",)),
    CanonicalTeam("Palermo", "PAL", "palermo", ("palermo fc",)),
    CanonicalTeam("Parma", "PAR", "parma", ("parma calcio", "parma calcio 1913")),
    CanonicalTeam("Pisa", "PIS", "pisa", ("pisa sc", "pisa sporting club", "ac pisa")),
    CanonicalTeam("Roma", "ROM", "roma", ("as roma",)),
    CanonicalTeam("Salernitana", "SAL", "salernitana", ("us salernitana",)),
    CanonicalTeam("Sampdoria", "SAM", "sampdoria", ("uc sampdoria",)),
    CanonicalTeam("Sassuolo", "SAS", "sassuolo", ("us sassuolo", "us sassuolo calcio")),
    CanonicalTeam("Spezia", "SPE", "spezia", ("spezia calcio",)),
    CanonicalTeam("Torino", "TOR", "torino", ("torino fc",)),
    CanonicalTeam("Udinese", "UDI", "udinese", ("udinese calcio",)),
    CanonicalTeam("Venezia", "VEN", "venezia", ("venezia fc",)),
    CanonicalTeam("Verona", "VER", "verona", ("hellas verona", "hellas verona fc")),
)


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_team_name(name: str) -> str:
    cleaned = strip_accents(name).lower().strip()
    cleaned = _NON_ALNUM_RE.sub(" ", cleaned)
    cleaned = _CLUB_NOISE_RE.sub(" ", cleaned)
    return _MULTI_SPACE_RE.sub(" ", cleaned).strip()


def normalize_player_name(name: str) -> str:
    cleaned = strip_accents(name).lower().strip()
    cleaned = cleaned.replace("-", " ").replace("'", " ").replace(".", " ")
    cleaned = _NON_ALNUM_RE.sub(" ", cleaned)
    return _MULTI_SPACE_RE.sub(" ", cleaned).strip()


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _build_team_alias_index() -> dict[str, CanonicalTeam]:
    index: dict[str, CanonicalTeam] = {}
    for team in SERIE_A_CATALOG:
        keys = (team.name, team.slug, team.short_name, *team.aliases)
        for key in keys:
            norm = normalize_team_name(key)
            if norm:
                index[norm] = team
            raw = strip_accents(key).lower().strip()
            if raw:
                index[raw] = team
    return index


_TEAM_ALIAS_INDEX: dict[str, CanonicalTeam] = _build_team_alias_index()


def resolve_canonical_team(raw_name: str, *, fuzzy_threshold: float = 0.84) -> CanonicalTeam:
    """Resolve any provider team name to a canonical Serie A team deterministically.

    If a newly promoted club is not in the static catalog, builds a valid fallback
    slug and 3-letter short_name so upserts never fail SQL check constraints.
    """
    raw_key = strip_accents(raw_name).lower().strip()
    if raw_key in _TEAM_ALIAS_INDEX:
        return _TEAM_ALIAS_INDEX[raw_key]

    norm = normalize_team_name(raw_name)
    if norm in _TEAM_ALIAS_INDEX:
        return _TEAM_ALIAS_INDEX[norm]

    # Controlled fuzzy match against known canonical keys
    best_team: CanonicalTeam | None = None
    best_score = 0.0
    for key, team in _TEAM_ALIAS_INDEX.items():
        score = _similarity(norm, key)
        if score > best_score:
            best_score = score
            best_team = team

    if best_team is not None and best_score >= fuzzy_threshold:
        return best_team

    # Safe deterministic fallback for unknown club names
    tokens = [t for t in norm.split() if t]
    base_name = raw_name.strip() or "Unknown"
    slug = re.sub(r"[^a-z0-9]+", "-", norm).strip("-") or "team-unknown"
    letters = "".join(ch for ch in ("".join(tokens) if tokens else "unk") if ch.isalpha())
    short = (letters[:3] or "UNK").upper().ljust(3, "X")
    return CanonicalTeam(name=base_name, short_name=short, slug=slug)


def make_team_upsert(
    raw_name: str,
    *,
    understat_id: int | None = None,
    fotmob_id: int | None = None,
    sofascore_id: int | None = None,
    logo_url: str | None = None,
) -> TeamUpsert:
    team = resolve_canonical_team(raw_name)
    return TeamUpsert(
        name=team.name,
        short_name=team.short_name,
        slug=team.slug,
        understat_id=understat_id,
        fotmob_id=fotmob_id,
        sofascore_id=sofascore_id,
        logo_url=logo_url,
    )


def match_player_name(
    target_name: str,
    candidates: Iterable[tuple[int, str]],
    *,
    fuzzy_threshold: float = 0.84,
) -> int | None:
    """Reconcile a player name against `(candidate_id, candidate_name)` pairs within a team.

    Resolution order:
      1. Exact normalised full-name match
      2. Exact surname + first-initial match (handles "L. Martínez" vs "Lautaro Martínez")
      3. Subset token match (handles Brazilian/Spanish mononyms like "Bremer" vs "Gleison Bremer")
      4. Controlled fuzzy match >= `fuzzy_threshold`
    """
    target_norm = normalize_player_name(target_name)
    if not target_norm:
        return None
    target_tokens = target_norm.split()

    best_id: int | None = None
    best_score = 0.0

    for cand_id, cand_name in candidates:
        cand_norm = normalize_player_name(cand_name)
        if not cand_norm:
            continue
        if cand_norm == target_norm:
            return cand_id

        cand_tokens = cand_norm.split()
        # Surname + first initial match (e.g. "l martinez" vs "lautaro martinez")
        if (
            len(target_tokens) >= 2
            and len(cand_tokens) >= 2
            and target_tokens[-1] == cand_tokens[-1]
            and target_tokens[0][0] == cand_tokens[0][0]
        ):
            score = 0.94
        # Mononym / exact surname token subset (only when unambiguous length >= 4)
        elif (
            len(target_tokens) == 1
            and len(target_tokens[0]) >= 4
            and target_tokens[0] in cand_tokens
        ) or (
            len(cand_tokens) == 1 and len(cand_tokens[0]) >= 4 and cand_tokens[0] in target_tokens
        ):
            score = 0.90
        else:
            score = _similarity(target_norm, cand_norm)

        if score > best_score:
            best_score = score
            best_id = cand_id

    if best_id is not None and best_score >= fuzzy_threshold:
        return best_id
    return None

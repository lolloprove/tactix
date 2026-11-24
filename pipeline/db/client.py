import logging
from collections.abc import Sequence
from datetime import datetime
from functools import lru_cache
from typing import Any

from supabase import Client, create_client

from config import get_settings
from db.models import Row

log = logging.getLogger(__name__)

# Natural keys used for idempotent UPSERTs (must match unique constraints in SQL).
CONFLICT_KEYS: dict[str, str] = {
    "teams": "slug",
    "matches": "season,home_team_id,away_team_id",
    "team_match_tactics": "match_id,team_id",
    "player_match_stats": "match_id,player_id",
    "team_conditional_splits": "team_id,season,condition_type,condition_value",
    "player_conditional_splits": "player_id,season,condition_type,condition_value",
    "match_ai_briefs": "match_id,brief_type",
    "team_how_to_beat": "team_id,season",
}


@lru_cache
def get_client() -> Client:
    """Service-role client: bypasses RLS. Never use outside the pipeline."""
    s = get_settings()
    if not s.supabase_url or s.supabase_service_role_key is None:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(s.supabase_url, s.supabase_service_role_key.get_secret_value())


def ping_db() -> bool:
    """Lightweight query to verify DB health and keep Supabase Free awake."""
    res = get_client().table("teams").select("id").limit(1).execute()
    return res.data is not None


def fetch_table(
    table: str,
    *,
    columns: str = "*",
    eq: dict[str, Any] | None = None,
    order: str | None = None,
    page_size: int = 1000,
) -> list[dict[str, Any]]:
    """Paginated read helper so PostgREST 1000-row cap never silently truncates data."""
    client = get_client()
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = client.table(table).select(columns)
        if eq:
            for col, val in eq.items():
                query = query.eq(col, val)
        if order:
            query = query.order(order)
        res = query.range(offset, offset + page_size - 1).execute()
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def upsert_rows(
    table: str,
    rows: Sequence[Row],
    *,
    on_conflict: str | None = None,
    chunk_size: int = 500,
) -> int:
    """Idempotent bulk upsert. `players` has no default key: pass the external id column."""
    if not rows:
        return 0
    conflict = on_conflict or CONFLICT_KEYS.get(table)
    if conflict is None:
        raise ValueError(f"No conflict key for table {table!r}; pass on_conflict explicitly")

    payload = [r.to_db() for r in rows]
    client = get_client()
    for start in range(0, len(payload), chunk_size):
        chunk = payload[start : start + chunk_size]
        client.table(table).upsert(chunk, on_conflict=conflict, returning="minimal").execute()
    log.info("upserted %d rows into %s (on_conflict=%s)", len(payload), table, conflict)
    return len(payload)


def brief_exists(match_id: int, brief_type: str) -> bool:
    """AI cache check: a brief is generated at most once per (match, type)."""
    res = (
        get_client()
        .table("match_ai_briefs")
        .select("id")
        .eq("match_id", match_id)
        .eq("brief_type", brief_type)
        .limit(1)
        .execute()
    )
    return bool(res.data)


def brief_is_fresh(
    match_id: int,
    brief_type: str,
    source_updated_at: datetime | None = None,
) -> bool:
    """Return True if a brief already exists and is at least as fresh as `source_updated_at`."""
    res = (
        get_client()
        .table("match_ai_briefs")
        .select("id,generated_at")
        .eq("match_id", match_id)
        .eq("brief_type", brief_type)
        .limit(1)
        .execute()
    )
    if not res.data:
        return False
    if source_updated_at is None:
        return True
    raw_ts = res.data[0].get("generated_at")
    if not raw_ts:
        return False
    generated_at = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
    return generated_at >= source_updated_at


def how_to_beat_is_fresh(
    team_id: int,
    season: str,
    through_round: int | None,
    vulnerabilities_payload: list[dict[str, Any]],
) -> bool:
    """Return True if `ai_playbook_text` exists and vulnerabilities/round haven't changed."""
    res = (
        get_client()
        .table("team_how_to_beat")
        .select("through_round,vulnerabilities_json,ai_playbook_text")
        .eq("team_id", team_id)
        .eq("season", season)
        .limit(1)
        .execute()
    )
    if not res.data:
        return False
    row = res.data[0]
    if not row.get("ai_playbook_text"):
        return False
    return (
        row.get("through_round") == through_round
        and row.get("vulnerabilities_json") == vulnerabilities_payload
    )

"""Connectivity smoke-test for all Tactix external data sources & services.

Run from `pipeline/`:
    python check_connectivity.py
    uv run python check_connectivity.py --json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass

from adapters.http import BlockedError, PoliteHttpClient
from adapters.match_events_adapter import (
    FOTMOB_BASE,
    FOTMOB_SERIE_A_ID,
    SOFASCORE_BASE,
    SOFASCORE_SERIE_A_ID,
)
from adapters.schedule_adapter import API_FOOTBALL_SERIE_A_ID, API_FOOTBALL_URL, FOOTBALL_DATA_URL
from adapters.understat_adapter import BASE_URL as UNDERSTAT_BASE
from adapters.understat_adapter import season_start_year
from config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("check_connectivity")


@dataclass
class CheckResult:
    service: str
    status: str  # PASS | WARN | FAIL | SKIP
    latency_ms: int
    detail: str


def _timed_check(service: str, fn) -> CheckResult:
    t0 = time.monotonic()
    try:
        detail = fn()
        return CheckResult(
            service=service,
            status="PASS",
            latency_ms=int((time.monotonic() - t0) * 1000),
            detail=detail,
        )
    except BlockedError as exc:
        return CheckResult(
            service=service,
            status="WARN",
            latency_ms=int((time.monotonic() - t0) * 1000),
            detail=f"Blocked (403): {exc}",
        )
    except Exception as exc:
        return CheckResult(
            service=service,
            status="FAIL",
            latency_ms=int((time.monotonic() - t0) * 1000),
            detail=f"{type(exc).__name__}: {exc}",
        )


def run_checks(season: str) -> list[CheckResult]:
    settings = get_settings()
    year = season_start_year(season)
    results: list[CheckResult] = []

    with PoliteHttpClient(min_interval_s=0.8, timeout_s=15.0) as http:
        # 1. Understat
        def check_understat() -> str:
            html = http.get_text(f"{UNDERSTAT_BASE}/league/Serie_A/{year}")
            if "errors.css" in html:
                raise RuntimeError("Understat returned maintenance/error page (errors.css)")
            has_dates = "datesData" in html or '"dates"' in html
            return f"HTML len={len(html)}, has_dates={has_dates}"

        results.append(_timed_check("understat", check_understat))

        # 2. FotMob
        def check_fotmob() -> str:
            data = http.get_json(
                f"{FOTMOB_BASE}/leagues",
                params={"id": FOTMOB_SERIE_A_ID},
                headers={"Referer": "https://www.fotmob.com/", "Origin": "https://www.fotmob.com"},
            )
            matches = len(
                (data.get("fixtures") or {}).get("allMatches")
                or (data.get("matches") or {}).get("allMatches")
                or []
            )
            return f"league={data.get('details', {}).get('name', 'Serie A')}, matches={matches}"

        results.append(_timed_check("fotmob", check_fotmob))

        # 3. SofaScore
        def check_sofascore() -> str:
            data = http.get_json(
                f"{SOFASCORE_BASE}/unique-tournament/{SOFASCORE_SERIE_A_ID}/seasons",
                headers={
                    "Referer": "https://www.sofascore.com/",
                    "Origin": "https://www.sofascore.com",
                },
            )
            seasons = data.get("seasons") or []
            return f"seasons_count={len(seasons)}, latest={seasons[0].get('year') if seasons else 'n/a'}"

        results.append(_timed_check("sofascore", check_sofascore))

        # 4. Official Schedule API
        if settings.football_api_key:
            key = settings.football_api_key.get_secret_value()
            if settings.football_api_provider == "api_football":

                def check_sched() -> str:
                    data = http.get_json(
                        API_FOOTBALL_URL,
                        params={"league": API_FOOTBALL_SERIE_A_ID, "season": year},
                        headers={"x-apisports-key": key},
                    )
                    return f"api_football fixtures={len(data.get('response') or [])}"
            else:

                def check_sched() -> str:
                    data = http.get_json(
                        FOOTBALL_DATA_URL,
                        params={"season": year},
                        headers={"X-Auth-Token": key},
                    )
                    return f"football_data matches={len(data.get('matches') or [])}"

            results.append(_timed_check("schedule_api", check_sched))
        else:
            results.append(CheckResult("schedule_api", "SKIP", 0, "FOOTBALL_API_KEY not set"))

    # 5. Supabase
    if settings.supabase_url and settings.supabase_service_role_key:

        def check_supabase() -> str:
            from db.client import ping_db

            ok = ping_db()
            return f"ping_db={ok}"

        results.append(_timed_check("supabase", check_supabase))
    else:
        results.append(
            CheckResult("supabase", "SKIP", 0, "SUPABASE_URL / SERVICE_ROLE_KEY not set")
        )

    # 6. Gemini
    if settings.gemini_api_key:

        def check_gemini() -> str:
            from ai.client import get_genai_client

            client = get_genai_client()
            model_info = client.models.get(model=settings.gemini_model)
            return f"model={model_info.name}"

        results.append(_timed_check("gemini", check_gemini))
    else:
        results.append(CheckResult("gemini", "SKIP", 0, "GEMINI_API_KEY not set"))

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Check connectivity to Tactix data sources.")
    parser.add_argument("--season", default=get_settings().season)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    results = run_checks(args.season)

    if args.as_json:
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        print(f"{'SERVICE':<15} {'STATUS':<6} {'MS':>6}  DETAIL")
        print("-" * 78)
        for r in results:
            print(f"{r.service:<15} {r.status:<6} {r.latency_ms:>6}  {r.detail}")

    # Fail only if BOTH event providers (fotmob & sofascore) AND understat fail
    by_svc = {r.service: r.status for r in results}
    events_ok = by_svc.get("fotmob") == "PASS" or by_svc.get("sofascore") == "PASS"
    understat_ok = by_svc.get("understat") == "PASS"
    if not events_ok and not understat_ok:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Polite HTTP client for unofficial JSON/HTML endpoints.

curl_cffi impersonates real browser TLS fingerprints. 429/5xx are retried with
exponential backoff + jitter (honouring Retry-After); 403 rotates the
impersonation target before retrying. Requests are spaced by a minimum interval.
"""

import logging
import time
from typing import Any

import curl_cffi
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

log = logging.getLogger(__name__)

IMPERSONATE_TARGETS = ("chrome", "safari", "edge")
MIN_INTERVAL_S = 2.0
TIMEOUT_S = 20.0
MAX_ATTEMPTS = 5


class RetryableHTTPError(Exception):
    def __init__(self, status: int, url: str, retry_after: float | None = None) -> None:
        super().__init__(f"HTTP {status} for {url}")
        self.status = status
        self.retry_after = retry_after


class BlockedError(Exception):
    """All impersonation targets got 403: the source is blocking us. Do not hammer it."""


def _wait(state: RetryCallState) -> float:
    exc = state.outcome.exception() if state.outcome else None
    if isinstance(exc, RetryableHTTPError) and exc.retry_after:
        return exc.retry_after
    return wait_exponential_jitter(initial=2, max=60)(state)


def _log_retry(state: RetryCallState) -> None:
    exc = state.outcome.exception() if state.outcome else None
    log.warning("retry %d after %s", state.attempt_number, exc)


class PoliteHttpClient:
    def __init__(self, *, min_interval_s: float = MIN_INTERVAL_S, timeout_s: float = TIMEOUT_S):
        self.min_interval_s = min_interval_s
        self.timeout_s = timeout_s
        self._target_idx = 0
        self._last_request_at = 0.0
        self._session = curl_cffi.Session(impersonate=IMPERSONATE_TARGETS[0])

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "PoliteHttpClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_s:
            time.sleep(self.min_interval_s - elapsed)
        self._last_request_at = time.monotonic()

    def _rotate_target(self) -> bool:
        if self._target_idx + 1 >= len(IMPERSONATE_TARGETS):
            return False
        self._target_idx += 1
        self._session.close()
        self._session = curl_cffi.Session(impersonate=IMPERSONATE_TARGETS[self._target_idx])
        log.warning("403: switching impersonation to %s", IMPERSONATE_TARGETS[self._target_idx])
        return True

    @retry(
        retry=retry_if_exception_type(RetryableHTTPError),
        wait=_wait,
        stop=stop_after_attempt(MAX_ATTEMPTS),
        before_sleep=_log_retry,
        reraise=True,
    )
    def _request(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        self._throttle()
        r = self._session.get(url, params=params, headers=headers, timeout=self.timeout_s)

        if r.status_code == 403:
            if self._rotate_target():
                raise RetryableHTTPError(403, url)
            raise BlockedError(f"403 on every impersonation target for {url}")
        if r.status_code == 429 or r.status_code >= 500:
            retry_after = r.headers.get("Retry-After")
            delay = float(retry_after) if retry_after and retry_after.isdigit() else None
            raise RetryableHTTPError(r.status_code, url, delay)
        r.raise_for_status()
        return r

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        return self._request(url, params=params, headers=headers).json()

    def get_text(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        return str(self._request(url, params=params, headers=headers).text)

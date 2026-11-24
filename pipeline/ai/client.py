import json
import logging
import time
from functools import lru_cache

from google import genai
from google.genai import types
from pydantic import BaseModel
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from config import get_settings

log = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = (
    "Sei un analista tattico professionista di Serie A per Tactix. "
    "Scrivi in italiano secco, tecnico, editoriale e mai banale: vieta frasi fatte da telecronaca "
    "('partita aperta', 'chi sbaglia meno', 'cuore e grinta'). "
    "Usa ESCLUSIVAMENTE i dati del JSON fornito: non inventare mai numeri, nomi, archetipi o eventi. "
    "Se un dato ha confidence 'low', segnalalo esplicitamente come tendenza su campione ridotto."
)

_last_call_at: float = 0.0


def _is_retryable_genai_error(exc: BaseException) -> bool:
    msg = str(exc).upper()
    return any(tok in msg for tok in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "TIMEOUT"))


@lru_cache
def get_genai_client() -> genai.Client:
    key = get_settings().gemini_api_key
    if key is None:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=key.get_secret_value())


def _respect_rate_limit(delay_s: float | None = None) -> None:
    global _last_call_at
    min_delay = get_settings().gemini_delay_s if delay_s is None else delay_s
    if min_delay <= 0:
        return
    elapsed = time.monotonic() - _last_call_at
    if _last_call_at > 0 and elapsed < min_delay:
        sleep_for = min_delay - elapsed
        log.debug("Gemini rate-limit sleep %.2fs", sleep_for)
        time.sleep(sleep_for)
    _last_call_at = time.monotonic()


@retry(
    retry=retry_if_exception(_is_retryable_genai_error),
    wait=wait_exponential_jitter(initial=5, max=60),
    stop=stop_after_attempt(4),
    reraise=True,
)
def generate_structured[T: BaseModel](
    schema: type[T],
    payload: dict,
    task: str,
    *,
    delay_s: float | None = None,
) -> T:
    """Send pre-aggregated deterministic JSON and get back a validated instance of `schema`."""
    _respect_rate_limit(delay_s)
    settings = get_settings()
    response = get_genai_client().models.generate_content(
        model=settings.gemini_model,
        contents=f"{task}\n\nDATI:\n{json.dumps(payload, ensure_ascii=False)}",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.35,
        ),
    )
    if isinstance(response.parsed, schema):
        return response.parsed
    return schema.model_validate_json(response.text or "")

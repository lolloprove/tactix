"""Mirrors the generated `confidence` columns in Postgres; used when the engine
builds JSON (briefs, vulnerabilities) before the split rows are read back."""

from db.models import ConfidenceLevel

MINUTES_MEDIUM = 270
MINUTES_HIGH = 540
MATCHES_MEDIUM = 3
MATCHES_HIGH = 6


def from_minutes(sample_minutes: int) -> ConfidenceLevel:
    if sample_minutes < MINUTES_MEDIUM:
        return "low"
    return "medium" if sample_minutes <= MINUTES_HIGH else "high"


def from_matches(sample_matches: int) -> ConfidenceLevel:
    if sample_matches < MATCHES_MEDIUM:
        return "low"
    return "medium" if sample_matches <= MATCHES_HIGH else "high"

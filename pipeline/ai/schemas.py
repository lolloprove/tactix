"""Gemini structured-output schemas.

The LLM only writes prose and picks among candidates the engine already
computed (by `*_key`). Every number in the stored brief comes from the engine
payload, never from the model: the brief builder merges narrative + candidates
into `db.models.MatchAiBriefUpsert`.
"""

from typing import Literal

from pydantic import BaseModel, Field


class EdgeNarrative(BaseModel):
    edge_key: str = Field(description="Exact edge_key of one of the provided edge candidates.")
    title: str = Field(description="Max 8 words, dry technical Italian, no numbers.")
    rationale: str = Field(
        description="1-2 concise technical sentences in Italian citing only the provided values."
    )


class XFactorNarrative(BaseModel):
    candidate_key: str = Field(
        description="Exact candidate_key of one of the provided x_factor candidates."
    )
    title: str = Field(description="Max 7 words, sharp tactical Italian.")
    rationale: str = Field(description="1 sentence in Italian grounded strictly in provided data.")


class ObservationNarrative(BaseModel):
    candidate_key: str = Field(description="Exact candidate_key of the starter.")
    observation: str = Field(
        description="1-2 crisp tactical sentences in Italian anchored to the starter's archetype, splits, and direct opponent."
    )
    sentiment: Literal["positive", "negative", "neutral"]


class MatchBriefNarrative(BaseModel):
    tactical_summary: str = Field(
        description="3-4 sentences in dry, technical Italian analysing the clash of tactical ideas. No clichés."
    )
    key_edges: list[EdgeNarrative] = Field(
        max_length=3,
        description="Top 3 non-obvious tactical keys selected from edge_candidates.",
    )
    x_factors: list[XFactorNarrative] = Field(
        max_length=3,
        description="Top 3 decisive players selected from x_factor_candidates.",
    )
    player_observations: list[ObservationNarrative] = Field(
        max_length=22,
        description="One concise observation (1-2 sentences) for EVERY starter in starter_candidates.",
    )


class HowToBeatNarrative(BaseModel):
    ai_playbook_text: str = Field(
        description="3-4 sentences in dry, imperative, technical Italian explaining how to beat this team using only the provided vulnerabilities."
    )

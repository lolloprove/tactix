"""Source adapter contract. Adapters only fetch and normalise; they never compute
tactical metrics (that is `engine/`) and never touch the database (that is `db/`).

DTOs carry provider ids only; `db/` resolves them to internal ids. Coordinates
must already be in the Tactix frame (0-100, x = width, y = length, own goal at y=0).
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

from adapters.http import PoliteHttpClient
from db.models import Coord, MatchStatus, PlayerPosition

Source = Literal["understat", "fotmob", "sofascore", "football_data", "api_football"]


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FixtureDTO(DTO):
    source: Source
    external_id: int
    season: str
    round: int
    kickoff_at: datetime
    home_external_id: int
    away_external_id: int
    status: MatchStatus
    home_team_name: str | None = None
    away_team_name: str | None = None
    home_goals: int | None = None
    away_goals: int | None = None
    home_xg: float | None = None
    away_xg: float | None = None


class TeamLineDTO(DTO):
    team_external_id: int
    team_name: str | None = None
    goals: int | None = None
    xg: float | None = None
    formation: str | None = None
    possession: float | None = None
    ppda: float | None = None
    own_half_passes: int | None = None
    opp_half_passes: int | None = None
    tackles: int | None = None
    interceptions: int | None = None
    fouls: int | None = None
    touches_opp_box: int | None = None
    attack_bias_left: float | None = None
    attack_bias_center: float | None = None
    attack_bias_right: float | None = None


class PlayerLineDTO(DTO):
    player_external_id: int
    team_external_id: int
    name: str
    position: PlayerPosition | None = None
    minutes: int
    is_starter: bool = False
    avg_x: Coord | None = None
    avg_y: Coord | None = None
    stats: dict[str, float | int | None] = {}


class EventDTO(DTO):
    """Single on-ball event, already in the acting team's frame."""

    team_external_id: int
    player_external_id: int | None
    minute: int
    type: str
    x: Coord
    y: Coord
    end_x: Coord | None = None
    end_y: Coord | None = None
    outcome: bool | None = None
    xg: float | None = None


class MatchDTO(DTO):
    fixture: FixtureDTO
    teams: tuple[TeamLineDTO, TeamLineDTO]
    players: list[PlayerLineDTO]
    events: list[EventDTO] = []


class SourceAdapter(ABC):
    source: ClassVar[Source]

    def __init__(self, http: PoliteHttpClient) -> None:
        self.http = http

    @abstractmethod
    def fetch_fixtures(self, season: str) -> list[FixtureDTO]:
        """All Serie A fixtures of the season known to the source."""

    @abstractmethod
    def fetch_match(self, external_id: int) -> MatchDTO | None:
        """Full match payload, or None if the source has no data yet."""

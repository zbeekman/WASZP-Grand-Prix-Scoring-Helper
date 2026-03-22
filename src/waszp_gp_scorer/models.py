"""Core data models for the WASZP GP Scorer application.

All data classes use attrs for concise, validated, immutable-by-default
definitions. These types are shared across all modules and carry no
business logic.
"""

from __future__ import annotations

import enum
from typing import Optional

import attrs


class FinishLineConfig(enum.Enum):
    """Configuration of the finishing line relative to the gate.

    FINISH_AT_GATE: The finishing line is at mark 2p (the gate). Gate
        rounding and finishing line crossing are the same physical event.
        A boat's lap count is ``gate_roundings + (1 if on_finish_list else 0)``.

    SEPARATE_PIN: The finishing line is a separate pin (reach-to-finish per
        RMG p.6). Gate roundings and finishing line crossings are distinct
        events that can interleave during the finishing window.
        A boat's lap count equals its gate roundings (capped at required_laps).
    """

    FINISH_AT_GATE = "FINISH_AT_GATE"
    SEPARATE_PIN = "SEPARATE_PIN"


class FinishType(enum.Enum):
    """Classification of how a competitor completed the race."""

    STANDARD = "Standard"
    GP = "GP"
    GATE = "Gate"
    FINISH_ONLY = "Finish Only"
    ERROR_NO_RECORDED_FINISH = "Error: No Recorded Finish"
    LETTER_SCORE = "Letter Score"


@attrs.define
class Competitor:
    """A registered competitor loaded from the entry CSV.

    Attributes:
        sail_number: Unique sail number string (e.g. ``"AUS1234"``).
        country_code: Three-letter ISO country code (e.g. ``"AUS"``).
        name: Sailor's full name.
        rig_size: Rig size string (e.g. ``"8.2"``, ``"7.5"``).
        division: Age/experience division string (e.g. ``"Open"``, ``"Youth"``).
        phone: Optional contact phone number.
        email: Optional contact email address.
    """

    sail_number: str
    country_code: str
    name: str
    rig_size: str
    division: str
    phone: Optional[str] = attrs.field(default=None)
    email: Optional[str] = attrs.field(default=None)


@attrs.define
class GateRounding:
    """A single entry in the gate rounding list.

    Attributes:
        position: 1-based position in the gate rounding sequence.
        sail_number: Sail number of the boat rounding the gate.
    """

    position: int
    sail_number: str


@attrs.define
class FinishEntry:
    """A single entry in the finish list.

    Attributes:
        position: 1-based position in the finish sequence.
        sail_number: Sail number of the finishing boat.
        letter_score: Optional penalty code (e.g. ``"DNS"``, ``"DSQ"``).
    """

    position: int
    sail_number: str
    letter_score: Optional[str] = attrs.field(default=None)


@attrs.define
class ScoredResult:
    """The scored output for a single competitor.

    Attributes:
        place: Integer place in the GP Finish Ranking (1-based).
        competitor: The :class:`Competitor` this result belongs to.
        laps: Number of laps credited to this boat under the scoring rules.
        finish_type: Classification per :class:`FinishType`.
        annotation: Optional human-readable explanation or warning text.
        letter_score: Optional letter score assigned (e.g. ``"DNS"``).
    """

    place: int
    competitor: Competitor
    laps: int
    finish_type: FinishType
    annotation: Optional[str] = attrs.field(default=None)
    letter_score: Optional[str] = attrs.field(default=None)


@attrs.define
class RaceSession:
    """Top-level container for all race state.

    This object is the single source of truth that is serialized to JSON
    for auto-save and session resume, passed to the scorer, and used by
    the exporter.

    Attributes:
        schema_version: Integer version of the JSON serialization schema.
            Increment when backwards-incompatible changes are made.
        event_name: Human-readable event name (e.g. ``"WASZP Pre-Games 2026"``).
        race_number: Race number within the event (e.g. ``1``).
        race_date: ISO 8601 date string (e.g. ``"2026-03-22"``).
        start_time: Approximate start time string (e.g. ``"14:00"``). Optional.
        num_laps: Number of laps required to complete the race. Defaults to 2.
        course_type: Course type string (e.g. ``"Standard WASZP W/L (Gate)"``).
        finish_line_config: Whether the finishing line is at the gate or a
            separate pin. Defaults to :attr:`FinishLineConfig.FINISH_AT_GATE`.
        finish_window_marker_position: Index (0-based) into ``gate_roundings``
            after which entries are considered window-phase entries.
            ``None`` if the marker has not been placed. Only meaningful when
            ``finish_line_config == FinishLineConfig.SEPARATE_PIN``.
        lap_counting_location: Informational string naming which gate or mark
            the human lap counter is stationed at.
        competitors: Ordered list of competitors loaded from the CSV.
        green_fleet: Set of sail numbers excluded from scoring (Green Fleet).
        gate_roundings: Ordered list of gate rounding entries.
        finish_entries: Ordered list of finish entries.
    """

    schema_version: int = attrs.field(default=1)
    event_name: str = attrs.field(default="")
    race_number: int = attrs.field(default=1)
    race_date: str = attrs.field(default="")
    start_time: Optional[str] = attrs.field(default=None)
    num_laps: int = attrs.field(default=2)
    course_type: str = attrs.field(default="Standard WASZP W/L (Gate)")
    finish_line_config: FinishLineConfig = attrs.field(
        default=FinishLineConfig.FINISH_AT_GATE
    )
    finish_window_marker_position: Optional[int] = attrs.field(default=None)
    lap_counting_location: str = attrs.field(default="Leeward gate (mark 2p)")
    competitors: list[Competitor] = attrs.field(factory=list)
    green_fleet: set[str] = attrs.field(factory=set)
    gate_roundings: list[GateRounding] = attrs.field(factory=list)
    finish_entries: list[FinishEntry] = attrs.field(factory=list)

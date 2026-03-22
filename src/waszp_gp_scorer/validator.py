"""Validation module for the WASZP GP Scorer.

Pure-function validators that check data entry events and whole-sheet
consistency. All functions return lists of typed warning objects so the
UI can render them consistently and tests can assert on type.

Validation levels
-----------------
- **Entry-level** (:func:`validate_gate_rounding`, :func:`validate_finish_entry`):
  check a single new entry before it is added to the session.
- **Sheet-level** (:func:`validate_sheet`):
  cross-list consistency checks over the full gate and finish lists.
- **Race-level** (:func:`validate_race_setup`):
  race configuration and session-wide rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from waszp_gp_scorer.models import (
    Competitor,
    FinishEntry,
    FinishLineConfig,
    GateRounding,
    RaceSession,
)
from waszp_gp_scorer.scorer import (
    ExcessRoundingsWarning,
    FinishOnlyWarning,
    LeadBoatViolationWarning,
    MissingFinishWindowMarkerWarning,
    NoRecordedFinishWarning,
    score as _score,
)

# Re-exported so callers can import all warning types from this module.
__all__ = [
    "ConsecutiveDuplicateWarning",
    "DuplicateFinishEntryWarning",
    "ExcessRoundingsWarning",
    "FinishOnlyWarning",
    "GreenFleetEntryWarning",
    "LeadBoatViolationWarning",
    "LetterScoreConflictWarning",
    "MissingFinishWindowMarkerWarning",
    "NoGPValueWarning",
    "NoRecordedFinishWarning",
    "UnknownRigSizeWarning",
    "UnknownSailNumberWarning",
    "ValidatorWarning",
    "validate_finish_entry",
    "validate_gate_rounding",
    "validate_race_setup",
    "validate_sheet",
]

# Letter scores that conflict with gate list presence.
_DNS_DNC_DNF: frozenset[str] = frozenset({"DNS", "DNC", "DNF"})

# Recognized rig sizes (mirrors csv_loader.KNOWN_RIG_SIZES).
_KNOWN_RIG_SIZES: frozenset[str] = frozenset({"8.2", "7.5", "6.9", "5.8"})


# ---------------------------------------------------------------------------
# Warning types defined in this module
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GreenFleetEntryWarning:
    """Sail number belongs to the Green Fleet and cannot score.

    Attributes:
        sail_number: The Green Fleet sail number.
        list_name: Which list the entry appeared on (``"gate"`` or ``"finish"``).
    """

    sail_number: str
    list_name: str


@dataclass(frozen=True)
class UnknownSailNumberWarning:
    """Sail number is not registered in the competitor CSV.

    Attributes:
        sail_number: The unrecognized sail number.
        list_name: Which list the entry appeared on (``"gate"`` or ``"finish"``).
    """

    sail_number: str
    list_name: str


@dataclass(frozen=True)
class ConsecutiveDuplicateWarning:
    """Same sail number entered twice in a row on the gate list.

    Attributes:
        sail_number: The sail number entered consecutively.
        position: 1-based position of the second (duplicate) entry.
    """

    sail_number: str
    position: int


@dataclass(frozen=True)
class DuplicateFinishEntryWarning:
    """Sail number appears more than once on the finish list.

    Attributes:
        sail_number: The duplicated sail number.
        positions: Finish list positions where the duplicates appear.
    """

    sail_number: str
    positions: tuple[int, ...]


@dataclass(frozen=True)
class LetterScoreConflictWarning:
    """Boat with DNS/DNC/DNF letter score also appears on the gate list.

    Per SI 13.2.3(i) the letter score will be overridden; the boat will be
    reclassified as a Gate finish using its gate rounding count.

    Attributes:
        sail_number: The sail number of the boat.
        letter_score: The letter score code (e.g. ``"DNS"``).
        gate_roundings: Number of gate roundings recorded for this boat.
    """

    sail_number: str
    letter_score: str
    gate_roundings: int


@dataclass(frozen=True)
class NoGPValueWarning:
    """Course configuration does not support GP scoring.

    GP scoring requires at least 2 laps and a gate.  A 1-lap race or a
    course with no gate has no GP value.

    Attributes:
        reason: Human-readable reason, e.g. ``"1-lap course"`` or
            ``"no-gate course type"``.
        num_laps: The configured lap count.
        course_type: The configured course type string.
    """

    reason: str
    num_laps: int
    course_type: str


@dataclass(frozen=True)
class UnknownRigSizeWarning:
    """Competitor has an unrecognized rig size.

    Known valid sizes are: ``8.2``, ``7.5``, ``6.9``, ``5.8``.

    Attributes:
        sail_number: The competitor's sail number.
        rig_size: The unrecognized rig size value.
    """

    sail_number: str
    rig_size: str


#: Union type alias for all warning objects returned by validator functions.
ValidatorWarning = Union[
    ConsecutiveDuplicateWarning,
    DuplicateFinishEntryWarning,
    ExcessRoundingsWarning,
    FinishOnlyWarning,
    GreenFleetEntryWarning,
    LeadBoatViolationWarning,
    LetterScoreConflictWarning,
    MissingFinishWindowMarkerWarning,
    NoGPValueWarning,
    NoRecordedFinishWarning,
    UnknownRigSizeWarning,
    UnknownSailNumberWarning,
]


# ---------------------------------------------------------------------------
# Entry-level validators
# ---------------------------------------------------------------------------


def validate_gate_rounding(
    sail_number: str,
    competitors: list[Competitor],
    green_fleet: set[str],
    existing_roundings: list[GateRounding],
    required_laps: int,
    finish_line_config: FinishLineConfig = FinishLineConfig.FINISH_AT_GATE,
) -> list[ValidatorWarning]:
    """Check a new gate rounding entry before adding it to the session.

    Checks performed (in order):

    1. :class:`GreenFleetEntryWarning` — sail number is in the Green Fleet.
    2. :class:`UnknownSailNumberWarning` — sail number not in competitor list.
    3. :class:`ConsecutiveDuplicateWarning` — same as the immediately preceding
       entry on the gate list.
    4. :class:`ExcessRoundingsWarning` — adding this entry would exceed the
       gate rounding cap for the boat.

    Args:
        sail_number: The sail number of the new entry to validate.
        competitors: The registered competitor list for this event.
        green_fleet: Set of sail numbers excluded from scoring.
        existing_roundings: Gate roundings already recorded in this session.
        required_laps: Number of laps required to complete the race.
        finish_line_config: Finish line configuration (affects gate cap).
            Defaults to :attr:`~waszp_gp_scorer.models.FinishLineConfig.FINISH_AT_GATE`.

    Returns:
        A list of :data:`ValidatorWarning` objects describing problems found.
        Empty list if the entry is clean.
    """
    warnings: list[ValidatorWarning] = []
    competitor_sails: set[str] = {c.sail_number for c in competitors}

    if sail_number in green_fleet:
        warnings.append(
            GreenFleetEntryWarning(sail_number=sail_number, list_name="gate")
        )

    if sail_number not in competitor_sails:
        warnings.append(
            UnknownSailNumberWarning(sail_number=sail_number, list_name="gate")
        )

    if existing_roundings and existing_roundings[-1].sail_number == sail_number:
        new_position = len(existing_roundings) + 1
        warnings.append(
            ConsecutiveDuplicateWarning(sail_number=sail_number, position=new_position)
        )

    gate_cap = (
        required_laps - 1
        if finish_line_config == FinishLineConfig.FINISH_AT_GATE
        else required_laps
    )
    current_count = sum(1 for r in existing_roundings if r.sail_number == sail_number)
    if current_count >= gate_cap:
        warnings.append(
            ExcessRoundingsWarning(
                sail_number=sail_number,
                raw_count=current_count + 1,
                cap=gate_cap,
            )
        )

    return warnings


def validate_finish_entry(
    sail_number: str,
    competitors: list[Competitor],
    green_fleet: set[str],
    existing_finish_entries: list[FinishEntry],
) -> list[ValidatorWarning]:
    """Check a new finish entry before adding it to the session.

    Checks performed (in order):

    1. :class:`GreenFleetEntryWarning` — sail number is in the Green Fleet.
    2. :class:`UnknownSailNumberWarning` — sail number not in competitor list.
    3. :class:`DuplicateFinishEntryWarning` — sail number already on the finish
       list.

    Args:
        sail_number: The sail number of the new entry to validate.
        competitors: The registered competitor list for this event.
        green_fleet: Set of sail numbers excluded from scoring.
        existing_finish_entries: Finish entries already recorded in this session.

    Returns:
        A list of :data:`ValidatorWarning` objects describing problems found.
        Empty list if the entry is clean.
    """
    warnings: list[ValidatorWarning] = []
    competitor_sails: set[str] = {c.sail_number for c in competitors}

    if sail_number in green_fleet:
        warnings.append(
            GreenFleetEntryWarning(sail_number=sail_number, list_name="finish")
        )

    if sail_number not in competitor_sails:
        warnings.append(
            UnknownSailNumberWarning(sail_number=sail_number, list_name="finish")
        )

    existing_positions = [
        fe.position for fe in existing_finish_entries if fe.sail_number == sail_number
    ]
    if existing_positions:
        new_position = len(existing_finish_entries) + 1
        all_positions = tuple(sorted(existing_positions + [new_position]))
        warnings.append(
            DuplicateFinishEntryWarning(
                sail_number=sail_number, positions=all_positions
            )
        )

    return warnings


# ---------------------------------------------------------------------------
# Sheet-level validators
# ---------------------------------------------------------------------------


def validate_sheet(
    gate_roundings: list[GateRounding],
    finish_entries: list[FinishEntry],
    competitors: list[Competitor],
    green_fleet: set[str],
    num_laps: int,
    finish_line_config: FinishLineConfig = FinishLineConfig.FINISH_AT_GATE,
) -> list[ValidatorWarning]:
    """Cross-list consistency checks over the full gate and finish lists.

    Checks performed:

    - :class:`DuplicateFinishEntryWarning` — same sail on finish list more
      than once.
    - :class:`FinishOnlyWarning` — non-letter-score finish entry has no gate
      roundings.
    - :class:`NoRecordedFinishWarning` — gate boat at cap with no finish entry.
    - :class:`LetterScoreConflictWarning` — DNS/DNC/DNF entry also on gate list.

    Args:
        gate_roundings: All gate rounding entries recorded so far.
        finish_entries: All finish entries recorded so far.
        competitors: The registered competitor list for this event.
        green_fleet: Set of sail numbers excluded from scoring.
        num_laps: Number of laps required to complete the race.
        finish_line_config: Finish line configuration (affects gate cap).
            Defaults to :attr:`~waszp_gp_scorer.models.FinishLineConfig.FINISH_AT_GATE`.

    Returns:
        A list of :data:`ValidatorWarning` objects describing problems found.
        Empty list if the sheet is consistent.
    """
    warnings: list[ValidatorWarning] = []

    gate_cap = (
        num_laps - 1
        if finish_line_config == FinishLineConfig.FINISH_AT_GATE
        else num_laps
    )

    # Raw gate rounding counts per boat.
    gate_counts_raw: dict[str, int] = {}
    for rounding in gate_roundings:
        sn = rounding.sail_number
        gate_counts_raw[sn] = gate_counts_raw.get(sn, 0) + 1

    gate_sail_numbers: set[str] = set(gate_counts_raw)

    # Index finish entries by sail number.
    finish_by_sail: dict[str, list[FinishEntry]] = {}
    for fe in finish_entries:
        finish_by_sail.setdefault(fe.sail_number, []).append(fe)

    # ------------------------------------------------------------------
    # DuplicateFinishEntryWarning
    # ------------------------------------------------------------------
    for sn, entries in finish_by_sail.items():
        if len(entries) > 1:
            positions = tuple(sorted(fe.position for fe in entries))
            warnings.append(
                DuplicateFinishEntryWarning(sail_number=sn, positions=positions)
            )

    # ------------------------------------------------------------------
    # FinishOnlyWarning: non-letter-score finish entry without gate roundings
    # ------------------------------------------------------------------
    for fe in finish_entries:
        if fe.letter_score is not None:
            continue
        if fe.sail_number in green_fleet:
            continue
        if fe.sail_number not in gate_sail_numbers:
            warnings.append(FinishOnlyWarning(sail_number=fe.sail_number))

    # ------------------------------------------------------------------
    # NoRecordedFinishWarning: gate boat at cap with no finish entry
    # ------------------------------------------------------------------
    for sn, raw_count in gate_counts_raw.items():
        if sn in green_fleet:
            continue
        capped_count = min(raw_count, gate_cap)
        if capped_count >= gate_cap and sn not in finish_by_sail:
            warnings.append(
                NoRecordedFinishWarning(sail_number=sn, gate_count=capped_count)
            )

    # ------------------------------------------------------------------
    # LetterScoreConflictWarning: DNS/DNC/DNF + gate list appearance
    # ------------------------------------------------------------------
    for fe in finish_entries:
        if fe.letter_score in _DNS_DNC_DNF and fe.sail_number in gate_sail_numbers:
            warnings.append(
                LetterScoreConflictWarning(
                    sail_number=fe.sail_number,
                    letter_score=fe.letter_score,
                    gate_roundings=gate_counts_raw[fe.sail_number],
                )
            )

    return warnings


# ---------------------------------------------------------------------------
# Race-level validators
# ---------------------------------------------------------------------------


def validate_race_setup(session: RaceSession) -> list[ValidatorWarning]:
    """Validate race configuration and session-wide rules.

    Checks performed:

    - :class:`NoGPValueWarning` — 1-lap course or course type with no gate.
    - :class:`UnknownRigSizeWarning` — competitor with unrecognized rig size.
    - :class:`MissingFinishWindowMarkerWarning` — ``SEPARATE_PIN`` session
      with no finishing window marker placed.
    - :class:`LeadBoatViolationWarning` — first boat in each fleet group has
      fewer than the required number of laps (checked independently for the
      ``8.2`` and ``non-8.2`` fleet groups).

    Args:
        session: The complete race session to validate.

    Returns:
        A list of :data:`ValidatorWarning` objects describing problems found.
        Empty list if no issues are detected.
    """
    warnings: list[ValidatorWarning] = []

    # ------------------------------------------------------------------
    # NoGPValueWarning
    # ------------------------------------------------------------------
    if session.num_laps == 1:
        warnings.append(
            NoGPValueWarning(
                reason="1-lap course",
                num_laps=session.num_laps,
                course_type=session.course_type,
            )
        )
    elif "gate" not in session.course_type.lower():
        warnings.append(
            NoGPValueWarning(
                reason="no-gate course type",
                num_laps=session.num_laps,
                course_type=session.course_type,
            )
        )

    # ------------------------------------------------------------------
    # UnknownRigSizeWarning
    # ------------------------------------------------------------------
    for comp in session.competitors:
        if comp.rig_size not in _KNOWN_RIG_SIZES:
            warnings.append(
                UnknownRigSizeWarning(
                    sail_number=comp.sail_number,
                    rig_size=comp.rig_size,
                )
            )

    # ------------------------------------------------------------------
    # MissingFinishWindowMarkerWarning and LeadBoatViolationWarning
    # Delegate to the scorer which already implements both checks.
    # ------------------------------------------------------------------
    _, scorer_warnings = _score(session)
    for w in scorer_warnings:
        if isinstance(w, (MissingFinishWindowMarkerWarning, LeadBoatViolationWarning)):
            warnings.append(w)

    return warnings

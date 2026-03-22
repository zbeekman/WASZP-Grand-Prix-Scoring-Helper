"""Tests for the validator module.

Covers all warning types and validation levels:
- Entry-level: validate_gate_rounding, validate_finish_entry
- Sheet-level: validate_sheet
- Race-level: validate_race_setup
"""

import pytest

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
)
from waszp_gp_scorer.validator import (
    ConsecutiveDuplicateWarning,
    DuplicateFinishEntryWarning,
    GreenFleetEntryWarning,
    LetterScoreConflictWarning,
    NoGPValueWarning,
    UnknownRigSizeWarning,
    UnknownSailNumberWarning,
    validate_finish_entry,
    validate_gate_rounding,
    validate_race_setup,
    validate_sheet,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _comp(sail: str, rig: str = "8.2") -> Competitor:
    """Build a minimal Competitor for test use."""
    return Competitor(
        sail_number=sail,
        country_code="TST",
        name=f"Sailor {sail}",
        rig_size=rig,
        division="Open",
    )


def _gate(sail: str, pos: int) -> GateRounding:
    return GateRounding(position=pos, sail_number=sail)


def _finish(sail: str, pos: int, letter: str | None = None) -> FinishEntry:
    return FinishEntry(position=pos, sail_number=sail, letter_score=letter)


def _session(
    competitors: list[Competitor] | None = None,
    green_fleet: set[str] | None = None,
    gate_roundings: list[GateRounding] | None = None,
    finish_entries: list[FinishEntry] | None = None,
    num_laps: int = 2,
    finish_line_config: FinishLineConfig = FinishLineConfig.FINISH_AT_GATE,
    finish_window_marker_position: int | None = None,
    course_type: str = "Standard WASZP W/L (Gate)",
) -> RaceSession:
    return RaceSession(
        competitors=competitors or [],
        green_fleet=green_fleet or set(),
        gate_roundings=gate_roundings or [],
        finish_entries=finish_entries or [],
        num_laps=num_laps,
        finish_line_config=finish_line_config,
        finish_window_marker_position=finish_window_marker_position,
        course_type=course_type,
    )


# ===========================================================================
# Entry-level: validate_gate_rounding
# ===========================================================================


class TestValidateGateRounding:
    """Tests for validate_gate_rounding."""

    def test_unknown_sail_number_fires(self) -> None:
        """UnknownSailNumberWarning fires for sail not in competitor list."""
        comps = [_comp("1001")]
        warns = validate_gate_rounding("9999", comps, set(), [], 2)
        types = [type(w) for w in warns]
        assert UnknownSailNumberWarning in types
        w = next(x for x in warns if isinstance(x, UnknownSailNumberWarning))
        assert w.sail_number == "9999"
        assert w.list_name == "gate"

    def test_unknown_sail_not_fired_for_known(self) -> None:
        """UnknownSailNumberWarning does NOT fire for a registered sail."""
        comps = [_comp("1001")]
        warns = validate_gate_rounding("1001", comps, set(), [], 2)
        assert not any(isinstance(w, UnknownSailNumberWarning) for w in warns)

    def test_green_fleet_entry_fires(self) -> None:
        """GreenFleetEntryWarning fires for a Green Fleet sail number."""
        comps = [_comp("GRN1")]
        green = {"GRN1"}
        warns = validate_gate_rounding("GRN1", comps, green, [], 2)
        types = [type(w) for w in warns]
        assert GreenFleetEntryWarning in types
        w = next(x for x in warns if isinstance(x, GreenFleetEntryWarning))
        assert w.sail_number == "GRN1"
        assert w.list_name == "gate"

    def test_green_fleet_not_fired_for_non_green(self) -> None:
        """GreenFleetEntryWarning does NOT fire for a regular competitor."""
        comps = [_comp("1001")]
        warns = validate_gate_rounding("1001", comps, set(), [], 2)
        assert not any(isinstance(w, GreenFleetEntryWarning) for w in warns)

    def test_consecutive_duplicate_fires(self) -> None:
        """ConsecutiveDuplicateWarning fires when same sail entered twice in a row."""
        comps = [_comp("1001")]
        existing = [_gate("1001", 1)]
        warns = validate_gate_rounding("1001", comps, set(), existing, 2)
        types = [type(w) for w in warns]
        assert ConsecutiveDuplicateWarning in types
        w = next(x for x in warns if isinstance(x, ConsecutiveDuplicateWarning))
        assert w.sail_number == "1001"
        assert w.position == 2  # second entry

    def test_consecutive_duplicate_not_fired_when_different(self) -> None:
        """ConsecutiveDuplicateWarning does NOT fire when previous entry differs."""
        comps = [_comp("1001"), _comp("2002")]
        existing = [_gate("2002", 1)]
        warns = validate_gate_rounding("1001", comps, set(), existing, 2)
        assert not any(isinstance(w, ConsecutiveDuplicateWarning) for w in warns)

    def test_consecutive_duplicate_not_fired_for_first_entry(self) -> None:
        """ConsecutiveDuplicateWarning does NOT fire if the gate list is empty."""
        comps = [_comp("1001")]
        warns = validate_gate_rounding("1001", comps, set(), [], 2)
        assert not any(isinstance(w, ConsecutiveDuplicateWarning) for w in warns)

    def test_excess_roundings_fires_at_cap_finish_at_gate(self) -> None:
        """ExcessRoundingsWarning fires when adding would exceed cap (FINISH_AT_GATE).

        For FINISH_AT_GATE with 2 required laps, gate cap = 1.
        Adding a second rounding for the same boat is excessive.
        """
        comps = [_comp("1001")]
        existing = [_gate("1001", 1)]  # already has 1 rounding == cap
        warns = validate_gate_rounding(
            "1001", comps, set(), existing, 2, FinishLineConfig.FINISH_AT_GATE
        )
        types = [type(w) for w in warns]
        assert ExcessRoundingsWarning in types
        w = next(x for x in warns if isinstance(x, ExcessRoundingsWarning))
        assert w.sail_number == "1001"
        assert w.raw_count == 2  # count after adding
        assert w.cap == 1

    def test_excess_roundings_fires_at_cap_separate_pin(self) -> None:
        """ExcessRoundingsWarning fires when adding would exceed cap (SEPARATE_PIN).

        For SEPARATE_PIN with 2 required laps, gate cap = 2.
        Adding a third rounding is excessive.
        """
        comps = [_comp("1001")]
        existing = [_gate("1001", 1), _gate("2002", 2), _gate("1001", 3)]
        warns = validate_gate_rounding(
            "1001", comps, set(), existing, 2, FinishLineConfig.SEPARATE_PIN
        )
        types = [type(w) for w in warns]
        assert ExcessRoundingsWarning in types
        w = next(x for x in warns if isinstance(x, ExcessRoundingsWarning))
        assert w.cap == 2

    def test_excess_roundings_not_fired_below_cap(self) -> None:
        """ExcessRoundingsWarning does NOT fire when boat is below the cap."""
        comps = [_comp("1001")]
        # For 3-lap FINISH_AT_GATE: gate cap = 2; first rounding is fine
        warns = validate_gate_rounding("1001", comps, set(), [], 3)
        assert not any(isinstance(w, ExcessRoundingsWarning) for w in warns)

    def test_clean_entry_no_warnings(self) -> None:
        """No warnings for a clean, valid gate rounding entry."""
        comps = [_comp("1001"), _comp("2002")]
        existing = [_gate("2002", 1)]
        warns = validate_gate_rounding("1001", comps, set(), existing, 2)
        assert warns == []


# ===========================================================================
# Entry-level: validate_finish_entry
# ===========================================================================


class TestValidateFinishEntry:
    """Tests for validate_finish_entry."""

    def test_unknown_sail_number_fires(self) -> None:
        """UnknownSailNumberWarning fires for sail not in competitor list."""
        comps = [_comp("1001")]
        warns = validate_finish_entry("9999", comps, set(), [])
        types = [type(w) for w in warns]
        assert UnknownSailNumberWarning in types
        w = next(x for x in warns if isinstance(x, UnknownSailNumberWarning))
        assert w.sail_number == "9999"
        assert w.list_name == "finish"

    def test_unknown_sail_not_fired_for_known(self) -> None:
        """UnknownSailNumberWarning does NOT fire for a registered sail."""
        comps = [_comp("1001")]
        warns = validate_finish_entry("1001", comps, set(), [])
        assert not any(isinstance(w, UnknownSailNumberWarning) for w in warns)

    def test_green_fleet_entry_fires(self) -> None:
        """GreenFleetEntryWarning fires for a Green Fleet sail number."""
        comps = [_comp("GRN1")]
        green = {"GRN1"}
        warns = validate_finish_entry("GRN1", comps, green, [])
        types = [type(w) for w in warns]
        assert GreenFleetEntryWarning in types
        w = next(x for x in warns if isinstance(x, GreenFleetEntryWarning))
        assert w.sail_number == "GRN1"
        assert w.list_name == "finish"

    def test_green_fleet_not_fired_for_non_green(self) -> None:
        """GreenFleetEntryWarning does NOT fire for a regular competitor."""
        comps = [_comp("1001")]
        warns = validate_finish_entry("1001", comps, set(), [])
        assert not any(isinstance(w, GreenFleetEntryWarning) for w in warns)

    def test_duplicate_finish_entry_fires(self) -> None:
        """DuplicateFinishEntryWarning fires when sail already on finish list."""
        comps = [_comp("1001")]
        existing = [_finish("1001", 1)]
        warns = validate_finish_entry("1001", comps, set(), existing)
        types = [type(w) for w in warns]
        assert DuplicateFinishEntryWarning in types
        w = next(x for x in warns if isinstance(x, DuplicateFinishEntryWarning))
        assert w.sail_number == "1001"
        assert w.positions == (1, 2)  # original + new

    def test_duplicate_not_fired_for_first_occurrence(self) -> None:
        """DuplicateFinishEntryWarning does NOT fire for first occurrence."""
        comps = [_comp("1001")]
        warns = validate_finish_entry("1001", comps, set(), [])
        assert not any(isinstance(w, DuplicateFinishEntryWarning) for w in warns)

    def test_clean_entry_no_warnings(self) -> None:
        """No warnings for a clean, valid finish entry."""
        comps = [_comp("1001"), _comp("2002")]
        existing = [_finish("2002", 1)]
        warns = validate_finish_entry("1001", comps, set(), existing)
        assert warns == []


# ===========================================================================
# Sheet-level: validate_sheet
# ===========================================================================


class TestValidateSheet:
    """Tests for validate_sheet."""

    def test_duplicate_finish_entry_fires(self) -> None:
        """DuplicateFinishEntryWarning fires for a duplicate on the finish list."""
        gate = [_gate("1001", 1)]
        finish = [_finish("1001", 1), _finish("1001", 2)]
        comps = [_comp("1001")]
        warns = validate_sheet(gate, finish, comps, set(), 2)
        types = [type(w) for w in warns]
        assert DuplicateFinishEntryWarning in types
        w = next(x for x in warns if isinstance(x, DuplicateFinishEntryWarning))
        assert w.sail_number == "1001"
        assert w.positions == (1, 2)

    def test_duplicate_finish_entry_not_fired_for_unique(self) -> None:
        """DuplicateFinishEntryWarning does NOT fire when each sail appears once."""
        gate = [_gate("1001", 1), _gate("2002", 2)]
        finish = [_finish("2002", 1), _finish("1001", 2)]
        comps = [_comp("1001"), _comp("2002")]
        warns = validate_sheet(gate, finish, comps, set(), 2)
        assert not any(isinstance(w, DuplicateFinishEntryWarning) for w in warns)

    def test_finish_only_warning_fires(self) -> None:
        """FinishOnlyWarning fires for a finish-list boat absent from gate list."""
        gate: list[GateRounding] = []
        finish = [_finish("1001", 1)]
        comps = [_comp("1001")]
        warns = validate_sheet(gate, finish, comps, set(), 2)
        types = [type(w) for w in warns]
        assert FinishOnlyWarning in types
        w = next(x for x in warns if isinstance(x, FinishOnlyWarning))
        assert w.sail_number == "1001"

    def test_finish_only_not_fired_when_gate_present(self) -> None:
        """FinishOnlyWarning does NOT fire when boat is on the gate list."""
        gate = [_gate("1001", 1)]
        finish = [_finish("1001", 1)]
        comps = [_comp("1001")]
        warns = validate_sheet(gate, finish, comps, set(), 2)
        assert not any(isinstance(w, FinishOnlyWarning) for w in warns)

    def test_finish_only_not_fired_for_letter_score(self) -> None:
        """FinishOnlyWarning does NOT fire for a letter-score finish entry."""
        gate: list[GateRounding] = []
        finish = [_finish("1001", 1, letter="DNS")]
        comps = [_comp("1001")]
        warns = validate_sheet(gate, finish, comps, set(), 2)
        assert not any(isinstance(w, FinishOnlyWarning) for w in warns)

    def test_finish_only_not_fired_for_green_fleet(self) -> None:
        """FinishOnlyWarning does NOT fire for a Green Fleet boat."""
        gate: list[GateRounding] = []
        finish = [_finish("GRN1", 1)]
        comps = [_comp("GRN1")]
        warns = validate_sheet(gate, finish, comps, {"GRN1"}, 2)
        assert not any(isinstance(w, FinishOnlyWarning) for w in warns)

    def test_no_recorded_finish_fires_at_cap(self) -> None:
        """NoRecordedFinishWarning fires for gate boat at cap with no finish entry.

        FINISH_AT_GATE, 2 laps: gate cap = 1. Boat with 1 rounding and no finish.
        """
        gate = [_gate("1001", 1)]
        finish: list[FinishEntry] = []
        comps = [_comp("1001")]
        warns = validate_sheet(gate, finish, comps, set(), 2)
        types = [type(w) for w in warns]
        assert NoRecordedFinishWarning in types
        w = next(x for x in warns if isinstance(x, NoRecordedFinishWarning))
        assert w.sail_number == "1001"
        assert w.gate_count == 1

    def test_no_recorded_finish_not_fired_when_on_finish(self) -> None:
        """NoRecordedFinishWarning does NOT fire when boat is on the finish list."""
        gate = [_gate("1001", 1)]
        finish = [_finish("1001", 1)]
        comps = [_comp("1001")]
        warns = validate_sheet(gate, finish, comps, set(), 2)
        assert not any(isinstance(w, NoRecordedFinishWarning) for w in warns)

    def test_no_recorded_finish_not_fired_below_cap(self) -> None:
        """NoRecordedFinishWarning does NOT fire for a boat below the gate cap.

        3-lap FINISH_AT_GATE: gate cap = 2. Boat with only 1 rounding → not at cap.
        """
        gate = [_gate("1001", 1)]
        finish: list[FinishEntry] = []
        comps = [_comp("1001")]
        warns = validate_sheet(gate, finish, comps, set(), 3)
        assert not any(isinstance(w, NoRecordedFinishWarning) for w in warns)

    def test_no_recorded_finish_not_fired_for_green_fleet(self) -> None:
        """NoRecordedFinishWarning does NOT fire for a Green Fleet boat."""
        gate = [_gate("GRN1", 1)]
        finish: list[FinishEntry] = []
        comps = [_comp("GRN1")]
        warns = validate_sheet(gate, finish, comps, {"GRN1"}, 2)
        assert not any(isinstance(w, NoRecordedFinishWarning) for w in warns)

    @pytest.mark.parametrize("letter_score", ["DNS", "DNC", "DNF"])
    def test_letter_score_conflict_fires(self, letter_score: str) -> None:
        """LetterScoreConflictWarning fires for DNS/DNC/DNF + gate list appearance."""
        gate = [_gate("1001", 1)]
        finish = [_finish("1001", 1, letter=letter_score)]
        comps = [_comp("1001")]
        warns = validate_sheet(gate, finish, comps, set(), 2)
        types = [type(w) for w in warns]
        assert LetterScoreConflictWarning in types
        w = next(x for x in warns if isinstance(x, LetterScoreConflictWarning))
        assert w.sail_number == "1001"
        assert w.letter_score == letter_score
        assert w.gate_roundings == 1

    def test_letter_score_conflict_not_fired_when_not_on_gate(self) -> None:
        """LetterScoreConflictWarning does NOT fire for DNS without gate roundings."""
        gate: list[GateRounding] = []
        finish = [_finish("1001", 1, letter="DNS")]
        comps = [_comp("1001")]
        warns = validate_sheet(gate, finish, comps, set(), 2)
        assert not any(isinstance(w, LetterScoreConflictWarning) for w in warns)

    def test_letter_score_conflict_not_fired_for_other_codes(self) -> None:
        """LetterScoreConflictWarning does NOT fire for DSQ (only DNS/DNC/DNF)."""
        gate = [_gate("1001", 1)]
        finish = [_finish("1001", 1, letter="DSQ")]
        comps = [_comp("1001")]
        warns = validate_sheet(gate, finish, comps, set(), 2)
        assert not any(isinstance(w, LetterScoreConflictWarning) for w in warns)

    def test_clean_sheet_no_warnings(self) -> None:
        """No warnings for a clean, consistent gate and finish sheet."""
        # 2-lap FINISH_AT_GATE: gate cap = 1; boat 1001 has 1 rounding and finishes
        gate = [_gate("1001", 1), _gate("2002", 2)]
        finish = [_finish("1001", 1), _finish("2002", 2)]
        comps = [_comp("1001"), _comp("2002")]
        warns = validate_sheet(gate, finish, comps, set(), 2)
        assert warns == []

    def test_separate_pin_no_recorded_finish_fires(self) -> None:
        """NoRecordedFinishWarning fires under SEPARATE_PIN at the correct cap.

        SEPARATE_PIN, 2 laps: gate cap = 2. Boat with 2 roundings and no finish.
        """
        gate = [_gate("1001", 1), _gate("2002", 2), _gate("1001", 3)]
        finish: list[FinishEntry] = []
        comps = [_comp("1001"), _comp("2002")]
        warns = validate_sheet(
            gate, finish, comps, set(), 2, FinishLineConfig.SEPARATE_PIN
        )
        nrf = [w for w in warns if isinstance(w, NoRecordedFinishWarning)]
        assert any(w.sail_number == "1001" for w in nrf)


# ===========================================================================
# Race-level: validate_race_setup
# ===========================================================================


class TestValidateRaceSetup:
    """Tests for validate_race_setup."""

    def test_no_gp_value_1lap(self) -> None:
        """NoGPValueWarning fires for a 1-lap course."""
        session = _session(num_laps=1)
        warns = validate_race_setup(session)
        types = [type(w) for w in warns]
        assert NoGPValueWarning in types
        w = next(x for x in warns if isinstance(x, NoGPValueWarning))
        assert w.num_laps == 1
        assert "1-lap" in w.reason

    def test_no_gp_value_no_gate_course(self) -> None:
        """NoGPValueWarning fires when the course type has no gate."""
        session = _session(course_type="Triangle Course", num_laps=2)
        warns = validate_race_setup(session)
        types = [type(w) for w in warns]
        assert NoGPValueWarning in types
        w = next(x for x in warns if isinstance(x, NoGPValueWarning))
        assert "gate" in w.reason.lower()

    def test_no_gp_value_not_fired_for_standard_course(self) -> None:
        """NoGPValueWarning does NOT fire for the standard gate course."""
        session = _session(course_type="Standard WASZP W/L (Gate)", num_laps=2)
        warns = validate_race_setup(session)
        assert not any(isinstance(w, NoGPValueWarning) for w in warns)

    def test_unknown_rig_size_fires(self) -> None:
        """UnknownRigSizeWarning fires for a competitor with an unknown rig size."""
        comps = [_comp("1001", rig="3.9")]
        session = _session(competitors=comps)
        warns = validate_race_setup(session)
        types = [type(w) for w in warns]
        assert UnknownRigSizeWarning in types
        w = next(x for x in warns if isinstance(x, UnknownRigSizeWarning))
        assert w.sail_number == "1001"
        assert w.rig_size == "3.9"

    def test_unknown_rig_size_not_fired_for_known(self) -> None:
        """UnknownRigSizeWarning does NOT fire for a known rig size."""
        for rig in ("8.2", "7.5", "6.9", "5.8"):
            comps = [_comp("1001", rig=rig)]
            session = _session(competitors=comps)
            warns = validate_race_setup(session)
            assert not any(isinstance(w, UnknownRigSizeWarning) for w in warns), rig

    def test_missing_finish_window_marker_fires_for_separate_pin(self) -> None:
        """MissingFinishWindowMarkerWarning fires for SEPARATE_PIN with no marker."""
        session = _session(
            finish_line_config=FinishLineConfig.SEPARATE_PIN,
            finish_window_marker_position=None,
        )
        warns = validate_race_setup(session)
        types = [type(w) for w in warns]
        assert MissingFinishWindowMarkerWarning in types

    def test_missing_finish_window_marker_not_fired_for_finish_at_gate(self) -> None:
        """MissingFinishWindowMarkerWarning does NOT fire for FINISH_AT_GATE."""
        session = _session(finish_line_config=FinishLineConfig.FINISH_AT_GATE)
        warns = validate_race_setup(session)
        assert not any(isinstance(w, MissingFinishWindowMarkerWarning) for w in warns)

    def test_missing_finish_window_marker_not_fired_when_marker_placed(self) -> None:
        """MissingFinishWindowMarkerWarning does NOT fire when marker is placed."""
        gate = [_gate("1001", 1)]
        session = _session(
            finish_line_config=FinishLineConfig.SEPARATE_PIN,
            finish_window_marker_position=0,
            gate_roundings=gate,
        )
        warns = validate_race_setup(session)
        assert not any(isinstance(w, MissingFinishWindowMarkerWarning) for w in warns)

    def test_lead_boat_violation_82_fleet(self) -> None:
        """LeadBoatViolationWarning fires independently for the 8.2 fleet."""
        # 2-lap race; 8.2 boat on finish list with only 1 lap (GP finish)
        comps = [_comp("8001", rig="8.2"), _comp("7001", rig="7.5")]
        gate = [_gate("7001", 1)]  # 7001 is at gate cap (1 rounding)
        # 8001 is finish-only (1 lap), 7001 has 1 rounding + finishes = 2 laps
        finish = [_finish("8001", 1), _finish("7001", 2)]
        session = _session(
            competitors=comps, gate_roundings=gate, finish_entries=finish
        )
        warns = validate_race_setup(session)
        lbv = [w for w in warns if isinstance(w, LeadBoatViolationWarning)]
        assert any(
            w.fleet_group == "8.2" and w.sail_number == "8001" for w in lbv
        ), f"Expected 8.2 violation; got {lbv}"

    def test_lead_boat_violation_non82_fleet(self) -> None:
        """LeadBoatViolationWarning fires independently for the non-8.2 fleet."""
        comps = [_comp("8001", rig="8.2"), _comp("7001", rig="7.5")]
        gate = [_gate("8001", 1)]  # 8001 at cap
        finish = [_finish("7001", 1), _finish("8001", 2)]
        session = _session(
            competitors=comps, gate_roundings=gate, finish_entries=finish
        )
        warns = validate_race_setup(session)
        lbv = [w for w in warns if isinstance(w, LeadBoatViolationWarning)]
        assert any(
            w.fleet_group == "non-8.2" and w.sail_number == "7001" for w in lbv
        ), f"Expected non-8.2 violation; got {lbv}"

    def test_lead_boat_violation_not_fired_when_lead_boat_qualified(self) -> None:
        """LeadBoatViolationWarning does NOT fire when lead boat has required laps."""
        comps = [_comp("1001", rig="8.2")]
        gate = [_gate("1001", 1)]  # 1 rounding = gate cap for 2-lap race
        finish = [_finish("1001", 1)]  # finishes → 2 laps
        session = _session(
            competitors=comps, gate_roundings=gate, finish_entries=finish
        )
        warns = validate_race_setup(session)
        assert not any(isinstance(w, LeadBoatViolationWarning) for w in warns)

    def test_clean_race_setup_no_warnings(self) -> None:
        """No warnings for a clean, valid race session."""
        comps = [_comp("1001", rig="8.2"), _comp("2002", rig="7.5")]
        gate = [_gate("1001", 1), _gate("2002", 2)]
        finish = [_finish("1001", 1), _finish("2002", 2)]
        session = _session(
            competitors=comps,
            gate_roundings=gate,
            finish_entries=finish,
            finish_line_config=FinishLineConfig.FINISH_AT_GATE,
        )
        warns = validate_race_setup(session)
        assert warns == []

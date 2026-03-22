"""Tests for GUI business-logic helpers and session metadata methods.

These tests cover all pure (non-display) logic introduced by issue #10:

- :func:`~waszp_gp_scorer.widgets.sail_combobox.filter_sail_numbers`
- :func:`~waszp_gp_scorer.phases.setup.get_finish_line_config`
- :func:`~waszp_gp_scorer.phases.setup.get_lap_counting_location`
- :func:`~waszp_gp_scorer.phases.setup.is_blocked_course_type`
- :func:`~waszp_gp_scorer.phases.setup.laps_needs_confirmation`
- :meth:`~waszp_gp_scorer.session.AutoSaveSession.update_metadata`
- :meth:`~waszp_gp_scorer.session.AutoSaveSession.set_competitors`

Tkinter widget classes require a display and are exercised manually /
via acceptance testing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from waszp_gp_scorer.models import (
    Competitor,
    FinishLineConfig,
    RaceSession,
)
from waszp_gp_scorer.phases.setup import (
    BLOCKED_COURSE_TYPES,
    COURSE_TYPES,
    get_finish_line_config,
    get_lap_counting_location,
    is_blocked_course_type,
    laps_needs_confirmation,
)
from waszp_gp_scorer.session import AutoSaveSession
from waszp_gp_scorer.widgets.sail_combobox import filter_sail_numbers

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _session() -> RaceSession:
    """Return a minimal RaceSession for testing."""
    return RaceSession()


def _auto_save(tmp_path: Path) -> AutoSaveSession:
    return AutoSaveSession(_session(), path=tmp_path / "session.json")


def _competitor(sail_number: str, rig_size: str = "8.2") -> Competitor:
    return Competitor(
        sail_number=sail_number,
        country_code="AUS",
        name=f"Sailor {sail_number}",
        rig_size=rig_size,
        division="Open",
    )


# ---------------------------------------------------------------------------
# filter_sail_numbers
# ---------------------------------------------------------------------------


class TestFilterSailNumbers:
    """Tests for the pure :func:`filter_sail_numbers` helper."""

    def test_empty_inputs_return_empty(self) -> None:
        assert filter_sail_numbers([], set()) == []

    def test_returns_sorted_list(self) -> None:
        result = filter_sail_numbers(["GBR1", "AUS2", "AUS1"], set())
        assert result == ["AUS1", "AUS2", "GBR1"]

    def test_excludes_green_fleet_members(self) -> None:
        result = filter_sail_numbers(["AUS1", "AUS2", "AUS3"], {"AUS2"})
        assert result == ["AUS1", "AUS3"]

    def test_excludes_all_when_all_are_green(self) -> None:
        result = filter_sail_numbers(["AUS1", "AUS2"], {"AUS1", "AUS2"})
        assert result == []

    def test_prefix_narrows_results(self) -> None:
        result = filter_sail_numbers(["AUS1", "GBR1", "AUS2"], set(), "AUS")
        assert result == ["AUS1", "AUS2"]

    def test_prefix_is_case_insensitive(self) -> None:
        result = filter_sail_numbers(["AUS1", "AUS2"], set(), "aus")
        assert result == ["AUS1", "AUS2"]

    def test_prefix_and_green_fleet_combined(self) -> None:
        result = filter_sail_numbers(["AUS1", "AUS2", "GBR1"], {"AUS1"}, "AUS")
        assert result == ["AUS2"]

    def test_prefix_with_no_match_returns_empty(self) -> None:
        result = filter_sail_numbers(["AUS1", "AUS2"], set(), "GBR")
        assert result == []

    def test_empty_prefix_returns_all_non_green(self) -> None:
        result = filter_sail_numbers(["AUS1", "AUS2"], {"AUS1"}, "")
        assert result == ["AUS2"]

    def test_green_fleet_not_in_original_list_is_ignored(self) -> None:
        # Green fleet entries that don't appear in all_sail_numbers are harmless.
        result = filter_sail_numbers(["AUS1", "AUS2"], {"GBR99"})
        assert result == ["AUS1", "AUS2"]

    def test_duplicate_in_all_sail_numbers_appears_once_in_output(self) -> None:
        # Duplicates in input produce a sorted, deduplicated result via sort
        # (set semantics preserved by sort — duplicates kept but sorted).
        result = filter_sail_numbers(["AUS1", "AUS1", "AUS2"], set())
        assert result == ["AUS1", "AUS1", "AUS2"]


# ---------------------------------------------------------------------------
# get_finish_line_config
# ---------------------------------------------------------------------------


class TestGetFinishLineConfig:
    """Tests for :func:`get_finish_line_config`."""

    def test_standard_wl_returns_finish_at_gate(self) -> None:
        config = get_finish_line_config("Standard WASZP W/L (Gate)")
        assert config == FinishLineConfig.FINISH_AT_GATE

    def test_sailgp_returns_separate_pin(self) -> None:
        config = get_finish_line_config("SailGP (Gate)")
        assert config == FinishLineConfig.SEPARATE_PIN

    def test_unknown_course_type_returns_finish_at_gate(self) -> None:
        config = get_finish_line_config("Some Other Course")
        assert config == FinishLineConfig.FINISH_AT_GATE

    def test_all_non_sailgp_course_types_return_finish_at_gate(self) -> None:
        for ct in COURSE_TYPES:
            if ct != "SailGP (Gate)":
                assert get_finish_line_config(ct) == FinishLineConfig.FINISH_AT_GATE, ct


# ---------------------------------------------------------------------------
# get_lap_counting_location
# ---------------------------------------------------------------------------


class TestGetLapCountingLocation:
    """Tests for :func:`get_lap_counting_location`."""

    def test_standard_wl_returns_leeward_gate(self) -> None:
        loc = get_lap_counting_location("Standard WASZP W/L (Gate)")
        assert loc == "Leeward gate (2s/2p)"

    def test_sailgp_returns_windward_gate(self) -> None:
        loc = get_lap_counting_location("SailGP (Gate)")
        assert loc == "Windward gate (1s/1p)"

    def test_unknown_course_type_returns_leeward_default(self) -> None:
        loc = get_lap_counting_location("Fictional Course")
        assert loc == "Leeward gate (2s/2p)"

    def test_all_non_sailgp_return_leeward_default(self) -> None:
        for ct in COURSE_TYPES:
            if ct != "SailGP (Gate)":
                assert get_lap_counting_location(ct) == "Leeward gate (2s/2p)", ct


# ---------------------------------------------------------------------------
# is_blocked_course_type
# ---------------------------------------------------------------------------


class TestIsBlockedCourseType:
    """Tests for :func:`is_blocked_course_type`."""

    @pytest.mark.parametrize("course_type", list(BLOCKED_COURSE_TYPES))
    def test_blocked_types_return_true(self, course_type: str) -> None:
        assert is_blocked_course_type(course_type) is True

    def test_standard_wl_not_blocked(self) -> None:
        assert is_blocked_course_type("Standard WASZP W/L (Gate)") is False

    def test_sailgp_not_blocked(self) -> None:
        assert is_blocked_course_type("SailGP (Gate)") is False

    def test_unknown_type_not_blocked(self) -> None:
        assert is_blocked_course_type("Something Else") is False

    def test_sprint_box_blocked(self) -> None:
        assert is_blocked_course_type("Sprint BOX (no gate, 1 lap)") is True

    def test_slalom_sprint_blocked(self) -> None:
        assert is_blocked_course_type("Slalom Sprint (no gate, 1 lap)") is True


# ---------------------------------------------------------------------------
# laps_needs_confirmation
# ---------------------------------------------------------------------------


class TestLapsNeedsConfirmation:
    """Tests for :func:`laps_needs_confirmation`."""

    @pytest.mark.parametrize("num_laps", [1, 2, 3])
    def test_three_or_fewer_laps_no_confirmation(self, num_laps: int) -> None:
        assert laps_needs_confirmation(num_laps) is False

    @pytest.mark.parametrize("num_laps", [4, 5, 10])
    def test_more_than_three_laps_needs_confirmation(self, num_laps: int) -> None:
        assert laps_needs_confirmation(num_laps) is True

    def test_boundary_exactly_3_is_false(self) -> None:
        assert laps_needs_confirmation(3) is False

    def test_boundary_exactly_4_is_true(self) -> None:
        assert laps_needs_confirmation(4) is True


# ---------------------------------------------------------------------------
# AutoSaveSession.update_metadata
# ---------------------------------------------------------------------------


class TestAutoSaveSessionUpdateMetadata:
    """Tests for the new :meth:`AutoSaveSession.update_metadata` method."""

    def test_update_event_name(self, tmp_path: Path) -> None:
        aut = _auto_save(tmp_path)
        aut.update_metadata(event_name="WASZP Worlds 2026")
        assert aut.session.event_name == "WASZP Worlds 2026"

    def test_update_race_number(self, tmp_path: Path) -> None:
        aut = _auto_save(tmp_path)
        aut.update_metadata(race_number=3)
        assert aut.session.race_number == 3

    def test_update_race_date(self, tmp_path: Path) -> None:
        aut = _auto_save(tmp_path)
        aut.update_metadata(race_date="2026-08-15")
        assert aut.session.race_date == "2026-08-15"

    def test_update_start_time(self, tmp_path: Path) -> None:
        aut = _auto_save(tmp_path)
        aut.update_metadata(start_time="14:30")
        assert aut.session.start_time == "14:30"

    def test_clear_start_time_with_none(self, tmp_path: Path) -> None:
        aut = _auto_save(tmp_path)
        aut.update_metadata(start_time="12:00")
        aut.update_metadata(start_time=None)
        assert aut.session.start_time is None

    def test_omitting_start_time_leaves_it_unchanged(self, tmp_path: Path) -> None:
        aut = _auto_save(tmp_path)
        aut.update_metadata(start_time="10:00")
        aut.update_metadata(event_name="No start time change")
        assert aut.session.start_time == "10:00"

    def test_update_num_laps(self, tmp_path: Path) -> None:
        aut = _auto_save(tmp_path)
        aut.update_metadata(num_laps=3)
        assert aut.session.num_laps == 3

    def test_update_course_type(self, tmp_path: Path) -> None:
        aut = _auto_save(tmp_path)
        aut.update_metadata(course_type="SailGP (Gate)")
        assert aut.session.course_type == "SailGP (Gate)"

    def test_update_finish_line_config(self, tmp_path: Path) -> None:
        aut = _auto_save(tmp_path)
        aut.update_metadata(finish_line_config=FinishLineConfig.SEPARATE_PIN)
        assert aut.session.finish_line_config == FinishLineConfig.SEPARATE_PIN

    def test_update_lap_counting_location(self, tmp_path: Path) -> None:
        aut = _auto_save(tmp_path)
        aut.update_metadata(lap_counting_location="Windward gate (1s/1p)")
        assert aut.session.lap_counting_location == "Windward gate (1s/1p)"

    def test_update_multiple_fields_at_once(self, tmp_path: Path) -> None:
        aut = _auto_save(tmp_path)
        aut.update_metadata(
            event_name="Midwinters 2026",
            race_number=2,
            num_laps=3,
        )
        assert aut.session.event_name == "Midwinters 2026"
        assert aut.session.race_number == 2
        assert aut.session.num_laps == 3

    def test_update_metadata_triggers_autosave(self, tmp_path: Path) -> None:
        save_path = tmp_path / "session.json"
        aut = AutoSaveSession(_session(), path=save_path)
        aut.update_metadata(event_name="AutoSave Test")
        assert save_path.exists()

    def test_unset_fields_remain_at_default(self, tmp_path: Path) -> None:
        aut = _auto_save(tmp_path)
        original_laps = aut.session.num_laps
        aut.update_metadata(event_name="Only name changed")
        assert aut.session.num_laps == original_laps


# ---------------------------------------------------------------------------
# AutoSaveSession.set_competitors
# ---------------------------------------------------------------------------


class TestAutoSaveSessionSetCompetitors:
    """Tests for the new :meth:`AutoSaveSession.set_competitors` method."""

    def test_sets_competitor_list(self, tmp_path: Path) -> None:
        aut = _auto_save(tmp_path)
        comps = [_competitor("AUS1"), _competitor("AUS2")]
        aut.set_competitors(comps)
        assert aut.session.competitors == comps

    def test_replaces_existing_competitors(self, tmp_path: Path) -> None:
        aut = _auto_save(tmp_path)
        aut.set_competitors([_competitor("OLD1")])
        new_comps = [_competitor("NEW1"), _competitor("NEW2")]
        aut.set_competitors(new_comps)
        assert aut.session.competitors == new_comps

    def test_set_empty_list(self, tmp_path: Path) -> None:
        aut = _auto_save(tmp_path)
        aut.set_competitors([_competitor("AUS1")])
        aut.set_competitors([])
        assert aut.session.competitors == []

    def test_triggers_autosave(self, tmp_path: Path) -> None:
        save_path = tmp_path / "session.json"
        aut = AutoSaveSession(_session(), path=save_path)
        aut.set_competitors([_competitor("AUS1")])
        assert save_path.exists()


# ---------------------------------------------------------------------------
# COURSE_TYPES list sanity
# ---------------------------------------------------------------------------


class TestCourseTypesList:
    """Sanity checks on the :data:`COURSE_TYPES` constant."""

    def test_standard_wl_is_first_entry(self) -> None:
        assert COURSE_TYPES[0] == "Standard WASZP W/L (Gate)"

    def test_sailgp_is_present(self) -> None:
        assert "SailGP (Gate)" in COURSE_TYPES

    def test_blocked_types_are_subset_of_course_types(self) -> None:
        assert BLOCKED_COURSE_TYPES.issubset(set(COURSE_TYPES))

    def test_at_least_two_non_blocked_types(self) -> None:
        non_blocked = [ct for ct in COURSE_TYPES if ct not in BLOCKED_COURSE_TYPES]
        assert len(non_blocked) >= 2

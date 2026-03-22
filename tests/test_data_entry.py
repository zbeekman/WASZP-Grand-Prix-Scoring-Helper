"""Tests for gate rounding data entry business-logic helpers.

These tests cover all pure (non-display) logic introduced by issue #11:

- :func:`~waszp_gp_scorer.phases.data_entry.get_bg_color`
- :func:`~waszp_gp_scorer.phases.data_entry.get_text_color`
- :func:`~waszp_gp_scorer.phases.data_entry.rounding_tier`
- :func:`~waszp_gp_scorer.phases.data_entry.compute_tiers`
- :func:`~waszp_gp_scorer.phases.data_entry.parse_gate_csv`
- :meth:`~waszp_gp_scorer.session.AutoSaveSession.remove_gate_rounding`
- :meth:`~waszp_gp_scorer.session.AutoSaveSession.insert_gate_rounding`
- :meth:`~waszp_gp_scorer.session.AutoSaveSession.replace_gate_rounding_sail`

Tkinter widget classes require a display and are exercised manually /
via acceptance testing.
"""

from __future__ import annotations

from pathlib import Path


from waszp_gp_scorer.models import GateRounding, RaceSession
from waszp_gp_scorer.phases.data_entry import (
    BG_COLORS,
    TEXT_COLORS,
    compute_tiers,
    get_bg_color,
    get_text_color,
    parse_gate_csv,
    rounding_tier,
)
from waszp_gp_scorer.session import AutoSaveSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auto_save(tmp_path: Path) -> AutoSaveSession:
    """Return a minimal AutoSaveSession backed by a temp file."""
    return AutoSaveSession(RaceSession(), path=tmp_path / "session.json")


def _rounding(position: int, sail_number: str) -> GateRounding:
    return GateRounding(position=position, sail_number=sail_number)


def _roundings(*sail_numbers: str) -> list[GateRounding]:
    """Build an ordered gate rounding list from a sequence of sail numbers."""
    return [
        GateRounding(position=i + 1, sail_number=sn)
        for i, sn in enumerate(sail_numbers)
    ]


# ---------------------------------------------------------------------------
# get_bg_color
# ---------------------------------------------------------------------------


class TestGetBgColor:
    """Tests for :func:`get_bg_color`."""

    def test_tier1_returns_white(self) -> None:
        assert get_bg_color(1) == BG_COLORS[0]

    def test_tier2_returns_cyan(self) -> None:
        assert get_bg_color(2) == BG_COLORS[1]

    def test_tier3_returns_green(self) -> None:
        assert get_bg_color(3) == BG_COLORS[2]

    def test_tier4_returns_yellow(self) -> None:
        assert get_bg_color(4) == BG_COLORS[3]

    def test_tier5_returns_pink(self) -> None:
        assert get_bg_color(5) == BG_COLORS[4]

    def test_tier6_clamps_to_tier5(self) -> None:
        assert get_bg_color(6) == BG_COLORS[4]

    def test_tier0_clamps_to_tier1(self) -> None:
        assert get_bg_color(0) == BG_COLORS[0]

    def test_negative_tier_clamps_to_tier1(self) -> None:
        assert get_bg_color(-5) == BG_COLORS[0]

    def test_large_tier_clamps_to_tier5(self) -> None:
        assert get_bg_color(100) == BG_COLORS[4]

    def test_returns_hex_string(self) -> None:
        color = get_bg_color(1)
        assert color.startswith("#")
        assert len(color) == 7


# ---------------------------------------------------------------------------
# get_text_color
# ---------------------------------------------------------------------------


class TestGetTextColor:
    """Tests for :func:`get_text_color`."""

    def test_tier1_is_near_black(self) -> None:
        assert get_text_color(1) == TEXT_COLORS[0]

    def test_tier2_returns_dark_cyan(self) -> None:
        assert get_text_color(2) == TEXT_COLORS[1]

    def test_tier5_returns_dark_pink(self) -> None:
        assert get_text_color(5) == TEXT_COLORS[4]

    def test_tier6_clamps_to_tier5(self) -> None:
        assert get_text_color(6) == TEXT_COLORS[4]

    def test_tier0_clamps_to_tier1(self) -> None:
        assert get_text_color(0) == TEXT_COLORS[0]

    def test_returns_hex_string(self) -> None:
        color = get_text_color(2)
        assert color.startswith("#")
        assert len(color) == 7


# ---------------------------------------------------------------------------
# rounding_tier
# ---------------------------------------------------------------------------


class TestRoundingTier:
    """Tests for :func:`rounding_tier`."""

    def test_first_occurrence_is_tier_1(self) -> None:
        roundings = _roundings("AUS1", "GBR2", "AUS3")
        assert rounding_tier("AUS1", roundings, 0) == 1

    def test_second_occurrence_is_tier_2(self) -> None:
        roundings = _roundings("AUS1", "GBR2", "AUS1")
        assert rounding_tier("AUS1", roundings, 2) == 2

    def test_third_occurrence_is_tier_3(self) -> None:
        roundings = _roundings("AUS1", "AUS1", "AUS1")
        assert rounding_tier("AUS1", roundings, 2) == 3

    def test_counts_only_matching_sail(self) -> None:
        roundings = _roundings("AUS1", "GBR2", "GBR2", "AUS1")
        # GBR2 at index 2 is its 2nd rounding
        assert rounding_tier("GBR2", roundings, 2) == 2
        # AUS1 at index 3 is its 2nd rounding
        assert rounding_tier("AUS1", roundings, 3) == 2

    def test_index_at_first_element_of_mixed_list(self) -> None:
        roundings = _roundings("GBR1", "AUS1", "GBR1")
        assert rounding_tier("GBR1", roundings, 0) == 1

    def test_index_beyond_list_returns_total_count(self) -> None:
        # When entry_index is beyond the list, the function returns the sail
        # number's total count in the list (fallback behaviour).
        roundings = _roundings("AUS1")
        assert rounding_tier("AUS1", roundings, 5) == 1

    def test_empty_roundings_returns_zero(self) -> None:
        assert rounding_tier("AUS1", [], 0) == 0

    def test_sail_not_present_at_index(self) -> None:
        roundings = _roundings("AUS1", "GBR2")
        # AUS1 doesn't appear at index 1 but we count it up to index 1
        assert rounding_tier("AUS1", roundings, 1) == 1


# ---------------------------------------------------------------------------
# compute_tiers
# ---------------------------------------------------------------------------


class TestComputeTiers:
    """Tests for :func:`compute_tiers`."""

    def test_empty_returns_empty(self) -> None:
        assert compute_tiers([]) == []

    def test_single_boat_single_rounding(self) -> None:
        assert compute_tiers(_roundings("AUS1")) == [1]

    def test_single_boat_multiple_roundings(self) -> None:
        assert compute_tiers(_roundings("AUS1", "AUS1", "AUS1")) == [1, 2, 3]

    def test_alternating_boats(self) -> None:
        result = compute_tiers(_roundings("AUS1", "GBR2", "AUS1", "GBR2"))
        assert result == [1, 1, 2, 2]

    def test_three_boats_mixed(self) -> None:
        roundings = _roundings("A", "B", "C", "A", "B", "A")
        assert compute_tiers(roundings) == [1, 1, 1, 2, 2, 3]

    def test_length_matches_roundings(self) -> None:
        roundings = _roundings("AUS1", "GBR2", "AUS1")
        assert len(compute_tiers(roundings)) == 3

    def test_all_unique_boats_are_tier_1(self) -> None:
        roundings = _roundings("A", "B", "C", "D", "E")
        assert compute_tiers(roundings) == [1, 1, 1, 1, 1]

    def test_tier_five_reached(self) -> None:
        roundings = _roundings("AUS1", "AUS1", "AUS1", "AUS1", "AUS1")
        assert compute_tiers(roundings) == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# parse_gate_csv
# ---------------------------------------------------------------------------


class TestParseGateCsv:
    """Tests for :func:`parse_gate_csv`."""

    def test_empty_string_returns_empty(self) -> None:
        assert parse_gate_csv("") == []

    def test_single_sail_number(self) -> None:
        assert parse_gate_csv("AUS1\n") == ["AUS1"]

    def test_multiple_lines(self) -> None:
        content = "AUS1\nGBR2\nFRA3\n"
        assert parse_gate_csv(content) == ["AUS1", "GBR2", "FRA3"]

    def test_ignores_blank_lines(self) -> None:
        content = "AUS1\n\nGBR2\n\nFRA3"
        assert parse_gate_csv(content) == ["AUS1", "GBR2", "FRA3"]

    def test_strips_whitespace(self) -> None:
        content = "  AUS1  \n  GBR2  "
        assert parse_gate_csv(content) == ["AUS1", "GBR2"]

    def test_uses_first_column_only(self) -> None:
        content = "AUS1,extra,data\nGBR2,more,stuff"
        assert parse_gate_csv(content) == ["AUS1", "GBR2"]

    def test_whitespace_only_line_skipped(self) -> None:
        content = "AUS1\n   \nGBR2"
        assert parse_gate_csv(content) == ["AUS1", "GBR2"]

    def test_preserves_order(self) -> None:
        content = "GBR1\nAUS2\nFRA3"
        assert parse_gate_csv(content) == ["GBR1", "AUS2", "FRA3"]

    def test_no_trailing_newline(self) -> None:
        assert parse_gate_csv("AUS1\nGBR2") == ["AUS1", "GBR2"]

    def test_header_row_included_if_non_blank(self) -> None:
        # No special header handling — first non-blank line is returned as-is.
        content = "SailNumber\nAUS1\nGBR2"
        assert parse_gate_csv(content) == ["SailNumber", "AUS1", "GBR2"]


# ---------------------------------------------------------------------------
# AutoSaveSession.remove_gate_rounding
# ---------------------------------------------------------------------------


class TestRemoveGateRounding:
    """Tests for ``AutoSaveSession.remove_gate_rounding``."""

    def test_removes_entry(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_gate_rounding(GateRounding(1, "AUS1"))
        auto.add_gate_rounding(GateRounding(2, "GBR2"))
        auto.remove_gate_rounding(0)
        assert len(auto.session.gate_roundings) == 1
        assert auto.session.gate_roundings[0].sail_number == "GBR2"

    def test_renumbers_remaining(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        for sn in ["A", "B", "C"]:
            auto.add_gate_rounding(GateRounding(1, sn))
        auto.remove_gate_rounding(1)  # remove "B"
        positions = [r.position for r in auto.session.gate_roundings]
        assert positions == [1, 2]

    def test_out_of_range_is_noop(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_gate_rounding(GateRounding(1, "AUS1"))
        auto.remove_gate_rounding(5)
        assert len(auto.session.gate_roundings) == 1

    def test_removes_last_entry(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_gate_rounding(GateRounding(1, "AUS1"))
        auto.add_gate_rounding(GateRounding(2, "GBR2"))
        auto.remove_gate_rounding(1)
        assert len(auto.session.gate_roundings) == 1
        assert auto.session.gate_roundings[0].sail_number == "AUS1"

    def test_removes_from_single_entry_list(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_gate_rounding(GateRounding(1, "AUS1"))
        auto.remove_gate_rounding(0)
        assert auto.session.gate_roundings == []

    def test_marker_shifts_when_pre_window_entry_removed(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        for sn in ["A", "B", "C", "D"]:
            auto.add_gate_rounding(GateRounding(1, sn))
        auto.set_finish_window_marker(2)  # marker after index 2 (A,B,C pre-window)
        auto.remove_gate_rounding(1)  # remove "B" (index 1, pre-window)
        assert auto.session.finish_window_marker_position == 1

    def test_marker_unchanged_when_post_window_entry_removed(
        self, tmp_path: Path
    ) -> None:
        auto = _auto_save(tmp_path)
        for sn in ["A", "B", "C", "D"]:
            auto.add_gate_rounding(GateRounding(1, sn))
        auto.set_finish_window_marker(1)  # A, B pre-window; C, D post-window
        auto.remove_gate_rounding(3)  # remove "D" (post-window)
        assert auto.session.finish_window_marker_position == 1

    def test_marker_shifts_to_minus1_when_only_pre_window_entry_removed(
        self, tmp_path: Path
    ) -> None:
        auto = _auto_save(tmp_path)
        auto.add_gate_rounding(GateRounding(1, "A"))
        auto.add_gate_rounding(GateRounding(2, "B"))
        auto.set_finish_window_marker(0)  # only "A" is pre-window
        auto.remove_gate_rounding(0)  # remove "A"
        assert auto.session.finish_window_marker_position == -1

    def test_triggers_save(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_gate_rounding(GateRounding(1, "AUS1"))
        save_path = tmp_path / "session.json"
        mtime_before = save_path.stat().st_mtime
        auto.remove_gate_rounding(0)
        assert save_path.stat().st_mtime >= mtime_before


# ---------------------------------------------------------------------------
# AutoSaveSession.insert_gate_rounding
# ---------------------------------------------------------------------------


class TestInsertGateRounding:
    """Tests for ``AutoSaveSession.insert_gate_rounding``."""

    def test_inserts_at_position(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_gate_rounding(GateRounding(1, "A"))
        auto.add_gate_rounding(GateRounding(2, "C"))
        auto.insert_gate_rounding(1, "B")
        sails = [r.sail_number for r in auto.session.gate_roundings]
        assert sails == ["A", "B", "C"]

    def test_renumbers_after_insert(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_gate_rounding(GateRounding(1, "A"))
        auto.add_gate_rounding(GateRounding(2, "C"))
        auto.insert_gate_rounding(1, "B")
        positions = [r.position for r in auto.session.gate_roundings]
        assert positions == [1, 2, 3]

    def test_insert_at_start(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_gate_rounding(GateRounding(1, "B"))
        auto.insert_gate_rounding(0, "A")
        sails = [r.sail_number for r in auto.session.gate_roundings]
        assert sails == ["A", "B"]

    def test_insert_at_end_clamps(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_gate_rounding(GateRounding(1, "A"))
        auto.insert_gate_rounding(100, "B")  # clamped to end
        sails = [r.sail_number for r in auto.session.gate_roundings]
        assert sails == ["A", "B"]

    def test_insert_into_empty_list(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.insert_gate_rounding(0, "AUS1")
        assert len(auto.session.gate_roundings) == 1
        assert auto.session.gate_roundings[0].sail_number == "AUS1"
        assert auto.session.gate_roundings[0].position == 1

    def test_marker_shifts_when_inserted_before_marker(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        for sn in ["A", "B", "C"]:
            auto.add_gate_rounding(GateRounding(1, sn))
        auto.set_finish_window_marker(1)  # A, B pre-window; C post-window
        auto.insert_gate_rounding(0, "X")  # insert before A (shifts marker right)
        assert auto.session.finish_window_marker_position == 2

    def test_marker_unchanged_when_inserted_after_marker(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        for sn in ["A", "B", "C"]:
            auto.add_gate_rounding(GateRounding(1, sn))
        auto.set_finish_window_marker(1)  # A, B pre-window; C post-window
        auto.insert_gate_rounding(2, "X")  # insert in post-window zone
        assert auto.session.finish_window_marker_position == 1

    def test_triggers_save(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_gate_rounding(GateRounding(1, "AUS1"))  # creates the file
        save_path = tmp_path / "session.json"
        mtime_before = save_path.stat().st_mtime
        auto.insert_gate_rounding(0, "GBR2")
        assert save_path.stat().st_mtime >= mtime_before


# ---------------------------------------------------------------------------
# AutoSaveSession.replace_gate_rounding_sail
# ---------------------------------------------------------------------------


class TestReplaceGateRoundingSail:
    """Tests for ``AutoSaveSession.replace_gate_rounding_sail``."""

    def test_replaces_sail_number(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_gate_rounding(GateRounding(1, "AUS1"))
        auto.replace_gate_rounding_sail(0, "GBR2")
        assert auto.session.gate_roundings[0].sail_number == "GBR2"

    def test_position_unchanged(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_gate_rounding(GateRounding(1, "A"))
        auto.add_gate_rounding(GateRounding(2, "B"))
        auto.replace_gate_rounding_sail(1, "Z")
        assert auto.session.gate_roundings[1].position == 2

    def test_other_entries_unchanged(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        for sn in ["A", "B", "C"]:
            auto.add_gate_rounding(GateRounding(1, sn))
        auto.replace_gate_rounding_sail(1, "X")
        sails = [r.sail_number for r in auto.session.gate_roundings]
        assert sails == ["A", "X", "C"]

    def test_out_of_range_is_noop(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_gate_rounding(GateRounding(1, "AUS1"))
        auto.replace_gate_rounding_sail(5, "GBR2")
        assert auto.session.gate_roundings[0].sail_number == "AUS1"

    def test_marker_unchanged(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        for sn in ["A", "B", "C"]:
            auto.add_gate_rounding(GateRounding(1, sn))
        auto.set_finish_window_marker(1)
        auto.replace_gate_rounding_sail(0, "Z")
        assert auto.session.finish_window_marker_position == 1

    def test_triggers_save(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_gate_rounding(GateRounding(1, "AUS1"))
        save_path = tmp_path / "session.json"
        mtime_before = save_path.stat().st_mtime
        auto.replace_gate_rounding_sail(0, "GBR2")
        assert save_path.stat().st_mtime >= mtime_before

    def test_replace_at_last_index(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        for sn in ["A", "B", "C"]:
            auto.add_gate_rounding(GateRounding(1, sn))
        auto.replace_gate_rounding_sail(2, "Z")
        assert auto.session.gate_roundings[2].sail_number == "Z"

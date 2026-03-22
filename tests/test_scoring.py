"""Tests for scoring phase business-logic helpers.

These tests cover all pure (non-display) logic introduced by issue #13:

- :data:`~waszp_gp_scorer.phases.scoring.RESULT_COLUMNS`
- :func:`~waszp_gp_scorer.phases.scoring.finish_type_display`
- :func:`~waszp_gp_scorer.phases.scoring.collect_rig_sizes`
- :func:`~waszp_gp_scorer.phases.scoring.scored_result_row`
- :func:`~waszp_gp_scorer.phases.scoring.filter_results_by_rig`
- :func:`~waszp_gp_scorer.phases.scoring.original_finish_list_rows`

Tkinter widget classes require a display and are exercised manually /
via acceptance testing.
"""

from __future__ import annotations

from waszp_gp_scorer.models import (
    Competitor,
    FinishEntry,
    FinishType,
    ScoredResult,
)
from waszp_gp_scorer.phases.scoring import (
    RESULT_COLUMNS,
    collect_rig_sizes,
    filter_results_by_rig,
    finish_type_display,
    original_finish_list_rows,
    scored_result_row,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _competitor(
    sail_number: str = "AUS1",
    country: str = "AUS",
    name: str = "Test Sailor",
    rig_size: str = "8.2",
    division: str = "Open",
) -> Competitor:
    return Competitor(
        sail_number=sail_number,
        country_code=country,
        name=name,
        rig_size=rig_size,
        division=division,
    )


def _result(
    place: int = 1,
    sail_number: str = "AUS1",
    rig_size: str = "8.2",
    laps: int = 3,
    finish_type: FinishType = FinishType.STANDARD,
    letter_score: str | None = None,
) -> ScoredResult:
    return ScoredResult(
        place=place,
        competitor=_competitor(sail_number=sail_number, rig_size=rig_size),
        laps=laps,
        finish_type=finish_type,
        letter_score=letter_score,
    )


def _finish_entry(
    position: int, sail_number: str, letter_score: str | None = None
) -> FinishEntry:
    return FinishEntry(
        position=position, sail_number=sail_number, letter_score=letter_score
    )


# ---------------------------------------------------------------------------
# RESULT_COLUMNS
# ---------------------------------------------------------------------------


class TestResultColumns:
    """Verify the column-name constant."""

    def test_has_eight_columns(self) -> None:
        assert len(RESULT_COLUMNS) == 8

    def test_required_column_names(self) -> None:
        expected = (
            "Place",
            "Country",
            "Sail #",
            "Sailor Name",
            "Rig Size",
            "Division",
            "Laps",
            "Finish Type",
        )
        assert RESULT_COLUMNS == expected


# ---------------------------------------------------------------------------
# finish_type_display
# ---------------------------------------------------------------------------


class TestFinishTypeDisplay:
    """Tests for :func:`finish_type_display`."""

    def test_standard_returns_value(self) -> None:
        r = _result(finish_type=FinishType.STANDARD)
        assert finish_type_display(r) == "Standard"

    def test_gp_returns_value(self) -> None:
        r = _result(finish_type=FinishType.GP, laps=2)
        assert finish_type_display(r) == "GP"

    def test_gate_returns_value(self) -> None:
        r = _result(finish_type=FinishType.GATE, laps=1)
        assert finish_type_display(r) == "Gate"

    def test_finish_only_returns_value(self) -> None:
        r = _result(finish_type=FinishType.FINISH_ONLY, laps=1)
        assert finish_type_display(r) == "Finish Only"

    def test_error_nrf_returns_value(self) -> None:
        r = _result(finish_type=FinishType.ERROR_NO_RECORDED_FINISH, laps=2)
        assert finish_type_display(r) == "Error: No Recorded Finish"

    def test_letter_score_returns_code(self) -> None:
        r = _result(finish_type=FinishType.LETTER_SCORE, laps=0, letter_score="DNS")
        assert finish_type_display(r) == "DNS"

    def test_letter_score_dsq_returns_code(self) -> None:
        r = _result(finish_type=FinishType.LETTER_SCORE, laps=0, letter_score="DSQ")
        assert finish_type_display(r) == "DSQ"

    def test_letter_score_with_no_code_falls_back_to_value(self) -> None:
        # letter_score=None but finish_type=LETTER_SCORE (edge case)
        r = ScoredResult(
            place=1,
            competitor=_competitor(),
            laps=0,
            finish_type=FinishType.LETTER_SCORE,
            letter_score=None,
        )
        assert finish_type_display(r) == "Letter Score"


# ---------------------------------------------------------------------------
# collect_rig_sizes
# ---------------------------------------------------------------------------


class TestCollectRigSizes:
    """Tests for :func:`collect_rig_sizes`."""

    def test_empty_list_returns_empty(self) -> None:
        assert collect_rig_sizes([]) == []

    def test_single_rig_size(self) -> None:
        comps = [_competitor(sail_number="AUS1", rig_size="8.2")]
        assert collect_rig_sizes(comps) == ["8.2"]

    def test_duplicates_are_deduplicated(self) -> None:
        comps = [
            _competitor(sail_number="AUS1", rig_size="8.2"),
            _competitor(sail_number="AUS2", rig_size="8.2"),
            _competitor(sail_number="AUS3", rig_size="8.2"),
        ]
        assert collect_rig_sizes(comps) == ["8.2"]

    def test_multiple_rig_sizes_sorted(self) -> None:
        comps = [
            _competitor(sail_number="AUS1", rig_size="8.2"),
            _competitor(sail_number="AUS2", rig_size="7.5"),
            _competitor(sail_number="AUS3", rig_size="6.0"),
        ]
        assert collect_rig_sizes(comps) == ["6.0", "7.5", "8.2"]

    def test_mixed_duplicates_and_unique(self) -> None:
        comps = [
            _competitor(sail_number="AUS1", rig_size="8.2"),
            _competitor(sail_number="AUS2", rig_size="7.5"),
            _competitor(sail_number="AUS3", rig_size="8.2"),
        ]
        assert collect_rig_sizes(comps) == ["7.5", "8.2"]


# ---------------------------------------------------------------------------
# scored_result_row
# ---------------------------------------------------------------------------


class TestScoredResultRow:
    """Tests for :func:`scored_result_row`."""

    def test_returns_eight_element_tuple(self) -> None:
        row = scored_result_row(_result())
        assert len(row) == 8

    def test_all_strings(self) -> None:
        row = scored_result_row(_result())
        assert all(isinstance(v, str) for v in row)

    def test_standard_result_columns(self) -> None:
        r = ScoredResult(
            place=1,
            competitor=_competitor(
                sail_number="AUS42",
                country="AUS",
                name="Alice Smith",
                rig_size="8.2",
                division="Open",
            ),
            laps=3,
            finish_type=FinishType.STANDARD,
        )
        row = scored_result_row(r)
        expected = ("1", "AUS", "AUS42", "Alice Smith", "8.2", "Open", "3", "Standard")
        assert row == expected

    def test_zero_laps_renders_as_empty_string(self) -> None:
        r = _result(finish_type=FinishType.LETTER_SCORE, laps=0, letter_score="DNS")
        row = scored_result_row(r)
        assert row[6] == ""  # Laps column
        assert row[7] == "DNS"  # Finish Type column shows letter score code

    def test_place_is_string(self) -> None:
        r = _result(place=5)
        assert scored_result_row(r)[0] == "5"

    def test_laps_is_string(self) -> None:
        r = _result(laps=2)
        assert scored_result_row(r)[6] == "2"


# ---------------------------------------------------------------------------
# filter_results_by_rig
# ---------------------------------------------------------------------------


class TestFilterResultsByRig:
    """Tests for :func:`filter_results_by_rig`."""

    def test_empty_results_returns_empty(self) -> None:
        assert filter_results_by_rig([], {"8.2"}) == []

    def test_empty_selected_rigs_returns_empty(self) -> None:
        results = [_result(rig_size="8.2"), _result(rig_size="7.5")]
        assert filter_results_by_rig(results, set()) == []

    def test_all_selected_returns_all(self) -> None:
        results = [
            _result(sail_number="AUS1", rig_size="8.2"),
            _result(sail_number="AUS2", rig_size="7.5"),
        ]
        filtered = filter_results_by_rig(results, {"8.2", "7.5"})
        assert len(filtered) == 2

    def test_filter_single_rig_size(self) -> None:
        results = [
            _result(sail_number="AUS1", rig_size="8.2"),
            _result(sail_number="AUS2", rig_size="7.5"),
            _result(sail_number="AUS3", rig_size="8.2"),
        ]
        filtered = filter_results_by_rig(results, {"8.2"})
        sails = [r.competitor.sail_number for r in filtered]
        assert sails == ["AUS1", "AUS3"]

    def test_order_preserved(self) -> None:
        results = [
            _result(sail_number="AUS1", rig_size="8.2"),
            _result(sail_number="AUS2", rig_size="8.2"),
            _result(sail_number="AUS3", rig_size="8.2"),
        ]
        filtered = filter_results_by_rig(results, {"8.2"})
        sails = [r.competitor.sail_number for r in filtered]
        assert sails == ["AUS1", "AUS2", "AUS3"]

    def test_unknown_rig_size_excluded_when_not_selected(self) -> None:
        results = [_result(sail_number="AUS1", rig_size="Unknown")]
        filtered = filter_results_by_rig(results, {"8.2"})
        assert filtered == []


# ---------------------------------------------------------------------------
# original_finish_list_rows
# ---------------------------------------------------------------------------


class TestOriginalFinishListRows:
    """Tests for :func:`original_finish_list_rows`."""

    def test_empty_entries_returns_empty(self) -> None:
        rows = original_finish_list_rows([], {}, {})
        assert rows == []

    def test_row_count_matches_finish_entries(self) -> None:
        entries = [_finish_entry(1, "AUS1"), _finish_entry(2, "AUS2")]
        rows = original_finish_list_rows(entries, {}, {})
        assert len(rows) == 2

    def test_each_row_has_eight_columns(self) -> None:
        entries = [_finish_entry(1, "AUS1")]
        rows = original_finish_list_rows(entries, {}, {})
        assert len(rows[0]) == 8

    def test_position_used_as_place(self) -> None:
        entries = [_finish_entry(3, "AUS1")]
        rows = original_finish_list_rows(entries, {}, {})
        assert rows[0][0] == "3"

    def test_competitor_data_filled_from_map(self) -> None:
        entries = [_finish_entry(1, "AUS1")]
        comp = _competitor(
            sail_number="AUS1", country="AUS", name="Bob",
            rig_size="8.2", division="Open",
        )
        r = _result(
            sail_number="AUS1", rig_size="8.2", laps=3, finish_type=FinishType.STANDARD
        )
        rows = original_finish_list_rows(entries, {"AUS1": r}, {"AUS1": comp})
        row = rows[0]
        assert row[1] == "AUS"  # Country
        assert row[2] == "AUS1"  # Sail #
        assert row[3] == "Bob"  # Name
        assert row[4] == "8.2"  # Rig Size
        assert row[5] == "Open"  # Division
        assert row[6] == "3"  # Laps
        assert row[7] == "Standard"  # Finish Type

    def test_unknown_boat_has_placeholder_values(self) -> None:
        entries = [_finish_entry(1, "UNK99")]
        rows = original_finish_list_rows(entries, {}, {})
        row = rows[0]
        assert row[1] == "UNK"  # Country
        assert row[3] == "Unknown (UNK99)"  # Name
        assert row[4] == "Unknown"  # Rig Size

    def test_entry_with_letter_score_no_result(self) -> None:
        entries = [_finish_entry(1, "AUS1", letter_score="DNS")]
        rows = original_finish_list_rows(entries, {}, {})
        row = rows[0]
        assert row[6] == ""  # Laps empty
        assert row[7] == "DNS"  # Finish Type shows letter score

    def test_entry_with_result_overrides_letter_score(self) -> None:
        # If a result exists (e.g. reclassified from DNS to GATE), result wins
        entries = [_finish_entry(1, "AUS1", letter_score="DNS")]
        r = _result(sail_number="AUS1", laps=2, finish_type=FinishType.GATE)
        comp = _competitor(sail_number="AUS1")
        rows = original_finish_list_rows(entries, {"AUS1": r}, {"AUS1": comp})
        assert rows[0][7] == "Gate"

    def test_order_preserved_from_finish_entries(self) -> None:
        entries = [
            _finish_entry(1, "AUS3"),
            _finish_entry(2, "AUS1"),
            _finish_entry(3, "AUS2"),
        ]
        rows = original_finish_list_rows(entries, {}, {})
        sail_numbers = [row[2] for row in rows]
        assert sail_numbers == ["AUS3", "AUS1", "AUS2"]

    def test_laps_zero_renders_as_empty(self) -> None:
        entries = [_finish_entry(1, "AUS1")]
        r = _result(
            sail_number="AUS1",
            laps=0,
            finish_type=FinishType.LETTER_SCORE,
            letter_score="OCS",
        )
        comp = _competitor(sail_number="AUS1")
        rows = original_finish_list_rows(entries, {"AUS1": r}, {"AUS1": comp})
        assert rows[0][6] == ""  # Laps empty
        assert rows[0][7] == "OCS"  # Finish Type shows code

    def test_entry_no_result_and_no_letter_score_has_empty_type(self) -> None:
        entries = [_finish_entry(1, "AUS1")]
        rows = original_finish_list_rows(entries, {}, {})
        assert rows[0][6] == ""
        assert rows[0][7] == ""

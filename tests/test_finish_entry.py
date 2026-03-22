"""Tests for finish list data entry business-logic helpers.

These tests cover all pure (non-display) logic introduced by issue #12:

- :func:`~waszp_gp_scorer.phases.finish_entry.finish_entry_tier`
- :func:`~waszp_gp_scorer.phases.finish_entry.compute_finish_tiers`
- :func:`~waszp_gp_scorer.phases.finish_entry.parse_finish_csv`
- :data:`~waszp_gp_scorer.phases.finish_entry.LETTER_SCORES`
- :meth:`~waszp_gp_scorer.session.AutoSaveSession.remove_finish_entry`
- :meth:`~waszp_gp_scorer.session.AutoSaveSession.insert_finish_entry`
- :meth:`~waszp_gp_scorer.session.AutoSaveSession.replace_finish_entry_sail`
- :meth:`~waszp_gp_scorer.session.AutoSaveSession.set_finish_entry_letter_score`

Tkinter widget classes require a display and are exercised manually /
via acceptance testing.
"""

from __future__ import annotations

from pathlib import Path

from waszp_gp_scorer.models import FinishEntry, GateRounding, RaceSession
from waszp_gp_scorer.phases.finish_entry import (
    LETTER_SCORES,
    compute_finish_tiers,
    finish_entry_tier,
    parse_finish_csv,
)
from waszp_gp_scorer.session import AutoSaveSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auto_save(tmp_path: Path) -> AutoSaveSession:
    """Return a minimal AutoSaveSession backed by a temp file."""
    return AutoSaveSession(RaceSession(), path=tmp_path / "session.json")


def _gate(*sail_numbers: str) -> list[GateRounding]:
    """Build a gate rounding list from a sequence of sail numbers."""
    return [
        GateRounding(position=i + 1, sail_number=sn)
        for i, sn in enumerate(sail_numbers)
    ]


def _finish(*sail_numbers: str) -> list[FinishEntry]:
    """Build a finish entry list from a sequence of sail numbers."""
    return [
        FinishEntry(position=i + 1, sail_number=sn) for i, sn in enumerate(sail_numbers)
    ]


# ---------------------------------------------------------------------------
# LETTER_SCORES constant
# ---------------------------------------------------------------------------


class TestLetterScores:
    """Tests for the :data:`LETTER_SCORES` constant."""

    def test_has_14_codes(self) -> None:
        assert len(LETTER_SCORES) == 14

    def test_contains_dns(self) -> None:
        assert "DNS" in LETTER_SCORES

    def test_contains_dnc(self) -> None:
        assert "DNC" in LETTER_SCORES

    def test_contains_dnf(self) -> None:
        assert "DNF" in LETTER_SCORES

    def test_contains_dsq(self) -> None:
        assert "DSQ" in LETTER_SCORES

    def test_contains_dne(self) -> None:
        assert "DNE" in LETTER_SCORES

    def test_contains_ocs(self) -> None:
        assert "OCS" in LETTER_SCORES

    def test_contains_ufd(self) -> None:
        assert "UFD" in LETTER_SCORES

    def test_contains_bfd(self) -> None:
        assert "BFD" in LETTER_SCORES

    def test_contains_zfp(self) -> None:
        assert "ZFP" in LETTER_SCORES

    def test_contains_nsc(self) -> None:
        assert "NSC" in LETTER_SCORES

    def test_contains_ret(self) -> None:
        assert "RET" in LETTER_SCORES

    def test_contains_scp(self) -> None:
        assert "SCP" in LETTER_SCORES

    def test_contains_rdg(self) -> None:
        assert "RDG" in LETTER_SCORES

    def test_contains_dpi(self) -> None:
        assert "DPI" in LETTER_SCORES

    def test_all_uppercase(self) -> None:
        for code in LETTER_SCORES:
            assert code == code.upper()

    def test_no_duplicates(self) -> None:
        assert len(LETTER_SCORES) == len(set(LETTER_SCORES))


# ---------------------------------------------------------------------------
# finish_entry_tier
# ---------------------------------------------------------------------------


class TestFinishEntryTier:
    """Tests for :func:`finish_entry_tier`."""

    def test_no_gate_roundings_returns_zero(self) -> None:
        assert finish_entry_tier("AUS1", []) == 0

    def test_one_rounding_returns_one(self) -> None:
        assert finish_entry_tier("AUS1", _gate("AUS1")) == 1

    def test_two_roundings_returns_two(self) -> None:
        assert finish_entry_tier("AUS1", _gate("AUS1", "AUS2", "AUS1")) == 2

    def test_other_boats_not_counted(self) -> None:
        assert finish_entry_tier("AUS1", _gate("AUS2", "AUS3")) == 0

    def test_mixed_fleet_counts_only_target(self) -> None:
        roundings = _gate("AUS1", "AUS2", "AUS1", "AUS3", "AUS1")
        assert finish_entry_tier("AUS1", roundings) == 3
        assert finish_entry_tier("AUS2", roundings) == 1
        assert finish_entry_tier("AUS3", roundings) == 1

    def test_empty_gate_list(self) -> None:
        assert finish_entry_tier("AUS99", []) == 0


# ---------------------------------------------------------------------------
# compute_finish_tiers
# ---------------------------------------------------------------------------


class TestComputeFinishTiers:
    """Tests for :func:`compute_finish_tiers`."""

    def test_empty_entries_returns_empty(self) -> None:
        assert compute_finish_tiers([], []) == []

    def test_all_finish_only_returns_zeros(self) -> None:
        entries = _finish("AUS1", "AUS2")
        assert compute_finish_tiers(entries, []) == [0, 0]

    def test_single_entry_with_one_rounding(self) -> None:
        entries = _finish("AUS1")
        roundings = _gate("AUS1")
        assert compute_finish_tiers(entries, roundings) == [1]

    def test_multiple_entries_correct_tiers(self) -> None:
        entries = _finish("AUS1", "AUS2", "AUS3")
        roundings = _gate("AUS1", "AUS1", "AUS2")
        assert compute_finish_tiers(entries, roundings) == [2, 1, 0]

    def test_order_matches_finish_entries(self) -> None:
        entries = _finish("AUS3", "AUS1")
        roundings = _gate("AUS1", "AUS3", "AUS1")
        tiers = compute_finish_tiers(entries, roundings)
        assert tiers[0] == 1  # AUS3 has 1 rounding
        assert tiers[1] == 2  # AUS1 has 2 roundings

    def test_length_matches_finish_entries(self) -> None:
        entries = _finish("AUS1", "AUS2", "AUS3", "AUS4")
        tiers = compute_finish_tiers(entries, _gate("AUS1"))
        assert len(tiers) == 4


# ---------------------------------------------------------------------------
# parse_finish_csv
# ---------------------------------------------------------------------------


class TestParseFinishCsv:
    """Tests for :func:`parse_finish_csv`."""

    def test_empty_string_returns_empty(self) -> None:
        assert parse_finish_csv("") == []

    def test_single_sail_number(self) -> None:
        assert parse_finish_csv("AUS1") == ["AUS1"]

    def test_multiple_lines(self) -> None:
        assert parse_finish_csv("AUS1\nAUS2\nAUS3") == ["AUS1", "AUS2", "AUS3"]

    def test_blank_lines_skipped(self) -> None:
        assert parse_finish_csv("AUS1\n\nAUS2\n") == ["AUS1", "AUS2"]

    def test_comma_separated_uses_first_field(self) -> None:
        assert parse_finish_csv("AUS1,extra data\nAUS2,more") == ["AUS1", "AUS2"]

    def test_strips_whitespace(self) -> None:
        assert parse_finish_csv("  AUS1  \n  AUS2  ") == ["AUS1", "AUS2"]

    def test_preserves_order(self) -> None:
        content = "AUS5\nAUS3\nAUS1\nAUS4\nAUS2"
        assert parse_finish_csv(content) == ["AUS5", "AUS3", "AUS1", "AUS4", "AUS2"]

    def test_whitespace_only_lines_skipped(self) -> None:
        assert parse_finish_csv("AUS1\n   \nAUS2") == ["AUS1", "AUS2"]


# ---------------------------------------------------------------------------
# AutoSaveSession.remove_finish_entry
# ---------------------------------------------------------------------------


class TestRemoveFinishEntry:
    """Tests for ``AutoSaveSession.remove_finish_entry``."""

    def test_remove_only_entry(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_finish_entry(FinishEntry(position=1, sail_number="AUS1"))
        auto.remove_finish_entry(0)
        assert auto.session.finish_entries == []

    def test_remove_first_renumbers(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        for sn in ("AUS1", "AUS2", "AUS3"):
            auto.add_finish_entry(
                FinishEntry(
                    position=len(auto.session.finish_entries) + 1, sail_number=sn
                )
            )
        auto.remove_finish_entry(0)
        entries = auto.session.finish_entries
        assert len(entries) == 2
        assert entries[0].sail_number == "AUS2"
        assert entries[0].position == 1
        assert entries[1].position == 2

    def test_remove_last_entry(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        for sn in ("AUS1", "AUS2"):
            auto.add_finish_entry(
                FinishEntry(
                    position=len(auto.session.finish_entries) + 1, sail_number=sn
                )
            )
        auto.remove_finish_entry(1)
        assert len(auto.session.finish_entries) == 1
        assert auto.session.finish_entries[0].sail_number == "AUS1"

    def test_remove_middle_renumbers(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        for sn in ("AUS1", "AUS2", "AUS3"):
            auto.add_finish_entry(
                FinishEntry(
                    position=len(auto.session.finish_entries) + 1, sail_number=sn
                )
            )
        auto.remove_finish_entry(1)
        entries = auto.session.finish_entries
        assert [e.sail_number for e in entries] == ["AUS1", "AUS3"]
        assert [e.position for e in entries] == [1, 2]

    def test_out_of_range_is_noop(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_finish_entry(FinishEntry(position=1, sail_number="AUS1"))
        auto.remove_finish_entry(5)
        assert len(auto.session.finish_entries) == 1

    def test_empty_list_is_noop(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.remove_finish_entry(0)
        assert auto.session.finish_entries == []

    def test_triggers_save(self, tmp_path: Path) -> None:
        path = tmp_path / "session.json"
        auto = AutoSaveSession(RaceSession(), path=path)
        auto.add_finish_entry(FinishEntry(position=1, sail_number="AUS1"))
        auto.remove_finish_entry(0)
        assert path.exists()


# ---------------------------------------------------------------------------
# AutoSaveSession.insert_finish_entry
# ---------------------------------------------------------------------------


class TestInsertFinishEntry:
    """Tests for ``AutoSaveSession.insert_finish_entry``."""

    def test_insert_into_empty_list(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.insert_finish_entry(0, "AUS1")
        entries = auto.session.finish_entries
        assert len(entries) == 1
        assert entries[0].sail_number == "AUS1"
        assert entries[0].position == 1

    def test_insert_at_start_renumbers(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_finish_entry(FinishEntry(position=1, sail_number="AUS2"))
        auto.insert_finish_entry(0, "AUS1")
        entries = auto.session.finish_entries
        assert entries[0].sail_number == "AUS1"
        assert entries[0].position == 1
        assert entries[1].sail_number == "AUS2"
        assert entries[1].position == 2

    def test_insert_at_end(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_finish_entry(FinishEntry(position=1, sail_number="AUS1"))
        auto.insert_finish_entry(1, "AUS2")
        entries = auto.session.finish_entries
        assert entries[1].sail_number == "AUS2"
        assert entries[1].position == 2

    def test_insert_middle_renumbers(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        for sn in ("AUS1", "AUS3"):
            auto.add_finish_entry(
                FinishEntry(
                    position=len(auto.session.finish_entries) + 1, sail_number=sn
                )
            )
        auto.insert_finish_entry(1, "AUS2")
        entries = auto.session.finish_entries
        assert [e.sail_number for e in entries] == ["AUS1", "AUS2", "AUS3"]
        assert [e.position for e in entries] == [1, 2, 3]

    def test_insert_clamped_to_end_when_index_too_large(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_finish_entry(FinishEntry(position=1, sail_number="AUS1"))
        auto.insert_finish_entry(99, "AUS2")
        entries = auto.session.finish_entries
        assert entries[-1].sail_number == "AUS2"

    def test_insert_negative_clamps_to_start(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_finish_entry(FinishEntry(position=1, sail_number="AUS2"))
        auto.insert_finish_entry(-5, "AUS1")
        entries = auto.session.finish_entries
        assert entries[0].sail_number == "AUS1"

    def test_triggers_save(self, tmp_path: Path) -> None:
        path = tmp_path / "session.json"
        auto = AutoSaveSession(RaceSession(), path=path)
        auto.insert_finish_entry(0, "AUS1")
        assert path.exists()


# ---------------------------------------------------------------------------
# AutoSaveSession.replace_finish_entry_sail
# ---------------------------------------------------------------------------


class TestReplaceFinishEntrySail:
    """Tests for ``AutoSaveSession.replace_finish_entry_sail``."""

    def test_replace_only_entry(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_finish_entry(FinishEntry(position=1, sail_number="AUS1"))
        auto.replace_finish_entry_sail(0, "AUS99")
        assert auto.session.finish_entries[0].sail_number == "AUS99"

    def test_replace_first_of_several(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        for sn in ("AUS1", "AUS2", "AUS3"):
            auto.add_finish_entry(
                FinishEntry(
                    position=len(auto.session.finish_entries) + 1, sail_number=sn
                )
            )
        auto.replace_finish_entry_sail(0, "NZL1")
        entries = auto.session.finish_entries
        assert entries[0].sail_number == "NZL1"
        assert entries[1].sail_number == "AUS2"

    def test_replace_last_entry(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        for sn in ("AUS1", "AUS2"):
            auto.add_finish_entry(
                FinishEntry(
                    position=len(auto.session.finish_entries) + 1, sail_number=sn
                )
            )
        auto.replace_finish_entry_sail(1, "GBR1")
        assert auto.session.finish_entries[1].sail_number == "GBR1"

    def test_position_unchanged_after_replace(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_finish_entry(FinishEntry(position=1, sail_number="AUS1"))
        auto.replace_finish_entry_sail(0, "AUS2")
        assert auto.session.finish_entries[0].position == 1

    def test_out_of_range_is_noop(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_finish_entry(FinishEntry(position=1, sail_number="AUS1"))
        auto.replace_finish_entry_sail(5, "AUS99")
        assert auto.session.finish_entries[0].sail_number == "AUS1"

    def test_triggers_save(self, tmp_path: Path) -> None:
        path = tmp_path / "session.json"
        auto = AutoSaveSession(RaceSession(), path=path)
        auto.add_finish_entry(FinishEntry(position=1, sail_number="AUS1"))
        auto.replace_finish_entry_sail(0, "AUS2")
        assert path.exists()


# ---------------------------------------------------------------------------
# AutoSaveSession.set_finish_entry_letter_score
# ---------------------------------------------------------------------------


class TestSetFinishEntryLetterScore:
    """Tests for ``AutoSaveSession.set_finish_entry_letter_score``."""

    def test_set_dns(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_finish_entry(FinishEntry(position=1, sail_number="AUS1"))
        auto.set_finish_entry_letter_score(0, "DNS")
        assert auto.session.finish_entries[0].letter_score == "DNS"

    def test_set_dsq(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_finish_entry(FinishEntry(position=1, sail_number="AUS1"))
        auto.set_finish_entry_letter_score(0, "DSQ")
        assert auto.session.finish_entries[0].letter_score == "DSQ"

    def test_clear_letter_score(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_finish_entry(FinishEntry(position=1, sail_number="AUS1"))
        auto.set_finish_entry_letter_score(0, "DNS")
        auto.set_finish_entry_letter_score(0, None)
        assert auto.session.finish_entries[0].letter_score is None

    def test_set_all_14_codes(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_finish_entry(FinishEntry(position=1, sail_number="AUS1"))
        for code in LETTER_SCORES:
            auto.set_finish_entry_letter_score(0, code)
            assert auto.session.finish_entries[0].letter_score == code

    def test_out_of_range_is_noop(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.add_finish_entry(FinishEntry(position=1, sail_number="AUS1"))
        auto.set_finish_entry_letter_score(5, "DNS")
        assert auto.session.finish_entries[0].letter_score is None

    def test_empty_list_is_noop(self, tmp_path: Path) -> None:
        auto = _auto_save(tmp_path)
        auto.set_finish_entry_letter_score(0, "DNS")
        assert auto.session.finish_entries == []

    def test_letter_score_persisted_on_save(self, tmp_path: Path) -> None:
        path = tmp_path / "session.json"
        auto = AutoSaveSession(RaceSession(), path=path)
        auto.add_finish_entry(FinishEntry(position=1, sail_number="AUS1"))
        auto.set_finish_entry_letter_score(0, "DNF")
        # Verify the JSON was written.
        assert path.exists()
        text = path.read_text()
        assert "DNF" in text

    def test_triggers_save(self, tmp_path: Path) -> None:
        path = tmp_path / "session.json"
        auto = AutoSaveSession(RaceSession(), path=path)
        auto.add_finish_entry(FinishEntry(position=1, sail_number="AUS1"))
        auto.set_finish_entry_letter_score(0, "OCS")
        assert path.exists()

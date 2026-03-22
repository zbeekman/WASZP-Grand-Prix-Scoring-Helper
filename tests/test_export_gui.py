"""Tests for GUI export and exit-prompt pure helpers (issue #14).

Covers:
- :func:`~waszp_gp_scorer.phases.scoring.session_has_data`
- Default-filename convention via
  :func:`~waszp_gp_scorer.exporter.export_filename` (integration with
  the scoring phase export flow)

Tkinter widget classes require a display and are exercised manually /
via acceptance testing.
"""

from __future__ import annotations

from waszp_gp_scorer.exporter import export_filename
from waszp_gp_scorer.models import (
    Competitor,
    FinishEntry,
    GateRounding,
    RaceSession,
)
from waszp_gp_scorer.phases.scoring import session_has_data

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _session(**kwargs) -> RaceSession:  # type: ignore[no-untyped-def]
    """Return a minimal RaceSession, optionally overriding fields."""
    return RaceSession(**kwargs)


def _competitor(sail_number: str = "AUS1") -> Competitor:
    return Competitor(
        sail_number=sail_number,
        country_code="AUS",
        name=f"Sailor {sail_number}",
        rig_size="8.2",
        division="Open",
    )


# ---------------------------------------------------------------------------
# session_has_data
# ---------------------------------------------------------------------------


class TestSessionHasData:
    """Tests for :func:`session_has_data`."""

    def test_empty_session_returns_false(self) -> None:
        sess = _session()
        assert session_has_data(sess) is False

    def test_session_with_competitors_returns_true(self) -> None:
        sess = _session()
        sess.competitors = [_competitor()]
        assert session_has_data(sess) is True

    def test_session_with_gate_rounding_returns_true(self) -> None:
        sess = _session()
        sess.gate_roundings = [GateRounding(position=1, sail_number="AUS1")]
        assert session_has_data(sess) is True

    def test_session_with_finish_entry_returns_true(self) -> None:
        sess = _session()
        sess.finish_entries = [FinishEntry(position=1, sail_number="AUS1")]
        assert session_has_data(sess) is True

    def test_session_with_all_data_types_returns_true(self) -> None:
        sess = _session()
        sess.competitors = [_competitor()]
        sess.gate_roundings = [GateRounding(position=1, sail_number="AUS1")]
        sess.finish_entries = [FinishEntry(position=1, sail_number="AUS1")]
        assert session_has_data(sess) is True

    def test_empty_lists_return_false(self) -> None:
        sess = _session()
        sess.competitors = []
        sess.gate_roundings = []
        sess.finish_entries = []
        assert session_has_data(sess) is False

    def test_only_event_name_set_returns_false(self) -> None:
        sess = _session()
        sess.event_name = "WASZP Worlds 2026"
        assert session_has_data(sess) is False

    def test_multiple_competitors_returns_true(self) -> None:
        sess = _session()
        sess.competitors = [_competitor("AUS1"), _competitor("AUS2")]
        assert session_has_data(sess) is True


# ---------------------------------------------------------------------------
# export_filename convention (used by the scoring phase export button)
# ---------------------------------------------------------------------------


class TestExportFilenameConvention:
    """Verify the default export filename format used by the export button."""

    def test_default_filename_format(self) -> None:
        sess = _session()
        sess.event_name = "Spring Series"
        sess.race_number = 3
        sess.race_date = "2026-03-22"
        name = export_filename(sess)
        assert name == "Spring_Series_Race3_2026-03-22.xlsx"

    def test_filename_ends_with_xlsx(self) -> None:
        sess = _session()
        name = export_filename(sess)
        assert name.endswith(".xlsx")

    def test_spaces_replaced_with_underscores(self) -> None:
        sess = _session()
        sess.event_name = "Grand Prix Final"
        name = export_filename(sess)
        assert " " not in name

    def test_empty_event_name_uses_placeholder(self) -> None:
        sess = _session()
        sess.event_name = ""
        name = export_filename(sess)
        assert "Event" in name

    def test_race_number_in_filename(self) -> None:
        sess = _session()
        sess.race_number = 7
        name = export_filename(sess)
        assert "Race7" in name

    def test_race_date_in_filename(self) -> None:
        sess = _session()
        sess.race_date = "2026-08-15"
        name = export_filename(sess)
        assert "2026-08-15" in name

    def test_empty_race_date_uses_placeholder(self) -> None:
        sess = _session()
        sess.race_date = ""
        name = export_filename(sess)
        # Should not raise, and should produce a valid filename
        assert name.endswith(".xlsx")
        assert "Race" in name

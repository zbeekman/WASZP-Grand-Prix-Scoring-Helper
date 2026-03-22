"""Tests for session persistence (JSON save/resume)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from waszp_gp_scorer.models import (
    Competitor,
    FinishEntry,
    FinishLineConfig,
    GateRounding,
    RaceSession,
)
from waszp_gp_scorer.session import (
    AutoSaveSession,
    load,
    save,
    session_filename,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def minimal_session() -> RaceSession:
    """A bare RaceSession with all defaults."""
    return RaceSession()


@pytest.fixture()
def full_session() -> RaceSession:
    """A fully-populated RaceSession covering every field."""
    competitors = [
        Competitor(
            sail_number="AUS1234",
            country_code="AUS",
            name="Alice Smith",
            rig_size="8.2",
            division="Open",
            phone="0400000001",
            email="alice@example.com",
        ),
        Competitor(
            sail_number="GBR5678",
            country_code="GBR",
            name="Bob Jones",
            rig_size="7.5",
            division="Youth",
        ),
    ]
    gate_roundings = [
        GateRounding(position=1, sail_number="AUS1234"),
        GateRounding(position=2, sail_number="GBR5678"),
    ]
    finish_entries = [
        FinishEntry(position=1, sail_number="AUS1234"),
        FinishEntry(position=2, sail_number="GBR5678", letter_score="DNS"),
    ]
    return RaceSession(
        event_name="Test Event 2026",
        race_number=3,
        race_date="2026-03-22",
        start_time="14:00",
        num_laps=3,
        finish_line_config=FinishLineConfig.SEPARATE_PIN,
        finish_window_marker_position=2,
        lap_counting_location="Windward mark",
        competitors=competitors,
        green_fleet={"GRN001"},
        gate_roundings=gate_roundings,
        finish_entries=finish_entries,
    )


# ---------------------------------------------------------------------------
# session_filename
# ---------------------------------------------------------------------------


def test_session_filename_basic(full_session: RaceSession) -> None:
    name = session_filename(full_session)
    assert name == "Test_Event_2026_Race3_2026-03-22_session.json"


def test_session_filename_spaces_replaced() -> None:
    session = RaceSession(
        event_name="My Cool Event", race_number=1, race_date="2026-01-01"
    )
    assert "My_Cool_Event" in session_filename(session)


def test_session_filename_empty_event_uses_fallback() -> None:
    session = RaceSession(race_number=1, race_date="2026-01-01")
    name = session_filename(session)
    assert name.endswith("_session.json")
    assert "Race1" in name


# ---------------------------------------------------------------------------
# save / load — round-trip
# ---------------------------------------------------------------------------


def test_round_trip_minimal_session(
    minimal_session: RaceSession, tmp_path: Path
) -> None:
    path = tmp_path / "session.json"
    save(minimal_session, path)
    loaded = load(path)
    assert loaded == minimal_session


def test_round_trip_full_session(full_session: RaceSession, tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    save(full_session, path)
    loaded = load(path)
    assert loaded == full_session


def test_round_trip_green_fleet(tmp_path: Path) -> None:
    session = RaceSession(green_fleet={"AUS001", "GBR002", "USA003"})
    path = tmp_path / "session.json"
    save(session, path)
    loaded = load(path)
    assert loaded.green_fleet == {"AUS001", "GBR002", "USA003"}


def test_round_trip_lap_counting_location(tmp_path: Path) -> None:
    """lap_counting_location round-trips correctly."""
    session = RaceSession(lap_counting_location="Windward mark")
    path = tmp_path / "session.json"
    save(session, path)
    loaded = load(path)
    assert loaded.lap_counting_location == "Windward mark"


# ---------------------------------------------------------------------------
# save / load — schema presence & human-readability
# ---------------------------------------------------------------------------


def test_schema_version_present_in_json(tmp_path: Path) -> None:
    session = RaceSession()
    path = tmp_path / "session.json"
    save(session, path)
    data = json.loads(path.read_text())
    assert "schema_version" in data
    assert isinstance(data["schema_version"], int)


def test_file_is_human_readable(tmp_path: Path) -> None:
    """The saved file must be indented JSON, not a single compact line."""
    session = RaceSession(event_name="Readable Test")
    path = tmp_path / "session.json"
    save(session, path)
    content = path.read_text()
    json.loads(content)  # must be valid JSON
    assert "\n" in content  # must be multi-line (indented)


def test_save_creates_parent_directories(tmp_path: Path) -> None:
    session = RaceSession()
    path = tmp_path / "nested" / "deep" / "session.json"
    save(session, path)
    assert path.exists()


# ---------------------------------------------------------------------------
# load — graceful defaults for missing optional fields
# ---------------------------------------------------------------------------


def test_missing_finish_line_config_defaults_to_finish_at_gate(tmp_path: Path) -> None:
    """finish_line_config absent → FINISH_AT_GATE."""
    path = tmp_path / "session.json"
    path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    session = load(path)
    assert session.finish_line_config == FinishLineConfig.FINISH_AT_GATE


def test_missing_finish_window_marker_position_defaults_to_none(tmp_path: Path) -> None:
    """finish_window_marker_position absent → None."""
    path = tmp_path / "session.json"
    path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    session = load(path)
    assert session.finish_window_marker_position is None


def test_missing_lap_counting_location_deserializes_gracefully(tmp_path: Path) -> None:
    """lap_counting_location absent → default string."""
    path = tmp_path / "session.json"
    path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    session = load(path)
    assert session.lap_counting_location == "Leeward gate (mark 2p)"


def test_missing_competitors_deserializes_to_empty_list(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    session = load(path)
    assert session.competitors == []


def test_missing_green_fleet_deserializes_to_empty_set(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    session = load(path)
    assert session.green_fleet == set()


# ---------------------------------------------------------------------------
# AutoSaveSession
# ---------------------------------------------------------------------------


def test_auto_save_on_add_gate_rounding(tmp_path: Path) -> None:
    path = tmp_path / "auto.json"
    auto = AutoSaveSession(RaceSession(), path)
    auto.add_gate_rounding(GateRounding(position=1, sail_number="AUS1"))
    assert path.exists()
    loaded = load(path)
    assert len(loaded.gate_roundings) == 1
    assert loaded.gate_roundings[0].sail_number == "AUS1"


def test_auto_save_on_add_finish_entry(tmp_path: Path) -> None:
    path = tmp_path / "auto.json"
    auto = AutoSaveSession(RaceSession(), path)
    auto.add_finish_entry(FinishEntry(position=1, sail_number="AUS1"))
    loaded = load(path)
    assert len(loaded.finish_entries) == 1
    assert loaded.finish_entries[0].sail_number == "AUS1"


def test_auto_save_on_set_finish_window_marker(tmp_path: Path) -> None:
    path = tmp_path / "auto.json"
    auto = AutoSaveSession(RaceSession(), path)
    auto.set_finish_window_marker(5)
    loaded = load(path)
    assert loaded.finish_window_marker_position == 5


def test_auto_save_on_set_finish_window_marker_none(tmp_path: Path) -> None:
    path = tmp_path / "auto.json"
    auto = AutoSaveSession(RaceSession(finish_window_marker_position=3), path)
    auto.set_finish_window_marker(None)
    loaded = load(path)
    assert loaded.finish_window_marker_position is None


def test_auto_save_on_green_fleet_add(tmp_path: Path) -> None:
    path = tmp_path / "auto.json"
    auto = AutoSaveSession(RaceSession(), path)
    auto.add_to_green_fleet("GRN001")
    loaded = load(path)
    assert "GRN001" in loaded.green_fleet


def test_auto_save_on_green_fleet_remove(tmp_path: Path) -> None:
    path = tmp_path / "auto.json"
    auto = AutoSaveSession(RaceSession(green_fleet={"GRN001"}), path)
    auto.remove_from_green_fleet("GRN001")
    loaded = load(path)
    assert "GRN001" not in loaded.green_fleet


def test_auto_save_remove_nonexistent_green_fleet_is_noop(tmp_path: Path) -> None:
    """Removing a sail number not in green fleet must not raise."""
    path = tmp_path / "auto.json"
    auto = AutoSaveSession(RaceSession(), path)
    auto.remove_from_green_fleet("NOTHERE")  # must not raise
    loaded = load(path)
    assert "NOTHERE" not in loaded.green_fleet


def test_auto_save_callback_invoked(tmp_path: Path) -> None:
    called_with: list[Path] = []
    path = tmp_path / "auto.json"
    auto = AutoSaveSession(RaceSession(), path, on_save=called_with.append)
    auto.add_gate_rounding(GateRounding(position=1, sail_number="AUS1"))
    assert called_with == [path]


def test_auto_save_session_property_returns_session(tmp_path: Path) -> None:
    session = RaceSession(event_name="Prop Test")
    auto = AutoSaveSession(session, tmp_path / "s.json")
    assert auto.session is session

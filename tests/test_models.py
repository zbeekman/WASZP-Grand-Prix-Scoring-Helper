"""Smoke tests for waszp_gp_scorer.models."""

from waszp_gp_scorer.models import (
    Competitor,
    FinishEntry,
    FinishLineConfig,
    FinishType,
    GateRounding,
    RaceSession,
    ScoredResult,
)


def test_import_all_public_names() -> None:
    """All public model names can be imported from waszp_gp_scorer.models."""
    # If the import block above succeeded, this trivially passes.
    assert Competitor is not None
    assert GateRounding is not None
    assert FinishEntry is not None
    assert ScoredResult is not None
    assert FinishLineConfig is not None
    assert RaceSession is not None
    assert FinishType is not None


def test_finish_line_config_values() -> None:
    """FinishLineConfig has the two required enum values."""
    assert FinishLineConfig.FINISH_AT_GATE is not None
    assert FinishLineConfig.SEPARATE_PIN is not None


def test_competitor_construction() -> None:
    """Competitor can be constructed with required fields."""
    c = Competitor(
        sail_number="AUS1234",
        country_code="AUS",
        name="Jane Doe",
        rig_size="8.2",
        division="Open",
    )
    assert c.sail_number == "AUS1234"
    assert c.phone is None
    assert c.email is None


def test_gate_rounding_construction() -> None:
    """GateRounding stores position and sail number."""
    gr = GateRounding(position=1, sail_number="AUS1234")
    assert gr.position == 1
    assert gr.sail_number == "AUS1234"


def test_finish_entry_construction() -> None:
    """FinishEntry stores position, sail number, and optional letter score."""
    fe = FinishEntry(position=3, sail_number="NZL99")
    assert fe.position == 3
    assert fe.letter_score is None

    fe_dns = FinishEntry(position=99, sail_number="GBR7", letter_score="DNS")
    assert fe_dns.letter_score == "DNS"


def test_scored_result_construction() -> None:
    """ScoredResult links a competitor with scoring output."""
    c = Competitor("USA42", "USA", "Bob Smith", "7.5", "Youth")
    sr = ScoredResult(
        place=2,
        competitor=c,
        laps=2,
        finish_type=FinishType.STANDARD,
    )
    assert sr.place == 2
    assert sr.laps == 2
    assert sr.annotation is None


def test_race_session_defaults() -> None:
    """RaceSession has correct defaults for all fields."""
    session = RaceSession()
    assert session.schema_version == 1
    assert session.num_laps == 2
    assert session.finish_line_config == FinishLineConfig.FINISH_AT_GATE
    assert session.finish_window_marker_position is None
    assert session.competitors == []
    assert session.green_fleet == set()
    assert session.gate_roundings == []
    assert session.finish_entries == []


def test_race_session_contains_required_fields() -> None:
    """RaceSession has all fields required by issue #2 acceptance criteria."""
    session = RaceSession(
        event_name="WASZP Pre-Games 2026",
        race_number=1,
        race_date="2026-03-22",
        num_laps=3,
        course_type="SailGP (Gate)",
        finish_line_config=FinishLineConfig.SEPARATE_PIN,
        finish_window_marker_position=5,
        lap_counting_location="Windward gate",
        schema_version=1,
    )
    assert session.event_name == "WASZP Pre-Games 2026"
    assert session.finish_line_config == FinishLineConfig.SEPARATE_PIN
    assert session.finish_window_marker_position == 5
    assert session.lap_counting_location == "Windward gate"

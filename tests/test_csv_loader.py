"""Tests for waszp_gp_scorer.csv_loader."""

from __future__ import annotations

import textwrap
import warnings
from pathlib import Path

import pytest

from waszp_gp_scorer.csv_loader import (
    KNOWN_RIG_SIZES,
    LoadSummary,
    UnknownRigSizeWarning,
    load_competitors,
)
from waszp_gp_scorer.models import Competitor

FIXTURES = Path(__file__).parent / "fixtures"
VALID_FLEET_CSV = FIXTURES / "valid_fleet.csv"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def write_csv(tmp_path: Path, content: str, filename: str = "test.csv") -> Path:
    """Write *content* to a temp CSV file and return its path."""
    p = tmp_path / filename
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Loading a well-formed CSV
# ---------------------------------------------------------------------------


def test_load_returns_correct_count() -> None:
    """Loading valid_fleet.csv produces 15 Competitor objects."""
    competitors, summary = load_competitors(VALID_FLEET_CSV)
    assert len(competitors) == 15
    assert summary.total_competitors == 15


def test_load_produces_competitor_objects() -> None:
    """All items in the returned list are Competitor instances."""
    competitors, _ = load_competitors(VALID_FLEET_CSV)
    for c in competitors:
        assert isinstance(c, Competitor)


def test_load_required_fields_populated() -> None:
    """Required fields are correctly populated for the first boat."""
    competitors, _ = load_competitors(VALID_FLEET_CSV)
    first = competitors[0]
    assert first.sail_number == "4017"
    assert first.country_code == "USA"
    assert first.name == "Alex Johnson"
    assert first.rig_size == "8.2"
    assert first.division == "Open"


def test_load_optional_fields_present() -> None:
    """Optional phone and email are populated when the CSV columns exist."""
    competitors, _ = load_competitors(VALID_FLEET_CSV)
    first = competitors[0]
    assert first.phone == "+15551234567"
    assert first.email == "alex.johnson@example.com"


def test_load_optional_phone_absent_for_some_boats() -> None:
    """Boats without a phone entry have phone=None."""
    competitors, _ = load_competitors(VALID_FLEET_CSV)
    # Charlie Martin (index 6) has an empty Mobile Number cell.
    charlie = competitors[6]
    assert charlie.name == "Charlie Martin"
    assert charlie.phone is None


def test_load_optional_email_absent_for_some_boats() -> None:
    """Boats without an email entry have email=None."""
    competitors, _ = load_competitors(VALID_FLEET_CSV)
    # Unknown Sailor (index 14) has an empty Sailor Email cell.
    unknown = competitors[14]
    assert unknown.name == "Unknown Sailor"
    assert unknown.email is None


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------


def test_summary_rig_size_counts() -> None:
    """Rig size counts match the fixture composition."""
    _, summary = load_competitors(VALID_FLEET_CSV)
    assert summary.rig_size_counts["8.2"] == 5
    assert summary.rig_size_counts["7.5"] == 4
    assert summary.rig_size_counts["6.9"] == 3
    assert summary.rig_size_counts["5.8"] == 2
    assert summary.rig_size_counts["3.9"] == 1  # unknown size


def test_summary_division_counts() -> None:
    """Division counts match the fixture composition."""
    _, summary = load_competitors(VALID_FLEET_CSV)
    assert summary.division_counts["Open"] == 6
    assert summary.division_counts["Youth (U21)"] == 4
    assert summary.division_counts["Master (40+)"] == 3
    assert summary.division_counts["Junior (U17)"] == 2


def test_summary_total_competitors() -> None:
    """total_competitors reflects the full fleet size."""
    _, summary = load_competitors(VALID_FLEET_CSV)
    assert summary.total_competitors == 15


def test_load_summary_is_load_summary_instance() -> None:
    """load_competitors returns a LoadSummary as the second element."""
    _, summary = load_competitors(VALID_FLEET_CSV)
    assert isinstance(summary, LoadSummary)


# ---------------------------------------------------------------------------
# Unknown rig size → warning
# ---------------------------------------------------------------------------


def test_unknown_rig_size_emits_warning() -> None:
    """A CSV row with an unrecognized rig size issues UnknownRigSizeWarning."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        load_competitors(VALID_FLEET_CSV)

    unknown_warnings = [
        w for w in caught if issubclass(w.category, UnknownRigSizeWarning)
    ]
    assert len(unknown_warnings) == 1
    assert "3.9" in str(unknown_warnings[0].message)


def test_known_rig_sizes_no_warning(tmp_path: Path) -> None:
    """A CSV where every boat has a known rig size produces no warnings."""
    csv_path = write_csv(
        tmp_path,
        """\
        Sail Number,Sailor Country Code,Sailor Name,Sail Size,Division
        101,USA,Sailor One,8.2,Open
        102,CAN,Sailor Two,7.5,Open
        103,AUS,Sailor Three,6.9,Open
        104,NZL,Sailor Four,5.8,Open
        """,
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        load_competitors(csv_path)

    unknown_warnings = [
        w for w in caught if issubclass(w.category, UnknownRigSizeWarning)
    ]
    assert len(unknown_warnings) == 0


def test_unknown_rig_size_warning_contains_sail_number(tmp_path: Path) -> None:
    """The UnknownRigSizeWarning message includes the offending sail number."""
    csv_path = write_csv(
        tmp_path,
        """\
        Sail Number,Sailor Country Code,Sailor Name,Sail Size,Division
        XYZ99,USA,Test Sailor,4.2,Open
        """,
    )
    with pytest.warns(UnknownRigSizeWarning, match="XYZ99"):
        load_competitors(csv_path)


# ---------------------------------------------------------------------------
# Missing optional columns — no error
# ---------------------------------------------------------------------------


def test_missing_division_column_no_error(tmp_path: Path) -> None:
    """A CSV without a Division column loads without raising an exception."""
    csv_path = write_csv(
        tmp_path,
        """\
        Sail Number,Sailor Country Code,Sailor Name,Sail Size
        201,USA,No Division Sailor,8.2
        """,
    )
    competitors, summary = load_competitors(csv_path)
    assert len(competitors) == 1
    assert competitors[0].division == ""


def test_missing_phone_column_no_error(tmp_path: Path) -> None:
    """A CSV without a Mobile Number column loads with phone=None."""
    csv_path = write_csv(
        tmp_path,
        """\
        Sail Number,Sailor Country Code,Sailor Name,Sail Size,Division
        202,CAN,No Phone Sailor,7.5,Open
        """,
    )
    competitors, _ = load_competitors(csv_path)
    assert competitors[0].phone is None


def test_missing_email_column_no_error(tmp_path: Path) -> None:
    """A CSV without a Sailor Email column loads with email=None."""
    csv_path = write_csv(
        tmp_path,
        """\
        Sail Number,Sailor Country Code,Sailor Name,Sail Size,Division
        203,AUS,No Email Sailor,6.9,Youth
        """,
    )
    competitors, _ = load_competitors(csv_path)
    assert competitors[0].email is None


def test_all_optional_columns_absent_no_error(tmp_path: Path) -> None:
    """A CSV with only the four required columns loads successfully."""
    csv_path = write_csv(
        tmp_path,
        """\
        Sail Number,Sailor Country Code,Sailor Name,Sail Size
        300,GBR,Minimal Sailor,5.8
        """,
    )
    competitors, summary = load_competitors(csv_path)
    assert len(competitors) == 1
    c = competitors[0]
    assert c.sail_number == "300"
    assert c.division == ""
    assert c.phone is None
    assert c.email is None


# ---------------------------------------------------------------------------
# Missing required columns → clear error
# ---------------------------------------------------------------------------


def test_missing_sail_number_column_raises(tmp_path: Path) -> None:
    """A CSV without 'Sail Number' raises ValueError with a descriptive message."""
    csv_path = write_csv(
        tmp_path,
        """\
        Sailor Country Code,Sailor Name,Sail Size
        USA,Missing Sail Num,8.2
        """,
    )
    with pytest.raises(ValueError, match="Sail Number"):
        load_competitors(csv_path)


def test_missing_sailor_name_column_raises(tmp_path: Path) -> None:
    """A CSV without 'Sailor Name' raises ValueError."""
    csv_path = write_csv(
        tmp_path,
        """\
        Sail Number,Sailor Country Code,Sail Size
        401,USA,7.5
        """,
    )
    with pytest.raises(ValueError, match="Sailor Name"):
        load_competitors(csv_path)


def test_missing_country_code_column_raises(tmp_path: Path) -> None:
    """A CSV without 'Sailor Country Code' raises ValueError."""
    csv_path = write_csv(
        tmp_path,
        """\
        Sail Number,Sailor Name,Sail Size
        402,Some Sailor,6.9
        """,
    )
    with pytest.raises(ValueError, match="Sailor Country Code"):
        load_competitors(csv_path)


def test_missing_sail_size_column_raises(tmp_path: Path) -> None:
    """A CSV without 'Sail Size' raises ValueError."""
    csv_path = write_csv(
        tmp_path,
        """\
        Sail Number,Sailor Country Code,Sailor Name
        403,NZL,No Rig Sailor
        """,
    )
    with pytest.raises(ValueError, match="Sail Size"):
        load_competitors(csv_path)


def test_error_message_lists_missing_column(tmp_path: Path) -> None:
    """ValueError message contains the name of the missing column."""
    csv_path = write_csv(
        tmp_path,
        """\
        Sail Number,Sailor Country Code,Sailor Name
        500,FRA,Incomplete
        """,
    )
    with pytest.raises(ValueError, match="Sail Size"):
        load_competitors(csv_path)


# ---------------------------------------------------------------------------
# Known valid rig sizes constant
# ---------------------------------------------------------------------------


def test_known_rig_sizes_constant() -> None:
    """KNOWN_RIG_SIZES contains exactly the four expected values."""
    assert KNOWN_RIG_SIZES == frozenset({"8.2", "7.5", "6.9", "5.8"})


# ---------------------------------------------------------------------------
# Ordering preserved
# ---------------------------------------------------------------------------


def test_competitor_order_preserved() -> None:
    """Competitors are returned in CSV row order."""
    competitors, _ = load_competitors(VALID_FLEET_CSV)
    sail_numbers = [c.sail_number for c in competitors]
    expected_first_three = ["4017", "2451", "3198"]
    assert sail_numbers[:3] == expected_first_three

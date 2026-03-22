"""CSV loading utilities for the WASZP GP Scorer.

Parses competitor registration CSVs into :class:`~waszp_gp_scorer.models.Competitor`
objects, detects rig sizes, and produces summary statistics.
"""

from __future__ import annotations

import csv
import warnings
from collections import Counter
from pathlib import Path
from typing import Optional

import attrs

from waszp_gp_scorer.models import Competitor

#: Rig sizes that are considered valid for WASZP boats.
KNOWN_RIG_SIZES: frozenset[str] = frozenset({"8.2", "7.5", "6.9", "5.8"})

#: Column names that must be present in the CSV header.
REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {"Sail Number", "Sailor Country Code", "Sailor Name", "Sail Size"}
)


class UnknownRigSizeWarning(UserWarning):
    """Issued when a rig size value is not in the known valid set.

    Known valid sizes are: ``8.2``, ``7.5``, ``6.9``, ``5.8``.
    The warning message includes the unrecognized value and the sail number.
    """


@attrs.define
class LoadSummary:
    """Aggregate statistics produced when loading a competitor CSV.

    Attributes:
        total_competitors: Total number of :class:`~waszp_gp_scorer.models.Competitor`
            objects parsed from the CSV.
        rig_size_counts: Mapping of rig size string to the number of competitors
            using that size (includes unknown sizes).
        division_counts: Mapping of division string to the number of competitors
            in that division.  Empty-string key collects competitors with no
            division value.
    """

    total_competitors: int
    rig_size_counts: dict[str, int]
    division_counts: dict[str, int]


def load_competitors(path: "Path | str") -> tuple[list[Competitor], LoadSummary]:
    """Parse a competitor registration CSV into Competitor objects.

    Auto-detects column names for the required fields ``Sail Number``,
    ``Sailor Country Code``, ``Sailor Name``, and ``Sail Size``.
    Optional columns ``Division``, ``Mobile Number``, and ``Sailor Email``
    are read when present; missing or empty values default gracefully.

    Issues :class:`UnknownRigSizeWarning` for each row whose ``Sail Size``
    is not in :data:`KNOWN_RIG_SIZES`.

    Args:
        path: Filesystem path to the CSV file (``str`` or :class:`pathlib.Path`).

    Returns:
        A ``(competitors, summary)`` tuple where *competitors* is an ordered
        list of :class:`~waszp_gp_scorer.models.Competitor` objects and
        *summary* contains aggregate statistics.

    Raises:
        ValueError: If any required column is absent from the CSV header.
        ValueError: If the CSV file is empty or contains no header row.
    """
    path = Path(path)

    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)

        if reader.fieldnames is None:
            raise ValueError(f"CSV file '{path}' appears to be empty or has no header.")

        # Strip surrounding whitespace from every header name for robust matching.
        fieldnames: set[str] = {f.strip() for f in reader.fieldnames if f is not None}

        missing = REQUIRED_COLUMNS - fieldnames
        if missing:
            raise ValueError(f"CSV is missing required column(s): {sorted(missing)}")

        competitors: list[Competitor] = []
        rig_size_counter: Counter[str] = Counter()
        division_counter: Counter[str] = Counter()

        for row in reader:
            # Normalise: strip whitespace from both keys and string values.
            cleaned: dict[str, str] = {
                k.strip(): (v.strip() if v is not None else "")
                for k, v in row.items()
                if k is not None
            }

            rig_size = cleaned.get("Sail Size", "")
            sail_number = cleaned.get("Sail Number", "?")

            if rig_size not in KNOWN_RIG_SIZES:
                warnings.warn(
                    f"Unknown rig size {rig_size!r} for sail number {sail_number!r}",
                    UnknownRigSizeWarning,
                    stacklevel=2,
                )

            division = cleaned.get("Division", "")

            raw_phone = cleaned.get("Mobile Number", "")
            phone: Optional[str] = raw_phone if raw_phone else None

            raw_email = cleaned.get("Sailor Email", "")
            email: Optional[str] = raw_email if raw_email else None

            competitor = Competitor(
                sail_number=sail_number,
                country_code=cleaned.get("Sailor Country Code", ""),
                name=cleaned.get("Sailor Name", ""),
                rig_size=rig_size,
                division=division,
                phone=phone,
                email=email,
            )
            competitors.append(competitor)
            rig_size_counter[rig_size] += 1
            division_counter[division] += 1

    summary = LoadSummary(
        total_competitors=len(competitors),
        rig_size_counts=dict(rig_size_counter),
        division_counts=dict(division_counter),
    )
    return competitors, summary

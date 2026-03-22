"""Session persistence: JSON save and load for RaceSession.

Provides ``save()`` and ``load()`` functions for round-trip serialization
of :class:`~waszp_gp_scorer.models.RaceSession` objects, an
:class:`AutoSaveSession` wrapper that triggers ``save()`` on every mutation,
and the session file naming convention.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional

from waszp_gp_scorer.models import (
    Competitor,
    FinishEntry,
    FinishLineConfig,
    GateRounding,
    RaceSession,
)

# Sentinel to distinguish "not provided" from None for optional fields.
_UNSET: object = object()

SCHEMA_VERSION: int = 1
_DEFAULT_LAP_COUNTING_LOCATION = "Leeward gate (mark 2p)"


def session_filename(session: RaceSession) -> str:
    """Return the canonical filename for a session file.

    Format: ``{EventName}_Race{N}_{Date}_session.json``

    Spaces in the event name are replaced with underscores. Falls back to
    ``"Session"`` when ``event_name`` is empty.

    Args:
        session: The race session to name.

    Returns:
        A filename string suitable for use on all major platforms.
    """
    safe_name = (
        session.event_name.replace(" ", "_") if session.event_name else "Session"
    )
    return f"{safe_name}_Race{session.race_number}_{session.race_date}_session.json"


def _serialize(session: RaceSession) -> dict[str, Any]:
    """Convert a :class:`RaceSession` to a JSON-serializable dict.

    Args:
        session: The session to serialize.

    Returns:
        A dict suitable for passing to :func:`json.dumps`.
    """
    return {
        "schema_version": session.schema_version,
        "event_name": session.event_name,
        "race_number": session.race_number,
        "race_date": session.race_date,
        "start_time": session.start_time,
        "num_laps": session.num_laps,
        "course_type": session.course_type,
        "finish_line_config": session.finish_line_config.value,
        "finish_window_marker_position": session.finish_window_marker_position,
        "lap_counting_location": session.lap_counting_location,
        "competitors": [
            {
                "sail_number": c.sail_number,
                "country_code": c.country_code,
                "name": c.name,
                "rig_size": c.rig_size,
                "division": c.division,
                "phone": c.phone,
                "email": c.email,
            }
            for c in session.competitors
        ],
        "green_fleet": sorted(session.green_fleet),
        "gate_roundings": [
            {"position": g.position, "sail_number": g.sail_number}
            for g in session.gate_roundings
        ],
        "finish_entries": [
            {
                "position": f.position,
                "sail_number": f.sail_number,
                "letter_score": f.letter_score,
            }
            for f in session.finish_entries
        ],
    }


def _deserialize(data: dict[str, Any]) -> RaceSession:
    """Convert a raw JSON dict back to a :class:`RaceSession`.

    Missing optional fields are filled with sensible defaults so that
    older session files continue to load after schema additions.

    Args:
        data: Dict parsed from session JSON.

    Returns:
        A fully-populated :class:`RaceSession`.
    """
    competitors = [
        Competitor(
            sail_number=c["sail_number"],
            country_code=c["country_code"],
            name=c["name"],
            rig_size=c["rig_size"],
            division=c["division"],
            phone=c.get("phone"),
            email=c.get("email"),
        )
        for c in data.get("competitors", [])
    ]
    green_fleet: set[str] = set(data.get("green_fleet", []))
    gate_roundings = [
        GateRounding(position=g["position"], sail_number=g["sail_number"])
        for g in data.get("gate_roundings", [])
    ]
    finish_entries = [
        FinishEntry(
            position=f["position"],
            sail_number=f["sail_number"],
            letter_score=f.get("letter_score"),
        )
        for f in data.get("finish_entries", [])
    ]

    finish_line_config_raw = data.get("finish_line_config")
    finish_line_config = (
        FinishLineConfig(finish_line_config_raw)
        if finish_line_config_raw is not None
        else FinishLineConfig.FINISH_AT_GATE
    )

    return RaceSession(
        schema_version=data.get("schema_version", SCHEMA_VERSION),
        event_name=data.get("event_name", ""),
        race_number=data.get("race_number", 1),
        race_date=data.get("race_date", ""),
        start_time=data.get("start_time"),
        num_laps=data.get("num_laps", 2),
        course_type=data.get("course_type", "Standard WASZP W/L (Gate)"),
        finish_line_config=finish_line_config,
        finish_window_marker_position=data.get("finish_window_marker_position"),
        lap_counting_location=data.get(
            "lap_counting_location", _DEFAULT_LAP_COUNTING_LOCATION
        ),
        competitors=competitors,
        green_fleet=green_fleet,
        gate_roundings=gate_roundings,
        finish_entries=finish_entries,
    )


def save(session: RaceSession, path: Path) -> None:
    """Serialize ``session`` to JSON at ``path``.

    The file is written with 2-space indentation for human readability.
    Parent directories are created automatically if they do not exist.

    Args:
        session: The race session to persist.
        path: Destination file path (will be created or overwritten).
    """
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = _serialize(session)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load(path: Path) -> RaceSession:
    """Deserialize a JSON session file into a :class:`RaceSession`.

    Missing optional fields are filled with defaults so that older session
    files remain loadable after schema additions.

    Args:
        path: Path to the ``.json`` session file.

    Returns:
        A :class:`RaceSession` populated from the file.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    data: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    return _deserialize(data)


class AutoSaveSession:
    """Wraps a :class:`RaceSession` and triggers :func:`save` on every mutation.

    All mutating operations must go through this wrapper so that the session
    file is kept in sync with in-memory state.

    Args:
        session: The race session to wrap.
        path: Destination file path for auto-saves.
        on_save: Optional callback invoked with the path after each save.

    Example::

        auto = AutoSaveSession(session, path=Path("session.json"))
        auto.add_gate_rounding(GateRounding(position=1, sail_number="AUS1"))
        # session.json is updated automatically
    """

    def __init__(
        self,
        session: RaceSession,
        path: Path,
        on_save: Optional[Callable[[Path], None]] = None,
    ) -> None:
        self._session = session
        self._path = Path(path)
        self._on_save = on_save

    @property
    def session(self) -> RaceSession:
        """The underlying :class:`RaceSession`."""
        return self._session

    def _trigger_save(self) -> None:
        """Write the session to disk and invoke the callback if set."""
        save(self._session, self._path)
        if self._on_save is not None:
            self._on_save(self._path)

    def add_gate_rounding(self, rounding: GateRounding) -> None:
        """Append a gate rounding entry and auto-save.

        Args:
            rounding: The :class:`GateRounding` to append.
        """
        self._session.gate_roundings.append(rounding)
        self._trigger_save()

    def add_finish_entry(self, entry: FinishEntry) -> None:
        """Append a finish entry and auto-save.

        Args:
            entry: The :class:`FinishEntry` to append.
        """
        self._session.finish_entries.append(entry)
        self._trigger_save()

    def set_finish_window_marker(self, position: Optional[int]) -> None:
        """Update the finish-window marker position and auto-save.

        Args:
            position: 0-based index into ``gate_roundings``, or ``None`` to
                clear the marker.
        """
        self._session.finish_window_marker_position = position
        self._trigger_save()

    def add_to_green_fleet(self, sail_number: str) -> None:
        """Add a sail number to the green fleet and auto-save.

        Args:
            sail_number: The sail number to mark as green fleet.
        """
        self._session.green_fleet.add(sail_number)
        self._trigger_save()

    def remove_from_green_fleet(self, sail_number: str) -> None:
        """Remove a sail number from the green fleet and auto-save.

        Does nothing if ``sail_number`` is not in the green fleet.

        Args:
            sail_number: The sail number to remove.
        """
        self._session.green_fleet.discard(sail_number)
        self._trigger_save()

    def set_competitors(self, competitors: list[Competitor]) -> None:
        """Replace the competitor list and auto-save.

        Args:
            competitors: New list of competitors (replaces any existing list).
        """
        self._session.competitors = competitors
        self._trigger_save()

    def remove_gate_rounding(self, index: int) -> None:
        """Remove gate rounding at 0-based *index*, renumber, and auto-save.

        Adjusts ``finish_window_marker_position`` when the deleted entry is
        within the pre-window zone.

        Args:
            index: 0-based index of the rounding to remove. No-op if out of range.
        """
        roundings = self._session.gate_roundings
        if not (0 <= index < len(roundings)):
            return
        roundings.pop(index)
        for i, r in enumerate(roundings):
            r.position = i + 1
        marker = self._session.finish_window_marker_position
        if marker is not None and index <= marker:
            self._session.finish_window_marker_position = marker - 1
        self._trigger_save()

    def insert_gate_rounding(self, index: int, sail_number: str) -> None:
        """Insert a gate rounding before 0-based *index*, renumber, and auto-save.

        Adjusts ``finish_window_marker_position`` when the insertion is within
        the pre-window zone.

        Args:
            index: 0-based index to insert before.  Clamped to valid range.
            sail_number: Sail number for the new rounding entry.
        """
        roundings = self._session.gate_roundings
        clamped = max(0, min(index, len(roundings)))
        new_rounding = GateRounding(position=clamped + 1, sail_number=sail_number)
        roundings.insert(clamped, new_rounding)
        for i, r in enumerate(roundings):
            r.position = i + 1
        marker = self._session.finish_window_marker_position
        if marker is not None and clamped <= marker:
            self._session.finish_window_marker_position = marker + 1
        self._trigger_save()

    def replace_gate_rounding_sail(self, index: int, sail_number: str) -> None:
        """Replace the sail number at 0-based *index* and auto-save.

        Args:
            index: 0-based index of the rounding to edit.  No-op if out of range.
            sail_number: The replacement sail number.
        """
        roundings = self._session.gate_roundings
        if 0 <= index < len(roundings):
            roundings[index].sail_number = sail_number
            self._trigger_save()

    def remove_finish_entry(self, index: int) -> None:
        """Remove finish entry at 0-based *index*, renumber, and auto-save.

        Args:
            index: 0-based index of the entry to remove. No-op if out of range.
        """
        entries = self._session.finish_entries
        if not (0 <= index < len(entries)):
            return
        entries.pop(index)
        for i, e in enumerate(entries):
            e.position = i + 1
        self._trigger_save()

    def insert_finish_entry(self, index: int, sail_number: str) -> None:
        """Insert a finish entry before 0-based *index*, renumber, and auto-save.

        Args:
            index: 0-based index to insert before.  Clamped to valid range.
            sail_number: Sail number for the new entry.
        """
        entries = self._session.finish_entries
        clamped = max(0, min(index, len(entries)))
        new_entry = FinishEntry(position=clamped + 1, sail_number=sail_number)
        entries.insert(clamped, new_entry)
        for i, e in enumerate(entries):
            e.position = i + 1
        self._trigger_save()

    def replace_finish_entry_sail(self, index: int, sail_number: str) -> None:
        """Replace the sail number at 0-based *index* and auto-save.

        Args:
            index: 0-based index of the entry to edit.  No-op if out of range.
            sail_number: The replacement sail number.
        """
        entries = self._session.finish_entries
        if 0 <= index < len(entries):
            entries[index].sail_number = sail_number
            self._trigger_save()

    def set_finish_entry_letter_score(
        self, index: int, letter_score: Optional[str]
    ) -> None:
        """Set or clear the letter score at 0-based *index* and auto-save.

        Args:
            index: 0-based index of the entry to update.  No-op if out of range.
            letter_score: The letter score string (e.g. ``"DNS"``), or ``None``
                to clear any existing score.
        """
        entries = self._session.finish_entries
        if 0 <= index < len(entries):
            entries[index].letter_score = letter_score
            self._trigger_save()

    def update_metadata(
        self,
        *,
        event_name: Optional[str] = None,
        race_number: Optional[int] = None,
        race_date: Optional[str] = None,
        start_time: object = _UNSET,
        num_laps: Optional[int] = None,
        course_type: Optional[str] = None,
        finish_line_config: Optional[FinishLineConfig] = None,
        lap_counting_location: Optional[str] = None,
    ) -> None:
        """Update session metadata fields and auto-save.

        Only keyword arguments that differ from their sentinel value are
        applied, so callers may update a single field without resetting others.
        Pass ``start_time=None`` explicitly to clear the start time.

        Args:
            event_name: Human-readable event name.
            race_number: Race number within the event.
            race_date: ISO 8601 date string.
            start_time: Approximate start time string, or ``None`` to clear.
                Omit the argument entirely to leave the existing value unchanged.
            num_laps: Number of required laps.
            course_type: Course type string.
            finish_line_config: Finishing line configuration.
            lap_counting_location: Lap counting location description.
        """
        if event_name is not None:
            self._session.event_name = event_name
        if race_number is not None:
            self._session.race_number = race_number
        if race_date is not None:
            self._session.race_date = race_date
        if start_time is not _UNSET:
            self._session.start_time = (
                start_time if isinstance(start_time, str) else None
            )
        if num_laps is not None:
            self._session.num_laps = num_laps
        if course_type is not None:
            self._session.course_type = course_type
        if finish_line_config is not None:
            self._session.finish_line_config = finish_line_config
        if lap_counting_location is not None:
            self._session.lap_counting_location = lap_counting_location
        self._trigger_save()

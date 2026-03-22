"""GP scoring engine for WASZP Grand Prix races.

Single public entry point: :func:`score`.

Supported configurations in this module:

- :attr:`~waszp_gp_scorer.models.FinishLineConfig.FINISH_AT_GATE`: The
  finishing line is at mark 2p; a gate rounding and a finish crossing are the
  same physical event.  Lap formula:
  ``laps = gate_roundings + (1 if on_finish else 0)``.
  Gate roundings are capped at ``required_laps − 1``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from waszp_gp_scorer.models import (
    Competitor,
    FinishEntry,
    FinishLineConfig,
    FinishType,
    RaceSession,
    ScoredResult,
)

# ---------------------------------------------------------------------------
# Warning types emitted by the scorer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExcessRoundingsWarning:
    """Boat appeared on the gate list more times than the allowed cap.

    Attributes:
        sail_number: The sail number of the boat.
        raw_count: The total number of gate roundings recorded.
        cap: The maximum number of gate roundings allowed (``required_laps − 1``
            for ``FINISH_AT_GATE``).
    """

    sail_number: str
    raw_count: int
    cap: int


@dataclass(frozen=True)
class NoRecordedFinishWarning:
    """Gate boat reached the maximum allowed gate roundings but has no finish entry.

    Attributes:
        sail_number: The sail number of the boat.
        gate_count: The (capped) number of gate roundings recorded.
    """

    sail_number: str
    gate_count: int


@dataclass(frozen=True)
class FinishOnlyWarning:
    """Boat appears on the finish list but not on the gate list; assumed 1 lap.

    Attributes:
        sail_number: The sail number of the boat.
    """

    sail_number: str


@dataclass(frozen=True)
class LeadBoatViolationWarning:
    """First boat in a fleet group on the finish list has fewer than required laps.

    The "lead boat" rule (SI 13.2.1) requires that the first boat to finish in
    each fleet group has completed the required number of laps.

    Attributes:
        sail_number: The sail number of the offending boat.
        fleet_group: Fleet group label: ``"8.2"`` or ``"non-8.2"``.
        laps: The number of laps the boat actually completed.
        required_laps: The number of laps required to complete the race.
    """

    sail_number: str
    fleet_group: str
    laps: int
    required_laps: int


@dataclass(frozen=True)
class MissingFinishWindowMarkerWarning:
    """``SEPARATE_PIN`` race scored without a Finishing Window Opened marker.

    When no marker has been placed (``finish_window_marker_position`` is
    ``None``) all gate roundings are treated as pre-window roundings and
    scoring proceeds normally.
    """


#: Union type alias for all warning types returned by :func:`score`.
ScorerWarning = Union[
    ExcessRoundingsWarning,
    NoRecordedFinishWarning,
    FinishOnlyWarning,
    LeadBoatViolationWarning,
    MissingFinishWindowMarkerWarning,
]

# Letter scores that trigger Gate reclassification when boat is also on gate list
_DNS_DNC_DNF: frozenset[str] = frozenset({"DNS", "DNC", "DNF"})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score(
    session: RaceSession,
) -> tuple[list[ScoredResult], list[ScorerWarning]]:
    """Score a race session and return the GP Finish Ranking with warnings.

    Args:
        session: The race session containing the competitor list, gate
            roundings, and finish entries.

    Returns:
        A two-tuple ``(results, warnings)`` where:

        - *results* is a list of :class:`~waszp_gp_scorer.models.ScoredResult`
          objects in GP Finish Ranking order (place 1 first).
        - *warnings* is a list of typed warning objects describing anomalies
          detected during scoring.

    Raises:
        NotImplementedError: If the session uses a finish-line configuration
            not yet supported by this module.
    """
    if session.finish_line_config == FinishLineConfig.FINISH_AT_GATE:
        return _score_finish_at_gate(session)
    if session.finish_line_config == FinishLineConfig.SEPARATE_PIN:
        return _score_separate_pin(session)
    raise NotImplementedError(
        f"Scoring for finish_line_config={session.finish_line_config!r} "
        "is not yet implemented."
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


@dataclass
class _BoatScore:
    """Intermediate per-boat scoring data before final place assignment."""

    sail_number: str
    competitor: Competitor
    laps: int
    finish_type: FinishType
    annotation: Optional[str]
    letter_score: Optional[str]
    #: Position in the finish list; ``None`` for gate-only boats.
    finish_pos: Optional[int]
    #: Per-lap sequence position of the last gate rounding; ``None`` if no
    #: gate roundings exist (e.g. Finish Only boats).
    last_lap_seq_pos: Optional[int]
    #: ``True`` if this Gate boat's last counted rounding was during the
    #: finishing window (``SEPARATE_PIN`` only; always ``False`` otherwise).
    is_window_phase: bool = False


def _make_placeholder_competitor(sail_number: str) -> Competitor:
    """Create a minimal :class:`~waszp_gp_scorer.models.Competitor` for an
    unregistered boat encountered on the gate or finish list."""
    return Competitor(
        sail_number=sail_number,
        country_code="UNK",
        name=f"Unknown ({sail_number})",
        rig_size="Unknown",
        division="Unknown",
    )


def _score_finish_at_gate(
    session: RaceSession,
) -> tuple[list[ScoredResult], list[ScorerWarning]]:
    """Implement the ``FINISH_AT_GATE`` scoring algorithm.

    Lap formula: ``laps = gate_roundings + (1 if on_finish else 0)``.
    Gate roundings capped at ``required_laps − 1``.
    """
    required_laps: int = session.num_laps
    gate_cap: int = required_laps - 1

    warnings: list[ScorerWarning] = []

    # ------------------------------------------------------------------
    # Step 1: Count raw gate roundings and apply cap
    # ------------------------------------------------------------------
    raw_gate_counts: dict[str, int] = {}
    for rounding in session.gate_roundings:
        sn = rounding.sail_number
        raw_gate_counts[sn] = raw_gate_counts.get(sn, 0) + 1

    gate_counts: dict[str, int] = {}
    for sn, count in raw_gate_counts.items():
        if count > gate_cap:
            warnings.append(
                ExcessRoundingsWarning(sail_number=sn, raw_count=count, cap=gate_cap)
            )
            gate_counts[sn] = gate_cap
        else:
            gate_counts[sn] = count

    # ------------------------------------------------------------------
    # Step 2: Build per-lap sequence positions (respecting cap)
    #
    # per_lap_seq_pos[sail][lap] = 1-based rank of that boat among all
    # boats completing *lap* at the gate, ordered by appearance in the
    # raw gate list.
    # ------------------------------------------------------------------
    boat_running_count: dict[str, int] = {}
    lap_completion_order: dict[int, list[str]] = {}

    for rounding in session.gate_roundings:
        sn = rounding.sail_number
        boat_running_count[sn] = boat_running_count.get(sn, 0) + 1
        lap_num = boat_running_count[sn]
        if lap_num > gate_cap:
            continue  # excess rounding — ignore for sequence tracking
        lap_completion_order.setdefault(lap_num, []).append(sn)

    per_lap_seq_pos: dict[str, dict[int, int]] = {}
    for lap, boats in lap_completion_order.items():
        for i, sn in enumerate(boats):
            per_lap_seq_pos.setdefault(sn, {})[lap] = i + 1  # 1-based

    # ------------------------------------------------------------------
    # Step 3: Build lookups
    # ------------------------------------------------------------------
    competitor_map: dict[str, Competitor] = {
        c.sail_number: c for c in session.competitors
    }

    # Last entry wins if a sail number appears multiple times on finish list.
    finish_entries_by_sail: dict[str, FinishEntry] = {}
    for finish_e in session.finish_entries:
        finish_entries_by_sail[finish_e.sail_number] = finish_e

    # finish_pos_map: finish list position for non-letter-score entries only.
    finish_pos_map: dict[str, int] = {}
    for finish_e in session.finish_entries:
        if finish_e.letter_score is None:
            finish_pos_map[finish_e.sail_number] = finish_e.position

    # ------------------------------------------------------------------
    # Step 4: Universe of boats (gate ∪ finish, minus green fleet)
    # ------------------------------------------------------------------
    universe: set[str] = (
        set(gate_counts.keys()) | set(finish_entries_by_sail.keys())
    ) - session.green_fleet

    # ------------------------------------------------------------------
    # Step 5: Classify each boat
    # ------------------------------------------------------------------
    boat_scores: list[_BoatScore] = []

    for sn in sorted(universe):  # sorted for deterministic output
        gc: int = gate_counts.get(sn, 0)
        fe: Optional[FinishEntry] = finish_entries_by_sail.get(sn)
        on_finish: bool = fe is not None
        letter_score: Optional[str] = fe.letter_score if fe else None

        comp: Competitor = competitor_map.get(sn) or _make_placeholder_competitor(sn)

        finish_type: FinishType
        laps: int
        annotation: Optional[str] = None

        if letter_score is not None:
            if letter_score in _DNS_DNC_DNF and gc >= 1:
                # DNS/DNC/DNF override: reclassify as Gate per SI 13.2.3(i)
                finish_type = FinishType.GATE
                laps = gc
                annotation = (
                    "SI 13.2.3(i): letter score overridden — boat appeared on "
                    "the gate list and is classified as a Gate finish"
                )
                # letter_score cleared in result; the annotation carries the info
                letter_score = None
            else:
                finish_type = FinishType.LETTER_SCORE
                laps = 0
        elif gc == gate_cap and on_finish:
            # Standard: completed all required gate roundings and finished
            finish_type = FinishType.STANDARD
            laps = required_laps
        elif gc == gate_cap and not on_finish:
            # Gate boat completed max allowed roundings but has no finish entry
            finish_type = FinishType.GATE
            laps = gc
            warnings.append(NoRecordedFinishWarning(sail_number=sn, gate_count=gc))
        elif on_finish and gc == 0:
            # Finish Only: crossed the line but never recorded at gate
            finish_type = FinishType.FINISH_ONLY
            laps = 1
            warnings.append(FinishOnlyWarning(sail_number=sn))
        elif on_finish and 0 < gc < gate_cap:
            # GP: crossed the line with fewer than max gate roundings
            finish_type = FinishType.GP
            laps = gc + 1
        elif gc >= 1 and not on_finish:
            # Gate: completed some gate roundings but missed the finish window
            finish_type = FinishType.GATE
            laps = gc
        else:
            # No activity and no letter score — not in the race
            continue

        # Per-lap sequence position of the last gate rounding (used to sort
        # Gate boats within a short-lap tier).
        last_lap_seq: Optional[int] = (
            per_lap_seq_pos.get(sn, {}).get(gc) if gc > 0 else None
        )

        boat_scores.append(
            _BoatScore(
                sail_number=sn,
                competitor=comp,
                laps=laps,
                finish_type=finish_type,
                annotation=annotation,
                letter_score=letter_score,
                finish_pos=finish_pos_map.get(sn),
                last_lap_seq_pos=last_lap_seq,
            )
        )

    # ------------------------------------------------------------------
    # Step 6: Build the GP Finish Ranking
    #
    # Full-lap tier (laps == required_laps): Standard boats in finish order.
    # Short-lap tiers (laps < required_laps, most laps first):
    #   Gate boats first (per-lap sequence order of last rounding), then
    #   line-crossers (GP, Finish Only) in finish list order.
    # Letter-score boats appended at bottom (place = total_non_letter + 1).
    # ------------------------------------------------------------------
    full_lap_boats: list[_BoatScore] = []
    # short_lap_map[laps] = (gate_boats, line_crosser_boats)
    short_lap_map: dict[int, tuple[list[_BoatScore], list[_BoatScore]]] = {}
    letter_score_boats: list[_BoatScore] = []

    for bs in boat_scores:
        if bs.finish_type == FinishType.LETTER_SCORE:
            letter_score_boats.append(bs)
        elif bs.laps == required_laps:
            full_lap_boats.append(bs)
        else:
            if bs.laps not in short_lap_map:
                short_lap_map[bs.laps] = ([], [])
            gate_list, crosser_list = short_lap_map[bs.laps]
            if bs.finish_type == FinishType.GATE:
                gate_list.append(bs)
            else:
                crosser_list.append(bs)

    # Sort full-lap tier by finish list position
    full_lap_boats.sort(key=lambda b: b.finish_pos or 0)

    # Sort short-lap tiers (most laps first)
    ranked_boats: list[_BoatScore] = list(full_lap_boats)
    for laps_count in sorted(short_lap_map.keys(), reverse=True):
        gate_boats, crosser_boats = short_lap_map[laps_count]
        # Gate boats sorted by per-lap sequence position of last rounding
        gate_boats.sort(key=lambda b: b.last_lap_seq_pos or 0)
        # Line-crossers sorted by finish list position
        crosser_boats.sort(key=lambda b: b.finish_pos or 0)
        ranked_boats.extend(gate_boats)
        ranked_boats.extend(crosser_boats)

    # Assign places and build ScoredResult objects
    results: list[ScoredResult] = []
    non_letter_count = len(ranked_boats)
    letter_place = non_letter_count + 1

    for place, bs in enumerate(ranked_boats, start=1):
        results.append(
            ScoredResult(
                place=place,
                competitor=bs.competitor,
                laps=bs.laps,
                finish_type=bs.finish_type,
                annotation=bs.annotation,
                letter_score=bs.letter_score,
            )
        )

    for bs in letter_score_boats:
        results.append(
            ScoredResult(
                place=letter_place,
                competitor=bs.competitor,
                laps=bs.laps,
                finish_type=bs.finish_type,
                annotation=bs.annotation,
                letter_score=bs.letter_score,
            )
        )

    # ------------------------------------------------------------------
    # Step 7: Lead-boat violation check
    #
    # Validate independently for the 8.2 fleet and the non-8.2 fleet.
    # The first boat (by finish list position) in each fleet must have
    # completed the required number of laps.
    # ------------------------------------------------------------------
    laps_by_sail: dict[str, int] = {r.competitor.sail_number: r.laps for r in results}

    eight_two_sails: set[str] = {
        c.sail_number
        for c in session.competitors
        if c.rig_size == "8.2" and c.sail_number not in session.green_fleet
    }

    finish_entries_sorted = sorted(
        session.finish_entries, key=lambda entry: entry.position
    )

    for fleet_label in ("8.2", "non-8.2"):
        first_sn: Optional[str] = None
        for finish_entry in finish_entries_sorted:
            if finish_entry.letter_score is not None:
                continue  # skip letter-score entries
            if finish_entry.sail_number in session.green_fleet:
                continue
            # For non-8.2 check, skip boats not in the competitor list
            # (unknown rig size → cannot classify fleet).
            if (
                fleet_label == "non-8.2"
                and finish_entry.sail_number not in competitor_map
            ):
                continue
            in_fleet = (
                finish_entry.sail_number in eight_two_sails
                if fleet_label == "8.2"
                else finish_entry.sail_number not in eight_two_sails
            )
            if in_fleet:
                first_sn = finish_entry.sail_number
                break

        if first_sn is not None:
            boat_laps = laps_by_sail.get(first_sn, 0)
            if boat_laps < required_laps:
                warnings.append(
                    LeadBoatViolationWarning(
                        sail_number=first_sn,
                        fleet_group=fleet_label,
                        laps=boat_laps,
                        required_laps=required_laps,
                    )
                )

    return results, warnings


def _score_separate_pin(
    session: RaceSession,
) -> tuple[list[ScoredResult], list[ScorerWarning]]:
    """Implement the ``SEPARATE_PIN`` scoring algorithm.

    Lap formula: ``laps = gate_roundings``, capped at ``required_laps``.

    Gate roundings and finish line crossings are distinct events.  The
    finishing window marker (``finish_window_marker_position``) splits the
    gate list into pre-window and window-phase roundings, which affects
    the within-tier ranking of Gate boats:

    - Pre-window Gate boats rank **ahead** of line-crossers (GP / Finish Only)
      in the same lap-count tier.
    - Window-phase Gate boats rank **behind** line-crossers in the same tier.
    """
    required_laps: int = session.num_laps
    gate_cap: int = required_laps  # SEPARATE_PIN: cap = required_laps

    warnings: list[ScorerWarning] = []

    # ------------------------------------------------------------------
    # Step 1: Missing marker check
    # ------------------------------------------------------------------
    has_marker: bool = session.finish_window_marker_position is not None
    if not has_marker:
        warnings.append(MissingFinishWindowMarkerWarning())
    # Threshold: gate list indices >= marker_threshold are window-phase.
    # When no marker: all roundings are pre-window.
    marker_threshold: int = (
        session.finish_window_marker_position + 1  # type: ignore[operator]
        if has_marker
        else len(session.gate_roundings)
    )

    # ------------------------------------------------------------------
    # Step 2: Count raw gate roundings and apply cap
    # ------------------------------------------------------------------
    raw_gate_counts: dict[str, int] = {}
    for rounding in session.gate_roundings:
        sn = rounding.sail_number
        raw_gate_counts[sn] = raw_gate_counts.get(sn, 0) + 1

    gate_counts: dict[str, int] = {}
    for sn, count in raw_gate_counts.items():
        if count > gate_cap:
            warnings.append(
                ExcessRoundingsWarning(sail_number=sn, raw_count=count, cap=gate_cap)
            )
            gate_counts[sn] = gate_cap
        else:
            gate_counts[sn] = count

    # ------------------------------------------------------------------
    # Step 3: For each boat, find the gate-list index (0-based) of its
    # last *counted* rounding and whether that rounding is window-phase.
    # ------------------------------------------------------------------
    boat_running: dict[str, int] = {}
    boat_last_rounding_idx: dict[str, int] = {}

    for idx, rounding in enumerate(session.gate_roundings):
        sn = rounding.sail_number
        boat_running[sn] = boat_running.get(sn, 0) + 1
        if boat_running[sn] <= gate_counts.get(sn, 0):
            boat_last_rounding_idx[sn] = idx

    # ------------------------------------------------------------------
    # Step 4: Build lookups
    # ------------------------------------------------------------------
    competitor_map: dict[str, Competitor] = {
        c.sail_number: c for c in session.competitors
    }

    finish_entries_by_sail: dict[str, FinishEntry] = {}
    for finish_e in session.finish_entries:
        finish_entries_by_sail[finish_e.sail_number] = finish_e

    finish_pos_map: dict[str, int] = {}
    for finish_e in session.finish_entries:
        if finish_e.letter_score is None:
            finish_pos_map[finish_e.sail_number] = finish_e.position

    # ------------------------------------------------------------------
    # Step 5: Universe of boats (gate ∪ finish, minus green fleet)
    # ------------------------------------------------------------------
    universe: set[str] = (
        set(gate_counts.keys()) | set(finish_entries_by_sail.keys())
    ) - session.green_fleet

    # ------------------------------------------------------------------
    # Step 6: Classify each boat
    # ------------------------------------------------------------------
    boat_scores: list[_BoatScore] = []

    for sn in sorted(universe):
        gc: int = gate_counts.get(sn, 0)
        fe: Optional[FinishEntry] = finish_entries_by_sail.get(sn)
        on_finish: bool = fe is not None
        letter_score: Optional[str] = fe.letter_score if fe else None

        comp: Competitor = competitor_map.get(sn) or _make_placeholder_competitor(sn)

        finish_type: FinishType
        laps: int
        annotation: Optional[str] = None

        if letter_score is not None:
            if letter_score in _DNS_DNC_DNF and gc >= 1:
                # DNS/DNC/DNF override: reclassify as Gate per SI 13.2.3(i)
                finish_type = FinishType.GATE
                laps = gc
                annotation = (
                    "SI 13.2.3(i): letter score overridden — boat appeared on "
                    "the gate list and is classified as a Gate finish"
                )
                letter_score = None
            else:
                finish_type = FinishType.LETTER_SCORE
                laps = 0
        elif gc >= gate_cap and on_finish:
            # Standard: completed all required gate roundings and finished
            finish_type = FinishType.STANDARD
            laps = required_laps
        elif gc >= gate_cap and not on_finish:
            # Error: No Recorded Finish — reached lap quota without crossing line
            finish_type = FinishType.ERROR_NO_RECORDED_FINISH
            laps = gc
            warnings.append(NoRecordedFinishWarning(sail_number=sn, gate_count=gc))
        elif on_finish and gc == 0:
            # Finish Only: crossed the line but never recorded at gate
            finish_type = FinishType.FINISH_ONLY
            laps = 1
            warnings.append(FinishOnlyWarning(sail_number=sn))
        elif on_finish and 0 < gc < gate_cap:
            # GP: crossed the line with fewer than required gate roundings
            # SEPARATE_PIN: laps = gate_roundings (no finish-crossing bonus)
            finish_type = FinishType.GP
            laps = gc
        elif gc >= 1 and not on_finish:
            # Gate: completed some gate roundings but did not cross finish
            finish_type = FinishType.GATE
            laps = gc
        else:
            continue  # no activity

        # Determine if this Gate boat's last rounding was window-phase
        last_idx: Optional[int] = boat_last_rounding_idx.get(sn)
        is_window: bool = last_idx is not None and last_idx >= marker_threshold

        boat_scores.append(
            _BoatScore(
                sail_number=sn,
                competitor=comp,
                laps=laps,
                finish_type=finish_type,
                annotation=annotation,
                letter_score=letter_score,
                finish_pos=finish_pos_map.get(sn),
                last_lap_seq_pos=last_idx,
                is_window_phase=is_window,
            )
        )

    # ------------------------------------------------------------------
    # Step 7: Build the GP Finish Ranking
    #
    # Full-lap tier (laps == required_laps): Standard in finish order.
    # Short-lap tiers (laps < required_laps, most laps first):
    #   (a) Pre-window Gate boats first (by gate-list index of last rounding)
    #   (b) Line-crossers (GP, Finish Only) in finish list order
    #   (c) Window-phase Gate boats last (by gate-list index of last rounding)
    # Letter-score boats appended at bottom.
    # ------------------------------------------------------------------
    full_lap_boats: list[_BoatScore] = []
    # short_lap_map[laps] = (pre_window_gate, line_crossers, window_gate)
    short_lap_map: dict[
        int, tuple[list[_BoatScore], list[_BoatScore], list[_BoatScore]]
    ] = {}
    letter_score_boats: list[_BoatScore] = []

    for bs in boat_scores:
        if bs.finish_type == FinishType.LETTER_SCORE:
            letter_score_boats.append(bs)
        elif bs.laps == required_laps:
            full_lap_boats.append(bs)
        else:
            if bs.laps not in short_lap_map:
                short_lap_map[bs.laps] = ([], [], [])
            pre_gate, crossers, win_gate = short_lap_map[bs.laps]
            if bs.finish_type == FinishType.GATE:
                if bs.is_window_phase:
                    win_gate.append(bs)
                else:
                    pre_gate.append(bs)
            elif bs.finish_type == FinishType.ERROR_NO_RECORDED_FINISH:
                # NRF boats are Gate-equivalent; treat as pre-window Gate
                pre_gate.append(bs)
            else:
                crossers.append(bs)

    full_lap_boats.sort(key=lambda b: b.finish_pos or 0)

    ranked_boats: list[_BoatScore] = list(full_lap_boats)
    for laps_count in sorted(short_lap_map.keys(), reverse=True):
        pre_gate, crossers, win_gate = short_lap_map[laps_count]
        pre_gate.sort(key=lambda b: b.last_lap_seq_pos or 0)
        crossers.sort(key=lambda b: b.finish_pos or 0)
        win_gate.sort(key=lambda b: b.last_lap_seq_pos or 0)
        ranked_boats.extend(pre_gate)
        ranked_boats.extend(crossers)
        ranked_boats.extend(win_gate)

    results: list[ScoredResult] = []
    non_letter_count = len(ranked_boats)
    letter_place = non_letter_count + 1

    for place, bs in enumerate(ranked_boats, start=1):
        results.append(
            ScoredResult(
                place=place,
                competitor=bs.competitor,
                laps=bs.laps,
                finish_type=bs.finish_type,
                annotation=bs.annotation,
                letter_score=bs.letter_score,
            )
        )

    for bs in letter_score_boats:
        results.append(
            ScoredResult(
                place=letter_place,
                competitor=bs.competitor,
                laps=bs.laps,
                finish_type=bs.finish_type,
                annotation=bs.annotation,
                letter_score=bs.letter_score,
            )
        )

    # ------------------------------------------------------------------
    # Step 8: Lead-boat violation check (same logic as FINISH_AT_GATE)
    # ------------------------------------------------------------------
    laps_by_sail: dict[str, int] = {r.competitor.sail_number: r.laps for r in results}

    eight_two_sails: set[str] = {
        c.sail_number
        for c in session.competitors
        if c.rig_size == "8.2" and c.sail_number not in session.green_fleet
    }

    finish_entries_sorted = sorted(
        session.finish_entries, key=lambda entry: entry.position
    )

    for fleet_label in ("8.2", "non-8.2"):
        first_sn: Optional[str] = None
        for finish_entry in finish_entries_sorted:
            if finish_entry.letter_score is not None:
                continue
            if finish_entry.sail_number in session.green_fleet:
                continue
            if (
                fleet_label == "non-8.2"
                and finish_entry.sail_number not in competitor_map
            ):
                continue
            in_fleet = (
                finish_entry.sail_number in eight_two_sails
                if fleet_label == "8.2"
                else finish_entry.sail_number not in eight_two_sails
            )
            if in_fleet:
                first_sn = finish_entry.sail_number
                break

        if first_sn is not None:
            boat_laps = laps_by_sail.get(first_sn, 0)
            if boat_laps < required_laps:
                warnings.append(
                    LeadBoatViolationWarning(
                        sail_number=first_sn,
                        fleet_group=fleet_label,
                        laps=boat_laps,
                        required_laps=required_laps,
                    )
                )

    return results, warnings

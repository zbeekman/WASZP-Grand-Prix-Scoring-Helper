"""Tests for the GP scoring engine (scorer.py).

Covers:
- RMG Conceptual Example 2 (2-boat minimal: Gate ahead of Finish Only)
- Standard finish (all boats complete required laps)
- GP finish (mixed lap counts)
- Gate finish (inserted correctly relative to line-crossers)
- Finish Only (boat on finish list only, warning returned)
- Error: No Recorded Finish (max gate roundings, no finish → warning)
- Letter score override (DNS/DNC/DNF + gate list → Gate, annotated)
- Short-lap tier ordering (Gate boats before line-crossers)
- Multiple Gate boats (sorted by per-lap sequence position)
- Multiple line-crossers (GP and Finish Only sorted by finish position)
- Per-lap sequence position (computed from interleaved gate log)
- Lead-boat violation (detected independently per fleet group)
- Two-fleet shared course
- Two-fleet lead-boat warning fires for correct fleet only
- RMG Example 1 (3-lap, 20-boat integration test, 5 named sub-assertions)
"""

import pytest

from waszp_gp_scorer.models import (
    Competitor,
    FinishEntry,
    FinishLineConfig,
    FinishType,
    GateRounding,
    RaceSession,
    ScoredResult,
)
from waszp_gp_scorer.scorer import (
    ExcessRoundingsWarning,
    FinishOnlyWarning,
    LeadBoatViolationWarning,
    MissingFinishWindowMarkerWarning,
    NoRecordedFinishWarning,
    ScorerWarning,
    score,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _competitor(
    sail_number: str,
    rig_size: str = "8.2",
    country_code: str = "TST",
) -> Competitor:
    """Create a minimal Competitor for testing."""
    return Competitor(
        sail_number=sail_number,
        country_code=country_code,
        name=f"Sailor {sail_number}",
        rig_size=rig_size,
        division="Open",
    )


def _session(
    *,
    num_laps: int = 2,
    gate_sns: list[str],
    finish_sns: list[tuple[str, str | None]],
    competitors: list[Competitor] | None = None,
    green_fleet: set[str] | None = None,
    rig_size: str = "8.2",
) -> RaceSession:
    """Build a :class:`RaceSession` from compact inputs.

    Args:
        num_laps: Required number of laps.
        gate_sns: Sail numbers in gate recording order (flat list; repeats
            indicate multiple roundings by the same boat).
        finish_sns: Sequence of ``(sail_number, letter_score_or_None)`` tuples
            in finish position order.
        competitors: Explicit competitor list; auto-generated from all
            mentioned sail numbers if ``None``.
        green_fleet: Set of Green Fleet sail numbers to exclude.
        rig_size: Default rig size for auto-generated competitors.
    """
    gate_roundings = [
        GateRounding(position=i + 1, sail_number=sn) for i, sn in enumerate(gate_sns)
    ]
    finish_entries = [
        FinishEntry(position=i + 1, sail_number=sn, letter_score=ls)
        for i, (sn, ls) in enumerate(finish_sns)
    ]
    if competitors is None:
        all_sns = {sn for sn in gate_sns} | {sn for sn, _ in finish_sns}
        competitors = [_competitor(sn, rig_size=rig_size) for sn in sorted(all_sns)]
    return RaceSession(
        num_laps=num_laps,
        finish_line_config=FinishLineConfig.FINISH_AT_GATE,
        competitors=competitors,
        green_fleet=green_fleet or set(),
        gate_roundings=gate_roundings,
        finish_entries=finish_entries,
    )


def _session_sep_pin(
    *,
    num_laps: int = 2,
    gate_sns: list[str],
    finish_sns: list[tuple[str, str | None]],
    marker_after: int | None = None,
    competitors: list[Competitor] | None = None,
) -> RaceSession:
    """Build a SEPARATE_PIN :class:`RaceSession` from compact inputs.

    Args:
        num_laps: Required number of laps.
        gate_sns: Sail numbers in gate recording order.
        finish_sns: Sequence of ``(sail_number, letter_score_or_None)`` tuples.
        marker_after: 0-based index of the last pre-window gate rounding
            (``finish_window_marker_position``).  ``None`` = no marker placed.
        competitors: Explicit competitor list; auto-generated if ``None``.
    """
    gate_roundings = [
        GateRounding(position=i + 1, sail_number=sn) for i, sn in enumerate(gate_sns)
    ]
    finish_entries = [
        FinishEntry(position=i + 1, sail_number=sn, letter_score=ls)
        for i, (sn, ls) in enumerate(finish_sns)
    ]
    if competitors is None:
        all_sns = {sn for sn in gate_sns} | {sn for sn, _ in finish_sns}
        competitors = [_competitor(sn) for sn in sorted(all_sns)]
    return RaceSession(
        num_laps=num_laps,
        finish_line_config=FinishLineConfig.SEPARATE_PIN,
        competitors=competitors,
        green_fleet=set(),
        gate_roundings=gate_roundings,
        finish_entries=finish_entries,
        finish_window_marker_position=marker_after,
    )


def _places(results: list[ScoredResult]) -> dict[str, int]:
    """Return ``{sail_number: place}`` mapping for a results list."""
    return {r.competitor.sail_number: r.place for r in results}


def _types(results: list[ScoredResult]) -> dict[str, FinishType]:
    """Return ``{sail_number: finish_type}`` mapping for a results list."""
    return {r.competitor.sail_number: r.finish_type for r in results}


def _warning_types(warnings: list[ScorerWarning]) -> list[type]:
    """Return the list of warning class types."""
    return [type(w) for w in warnings]


# ---------------------------------------------------------------------------
# RMG Example 2: minimal 2-boat Gate vs Finish Only (RMG p.16)
# ---------------------------------------------------------------------------


class TestRMGExample2:
    """RMG Conceptual Example 2: Gate finish ahead of Finish Only.

    'Boat X features on the leeward mark list but not the finish list so did
    one lap; whilst Boat Y features on the finish list but not the leeward
    mark list; also completing one lap. Boat X is ranked ahead of Boat Y
    because Boat X completed one lap before Boat Y.'
    """

    def test_boat_x_ranked_ahead_of_boat_y(self) -> None:
        """Gate boat X must rank ahead of Finish Only boat Y."""
        session = _session(
            num_laps=2,
            gate_sns=["X"],
            finish_sns=[("Y", None)],
        )
        results, _ = score(session)
        places = _places(results)
        assert places["X"] < places["Y"], (
            f"Gate boat X (place {places['X']}) should rank ahead of "
            f"Finish Only boat Y (place {places['Y']})"
        )

    def test_x_is_gate_y_is_finish_only(self) -> None:
        """X classified as Gate, Y as Finish Only."""
        session = _session(
            num_laps=2,
            gate_sns=["X"],
            finish_sns=[("Y", None)],
        )
        results, _ = score(session)
        types = _types(results)
        assert types["X"] == FinishType.GATE
        assert types["Y"] == FinishType.FINISH_ONLY

    def test_finish_only_warning_issued(self) -> None:
        """FinishOnlyWarning must be returned for boat Y."""
        session = _session(
            num_laps=2,
            gate_sns=["X"],
            finish_sns=[("Y", None)],
        )
        _, warnings = score(session)
        fo_warnings = [w for w in warnings if isinstance(w, FinishOnlyWarning)]
        assert len(fo_warnings) == 1
        assert fo_warnings[0].sail_number == "Y"


# ---------------------------------------------------------------------------
# Standard finish
# ---------------------------------------------------------------------------


class TestStandardFinish:
    """All boats complete required laps → correct places in finish order."""

    def test_two_lap_race_all_standard(self) -> None:
        """Three boats all complete 2 laps → sorted by finish position."""
        session = _session(
            num_laps=2,
            gate_sns=["A", "B", "C"],  # 1 rounding each = gate_cap
            finish_sns=[("A", None), ("B", None), ("C", None)],
        )
        results, warnings = score(session)
        places = _places(results)
        assert places["A"] == 1
        assert places["B"] == 2
        assert places["C"] == 3

    def test_all_classified_as_standard(self) -> None:
        """All boats must have FinishType.STANDARD."""
        session = _session(
            num_laps=2,
            gate_sns=["A", "B", "C"],
            finish_sns=[("A", None), ("B", None), ("C", None)],
        )
        results, _ = score(session)
        for r in results:
            assert r.finish_type == FinishType.STANDARD

    def test_standard_laps_equal_required(self) -> None:
        """Standard boats get laps = required_laps."""
        session = _session(
            num_laps=2,
            gate_sns=["A", "B"],
            finish_sns=[("A", None), ("B", None)],
        )
        results, _ = score(session)
        for r in results:
            assert r.laps == 2

    def test_finish_order_preserved_when_all_same_laps(self) -> None:
        """Standard boats keep their finish list order (not gate order)."""
        # C finishes first (finish pos 1) but A rounded gate first
        session = _session(
            num_laps=2,
            gate_sns=["A", "B", "C"],
            finish_sns=[("C", None), ("B", None), ("A", None)],
        )
        results, _ = score(session)
        places = _places(results)
        assert places["C"] == 1
        assert places["B"] == 2
        assert places["A"] == 3


# ---------------------------------------------------------------------------
# GP finish
# ---------------------------------------------------------------------------


class TestGPFinish:
    """Mixed lap counts: more-laps boats ranked ahead."""

    def test_three_lap_boat_ahead_of_two_lap_boat(self) -> None:
        """3-lap Standard boat ranks ahead of 2-lap GP boat."""
        session = _session(
            num_laps=3,
            gate_sns=["S", "S", "G"],  # S: 2 roundings, G: 1 rounding
            finish_sns=[("G", None), ("S", None)],  # G finishes before S
        )
        results, _ = score(session)
        places = _places(results)
        assert places["S"] < places["G"], "3-lap S must rank ahead of 2-lap G"

    def test_gp_boat_laps_is_gate_count_plus_one(self) -> None:
        """GP boat laps = gate_roundings + 1."""
        session = _session(
            num_laps=3,
            gate_sns=["S", "S", "G"],
            finish_sns=[("S", None), ("G", None)],
        )
        results, _ = score(session)
        types = _types(results)
        laps = {r.competitor.sail_number: r.laps for r in results}
        assert types["G"] == FinishType.GP
        assert laps["G"] == 2  # 1 gate rounding + 1 finish

    def test_gp_boats_ordered_by_finish_position(self) -> None:
        """Multiple GP boats with same lap count → ordered by finish position."""
        session = _session(
            num_laps=3,
            gate_sns=["G1", "G2"],  # both 1 gate rounding in 3-lap race → GP
            finish_sns=[("G2", None), ("G1", None)],  # G2 finishes first
        )
        results, _ = score(session)
        places = _places(results)
        assert places["G2"] < places["G1"]


# ---------------------------------------------------------------------------
# Gate finish
# ---------------------------------------------------------------------------


class TestGateFinish:
    """Gate boat inserted correctly relative to line-crossers in same tier."""

    def test_gate_boat_ahead_of_gp_same_lap_count(self) -> None:
        """Gate boat with N laps ranks ahead of GP/Finish Only with N laps."""
        # 3-lap race: gate_cap = 2
        # Gate boat G2: 2 gate roundings, no finish → laps = 2, Gate
        # GP boat G1: 1 gate rounding + finish → laps = 2, GP
        session = _session(
            num_laps=3,
            gate_sns=["G2", "G2", "G1"],  # G2 gets 2 roundings, G1 gets 1
            finish_sns=[("G1", None)],
        )
        results, _ = score(session)
        places = _places(results)
        assert places["G2"] < places["G1"], "Gate G2 must rank ahead of GP G1"

    def test_gate_finish_type(self) -> None:
        """Boat on gate list only → FinishType.GATE."""
        session = _session(
            num_laps=2,
            gate_sns=["G"],
            finish_sns=[],
        )
        results, _ = score(session)
        types = _types(results)
        assert types["G"] == FinishType.GATE

    def test_gate_laps_equals_gate_count(self) -> None:
        """Gate boat laps = gate_roundings (no finish bonus)."""
        session = _session(
            num_laps=3,
            gate_sns=["G", "G"],  # 2 gate roundings
            finish_sns=[],
        )
        results, _ = score(session)
        laps = {r.competitor.sail_number: r.laps for r in results}
        assert laps["G"] == 2


# ---------------------------------------------------------------------------
# Finish Only
# ---------------------------------------------------------------------------


class TestFinishOnly:
    """Boat on finish list only → assumed 1 lap, warning returned."""

    def test_finish_only_type(self) -> None:
        """Boat on finish list, not gate list → FinishType.FINISH_ONLY."""
        session = _session(
            num_laps=2,
            gate_sns=[],
            finish_sns=[("F", None)],
        )
        results, _ = score(session)
        types = _types(results)
        assert types["F"] == FinishType.FINISH_ONLY

    def test_finish_only_laps_is_one(self) -> None:
        """Finish Only boat assumed to have 1 lap."""
        session = _session(
            num_laps=2,
            gate_sns=[],
            finish_sns=[("F", None)],
        )
        results, _ = score(session)
        laps = {r.competitor.sail_number: r.laps for r in results}
        assert laps["F"] == 1

    def test_finish_only_warning_returned(self) -> None:
        """FinishOnlyWarning is returned for boat on finish list only."""
        session = _session(
            num_laps=2,
            gate_sns=[],
            finish_sns=[("F", None)],
        )
        _, warnings = score(session)
        fo = [w for w in warnings if isinstance(w, FinishOnlyWarning)]
        assert len(fo) == 1
        assert fo[0].sail_number == "F"

    def test_finish_only_ranked_last_among_same_lap_tier(self) -> None:
        """Finish Only boat ranks after Gate boat in same 1-lap tier."""
        session = _session(
            num_laps=2,
            gate_sns=["G"],
            finish_sns=[("F", None)],
        )
        results, _ = score(session)
        places = _places(results)
        assert places["G"] < places["F"]


# ---------------------------------------------------------------------------
# Error: No Recorded Finish (gate_cap roundings, no finish)
# ---------------------------------------------------------------------------


class TestNoRecordedFinish:
    """Gate boat with max gate roundings but no finish entry → warning."""

    def test_nrf_warning_issued(self) -> None:
        """NoRecordedFinishWarning for boat with gate_cap roundings, no finish."""
        # 2-lap race: gate_cap = 1. Boat A: 1 gate rounding, no finish.
        session = _session(
            num_laps=2,
            gate_sns=["A"],
            finish_sns=[],
        )
        _, warnings = score(session)
        nrf = [w for w in warnings if isinstance(w, NoRecordedFinishWarning)]
        assert len(nrf) == 1
        assert nrf[0].sail_number == "A"
        assert nrf[0].gate_count == 1  # = gate_cap

    def test_nrf_classified_as_gate(self) -> None:
        """NoRecordedFinish boat is classified as FinishType.GATE."""
        session = _session(
            num_laps=2,
            gate_sns=["A"],
            finish_sns=[],
        )
        results, _ = score(session)
        types = _types(results)
        assert types["A"] == FinishType.GATE

    def test_nrf_placed_before_line_crossers_in_short_lap_tier(self) -> None:
        """NRF boat (Gate) is placed first in its short-lap tier."""
        # 3-lap race: gate_cap = 2
        # A: 2 gate roundings, no finish → Gate (NRF warning), laps = 2
        # B: 1 gate rounding + finish → GP, laps = 2
        session = _session(
            num_laps=3,
            gate_sns=["A", "B", "A"],  # A gets 2 roundings, B gets 1
            finish_sns=[("B", None)],
        )
        results, _ = score(session)
        places = _places(results)
        assert places["A"] < places["B"], "NRF Gate boat A must rank ahead of GP B"

    def test_no_nrf_warning_for_fewer_than_cap_roundings(self) -> None:
        """No NRF warning when gate_count < gate_cap (regular Gate boat)."""
        # 3-lap race: gate_cap = 2. Boat with only 1 rounding → no NRF warning
        session = _session(
            num_laps=3,
            gate_sns=["A"],  # 1 rounding, gate_cap = 2 → not at cap
            finish_sns=[],
        )
        _, warnings = score(session)
        nrf = [w for w in warnings if isinstance(w, NoRecordedFinishWarning)]
        assert len(nrf) == 0


# ---------------------------------------------------------------------------
# Letter score override
# ---------------------------------------------------------------------------


class TestLetterScoreOverride:
    """DNS/DNC/DNF + gate list → reclassified as Gate with SI 13.2.3(i) note."""

    @pytest.mark.parametrize("letter", ["DNS", "DNC", "DNF"])
    def test_dns_dnc_dnf_on_gate_list_becomes_gate(self, letter: str) -> None:
        """DNS/DNC/DNF boat on gate list is reclassified as Gate."""
        session = _session(
            num_laps=2,
            gate_sns=["G"],
            finish_sns=[("G", letter)],
        )
        results, _ = score(session)
        types = _types(results)
        assert (
            types["G"] == FinishType.GATE
        ), f"Boat with {letter} on gate list must be reclassified as Gate"

    @pytest.mark.parametrize("letter", ["DNS", "DNC", "DNF"])
    def test_override_annotation_mentions_si(self, letter: str) -> None:
        """Reclassified boat has annotation referencing SI 13.2.3(i)."""
        session = _session(
            num_laps=2,
            gate_sns=["G"],
            finish_sns=[("G", letter)],
        )
        results, _ = score(session)
        r = next(r for r in results if r.competitor.sail_number == "G")
        assert r.annotation is not None
        assert "13.2.3" in r.annotation

    def test_dns_without_gate_list_stays_letter_score(self) -> None:
        """DNS boat NOT on gate list stays as FinishType.LETTER_SCORE."""
        session = _session(
            num_laps=2,
            gate_sns=[],
            finish_sns=[("G", "DNS")],
        )
        results, _ = score(session)
        types = _types(results)
        assert types["G"] == FinishType.LETTER_SCORE

    def test_non_dns_letter_score_stays_letter_score(self) -> None:
        """DSQ or OCS boat on gate list stays as LETTER_SCORE (not overridden)."""
        session = _session(
            num_laps=2,
            gate_sns=["G"],
            finish_sns=[("G", "DSQ")],
        )
        results, _ = score(session)
        types = _types(results)
        assert types["G"] == FinishType.LETTER_SCORE

    def test_letter_score_place_at_bottom(self) -> None:
        """Letter score boats are placed at entries + 1, below all finishers."""
        session = _session(
            num_laps=2,
            gate_sns=["A"],
            finish_sns=[("A", None), ("B", "DNF")],
        )
        results, _ = score(session)
        places = _places(results)
        # A is standard (1 gate rounding + finish = 2 laps in 2-lap race)
        # B is letter score (no gate rounding)
        assert places["B"] > places["A"]

    def test_letter_score_place_equals_entries_plus_one(self) -> None:
        """Letter score place = count of non-letter-score entries + 1."""
        session = _session(
            num_laps=2,
            gate_sns=["A", "B"],  # A and B each do 1 rounding
            finish_sns=[("A", None), ("B", None), ("C", "DNF")],
        )
        results, _ = score(session)
        non_letter = sum(1 for r in results if r.finish_type != FinishType.LETTER_SCORE)
        c_result = next(r for r in results if r.competitor.sail_number == "C")
        assert c_result.place == non_letter + 1


# ---------------------------------------------------------------------------
# Short-lap tier ordering
# ---------------------------------------------------------------------------


class TestShortLapTierOrdering:
    """Gate boats always rank ahead of line-crossers in same lap-count tier."""

    def test_gate_boat_before_gp_same_tier(self) -> None:
        """Gate boat with same laps as GP boat → Gate ranks first."""
        # 3-lap race, both have 2 laps
        # GateX: 2 gate roundings, no finish → Gate, laps=2
        # GPY: 1 gate rounding + finish → GP, laps=2
        session = _session(
            num_laps=3,
            gate_sns=["GateX", "GPY", "GateX"],
            finish_sns=[("GPY", None)],
        )
        results, _ = score(session)
        places = _places(results)
        assert places["GateX"] < places["GPY"]

    def test_gate_boat_before_finish_only_same_tier(self) -> None:
        """Gate boat ranks before Finish Only in same 1-lap tier."""
        session = _session(
            num_laps=2,
            gate_sns=["G"],
            finish_sns=[("F", None)],
        )
        results, _ = score(session)
        places = _places(results)
        assert places["G"] < places["F"]

    def test_multiple_gate_boats_sorted_by_sequence_position(self) -> None:
        """Multiple Gate boats with same laps → sorted by per-lap seq position."""
        # 2-lap race (gate_cap = 1)
        # Gate boats G1, G2, G3 each with 1 gate rounding (= gate_cap)
        # G1 rounds gate first (seq pos 1), G2 second (seq pos 2), G3 third (seq pos 3)
        # No finish entries → all Gate in 1-lap tier
        session = _session(
            num_laps=2,
            gate_sns=["G1", "G2", "G3"],
            finish_sns=[],
        )
        results, _ = score(session)
        places = _places(results)
        assert places["G1"] < places["G2"] < places["G3"]

    def test_multiple_line_crossers_sorted_by_finish_position(self) -> None:
        """Multiple line-crossers in the same tier sort by finish list position.

        In the 2-lap tier (3-lap race), GP boats GP1, GP2, GP3 all have
        1 gate rounding + finish = 2 laps. They should be ordered by their
        finish list position, not by gate sequence.
        """
        # Gate sns: GP3, GP2, GP1 — gate sequence order is GP3 first
        # Finish order: GP1, GP2, GP3 — finish position is reversed
        session = _session(
            num_laps=3,
            gate_sns=["GP3", "GP2", "GP1"],
            finish_sns=[("GP1", None), ("GP2", None), ("GP3", None)],
        )
        results, _ = score(session)
        places = _places(results)
        # Finish list order wins over gate sequence for line-crossers
        assert places["GP1"] < places["GP2"] < places["GP3"]

    def test_gate_boats_before_all_line_crossers(self) -> None:
        """Gate boat(s) always rank above ALL line-crossers in same tier."""
        # 3-lap race, 2-lap tier:
        # GateX: Gate, 2 laps; GP1, GP2, FO: line-crossers, 2 laps
        session = _session(
            num_laps=3,
            gate_sns=["GateX", "GateX", "GP1", "GP2"],
            finish_sns=[("FO", None), ("GP1", None), ("GP2", None)],
        )
        results, _ = score(session)
        places = _places(results)
        gate_place = places["GateX"]
        for sn in ("FO", "GP1", "GP2"):
            assert (
                gate_place < places[sn]
            ), f"Gate boat must rank ahead of line-crosser {sn}"


# ---------------------------------------------------------------------------
# Per-lap sequence position
# ---------------------------------------------------------------------------


class TestPerLapSequencePosition:
    """Per-lap sequence positions are computed from the interleaved gate log."""

    def test_sequence_position_from_interleaved_log(self) -> None:
        """A, B, C have correct 1-lap seq positions despite interleaved entries.

        Gate log: [W, A, W, B, C]
        W completes lap 1 (row 1) then lap 2 (row 3).
        A, B, C each complete only lap 1 (rows 2, 4, 5 respectively).

        Lap-1 sequence positions: W=1, A=2, B=3, C=4.
        In the 1-lap Gate tier, ranking should be A before B before C
        (W is in the 2-lap tier since it completed 2 roundings = gate_cap
        for a 3-lap race).
        """
        session = _session(
            num_laps=3,
            gate_sns=["W", "A", "W", "B", "C"],
            finish_sns=[],
        )
        results, _ = score(session)
        places = _places(results)
        # W (2 laps, gate_cap=2) is in the 2-lap tier
        # A, B, C (1 lap each) in the 1-lap tier, in gate sequence order
        assert places["W"] < places["A"]  # 2-lap tier before 1-lap tier
        assert places["A"] < places["B"] < places["C"]

    def test_seq_pos_reflects_lap_specific_order_not_row_index(self) -> None:
        """Relative ranking within a tier is by per-lap seq pos, not raw index.

        Gate log: [W, W, A, B, C]
        W at rows 1, 2 (2 roundings = gate_cap for 3-lap race).
        A at row 3 (lap-1 seq pos 2), B at row 4 (seq pos 3), C at row 5 (seq pos 4).

        If we (incorrectly) sorted by raw row index, A would be 3, B 4, C 5.
        The correct per-lap seq positions are 2, 3, 4 (but relative order is same).
        The key test: A is ranked 2nd in the 1-lap tier (after W in 2-lap tier),
        B is 3rd, C is 4th.
        """
        session = _session(
            num_laps=3,
            gate_sns=["W", "W", "A", "B", "C"],
            finish_sns=[],
        )
        results, _ = score(session)
        places = _places(results)
        assert places["W"] < places["A"] < places["B"] < places["C"]


# ---------------------------------------------------------------------------
# Excess gate roundings
# ---------------------------------------------------------------------------


class TestExcessRoundings:
    """Boats with more gate roundings than the cap get a warning and are capped."""

    def test_excess_warning_issued(self) -> None:
        """ExcessRoundingsWarning issued when raw count exceeds gate_cap."""
        # 2-lap race (gate_cap = 1); boat recorded 2 times
        session = _session(
            num_laps=2,
            gate_sns=["A", "A"],  # 2 roundings; cap is 1
            finish_sns=[("A", None)],
        )
        _, warnings = score(session)
        excess = [w for w in warnings if isinstance(w, ExcessRoundingsWarning)]
        assert len(excess) == 1
        assert excess[0].sail_number == "A"
        assert excess[0].raw_count == 2
        assert excess[0].cap == 1

    def test_excess_capped_result(self) -> None:
        """Boat with excess roundings scored at cap (Standard, not promoted)."""
        session = _session(
            num_laps=2,
            gate_sns=["A", "A"],
            finish_sns=[("A", None)],
        )
        results, _ = score(session)
        r = next(r for r in results if r.competitor.sail_number == "A")
        assert r.laps == 2  # capped gate_count (1) + 1 finish = 2
        assert r.finish_type == FinishType.STANDARD


# ---------------------------------------------------------------------------
# Lead-boat violation
# ---------------------------------------------------------------------------


class TestLeadBoatViolation:
    """First boat in a fleet group having fewer than required laps → warning."""

    def test_lead_boat_warning_for_82_fleet(self) -> None:
        """LeadBoatViolationWarning fires when first 8.2 finisher short-lapped."""
        # 2-lap race; first 8.2 boat to cross line has 0 gate roundings (1 lap)
        comps = [
            _competitor("A", rig_size="8.2"),
            _competitor("B", rig_size="8.2"),
        ]
        session = _session(
            num_laps=2,
            gate_sns=["B"],  # B has 1 rounding; A has 0
            finish_sns=[("A", None), ("B", None)],  # A crosses first
            competitors=comps,
        )
        _, warnings = score(session)
        lb = [w for w in warnings if isinstance(w, LeadBoatViolationWarning)]
        assert len(lb) >= 1
        lb_82 = [w for w in lb if w.fleet_group == "8.2"]
        assert len(lb_82) == 1
        assert lb_82[0].sail_number == "A"
        assert lb_82[0].laps == 1
        assert lb_82[0].required_laps == 2

    def test_no_lead_boat_warning_when_lead_has_full_laps(self) -> None:
        """No LeadBoatViolationWarning when first 8.2 finisher has full laps."""
        comps = [
            _competitor("A", rig_size="8.2"),
            _competitor("B", rig_size="8.2"),
        ]
        session = _session(
            num_laps=2,
            gate_sns=["A", "B"],  # both have 1 rounding = gate_cap
            finish_sns=[("A", None), ("B", None)],
            competitors=comps,
        )
        _, warnings = score(session)
        lb = [w for w in warnings if isinstance(w, LeadBoatViolationWarning)]
        assert len(lb) == 0

    def test_lead_boat_violation_detected_independently_per_fleet(self) -> None:
        """8.2 and non-8.2 fleet lead-boat checks are independent."""
        comps = [
            _competitor("A82", rig_size="8.2"),
            _competitor("B82", rig_size="8.2"),
            _competitor("C75", rig_size="7.5"),
            _competitor("D75", rig_size="7.5"),
        ]
        # First 8.2 finisher (A82) has full laps; first 7.5 finisher (C75) has 1 lap
        session = RaceSession(
            num_laps=2,
            finish_line_config=FinishLineConfig.FINISH_AT_GATE,
            competitors=comps,
            green_fleet=set(),
            gate_roundings=[
                GateRounding(position=1, sail_number="A82"),
                GateRounding(position=2, sail_number="B82"),
                GateRounding(position=3, sail_number="D75"),
                # C75 has no gate rounding (Finish Only → 1 lap)
            ],
            finish_entries=[
                FinishEntry(position=1, sail_number="C75"),  # 1 lap, first 7.5
                FinishEntry(position=2, sail_number="A82"),  # 2 laps, first 8.2
                FinishEntry(position=3, sail_number="B82"),  # 2 laps
                FinishEntry(position=4, sail_number="D75"),  # 2 laps
            ],
        )
        _, warnings = score(session)
        lb = [w for w in warnings if isinstance(w, LeadBoatViolationWarning)]
        fleet_groups = {w.fleet_group for w in lb}
        # Warning for non-8.2 (C75 has 1 lap), NOT for 8.2 (A82 has 2 laps)
        assert "non-8.2" in fleet_groups
        assert "8.2" not in fleet_groups


# ---------------------------------------------------------------------------
# Two-fleet shared course
# ---------------------------------------------------------------------------


class TestTwoFleetSharedCourse:
    """8.2 and non-8.2 boats on same course → per-fleet rankings correct."""

    def test_overall_ranking_includes_all_fleets(self) -> None:
        """Results list contains boats from both 8.2 and 7.5 fleets."""
        comps = [
            _competitor("A82", rig_size="8.2"),
            _competitor("B75", rig_size="7.5"),
        ]
        session = _session(
            num_laps=2,
            gate_sns=["A82", "B75"],
            finish_sns=[("A82", None), ("B75", None)],
            competitors=comps,
        )
        results, _ = score(session)
        sail_numbers = {r.competitor.sail_number for r in results}
        assert "A82" in sail_numbers
        assert "B75" in sail_numbers

    def test_two_fleet_lead_boat_warning_fires_for_correct_fleet_only(
        self,
    ) -> None:
        """Warning fires only for the fleet whose lead boat short-lapped."""
        comps = [
            _competitor("A82", rig_size="8.2"),
            _competitor("B82", rig_size="8.2"),
            _competitor("C75", rig_size="7.5"),
        ]
        # C75 (7.5) is first boat overall to cross, but with 0 gate roundings (1 lap)
        # A82 (8.2) crosses second with full laps
        session = RaceSession(
            num_laps=2,
            finish_line_config=FinishLineConfig.FINISH_AT_GATE,
            competitors=comps,
            green_fleet=set(),
            gate_roundings=[
                GateRounding(position=1, sail_number="A82"),
                GateRounding(position=2, sail_number="B82"),
            ],
            finish_entries=[
                FinishEntry(position=1, sail_number="C75"),  # 7.5, 1 lap
                FinishEntry(position=2, sail_number="A82"),  # 8.2, 2 laps
                FinishEntry(position=3, sail_number="B82"),  # 8.2, 2 laps
            ],
        )
        _, warnings = score(session)
        lb = [w for w in warnings if isinstance(w, LeadBoatViolationWarning)]
        fleet_groups = {w.fleet_group for w in lb}
        assert "non-8.2" in fleet_groups  # C75 has 1 lap → violation
        assert "8.2" not in fleet_groups  # A82 has 2 laps → no violation


# ---------------------------------------------------------------------------
# RMG Example 1: 3-lap race, 20 boats (RMG pp.18-19)
# ---------------------------------------------------------------------------


def _rmg_example_1_session() -> RaceSession:
    """Build the RaceSession for RMG Example 1."""
    sail_numbers = [
        "2106",
        "2798",
        "3001",
        "2511",
        "2469",
        "2445",
        "2688",
        "2096",
        "2314",
        "2275",
        "2864",
        "2554",
        "2117",
        "2228",
        "2916",
        "3102",
        "3118",
        "2186",
        "2994",
        "2666",
    ]
    competitors = [_competitor(sn) for sn in sail_numbers]

    # Gate list: 29 entries in recording order
    gate_sns = [
        # Lap-1 roundings (15 boats)
        "2106",
        "2798",
        "3001",
        "2511",
        "2469",
        "2445",
        "2688",
        "2096",
        "2314",
        "2275",
        "2864",
        "2554",
        "2117",
        "2228",
        "2916",
        # Lap-2 roundings (14 boats; 3102, 3118, 2994 appear here for the first time)
        "2106",
        "2798",
        "3001",
        "2511",
        "2469",
        "2445",
        "2096",
        "2314",
        "3102",
        "3118",
        "2275",
        "2864",
        "2554",
        "2994",
    ]

    # Finish list: 17 regular finishers + 2666 with DNF
    finish_entries_data: list[tuple[str, str | None]] = [
        ("2106", None),
        ("3001", None),
        ("2186", None),
        ("2798", None),
        ("2469", None),
        ("2445", None),
        ("2314", None),
        ("2096", None),
        ("2864", None),
        ("2275", None),
        ("2554", None),
        ("2916", None),
        ("2228", None),
        ("3102", None),
        ("3118", None),
        ("2117", None),
        ("2994", None),
        ("2666", "DNF"),  # started but DNF — not on gate list
    ]

    gate_roundings = [
        GateRounding(position=i + 1, sail_number=sn) for i, sn in enumerate(gate_sns)
    ]
    finish_entries = [
        FinishEntry(position=i + 1, sail_number=sn, letter_score=ls)
        for i, (sn, ls) in enumerate(finish_entries_data)
    ]
    return RaceSession(
        num_laps=3,
        finish_line_config=FinishLineConfig.FINISH_AT_GATE,
        competitors=competitors,
        green_fleet=set(),
        gate_roundings=gate_roundings,
        finish_entries=finish_entries,
    )


class TestRMGExample1:
    """Integration test: RMG Grand Prix Finish Example (3-lap, 20 boats).

    Expected GP Finish Ranking:
      1–10: Standard 3-lap boats in finish order
      11:   2511  (Gate, 2 laps)
      12:   2916  (GP, 2 laps)
      13:   2228  (GP, 2 laps)
      14:   3102  (GP, 2 laps)
      15:   3118  (GP, 2 laps)
      16:   2117  (GP, 2 laps)
      17:   2994  (GP, 2 laps)
      18:   2688  (Gate, 1 lap)
      19:   2186  (Finish Only, 1 lap)
      20:   2666  (DNF letter score)
    """

    @pytest.fixture
    def results_and_warnings(
        self,
    ) -> tuple[list[ScoredResult], list[ScorerWarning]]:
        """Score the RMG Example 1 session and return (results, warnings)."""
        return score(_rmg_example_1_session())

    def test_full_ranking_places(
        self, results_and_warnings: tuple[list[ScoredResult], list[ScorerWarning]]
    ) -> None:
        """All 20 places in the expected GP Finish Ranking are correct."""
        results, _ = results_and_warnings
        places = _places(results)
        expected = {
            "2106": 1,
            "3001": 2,
            "2798": 3,
            "2469": 4,
            "2445": 5,
            "2314": 6,
            "2096": 7,
            "2864": 8,
            "2275": 9,
            "2554": 10,
            "2511": 11,
            "2916": 12,
            "2228": 13,
            "3102": 14,
            "3118": 15,
            "2117": 16,
            "2994": 17,
            "2688": 18,
            "2186": 19,
            "2666": 20,
        }
        for sn, exp_place in expected.items():
            assert (
                places[sn] == exp_place
            ), f"Boat {sn}: expected place {exp_place}, got {places[sn]}"

    def test_finish_types(
        self, results_and_warnings: tuple[list[ScoredResult], list[ScorerWarning]]
    ) -> None:
        """Finish types match the RMG expected values."""
        results, _ = results_and_warnings
        types = _types(results)
        expected_types = {
            "2106": FinishType.STANDARD,
            "2798": FinishType.STANDARD,
            "3001": FinishType.STANDARD,
            "2469": FinishType.STANDARD,
            "2445": FinishType.STANDARD,
            "2096": FinishType.STANDARD,
            "2314": FinishType.STANDARD,
            "2275": FinishType.STANDARD,
            "2864": FinishType.STANDARD,
            "2554": FinishType.STANDARD,
            "2511": FinishType.GATE,
            "2916": FinishType.GP,
            "2228": FinishType.GP,
            "3102": FinishType.GP,
            "3118": FinishType.GP,
            "2117": FinishType.GP,
            "2994": FinishType.GP,
            "2688": FinishType.GATE,
            "2186": FinishType.FINISH_ONLY,
            "2666": FinishType.LETTER_SCORE,
        }
        for sn, exp_type in expected_types.items():
            assert (
                types[sn] == exp_type
            ), f"Boat {sn}: expected {exp_type}, got {types[sn]}"

    def test_lap_counts(
        self, results_and_warnings: tuple[list[ScoredResult], list[ScorerWarning]]
    ) -> None:
        """Lap counts match the RMG expected values."""
        results, _ = results_and_warnings
        laps = {r.competitor.sail_number: r.laps for r in results}
        expected_laps = {
            "2106": 3,
            "2798": 3,
            "3001": 3,
            "2469": 3,
            "2445": 3,
            "2096": 3,
            "2314": 3,
            "2275": 3,
            "2864": 3,
            "2554": 3,
            "2511": 2,
            "2916": 2,
            "2228": 2,
            "3102": 2,
            "3118": 2,
            "2117": 2,
            "2994": 2,
            "2688": 1,
            "2186": 1,
        }
        for sn, exp_laps in expected_laps.items():
            assert (
                laps[sn] == exp_laps
            ), f"Boat {sn}: expected {exp_laps} laps, got {laps[sn]}"

    # --- 5 named sub-assertions from RMG p.19 ---

    def test_2186_cross_tier_demotion(
        self, results_and_warnings: tuple[list[ScoredResult], list[ScorerWarning]]
    ) -> None:
        """Sub-assertion 1 (RMG p.19): 2186 crosses line 3rd but ranks 19th.

        '...does not appear on the gate list. It appears once in total.
        Therefore, despite crossing the line in third, 2186 only sailed one
        lap.'
        """
        results, _ = results_and_warnings
        places = _places(results)
        assert places["2186"] == 19, (
            "Boat 2186 finished 3rd across the line but should be placed 19th "
            "due to sailing only 1 lap (Finish Only classification)"
        )

    def test_2511_gate_ahead_of_gp_finishers(
        self, results_and_warnings: tuple[list[ScoredResult], list[ScorerWarning]]
    ) -> None:
        """Sub-assertion 2 (RMG p.19): 2511 ranks ahead of 2-lap GP boats.

        '...2511 completed two laps before any of the [GP 2-lap] numbers
        completed two laps, so is ranked ahead of the [GP 2-lap] numbers.'
        """
        results, _ = results_and_warnings
        places = _places(results)
        gp_2lap = ["2916", "2228", "3102", "3118", "2117", "2994"]
        for sn in gp_2lap:
            assert places["2511"] < places[sn], (
                f"Gate boat 2511 (place {places['2511']}) must rank ahead of "
                f"GP boat {sn} (place {places[sn]}) in the 2-lap tier"
            )

    def test_2688_gate_ahead_of_finish_only(
        self, results_and_warnings: tuple[list[ScoredResult], list[ScorerWarning]]
    ) -> None:
        """Sub-assertion 3 (RMG p.19): 2688 (Gate, 1 lap) ahead of 2186.

        '...2688 completed one lap before 2186 completed one lap so is
        ranked ahead of 2186.'
        """
        results, _ = results_and_warnings
        places = _places(results)
        assert places["2688"] < places["2186"], (
            f"Gate boat 2688 (place {places['2688']}) must rank ahead of "
            f"Finish Only 2186 (place {places['2186']}) in the 1-lap tier"
        )

    def test_2666_dnf_at_bottom(
        self, results_and_warnings: tuple[list[ScoredResult], list[ScorerWarning]]
    ) -> None:
        """Sub-assertion 4 (RMG p.19): 2666 DNF scored at place 20.

        '...2666 started the race but does not appear on either list.
        Therefore, 2666 failed to complete one lap and scores a DNF.'
        """
        results, _ = results_and_warnings
        places = _places(results)
        assert places["2666"] == 20

    def test_2916_gp_behind_gate(
        self, results_and_warnings: tuple[list[ScoredResult], list[ScorerWarning]]
    ) -> None:
        """Sub-assertion 5 (RMG p.19): 2916 (GP, 2 laps) ranks behind 2511.

        '2916 has 1 gate rounding + 1 finish crossing = 2 laps. Despite
        being on the finish list, 2916 ranks behind 2511 (Gate, same lap
        count) because gate roundings precede the finishing window.'
        """
        results, _ = results_and_warnings
        places = _places(results)
        assert places["2511"] < places["2916"], (
            f"Gate boat 2511 (place {places['2511']}) must rank ahead of "
            f"GP boat 2916 (place {places['2916']}) in the 2-lap tier"
        )

    def test_2798_at_place_3(
        self, results_and_warnings: tuple[list[ScoredResult], list[ScorerWarning]]
    ) -> None:
        """2798 is 3rd in finish order despite 2186 crossing line at position 3.

        '...finish list position 4 (2186 at pos 3 is a 1-lapper, so 2798
        is 3rd among 3-lappers)'
        """
        results, _ = results_and_warnings
        places = _places(results)
        assert places["2798"] == 3, (
            "2798 should be 3rd in GP ranking (2186 at finish pos 3 is "
            "demoted to 1-lap tier)"
        )


# ---------------------------------------------------------------------------
# SEPARATE_PIN config — lap formula & classification
# ---------------------------------------------------------------------------


class TestSeparatePinLapFormula:
    """SEPARATE_PIN: laps = gate_roundings (no finish-crossing bonus)."""

    def test_gp_laps_equals_gate_count(self) -> None:
        """GP boat laps = gate_roundings, not gate_roundings + 1."""
        # 2-lap SEPARATE_PIN; boat G rounds gate once and finishes
        # Under FINISH_AT_GATE it would get 2 laps (1+1). Under SEPARATE_PIN: 1.
        session = _session_sep_pin(
            num_laps=2,
            gate_sns=["G"],
            finish_sns=[("G", None)],
            marker_after=None,
        )
        results, _ = score(session)
        laps = {r.competitor.sail_number: r.laps for r in results}
        assert laps["G"] == 1

    def test_gp_classified_as_gp(self) -> None:
        """Boat with fewer gate roundings + finish → FinishType.GP."""
        session = _session_sep_pin(
            num_laps=2,
            gate_sns=["G"],
            finish_sns=[("G", None)],
            marker_after=None,
        )
        results, _ = score(session)
        types = _types(results)
        assert types["G"] == FinishType.GP

    def test_standard_requires_full_gate_roundings_plus_finish(self) -> None:
        """Standard = required_laps gate roundings + on finish list."""
        # 2-lap race: need 2 gate roundings + finish for Standard
        session = _session_sep_pin(
            num_laps=2,
            gate_sns=["S", "S"],
            finish_sns=[("S", None)],
            marker_after=None,
        )
        results, _ = score(session)
        types = _types(results)
        laps = {r.competitor.sail_number: r.laps for r in results}
        assert types["S"] == FinishType.STANDARD
        assert laps["S"] == 2

    def test_window_phase_rounding_counts_toward_laps(self) -> None:
        """1 pre-window + 1 window-phase rounding = 2 laps total."""
        # 2-lap SEPARATE_PIN; G rounds gate twice with window after first rounding
        # marker_after=0 means gate_roundings[0] is pre-window, [1] is window-phase
        session = _session_sep_pin(
            num_laps=2,
            gate_sns=["G", "G"],
            finish_sns=[],
            marker_after=0,
        )
        results, _ = score(session)
        laps = {r.competitor.sail_number: r.laps for r in results}
        assert laps["G"] == 2  # both roundings count regardless of window phase


# ---------------------------------------------------------------------------
# SEPARATE_PIN config — tier ordering
# ---------------------------------------------------------------------------


class TestSeparatePinTierOrdering:
    """SEPARATE_PIN: pre-window Gate < line-crossers < window-phase Gate."""

    def test_pre_window_gate_ahead_of_gp_same_tier(self) -> None:
        """Pre-window Gate boat ranks ahead of GP boat in same lap-count tier."""
        # 2-lap race; marker after index 1 (both roundings are pre-window)
        # GateB: 1 rounding at idx 0 (pre-window), no finish → Gate, 1 lap
        # GP_A:  1 rounding at idx 1 (pre-window) + finish → GP, 1 lap
        session = _session_sep_pin(
            num_laps=2,
            gate_sns=["GateB", "GP_A"],
            finish_sns=[("GP_A", None)],
            marker_after=1,  # both roundings are pre-window
        )
        results, _ = score(session)
        places = _places(results)
        assert (
            places["GateB"] < places["GP_A"]
        ), "Pre-window Gate GateB must rank ahead of GP GP_A in same tier"

    def test_window_phase_gate_behind_gp_same_tier(self) -> None:
        """Window-phase Gate boat ranks behind GP boat in same lap-count tier."""
        # 2-lap race; marker after index 0
        # GP_A:  1 rounding at idx 0 (pre-window) + finish → GP, 1 lap
        # GateW: 1 rounding at idx 1 (window-phase), no finish → Gate, 1 lap
        session = _session_sep_pin(
            num_laps=2,
            gate_sns=["GP_A", "GateW"],
            finish_sns=[("GP_A", None)],
            marker_after=0,
        )
        results, _ = score(session)
        places = _places(results)
        assert (
            places["GP_A"] < places["GateW"]
        ), "GP GP_A must rank ahead of window-phase Gate GateW in same tier"

    def test_full_ordering_in_one_tier(self) -> None:
        """Within a 1-lap tier: pre-window Gate < GP < window-phase Gate."""
        # gate log: [PreGate(idx 0), GP_A(idx 1), WinGate(idx 2)]
        # marker_after=0 → idx 0 pre-window; idx 1, 2 window-phase
        # PreGate: Gate, pre-window → first
        # GP_A:    GP (line-crosser) → second
        # WinGate: Gate, window-phase → third
        session = _session_sep_pin(
            num_laps=2,
            gate_sns=["PreGate", "GP_A", "WinGate"],
            finish_sns=[("GP_A", None)],
            marker_after=0,
        )
        results, _ = score(session)
        places = _places(results)
        assert places["PreGate"] < places["GP_A"] < places["WinGate"]


# ---------------------------------------------------------------------------
# SEPARATE_PIN config — Error: No Recorded Finish
# ---------------------------------------------------------------------------


class TestSeparatePinNRF:
    """SEPARATE_PIN: required_laps gate roundings + no finish → ERROR_NRF."""

    def test_nrf_classified_as_error_no_recorded_finish(self) -> None:
        """Boat with required_laps roundings and no finish → ERROR_NRF."""
        # 2-lap race: 2 gate roundings = gate_cap; not on finish list
        session = _session_sep_pin(
            num_laps=2,
            gate_sns=["A", "A"],
            finish_sns=[],
            marker_after=None,
        )
        results, _ = score(session)
        types = _types(results)
        assert types["A"] == FinishType.ERROR_NO_RECORDED_FINISH

    def test_nrf_warning_issued_for_separate_pin(self) -> None:
        """NoRecordedFinishWarning returned for SEPARATE_PIN NRF boat."""
        session = _session_sep_pin(
            num_laps=2,
            gate_sns=["A", "A"],
            finish_sns=[],
            marker_after=None,
        )
        _, warnings = score(session)
        nrf = [w for w in warnings if isinstance(w, NoRecordedFinishWarning)]
        assert len(nrf) == 1
        assert nrf[0].sail_number == "A"
        assert nrf[0].gate_count == 2

    def test_gate_boat_below_cap_not_nrf(self) -> None:
        """Gate boat with fewer than required_laps roundings → Gate, no NRF."""
        # 3-lap race: gate_cap = 3; boat with 2 roundings → Gate, not NRF
        session = _session_sep_pin(
            num_laps=3,
            gate_sns=["A", "A"],
            finish_sns=[],
            marker_after=None,
        )
        results, _ = score(session)
        types = _types(results)
        laps = {r.competitor.sail_number: r.laps for r in results}
        assert types["A"] == FinishType.GATE
        assert laps["A"] == 2


# ---------------------------------------------------------------------------
# SEPARATE_PIN config — missing finish window marker
# ---------------------------------------------------------------------------


class TestSeparatePinMissingMarker:
    """SEPARATE_PIN with no marker: warning returned, all roundings pre-window."""

    def test_missing_marker_warning_returned(self) -> None:
        """MissingFinishWindowMarkerWarning issued when no marker placed."""
        session = _session_sep_pin(
            num_laps=2,
            gate_sns=["A", "A"],
            finish_sns=[("A", None)],
            marker_after=None,
        )
        _, warnings = score(session)
        mm = [w for w in warnings if isinstance(w, MissingFinishWindowMarkerWarning)]
        assert len(mm) == 1

    def test_scoring_runs_with_missing_marker(self) -> None:
        """Scoring completes normally even with no marker; all roundings pre-window."""
        session = _session_sep_pin(
            num_laps=2,
            gate_sns=["A", "B"],
            finish_sns=[("A", None), ("B", None)],
            marker_after=None,
        )
        results, _ = score(session)
        # Both boats have 1 rounding (pre-window) + finish → GP, 1 lap each
        types = _types(results)
        assert types["A"] == FinishType.GP
        assert types["B"] == FinishType.GP

    def test_all_roundings_treated_as_pre_window_when_no_marker(self) -> None:
        """Without marker, Gate boats are all pre-window (rank before GP)."""
        # GateX: 1 rounding + no finish → Gate, 1 lap (treated as pre-window)
        # GP_Y:  1 rounding + finish → GP, 1 lap
        # Pre-window Gate ranks ahead of GP
        session = _session_sep_pin(
            num_laps=2,
            gate_sns=["GateX", "GP_Y"],
            finish_sns=[("GP_Y", None)],
            marker_after=None,
        )
        results, _ = score(session)
        places = _places(results)
        assert (
            places["GateX"] < places["GP_Y"]
        ), "Without marker, Gate (pre-window) must rank ahead of GP"

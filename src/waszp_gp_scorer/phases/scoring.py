"""Scoring & results display phase for the WASZP GP Scorer.

The **pure business-logic helpers** listed below have no :mod:`tkinter`
dependency and are always importable.  The widget class
(:class:`ScoringPhase`) is only defined when :mod:`tkinter` is available.

Pure helpers
------------
- :data:`RESULT_COLUMNS` — ordered column names for the results tables
- :func:`finish_type_display` — human-readable finish-type string for a result
- :func:`collect_rig_sizes` — sorted unique rig sizes from a competitor list
- :func:`scored_result_row` — format a :class:`~waszp_gp_scorer.models.ScoredResult`
  as a display tuple
- :func:`filter_results_by_rig` — filter results to selected rig sizes
- :func:`original_finish_list_rows` — build display rows for the original
  finish list panel
"""

from __future__ import annotations

from typing import Optional

from waszp_gp_scorer.models import (
    Competitor,
    FinishEntry,
    FinishType,
    ScoredResult,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Column headers shared by both the GP Finish Ranking and original-finish-list
#: tables.
RESULT_COLUMNS: tuple[str, ...] = (
    "Place",
    "Country",
    "Sail #",
    "Sailor Name",
    "Rig Size",
    "Division",
    "Laps",
    "Finish Type",
)

#: Explanation shown as a tooltip when hovering over a "Gate" finish-type cell
#: in the GP Finish Ranking table.
_GATE_TOOLTIP_TEXT: str = (
    "Gate finish (SI 13.2.3(i)):\n"
    "Boat completed gate roundings but did not cross the finishing line.\n\n"
    "Also applies when a DNS / DNC / DNF letter score is overridden because\n"
    "the boat also appeared on the gate list — the letter score is replaced\n"
    "with a Gate classification."
)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def finish_type_display(result: ScoredResult) -> str:
    """Return the display string for the Finish Type column of *result*.

    For :attr:`~waszp_gp_scorer.models.FinishType.LETTER_SCORE` entries the
    actual letter-score code is returned (e.g. ``"DNS"``).  For all other
    finish types the :attr:`~waszp_gp_scorer.models.FinishType.value` string
    is returned.

    Args:
        result: The scored result to format.

    Returns:
        A human-readable finish-type string.
    """
    if result.finish_type == FinishType.LETTER_SCORE and result.letter_score:
        return result.letter_score
    return result.finish_type.value


def collect_rig_sizes(competitors: list[Competitor]) -> list[str]:
    """Return a sorted list of unique rig sizes found in *competitors*.

    Args:
        competitors: List of registered competitors.

    Returns:
        Sorted list of unique rig-size strings (e.g. ``["7.5", "8.2"]``).
        Empty list when *competitors* is empty.
    """
    return sorted({c.rig_size for c in competitors})


def scored_result_row(result: ScoredResult) -> tuple[str, ...]:
    """Format *result* as an 8-element display tuple matching :data:`RESULT_COLUMNS`.

    Columns: Place, Country, Sail #, Sailor Name, Rig Size, Division, Laps,
    Finish Type.

    A ``laps`` value of 0 (letter-score boats) is rendered as an empty string.

    Args:
        result: The :class:`~waszp_gp_scorer.models.ScoredResult` to format.

    Returns:
        An 8-element :class:`tuple` of :class:`str`.
    """
    c = result.competitor
    laps_str = str(result.laps) if result.laps > 0 else ""
    return (
        str(result.place),
        c.country_code,
        c.sail_number,
        c.name,
        c.rig_size,
        c.division,
        laps_str,
        finish_type_display(result),
    )


def filter_results_by_rig(
    results: list[ScoredResult],
    selected_rigs: set[str],
) -> list[ScoredResult]:
    """Return the subset of *results* whose rig size is in *selected_rigs*.

    Order is preserved.

    Args:
        results: Full list of scored results.
        selected_rigs: Set of rig-size strings to include.

    Returns:
        Filtered list of :class:`~waszp_gp_scorer.models.ScoredResult`.
    """
    return [r for r in results if r.competitor.rig_size in selected_rigs]


def original_finish_list_rows(
    finish_entries: list[FinishEntry],
    results_by_sail: dict[str, ScoredResult],
    competitor_map: dict[str, Competitor],
) -> list[tuple[str, ...]]:
    """Build display rows for the original finish-list panel (in entry order).

    Each row matches :data:`RESULT_COLUMNS` with ``Place`` being the boat's
    finish-list position (1-based entry order, not GP ranking place).  Boats
    whose rig size is unknown (not in *competitor_map*) are given placeholder
    values.

    Args:
        finish_entries: Finish entries in recorded order.
        results_by_sail: Mapping of sail number → scored result.
        competitor_map: Mapping of sail number → competitor.

    Returns:
        List of 8-element :class:`str` tuples in finish-entry order.
    """
    rows: list[tuple[str, ...]] = []
    for entry in finish_entries:
        sn = entry.sail_number
        comp: Optional[Competitor] = competitor_map.get(sn)
        result: Optional[ScoredResult] = results_by_sail.get(sn)

        country = comp.country_code if comp else "UNK"
        name = comp.name if comp else f"Unknown ({sn})"
        rig_size = comp.rig_size if comp else "Unknown"
        division = comp.division if comp else "Unknown"

        if result is not None:
            laps_str = str(result.laps) if result.laps > 0 else ""
            ft_str = finish_type_display(result)
        elif entry.letter_score:
            laps_str = ""
            ft_str = entry.letter_score
        else:
            laps_str = ""
            ft_str = ""

        rows.append(
            (
                str(entry.position),
                country,
                sn,
                name,
                rig_size,
                division,
                laps_str,
                ft_str,
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Tkinter-dependent widget — only defined when tkinter is available
# ---------------------------------------------------------------------------
try:
    import tkinter as tk
    from tkinter import messagebox, ttk

    from waszp_gp_scorer.scorer import (
        LeadBoatViolationWarning,
        ScorerWarning,
        score,
    )
    from waszp_gp_scorer.session import AutoSaveSession

    class ScoringPhase(ttk.Frame):
        """Scoring & results display phase.

        Displays:

        - **GP Finish Ranking** panel (left): boats sorted by the scoring
          algorithm, with rig-size checkboxes to show/hide fleet subgroups.
        - **Original Finish List** panel (right): boats in the order they were
          entered into the finish list.
        - **Warnings** section: lead-boat violation warnings shown prominently.
        - **Gate tooltip**: hovering over a "Gate" row in the ranking table
          shows the SI 13.2.3(i) explanation.

        Scoring is recalculated automatically whenever :meth:`refresh` is
        called (triggered by the application shell on each navigation to this
        phase).

        Args:
            parent: Parent widget.
            auto_save: Optional initial
                :class:`~waszp_gp_scorer.session.AutoSaveSession`.
                Can be ``None`` and set later via :meth:`set_session`.
        """

        def __init__(
            self,
            parent: tk.Widget,
            auto_save: "Optional[AutoSaveSession]" = None,
        ) -> None:
            super().__init__(parent)
            self._auto_save: "Optional[AutoSaveSession]" = None
            self._scored_results: list[ScoredResult] = []
            self._scorer_warnings: list[ScorerWarning] = []
            self._rig_vars: dict[str, tk.BooleanVar] = {}
            self._tooltip_window: "Optional[tk.Toplevel]" = None

            self._build_ui()

            if auto_save is not None:
                self.set_session(auto_save)

        # ------------------------------------------------------------------
        # UI construction
        # ------------------------------------------------------------------

        def _build_ui(self) -> None:
            """Construct all widgets for the scoring phase."""
            self.columnconfigure(0, weight=1)

            # --- Rig-size filter row ---
            self._filter_frame = ttk.LabelFrame(
                self, text="Rig-size filter", padding=4
            )
            self._filter_frame.grid(row=0, column=0, sticky=tk.EW, padx=8, pady=(4, 2))
            # Checkboxes are added dynamically in _update_rig_filter_checkboxes()

            # --- Side-by-side panels ---
            panels = ttk.Frame(self)
            panels.grid(row=1, column=0, sticky=tk.NSEW, padx=8, pady=4)
            panels.columnconfigure(0, weight=1)
            panels.columnconfigure(1, weight=1)
            panels.rowconfigure(0, weight=1)
            self.rowconfigure(1, weight=1)

            # Left: GP Finish Ranking
            left_frame = ttk.LabelFrame(panels, text="GP Finish Ranking", padding=4)
            left_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 4))
            left_frame.rowconfigure(0, weight=1)
            left_frame.columnconfigure(0, weight=1)
            self._ranking_tree = self._build_table(left_frame)

            # Tooltip bindings for Gate rows
            self._ranking_tree.bind("<Motion>", self._on_ranking_motion)
            self._ranking_tree.bind(
                "<Leave>", lambda _e: self._hide_tooltip()
            )

            # Right: Original Finish List
            right_frame = ttk.LabelFrame(
                panels, text="Original Finish List", padding=4
            )
            right_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=(4, 0))
            right_frame.rowconfigure(0, weight=1)
            right_frame.columnconfigure(0, weight=1)
            self._finish_tree = self._build_table(right_frame)

            # --- Warnings section ---
            warn_frame = ttk.LabelFrame(self, text="Warnings", padding=4)
            warn_frame.grid(row=2, column=0, sticky=tk.EW, padx=8, pady=(2, 4))

            self._warnings_label = ttk.Label(
                warn_frame,
                text="",
                foreground="#AA0000",
                wraplength=860,
                justify=tk.LEFT,
                font=("Helvetica", 11, "bold"),
            )
            self._warnings_label.pack(fill=tk.X)

            # Gate-type info label (always visible when Gate boats are present)
            self._gate_info_label = ttk.Label(
                self,
                text="",
                foreground="#555555",
                wraplength=860,
                justify=tk.LEFT,
            )
            self._gate_info_label.grid(
                row=3, column=0, sticky=tk.EW, padx=12, pady=(0, 4)
            )

        def _build_table(self, parent: tk.Widget) -> ttk.Treeview:
            """Build a Treeview table with :data:`RESULT_COLUMNS` headings.

            Args:
                parent: The frame to place the table in.

            Returns:
                The configured :class:`~tkinter.ttk.Treeview` widget.
            """
            tree = ttk.Treeview(
                parent,
                columns=RESULT_COLUMNS,
                show="headings",
                selectmode="browse",
            )
            for col in RESULT_COLUMNS:
                tree.heading(col, text=col)

            tree.column("Place", width=45, anchor=tk.CENTER, stretch=False)
            tree.column("Country", width=60, anchor=tk.CENTER, stretch=False)
            tree.column("Sail #", width=80, anchor=tk.CENTER, stretch=False)
            tree.column("Sailor Name", width=150, stretch=True)
            tree.column("Rig Size", width=65, anchor=tk.CENTER, stretch=False)
            tree.column("Division", width=70, anchor=tk.CENTER, stretch=False)
            tree.column("Laps", width=40, anchor=tk.CENTER, stretch=False)
            tree.column("Finish Type", width=120, anchor=tk.W, stretch=False)

            vsb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=vsb.set)
            tree.grid(row=0, column=0, sticky=tk.NSEW)
            vsb.grid(row=0, column=1, sticky=tk.NS)

            return tree

        # ------------------------------------------------------------------
        # Session lifecycle
        # ------------------------------------------------------------------

        def set_session(self, auto_save: "AutoSaveSession") -> None:
            """Update the active session and refresh the display.

            Args:
                auto_save: The
                    :class:`~waszp_gp_scorer.session.AutoSaveSession` to use.
            """
            self._auto_save = auto_save
            self.refresh()

        # ------------------------------------------------------------------
        # Scoring & display refresh
        # ------------------------------------------------------------------

        def refresh(self) -> None:
            """Re-run the scorer and rebuild both result tables.

            Safe to call when no session is active (becomes a no-op).
            """
            if self._auto_save is None:
                return
            self._run_scoring()
            self._update_rig_filter_checkboxes()
            self._apply_filters()
            self._display_warnings(self._scorer_warnings)

        def _run_scoring(self) -> None:
            """Invoke :func:`~waszp_gp_scorer.scorer.score` and cache results."""
            if self._auto_save is None:
                return
            try:
                results, warnings = score(self._auto_save.session)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Scoring error", f"Could not score race:\n{exc}")
                self._scored_results = []
                self._scorer_warnings = []
                return
            self._scored_results = results
            self._scorer_warnings = warnings

        def _update_rig_filter_checkboxes(self) -> None:
            """Rebuild rig-size checkboxes to match the current competitor list."""
            # Remove old checkboxes
            for widget in self._filter_frame.winfo_children():
                widget.destroy()

            if self._auto_save is None:
                return

            competitors = self._auto_save.session.competitors
            rig_sizes = collect_rig_sizes(competitors)

            # Preserve checked state for existing rigs; default new rigs to True
            new_vars: dict[str, tk.BooleanVar] = {}
            for rig in rig_sizes:
                var = self._rig_vars.get(rig, tk.BooleanVar(value=True))
                new_vars[rig] = var
                cb = ttk.Checkbutton(
                    self._filter_frame,
                    text=rig,
                    variable=var,
                    command=self._on_rig_filter_changed,
                )
                cb.pack(side=tk.LEFT, padx=6)

            self._rig_vars = new_vars

            # If no rig sizes found but there are results, show an "All" checkbox
            if not rig_sizes and self._scored_results:
                ttk.Label(self._filter_frame, text="(no rig-size data)").pack(
                    side=tk.LEFT, padx=6
                )

        def _on_rig_filter_changed(self) -> None:
            """Respond to a rig-size checkbox toggle by re-filtering tables."""
            self._apply_filters()

        def _apply_filters(self) -> None:
            """Rebuild both tables according to current rig-size checkbox state."""
            selected = {rig for rig, var in self._rig_vars.items() if var.get()}

            # When no rig checkboxes exist (empty competitor list) show all results
            if not self._rig_vars:
                filtered_results = list(self._scored_results)
            else:
                filtered_results = filter_results_by_rig(self._scored_results, selected)

            self._populate_ranking_table(filtered_results)
            self._populate_finish_list(selected)

        def _populate_ranking_table(self, results: list[ScoredResult]) -> None:
            """Populate the GP Finish Ranking Treeview from *results*.

            Args:
                results: Filtered and sorted scored results.
            """
            for child in self._ranking_tree.get_children():
                self._ranking_tree.delete(child)

            has_gate = False
            for i, result in enumerate(results):
                row = scored_result_row(result)
                tags: tuple[str, ...] = ()
                if result.finish_type == FinishType.GATE:
                    tags = ("gate_row",)
                    has_gate = True
                self._ranking_tree.insert(
                    "", tk.END, iid=f"rank_{i}", values=row, tags=tags
                )

            self._ranking_tree.tag_configure("gate_row", foreground="#555555")

            # Show gate info label when any Gate rows are visible
            if has_gate:
                self._gate_info_label.configure(
                    text=(
                        "\u2139  Gate finish (SI 13.2.3(i)): hover over a Gate row "
                        "in the GP Finish Ranking table for details."
                    )
                )
            else:
                self._gate_info_label.configure(text="")

        def _populate_finish_list(self, selected_rigs: set[str]) -> None:
            """Populate the Original Finish List Treeview.

            Filters to boats whose rig size is in *selected_rigs*; when the
            rig-filter dict is empty (no competitor data), all entries are shown.

            Args:
                selected_rigs: Set of rig sizes to include.
            """
            for child in self._finish_tree.get_children():
                self._finish_tree.delete(child)

            if self._auto_save is None:
                return

            session = self._auto_save.session
            results_by_sail = {
                r.competitor.sail_number: r for r in self._scored_results
            }
            competitor_map = {c.sail_number: c for c in session.competitors}

            all_rows = original_finish_list_rows(
                session.finish_entries, results_by_sail, competitor_map
            )

            for i, row in enumerate(all_rows):
                # row[4] = Rig Size
                rig = row[4]
                if self._rig_vars and rig not in selected_rigs and rig != "Unknown":
                    continue  # filtered out
                self._finish_tree.insert("", tk.END, iid=f"finish_{i}", values=row)

        # ------------------------------------------------------------------
        # Warnings display
        # ------------------------------------------------------------------

        def _display_warnings(self, warnings: "list[ScorerWarning]") -> None:
            """Render lead-boat violation warnings into the warnings label.

            Only :class:`~waszp_gp_scorer.scorer.LeadBoatViolationWarning`
            objects are rendered prominently; other warning types are
            suppressed (they are shown during data entry).

            Args:
                warnings: All scorer warnings from
                    :func:`~waszp_gp_scorer.scorer.score`.
            """
            parts: list[str] = []
            for w in warnings:
                if isinstance(w, LeadBoatViolationWarning):
                    parts.append(
                        f"\u26a0 Lead-boat violation ({w.fleet_group} fleet): "
                        f"{w.sail_number} finished first but completed only "
                        f"{w.laps} of {w.required_laps} required laps."
                    )
            self._warnings_label.configure(text="\n".join(parts))

        # ------------------------------------------------------------------
        # Gate-row tooltip
        # ------------------------------------------------------------------

        def _on_ranking_motion(self, event: tk.Event) -> None:
            """Show or hide the Gate tooltip as the mouse moves over the table.

            Args:
                event: The ``<Motion>`` event from the ranking Treeview.
            """
            item = self._ranking_tree.identify_row(event.y)
            if not item:
                self._hide_tooltip()
                return
            values = self._ranking_tree.item(item, "values")
            finish_type_idx = 7  # 8th column (0-based)
            if len(values) > finish_type_idx and values[finish_type_idx] == "Gate":
                self._show_tooltip(event.x_root, event.y_root)
            else:
                self._hide_tooltip()

        def _show_tooltip(self, x: int, y: int) -> None:
            """Display the Gate-tooltip popup near (*x*, *y*).

            Args:
                x: Root x coordinate for tooltip placement.
                y: Root y coordinate for tooltip placement.
            """
            if self._tooltip_window is not None:
                return  # already showing
            self._tooltip_window = tk.Toplevel(self)
            self._tooltip_window.wm_overrideredirect(True)
            self._tooltip_window.wm_geometry(f"+{x + 15}+{y + 10}")
            lbl = tk.Label(
                self._tooltip_window,
                text=_GATE_TOOLTIP_TEXT,
                background="#FFFFE0",
                relief=tk.SOLID,
                borderwidth=1,
                wraplength=340,
                justify=tk.LEFT,
                padx=6,
                pady=4,
            )
            lbl.pack()

        def _hide_tooltip(self) -> None:
            """Destroy the Gate-tooltip popup if it is currently shown."""
            if self._tooltip_window is not None:
                self._tooltip_window.destroy()
                self._tooltip_window = None

except ImportError:
    pass

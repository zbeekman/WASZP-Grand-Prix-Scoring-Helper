"""Finish list data entry phase for the WASZP GP Scorer.

The **pure business-logic helpers** listed below have no :mod:`tkinter`
dependency and are always importable.  The widget class
(:class:`FinishListPhase`) is only defined when :mod:`tkinter` is available.

Pure helpers
------------
- :data:`LETTER_SCORES` — ordered list of all 14 letter score codes
- :func:`finish_entry_tier` — gate-rounding-count tier for a single finish entry
- :func:`compute_finish_tiers` — list of tiers for all finish entries
- :func:`parse_finish_csv` — parse a single-column CSV into a sail number list
"""

from __future__ import annotations

from waszp_gp_scorer.models import FinishEntry, GateRounding

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: All 14 letter score codes, in display order.
LETTER_SCORES: list[str] = [
    "DNS",
    "DNC",
    "DNF",
    "DSQ",
    "DNE",
    "OCS",
    "UFD",
    "BFD",
    "ZFP",
    "NSC",
    "RET",
    "SCP",
    "RDG",
    "DPI",
]

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def finish_entry_tier(sail_number: str, gate_roundings: list[GateRounding]) -> int:
    """Return the lap-count tier for *sail_number* based on gate roundings.

    The tier equals the total number of gate roundings recorded for the boat.
    A boat with no gate roundings returns 0 (finish-only).

    Args:
        sail_number: The sail number to look up.
        gate_roundings: The full list of gate rounding entries.

    Returns:
        A non-negative integer (0 = no roundings, 1 = one rounding, ...).
    """
    return sum(1 for r in gate_roundings if r.sail_number == sail_number)


def compute_finish_tiers(
    finish_entries: list[FinishEntry],
    gate_roundings: list[GateRounding],
) -> list[int]:
    """Return a list of tiers for every entry in *finish_entries*.

    The i-th element gives the gate-rounding count for the boat at
    ``finish_entries[i]``.

    Args:
        finish_entries: Ordered list of finish entries.
        gate_roundings: Ordered list of gate rounding entries.

    Returns:
        A list of non-negative integers the same length as *finish_entries*.
    """
    counts: dict[str, int] = {}
    for r in gate_roundings:
        counts[r.sail_number] = counts.get(r.sail_number, 0) + 1
    return [counts.get(fe.sail_number, 0) for fe in finish_entries]


def parse_finish_csv(content: str) -> list[str]:
    """Parse a single-column CSV string into an ordered list of sail numbers.

    Each non-blank line contributes one sail number (the first
    comma-separated field is used so the file can have extra metadata
    columns without breaking the import).

    Args:
        content: Raw CSV text.

    Returns:
        Ordered list of stripped, non-empty sail number strings.
    """
    result: list[str] = []
    for line in content.splitlines():
        parts = line.split(",")
        sn = parts[0].strip()
        if sn:
            result.append(sn)
    return result


# ---------------------------------------------------------------------------
# Tkinter-dependent widget — only defined when tkinter is available
# ---------------------------------------------------------------------------
try:
    import tkinter as tk
    from pathlib import Path
    from tkinter import filedialog, messagebox, ttk
    from typing import Optional

    from waszp_gp_scorer.models import (
        Competitor,
        FinishEntry as _FinishEntry,
    )
    from waszp_gp_scorer.phases.data_entry import BG_COLORS, TEXT_COLORS
    from waszp_gp_scorer.session import AutoSaveSession
    from waszp_gp_scorer.validator import (
        DuplicateFinishEntryWarning,
        FinishOnlyWarning,
        GreenFleetEntryWarning,
        LetterScoreConflictWarning,
        UnknownSailNumberWarning,
        ValidatorWarning,
        validate_finish_entry,
    )
    from waszp_gp_scorer.widgets.sail_combobox import SailCombobox

    # Light grey style for duplicate first-occurrence rows.
    _DUP_FIRST_BG: str = "#CCCCCC"
    _DUP_FIRST_FG: str = "#888888"

    # Light grey for finish-only (no gate roundings) rows.
    _FINISH_ONLY_BG: str = "#F0F0F0"
    _FINISH_ONLY_FG: str = "#888888"

    class _LetterScoreDialog(tk.Toplevel):
        """Modal dialog for choosing a letter score from the 14-code list.

        Args:
            parent: Parent widget.
            current: The currently assigned letter score (empty string for none).
            title: Dialog window title.
        """

        def __init__(
            self,
            parent: tk.Widget,
            current: str = "",
            title: str = "Set Letter Score",
        ) -> None:
            super().__init__(parent)
            self.title(title)
            self.resizable(False, False)
            self.grab_set()
            self.result: "Optional[str]" = None
            self._build_ui(current)

        def _build_ui(self, current: str) -> None:
            """Construct dialog widgets.

            Args:
                current: Pre-selected letter score value.
            """
            frm = ttk.Frame(self, padding=12)
            frm.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frm, text="Letter score:").pack(anchor=tk.W, pady=(0, 4))

            self._var = tk.StringVar(value=current)
            self._cb = ttk.Combobox(
                frm,
                textvariable=self._var,
                values=LETTER_SCORES,
                state="readonly",
                width=10,
            )
            self._cb.pack(fill=tk.X, pady=(0, 8))

            btn_frame = ttk.Frame(frm)
            btn_frame.pack(fill=tk.X)

            ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(
                side=tk.RIGHT, padx=(4, 0)
            )
            ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(
                side=tk.RIGHT
            )

            self._cb.focus_set()

        def _on_ok(self) -> None:
            """Handle OK button: accept the selected value."""
            value = self._var.get()
            if value:
                self.result = value
                self.destroy()

    class _SailPickerDialog(tk.Toplevel):
        """Modal dialog for picking a sail number with autocomplete.

        Args:
            parent: Parent widget.
            all_sail_numbers: Full list of sail numbers for the combobox.
            green_fleet: Sail numbers to exclude from the dropdown.
            title: Dialog window title.
        """

        def __init__(
            self,
            parent: tk.Widget,
            all_sail_numbers: list[str],
            green_fleet: set[str],
            title: str = "Select Sail Number",
        ) -> None:
            super().__init__(parent)
            self.title(title)
            self.resizable(False, False)
            self.grab_set()
            self.result: "Optional[str]" = None
            self._build_ui(all_sail_numbers, green_fleet)

        def _build_ui(self, all_sail_numbers: list[str], green_fleet: set[str]) -> None:
            """Construct dialog widgets.

            Args:
                all_sail_numbers: Full sail number list for autocomplete.
                green_fleet: Sail numbers excluded from the dropdown.
            """
            frm = ttk.Frame(self, padding=12)
            frm.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frm, text="Sail number:").pack(anchor=tk.W, pady=(0, 4))

            self._cb = SailCombobox(
                frm,
                all_sail_numbers=all_sail_numbers,
                green_fleet=green_fleet,
                on_confirm=self._on_confirm,
            )
            self._cb.pack(fill=tk.X, pady=(0, 8))

            btn_frame = ttk.Frame(frm)
            btn_frame.pack(fill=tk.X)

            ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(
                side=tk.RIGHT, padx=(4, 0)
            )
            ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(
                side=tk.RIGHT
            )

            self._cb.focus_set()

        def _on_confirm(self, sail_number: str) -> None:
            """Handle Tab/Enter confirmation from the combobox.

            Args:
                sail_number: The confirmed valid sail number.
            """
            self.result = sail_number
            self.destroy()

        def _on_ok(self) -> None:
            """Handle OK button click."""
            value = self._cb.get_value()
            if value:
                self.result = value
                self.destroy()

    class FinishListPhase(ttk.Frame):
        """Finish list data entry phase.

        Provides a live-updating table of finish entries with:

        - Autocomplete sail number entry via
          :class:`~waszp_gp_scorer.widgets.sail_combobox.SailCombobox`
        - Tab/Enter to confirm and advance to the next entry
        - Background and text color highlighting per lap count from gate data
        - Duplicate finish entry: first occurrence shown in light grey
        - Letter score assignment per row (DNS, DNC, DNF, DSQ, DNE, OCS,
          UFD, BFD, ZFP, NSC, RET, SCP, RDG, DPI)
        - Delete, insert-before, and edit-sail operations on any row
        - Inline validation warnings (duplicate, finish-only, Green Fleet,
          unknown sail number, letter score conflict)
        - CSV upload for a pre-recorded single-column finish list

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
            self._competitor_map: "dict[str, Competitor]" = {}
            self._all_sail_numbers: list[str] = []

            self._build_ui()

            if auto_save is not None:
                self.set_session(auto_save)

        # ------------------------------------------------------------------
        # UI construction
        # ------------------------------------------------------------------

        def _build_ui(self) -> None:
            """Construct all widgets for the finish list phase."""
            self.columnconfigure(0, weight=1)

            # --- Entry form ---
            entry_frame = ttk.LabelFrame(self, text="Add Finish Entry", padding=6)
            entry_frame.grid(row=0, column=0, sticky=tk.EW, padx=8, pady=4)

            self._combobox = SailCombobox(
                entry_frame,
                all_sail_numbers=[],
                green_fleet=set(),
                on_confirm=self._on_add_entry,
            )
            self._combobox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

            ttk.Button(entry_frame, text="Add", command=self._on_add_entry).pack(
                side=tk.LEFT
            )
            ttk.Button(
                entry_frame, text="Upload Finish CSV…", command=self._on_csv_upload
            ).pack(side=tk.LEFT, padx=(8, 0))

            # --- Main area: table + legend ---
            main_frame = ttk.Frame(self)
            main_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=8, pady=4)
            main_frame.columnconfigure(0, weight=1)
            main_frame.rowconfigure(0, weight=1)
            self.rowconfigure(1, weight=1)

            # Table
            table_frame = ttk.Frame(main_frame)
            table_frame.grid(row=0, column=0, sticky=tk.NSEW)
            table_frame.rowconfigure(0, weight=1)
            table_frame.columnconfigure(0, weight=1)

            cols = (
                "#",
                "Sail",
                "Name",
                "Division/Rig",
                "Laps",
                "Letter Score",
                "Notes",
            )
            self._tree = ttk.Treeview(
                table_frame,
                columns=cols,
                show="headings",
                selectmode="browse",
            )
            for col in cols:
                self._tree.heading(col, text=col)
            self._tree.column("#", width=40, anchor=tk.CENTER, stretch=False)
            self._tree.column("Sail", width=80, anchor=tk.CENTER, stretch=False)
            self._tree.column("Name", width=160, stretch=True)
            self._tree.column("Division/Rig", width=110, stretch=False)
            self._tree.column("Laps", width=50, anchor=tk.CENTER, stretch=False)
            self._tree.column("Letter Score", width=90, anchor=tk.CENTER, stretch=False)
            self._tree.column("Notes", width=200, stretch=True)

            self._configure_tree_tags()

            vsb = ttk.Scrollbar(
                table_frame, orient=tk.VERTICAL, command=self._tree.yview
            )
            self._tree.configure(yscrollcommand=vsb.set)
            self._tree.grid(row=0, column=0, sticky=tk.NSEW)
            vsb.grid(row=0, column=1, sticky=tk.NS)

            # Legend
            legend_frame = ttk.LabelFrame(main_frame, text="Color Key", padding=6)
            legend_frame.grid(row=0, column=1, sticky=tk.N, padx=(8, 0))
            self._build_legend(legend_frame)

            # --- Table operation buttons ---
            ops_frame = ttk.Frame(self)
            ops_frame.grid(row=2, column=0, sticky=tk.EW, padx=8, pady=2)

            ttk.Button(ops_frame, text="Delete Row", command=self._on_delete_row).pack(
                side=tk.LEFT, padx=2
            )
            ttk.Button(
                ops_frame, text="Insert Before", command=self._on_insert_before
            ).pack(side=tk.LEFT, padx=2)
            ttk.Button(
                ops_frame, text="Edit Sail Number", command=self._on_edit_sail
            ).pack(side=tk.LEFT, padx=2)
            ttk.Button(
                ops_frame, text="Set Letter Score", command=self._on_set_letter_score
            ).pack(side=tk.LEFT, padx=2)
            ttk.Button(
                ops_frame,
                text="Clear Letter Score",
                command=self._on_clear_letter_score,
            ).pack(side=tk.LEFT, padx=2)

            # --- Warnings area ---
            warnings_frame = ttk.LabelFrame(self, text="Warnings", padding=4)
            warnings_frame.grid(row=3, column=0, sticky=tk.EW, padx=8, pady=4)

            self._warnings_label = ttk.Label(
                warnings_frame,
                text="",
                foreground="#AA5500",
                wraplength=700,
                justify=tk.LEFT,
            )
            self._warnings_label.pack(fill=tk.X)

        def _build_legend(self, parent: tk.Widget) -> None:
            """Build the color key legend inside *parent*.

            Args:
                parent: Frame to populate with legend rows.
            """
            legend_items = [
                ("0 laps (finish only)", _FINISH_ONLY_BG, _FINISH_ONLY_FG),
                ("1 lap", BG_COLORS[0], TEXT_COLORS[0]),
                ("2 laps", BG_COLORS[1], TEXT_COLORS[1]),
                ("3 laps", BG_COLORS[2], TEXT_COLORS[2]),
                ("4 laps", BG_COLORS[3], TEXT_COLORS[3]),
                ("5+ laps", BG_COLORS[4], TEXT_COLORS[4]),
                ("Duplicate (first)", _DUP_FIRST_BG, _DUP_FIRST_FG),
            ]
            for row_idx, (label, bg, fg) in enumerate(legend_items):
                swatch = tk.Label(
                    parent,
                    text="  ■  ",
                    background=bg,
                    foreground=fg,
                    relief=tk.SOLID,
                    bd=1,
                )
                swatch.grid(row=row_idx, column=0, padx=(0, 4), pady=2, sticky=tk.W)
                ttk.Label(parent, text=label).grid(row=row_idx, column=1, sticky=tk.W)

        def _configure_tree_tags(self) -> None:
            """Configure Treeview color tags for all tiers and special rows."""
            self._tree.tag_configure(
                "tier0", background=_FINISH_ONLY_BG, foreground=_FINISH_ONLY_FG
            )
            for i, (bg, fg) in enumerate(zip(BG_COLORS, TEXT_COLORS)):
                self._tree.tag_configure(f"tier{i + 1}", background=bg, foreground=fg)
            self._tree.tag_configure(
                "dup_first",
                background=_DUP_FIRST_BG,
                foreground=_DUP_FIRST_FG,
            )

        # ------------------------------------------------------------------
        # Session lifecycle
        # ------------------------------------------------------------------

        def set_session(self, auto_save: "AutoSaveSession") -> None:
            """Update the active session and refresh all UI elements.

            Args:
                auto_save: The
                    :class:`~waszp_gp_scorer.session.AutoSaveSession` to use
                    for all data operations.
            """
            self._auto_save = auto_save
            session = auto_save.session

            self._competitor_map = {c.sail_number: c for c in session.competitors}
            self._all_sail_numbers = [c.sail_number for c in session.competitors]

            self._combobox._all_sail_numbers = self._all_sail_numbers
            self._combobox.update_green_fleet(set(session.green_fleet))

            self._refresh_table()
            self._warnings_label.configure(text="")

        # ------------------------------------------------------------------
        # Table helpers
        # ------------------------------------------------------------------

        def _refresh_table(self) -> None:
            """Rebuild the Treeview from the current session finish entries."""
            for child in self._tree.get_children():
                self._tree.delete(child)

            if self._auto_save is None:
                return

            session = self._auto_save.session
            entries = session.finish_entries
            gate_roundings = session.gate_roundings

            # Gate rounding counts per boat.
            gate_counts: dict[str, int] = {}
            for r in gate_roundings:
                gate_counts[r.sail_number] = gate_counts.get(r.sail_number, 0) + 1

            # Identify first occurrences of duplicated sail numbers.
            seen: dict[str, int] = {}
            duplicate_first_indices: set[int] = set()
            for i, fe in enumerate(entries):
                sn = fe.sail_number
                if sn in seen:
                    duplicate_first_indices.add(seen[sn])
                else:
                    seen[sn] = i

            for i, fe in enumerate(entries):
                tier = gate_counts.get(fe.sail_number, 0)
                tier_idx = min(tier, 5)  # clamp to 0–5

                if i in duplicate_first_indices:
                    tag = "dup_first"
                    notes = "duplicate (first occurrence)"
                else:
                    tag = f"tier{tier_idx}"
                    notes = (
                        "finish only"
                        if (
                            fe.sail_number not in gate_counts
                            and fe.letter_score is None
                        )
                        else ""
                    )

                competitor = self._competitor_map.get(fe.sail_number)
                name = competitor.name if competitor else ""
                division = competitor.division if competitor else ""
                rig = competitor.rig_size if competitor else ""
                div_rig = f"{division}/{rig}" if division and rig else (division or rig)
                laps_str = str(tier) if tier > 0 else ""

                self._tree.insert(
                    "",
                    tk.END,
                    iid=f"row_{i}",
                    values=(
                        fe.position,
                        fe.sail_number,
                        name,
                        div_rig,
                        laps_str,
                        fe.letter_score or "",
                        notes,
                    ),
                    tags=(tag,),
                )

        def _get_selected_data_index(self) -> "Optional[int]":
            """Return the 0-based data index of the selected Treeview row.

            Returns:
                The integer index, or ``None`` if nothing valid is selected.
            """
            sel = self._tree.selection()
            if not sel:
                return None
            iid = sel[0]
            if not iid.startswith("row_"):
                return None
            try:
                return int(iid[4:])
            except ValueError:
                return None

        # ------------------------------------------------------------------
        # Validation helpers
        # ------------------------------------------------------------------

        def _show_entry_warnings(self, sail_number: str) -> None:
            """Validate *sail_number* as a new finish entry and display results.

            Args:
                sail_number: Sail number about to be entered.
            """
            if self._auto_save is None:
                return
            session = self._auto_save.session

            warnings: list[ValidatorWarning] = list(
                validate_finish_entry(
                    sail_number=sail_number,
                    competitors=session.competitors,
                    green_fleet=session.green_fleet,
                    existing_finish_entries=session.finish_entries,
                )
            )

            # Finish-only warning: boat not on gate list and no letter score.
            gate_sails: set[str] = {r.sail_number for r in session.gate_roundings}
            if sail_number not in gate_sails:
                warnings.append(FinishOnlyWarning(sail_number=sail_number))

            self._display_warnings(warnings)

        def _display_warnings(self, warnings: "list[ValidatorWarning]") -> None:
            """Render *warnings* into the warnings label.

            Args:
                warnings: List of warning objects to render.
            """
            if not warnings:
                self._warnings_label.configure(text="")
                return
            parts: list[str] = []
            for w in warnings:
                if isinstance(w, GreenFleetEntryWarning):
                    parts.append(f"\u26a0 {w.sail_number} is in the Green Fleet.")
                elif isinstance(w, UnknownSailNumberWarning):
                    parts.append(
                        f"\u26a0 {w.sail_number} is not a registered competitor."
                    )
                elif isinstance(w, DuplicateFinishEntryWarning):
                    pos_str = ", ".join(str(p) for p in w.positions)
                    parts.append(
                        f"\u26a0 Duplicate finish entry: {w.sail_number}"
                        f" at positions {pos_str}."
                    )
                elif isinstance(w, FinishOnlyWarning):
                    parts.append(
                        f"\u26a0 {w.sail_number} is on the finish list"
                        " but has no gate roundings (finish-only)."
                    )
                elif isinstance(w, LetterScoreConflictWarning):
                    parts.append(
                        f"\u26a0 {w.sail_number} has letter score {w.letter_score}"
                        f" but also appears on the gate list"
                        f" ({w.gate_roundings} rounding(s))."
                        " The letter score will be overridden."
                    )
                else:
                    parts.append(f"\u26a0 {w!r}")
            self._warnings_label.configure(text="\n".join(parts))

        # ------------------------------------------------------------------
        # Event handlers
        # ------------------------------------------------------------------

        def _on_add_entry(self, sail_number: "Optional[str]" = None) -> None:
            """Add a finish entry for *sail_number* (or the combobox value).

            Args:
                sail_number: Sail number to add.  If ``None``, reads from the
                    combobox.
            """
            if self._auto_save is None:
                messagebox.showwarning(
                    "No session", "Load a CSV and complete setup first."
                )
                return

            sn = sail_number if sail_number is not None else self._combobox.get_value()
            if not sn:
                return

            # Validate — warnings are informational, entry is still added.
            self._show_entry_warnings(sn)

            session = self._auto_save.session
            new_position = len(session.finish_entries) + 1
            entry = _FinishEntry(position=new_position, sail_number=sn)
            self._auto_save.add_finish_entry(entry)

            self._combobox._var.set("")
            self._refresh_table()
            self._combobox.focus_set()

        def _on_delete_row(self) -> None:
            """Delete the currently selected finish entry row."""
            if self._auto_save is None:
                return
            idx = self._get_selected_data_index()
            if idx is None:
                messagebox.showinfo("No row selected", "Please select a row to delete.")
                return
            self._auto_save.remove_finish_entry(idx)
            self._refresh_table()

        def _on_insert_before(self) -> None:
            """Insert a new finish entry before the selected row."""
            if self._auto_save is None:
                return
            idx = self._get_selected_data_index()
            if idx is None:
                messagebox.showinfo(
                    "No row selected", "Please select a row to insert before."
                )
                return

            dialog = _SailPickerDialog(
                self,
                self._all_sail_numbers,
                set(self._auto_save.session.green_fleet),
                title="Insert Before Row",
            )
            self.wait_window(dialog)
            if dialog.result:
                self._auto_save.insert_finish_entry(idx, dialog.result)
                self._refresh_table()

        def _on_edit_sail(self) -> None:
            """Edit the sail number of the selected finish entry row."""
            if self._auto_save is None:
                return
            idx = self._get_selected_data_index()
            if idx is None:
                messagebox.showinfo("No row selected", "Please select a row to edit.")
                return

            dialog = _SailPickerDialog(
                self,
                self._all_sail_numbers,
                set(self._auto_save.session.green_fleet),
                title="Edit Sail Number",
            )
            self.wait_window(dialog)
            if dialog.result:
                self._auto_save.replace_finish_entry_sail(idx, dialog.result)
                self._refresh_table()

        def _on_set_letter_score(self) -> None:
            """Set a letter score for the selected finish entry row."""
            if self._auto_save is None:
                return
            idx = self._get_selected_data_index()
            if idx is None:
                messagebox.showinfo(
                    "No row selected",
                    "Please select a row to set a letter score.",
                )
                return

            entries = self._auto_save.session.finish_entries
            current = entries[idx].letter_score or ""
            dialog = _LetterScoreDialog(self, current=current, title="Set Letter Score")
            self.wait_window(dialog)
            if dialog.result:
                self._auto_save.set_finish_entry_letter_score(idx, dialog.result)

                # Warn on DNS/DNC/DNF conflict with gate list.
                session = self._auto_save.session
                fe = session.finish_entries[idx]
                gate_counts: dict[str, int] = {}
                for r in session.gate_roundings:
                    gate_counts[r.sail_number] = gate_counts.get(r.sail_number, 0) + 1
                warn_list: list[ValidatorWarning] = []
                if (
                    fe.letter_score in {"DNS", "DNC", "DNF"}
                    and fe.sail_number in gate_counts
                ):
                    warn_list.append(
                        LetterScoreConflictWarning(
                            sail_number=fe.sail_number,
                            letter_score=fe.letter_score,
                            gate_roundings=gate_counts[fe.sail_number],
                        )
                    )
                self._display_warnings(warn_list)
                self._refresh_table()

        def _on_clear_letter_score(self) -> None:
            """Clear the letter score from the selected finish entry row."""
            if self._auto_save is None:
                return
            idx = self._get_selected_data_index()
            if idx is None:
                messagebox.showinfo(
                    "No row selected",
                    "Please select a row to clear the letter score.",
                )
                return
            self._auto_save.set_finish_entry_letter_score(idx, None)
            self._warnings_label.configure(text="")
            self._refresh_table()

        def _on_csv_upload(self) -> None:
            """Load finish entries from a single-column CSV file."""
            if self._auto_save is None:
                messagebox.showwarning(
                    "No session",
                    "Load a competitor CSV and complete setup first.",
                )
                return

            path_str = filedialog.askopenfilename(
                title="Select finish list CSV",
                filetypes=[
                    ("CSV files", "*.csv"),
                    ("Text files", "*.txt"),
                    ("All files", "*.*"),
                ],
            )
            if not path_str:
                return

            try:
                content = Path(path_str).read_text(encoding="utf-8")
            except OSError as exc:
                messagebox.showerror("Read error", str(exc))
                return

            sail_numbers = parse_finish_csv(content)
            if not sail_numbers:
                messagebox.showinfo("Empty file", "No sail numbers found in the file.")
                return

            session = self._auto_save.session
            for sn in sail_numbers:
                new_position = len(session.finish_entries) + 1
                entry = _FinishEntry(position=new_position, sail_number=sn)
                self._auto_save.add_finish_entry(entry)

            self._refresh_table()

except ImportError:
    pass

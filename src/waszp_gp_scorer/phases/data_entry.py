"""Gate rounding data entry phase for the WASZP GP Scorer.

The **pure business-logic helpers** listed below have no :mod:`tkinter`
dependency and are always importable.  The widget class
(:class:`GateRoundingPhase`) is only defined when :mod:`tkinter` is available.

Pure helpers
------------
- :data:`BG_COLORS` — pastel background colors for rounding tiers 1–5+
- :data:`TEXT_COLORS` — text colors for rounding tiers 1–5+
- :func:`get_bg_color` — background hex color for a 1-based tier
- :func:`get_text_color` — text hex color for a 1-based tier
- :func:`rounding_tier` — 1-based tier of a rounding at a given index
- :func:`compute_tiers` — list of tiers for all entries in a gate log
- :func:`parse_gate_csv` — parse a single-column CSV into a sail number list
"""

from __future__ import annotations

from waszp_gp_scorer.models import GateRounding

# ---------------------------------------------------------------------------
# Color constants
# ---------------------------------------------------------------------------

#: Background colors for rounding tiers 1 through 5+ (index 0 = tier 1).
BG_COLORS: list[str] = [
    "#FFFFFF",  # tier 1: white
    "#66D9FF",  # tier 2: light cyan
    "#CCFF66",  # tier 3: light green
    "#FFFF66",  # tier 4: yellow
    "#FF80BF",  # tier 5+: pink
]

#: Text colors for rounding tiers 1 through 5+ (index 0 = tier 1).
TEXT_COLORS: list[str] = [
    "#1C1C1E",  # tier 1: near-black
    "#0088AA",  # tier 2: dark cyan
    "#5A9900",  # tier 3: dark green
    "#9E9E00",  # tier 4: dark yellow
    "#AA0055",  # tier 5+: dark pink
]

# Lighter versions for after-window entries.
_AFTER_BG_COLORS: list[str] = [
    "#F5F5F5",  # tier 1 after
    "#B3ECFF",  # tier 2 after
    "#E6FFB3",  # tier 3 after
    "#FFFFB3",  # tier 4 after
    "#FFB3D9",  # tier 5+ after
]

_AFTER_TEXT_COLORS: list[str] = [
    "#888888",  # tier 1 after
    "#66AACC",  # tier 2 after
    "#88AA44",  # tier 3 after
    "#AAAA44",  # tier 4 after
    "#CC4488",  # tier 5+ after
]

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def get_bg_color(tier: int) -> str:
    """Return the background hex color for *tier* (1-based).

    Tier 1 is white (first rounding).  Tiers beyond 5 return the tier-5 color.
    Invalid inputs below 1 are clamped to tier 1.

    Args:
        tier: 1-based rounding tier (1 = first rounding by this boat).

    Returns:
        A hex color string (e.g. ``"#FFFFFF"``).
    """
    idx = max(0, min(tier - 1, len(BG_COLORS) - 1))
    return BG_COLORS[idx]


def get_text_color(tier: int) -> str:
    """Return the text hex color for *tier* (1-based).

    Tier 1 is near-black.  Tiers beyond 5 return the tier-5 color.
    Invalid inputs below 1 are clamped to tier 1.

    Args:
        tier: 1-based rounding tier.

    Returns:
        A hex color string (e.g. ``"#1C1C1E"``).
    """
    idx = max(0, min(tier - 1, len(TEXT_COLORS) - 1))
    return TEXT_COLORS[idx]


def rounding_tier(
    sail_number: str,
    roundings: list[GateRounding],
    entry_index: int,
) -> int:
    """Return the 1-based tier for the rounding at *entry_index*.

    The tier is the count of times *sail_number* has appeared in *roundings*
    up to and including *entry_index*.  Returns 0 if *entry_index* is beyond
    the end of *roundings*.

    Args:
        sail_number: The sail number to count occurrences of.
        roundings: The full ordered gate rounding list.
        entry_index: 0-based index of the entry whose tier to return.

    Returns:
        A non-negative integer (1 = first rounding, 2 = second, ...).
    """
    count = 0
    for i, rounding in enumerate(roundings):
        if rounding.sail_number == sail_number:
            count += 1
        if i == entry_index:
            return count
    return count


def compute_tiers(roundings: list[GateRounding]) -> list[int]:
    """Return a list of 1-based tiers for every entry in *roundings*.

    The i-th element gives the tier of ``roundings[i]``, i.e., how many
    times that sail number has appeared up to and including index i.

    Args:
        roundings: Ordered list of gate rounding entries.

    Returns:
        A list of positive integers the same length as *roundings*.
    """
    tiers: list[int] = []
    counts: dict[str, int] = {}
    for rounding in roundings:
        sn = rounding.sail_number
        counts[sn] = counts.get(sn, 0) + 1
        tiers.append(counts[sn])
    return tiers


def parse_gate_csv(content: str) -> list[str]:
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
        FinishLineConfig,
    )
    from waszp_gp_scorer.session import AutoSaveSession
    from waszp_gp_scorer.validator import (
        ConsecutiveDuplicateWarning,
        ExcessRoundingsWarning,
        GreenFleetEntryWarning,
        UnknownSailNumberWarning,
        ValidatorWarning,
        validate_gate_rounding,
    )
    from waszp_gp_scorer.widgets.sail_combobox import SailCombobox

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
            self.result: Optional[str] = None
            self._build_ui(all_sail_numbers, green_fleet)

        def _build_ui(self, all_sail_numbers: list[str], green_fleet: set[str]) -> None:
            """Construct dialog widgets."""
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

    class GateRoundingPhase(ttk.Frame):
        """Gate rounding data entry phase.

        Provides a live-updating table of gate roundings with:

        - Autocomplete sail number entry via
          :class:`~waszp_gp_scorer.widgets.sail_combobox.SailCombobox`
        - Tab/Enter to confirm and advance to the next entry
        - Background and text color highlighting per rounding tier
        - Retroactive color update when a sail number rounds again
        - Color key legend
        - Delete, insert-before, and edit-sail operations on any row
        - Finishing Window Opened marker with visual divider
        - Entries after the marker shown in lighter style with annotation
        - Inline validation warnings (consecutive duplicate, Green Fleet,
          unknown sail number, excess roundings)
        - CSV upload for a pre-recorded single-column gate list

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
            """Construct all widgets for the gate rounding phase."""
            self.columnconfigure(0, weight=1)

            # --- Entry form ---
            entry_frame = ttk.LabelFrame(self, text="Add Gate Rounding", padding=6)
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
                entry_frame, text="Upload Gate CSV…", command=self._on_csv_upload
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

            cols = ("#", "Sail", "Name", "Division/Rig", "Notes")
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
            self._tree.column("Notes", width=180, stretch=True)

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

            # --- Finishing window controls ---
            win_frame = ttk.Frame(self)
            win_frame.grid(row=3, column=0, sticky=tk.EW, padx=8, pady=2)

            self._window_btn = ttk.Button(
                win_frame,
                text="Finishing Window Opened",
                command=self._on_finishing_window,
            )
            self._window_btn.pack(side=tk.LEFT, padx=2)

            self._remove_marker_btn = ttk.Button(
                win_frame,
                text="Remove Marker",
                command=self._on_remove_marker,
                state=tk.DISABLED,
            )
            self._remove_marker_btn.pack(side=tk.LEFT, padx=2)

            # --- Warnings area ---
            warnings_frame = ttk.LabelFrame(self, text="Warnings", padding=4)
            warnings_frame.grid(row=4, column=0, sticky=tk.EW, padx=8, pady=4)

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
                ("1st rounding", BG_COLORS[0], TEXT_COLORS[0]),
                ("2nd rounding", BG_COLORS[1], TEXT_COLORS[1]),
                ("3rd rounding", BG_COLORS[2], TEXT_COLORS[2]),
                ("4th rounding", BG_COLORS[3], TEXT_COLORS[3]),
                ("5th+ rounding", BG_COLORS[4], TEXT_COLORS[4]),
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
            for i, (bg, fg) in enumerate(zip(BG_COLORS, TEXT_COLORS)):
                self._tree.tag_configure(f"tier{i + 1}", background=bg, foreground=fg)
            for i, (bg, fg) in enumerate(zip(_AFTER_BG_COLORS, _AFTER_TEXT_COLORS)):
                self._tree.tag_configure(
                    f"tier{i + 1}_after", background=bg, foreground=fg
                )
            self._tree.tag_configure(
                "marker",
                background="#888888",
                foreground="#FFFFFF",
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
            self._refresh_marker_btn()
            self._warnings_label.configure(text="")

        # ------------------------------------------------------------------
        # Table helpers
        # ------------------------------------------------------------------

        def _refresh_table(self) -> None:
            """Rebuild the Treeview from the current session gate roundings."""
            for child in self._tree.get_children():
                self._tree.delete(child)

            if self._auto_save is None:
                return

            session = self._auto_save.session
            roundings = session.gate_roundings
            marker_pos = session.finish_window_marker_position
            tiers = compute_tiers(roundings)

            marker_inserted = False

            for i, rounding in enumerate(roundings):
                tier = tiers[i]
                is_after = marker_pos is not None and i > marker_pos

                # Insert marker divider before the first after-window entry.
                if not marker_inserted and marker_pos is not None and i > marker_pos:
                    self._tree.insert(
                        "",
                        tk.END,
                        iid="__marker__",
                        values=("", "—", "Finishing Window Opened", "", ""),
                        tags=("marker",),
                    )
                    marker_inserted = True

                competitor = self._competitor_map.get(rounding.sail_number)
                name = competitor.name if competitor else ""
                division = competitor.division if competitor else ""
                rig = competitor.rig_size if competitor else ""
                div_rig = f"{division}/{rig}" if division and rig else (division or rig)
                notes = "after finishing window" if is_after else ""

                tier_idx = min(tier, 5)
                tag = f"tier{tier_idx}_after" if is_after else f"tier{tier_idx}"

                self._tree.insert(
                    "",
                    tk.END,
                    iid=f"row_{i}",
                    values=(
                        rounding.position,
                        rounding.sail_number,
                        name,
                        div_rig,
                        notes,
                    ),
                    tags=(tag,),
                )

            # If marker is set but all entries are pre-window (or no entries),
            # append the marker divider at the end.
            if marker_pos is not None and not marker_inserted:
                self._tree.insert(
                    "",
                    tk.END,
                    iid="__marker__",
                    values=("", "—", "Finishing Window Opened", "", ""),
                    tags=("marker",),
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
            if iid == "__marker__" or not iid.startswith("row_"):
                return None
            try:
                return int(iid[4:])
            except ValueError:
                return None

        # ------------------------------------------------------------------
        # Marker helpers
        # ------------------------------------------------------------------

        def _refresh_marker_btn(self) -> None:
            """Enable or disable the remove-marker button based on session state."""
            if self._auto_save is None:
                return
            has_marker = (
                self._auto_save.session.finish_window_marker_position is not None
            )
            self._remove_marker_btn.configure(
                state=tk.NORMAL if has_marker else tk.DISABLED
            )

        # ------------------------------------------------------------------
        # Validation helpers
        # ------------------------------------------------------------------

        def _show_entry_warnings(self, sail_number: str) -> None:
            """Validate *sail_number* as a new gate rounding and display results.

            Args:
                sail_number: Sail number about to be entered.
            """
            if self._auto_save is None:
                return
            session = self._auto_save.session
            warnings = validate_gate_rounding(
                sail_number=sail_number,
                competitors=session.competitors,
                green_fleet=session.green_fleet,
                existing_roundings=session.gate_roundings,
                required_laps=session.num_laps,
                finish_line_config=session.finish_line_config,
            )
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
                elif isinstance(w, ConsecutiveDuplicateWarning):
                    parts.append(
                        f"\u26a0 Consecutive duplicate: {w.sail_number}"
                        f" at position {w.position}."
                    )
                elif isinstance(w, ExcessRoundingsWarning):
                    parts.append(
                        f"\u26a0 Excess roundings: {w.sail_number} has"
                        f" {w.raw_count} roundings (cap: {w.cap})."
                    )
                else:
                    parts.append(f"\u26a0 {w!r}")
            self._warnings_label.configure(text="\n".join(parts))

        # ------------------------------------------------------------------
        # Event handlers
        # ------------------------------------------------------------------

        def _on_add_entry(self, sail_number: "Optional[str]" = None) -> None:
            """Add a gate rounding for *sail_number* (or the combobox value).

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
            new_position = len(session.gate_roundings) + 1
            rounding = GateRounding(position=new_position, sail_number=sn)
            self._auto_save.add_gate_rounding(rounding)

            self._combobox._var.set("")
            self._refresh_table()
            self._combobox.focus_set()

        def _on_delete_row(self) -> None:
            """Delete the currently selected gate rounding row."""
            if self._auto_save is None:
                return
            idx = self._get_selected_data_index()
            if idx is None:
                messagebox.showinfo("No row selected", "Please select a row to delete.")
                return
            self._auto_save.remove_gate_rounding(idx)
            self._refresh_table()
            self._refresh_marker_btn()

        def _on_insert_before(self) -> None:
            """Insert a new gate rounding before the selected row."""
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
                self._auto_save.insert_gate_rounding(idx, dialog.result)
                self._refresh_table()

        def _on_edit_sail(self) -> None:
            """Edit the sail number of the selected gate rounding row."""
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
                self._auto_save.replace_gate_rounding_sail(idx, dialog.result)
                self._refresh_table()

        def _on_finishing_window(self) -> None:
            """Place the finishing window marker after the current last entry.

            If called when roundings are empty, the marker is placed at -1
            (all future entries will be post-window).  Re-clicking moves the
            marker to the new current end position.
            """
            if self._auto_save is None:
                messagebox.showwarning("No session", "No active session.")
                return
            session = self._auto_save.session
            new_pos = len(session.gate_roundings) - 1  # -1 if empty
            self._auto_save.set_finish_window_marker(new_pos)
            self._refresh_table()
            self._refresh_marker_btn()

        def _on_remove_marker(self) -> None:
            """Remove the finishing window marker."""
            if self._auto_save is None:
                return
            self._auto_save.set_finish_window_marker(None)
            self._refresh_table()
            self._refresh_marker_btn()

        def _on_csv_upload(self) -> None:
            """Load gate roundings from a single-column CSV file."""
            if self._auto_save is None:
                messagebox.showwarning(
                    "No session",
                    "Load a competitor CSV and complete setup first.",
                )
                return

            path_str = filedialog.askopenfilename(
                title="Select gate list CSV",
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

            sail_numbers = parse_gate_csv(content)
            if not sail_numbers:
                messagebox.showinfo("Empty file", "No sail numbers found in the file.")
                return

            session = self._auto_save.session
            for sn in sail_numbers:
                new_position = len(session.gate_roundings) + 1
                rounding = GateRounding(position=new_position, sail_number=sn)
                self._auto_save.add_gate_rounding(rounding)

            self._refresh_table()

        # ------------------------------------------------------------------
        # Public API (called by App)
        # ------------------------------------------------------------------

        def check_can_advance(self) -> bool:
            """Check if it is safe to navigate to the finish list phase.

            For
            :attr:`~waszp_gp_scorer.models.FinishLineConfig.SEPARATE_PIN`
            races, warns if no finishing window marker has been placed.

            Returns:
                ``True`` if navigation should proceed; ``False`` to stay on
                this phase.
            """
            if self._auto_save is None:
                return True
            session = self._auto_save.session
            if (
                session.finish_line_config == FinishLineConfig.SEPARATE_PIN
                and session.finish_window_marker_position is None
            ):
                return messagebox.askyesno(
                    "Missing Finishing Window Marker",
                    "No Finishing Window Opened marker has been placed.\n\n"
                    "This is required for SEPARATE_PIN scoring.\n\n"
                    "Continue to the finish list anyway?",
                )
            return True

except ImportError:
    pass

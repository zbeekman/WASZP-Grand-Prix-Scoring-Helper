"""Setup phase UI for the WASZP GP Scorer application.

The **pure business-logic helpers** listed below have no :mod:`tkinter`
dependency and are always importable.  The widget classes
(:class:`SetupPhase`, :class:`GreenFleetDialog`) are only defined when
:mod:`tkinter` is available.

Pure helpers
------------
- :data:`COURSE_TYPES` — ordered list of valid course type strings
- :data:`BLOCKED_COURSE_TYPES` — course types that block GP scoring
- :func:`get_finish_line_config` — map course type → :class:`FinishLineConfig`
- :func:`get_lap_counting_location` — default lap counting location per course
- :func:`is_blocked_course_type` — whether a course type is unsupported
- :func:`laps_needs_confirmation` — whether a lap count warrants a prompt
"""

from __future__ import annotations

from waszp_gp_scorer.models import FinishLineConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: All supported course type display strings, in menu order.
COURSE_TYPES: list[str] = [
    "Standard WASZP W/L (Gate)",
    "SailGP (Gate)",
    "Sprint BOX (no gate, 1 lap)",
    "Slalom Sprint (no gate, 1 lap)",
]

#: Course types that are incompatible with GP scoring (1-lap / no-gate).
BLOCKED_COURSE_TYPES: frozenset[str] = frozenset(
    {
        "Sprint BOX (no gate, 1 lap)",
        "Slalom Sprint (no gate, 1 lap)",
    }
)

#: Map from course type to the finish line configuration it implies.
_COURSE_FINISH_CONFIG: dict[str, FinishLineConfig] = {
    "SailGP (Gate)": FinishLineConfig.SEPARATE_PIN,
}

#: Default lap counting location by course type (per PRD Data Model Notes).
_COURSE_LAP_LOCATION: dict[str, str] = {
    "Standard WASZP W/L (Gate)": "Leeward gate (2s/2p)",
    "SailGP (Gate)": "Windward gate (1s/1p)",
}

_DEFAULT_LAP_LOCATION: str = "Leeward gate (2s/2p)"

# ---------------------------------------------------------------------------
# Pure business-logic helpers (no tkinter dependency)
# ---------------------------------------------------------------------------


def get_finish_line_config(course_type: str) -> FinishLineConfig:
    """Return the :class:`FinishLineConfig` implied by *course_type*.

    SailGP uses :attr:`FinishLineConfig.SEPARATE_PIN`; all other supported
    course types default to :attr:`FinishLineConfig.FINISH_AT_GATE`.

    Args:
        course_type: One of the :data:`COURSE_TYPES` strings.

    Returns:
        The corresponding :class:`FinishLineConfig` value.
    """
    return _COURSE_FINISH_CONFIG.get(course_type, FinishLineConfig.FINISH_AT_GATE)


def get_lap_counting_location(course_type: str) -> str:
    """Return the default lap counting location description for *course_type*.

    Standard W/L courses default to ``"Leeward gate (2s/2p)"`` per the PRD
    Data Model Notes.  SailGP defaults to ``"Windward gate (1s/1p)"``.
    Unknown or blocked course types fall back to the Standard W/L default.

    Args:
        course_type: One of the :data:`COURSE_TYPES` strings.

    Returns:
        A human-readable location string.
    """
    return _COURSE_LAP_LOCATION.get(course_type, _DEFAULT_LAP_LOCATION)


def is_blocked_course_type(course_type: str) -> bool:
    """Return ``True`` if *course_type* is incompatible with GP scoring.

    Sprint BOX and Slalom Sprint races are single-lap, no-gate formats
    that cannot be scored with the WASZP GP rules.

    Args:
        course_type: A course type string.

    Returns:
        ``True`` when the course type should block progression.
    """
    return course_type in BLOCKED_COURSE_TYPES


def laps_needs_confirmation(num_laps: int) -> bool:
    """Return ``True`` if *num_laps* is large enough to warrant a prompt.

    Values greater than 3 are unusual and should be confirmed by the user
    before proceeding.

    Args:
        num_laps: The proposed number of laps.

    Returns:
        ``True`` when ``num_laps > 3``.
    """
    return num_laps > 3


# ---------------------------------------------------------------------------
# Tkinter-dependent widgets — only defined when tkinter is available
# ---------------------------------------------------------------------------
try:
    import tkinter as tk
    from pathlib import Path
    from tkinter import filedialog, messagebox, ttk
    from typing import Callable, Optional

    from waszp_gp_scorer.csv_loader import load_competitors
    from waszp_gp_scorer.models import RaceSession
    from waszp_gp_scorer.session import AutoSaveSession, session_filename
    from waszp_gp_scorer.widgets.sail_combobox import SailCombobox, filter_sail_numbers

    class GreenFleetDialog(tk.Toplevel):
        """Modal dialog for managing Green Fleet sail number exclusions.

        Shows the current Green Fleet members in a listbox and provides an
        autocomplete entry to add new members. Changes are applied immediately
        to the underlying :class:`AutoSaveSession`.

        Args:
            parent: Parent widget (typically the root :class:`App` window).
            auto_save: The active :class:`AutoSaveSession` to mutate.
        """

        def __init__(self, parent: tk.Widget, auto_save: "AutoSaveSession") -> None:
            super().__init__(parent)
            self.title("Green Fleet Wizard")
            self.resizable(False, False)
            self.grab_set()  # make modal

            self._auto_save = auto_save
            self._build_ui()
            self._refresh_list()

        def _build_ui(self) -> None:
            """Construct the dialog widgets."""
            frm = ttk.Frame(self, padding=12)
            frm.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frm, text="Green Fleet Sail Numbers").grid(
                row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 6)
            )

            self._listbox = tk.Listbox(frm, height=10, width=20, selectmode=tk.SINGLE)
            self._listbox.grid(
                row=1, column=0, columnspan=2, sticky=tk.NSEW, pady=(0, 8)
            )

            ttk.Button(frm, text="Remove Selected", command=self._remove_selected).grid(
                row=2, column=0, columnspan=2, sticky=tk.EW, pady=(0, 8)
            )

            ttk.Label(frm, text="Add sail number:").grid(
                row=3, column=0, sticky=tk.W, padx=(0, 4)
            )

            session = self._auto_save.session
            all_sns = [c.sail_number for c in session.competitors]
            self._combobox = SailCombobox(
                frm,
                all_sail_numbers=all_sns,
                green_fleet=set(session.green_fleet),
                on_confirm=self._add_sail_number,
            )
            self._combobox.grid(row=3, column=1, sticky=tk.EW)

            ttk.Button(frm, text="Add", command=self._add_from_entry).grid(
                row=4, column=1, sticky=tk.E, pady=(4, 0)
            )

            ttk.Button(frm, text="Close", command=self.destroy).grid(
                row=5, column=0, columnspan=2, sticky=tk.EW, pady=(8, 0)
            )

            frm.columnconfigure(1, weight=1)

        def _refresh_list(self) -> None:
            """Repopulate the listbox from the current session green fleet."""
            self._listbox.delete(0, tk.END)
            for sn in sorted(self._auto_save.session.green_fleet):
                self._listbox.insert(tk.END, sn)
            self._combobox.update_green_fleet(set(self._auto_save.session.green_fleet))

        def _add_sail_number(self, sail_number: str) -> None:
            """Add *sail_number* to the green fleet and refresh.

            Args:
                sail_number: A valid sail number from the competitor list.
            """
            self._auto_save.add_to_green_fleet(sail_number)
            self._combobox.configure(textvariable=tk.StringVar())
            self._refresh_list()

        def _add_from_entry(self) -> None:
            """Add the currently typed sail number via the Add button."""
            value = self._combobox.get_value()
            session = self._auto_save.session
            all_sns = [c.sail_number for c in session.competitors]
            allowed = filter_sail_numbers(all_sns, set(session.green_fleet))
            if value in allowed:
                self._add_sail_number(value)
            else:
                messagebox.showwarning(
                    "Invalid sail number",
                    f"{value!r} is not a valid non-Green-Fleet sail number.",
                    parent=self,
                )

        def _remove_selected(self) -> None:
            """Remove the selected sail number from the green fleet."""
            sel = self._listbox.curselection()  # type: ignore[no-untyped-call]
            if not sel:
                return
            sail_number = self._listbox.get(sel[0])
            self._auto_save.remove_from_green_fleet(sail_number)
            self._refresh_list()

    class SetupPhase(ttk.Frame):
        """Setup phase frame: load CSV, configure metadata, manage Green Fleet.

        This frame is the first phase shown by :class:`~waszp_gp_scorer.gui.App`.
        It produces an :class:`~waszp_gp_scorer.session.AutoSaveSession` when
        the scorer completes setup, forwarded to the app via ``on_session_ready``.

        Args:
            parent: Parent widget.
            on_session_ready: Callback invoked with the ready
                :class:`~waszp_gp_scorer.session.AutoSaveSession` when the form
                is valid and the user advances. If ``None``, no callback is fired.
            session_dir: Directory in which to write the auto-save file.
                Defaults to the current working directory.
        """

        def __init__(
            self,
            parent: tk.Widget,
            on_session_ready: "Optional[Callable[[AutoSaveSession], None]]" = None,
            session_dir: "Optional[Path]" = None,
        ) -> None:
            super().__init__(parent)
            self._on_session_ready = on_session_ready
            self._session_dir = session_dir or Path.cwd()
            self._auto_save: "Optional[AutoSaveSession]" = None
            self._build_ui()

        # ------------------------------------------------------------------
        # UI construction
        # ------------------------------------------------------------------

        def _build_ui(self) -> None:
            """Build all widgets for the setup phase."""
            self.columnconfigure(0, weight=1)

            # --- CSV Load Section ---
            csv_frame = ttk.LabelFrame(self, text="Load Competitor CSV", padding=8)
            csv_frame.grid(row=0, column=0, sticky=tk.EW, padx=8, pady=6)
            csv_frame.columnconfigure(0, weight=1)

            self._drop_label = ttk.Label(
                csv_frame,
                text="Drag and drop CSV here, or use the button below.",
                anchor=tk.CENTER,
                relief=tk.SOLID,
                padding=16,
            )
            self._drop_label.grid(row=0, column=0, sticky=tk.EW, pady=(0, 4))

            # Wire up drag-and-drop if tkinterdnd2 is installed.
            try:
                from tkinterdnd2 import DND_FILES

                self._drop_label.drop_target_register(  # type: ignore[attr-defined]
                    DND_FILES
                )
                self._drop_label.dnd_bind(  # type: ignore[attr-defined]
                    "<<Drop>>", self._on_dnd_drop
                )
            except (ImportError, AttributeError):
                pass  # fall back to file picker only

            ttk.Button(csv_frame, text="Browse for CSV…", command=self._pick_csv).grid(
                row=1, column=0, sticky=tk.W
            )

            self._summary_label = ttk.Label(csv_frame, text="", foreground="green")
            self._summary_label.grid(row=2, column=0, sticky=tk.W)

            # --- Metadata Form ---
            meta_frame = ttk.LabelFrame(self, text="Race Metadata", padding=8)
            meta_frame.grid(row=1, column=0, sticky=tk.EW, padx=8, pady=6)
            meta_frame.columnconfigure(1, weight=1)

            fields = [
                ("Event name:", "event_name", ""),
                ("Race number:", "race_number", "1"),
                ("Date (YYYY-MM-DD):", "race_date", ""),
                ("Approx. start time:", "start_time", ""),
                ("Number of laps:", "num_laps", "2"),
            ]
            self._vars: dict[str, tk.StringVar] = {}
            for row_idx, (label, key, default) in enumerate(fields):
                ttk.Label(meta_frame, text=label).grid(
                    row=row_idx, column=0, sticky=tk.W, pady=2, padx=(0, 6)
                )
                var = tk.StringVar(value=default)
                self._vars[key] = var
                ttk.Entry(meta_frame, textvariable=var).grid(
                    row=row_idx, column=1, sticky=tk.EW
                )

            # Course type dropdown
            next_row = len(fields)
            ttk.Label(meta_frame, text="Course type:").grid(
                row=next_row, column=0, sticky=tk.W, pady=2, padx=(0, 6)
            )
            self._course_var = tk.StringVar(value=COURSE_TYPES[0])
            self._course_cb = ttk.Combobox(
                meta_frame,
                textvariable=self._course_var,
                values=COURSE_TYPES,
                state="readonly",
            )
            self._course_cb.grid(row=next_row, column=1, sticky=tk.EW)
            self._course_var.trace_add("write", self._on_course_type_changed)

            # Finish line config dropdown
            next_row += 1
            ttk.Label(meta_frame, text="Finish line config:").grid(
                row=next_row, column=0, sticky=tk.W, pady=2, padx=(0, 6)
            )
            self._finish_config_var = tk.StringVar(
                value=FinishLineConfig.FINISH_AT_GATE.value
            )
            _config_options = [e.value for e in FinishLineConfig]
            self._finish_config_cb = ttk.Combobox(
                meta_frame,
                textvariable=self._finish_config_var,
                values=_config_options,
                state="readonly",
            )
            self._finish_config_cb.grid(row=next_row, column=1, sticky=tk.EW)

            # Lap counting location
            next_row += 1
            ttk.Label(meta_frame, text="Lap counting location:").grid(
                row=next_row, column=0, sticky=tk.W, pady=2, padx=(0, 6)
            )
            self._lap_location_var = tk.StringVar(
                value=get_lap_counting_location(COURSE_TYPES[0])
            )
            ttk.Entry(meta_frame, textvariable=self._lap_location_var).grid(
                row=next_row, column=1, sticky=tk.EW
            )

            # --- Green Fleet Section ---
            gf_frame = ttk.LabelFrame(self, text="Green Fleet", padding=8)
            gf_frame.grid(row=2, column=0, sticky=tk.EW, padx=8, pady=6)

            self._gf_btn = ttk.Button(
                gf_frame,
                text="Manage Green Fleet…",
                command=self._open_green_fleet_wizard,
                state=tk.DISABLED,
            )
            self._gf_btn.pack(side=tk.LEFT)

            self._gf_summary_label = ttk.Label(gf_frame, text="Load a CSV first.")
            self._gf_summary_label.pack(side=tk.LEFT, padx=8)

        # ------------------------------------------------------------------
        # Event handlers
        # ------------------------------------------------------------------

        def _on_dnd_drop(self, event: "tk.Event[tk.Widget]") -> None:
            """Handle a drag-and-drop CSV drop event.

            Args:
                event: The Tk DND event; ``event.data`` contains the file path.
            """
            path_str: str = event.data.strip().strip("{}")  # type: ignore[attr-defined]
            self._load_csv(Path(path_str))

        def _pick_csv(self) -> None:
            """Open a file picker dialog and load the chosen CSV."""
            path_str = filedialog.askopenfilename(
                title="Select competitor CSV",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if path_str:
                self._load_csv(Path(path_str))

        def _load_csv(self, path: Path) -> None:
            """Load competitors from *path* and initialise the session.

            Args:
                path: Filesystem path to the competitor CSV file.
            """
            try:
                competitors, summary = load_competitors(path)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("CSV load error", str(exc))
                return

            session = RaceSession(
                course_type=self._course_var.get(),
                finish_line_config=get_finish_line_config(self._course_var.get()),
                lap_counting_location=self._lap_location_var.get(),
                competitors=competitors,
            )
            save_path = self._session_dir / session_filename(session)
            self._auto_save = AutoSaveSession(session, path=save_path)

            # Build summary text
            rig_parts = ", ".join(
                f"{sz}: {cnt}" for sz, cnt in sorted(summary.rig_size_counts.items())
            )
            div_parts = ", ".join(
                f"{div or 'None'}: {cnt}"
                for div, cnt in sorted(summary.division_counts.items())
            )
            self._summary_label.configure(
                text=(
                    f"{summary.total_competitors} competitors loaded. "
                    f"Rigs — {rig_parts}. Divisions — {div_parts}."
                )
            )

            self._gf_btn.configure(state=tk.NORMAL)
            self._gf_summary_label.configure(text="No Green Fleet members.")

            if self._on_session_ready is not None:
                self._on_session_ready(self._auto_save)

        def _on_course_type_changed(self, *_: object) -> None:
            """React to a course type change in the dropdown."""
            course_type = self._course_var.get()

            if is_blocked_course_type(course_type):
                messagebox.showwarning(
                    "Course type not supported",
                    f"{course_type!r} uses a single-lap, no-gate format which is "
                    "incompatible with GP scoring. Please select a Gate course.",
                )
                # Reset to first valid type
                self._course_var.set(COURSE_TYPES[0])
                return

            # Auto-set finish line config for SailGP
            config = get_finish_line_config(course_type)
            self._finish_config_var.set(config.value)
            if course_type == "SailGP (Gate)":
                self._finish_config_cb.configure(state=tk.DISABLED)
            else:
                self._finish_config_cb.configure(state="readonly")

            # Update lap counting location default
            self._lap_location_var.set(get_lap_counting_location(course_type))

            # Propagate to session if available
            if self._auto_save is not None:
                self._auto_save.update_metadata(
                    course_type=course_type,
                    finish_line_config=config,
                    lap_counting_location=get_lap_counting_location(course_type),
                )

        def _open_green_fleet_wizard(self) -> None:
            """Open the Green Fleet management dialog."""
            if self._auto_save is None:
                return
            dialog = GreenFleetDialog(self, self._auto_save)
            self.wait_window(dialog)
            green_count = len(self._auto_save.session.green_fleet)
            self._gf_summary_label.configure(
                text=(
                    f"{green_count} Green Fleet member(s)."
                    if green_count
                    else "No Green Fleet members."
                )
            )

        # ------------------------------------------------------------------
        # Public API (called by App)
        # ------------------------------------------------------------------

        def commit_metadata(self) -> bool:
            """Validate and commit metadata form values to the session.

            Validates that a CSV has been loaded, the laps count is a positive
            integer, and prompts for confirmation when laps > 3.

            Returns:
                ``True`` if validation passed and the session was updated.
                ``False`` if validation failed or the user cancelled.
            """
            if self._auto_save is None:
                messagebox.showwarning(
                    "No CSV loaded", "Please load a competitor CSV first."
                )
                return False

            try:
                num_laps = int(self._vars["num_laps"].get())
                if num_laps < 1:
                    raise ValueError
            except ValueError:
                messagebox.showerror(
                    "Invalid laps",
                    "Number of laps must be a positive integer.",
                )
                return False

            if laps_needs_confirmation(num_laps):
                ok = messagebox.askyesno(
                    "Unusual lap count",
                    f"{num_laps} laps is larger than the usual maximum of 3.\n\n"
                    "Continue with this lap count?",
                )
                if not ok:
                    return False

            race_number_str = self._vars["race_number"].get()
            try:
                race_number = int(race_number_str)
            except ValueError:
                messagebox.showerror(
                    "Invalid race number", "Race number must be an integer."
                )
                return False

            self._auto_save.update_metadata(
                event_name=self._vars["event_name"].get().strip(),
                race_number=race_number,
                race_date=self._vars["race_date"].get().strip(),
                start_time=self._vars["start_time"].get().strip() or None,
                num_laps=num_laps,
                course_type=self._course_var.get(),
                finish_line_config=FinishLineConfig(self._finish_config_var.get()),
                lap_counting_location=self._lap_location_var.get().strip(),
            )
            return True

        def load_session(self, auto_save: "AutoSaveSession") -> None:
            """Populate the form from a resumed *auto_save* session.

            Called by :class:`~waszp_gp_scorer.gui.App` when resuming a previous
            session on launch.

            Args:
                auto_save: The loaded :class:`AutoSaveSession` to display.
            """
            self._auto_save = auto_save
            session = auto_save.session

            self._vars["event_name"].set(session.event_name)
            self._vars["race_number"].set(str(session.race_number))
            self._vars["race_date"].set(session.race_date)
            self._vars["start_time"].set(session.start_time or "")
            self._vars["num_laps"].set(str(session.num_laps))
            self._course_var.set(session.course_type)
            self._finish_config_var.set(session.finish_line_config.value)
            self._lap_location_var.set(session.lap_counting_location)

            competitor_count = len(session.competitors)
            if competitor_count:
                self._summary_label.configure(
                    text=(
                        f"{competitor_count} competitors loaded "
                        "(from resumed session)."
                    )
                )
                self._gf_btn.configure(state=tk.NORMAL)

            green_count = len(session.green_fleet)
            self._gf_summary_label.configure(
                text=(
                    f"{green_count} Green Fleet member(s)."
                    if green_count
                    else "No Green Fleet members."
                )
            )

except ImportError:
    pass

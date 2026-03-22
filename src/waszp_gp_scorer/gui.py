"""Top-level application shell for the WASZP GP Scorer.

Provides :class:`App`, which hosts all GUI phases and owns the
:class:`~waszp_gp_scorer.session.AutoSaveSession`.  This module requires
:mod:`tkinter`; it will fail to define :class:`App` in headless environments.

Usage::

    from waszp_gp_scorer.gui import App
    app = App()
    app.mainloop()
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Optional

from waszp_gp_scorer.session import AutoSaveSession, load
from waszp_gp_scorer.phases.setup import SetupPhase
from waszp_gp_scorer.phases.data_entry import GateRoundingPhase
from waszp_gp_scorer.phases.finish_entry import FinishListPhase

# ---------------------------------------------------------------------------
# Root window base: use tkinterdnd2 when available for platform DnD support.
# ---------------------------------------------------------------------------
try:
    from tkinterdnd2 import TkinterDnD as _TkinterDnD

    _DND_ROOT: type = _TkinterDnD.Tk
except ImportError:
    _DND_ROOT = tk.Tk


class App(_DND_ROOT):  # type: ignore[misc]
    """Top-level WASZP GP Scorer application window.

    Manages phase navigation (setup → gate rounding → finish → scoring →
    export), owns the :class:`~waszp_gp_scorer.session.AutoSaveSession`, and
    handles exit prompts and resume-on-launch.

    Args:
        session_dir: Directory for auto-save session files.
            Defaults to the current working directory.
    """

    #: Ordered list of phase identifiers.
    PHASES: list[str] = ["setup", "gate_rounding", "finish", "scoring", "export"]

    #: Human-readable titles for each phase.
    PHASE_TITLES: dict[str, str] = {
        "setup": "Setup",
        "gate_rounding": "Gate Rounding Entry",
        "finish": "Finish List Entry",
        "scoring": "Scoring & Results",
        "export": "Export",
    }

    def __init__(self, session_dir: Optional[Path] = None) -> None:
        super().__init__()
        self.title("WASZP GP Scorer")
        self.resizable(True, True)
        self.minsize(900, 640)

        self._session_dir = session_dir or Path.cwd()
        self._auto_save: Optional[AutoSaveSession] = None
        self._current_phase_index: int = 0
        self._has_unexported_results: bool = False

        self._build_ui()
        self._try_resume_session()
        self._show_phase(0)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the navigation bar and content area."""
        # Navigation bar
        nav = tk.Frame(self, bd=1, relief=tk.FLAT)
        nav.pack(side=tk.TOP, fill=tk.X, padx=8, pady=4)

        self._back_btn = tk.Button(nav, text="◀ Back", command=self.go_back, width=10)
        self._back_btn.pack(side=tk.LEFT)

        self._phase_label = tk.Label(
            nav, text="", font=("Helvetica", 13, "bold"), anchor=tk.CENTER
        )
        self._phase_label.pack(side=tk.LEFT, expand=True, fill=tk.X)

        self._next_btn = tk.Button(
            nav, text="Next ▶", command=self.go_forward, width=10
        )
        self._next_btn.pack(side=tk.RIGHT)

        # Content area
        self._content = tk.Frame(self)
        self._content.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Build phase frames
        self._setup_phase = SetupPhase(
            self._content,
            on_session_ready=self._on_session_ready,
            session_dir=self._session_dir,
        )
        self._gate_phase = GateRoundingPhase(self._content)
        self._finish_phase = FinishListPhase(self._content)
        self._phase_frames: dict[str, ttk.Frame] = {
            "setup": self._setup_phase,
            "gate_rounding": self._gate_phase,
            "finish": self._finish_phase,
        }

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def _on_session_ready(self, auto_save: AutoSaveSession) -> None:
        """Receive the configured session from :class:`SetupPhase`.

        Args:
            auto_save: The ready :class:`AutoSaveSession`.
        """
        self._auto_save = auto_save
        self._has_unexported_results = False
        self._gate_phase.set_session(auto_save)
        self._finish_phase.set_session(auto_save)

    def _try_resume_session(self) -> None:
        """Offer to resume the most recent session file if one exists."""
        session_files = sorted(self._session_dir.glob("*_session.json"))
        if not session_files:
            return

        latest = session_files[-1]
        answer = messagebox.askyesno(
            "Resume previous session?",
            f"A previous session file was found:\n{latest.name}\n\nResume it?",
        )
        if not answer:
            return

        try:
            session = load(latest)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Load error", f"Could not load session:\n{exc}")
            return

        auto_save = AutoSaveSession(session, path=latest)
        self._auto_save = auto_save
        self._setup_phase.load_session(auto_save)
        self._gate_phase.set_session(auto_save)
        self._finish_phase.set_session(auto_save)

    # ------------------------------------------------------------------
    # Phase navigation
    # ------------------------------------------------------------------

    def _show_phase(self, index: int) -> None:
        """Show the phase at *index* and update navigation controls.

        Args:
            index: Phase index into :attr:`PHASES`.
        """
        self._current_phase_index = index
        phase_name = self.PHASES[index]
        self._phase_label.configure(
            text=self.PHASE_TITLES.get(phase_name, phase_name.replace("_", " ").title())
        )

        # Hide all phase frames and show the current one.
        for child in self._content.winfo_children():
            child.pack_forget()  # type: ignore[union-attr]

        frame = self._phase_frames.get(phase_name)
        if frame is not None:
            frame.pack(fill=tk.BOTH, expand=True)
        else:
            # Placeholder label for phases not yet implemented.
            lbl = ttk.Label(
                self._content,
                text=(
                    f"[{self.PHASE_TITLES.get(phase_name, phase_name)} "
                    "— coming soon]"
                ),
                anchor=tk.CENTER,
                font=("Helvetica", 14),
            )
            lbl.pack(expand=True)

        self._back_btn.configure(state=tk.NORMAL if index > 0 else tk.DISABLED)
        self._next_btn.configure(
            state=tk.NORMAL if index < len(self.PHASES) - 1 else tk.DISABLED
        )

    def go_forward(self) -> None:
        """Validate the current phase and advance to the next phase."""
        if self._current_phase_index >= len(self.PHASES) - 1:
            return

        # Validate the setup phase before advancing.
        if self._current_phase_index == 0:
            if not self._setup_phase.commit_metadata():
                return

        # Validate the gate rounding phase before advancing to finish list.
        if self._current_phase_index == 1:
            if not self._gate_phase.check_can_advance():
                return

        self._show_phase(self._current_phase_index + 1)

    def go_back(self) -> None:
        """Navigate to the previous phase."""
        if self._current_phase_index > 0:
            self._show_phase(self._current_phase_index - 1)

    # ------------------------------------------------------------------
    # Exit handling
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        """Handle window close: prompt if results have not been exported."""
        if self._has_unexported_results and self._auto_save is not None:
            answer = messagebox.askyesnocancel(
                "Exit without exporting?",
                "The scoring results have not been exported to Excel.\n\n"
                "Your session is auto-saved and can be resumed.\n\n"
                "Exit anyway?",
            )
            if answer is None:
                return  # Cancel — stay open.
        self.destroy()


def main() -> None:
    """Launch the WASZP GP Scorer application."""
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()

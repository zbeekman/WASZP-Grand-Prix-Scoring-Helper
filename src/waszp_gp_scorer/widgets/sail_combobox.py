"""Filtered autocomplete Combobox widget for sail number entry.

Provides :func:`filter_sail_numbers` (a pure, display-free function) and
:class:`SailCombobox`, a :class:`ttk.Combobox` subclass that narrows its
dropdown on each keystroke, excludes Green Fleet sail numbers, validates
the typed value against the allowed set, and fires a callback on Tab/Enter.

:class:`SailCombobox` is only defined when :mod:`tkinter` is available;
:func:`filter_sail_numbers` is always available.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Sequence


def filter_sail_numbers(
    all_sail_numbers: Sequence[str],
    green_fleet: set[str],
    prefix: str = "",
) -> list[str]:
    """Return allowed sail numbers filtered by prefix, excluding green fleet.

    Args:
        all_sail_numbers: Full ordered sequence of all known sail numbers.
        green_fleet: Set of sail numbers to exclude from the result.
        prefix: Optional case-insensitive prefix to narrow the results.

    Returns:
        Sorted list of sail numbers that are not in *green_fleet* and
        start with *prefix* (if given).
    """
    allowed = [sn for sn in all_sail_numbers if sn not in green_fleet]
    if prefix:
        prefix_lower = prefix.lower()
        allowed = [sn for sn in allowed if sn.lower().startswith(prefix_lower)]
    return sorted(allowed)


# ---------------------------------------------------------------------------
# Tkinter-dependent widget — only defined when tkinter is available
# ---------------------------------------------------------------------------
try:
    import tkinter as tk
    from tkinter import ttk

    class SailCombobox(ttk.Combobox):
        """Autocomplete Combobox filtered by keystroke for sail number entry.

        Narrows the dropdown on each keystroke by calling
        :func:`filter_sail_numbers`. Excludes Green Fleet sail numbers.
        Validates the typed value against the allowed set. Tab/Enter confirms
        the value and fires ``on_confirm``. Arrow keys navigate the dropdown
        natively via the standard Combobox behaviour.

        Args:
            parent: Parent widget.
            all_sail_numbers: The full ordered sequence of valid sail numbers.
            green_fleet: Set of sail numbers to exclude from the dropdown.
                Defaults to an empty set.
            on_confirm: Callback invoked with the confirmed sail number when
                Tab or Enter is pressed and the value is valid.
            **kwargs: Additional keyword arguments forwarded to
                :class:`ttk.Combobox`.
        """

        def __init__(
            self,
            parent: tk.Widget,
            all_sail_numbers: Sequence[str],
            green_fleet: Optional[set[str]] = None,
            on_confirm: Optional[Callable[[str], None]] = None,
            **kwargs: Any,
        ) -> None:
            self._all_sail_numbers: list[str] = list(all_sail_numbers)
            self._green_fleet: set[str] = set(green_fleet) if green_fleet else set()
            self._on_confirm = on_confirm

            initial_values = filter_sail_numbers(
                self._all_sail_numbers, self._green_fleet
            )
            super().__init__(parent, values=initial_values, **kwargs)

            self._var: tk.StringVar = tk.StringVar()
            self.configure(textvariable=self._var)
            self._var.trace_add("write", self._on_text_changed)
            self.bind("<Return>", self._on_confirm_key)
            self.bind("<Tab>", self._on_confirm_key)

        # ------------------------------------------------------------------
        # Internal helpers
        # ------------------------------------------------------------------

        def _on_text_changed(self, *_: object) -> None:
            """Update the dropdown values based on the current text input."""
            text = self._var.get()
            filtered = filter_sail_numbers(
                self._all_sail_numbers, self._green_fleet, text
            )
            self.configure(values=filtered)

        def _on_confirm_key(self, _: "tk.Event[SailCombobox]") -> Optional[str]:
            """Confirm the current value if it is in the allowed set.

            Returns ``"break"`` to suppress the default key event behaviour.
            """
            value = self._var.get().strip()
            allowed = filter_sail_numbers(self._all_sail_numbers, self._green_fleet)
            if value in allowed and self._on_confirm is not None:
                self._on_confirm(value)
            return "break"

        # ------------------------------------------------------------------
        # Public API
        # ------------------------------------------------------------------

        def update_green_fleet(self, green_fleet: set[str]) -> None:
            """Refresh the dropdown after the Green Fleet set changes.

            Args:
                green_fleet: The updated set of excluded sail numbers.
            """
            self._green_fleet = set(green_fleet)
            text = self._var.get()
            self.configure(
                values=filter_sail_numbers(
                    self._all_sail_numbers, self._green_fleet, text
                )
            )

        def is_valid(self) -> bool:
            """Return ``True`` if the current value is in the allowed set."""
            value = self._var.get().strip()
            return value in filter_sail_numbers(
                self._all_sail_numbers, self._green_fleet
            )

        def get_value(self) -> str:
            """Return the current stripped text value."""
            return self._var.get().strip()

except ImportError:
    pass

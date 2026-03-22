# WASZP GP Scorer — Product Requirements Document

**Version:** 2.4
**Date:** 2026-03-22
**Author:** Izaak Beekman
**Status:** Draft

---

## Problem Statement

Scoring a WASZP grand prix (GP) finish race by hand is slow, can be error-prone, and cognitively demanding. The scorer must simultaneously manage two independent data sources — a handwritten or voice-memo finish list and a gate list — cross-reference them, apply nuanced lap-count ordering rules, and produce a clean results table, all under time pressure at the event.

The core difficulty is that finish order on the water is not the same as scored order. A boat that sailed more laps finishes ahead of a boat that crossed the line first but sailed fewer laps. Determining who sailed how many laps requires the gate list, and the two lists must be reconciled carefully. Mistakes propagate silently and are hard to spot after the fact.

There is currently no purpose-built tool for this workflow. The WASZP GP Scorer application solves this by digitizing both sheets, validating entries against the registered competitor list in real time, computing GP scoring automatically, and producing a publication-ready Excel file.

---

## Solution

A standalone Python desktop application (macOS and Windows) called **WASZP GP Scorer**. It guides the scorer through a wizard-style workflow:

1. **Setup** — load the competitor CSV, configure event metadata, optionally identify Green Fleet sailors.
2. **Gate Rounding Entry** — type in sail numbers from the gate list voice memo or paper sheet, with live autocomplete and a growing lap-count table that highlights completed laps in pastel colors.
3. **Finish List Entry** — type in the finish order, with lap-count highlighting applied immediately from the gate rounding data already entered.
4. **Scoring** — the app automatically applies SI 13.2.3 GP scoring rules, classifies each boat's finish type, validates the lead-boat rule, and displays a GP Finish Ranking table alongside the original finish order.
5. **Export** — one-click Excel export with multiple sub-tables (overall, per rig size) and full color highlighting.

The app runs without any Python installation on the end-user machine, distributed as a macOS `.app` DMG and a Windows `.exe`.

---

## User Stories

### Setup

1. As a scorer, I want to drag-and-drop a competitor registration CSV onto the app, so that I can quickly load the fleet without navigating file dialogs.
2. As a scorer, I want to browse for the competitor CSV via a file picker, so that I have a fallback if drag-and-drop is unavailable.
3. As a scorer, I want the app to automatically detect and load `Sail Number`, `Sailor Country Code`, `Sailor Name`, and `Sail Size` from the CSV, so that I don't have to configure column mappings.
4. As a scorer, I want the app to also load `Division` (age group), phone, and email fields if present, so that I have full competitor context without extra steps.
5. As a scorer, I want a summary shown after CSV load (N competitors, rig sizes with counts, age divisions with counts), so that I can confirm the right file was loaded.
6. As a scorer, I want a warning if an unrecognized rig size appears in the CSV, so that I can catch data entry errors in the registration file before scoring begins.
7. As a scorer, I want to enter the event name, race number, date, approximate start time, number of laps, course type, and finishing line configuration before data entry, so that all results are correctly labeled.
8. As a scorer, I want the number of laps to default to 2, so that the most common case requires no change.
9. As a scorer, I want a block if I select 1 lap or a no-gate course type (Sprint BOX, Slalom Sprint), so that I am reminded GP scoring does not apply to single-lap races.
10. As a scorer, I want a confirmation prompt if I enter more than 3 laps, so that unusual configurations are flagged before I proceed.
11. As a scorer, I want to select from course types — Standard WASZP W/L (Gate), SailGP (Gate), Sprint BOX (no gate, 1 lap), Slalom Sprint (no gate, 1 lap) — so that the app adapts its workflow to the actual course sailed.
12. As a scorer, I want to select the finishing line configuration — "Finishing line at gate (mark 2p)" or "Finishing line with separate pin" — so that the app uses the correct lap-counting formula and gate recording behavior.
13. As a scorer, I want the app to automatically set "Finishing line with separate pin" and disable the option when SailGP course is selected, so that the correct configuration is enforced.
14. As a scorer, I want "Finishing line at gate (mark 2p)" to be the default finishing line configuration for W/L courses, so that the most common configuration requires no change.
15. As a scorer, I want to specify the lap counting location — which gate or marks the human counter is stationed at — so that this information is recorded in the session and exported with the results. See Data Model Notes for defaults by course type.
16. As a scorer, I want an optional "Enter Green Fleet Sail Numbers" wizard, so that I can exclude Green Fleet competitors who race separately from all scoring and autocomplete.
17. As a scorer, I want to use the same autocomplete mechanism in the Green Fleet wizard as in data entry, so that entering Green Fleet numbers is fast and consistent.
18. As a scorer, I want the Green Fleet list to be saved in the session file, so that if I resume a session those exclusions are preserved.
19. As a scorer, I want the Green Fleet wizard to be reopenable at any time, so that I can add or remove sailors if I made a mistake.

### Gate Rounding Entry

20. As a scorer, I want to enter gate rounding sail numbers one at a time using a filtered autocomplete combobox, so that entry is fast and validated as I type.
21. As a scorer, I want the autocomplete dropdown to narrow as I type each digit of the sail number, so that I can find the right boat quickly in a large fleet.
22. As a scorer, I want Tab or Enter to confirm a sail number and advance to the next entry row, so that I can enter a long list without touching the mouse.
23. As a scorer, I want the gate rounding table to populate live as I enter each sail number, so that I have a running view of the data I have entered.
24. As a scorer, I want the second and subsequent gate roundings for a sail number to be highlighted in a distinct pastel background color, so that I can see at a glance which boats have completed laps.
25. As a scorer, I want different background colors for each lap tier (1st rounding = white, 2nd = blue, 3rd = green, 4th = yellow, 5th+ = pink), so that multi-lap completions are visually distinguishable. See Highlighting Color Scheme for exact hex values.
26. As a scorer, I want the text color of every row for a given sail number to update retroactively whenever that boat gains a new rounding, so that text color reflects the boat's current total lap count across all rows for that boat. See Highlighting Color Scheme for exact hex values and color pairing rationale.
27. As a scorer, I want a color key displayed alongside the gate rounding table showing both the background color (which rounding this row represents) and the text color (boat's current total lap count), so that I can quickly reference what each color signal means.
28. As a scorer, I want a warning if the same sail number appears twice in a row with no other boats in between, so that likely recording errors are caught immediately.
29. As a scorer, I want a warning and annotation if a boat appears to have completed more laps than the number configured in setup, so that data entry errors are flagged.
30. As a scorer, I want to delete any row from the gate rounding table, so that I can correct mistakes.
31. As a scorer, I want to insert a row at any position in the gate rounding table, so that I can add a missed rounding in the correct order.
32. As a scorer, I want to edit the sail number in any gate rounding row, so that I can fix a typo after confirming.
33. As a scorer, I want other fields (sailor name, rig size, division, country) to auto-populate when I edit a sail number, so that I don't have to re-enter metadata.
34. As a scorer, I want a warning if I enter a Green Fleet sail number in the gate list, so that I am reminded that boat races separately and the entry will be excluded.
35. As a scorer, I want a warning if I enter a sail number not found in the competitor CSV, so that I can confirm before adding an unregistered boat.
36. As a scorer, I want an optional CSV upload for the gate list (single column of sail numbers), so that if I have a digitally transcribed voice memo I can upload it directly instead of typing.
37. As a scorer, I want to be able to use the arrow keys to select the sail number from the autocomplete dropdown, so that I can keep my hands on the keyboard for faster entry.
38. As a scorer, I want a prominent "Finishing Window Opened" button available during gate rounding entry, so that I can mark the point in the gate log where the finishing window opened. This affects tier ordering for Gate finish boats under "Finishing line with separate pin" and provides an audit trail under "Finishing line at gate". When two fleets share a course, the scorer should wait until both fleets' lead boats have finished before pressing this button (see Authoritative Rules Reference for SI 13.2.1 details).
39. As a scorer, I want gate rounding entries after the Finishing Window Opened marker shown below a visible divider, rendered in a lighter style with an "after finishing window" annotation, so that I can clearly distinguish pre-window roundings from window-phase roundings.
40. As a scorer, I want to be able to delete and re-place the Finishing Window Opened marker, so that I can correct its position if I placed it too early or too late.
41. As a scorer, when "Finishing line with separate pin" is configured and I navigate from gate rounding entry to the finish list without having placed the Finishing Window Opened marker, I want a warning prompt, so that I don't proceed without marking the window boundary.
42. As a scorer, when "Finishing line at gate (mark 2p)" is configured, I want the Finishing Window Opened marker to be optional with no warning if absent, so that scorers who do not have a separate gate counter are not impeded.

### Finish List Entry

43. As a scorer, I want to enter finish list sail numbers using the same filtered autocomplete combobox as gate roundings, so that the experience is consistent.
44. As a scorer, I want lap-count highlighting applied to the finish list live as I type, drawn from the gate rounding data already entered, so that I can see each boat's lap count without switching tabs.
45. As a scorer, I want an optional CSV upload for the finish list (single column of sail numbers), so that if Vakaros Race Sense or some other tracking system produces a digital finish list I can load it directly.
46. As a scorer, I want a warning if a sail number appears more than once on the finish list, so that I can distinguish between erroneous duplicate entries or sailors intentionally recrossing the finishing line to cure a rule infraction.
47. As a scorer, I want to keep the first occurrence of a duplicate finish entry in a light grey for audit purposes, but use the last crossing for scoring purposes, so that re-crossings are handled correctly per the rules.
48. As a scorer, I want a warning if a sail number is on the finish list but not the gate list, so that "finish only" boats are flagged as likely recording errors.
49. As a scorer, I want each finish list row to have an optional letter score dropdown, so that I can assign DNS, DNC, DNF, DSQ, DNE, OCS, UFD, BFD, ZFP, NSC, RET, SCP, RDG, or DPI without leaving the row.
50. As a scorer, I want a warning if I assign DNS, DNC, or DNF to a boat that also appears on the gate list, so that I am reminded the boat should be reclassified as a Gate finish per SI 13.2.3(i).
51. As a scorer, I want the same editing capabilities (delete, insert, edit sail number) on the finish list as on the gate list, so that corrections are equally easy.
52. As a scorer, I want a warning if I enter a Green Fleet sail number on the finish list, so that I am reminded the entry will be excluded from scoring.

### Scoring & Results Display

53. As a scorer, I want scoring to recalculate automatically whenever either sheet is modified, so that the results are always up to date without manual triggering.
54. As a scorer, I want to see each boat classified with a finish type, so that I can understand why each boat is placed where it is:
    - **Standard** — completed required laps and crossed the finishing line.
    - **GP** — crossed the finishing line with fewer than required laps.
    - **Gate** — completed ≥ 1 lap at the gate but never crossed the finishing line (the intended GP outcome for back-of-fleet boats per SI 13.2.3(i)).
    - **Finish Only** — on the finish list but absent from the gate list; assumed 1 lap, probably a recording error.
    - **Error: No Recorded Finish** — expected to finish (full gate roundings) but absent from the finish list, probably recording error.

    See Scoring Algorithm §2 for full classification rules and config-conditional thresholds.
55. As a scorer, I want the "Gate" finish type to have a tooltip explaining its meaning per SI 13.2.3(i) — boats that "have completed a lap before the finishing window opens but then fail to finish while it is open" — so that less experienced scorers understand the classification. The tooltip may also note that this outcome is informally called a "Whiskey finish" or "finish in place" in WASZP race management practice, though these terms do not appear in the official SIs or RMG.
56. As a scorer, I want boats ordered first by lap count (more laps = higher rank), then by position within each lap-count tier per SI 13.2.3, so that the GP Finish Ranking reflects the correct scoring. See Scoring Algorithm §3 for tier ordering rules, config-conditional behavior, and worked examples.
57. As a scorer, I want boats with letter scores placed at the bottom of the ranking with a score of (entries + 1) so that non-finishers are correctly separated.
58. As a scorer, I want a warning if the first boat on the finish list in the 8.2 fleet has fewer than the required laps, so that the lead-boat rule violation is flagged for the 8.2 group.
59. As a scorer, I want the same lead-boat warning for the non-8.2 (combined) fleet, so that both fleet groups are validated independently.
60. As a scorer, I want to see a GP Finish Ranking table (sorted) and the original finish list (unsorted) side by side, so that I can compare the two views simultaneously.
61. As a scorer, I want checkboxes to show or hide individual rig sizes in both panels, so that I can focus on one fleet at a time during review.
62. As a scorer, I want all tables to show columns: Place, Country (3-letter code), Sail #, Sailor Name, Rig Size, Division, Laps, Finish Type, so that all relevant information is visible at once.
63. As a scorer, I want to navigate back to the gate rounding or finish list entry from the scoring view to correct an error, so that fixing mistakes doesn't require starting over.

### Export

64. As a scorer, I want a manual "Export to Excel" button, so that I control when the final file is produced.
65. As a scorer, I want the Excel file to default to the name `{EventName}_Race{N}_{Date}.xlsx`, so that files are automatically organized by event and race.
66. As a scorer, I want the first Excel sheet ("Finish Placings") to contain an overall GP Finish Ranking table, an overall original finish order table, then 8.2-fleet-only tables, then non-8.2-fleet tables, so that all relevant breakdowns are in one sheet.
67. As a scorer, I want each Excel table to have left (GP ranked) and right (original order) columns, so that the PRO can compare GP order against raw finish order at a glance.
68. As a scorer, I want the second Excel sheet ("Gate List") to contain the full gate rounding table in entry order with lap-count highlighting, so that the gate rounding record is preserved alongside the results.
69. As a scorer, I want both color signals reproduced in the Excel gate list sheet — background cell fill matching the row's rounding tier, and font color matching the boat's total-lap text color — so that the exported file is visually identical to the on-screen display.
70. As a scorer, I want all Excel tables to include Place, Country, Sail #, Sailor Name, Rig Size, Division, Laps, and Finish Type columns, so that nothing is lost in the export.
71. As a scorer, I want to be prompted to export to Excel when I exit the app if I haven't exported yet, so that I don't accidentally lose results.

### Save & Resume

72. As a scorer, I want the app to auto-save all state to a JSON sidecar file on every change, so that a crash or accidental close doesn't lose my work.
73. As a scorer, I want to be offered the option to resume a previous session on launch, so that I can pick up where I left off after an interruption.
74. As a scorer, I want to be prompted to save the JSON session file on exit, so that I have an explicit checkpoint of my work.
75. As a scorer, I want the session file to be versioned, so that future app versions can read sessions created by older versions.

---

## Implementation Decisions

### Module Design

The application is structured around **deep modules** — components with rich internal logic exposed through a narrow, stable interface that can be tested in isolation.

#### `models.py` — Data classes (attrs)
Core data types shared across all modules. These change rarely and carry no business logic.
- `Competitor(sail_number, country_code, name, rig_size, division)` — loaded from CSV
- `GateRounding(position, sail_number)` — ordered entry in the gate list
- `FinishEntry(position, sail_number, letter_score)` — ordered entry in the finish list
- `ScoredResult(place, competitor, laps, finish_type, annotation)` — output of scorer
- `FinishLineConfig` — enum with two values: `FINISH_AT_GATE` (finishing line is at mark 2p; gate rounding and finishing line crossing are the same physical event) and `SEPARATE_PIN` (finishing line is a separate pin or reach to finish per RMG p.6; gate roundings and finishing line crossings are distinct and can interleave during the finishing window)
- `RaceSession` — top-level container for all state; serialized to/from JSON. Includes `finish_line_config: FinishLineConfig` (default `FINISH_AT_GATE`), `finish_window_marker_position: Optional[int]` (index into the gate rounding list after which entries are "window-phase"; `None` if the marker has not been placed; only relevant when `finish_line_config == SEPARATE_PIN`), and `lap_counting_location: str` (informational field for human counter positioning; default depends on course type)

#### `scorer.py` — GP scoring algorithm (pure functions, no UI)
The deepest and most critical module. Takes a `RaceSession` and returns a list of `ScoredResult`. No side effects, no UI dependencies. Fully testable with synthetic data.

Responsibilities:
- Count gate roundings per sail number → assign lap counts, using the config-conditional formula:
  - `FINISH_AT_GATE`: `laps = gate_roundings + (1 if on_finish_list else 0)`. The finishing line crossing at 2p is counted as a lap by the finish flag rather than a gate rounding entry (matching the RMG example where a 3-lap winner has 2 gate list entries + 1 finish). Gate roundings capped at `required_laps − 1`. If a Finishing Window Opened marker is present, roundings after the marker are tagged for visual display as window-phase, but this is purely informational — the same cap and formula apply regardless.
  - `SEPARATE_PIN`: `laps = gate_roundings` (all gate roundings, regardless of whether they fall before or after the Finishing Window Opened marker). Gate roundings capped at `required_laps`. The marker does not affect lap counts — it determines tier ordering for Gate finish boats (see Scoring Algorithm §3) and is shown visually in the gate log for audit purposes.
- Classify finish type per boat (Standard, GP, Gate, Finish Only, Error: No Recorded Finish, Letter Score)
- Build GP Finish Ranking per the ordering rules: full-lap tier (Standard finishers in finish order, Error: No Recorded Finish interleaved by per-lap sequence position); short-lap tiers (pre-window gate-only boats first in per-lap sequence order, then line-crossers GP/Finish Only in finish order, then window-phase gate-only boats at the bottom of their tier for `SEPARATE_PIN`); letter scores at bottom
- Validate lead-boat rule for each fleet group
- Return all warnings as a structured list alongside results

#### `validator.py` — Validation and warnings (pure functions)
Checks individual data entry events and whole-sheet consistency. Returns typed `Warning` objects (not strings) so the UI can display them consistently and tests can assert on their type and content.

Responsibilities:
- Unknown sail number
- Consecutive duplicate on gate list
- Duplicate on finish list
- Green Fleet boat entered on either list
- Boat on finish list but not gate list
- Boat on gate list with required laps but not finish list
- Letter score conflict with gate list appearance
- Lead-boat rule violation (first boat in fleet on finish list has fewer than required laps)
- Unrecognized rig size
- `SEPARATE_PIN` config with no Finishing Window Opened marker placed when scoring is requested or when the user navigates to the finish list

#### `session.py` — Persistence (JSON serialize/deserialize)
Converts `RaceSession` to/from JSON. Handles schema versioning. Auto-saves on every mutation. The only module that touches the filesystem (apart from `exporter.py`).

#### `exporter.py` — Excel export (openpyxl)
Takes a scored `RaceSession` and produces the two-sheet Excel file. Applies cell fills matching the on-screen pastel color scheme. No scoring logic — receives pre-computed results from `scorer.py`.

#### `widgets/sail_combobox.py` — Filtered autocomplete combobox
A custom `ttk.Combobox` subclass that:
- Narrows the dropdown on each keystroke
- Excludes Green Fleet sail numbers from its list
- Emits a validation warning if the typed value is not in the allowed set
- Confirms Tab/Enter and fires a callback to advance focus
Used by gate rounding entry, finish list entry, and the Green Fleet wizard.

#### `phases/` — UI phase panels (tkinter frames)
Each phase is a self-contained `tk.Frame` subclass managed by `gui.py`. Phases observe `RaceSession` and redraw on change. They do not contain scoring logic.
- `setup.py` — CSV load, metadata form, Green Fleet wizard, course/lap configuration
- `data_entry.py` — gate list entry (2a) and finish list entry (2b) with editing controls
- `lap_display.py` — live gate rounding table with highlighting (embedded in data_entry)
- `scoring.py` — GP Finish Ranking and original finish order panels, rig-size filter checkboxes

#### `gui.py` — App shell and navigation
Top-level `tk.Tk` window. Owns the `RaceSession`. Manages phase transitions (forward/back navigation). Wires auto-save to session mutations. Handles exit prompt logic.

### Position Definition

**"Position" in this document always means per-lap sequence position** — a boat's ordinal rank among all boats completing the same lap number at the same counting location, NOT the raw row index in the gate log. For example, if boats A, B, C each complete their 1st lap (recorded as gate roundings in the log), and A's 1st rounding is at row 1, B's at row 3, and C's at row 5 (with other boats' roundings at rows 2, 4), then A is 1st, B is 2nd, C is 3rd among 1-lap completers. When a boat's "last gate rounding position" is referenced for scoring, it means the boat's sequence position for that specific lap (e.g., "3rd boat to complete lap 1"), not its absolute row number in the gate log. The scorer module must compute per-lap sequence positions from the raw gate log.

### Scoring Algorithm (detailed)

1. **Build lap count map** (config-conditional):
   - **`FINISH_AT_GATE`**: For each sail number, count all appearances on the gate list, capped at `required_laps − 1` (warn if exceeded). Lap total = `gate_roundings + (1 if on_finish_list else 0)`. If a Finishing Window Opened marker is present, split the gate list at that position for display purposes (lighter style below the divider), but apply the same cap and formula to all entries regardless of position — the marker has no effect on scoring.
   - **`SEPARATE_PIN`**: For each sail number, count all appearances on the gate list, capped at `required_laps` (warn if exceeded). Lap total = `gate_roundings`. If a Finishing Window Opened marker is present, split the gate list at that position for display purposes (lighter style below the divider) and for tier ordering of Gate finish boats (see §3), but the marker does not affect lap counts.

2. **Classify each boat** (for each boat in the universe — all competitors + any unregistered entries on either list):
   - `FINISH_AT_GATE`:
     - Gate roundings == `required_laps − 1` AND on finish list → **Standard**
     - On finish list AND gate roundings < `required_laps − 1` (including 0) → **GP**
     - Gate roundings ≥ 1 AND not on finish list → **Gate Finish**
     - On finish list AND not on gate list → **Finish Only** (assume 1 lap)
     - Gate roundings == `required_laps − 1` AND not on finish list → **Error: No Recorded Finish** (warn); interleave by per-lap sequence position
   - `SEPARATE_PIN`:
     - Gate roundings == `required_laps` AND on finish list → **Standard**
     - On finish list AND gate roundings < `required_laps` (including 0) → **GP**
     - Gate roundings ≥ 1 AND not on finish list → **Gate Finish** (tier ordering depends on whether last rounding is pre-window or window-phase — see §3)
     - On finish list AND not on gate list → **Finish Only** (assume 1 lap, warn)
     - Gate roundings == `required_laps` AND not on finish list → **Error: No Recorded Finish** (warn); interleave by last per-lap sequence position
   - Regardless of config:
     - Has letter score AND not on gate list → **Letter Score**
     - Has letter score of DNS, DNC, or DNF AND on gate list → override to **Gate Finish**; annotate SI 13.2.3(i)

3. **Sort into lap-count tiers** (most laps first). Within each tier:
   - **Full-lap tier**: Standard finishers in finish list position order. Error: No Recorded Finish boats interleaved by their final per-lap sequence position relative to Standard finishers' final per-lap sequence positions.
   - **Short-lap tiers** (config-conditional):
     - `FINISH_AT_GATE`: Gate-finish boats *first* (in per-lap sequence order of their last qualifying rounding; SI 13.2.5 "last known position"), then line-crossers (GP, Finish Only) in finish list position order. The two sequences are non-overlapping in time.
     - `SEPARATE_PIN`: (a) pre-window Gate-finish boats first (per-lap sequence order of last pre-window rounding; SI 13.2.5 "last known position"); (b) then line-crossers (GP, Finish Only) in finish list position order; (c) then window-phase Gate-finish boats (conservative placement, per-lap sequence order of last window-phase rounding).
   - **Short-lap tier examples** (all boats have 1 lap in a 2-lap race):
     - *Finishing line at gate*: A (Gate, 1 gate rounding, no finish), B (GP, 1 gate rounding + finish), C (Finish Only, no gate rounding + finish). Ranking: A, then B and C in finish list order.
     - *Separate pin, pre-window gate-only*: same scenario, marker placed after A's rounding. Ranking: A (pre-window), then B and C in finish list order.
     - *Separate pin, window-phase gate-only*: same scenario, A's rounding after marker. Ranking: B and C in finish list order, then A (window-phase, conservative placement).

4. Append letter-score boats at the bottom (score = entries + 1).
5. Validate lead-boat rule for each fleet group independently.
6. Return results + warnings list.

### Data Model Notes

- Rig sizes detected dynamically from CSV. Two scoring groups: `8.2` vs everything else.
- Country code stored as 3-letter ISO string from `Sailor Country Code` CSV column (required).
- Green Fleet sail numbers stored as a set in `RaceSession`; excluded from autocomplete lists and all output.
- Letter scores stored per finish entry row as an optional enum.
- `finish_line_config` stored as a string enum (`"FINISH_AT_GATE"` / `"SEPARATE_PIN"`) in JSON; defaults to `"FINISH_AT_GATE"` on deserialize if absent (backward compatibility with sessions created before this field existed).
- `finish_window_marker_position` stored as a nullable integer (0-based index into the gate rounding list); `null` in JSON if not yet placed. Under `SEPARATE_PIN`, determines tier ordering for Gate finish boats (does not affect lap counts); under `FINISH_AT_GATE`, purely informational for display. Always serialized to preserve round-trip fidelity.
- `lap_counting_location` stored as a string in JSON; informational only (does not affect scoring). Defaults: `"Leeward gate (2s/2p)"` for Standard WASZP W/L (per RMG: "Numbers only need to be recorded at the leeward marks"); `"Windward gate (1s/1p)"` for SailGP. The user may override the default. On a 2-lap SailGP course, expected sightings for a full-course boat vary by counting location: at the leeward gate the counter sees each boat twice; at the windward marks the counter sees the boat three times (1p on the initial reach, 1s/1p gate on the first upwind, 1s before the reach to finish).
- Session JSON includes a `schema_version` integer field; increment on breaking changes.

### Technology Stack

| Concern | Choice |
|---|---|
| Language | Python ≥ 3.10 |
| GUI toolkit | `tkinter` + `tkinter.ttk` |
| Drag-and-drop | `tkinterdnd2` (graceful fallback to file picker) |
| Autocomplete widget | Custom `ttk.Combobox` subclass |
| Data manipulation | `pandas`, `numpy` |
| Excel export | `openpyxl` |
| Data classes | `attrs` |
| Dependency management | `pip-tools` (`requirements.txt` from `pyproject.toml`) |
| Build — macOS | PyInstaller + `dmgbuild`; ad-hoc code signing |
| Build — Windows | PyInstaller via GitHub Actions CI |
| Project layout | `src/` layout, PEP 621 `pyproject.toml` |
| Min OS | macOS 12 (Monterey), Windows 10 |
| Testing | `pytest` with synthetic CSV fixtures |

### Distribution

- **App name:** WASZP GP Scorer
- **Bundle ID:** `com.waszp.racehub.gp-scorer`
- **Icon:** Derived from `WASZP-Logo-01.png` → `.icns` (macOS), `.ico` (Windows)
- **DMG background:** `WASZP-Logo-01.png`
- **macOS signing:** ad-hoc (`codesign --force --deep --sign -`); Gatekeeper warning on first launch is acceptable
- **Windows signing:** none

### Highlighting Color Scheme

Two independent color signals are applied to each row. They communicate different things and must never be confused:

**Background color** — applied to the row itself; reflects *which rounding this specific entry represents*:

| Nth rounding | Background color | Hex |
|---|---|---|
| 1st rounding | None (white) | — |
| 2nd rounding | Highlighter blue | `#66D9FF` |
| 3rd rounding | Highlighter green | `#CCFF66` |
| 4th rounding | Highlighter yellow | `#FFFF66` |
| 5th+ rounding | Highlighter pink | `#FF80BF` |

**Text color** — applied to *all rows for a given sail number* and updated retroactively whenever a new rounding for that boat is added; reflects *that boat's current total lap count*:

| Total roundings for boat | Text color | Hex | Notes |
|---|---|---|---|
| 1 | Default black | `#1C1C1E` | No text highlight until a 2nd rounding is recorded |
| 2 | Medium teal-blue | `#0088AA` | All rows for this boat switch when the 2nd rounding is entered |
| 3 | Medium green | `#5A9900` | All rows for this boat switch (retroactively) when the 3rd rounding is entered |
| 4 | Medium olive | `#9E9E00` | |
| 5+ | Medium magenta | `#AA0055` | |

The text colors are derived as the legible foreground complement of the corresponding highlighter background colors (`#0088AA` on `#66D9FF`, `#5A9900` on `#CCFF66`, etc.), chosen to be saturated but not so dark that they muddy the white-background rows where they appear retroactively.

The combination means: a row with a **white background** but **colored text** immediately signals that this was the boat's first rounding but they have been seen again later in the log. A row with a **colored background and matching dark text** confirms the rounding tier. A row with **black text on white** means the boat has only been sighted once so far.

### Fleet & Rig Structure

| Scoring group | Rig sizes |
|---|---|
| 8.2 fleet | 8.2 |
| Non-8.2 fleet | 7.5, 6.9, 5.8 (WASZP X), and any others |

Known valid rig sizes: `8.2`, `7.5`, `6.9`, `5.8`. Warn on any other value.

### Letter Score Reference (RRS 2025-2028 Appendix A, Rule A10)

| Code | Full name |
|---|---|
| `DNC` | Did Not Compete |
| `DNS` | Did Not Start |
| `OCS` | On Course Side |
| `UFD` | U-Flag Disqualification |
| `BFD` | Black Flag Disqualification |
| `ZFP` | 20% Penalty (rule 30.2) |
| `NSC` | Did Not Sail the Course |
| `DNF` | Did Not Finish |
| `RET` | Retired |
| `SCP` | Scoring Penalty (rule 44.3(a)) |
| `DSQ` | Disqualification |
| `DNE` | Non-Excludable Disqualification |
| `DGM` | Disqualification — Gross Misconduct |
| `RDG` | Redress Given |
| `DPI` | Discretionary Penalty Imposed |

`DNC`, `DNS`, `OCS`, `NSC`, `DNF`, `RET`, `DSQ`, `DNE`, `DGM`, `UFD`, `BFD` → score = entries + 1.
`ZFP`, `SCP`, `RDG`, `DPI` → percentage/discretionary; display code only, note points are calculated externally.

### Warnings System

All warnings are typed objects (not raw strings) so the UI can render them consistently and tests can assert on type.

| Condition | Type |
|---|---|
| Green Fleet sail number entered on either list | `GreenFleetEntryWarning` |
| Sail number not in competitor CSV | `UnknownSailNumberWarning` |
| Duplicate sail number on finish list | `DuplicateFinishEntryWarning` |
| Finish list boat absent from gate list | `FinishOnlyWarning` |
| Gate list boat (required laps) absent from finish list | `NoRecordedFinishWarning` |
| Letter score conflicts with gate list appearance | `LetterScoreConflictWarning` |
| First boat in fleet on finish list has fewer than required laps (i.e. the "second lead boat" per SI 13.2.1 has short-lapped) | `LeadBoatViolationWarning` |
| Consecutive duplicate on gate list | `ConsecutiveDuplicateWarning` |
| More gate roundings than required laps | `ExcessRoundingsWarning` |
| 1-lap race or no-gate course type selected | `NoGPValueWarning` |
| Unrecognized rig size in CSV | `UnknownRigSizeWarning` |
| Navigating to finish list with `SEPARATE_PIN` config and no Finishing Window Opened marker placed (not raised for `FINISH_AT_GATE`) | `MissingFinishWindowMarkerWarning` |

---

## Testing Decisions

### What makes a good test
Tests should exercise **external behavior** — inputs and outputs of a module's public interface — not internal implementation details. A good test for `scorer.py` passes in a `RaceSession` with known data and asserts on the returned `ScoredResult` list. It does not inspect internal variables or mock internal calls.

### Modules to test

#### `scorer.py` — highest priority; pure functions make this straightforward
- Standard finish: all boats complete required laps and cross the finishing line → correct numeric places
- GP finish: mix of 2-lap and 1-lap finishers in a 2-lap race → 2-lappers ranked ahead
- Gate finish: boat completes laps at gate, never crosses finishing line → inserted correctly relative to finishing line boats with same lap count
- Lead-boat violation: first 8.2 finisher (the "second lead boat" per SI 13.2.1) has fewer than required laps → warning returned
- Letter score override: boat with DNS also on gate list → reclassified, annotated
- Finish Only: boat on finish list, not gate list → assumed 1 lap, warning returned, and annotated as likely recording error
- Error: No Recorded Finish: boat with required laps on gate list, absent from finish list → interleaved by per-lap sequence position among full-lap finishers and annotate
- Short-lap tier ordering: gate-only boat and a GP finisher both have 1 lap → gate-only boat ranks **ahead** regardless of relative gate position, because gate roundings precede the finishing window (RMG p.18-19, confirmed by 2511 example)
- Short-lap tier ordering (multiple gate-only boats): three gate-only 1-lappers ranked A, B, C in per-lap sequence order; one GP 1-lapper also in the 1-lap tier → ranking is A, B, C, then the GP boat (gate-only boats always ahead of line-crossers in the same tier)
- Short-lap tier ordering (multiple line-crossers): gate-only 1-lapper ahead of all, then GP and Finish Only in finish list order among themselves
- Fleet grouping: 8.2 and 7.5 boats interleaved → places computed correctly within each group
- **Finishing line config — `FINISH_AT_GATE` lap formula**: in a 2-lap race, a boat with 1 gate rounding that also crossed the finishing line has `laps = 1 + 1 = 2` (Standard); a boat with 1 gate rounding that did not cross has `laps = 1` (Gate)
- **Finishing line config — `SEPARATE_PIN` lap formula**: in a 2-lap race, a boat with 2 gate roundings has `laps = 2` regardless of whether it also crossed the finishing line or whether roundings occurred before or after the Finishing Window Opened marker; the marker does not affect lap counts
- **`SEPARATE_PIN` window-phase roundings count toward laps**: in a 2-lap race, a boat with 1 pre-window rounding and 1 window-phase rounding has `laps = 2` (not `laps = 1`)
- **`SEPARATE_PIN` pre-window gate-only vs finish boat**: pre-window Gate boat (1 pre-window rounding, no finish) ranks ahead of GP boat (1 pre-window rounding + crossing finishing line) in same tier
- **`SEPARATE_PIN` window-phase gate-only vs finish boat**: window-phase Gate boat (last rounding after marker, no finish) ranks behind GP boat (1 pre-window rounding + crossing finishing line) in same tier
- **`SEPARATE_PIN` two window-phase boats, one finishes**: two boats both have 1 window-phase rounding; one also crosses the finishing line (GP), the other does not (Gate). The GP boat ranks ahead of the Gate boat in the same tier — the recorded finish wins because the finishing window may have expired while the Gate boat was reaching to the line
- **`SEPARATE_PIN` Error: No Recorded Finish threshold**: in a 2-lap race, a boat with 2 gate roundings (regardless of window phase) and no finish entry triggers `NoRecordedFinishWarning`; a boat with only 1 gate rounding and no finish is classified Gate (not an error)
- **`MissingFinishWindowMarkerWarning`**: with `SEPARATE_PIN` config and no marker placed, scoring still runs but `MissingFinishWindowMarkerWarning` is returned; all gate roundings are treated as pre-window for tier ordering purposes
- **Two-fleet shared course (8.2 and 7.5/6.9)**: single gate list and finish list with both rig sizes interleaved → per-fleet rankings computed correctly; lead-boat validation fires independently for each fleet group; overall ranking includes all boats
- **Two-fleet lead-boat validation**: first 8.2 finisher has full laps but first 7.5 finisher has short laps → `LeadBoatViolationWarning` for non-8.2 fleet only, not for 8.2 fleet
- **Per-lap sequence position**: three boats A, B, C complete their 1st lap; gate log has A's 1st rounding at row 2, B's at row 5, C's at row 8 (other boats' roundings interleaved) → A is position 1, B is position 2, C is position 3 among 1-lap completers (NOT row indices 2, 5, 8)

#### RMG Worked Examples — Integration Test Fixtures

The following examples are extracted verbatim from the WASZP Race Management Guide v3 (2025) and should be implemented as integration test fixtures for `scorer.py`. Each example includes complete input data and expected output taken directly from the authoritative race management documentation. These tests validate that the scoring algorithm produces correct results against the official published examples — not just against the developer's interpretation of the rules.

##### RMG Example 1: Grand Prix Finish — 3-lap race, 20 boats, `FINISH_AT_GATE` *(RMG pp.18-19)*

**Configuration:**
- Course: Standard WASZP W/L (Gate)
- Finishing line config: `FINISH_AT_GATE`
- Required laps: 3
- Fleet: 20 boats entered (all same rig size for simplicity; rig-size splitting tested separately)

**Gate List (29 entries, in recording order):**
```
2106, 2798, 3001, 2511, 2469, 2445, 2688, 2096, 2314, 2275, 2864, 2554, 2117, 2228, 2916,
2106, 2798, 3001, 2511, 2469, 2445, 2096, 2314, 3102, 3118, 2275, 2864, 2554, 2994
```

**Finish List (17 entries, in crossing order):**
```
2106, 3001, 2186, 2798, 2469, 2445, 2314, 2096, 2864, 2275, 2554, 2916, 2228, 3102, 3118, 2117, 2994
```

**Competitor not on either list:** 2666 (started but DNF — must be in competitor CSV with letter score `DNF` assigned on the finish list, or handled as a known entrant absent from both lists)

**Expected lap counts** (formula: `gate_roundings + (1 if on_finish_list else 0)`, gate cap = 2):

| Sail # | Gate roundings | On finish list | Laps | Finish Type |
|---|---|---|---|---|
| 2106 | 2 | Yes | 3 | Standard |
| 2798 | 2 | Yes | 3 | Standard |
| 3001 | 2 | Yes | 3 | Standard |
| 2469 | 2 | Yes | 3 | Standard |
| 2445 | 2 | Yes | 3 | Standard |
| 2096 | 2 | Yes | 3 | Standard |
| 2314 | 2 | Yes | 3 | Standard |
| 2275 | 2 | Yes | 3 | Standard |
| 2864 | 2 | Yes | 3 | Standard |
| 2554 | 2 | Yes | 3 | Standard |
| 2511 | 2 | No | 2 | Gate |
| 2916 | 1 | Yes | 2 | GP |
| 2228 | 1 | Yes | 2 | GP |
| 3102 | 1 | Yes | 2 | GP |
| 3118 | 1 | Yes | 2 | GP |
| 2117 | 1 | Yes | 2 | GP |
| 2994 | 1 | Yes | 2 | GP |
| 2688 | 1 | No | 1 | Gate |
| 2186 | 0 | Yes | 1 | Finish Only |
| 2666 | 0 | No | — | DNF |

**Expected GP Finish Ranking:**

| Place | Sail # | Laps | Finish Type | Tier ordering rationale |
|---|---|---|---|---|
| 1 | 2106 | 3 | Standard | Full-lap tier; finish list position 1 |
| 2 | 3001 | 3 | Standard | Full-lap tier; finish list position 2 |
| 3 | 2798 | 3 | Standard | Full-lap tier; finish list position 4 (2186 at pos 3 is a 1-lapper, so 2798 is 3rd among 3-lappers) |
| 4 | 2469 | 3 | Standard | Full-lap tier; finish list position 5 |
| 5 | 2445 | 3 | Standard | Full-lap tier; finish list position 6 |
| 6 | 2314 | 3 | Standard | Full-lap tier; finish list position 7 |
| 7 | 2096 | 3 | Standard | Full-lap tier; finish list position 8 |
| 8 | 2864 | 3 | Standard | Full-lap tier; finish list position 9 |
| 9 | 2275 | 3 | Standard | Full-lap tier; finish list position 10 |
| 10 | 2554 | 3 | Standard | Full-lap tier; finish list position 11 |
| 11 | 2511 | 2 | Gate | 2-lap tier; Gate boat first — "completed two laps before any [GP 2-lap boats]" (RMG p.19) |
| 12 | 2916 | 2 | GP | 2-lap tier; line-crosser, finish list position 12 |
| 13 | 2228 | 2 | GP | 2-lap tier; line-crosser, finish list position 13 |
| 14 | 3102 | 2 | GP | 2-lap tier; line-crosser, finish list position 14 |
| 15 | 3118 | 2 | GP | 2-lap tier; line-crosser, finish list position 15 |
| 16 | 2117 | 2 | GP | 2-lap tier; line-crosser, finish list position 16 |
| 17 | 2994 | 2 | GP | 2-lap tier; line-crosser, finish list position 17 |
| 18 | 2688 | 1 | Gate | 1-lap tier; Gate boat first — "completed one lap before 2186" (RMG p.19) |
| 19 | 2186 | 1 | Finish Only | 1-lap tier; line-crosser, finish list position 3; ranked last among 1-lappers despite finishing 3rd across the line |
| 20 | 2666 | — | DNF | Letter score; "started the race but does not appear on either list" (RMG p.19) |

**Explicitly called-out scoring cases from RMG p.19** (each should be a named sub-assertion in the test):

1. **2186 — Finish Only, cross-tier demotion**: "the third boat to cross the finish line — does not appear on the gate list. It appears once in total. Therefore, despite crossing the line in third, 2186 only sailed one lap." Validates that finish list position alone does not determine rank; lap count is primary.

2. **2511 — Gate finish ahead of GP finishers**: "2511 appears twice in total, so sailed two laps but failed to cross the finishing line within the finishing window... Notice that 2511 completed two laps before any of the [GP 2-lap] numbers completed two laps, so is ranked ahead of the [GP 2-lap] numbers." Validates the gate-before-line-crossers rule within a tier under `FINISH_AT_GATE`.

3. **2688 — Gate finish (1 lap) ahead of Finish Only (1 lap)**: "2688 appears once in total, so sailed one lap but failed to cross the finishing line... Notice that 2688 completed one lap before 2186 completed one lap so is ranked ahead of 2186." Validates gate-before-line-crossers at the 1-lap tier too.

4. **2666 — DNF, absent from both lists**: "2666 started the race but does not appear on either list. Therefore, 2666 failed to complete one lap and scores a DNF." Validates DNF handling for boats that started but have zero recorded activity.

5. **2916 — GP finish (2 laps), behind Gate finish**: 2916 has 1 gate rounding + 1 finish crossing = 2 laps. Despite being on the finish list, 2916 ranks behind 2511 (Gate, same lap count) because gate roundings precede the finishing window under `FINISH_AT_GATE`.

##### RMG Conceptual Example 2: Gate vs Finish — 2-lap race *(RMG p.16)*

A minimal 2-boat example from the RMG narrative, useful as a focused unit test:

> "For a 2-lap race, a boat that sails two laps will feature on both lists. Boat X features on the leeward mark list but not the finish list so did one lap; whilst Boat Y features on the finish list but not the leeward mark list; also completing one lap. Boat X is ranked ahead of Boat Y because Boat X completed one lap before Boat Y."

**Configuration:** `FINISH_AT_GATE`, required laps = 2

| Boat | Gate list | Finish list | Laps | Finish Type | Expected rank |
|---|---|---|---|---|---|
| X | 1 rounding | No | 1 | Gate | 1st |
| Y | 0 roundings | Yes | 1 | Finish Only | 2nd |

Validates the most basic gate-before-finish-line rule. Boat X's gate rounding happened *before* the finishing window opened (by definition under `FINISH_AT_GATE`), so X ranks ahead of Y despite Y crossing the line.

##### RMG Scoring Principles — Derived Test Cases *(RMG pp.15-17)*

The following principles are stated in the RMG narrative and GP finish SI text. Each should have at least one test case:

1. **"Boats that completed more laps are ranked ahead of boats that completed fewer"** (RMG p.16) — Already covered by the 3-lap example (10 Standard boats all rank ahead of 7 GP/Gate 2-lap boats).

2. **"Boats that completed the same number of laps are ranked in the order than they completed their last lap"** (RMG p.16) — Covered by within-tier ordering in the 3-lap example.

3. **Lap counting stops when the lead boat crosses the finishing line** (RMG p.16): "When the lead boat crosses the finishing line to finish, the lap counting stops immediately... and the boats crossing the finishing line must now be recorded instead." Under `FINISH_AT_GATE`, this means gate list and finish list are non-overlapping in time. Test: no boat should appear on the finish list *and* have its final gate rounding after the lead boat's last gate rounding if the data is well-formed (the app does not enforce this — it is a data quality property, not a scoring rule).

4. **Reach-to-finish variant is functionally `SEPARATE_PIN`** (RMG p.6): "Lap counting needs to account for competitors on the final reach when the Finish Window closes." A W/L course with reach to finish requires `SEPARATE_PIN` config. Test: ensure the SailGP course auto-selects `SEPARATE_PIN` (UI test), and that a W/L course with `SEPARATE_PIN` produces correct tier ordering per §3 of the scoring algorithm.

#### `validator.py`
- Each warning type triggered by its corresponding input condition
- No false positives on clean input

#### `session.py`
- Round-trip: serialize a `RaceSession` to JSON and deserialize → identical object
- Schema version field present in output
- Missing optional fields in JSON deserialize gracefully
- `lap_counting_location` field round-trips correctly

#### `exporter.py`
- Output file has exactly 2 sheets with correct names
- Correct number of rows per table (including header)
- Cell fill colors match expected background hex values for each rounding tier
- Cell font colors match expected text hex values for each boat's total-lap tier
- Country code column present in all tables

#### `widgets/sail_combobox.py`
- Filtering: typing "20" narrows list to sail numbers containing "20"
- Green Fleet exclusion: Green Fleet sail numbers absent from dropdown
- Tab/Enter callback fires with correct value

### Test fixtures
All tests use synthetic CSV files in `tests/fixtures/`. Real competitor data is never committed. The anonymised file `2026-MIDWINTERS-Sailor-anonymized.csv` in the repo root may be used as a realistic fixture template. Example CSV files need to be large enough to test all features, but should not be so large that it makes human verification challenging. A fleet of more than 10 and less than 20 boats is sufficient.

---

## Out of Scope

- **Series / multi-race accumulation** — drop scores, points totals, series leaderboard. The app produces per-race results; series scoring is handled externally. Reviewed: Games NoR 14 defines only series-level scoring (discard schedules, championship minimum races). Per-race scoring is entirely governed by SI 13.2. The per-race place numbers produced by the GP Scorer feed directly into the external series scoring system.
- **Lap counting at multiple gate locations simultaneously** — the app records a single gate list per race, regardless of which physical marks the counter is stationed at. The `lap_counting_location` field records where the counter sat for audit purposes but does not affect scoring logic.
- **Multiple simultaneous gate lists** — one gate list per race.
- **Sprint BOX and Slalom Sprint courses** — these are single-lap, no-gate formats that do not require GP scoring; the app will display a warning if such a course type is selected and block the user from proceeding.
- **Sprint Racing tournament format** — scope depends on whether the Games SIs specify a SailGP-style gate course (in which case existing support covers it) or a slalom/elimination format. Pending Games SIs publication.
- **Distance Race** — all fleets start together, no gate roundings, out of scope.
- **Green Fleet racing** — Green Fleet races separately in a simplified coached format; excluded from GP scoring. The app provides a wizard to identify and exclude Green Fleet sail numbers.
- **Networking, cloud sync, multi-user collaboration** — single-user desktop tool only.
- **Standard penalties for class rule infringements (SI Appendix 3)** — percentage-based penalties calculated using the RRS 44.3(c) method (e.g. "50% all races of day", "10% previous race") are applied externally in the series scoring system (e.g. Sailwave). The GP Scorer does not compute percentage penalties. The letter score `SCP` may be used to flag that a scoring penalty exists, but the points adjustment is calculated and applied outside the app.
- **Separate per-fleet finishing windows** — the app supports a single finishing window per race (matching the SI 13.2 design where fleets share a course area and a single finishing window opens on the second lead boat). If fleets race on separate course areas with independent finishing windows, the scorer should launch a separate instance of the app with a separate competitor CSV for each course area.

---

## Reference Documents

All authoritative race documents are stored in `racedocs/`. When resolving ambiguity or verifying scoring logic, consult them in the priority order listed below — the SIs are the primary authority for per-race GP scoring; the RMG supplements with worked examples; the RRS provides foundational rule definitions; the NoR governs series-level scoring only.

| File | Description | When to consult |
|---|---|---|
| [`WASZP Pre-Games 2026 SIs - FINAL.pdf`](../racedocs/WASZP%20Pre-Games%202026%20SIs%20-%20FINAL.pdf) | WASZP Pre-Games 2026 Sailing Instructions (9 pp). **Primary authority for GP finish scoring.** | SI 13.2 (Grand Prix Finish) — the core algorithm this app implements. Also: course definitions (Appendix 1), fleet structure & starting sequence (SI 7–8, 11.2), standard penalties (Appendix 3). This is the first document to check for any scoring question. |
| [`Race-Management-Guide-1.pdf`](../racedocs/Race-Management-Guide-1.pdf) | WASZP Race Management Guide v3, 2025 (34 pp). | GP finish worked example (pp.18–19), course layout diagrams, lap counting procedures, finishing line configurations (gate vs separate pin), W/L with reach-to-finish variant (p.6). **Where the RMG conflicts with the SIs, the SIs are authoritative.** |
| [`Racing-Rules-of-Sailing-2025-2028.pdf`](../racedocs/Racing-Rules-of-Sailing-2025-2028.pdf) | The Racing Rules of Sailing 2025–2028, World Sailing (full document). | Foundational rule definitions referenced by the SIs (e.g., rule 44.3 for scoring penalties, Appendix A Rule A10 for letter score definitions). Consult when a rule number is cited in the SIs or when resolving protest/scoring disputes that go beyond GP-specific rules. |
| [`WASZP GAMES 2026 - NoR - Final.pdf`](../racedocs/WASZP%20GAMES%202026%20-%20NoR%20-%20Final.pdf) | WASZP Games 2026 Notice of Race (8 pp). | Extended series scoring & discard schedules (NoR 14), Games-specific event structure. Does **not** contain per-race scoring rules. |

---

## Further Notes

### Authoritative Rules Reference
The GP finish scoring rules are defined in **SI 13.2 (Grand Prix Finish)** of the WASZP Pre-Games 2026 Sailing Instructions (the closest published SIs to the Games). The core rule:

> *"Their score in the race will be based on the order when they either completed their last lap or finished, with those having completed more laps finishing ahead of those with fewer laps."* — SI 13.2.3

SI 13.2.1 defines two lead boats when fleets share a course area: the **first lead boat** is first overall across all fleets; the **second lead boat** is first within its fleet. Per SI 13.2.2, the finishing window closes 10 minutes after the **second lead boat** finishes. Per SI 13.2.3, the finish flag is displayed when the second lead boat is in the vicinity of the final mark for the final time. The finishing window opens when the second lead boat crosses the finishing line — i.e., when the *later* of the two fleet leaders finishes, not the first. The RMG uses "lead boat" (singular) because it describes the single-fleet case; the SIs are authoritative for the shared-course multi-fleet case.

The same rule text appears verbatim in the sample sailing instructions in the **WASZP Race Management Guide v3 (2025)**, which also provides a worked example (p.18-19) that confirms the correct interpretation for the **"Finishing line at gate (mark 2p)"** configuration: the gate list is recorded up until the second lead boat crosses the finishing line, at which point lap counting stops and the finish list begins. This makes the two lists non-overlapping in time — all gate roundings precede all finishing line crossings — and therefore gate-only boats within any lap tier always completed their last lap before any finish boat in the same tier.

The RMG example assumes mark 2p is the finishing line (the common WASZP W/L setup, Course 1). The SailGP course (Course 2 per the Pre-Games 2026 SIs appendix) ends at mark 1s (windward), meaning the finishing line is always separate from whichever gate the counter is stationed at — the app automatically selects "Finishing line with separate pin" when SailGP is chosen. For W/L, a "reach to finish" variant (described in RMG p.6) adds a separate finish pin offset from the leeward gate; this is functionally identical to "Finishing line with separate pin" for scoring purposes. The app supports both configurations via the **Finishing line configuration** setup option, applying the correct lap formula and tier ordering for each.

The Games SIs are not yet published but are expected to be substantively identical. The PRD will be updated once they are available.

### NoR Scoring Review
Per-race scoring is entirely governed by SI 13.2 (Grand Prix Finish). The per-race place numbers produced by the GP Scorer are the input to the series scoring system. No per-race scoring rules were found in the NoR that conflict with or supplement SI 13.2.

### Fleet Start Stagger
The 7.5 + 6.9 combined fleet starts 2 minutes before the 8.2 fleet (SI 11.2). This is informational context only — the app does not model start times.

### Session File Location
Auto-saved to the same directory as the loaded competitor CSV, named `{EventName}_Race{N}_{Date}_session.json`. User may relocate or change name via a "Save As" option.

### Development Conventions
- Virtual environment mandatory; never install globally.
- All code passes `flake8` zero violations before commit, but relaxes line length in flake8 settings to match black line length convention.
- Type hints on all function signatures; docstrings on all functions and classes.
- Never commit real user data or `.env` files.
- Use `importlib.resources` for packaged assets (icons, configs) to support PyInstaller bundles.
- Line length 88 (Black). `black`, `mypy`, `pytest`, `pytest-cov` are dev dependencies.

---

## Glossary

Common abbreviations used throughout this document, the sailing instructions, and race management communications.

| Abbreviation | Full term | Notes |
|---|---|---|
| **GP** | Grand Prix | The finish scoring format where boats are ranked by laps completed, not finish-line crossing order. |
| **RMG** | Race Management Guide | The WASZP Race Management Guide v3 (2025). Supplements the SIs with practical procedures and worked examples. SIs are authoritative where they conflict. |
| **RRS** | Racing Rules of Sailing | The Racing Rules of Sailing 2025–2028, published by World Sailing. The foundational rulebook for all sailboat racing. |
| **NoR** | Notice of Race | The event-level document that governs entry, eligibility, and series scoring (e.g., discard schedules). |
| **SI** | Sailing Instructions | The race-level document that governs on-the-water procedure and scoring. SI 13.2 defines the GP finish rules this app implements. |
| **PRO** | Principal Race Officer | The official responsible for running races on the water. |
| **W/L** | Windward/Leeward | A course type where boats sail upwind to a windward mark and downwind through a leeward gate. The standard WASZP course layout. |
| **WASZP** | — | A one-design foiling dinghy class. Not an acronym. |
| **NRF** | No Recorded Finish | Shorthand for the "Error: No Recorded Finish" finish type — a boat with full gate roundings but missing from the finish list. |
| **BFD** | Black Flag Disqualification | RRS rule 30.4. |
| **DGM** | Disqualification — Gross Misconduct | RRS rule 69.1. |
| **DNC** | Did Not Compete | Boat entered but did not come to the starting area. |
| **DNE** | Non-Excludable Disqualification | Cannot be discarded in series scoring. |
| **DNF** | Did Not Finish | Started but did not finish the race. |
| **DNS** | Did Not Start | Came to the starting area but did not start. |
| **DPI** | Discretionary Penalty Imposed | Penalty at the discretion of the protest committee. |
| **DSQ** | Disqualification | Disqualified after a hearing. |
| **NSC** | Did Not Sail the Course | Started but did not sail the required course. |
| **OCS** | On Course Side | Over the starting line at the start signal. |
| **RDG** | Redress Given | Score adjusted by the protest committee. |
| **RET** | Retired | Retired from the race after starting. |
| **SCP** | Scoring Penalty | Voluntary penalty under RRS rule 44.3(a). |
| **UFD** | U-Flag Disqualification | RRS rule 30.3. |
| **ZFP** | 20% Penalty | Penalty under RRS rule 30.2. |

# Python macOS Desktop App — Project Bootstrap Prompt

Use this document as a prompt when bootstrapping a new Python desktop application that processes data files (CSV, Excel) and ships as a standalone macOS `.app` with a DMG installer.

---

## 1. Python Version & Build System

- **Python**: >=3.10 (target 3.10–3.13)
- **Build backend**: `setuptools` (>=68.0) with `wheel`
- **Project metadata**: `pyproject.toml` (PEP 621), no `setup.py`/`setup.cfg`
- **Version management**: Dynamic — read from `__init__.py` (`__version__` attribute) via `[tool.setuptools.dynamic]`
- **Package layout**: `src` layout (`src/<package_name>/`)
- **Package data**: Include non-Python files (YAML configs, etc.) via `[tool.setuptools.package-data]`

### Entry Points

Define console scripts for both a CLI and GUI interface:

```toml
[project.scripts]
my-app = "my_package.cli:main"
my-app-gui = "my_package.gui:main"
```

Also support `python -m my_package` via a `__main__.py` module.

---

## 2. Core Dependencies

| Purpose | Package |
|---------|---------|
| Data manipulation | `pandas` |
| Numerical computing | `numpy` |
| Excel read/write | `openpyxl` |
| Data classes / models | `attrs` |
| YAML config parsing | `PyYAML` |
| Email validation | `email-validator` |
| GUI drag-and-drop | `tkinterdnd2` |

Try to use the latest stable versions. When pinning use compatible releases (`~=`).

### Pinned Dependencies

Use `pip-tools` to generate a `requirements.txt` lockfile from `pyproject.toml`:

```bash
pip-compile pyproject.toml -o requirements.txt
```

---

## 3. GUI Framework — Tkinter

- **Toolkit**: `tkinter` (ships with Python — no extra install)
- **Drag-and-drop**: `tkinterdnd2` for file drop support
- Use `tkinter.filedialog` for file/directory pickers
- Use `tkinter.messagebox` for alerts and confirmations
- Use `tkinter.ttk` for themed widgets where appropriate
- Handle the case where `tkinterdnd2` is unavailable — fall back gracefully to a file-chooser button

---

## 4. Project Structure

```
project-root/
├── pyproject.toml              # All project metadata, deps, tool config
├── requirements.txt            # Pinned deps (pip-compile output)
├── .flake8                     # Linting config
├── CONTRIBUTING.md             # Dev guidelines
├── MANIFEST.in                 # Source distribution manifest
├── .gitignore
├── src/
│   └── my_package/
│       ├── __init__.py         # __version__ defined here
│       ├── __main__.py         # python -m entry point
│       ├── cli.py              # argparse CLI
│       ├── gui.py              # tkinter GUI
│       ├── config.py           # YAML config loader
│       ├── models.py           # attrs data classes
│       ├── ... (domain modules)
│       ├── settings.yml        # Default config (packaged with app)
│       └── scripts/
│           └── __init__.py
├── tests/
│   └── test_*.py
├── assets/
│   ├── icon.icns               # macOS app icon
│   ├── icon.png                # Source icon (multi-resolution)
│   └── dmg-background.png      # DMG installer background
├── build_macos.sh              # PyInstaller build script
└── create_dmg.sh               # DMG creation script
```

---

## 5. Linting & Formatting

### Flake8

```ini
# .flake8
[flake8]
max-line-length = 88
extend-ignore = E203, W503
```

- Line length 88 matches Black's default
- `E203` ignored (conflicts with Black)
- `W503` ignored (outdated PEP 8 guidance)

### Black (Code Formatter)

```toml
# in pyproject.toml
[tool.black]
line-length = 100
target-version = ["py310"]
```

### Mypy (Type Checking)

```toml
# in pyproject.toml
[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false
```

---

## 6. Testing

### Pytest

```toml
# in pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "--verbose --cov=my_package --cov-report=term-missing"
```

- Coverage via `pytest-cov`
- Use synthetic/fixture CSV files for data-processing tests (keep test data in a `synthetic-tests/` or `tests/fixtures/` directory)
- Never commit real user data

### Dev Dependencies

```toml
[project.optional-dependencies]
dev = [
    "flake8",
    "pytest",
    "pytest-cov",
    "black",
    "mypy",
]
```

---

## 7. macOS Distribution

### Build Dependencies

```toml
[project.optional-dependencies]
build = [
    "pyinstaller",
    "pip-tools",
    "Pillow",
    "dmgbuild",
]
```

### Step 1: Build `.app` with PyInstaller (`build_macos.sh`)

Key PyInstaller flags:

```bash
pyinstaller \
    --name "My App Name" \
    --windowed \
    --icon assets/icon.icns \
    --add-data "src/my_package/settings.yml:my_package" \
    --osx-bundle-identifier com.example.myapp \
    --hidden-import my_package.gui \
    --hidden-import my_package.cli \
    # ... list all submodules as hidden imports ...
    src/my_package/gui.py
```

Important details:
- `--windowed` — no terminal window on launch
- `--add-data` — bundle config/resource files with the app
- `--hidden-import` — PyInstaller's analysis misses dynamic imports; list all modules explicitly
- If using `tkinterdnd2`, locate its `tkdnd/` data directory at build time and add it with `--add-data`
- Ad-hoc code sign the result: `codesign --force --deep --sign - "dist/My App.app"`
- Handle PyInstaller's permission-locked build artifacts gracefully (chmod before rm)

### Step 2: Create DMG Installer (`create_dmg.sh`)

Uses the `dmgbuild` Python library for a professional installer:

```bash
python3 -m dmgbuild -s dmg_settings.py "My App" "MyApp-v${VERSION}.dmg"
```

DMG settings (generated Python file):
- Custom background image
- Icon positioning (app on left, Applications symlink on right)
- 128px icons, hidden toolbar/sidebar/status bar
- Generate SHA256 checksum alongside the DMG

### Step 3: Verify

- Open the DMG, drag app to Applications
- Launch from Applications — no Python install required on the user's machine

---

## 8. CI/CD (GitHub Actions)

Example workflow for building and testing on Windows (adapt for macOS):

```yaml
on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  build:
    runs-on: windows-latest   # or macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[build]"
      - run: pyinstaller --name "My App" --windowed src/my_package/gui.py
      - uses: actions/upload-artifact@v4
        with:
          name: app-bundle
          path: dist/

  test:
    needs: build
    runs-on: windows-latest
    steps:
      - uses: actions/download-artifact@v4
      - run: ./my-app --version
      - run: ./my-app --help
```

---

## 9. Development Setup

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Verify
my-app --version

# Lint
python -m flake8 src/

# Format
python -m black src/

# Type check
python -m mypy src/

# Test
python -m pytest
```

---

## 10. Key Conventions

- **Virtual environment is mandatory** — never install packages globally
- **All code must pass `flake8`** with zero violations before commit
- **No trailing whitespace** on any line (Python, YAML, TOML, shell scripts)
- **Blank lines must be truly blank** (no invisible spaces) in YAML and Markdown
- **Type hints** on all function signatures
- **Docstrings** on all public functions and classes
- **Never commit** sensitive data, real user data, or `.env` files
- Use `importlib.resources` to load packaged data files (YAML configs, etc.) so they work both in development and inside a PyInstaller bundle

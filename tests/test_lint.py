"""Lint and type-check tests.

Runs black, flake8, mypy, and actionlint as subprocess calls so that
``pytest`` alone catches formatting, style, type, and CI-workflow errors.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_black() -> None:
    """All Python files must be formatted with black."""
    result = subprocess.run(
        ["black", "--check", "."],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert (
        result.returncode == 0
    ), f"black --check failed:\n{result.stdout}\n{result.stderr}"


def test_flake8() -> None:
    """No flake8 violations in src/ or tests/."""
    result = subprocess.run(
        ["flake8", "src/", "tests/"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"flake8 failed:\n{result.stdout}\n{result.stderr}"


def test_mypy() -> None:
    """src/ must pass strict mypy type checking."""
    result = subprocess.run(
        ["mypy", "src/"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"mypy failed:\n{result.stdout}\n{result.stderr}"


@pytest.mark.skipif(
    shutil.which("actionlint") is None,
    reason="actionlint not installed",
)
def test_actionlint() -> None:
    """GitHub Actions workflow files must pass actionlint."""
    workflows = REPO_ROOT / ".github" / "workflows"
    if not workflows.is_dir():
        pytest.skip("no .github/workflows/ directory")
    result = subprocess.run(
        ["actionlint"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert (
        result.returncode == 0
    ), f"actionlint failed:\n{result.stdout}\n{result.stderr}"

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_release_version.py"


def test_release_version_surfaces_are_consistent():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--expected", "0.1.5"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Release version consistency verified: 0.1.5" in result.stdout


def test_release_version_rejects_mismatched_tag():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--expected", "9.9.9"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "expected '9.9.9'" in result.stderr

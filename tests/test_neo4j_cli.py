"""Subprocess test for ``python -m twin.sync.neo4j`` in fake mode."""

from __future__ import annotations

import subprocess
import sys


def test_cli_fake_mode() -> None:
    """Run the sync CLI in TESTING=1 mode and verify it exits cleanly."""
    result = subprocess.run(
        [sys.executable, "-m", "twin.sync.neo4j"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
        env={**__import__("os").environ, "TESTING": "1"},
    )
    assert result.returncode == 0
    output = result.stdout + result.stderr
    assert "rebuilt=True" in output
    assert "Done: 1/1" in output

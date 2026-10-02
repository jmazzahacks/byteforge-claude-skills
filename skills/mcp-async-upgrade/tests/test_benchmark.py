"""The measurement harness must fail closed when a caller's result is wrong."""
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from benchmark import measure


@pytest.mark.anyio
async def test_failed_identity_checks_do_not_count_as_throughput():
    async def wrong_result(arguments):
        return {"identity": "wrong-fixture", "mode": "fast"}

    tool = SimpleNamespace(run=wrong_result)
    mcp = SimpleNamespace(_tool_manager=SimpleNamespace(get_tool=lambda name: tool))
    row = await measure(mcp, 1, 0, "sync")
    assert row["errors"] == ["ValueError", "ValueError"]
    assert row["identity_checks_passed"] == 0
    assert row["throughput_calls_s"] == 0


def test_optimized_python_still_rejects_wrong_identity():
    script = """
import asyncio
from types import SimpleNamespace
from benchmark import invoke
from async_example.server import caller

async def wrong_result(arguments):
    return {"identity": "wrong-fixture", "mode": "fast"}

async def check():
    before = caller.get()
    tool = SimpleNamespace(run=wrong_result)
    mcp = SimpleNamespace(_tool_manager=SimpleNamespace(get_tool=lambda name: tool))
    try:
        await invoke(mcp, "fast", "expected-fixture", 0)
    except ValueError:
        if caller.get() != before:
            raise RuntimeError("Caller context leaked after mismatch")
    else:
        raise RuntimeError("Optimized Python silently accepted the wrong identity")

asyncio.run(check())
"""
    result = subprocess.run(
        [sys.executable, "-O", "-c", script],
        cwd=Path(__file__).resolve().parents[1] / "scripts",
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "assets"), str(ROOT / "scripts")]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def local_backend():
    from loopback import backend
    with backend() as instance:
        yield instance

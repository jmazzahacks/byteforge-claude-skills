"""Compare registered blocking/async tools against a synthetic loopback API."""
import argparse
import asyncio
from contextlib import contextmanager
import hashlib
import importlib.metadata as metadata
import json
import logging
import math
from pathlib import Path
import platform
import sys
import time
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "assets"))

import httpx
from async_example.server import Caller, ExampleServer, PoolSettings, caller
from loopback import backend
from sync_reference import synchronous_server


def percentiles(values):
    ordered = sorted(values)
    return {f"p{p}": ordered[max(0, math.ceil(len(ordered) * p / 100) - 1)]
            if ordered else None for p in (50, 95, 99)}


@contextmanager
def pool_probe(enabled):
    """Harness-only patch; fail rather than invent metrics on unknown versions."""
    rows = []
    if not enabled:
        yield rows
        return
    if metadata.version("httpcore") != "1.0.9":
        raise RuntimeError("Pool probe requires httpcore==1.0.9; re-audit before changing")
    from httpcore._async.connection_pool import AsyncPoolRequest
    original = AsyncPoolRequest.wait_for_connection

    async def measured(self, timeout=None):
        queued = self.is_queued()
        start = time.perf_counter()
        try:
            return await original(self, timeout)
        finally:
            rows.append({"ms": (time.perf_counter() - start) * 1000, "queued": queued})

    with patch.object(AsyncPoolRequest, "wait_for_connection", measured):
        yield rows


async def invoke(mcp, name, token, delay):
    reset = caller.set(Caller(is_http=True, token=token))
    try:
        # Exercises actual registered-tool validation and wrappers. This private
        # lookup is pinned to MCP 1.29.1; ASGI routing is tested separately.
        tool = mcp._tool_manager.get_tool(name)
        result = await tool.run({"delay": delay} if name == "slow" else {})
        if result != {"identity": token, "mode": name}:
            raise ValueError("identity/result mismatch")
    finally:
        caller.reset(reset)


async def measure(mcp, count, delay, variant):
    service, completion, errors, heartbeat = [], [], [], []
    successes = 0
    done = False
    start = time.perf_counter()

    async def call(index):
        nonlocal successes
        begin = time.perf_counter()
        try:
            await invoke(mcp, "slow", f"fixture-{index}", delay)
            successes += 1
        except Exception as exc:
            errors.append(type(exc).__name__)
        service.append((time.perf_counter() - begin) * 1000)
        completion.append((time.perf_counter() - start) * 1000)

    async def quick():
        nonlocal successes
        await asyncio.sleep(0.01)
        begin = time.perf_counter()
        try:
            await invoke(mcp, "fast", "fixture-fast", 0)
            successes += 1
        except Exception as exc:
            errors.append(type(exc).__name__)
        return {"scheduled_ms": 10, "actual_start_ms": (begin - start) * 1000,
                "service_ms": (time.perf_counter() - begin) * 1000,
                "completion_ms": (time.perf_counter() - start) * 1000}

    async def beat():
        while not done:
            due = time.perf_counter() + 0.01
            await asyncio.sleep(0.01)
            heartbeat.append(max(0, (time.perf_counter() - due) * 1000))

    with pool_probe(variant == "async") as acquisitions:
        pulse, fast = asyncio.create_task(beat()), asyncio.create_task(quick())
        await asyncio.sleep(0)  # Arm the timers before dispatch can block.
        await asyncio.gather(*(call(index) for index in range(count)))
        fast_result = await fast
        elapsed = time.perf_counter() - start
        done = True
        await pulse
    return {
        "variant": variant, "slow_calls": count, "backend_delay_ms": delay * 1000,
        "wave_ms": elapsed * 1000, "throughput_calls_s": successes / elapsed,
        "service_ms": percentiles(service), "completion_ms": percentiles(completion),
        "fast": fast_result, "heartbeat_delay_max_ms": max(heartbeat, default=0),
        "errors": errors, "identity_checks_passed": successes,
        "pool_acquire_ms": percentiles([x["ms"] for x in acquisitions]),
        "pool_acquire_max_ms": max((x["ms"] for x in acquisitions), default=None),
        "pool_acquisitions": len(acquisitions) if variant == "async" else None,
        "queued_acquisitions": sum(x["queued"] for x in acquisitions) if variant == "async" else None,
    }


async def run(args):
    if metadata.version("mcp") != "1.29.1":
        raise RuntimeError("Registered-tool probe requires mcp==1.29.1; re-audit before changing")
    versions = {name: metadata.version(name) for name in
                ("mcp", "httpx", "httpcore", "anyio", "starlette", "pydantic")}
    print(json.dumps({"kind": "environment", "python": platform.python_version(), "versions": versions,
        "boundary": "registered Tool.run + SDK + loopback sockets; excludes ingress/proxy/backend production load",
        "pool_note": "httpcore 1.0.9 private wait_for_connection; includes immediate acquisitions; sync unmeasured",
        "source_sha256": {str(p.relative_to(SKILL)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(SKILL.rglob('*.py'))},
        "connections": args.connections, "idle_connections": args.connections, "pool_timeout_s": 1}))
    failed = False
    with backend() as (url, _):
        for repeat in range(args.repeat):
            for count in (1, 10, 100):
                for warmth in ("cold", "warm"):
                    # Alternate order to reduce a consistent first-variant bias.
                    for variant in (("sync", "async") if repeat % 2 == 0 else ("async", "sync")):
                        settings = PoolSettings(connections=args.connections, idle_connections=args.connections)

                        async def sample(mcp):
                            if warmth == "warm":
                                await asyncio.gather(*(invoke(mcp, "fast", f"warm-{i}", 0)
                                                       for i in range(min(count, args.connections))))
                            row = await measure(mcp, count, args.delay, variant)
                            row.update(repeat=repeat, warmth=warmth)
                            return row

                        if variant == "sync":
                            with httpx.Client(trust_env=False, limits=httpx.Limits(
                                max_connections=args.connections,
                                max_keepalive_connections=args.connections)) as transport:
                                row = await sample(synchronous_server(url, transport))
                        else:
                            server = ExampleServer(url, settings)
                            async with server.runtime.open():
                                row = await sample(server.mcp)
                        failed |= bool(row["errors"])
                        print(json.dumps(row), flush=True)
    if failed:
        raise SystemExit("Benchmark contained errors; inspect JSONL")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--delay", type=float, default=0.05)
    parser.add_argument("--connections", type=int, default=20)
    args = parser.parse_args()
    if args.repeat < 1 or args.connections < 1 or not 0 <= args.delay <= 2:
        parser.error("repeat/connections must be positive; delay must be between 0 and 2 seconds")
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(run(args))

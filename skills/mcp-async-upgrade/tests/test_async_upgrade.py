import asyncio
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

import anyio
import httpx
import pytest

from async_example.client import AsyncBackendClient, BackendError, SyncBackendClient
from async_example.server import BackendRuntime, Caller, CallerMiddleware, ExampleServer, PoolSettings, caller, caller_token
from benchmark import invoke, pool_probe
from sync_reference import synchronous_server


@pytest.mark.anyio
async def test_registered_tool_schemas_and_async_wrappers(local_backend):
    url, _ = local_backend
    candidate = ExampleServer(url)
    with httpx.Client(trust_env=False) as client:
        baseline = synchronous_server(url, client)
        old = [tool.model_dump() for tool in await baseline.list_tools()]
        new = [tool.model_dump() for tool in await candidate.mcp.list_tools()]
        assert old == new
        assert all(tool.is_async for tool in candidate.mcp._tool_manager.list_tools())
        assert not any(tool.is_async for tool in baseline._tool_manager.list_tools())
    async with candidate.runtime.open():
        await invoke(candidate.mcp, "slow", "fixture-slow", 0)
        await invoke(candidate.mcp, "fast", "fixture-fast", 0)


@pytest.mark.anyio
async def test_shared_client_defaults_and_response_cookies_never_mix_callers(local_backend):
    url, backend = local_backend
    async with httpx.AsyncClient(auth=("wrong", "identity"), cookies={"session": "wrong"},
                                  headers={"Authorization": "Bearer wrong"},
                                  params={"api_key": "wrong"}, trust_env=False) as transport:
        async def fetch(index):
            async with AsyncBackendClient(url, f"fixture-{index}", transport=transport) as client:
                return await client.fetch("slow", 0.01)
        results = await asyncio.gather(*(fetch(i) for i in range(10)))
        assert [r.identity for r in results] == [f"fixture-{i}" for i in range(10)]
        await fetch(10)  # Response Set-Cookie must not carry into a later caller.
        assert not transport.is_closed  # Per-call wrappers only borrowed it.
        assert len(backend.records) == 11
        assert all(r["cookie"] is None and "api_key" not in r["query"] for r in backend.records)
        assert {r["authorization"] for r in backend.records} == {f"Bearer fixture-{i}" for i in range(11)}


@pytest.mark.anyio
async def test_full_stateless_http_lifecycle_and_mixed_auth(local_backend, monkeypatch):
    url, backend = local_backend
    monkeypatch.setenv("EXAMPLE_API_KEY", "stdio-must-not-leak")
    server = ExampleServer(url)
    app = server.http_app()
    # Count actual per-process clients, not per-tool wrapper objects.
    original = httpx.AsyncClient
    created = []
    def counted(*args, **kwargs):
        transport = original(*args, **kwargs)
        created.append(transport)
        return transport
    async with original(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000") as wire:
        with patch("async_example.server.httpx.AsyncClient", counted):
            async with app.router.lifespan_context(app):
                shared = server.runtime.transport
                headers = {"Accept": "application/json, text/event-stream"}
                init = await wire.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 1,
                    "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                    "clientInfo": {"name": "fixture", "version": "1"}}})
                assert init.status_code == 200, init.text
                assert "result" in init.json()

                async def call(index, auth):
                    request_headers = dict(headers)
                    if auth is not None:
                        request_headers["Authorization"] = auth
                    response = await wire.post("/mcp", headers=request_headers, json={"jsonrpc": "2.0",
                        "id": index + 2, "method": "tools/call", "params": {
                        "name": "slow" if index % 2 else "fast",
                        "arguments": {"delay": 0.01} if index % 2 else {}}})
                    assert response.status_code == 200, response.text
                    assert "mcp-session-id" not in response.headers
                    return response.json()["result"]

                valid = [f"Bearer fixture-{i}" for i in range(10)]
                invalid = [None, "Basic dGVzdDp0ZXN0", "Bearer ", "Bearer"]
                results = await asyncio.gather(*(call(i, token) for i, token in enumerate(valid + invalid)))
                for i, result in enumerate(results[:10]):
                    assert result.get("isError", False) is False
                    payload = json.loads(result["content"][0]["text"])
                    assert payload["identity"] == f"fixture-{i}"
                assert all(result["isError"] for result in results[10:])
                assert len(backend.records) == 10
                assert server.runtime.transport is shared
                assert len(created) == 1
                assert caller.get() == Caller()
        assert shared.is_closed and server.runtime.transport is None


@pytest.mark.anyio
@pytest.mark.parametrize("outcome", ["success", "error", "cancel"])
async def test_context_restoration(outcome):
    before = Caller(True, "outer-fixture")
    token = caller.set(before)
    async def inner(scope, receive, send):
        assert caller.get() == Caller(True, "inner-fixture")
        if outcome == "error":
            raise LookupError("fixture error")
        if outcome == "cancel":
            await anyio.lowlevel.checkpoint()
    middleware = CallerMiddleware(inner)
    scope = {"type": "http", "headers": [(b"authorization", b"Bearer inner-fixture")]}
    try:
        if outcome == "error":
            with pytest.raises(LookupError):
                await middleware(scope, None, None)
        elif outcome == "cancel":
            with anyio.CancelScope() as cancellation:
                cancellation.cancel()
                await middleware(scope, None, None)
            assert cancellation.cancelled_caught
        else:
            await middleware(scope, None, None)
        assert caller.get() == before
    finally:
        caller.reset(token)


@pytest.mark.anyio
async def test_duplicate_auth_does_not_fall_back_to_env(monkeypatch):
    monkeypatch.setenv("EXAMPLE_API_KEY", "stdio-fixture")
    assert caller_token() == "stdio-fixture"
    async def inner(*_):
        assert caller.get().is_http
        with pytest.raises(ValueError):
            caller_token()
    await CallerMiddleware(inner)({"type": "http", "headers": [
        (b"authorization", b"Bearer one"), (b"authorization", b"Bearer two")]}, None, None)
    assert caller_token() == "stdio-fixture"


@pytest.mark.anyio
@pytest.mark.parametrize("outcome", ["success", "error", "cancel"])
async def test_owned_client_cleanup(outcome, monkeypatch):
    class CheckedClient(httpx.AsyncClient):
        async def aclose(self):
            await anyio.lowlevel.checkpoint()
            await super().aclose()
    transport = CheckedClient(trust_env=False)
    monkeypatch.setattr("async_example.client.httpx.AsyncClient", lambda **_: transport)
    client = AsyncBackendClient("http://127.0.0.1", "fixture")
    if outcome == "cancel":
        with anyio.CancelScope() as scope:
            scope.cancel()
            async with client:
                await anyio.lowlevel.checkpoint()
        assert scope.cancelled_caught
    elif outcome == "error":
        with pytest.raises(LookupError):
            async with client:
                raise LookupError()
    else:
        async with client:
            pass
    assert transport.is_closed and client.closed
    await client.aclose()  # Idempotent.


@pytest.mark.anyio
async def test_runtime_cleanup_in_cancelled_scope_and_reentry():
    runtime = BackendRuntime(PoolSettings())
    with anyio.CancelScope() as scope:
        async with runtime.open() as transport:
            with pytest.raises(RuntimeError):
                async with runtime.open():
                    pass
            scope.cancel()
            await anyio.lowlevel.checkpoint()
    assert scope.cancelled_caught and transport.is_closed and runtime.transport is None
    async with runtime.open() as next_transport:
        assert next_transport is not transport
    assert next_transport.is_closed


@pytest.mark.anyio
async def test_read_timeout_and_recovery(local_backend):
    url, _ = local_backend
    async with AsyncBackendClient(url, "fixture", timeout=httpx.Timeout(0.03)) as client:
        with pytest.raises(httpx.ReadTimeout):
            await client.fetch("slow", 0.2)
        assert (await client.fetch()).identity == "fixture"


@pytest.mark.anyio
async def test_real_pool_timeout_cancellation_and_recovery(local_backend):
    url, backend = local_backend
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=1), trust_env=False) as transport:
        async with AsyncBackendClient(url, "fixture", transport=transport,
                                      timeout=httpx.Timeout(2, pool=0.03)) as client:
            held = asyncio.create_task(client.fetch("hold"))
            try:
                with anyio.fail_after(2):
                    while not backend.started.is_set():
                        await anyio.sleep(0.001)
                with pool_probe(True) as waits:
                    with pytest.raises(httpx.PoolTimeout):
                        await client.fetch()
                assert any(row["queued"] for row in waits)
                held.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await held
                assert (await client.fetch()).identity == "fixture"
            finally:
                backend.release.set()
                if not held.done():
                    held.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await held


@pytest.mark.anyio
@pytest.mark.parametrize("mode,status", [("error", 503), ("redirect", 307)])
async def test_error_parity_and_no_retry_or_redirect(local_backend, mode, status):
    url, backend = local_backend
    with SyncBackendClient(url, "fixture") as sync:
        with pytest.raises(BackendError) as old:
            sync.fetch(mode)
    async with AsyncBackendClient(url, "fixture") as client:
        with pytest.raises(BackendError) as new:
            await client.fetch(mode)
    assert old.value.status == new.value.status == status
    assert len(backend.records) == 2


def test_sync_client_compatibility_and_borrowed_cleanup(local_backend):
    url, _ = local_backend
    with httpx.Client(trust_env=False) as transport:
        with SyncBackendClient(url, "fixture", transport=transport) as client:
            assert asdict(client.fetch()) == {"identity": "fixture", "mode": "fast"}
        assert not transport.is_closed
        with pytest.raises(RuntimeError):
            client.fetch()


@pytest.mark.anyio
async def test_stdio_owns_runtime_for_entire_run(local_backend, monkeypatch):
    url, _ = local_backend
    monkeypatch.setenv("EXAMPLE_API_KEY", "fixture-stdio")
    server = ExampleServer(url)
    seen = []
    async def run():
        seen.append(server.runtime.transport)
        assert (await server.fetch("fast", 0))["identity"] == "fixture-stdio"
        raise LookupError("simulated stdio failure")
    monkeypatch.setattr(server.mcp, "run_stdio_async", run)
    with pytest.raises(LookupError):
        await server.run_stdio()
    assert seen[0].is_closed and server.runtime.transport is None


@pytest.mark.anyio
async def test_borrowed_client_survives_cancelled_wrapper(local_backend):
    url, _ = local_backend
    async with httpx.AsyncClient(trust_env=False) as transport:
        wrapper = AsyncBackendClient(url, "fixture", transport=transport)
        with anyio.CancelScope() as scope:
            async with wrapper:
                scope.cancel()
                await anyio.lowlevel.checkpoint()
        assert scope.cancelled_caught and wrapper.closed
        assert not transport.is_closed
        async with AsyncBackendClient(url, "next-fixture", transport=transport) as next_client:
            assert (await next_client.fetch()).identity == "next-fixture"


@pytest.mark.anyio
async def test_real_stdio_protocol_roundtrip(local_backend):
    url, backend = local_backend
    assets = Path(__file__).resolve().parents[1] / "assets"
    env = dict(os.environ, PYTHONPATH=str(assets), EXAMPLE_API_KEY="stdio-fixture",
               EXAMPLE_BACKEND_URL=url, MCP_TRANSPORT="stdio", PYTHONDONTWRITEBYTECODE="1")
    process = await asyncio.create_subprocess_exec(sys.executable, "-m", "async_example.server",
        env=env, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)
    stderr = asyncio.create_task(process.stderr.read())

    async def send(method, params, ident=None):
        message = {"jsonrpc": "2.0", "method": method, "params": params}
        if ident is not None:
            message["id"] = ident
        process.stdin.write((json.dumps(message) + "\n").encode())
        await process.stdin.drain()
        if ident is None:
            return
        # Strict JSON parsing rejects any diagnostic pollution of stdout.
        line = await asyncio.wait_for(process.stdout.readline(), 5)
        result = json.loads(line)
        assert result["jsonrpc"] == "2.0" and result["id"] == ident, result
        return result["result"]

    try:
        await send("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
            "clientInfo": {"name": "fixture", "version": "1"}}, 1)
        await send("notifications/initialized", {})
        tools = await send("tools/list", {}, 2)
        assert {t["name"] for t in tools["tools"]} == {"slow", "fast"}
        result = await send("tools/call", {"name": "fast", "arguments": {}}, 3)
        assert json.loads(result["content"][0]["text"])["identity"] == "stdio-fixture"
        assert len(backend.records) == 1
        process.stdin.close()
        await asyncio.wait_for(process.wait(), 5)
        assert process.returncode == 0, (await stderr).decode()
        assert await process.stdout.read() == b""
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        await stderr

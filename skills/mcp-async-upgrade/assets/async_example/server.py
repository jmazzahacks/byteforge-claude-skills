"""MCP 1.29.1 example: process-owned transport, request-owned identity."""
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from functools import wraps
import logging
import os
import sys

import anyio
import httpx
from mcp.server.fastmcp import FastMCP

from .client import AsyncBackendClient


@dataclass(frozen=True)
class Caller:
    is_http: bool = False
    token: str | None = None


caller: ContextVar[Caller] = ContextVar("example_caller", default=Caller())


def caller_token() -> str:
    context = caller.get()
    # HTTP with no bearer is NOT stdio. Never borrow a process credential.
    token = context.token if context.is_http else os.environ.get("EXAMPLE_API_KEY")
    if not token or any(char.isspace() for char in token):
        raise ValueError("Missing caller bearer credential")
    return token


class CallerMiddleware:
    """Raw ASGI middleware; preserves streaming and restores nested contexts."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        values = [v for k, v in scope.get("headers", []) if k.lower() == b"authorization"]
        token = None
        if len(values) == 1:
            scheme, separator, raw = values[0].decode("latin-1").partition(" ")
            raw = raw.strip()
            if separator and scheme.lower() == "bearer" and raw and not any(c.isspace() for c in raw):
                token = raw
        reset = caller.set(Caller(is_http=True, token=token))
        try:
            await self.app(scope, receive, send)
        finally:
            caller.reset(reset)


@dataclass(frozen=True)
class PoolSettings:
    # Demonstration values, not production capacity recommendations.
    connections: int = 20
    idle_connections: int = 10
    idle_expiry: float = 5
    request_timeout: float = 10
    pool_timeout: float = 1


class BackendRuntime:
    def __init__(self, settings: PoolSettings):
        self.settings = settings
        self.transport: httpx.AsyncClient | None = None

    @asynccontextmanager
    async def open(self):
        if self.transport is not None:
            raise RuntimeError("Backend runtime already open")
        transport = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=self.settings.connections,
                               max_keepalive_connections=self.settings.idle_connections,
                               keepalive_expiry=self.settings.idle_expiry),
            trust_env=False,
        )
        self.transport = transport
        try:
            yield transport
        finally:
            self.transport = None
            with anyio.CancelScope(shield=True):
                await transport.aclose()


def require_caller(function):
    """Keep wrappers async and preserve signatures used for tool schemas."""
    @wraps(function)
    async def wrapped(*args, **kwargs):
        caller_token()  # Put existing async identity/gate checks here and await them.
        return await function(*args, **kwargs)
    return wrapped


class ExampleServer:
    def __init__(self, backend_url: str, settings: PoolSettings | None = None):
        self.backend_url = backend_url
        self.runtime = BackendRuntime(settings or PoolSettings())
        self.mcp = FastMCP("example-service", stateless_http=True, json_response=True)

        @self.mcp.tool()
        @require_caller
        async def slow(delay: float = 0.05) -> dict:
            """Exercise a backend request with a synthetic delay."""
            return await self.fetch("slow", delay)

        @self.mcp.tool()
        @require_caller
        async def fast() -> dict:
            """Exercise a backend request without a synthetic delay."""
            return await self.fetch("fast", 0)

    async def fetch(self, mode, delay):
        token = caller_token()
        transport = self.runtime.transport
        if transport is None:
            raise RuntimeError("Backend runtime is not open")
        settings = self.runtime.settings
        async with AsyncBackendClient(
            self.backend_url, token, transport=transport,
            timeout=httpx.Timeout(settings.request_timeout, pool=settings.pool_timeout),
        ) as client:
            return asdict(await client.fetch(mode, delay))

    def http_app(self):
        app = self.mcp.streamable_http_app()
        framework_lifespan = app.router.lifespan_context

        @asynccontextmanager
        async def lifespan(app):
            # Outer transport outlives every independent stateless request.
            # Retain the framework's own session-manager startup/shutdown.
            async with self.runtime.open():
                async with framework_lifespan(app) as state:
                    yield state

        app.router.lifespan_context = lifespan
        app.add_middleware(CallerMiddleware)
        return app

    async def run_stdio(self):
        async with self.runtime.open():
            await self.mcp.run_stdio_async()


def main():
    backend_url = os.environ["EXAMPLE_BACKEND_URL"]
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport not in {"stdio", "streamable-http"}:
        raise ValueError("Use stdio or streamable-http for this example")
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, force=True)
    server = ExampleServer(backend_url)
    if transport == "stdio":
        anyio.run(server.run_stdio)
    else:
        import uvicorn
        uvicorn.run(server.http_app(), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()

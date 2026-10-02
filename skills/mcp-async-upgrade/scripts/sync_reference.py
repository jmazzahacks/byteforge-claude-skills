"""Intentionally blocking reference for local measurements, never deployment."""
from dataclasses import asdict
from functools import wraps

from mcp.server.fastmcp import FastMCP
from async_example.client import SyncBackendClient
from async_example.server import caller_token


def synchronous_server(base_url, transport):
    mcp = FastMCP("blocking-reference", stateless_http=True, json_response=True)

    def gate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            caller_token()
            return function(*args, **kwargs)
        return wrapped

    def fetch(mode, delay):
        with SyncBackendClient(base_url, caller_token(), transport=transport) as client:
            return asdict(client.fetch(mode, delay))

    @mcp.tool()
    @gate
    def slow(delay: float = 0.05) -> dict:
        """Exercise a backend request with a synthetic delay."""
        return fetch("slow", delay)

    @mcp.tool()
    @gate
    def fast() -> dict:
        """Exercise a backend request without a synthetic delay."""
        return fetch("fast", 0)

    return mcp

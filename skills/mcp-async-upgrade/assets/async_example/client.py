"""Shared endpoint contract with synchronous and asynchronous clients.

Adapt the endpoint, typed result and error mapping to the existing SDK. The
synthetic /work endpoint exists only to make this example executable.
"""
from dataclasses import dataclass

import anyio
import httpx


class BackendError(Exception):
    def __init__(self, status: int):
        self.status = status
        super().__init__(f"Backend returned HTTP {status}")


@dataclass(frozen=True)
class WorkResult:
    identity: str
    mode: str


def parse_response(response: httpx.Response) -> WorkResult:
    if response.status_code != 200:
        # Replace with the existing SDK's status -> typed error mapping.
        # Do not put response bodies, URLs or credentials in public errors.
        raise BackendError(response.status_code)
    payload = response.json()
    return WorkResult(identity=payload["identity"], mode=payload["mode"])


def make_request(base_url, token, mode, delay, timeout):
    if not token or any(char.isspace() for char in token):
        raise ValueError("A nonempty bearer token is required")
    # base_url is trusted service configuration, never a tool argument.
    # A fresh Request avoids merging a borrowed client's cookies, default
    # headers, query parameters or base URL into the caller's request.
    return httpx.Request(
        "GET", base_url.rstrip("/") + "/work",
        params={"mode": mode, "delay": delay},
        headers={"Authorization": f"Bearer {token}"},
        extensions={"timeout": timeout.as_dict()},
    )


class AsyncBackendClient:
    def __init__(self, base_url: str, token: str, *,
                 transport: httpx.AsyncClient | None = None,
                 timeout: httpx.Timeout | None = None):
        self.base_url, self.token = base_url, token
        self.timeout = timeout if timeout is not None else httpx.Timeout(10, pool=1)
        self.owns_transport = transport is None
        self.transport = transport if transport is not None else httpx.AsyncClient(trust_env=False)
        self.closed = False

    async def __aenter__(self):
        if self.closed:
            raise RuntimeError("Client is closed")
        return self

    async def __aexit__(self, *_):
        await self.aclose()

    async def aclose(self):
        if self.closed:
            return
        if self.owns_transport:
            # Cleanup must run even in an already-cancelled AnyIO scope.
            # Operations themselves remain cancellable and are never retried.
            with anyio.CancelScope(shield=True):
                await self.transport.aclose()
        self.closed = True

    async def fetch(self, mode: str = "fast", delay: float = 0) -> WorkResult:
        if self.closed:
            raise RuntimeError("Client is closed")
        request = make_request(self.base_url, self.token, mode, delay, self.timeout)
        response = await self.transport.send(request, auth=None, follow_redirects=False)
        return parse_response(response)


class SyncBackendClient:
    """Existing callers retain the synchronous API and shared result/error map."""
    def __init__(self, base_url: str, token: str, *, transport=None, timeout=None):
        self.base_url, self.token = base_url, token
        self.timeout = timeout if timeout is not None else httpx.Timeout(10, pool=1)
        self.owns_transport = transport is None
        self.transport = transport if transport is not None else httpx.Client(trust_env=False)
        self.closed = False

    def __enter__(self):
        if self.closed:
            raise RuntimeError("Client is closed")
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        if not self.closed and self.owns_transport:
            self.transport.close()
        self.closed = True

    def fetch(self, mode: str = "fast", delay: float = 0) -> WorkResult:
        if self.closed:
            raise RuntimeError("Client is closed")
        request = make_request(self.base_url, self.token, mode, delay, self.timeout)
        return parse_response(self.transport.send(request, auth=None, follow_redirects=False))

# Implementation boundaries

Read with `assets/async_example/client.py` and `server.py`. The example implements
a synthetic read-only endpoint so resource and identity behavior can be executed
without a project-specific backend. Replace the endpoint contract, not merely the
module name, when applying it to a service.

## Client ownership and compatibility

`SyncBackendClient` and `AsyncBackendClient` share `make_request`, `WorkResult` and
`parse_response`. The latter demonstrates preserving a status-bearing error;
reuse the actual SDK's typed errors and payload validation when migrating it.
Exercise all status cases, empty/malformed bodies, endpoint-specific timeouts,
pagination and optional arguments from the existing contract matrix. Keep public
method signatures/defaults and synchronous consumers compatible.

Borrowed transports may carry defaults left by other callers. HTTPX high-level
request/build methods merge client and request headers, cookies and query params.
The example creates a fresh Request, supplies its own timeout extension and
credential, and disables client auth and redirects on send. It does not inherit
the borrowed client's base URL. Response bodies are consumed by normal send;
if adapting to streamed responses, close each response in `finally` too.
Existing custom auth handlers, request hooks and custom transports remain trusted
code: explicit requests do not sandbox hooks that intentionally rewrite them.

No request is retried automatically. This matters even more for writes: a lost
response after the backend committed is not evidence that the action failed.
Keep the service's idempotency-key or reconciliation policy, if any.

The SDK-created async transport closes in a shielded scope; wrappers never close
borrowed transports. A shared transport's owner must wait for its users to finish
before closing it. Do not close a shared SDK instance concurrently with active
operations. AnyIO shielding covers cancellation through AnyIO scopes; verify the
actual host framework's shutdown/cancellation mechanism rather than promising
protection against arbitrary repeated low-level task cancellation.

## Lifecycle and request context

`ExampleServer` has an instance-owned `BackendRuntime`, so tests and multiple
server objects do not accidentally share a global pool. It rejects double-open,
creates its HTTPX client on startup, clears the reference and closes on shutdown.
The process-lifespan wrapper retains the framework's lifespan and yielded state.
Do not replace that wrapper with a per-request MCP lifespan just because both
APIs are named "lifespan". With another framework version, instrument creation,
reuse across stateless requests, and closure before selecting an integration.

`CallerMiddleware` is plain ASGI middleware. It neither buffers bodies nor
creates a response task that could change ContextVar propagation. Every HTTP
request, even an unauthenticated one, establishes an HTTP context. It accepts one
nonempty bearer header and treats duplicate/malformed credentials as absent;
the backend-dependent tools reject them before sending anything. This example
does not validate token signatures or replace a gateway's authorization policy.

`require_caller` demonstrates an async wrapper preserving the original function
signature. In a real service, await registration, access checks and identity
enrichment before the tool body; leaving a synchronous lookup in the wrapper
still blocks every concurrent request. Test app-specific wrappers, including
request-response gates, using the existing project's regression suite.

The CLI demonstrates stdio or stateless Streamable HTTP on loopback. It keeps
stdout protocol-safe. Configure the real service's bind/proxy/logging settings
through its existing deployment conventions; keep its endpoint and host/origin
protections. Build the HTTP app once per serving lifecycle.

## Sizing and temporary offload

Set connect/read/write/pool timeout budgets separately where needed. A long
backend operation may need a longer read budget without an equally long local
pool wait. HTTPX read timeouts are inactivity timeouts, not total request
deadlines; add the project's overall operation deadline separately if required.
Multiply pool limits by workers/replicas and account for the backend's limits.
PoolTimeout is transport pressure, not an authorization or tenant-rate decision.

When native async is unavailable, allocate a bounded process-local AnyIO thread
limiter and await `to_thread.run_sync` with `abandon_on_cancel=False`. Underlying
library timeouts still matter: the waiting task can defer cancellation until the
worker finishes. With abandonment enabled the worker continues anyway; do not
release application-level capacity as if that work had stopped. CPU-heavy work
needs a separate design, often a process pool or task worker, with its own limits.

## Primary API references

- [HTTPX client merging and explicit Request objects](https://www.python-httpx.org/advanced/clients/)
- [HTTPX asynchronous clients and cleanup](https://www.python-httpx.org/async/)
- [AnyIO shielding and cancellation](https://anyio.readthedocs.io/en/stable/cancellation.html)
- [AnyIO thread offload and cancellation limits](https://anyio.readthedocs.io/en/stable/threads.html)

Use the installed MCP source as the authority for dispatch and lifespan details;
the harness pins its private inspection points and rejects unknown versions.

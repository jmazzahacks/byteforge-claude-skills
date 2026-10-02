---
name: mcp-async-upgrade
description: Migrate an existing Python MCP server and its blocking SDK calls to native async I/O, preserving tool contracts, synchronous SDK consumers, caller isolation, and transport lifecycle. Use when slow backend requests serialize MCP tools or block the event loop; includes executable examples and a local concurrency benchmark.
---

# Upgrade an Existing Python MCP Server to Async I/O

Audit the actual call path, migrate network I/O, prove isolation and resource
cleanup, then release using the project's established deployment workflow.
Changing `def` to `async def` while retaining `requests`, blocking database calls,
or synchronous decorators does not make the path non-blocking.

## 1. Establish the scope and baseline

Inspect the repository and existing decisions first. Ask only for missing facts:

- Which MCP server and SDK/library repositories are in scope? Which synchronous
  consumers must remain supported?
- What transports, public tool schemas, endpoint paths, auth/gate semantics, and
  error types must remain compatible?
- What concurrency and backend latency should the migration handle? What pool
  limits/timeouts already exist? Use measurements to choose new values.
- Is the requested deliverable local implementation, publication, or deployment?
  Complete authorized work; a migration request alone does not authorize release.

Record the installed Python/framework/HTTP-client versions, dependency locks,
source revisions and current image digest when applicable. Inspect **installed
framework dispatch**, not just its documentation or function annotations. Some
framework/version combinations call synchronous tools directly on the event
loop; others offload them. Do not assert identical dispatch across MCP variants.

Trace each registered tool through decorators, gates, identity enrichment,
pagination and HTTP/database clients. Record all blocking I/O and CPU-heavy work.
On reruns, reuse existing async clients and lifecycle hooks; reconcile gaps
without installing duplicate pools or wrapping tools repeatedly.
Save the existing tool schemas and an endpoint contract matrix: arguments,
defaults, typed result, backend status mapping and side effects. Benchmark the
current path before changing it. Keep CPU-bound work for a separate worker or
executor design; async syntax does not parallelize Python computation.

The included examples are tested with Python 3.13 and `mcp==1.29.1` (the SDK's
`mcp.server.fastmcp`, not the separate `fastmcp` package). They are an executable
reference, not a reason to upgrade a target project. Keep a compatible installed
version when it supports async tools. Re-audit dispatch and lifecycle on other
versions, especially major upgrades.

## 2. Preserve the SDK contract while changing I/O

Read [the implementation notes](references/implementation.md) and adapt
[the client example](assets/async_example/client.py) to the target SDK.

- Retain the synchronous client for its current consumers; add an async client.
  Share parsers and error mapping rather than independently reimplementing them.
  Check **every endpoint**, including less common actions and long operations.
- Await native async HTTP/database calls through the complete tool path, including
  decorators and authorization/identity lookups. Preserve signatures with
  `functools.wraps` where appropriate and compare generated schemas afterward.
- Give each client explicit resource ownership. An SDK-created transport is
  closed by that SDK; a borrowed shared transport is closed only by its owner.
  Provide async context management and idempotent `aclose()`.
- Shield cleanup in an already-cancelled AnyIO scope, while preserving operation
  cancellation. Do not catch cancellation and convert it into a success result.
- Preserve status/error behavior and avoid automatic redirects or write retries.
  Timeout/cancellation can leave a backend write's outcome unknown. Retrying it
  needs the existing idempotency/reconciliation contract.

If a dependency has no async API, use an explicit bounded offload as an interim
design: `anyio.to_thread.run_sync(..., limiter=..., abandon_on_cancel=False)`.
Choose the limiter per process, not per call. The worker still blocks a thread;
cancelling the await cannot forcibly stop it. Set underlying I/O timeouts and
account for work that continues or delays cancellation. Do not describe this as
native async, or silently increase thread counts to hide saturation.

## 3. Own one transport per serving process

Adapt [the server example](assets/async_example/server.py).

- Create the shared transport inside the serving event loop, once per process.
  Never share it across worker processes, forks or separate event loops.
- For the demonstrated stateless Streamable HTTP path, wrap the **outer ASGI
  lifespan** and compose the existing framework lifespan. The low-level server
  lifespan can run per stateless request; using it for the pool defeats reuse.
  Verify the actual frequency for the installed framework. Retain its session
  manager's startup/shutdown and lifespan state.
- For stdio, wrap the entire async server runtime in the transport context.
  Keep stdout exclusively for MCP protocol messages; diagnostics go to stderr.
- Bound active/idle connections, idle expiry and connect/read/write/pool waits.
  The example's 20 connections, 10 idle and one-second pool timeout are test
  settings, not universal recommendations. Tune per process and multiply by the
  number of workers when assessing backend pressure.
- Pool acquisition waits are local resource pressure. Keep backend admission,
  rate limits and tenant policy with their existing owner; do not add a per-user
  MCP queue as a substitute for fixing blocking I/O.

Keep the existing endpoint and stateless transport. Preserve host/origin checks,
authentication middleware, proxy conventions and observability. Configure logging
using `byteforge-loki-logging` if available; do not overwrite a project's existing
logging setup with the example's demonstration logger.

## 4. Isolate callers even when connections are shared

Use per-call SDK wrappers with explicit credentials. Never mutate shared client
`Authorization` defaults. Middleware must set **both transport context and caller
identity** and reset the ContextVar token in `finally` after success, error or
cancellation. A missing/Basic/empty bearer on HTTP must fail before backend
forwarding; it must not select the stdio process credential.

Construct explicit `httpx.Request` objects and send with `auth=None` and
`follow_redirects=False` when borrowing a client. This avoids merging shared
cookies, headers and query defaults into another caller's request. Test real
HTTPX merging behavior, including cookies learned from earlier responses; a mock
that checks only the explicit Authorization argument is insufficient. Keep the
backend URL trusted service configuration, not caller-provided input. Preserve
the project's actual token validation and authorization rules.

Replace `EXAMPLE_API_KEY` / `EXAMPLE_BACKEND_URL` in the example with
`{PROJECT_NAME}_API_KEY` / `{PROJECT_NAME}_BACKEND_URL`, substituting the uppercase
project prefix. Replace the `async_example` module and synthetic `/work` endpoint
with `{project_name}` and the real SDK contract. Never copy fixture identities
into a deployed configuration. The environment credential is a **stdio-only**
fallback; all HTTP entrypoints must pass through the context middleware.

## 5. Run behavioral regressions and measure the change

Use [the validation guide](references/validation.md) to run and adapt the included
regressions and benchmark. From this skill's directory:

```bash
uv venv /tmp/mcp-async-validation
uv pip install --python /tmp/mcp-async-validation/bin/python -r requirements-test.txt
PYTHONDONTWRITEBYTECODE=1 /tmp/mcp-async-validation/bin/python -m pytest -q -p no:cacheprovider tests
PYTHONDONTWRITEBYTECODE=1 /tmp/mcp-async-validation/bin/python scripts/benchmark.py --repeat 2 > /tmp/mcp-async-benchmark.jsonl
```

These versions constrain the isolated harness, not the application's lock.
The backend binds an ephemeral loopback port and uses only fixture credentials.
No production URL is accepted by the benchmark. Adapt the dispatch adapter to the
actual project, retaining registered-tool validation and the real SDK path.

Required evidence before declaring the migration complete:

- Baseline/candidate schema and error parity; existing sync SDK regressions.
- Concurrent mixed tools and distinct callers; anonymous/malformed HTTP alongside
  valid requests; cookie/auth/query contamination and context restoration.
- Actual socket read timeouts, deliberately exhausted pool and pool timeout,
  cancellation/recovery, and owned/borrowed cleanup in cancelled scopes.
- Multiple independent stateless ASGI requests sharing one transport, correct
  framework lifespan composition, and whole-runtime stdio ownership.
- Waves of 1/10/100 slow calls plus a fast call and event-loop heartbeat. Report
  wave/service/completion latency, percentiles, fast latency, throughput, errors,
  identity checks and measured pool waits. Separate cold and warmed pools.

The runnable benchmark measures registered tool dispatch plus SDK and loopback
HTTP. It does not measure proxy ingress or production backend capacity, and
concurrent requests are not a count of human users. Report slowdowns as well as
improvements; cold single-call overhead can increase. Never turn a single run's
speedup into a general capacity promise.

## 6. Review and release within the authorized scope

Keep the existing dependency lock and transport deployment conventions. Reuse
`mcp-docker-deployment`, `uv-supply-chain-hardening`, and
`mcp-server-nginx-gatekeeper` when those skills are available and relevant; avoid
duplicating or replacing their workflows here.

Before publishing, verify in the built artifact the actual dependency versions,
imports, registered tool schemas/async flags, and pool startup/shutdown. Make
failed registration/lifecycle smoke checks block publication. The validation
guide distinguishes package tests from checks of the actual service image.

If the service pins its SDK by immutable commit, publish the reviewed SDK first,
then update the service pin, rebuild and test that service. With deployment
authorization, record the exact image digest and rollback reference, deploy,
verify digest/health, run lightweight authenticated and anonymous reads and
inspect service logs. Keep synthetic load tests isolated. Do not claim multiple
production identities were tested if only one was available.

## Reporting problems with this skill

If you find a bug or stale instruction while using this skill:

- If HiveMake is connected and `byteforge-skills-maintainer-agent` is available,
  file a ticket with that agent. Use `discover_agents` to find its project ID.
- Otherwise, open an issue at
  [GitHub Issues](https://github.com/jmazzahacks/byteforge-claude-skills/issues).
  If you cannot submit a report, give the human the details and this link.

Include the skill name, plugin version if known, the instruction followed,
expected and actual results, relevant errors/runtime versions, and any fix or
workaround that worked. Omit credentials and private data.

Address the user's immediate problem first; report the skill defect afterward.

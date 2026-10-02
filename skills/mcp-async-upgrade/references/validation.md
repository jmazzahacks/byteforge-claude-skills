# Validation and measurement

The runnable harness uses Python 3.13, MCP SDK 1.29.1, HTTPX 0.28.1, httpcore 1.0.9
and AnyIO 4.15.0. See `requirements-test.txt` for the remaining direct pins.
Install in an isolated environment as shown in SKILL.md. These are tested example
versions, not an instruction to change the target application's dependency set.

## What the regression suite exercises

`tests/test_async_upgrade.py` uses a real threaded HTTP backend on an ephemeral
loopback port. Synthetic waits happen off the MCP event loop. It covers:

| Boundary | Evidence |
| --- | --- |
| Registered tools | Same generated schemas before/after; async wrappers; real tool dispatch |
| HTTP SDK | Concurrent distinct bearer identities, shared default auth/query/cookies, learned response cookies |
| Stateless ASGI | Initialize and mixed tool calls, valid and malformed HTTP auth, one shared client across independent requests, actual framework lifespan |
| Cancellation | Context restoration after cancellation/error; shielded owned-client and process-client cleanup |
| Resource pressure | Real socket read timeout, a held request exhausting a one-connection pool, pool timeout, cancellation and successful reuse afterward |
| Compatibility | Sync client still works; sync/async error mapping agrees; no redirect/retry; borrowed clients remain open |
| Stdio | Whole-runtime ownership and cleanup on failure; real subprocess initialize/list/call exchange with strict JSON-only stdout |

The fixture echoes its synthetic bearer value as an identity assertion. Use only
the generated fixture credentials with it; real services should return their
normal identity/result types and must not expose bearer tokens to tool callers.

Adapt this matrix to the project's real methods, authorization rules and wrappers.
A tiny example cannot establish parity for an unrelated SDK's entire endpoint
surface. Test normal, error and already-cancelled shutdown using the host's actual
cancellation machinery. Retain synchronous regression tests after conversion.

## Reading benchmark JSONL

`scripts/benchmark.py` registers a deliberately blocking reference and a native
async candidate. Both use the same SDK contract, dependency versions, synthetic
backend, delay and pool limits. It schedules 1, 10 and 100 slow requests plus a
fast request and a 10ms heartbeat. It executes FastMCP's registered `Tool.run`,
including validation and wrappers, rather than calling undecorated functions.

Each cold case opens a new transport; warmed cases perform unmeasured priming
calls first. The synchronous reference serializes those priming calls on the
tested SDK, so it may warm fewer connections than the concurrent candidate.
This is reported as application warm-up, not equal numbers of preconnected sockets.
Repeats alternate variant order; report repeat distributions, not the best run.

The first JSON row records runtime versions, source hashes, limits and measurement
boundaries. Subsequent rows report:

- Wave completion and successful-call throughput, including the fast call.
- Slow-call service time (after dispatch starts) and completion time (since wave
  scheduling), with nearest-rank p50/p95/p99. Queueing can make these very different.
- Fast-call scheduled, actual-start, service and completion times; a late start
  reveals loop starvation even if the request itself completes quickly.
- Maximum heartbeat delay **beyond** its 10ms interval, errors and exact identity
  checks passed. The command exits nonzero if any measured call fails.
- Async connection acquisition percentiles/max and acquisition counts, including
  immediate acquisitions, plus how many initially queued. Sync waits are null,
  not zero. Local acquisition waits are not backend admission queues.

Acquisition counts measure internal attempts, not unique requests: a request can
be queued/reassigned more than once. Pool percentiles likewise describe attempts,
not each request's cumulative wait. The synthetic backend disables Nagle's
algorithm on its sockets so separate header/body writes do not add artificial
delayed-ACK stalls to the configured sleep.

The pool probe monkeypatches private `httpcore._async.connection_pool.AsyncPoolRequest`
methods only inside the harness and requires exactly httpcore 1.0.9. Registered
dispatch uses the private MCP tool manager and requires MCP 1.29.1. Re-audit these
probes before changing versions; do not copy them into application runtime. A
deliberately exhausted-pool regression verifies that queued waits are observable.

The default 20-connection pool makes resource contention visible in a 100-call
wave. Change `--connections`, `--delay` or `--repeat` to explore it. Treat values as
experimental inputs, not recommended production limits. The benchmark accepts no
remote endpoint and reads no production token. Keep high-load synthetic tests
isolated from production.

For a target service, replace the dispatch adapter with its actual registered
tools and the real SDK, use synthetic endpoints, preserve gate/identity wrappers,
and compare against its own pre-change source. The generic blocking reference
demonstrates a failure mode; it is not evidence that every framework serializes
synchronous tools or that every application improves by the measured amount.

## Release verification in the actual artifact

Before publication, run the target project's tests and a smoke check inside the
built image (if it deploys with Docker): installed SDK/framework versions, import
and registration, generated schemas, async flags on wrappers, and backend pool
open/close. The example's package-level checks do not substitute for that image
check. Ensure a failed smoke check prevents image push in the existing build flow.

Publish an immutable SDK revision before building a service that pins it. Verify
the service actually installed that revision. Record the tested image digest,
previous digest and rollback steps. After an authorized rollout, verify the
running digest and health, run lightweight reads with the available identities,
exercise anonymous rejection and inspect logs for startup/shutdown/request errors.
Distinguish local simultaneous-identity tests from production checks with only one
available identity. Avoid extrapolating loopback results to backend capacity or
human-user counts. Do not publish a throughput claim without the source/runtime,
measurement boundary, repeats, error counts and cold/warm qualification.

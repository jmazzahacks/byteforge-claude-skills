---
name: byteforge-prometheus-metrics
description: Configure Prometheus metrics for Python/Flask applications with multi-worker gunicorn safety and optional Redis-backed business metrics. Use when adding a /metrics endpoint, instrumenting a Flask app, or fixing inflated metrics from multi-worker gunicorn.
---

# Prometheus Metrics for Python/Flask Apps

This skill wires Prometheus metrics into a Python/Flask application **safely under multi-worker gunicorn** and adds an optional Redis-backed pattern for cross-worker business metrics.

## When to Use This Skill

Use this skill when:
- Adding a `/metrics` endpoint to a Python/Flask service
- The service runs (or might run) under gunicorn with more than one worker
- You need cross-worker business metrics (signups, jobs, queue depth, etc.) and Redis is available
- You are debugging inflated `rate()` values, phantom traffic, or `process_start_time_seconds` reporting multiple values for the same service

## The Multi-Worker Gunicorn Trap (Read This First)

`prometheus_client` keeps metrics in **per-process** memory. Under gunicorn with N workers, each worker has its own private registry. Prometheus scrapes hit a random worker each time, so:

- Counter values appear to "reset" as scrapes bounce between workers → PromQL `rate()` manufactures phantom traffic (often 5–10× the real rate for a 4-worker setup)
- `process_start_time_seconds` returns **N distinct values** over time — a one-line diagnostic for this bug
- Gauges that should be aggregate-able (e.g. queue depth) report whichever worker answered the scrape

**Fix:** every Step in this skill assumes multi-worker. The pieces are:

1. `prometheus_flask_exporter.GunicornPrometheusMetrics` (multiproc-aware)
2. `PROMETHEUS_MULTIPROC_DIR` env var set, dir cleaned on startup
3. `gunicorn_conf.py` with `child_exit` hook so dead workers release their shards
4. Custom Gauges declare `multiprocess_mode='livesum'` (or similar) — or they are silently dropped
5. Redis as the source-of-truth for cross-worker business counters (optional)

Skip any of these and metrics will look fine in dev (single process) and silently wrong in prod.

## What This Skill Creates

1. **requirements.txt entries** — `prometheus_client`, `prometheus_flask_exporter`, optionally `redis`
2. **Metrics initialization** in the main app file, wired through `create_app()` (post-fork)
3. **`gunicorn_conf.py`** — `child_exit` hook for multiproc shard cleanup
4. **Deploy snippets** — Dockerfile/docker-compose/systemd showing `PROMETHEUS_MULTIPROC_DIR` setup + startup dir cleanup
5. **Custom metric examples** — file-multiproc-safe (with Gauge mode) and Redis-backed (cross-worker aggregate)
6. **Starter Grafana dashboard JSON** — `references/starter-dashboard.json`, importable as-is
7. **Prometheus scrape config snippet** — for whoever runs the Prometheus server
8. **Verification checklist** — counter monotonicity and `rate()` sanity post-deploy

## Step 1: Gather Project Information

**IMPORTANT**: Before making changes, ask the user these questions:

1. **"What is your application tag/name?"** (e.g., "my-api", "ingest-worker")
   - This is the `application` label on all metrics — **must match** the `application_tag` you use in [[byteforge-loki-logging]] so logs and metrics correlate in Grafana
2. **"What is your main application file?"** (e.g., "app.py", "server.py")
   - Where `create_app()` lives
3. **"Does this service run under gunicorn with more than one worker?"** (yes/no — assume yes if unsure)
   - If yes: full multiproc setup (Steps 4 and 5)
   - If no: simpler single-process path, but **still scaffold the multiproc setup** behind a `PROMETHEUS_MULTIPROC_DIR` env-var gate so the service stays safe when scaled up later
4. **"Is Redis available to this service?"** (yes/no)
   - If yes: scaffold Step 6's Redis-backed business metrics pattern
   - If no: skip Step 6; document it as a follow-up if Redis is added later
5. **"What's the metrics scrape path?"** (default: `/metrics`)
   - Override only if `/metrics` collides with an existing route

## Step 2: Add Dependencies to requirements.txt

Add:

```txt
# Prometheus metrics
prometheus_client>=0.19.0
prometheus_flask_exporter>=0.23.0
```

If the user answered "yes" to Redis (Step 1, Q4), also add:

```txt
redis>=5.0.0
```

Install:

```bash
pip install -r requirements.txt
```

## Step 3: Wire Metrics into the Flask App

Add inside `create_app()` in `{app_file}.py`, **after** `Flask(__name__)` and **before** registering blueprints/routes:

```python
import os
from flask import Flask
from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics


def create_app() -> Flask:
    app = Flask(__name__)

    # ... existing setup (logging, etc.) ...

    # Prometheus metrics — multiproc-aware. Reads PROMETHEUS_MULTIPROC_DIR
    # automatically; if unset, falls back to single-process mode (only
    # safe for dev or workers=1).
    metrics = GunicornPrometheusMetrics(
        app,
        defaults_prefix='flask',
        group_by='endpoint',  # group HTTP latency by Flask endpoint name, not URL path
    )
    metrics.info(
        'app_info',
        'Application info',
        application='{application_tag}',
    )

    # ... register blueprints, configure Api, etc.
    return app


app = create_app()
```

**CRITICAL**: Replace:
- `{app_file}` → your main application filename
- `{application_tag}` → the tag from Step 1, Q1

**Why inside `create_app()` and not at module level**: gunicorn imports the module in each worker post-fork. Module-level initialization runs in the master process and breaks multiproc shard ownership. This matches the same fork-safety rule that [[byteforge-loki-logging]] documents for the Loki handler.

**Why `group_by='endpoint'`**: URL-path grouping explodes cardinality (one time series per unique URL — `/users/123`, `/users/456`, ...). Endpoint grouping uses Flask's route name (`get_user`), keeping cardinality bounded.

### What this gives you for free

- `/metrics` endpoint mounted automatically
- `flask_http_request_total{method,status,endpoint}` — request counter
- `flask_http_request_duration_seconds{method,status,endpoint}` — latency histogram (p50/p95/p99 via PromQL)
- `flask_http_request_exceptions_total{method,endpoint}` — unhandled exception counter
- Default process metrics: `process_resident_memory_bytes`, `process_cpu_seconds_total`, `process_start_time_seconds`, GC stats

## Step 4: Create gunicorn_conf.py

Create `gunicorn_conf.py` in the project root:

```python
"""Gunicorn config — required for prometheus_client multiproc safety.

When a worker dies, its on-disk metric shards must be released or stale
data accumulates and the multiproc collector returns inflated values.
"""
from prometheus_client import multiprocess


def child_exit(server, worker):
    multiprocess.mark_process_dead(worker.pid)
```

That single hook is the only thing this file must do for metrics. Add other gunicorn settings (workers, bind, timeout) however the project normally configures them.

## Step 5: Deploy-Side Setup (Dockerfile / docker-compose / systemd)

Three things must happen at container/service startup, in this order:

1. `PROMETHEUS_MULTIPROC_DIR` is exported
2. That directory is created fresh (stale shards from a previous container exit will inflate counters)
3. gunicorn is launched with `-c gunicorn_conf.py`

### Option A: Docker Compose with an entrypoint script

`entrypoint.sh`:

```bash
#!/bin/sh
set -e

: "${PROMETHEUS_MULTIPROC_DIR:=/tmp/prometheus_multiproc}"
export PROMETHEUS_MULTIPROC_DIR

rm -rf "$PROMETHEUS_MULTIPROC_DIR"
mkdir -p "$PROMETHEUS_MULTIPROC_DIR"

exec gunicorn -c gunicorn_conf.py -b 0.0.0.0:{port} {app_module}:app "$@"
```

**CRITICAL**: Replace:
- `{port}` → your bind port (e.g. `7843`)
- `{app_module}` → the import path of your app (e.g. `my_api` for `my_api.py`)

`Dockerfile`:

```dockerfile
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
```

`docker-compose.yaml` — mount tmpfs over the multiproc dir to avoid hitting the container's writable layer for every metric increment:

```yaml
services:
  {app_name}:
    tmpfs:
      - /tmp/prometheus_multiproc
    environment:
      - PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc
```

### Option B: systemd unit

```ini
[Service]
Environment=PROMETHEUS_MULTIPROC_DIR=/run/prometheus_multiproc_{service_name}
RuntimeDirectory=prometheus_multiproc_{service_name}
RuntimeDirectoryMode=0755
ExecStartPre=/bin/sh -c 'rm -rf $PROMETHEUS_MULTIPROC_DIR/*'
ExecStart=/path/to/venv/bin/gunicorn -c gunicorn_conf.py -b 127.0.0.1:{port} {app_module}:app
```

`RuntimeDirectory` is on tmpfs by default under systemd and is cleaned up when the service stops.

### Why tmpfs

Metrics shards are written on every increment. On a busy service, that is thousands of file writes per second. tmpfs keeps them in RAM, avoiding disk I/O and SSD wear.

## Step 6: Custom Application Metrics

Two patterns. Use **Pattern A** for per-request metrics that are naturally per-process (timings, error counts, in-flight requests). Use **Pattern B** for business metrics that need a single global value across workers.

### Pattern A: File-multiproc metrics (the default)

For Counters and Histograms, the multiproc collector sums across workers automatically. No extra work:

```python
from prometheus_client import Counter, Histogram

orders_placed_total = Counter(
    'orders_placed_total',
    'Orders placed, by product category',
    ['category'],
)

order_processing_seconds = Histogram(
    'order_processing_seconds',
    'Time spent processing an order',
    ['category'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# In your route:
with order_processing_seconds.labels(category='digital').time():
    place_order(...)
orders_placed_total.labels(category='digital').inc()
```

**Gauges are different — you MUST declare `multiprocess_mode`.** Without it, the multiproc collector silently drops the metric:

```python
from prometheus_client import Gauge

# 'livesum' = sum across all live workers (good for in-flight requests, active jobs)
# 'liveall' = expose one series per live worker (good for debugging)
# 'max' / 'min' = aggregate by max/min across workers
in_flight_orders = Gauge(
    'in_flight_orders',
    'Orders currently being processed',
    multiprocess_mode='livesum',
)

in_flight_orders.inc()
try:
    place_order(...)
finally:
    in_flight_orders.dec()
```

### Pattern B: Redis-backed business metrics

For metrics where you want **one true global value** across workers (e.g. "total signups today", "queued background jobs", "active subscribers"), keep the source of truth in Redis and expose a custom collector that reads Redis at scrape time.

This is preferred over Pattern A for business metrics because:
- The value is correct even if a worker just restarted (no shard re-aggregation lag)
- It survives the whole gunicorn pool being recycled
- Other services can read/increment the same counter

**Add a module `metrics_redis.py`:**

```python
import os
import redis
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily
from prometheus_client.registry import Collector

REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
METRIC_KEY_PREFIX = 'metrics:{application_tag}:'

_redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def incr(name: str, amount: int = 1) -> None:
    """Increment a monotonic business counter. Safe across workers and processes."""
    _redis_client.incrby(f'{METRIC_KEY_PREFIX}{name}', amount)


def set_gauge(name: str, value: float) -> None:
    """Set a gauge value. Safe across workers."""
    _redis_client.set(f'{METRIC_KEY_PREFIX}gauge:{name}', value)


class RedisBusinessMetricsCollector(Collector):
    """Custom collector that reads business metrics from Redis at scrape time."""

    def __init__(self, application_tag: str):
        self.application_tag = application_tag

    def collect(self):
        # Counters — keys matching metrics:<tag>:<name> (non-gauge)
        counter_keys = _redis_client.keys(f'{METRIC_KEY_PREFIX}*')
        for key in counter_keys:
            if ':gauge:' in key:
                continue
            name = key.split(':', 2)[-1]
            value = int(_redis_client.get(key) or 0)
            m = CounterMetricFamily(
                name,
                f'Business counter: {name}',
                labels=['application'],
            )
            m.add_metric([self.application_tag], value)
            yield m

        # Gauges — keys matching metrics:<tag>:gauge:<name>
        gauge_keys = _redis_client.keys(f'{METRIC_KEY_PREFIX}gauge:*')
        for key in gauge_keys:
            name = key.rsplit(':', 1)[-1]
            value = float(_redis_client.get(key) or 0)
            m = GaugeMetricFamily(
                name,
                f'Business gauge: {name}',
                labels=['application'],
            )
            m.add_metric([self.application_tag], value)
            yield m
```

**Register the collector once, inside `create_app()`** (after `GunicornPrometheusMetrics`):

```python
from prometheus_client import REGISTRY
from metrics_redis import RedisBusinessMetricsCollector

REGISTRY.register(RedisBusinessMetricsCollector(application_tag='{application_tag}'))
```

**Use it from anywhere:**

```python
from metrics_redis import incr, set_gauge

# In a signup route:
incr('signups_total')

# In a background job:
set_gauge('jobs_queue_depth', queue.size())
```

**CRITICAL**: Replace `{application_tag}` in `METRIC_KEY_PREFIX` with the tag from Step 1, Q1.

### Naming the keys

Redis keys collide silently when reused. Always namespace by `application_tag`. The prefix `metrics:{application_tag}:` keeps each service's counters isolated and makes Redis introspection easy (`redis-cli KEYS 'metrics:my-api:*'`).

### Cardinality warning

Custom collectors that read Redis on every scrape can explode if you create one Redis key per high-cardinality dimension (user ID, request ID). Keep labels low-cardinality (status, category, region) — the same rule that applies to Prometheus metrics in general.

## Step 7: Post-Deploy Verification

Run these checks **after deploying**. Skipping this step is how the multi-worker bug ships to production unnoticed.

### Check 1: Counters are monotonically non-decreasing

```bash
for i in 1 2 3 4 5; do
  curl -s https://<your-host>/metrics | grep '^flask_http_request_total{' | head -3
  echo "---"
  sleep 2
done
```

Counter values should only go up or stay the same. If they bounce (down, then up, then down), multiproc is not wired correctly — re-check Steps 3, 4, 5.

### Check 2: `process_start_time_seconds` reports ONE value, not N

```bash
curl -s https://<your-host>/metrics | grep '^process_start_time_seconds'
```

You should see exactly one line. If you see N distinct values where N matches your worker count, `PROMETHEUS_MULTIPROC_DIR` is unset or the multiproc collector isn't being used.

### Check 3: `rate()` returns a sensible value in Grafana

```promql
sum(rate(flask_http_request_total{application="{application_tag}"}[5m]))
```

Compare to your nginx/gateway access-log rate. They should agree within ~10%. If `rate()` is 3–10× higher, the counter is "resetting" because scrapes bounce between workers with private registries.

### Check 4: Custom Gauges show up

```bash
curl -s https://<your-host>/metrics | grep -E '^(in_flight_orders|jobs_queue_depth)'
```

If a Gauge is missing entirely, it was declared without `multiprocess_mode` and the multiproc collector dropped it. Add `multiprocess_mode='livesum'` (or similar) and restart.

## Step 8: Starter Grafana Dashboard

A starter dashboard is included at `references/starter-dashboard.json`. To install:

1. Grafana → Dashboards → Import → Upload JSON
2. Select the Prometheus datasource
3. The dashboard is parameterized on `application` — pick `{application_tag}` from the dropdown

It includes:
- Request rate (req/s) by status class (2xx/4xx/5xx)
- Latency p50 / p95 / p99
- In-flight requests
- Error rate (5xx / total)
- Process memory + CPU
- Open file descriptors
- Worker restart events (gaps in `process_start_time_seconds`)

For the Redis-backed business metrics, add panels manually — the metric names are project-specific.

## Step 9: Prometheus Scrape Config

Hand this snippet to whoever runs the Prometheus server. The exact location depends on whether they use static configs, file-based SD, or Kubernetes ServiceMonitors.

### Static config

```yaml
scrape_configs:
  - job_name: '{application_tag}'
    metrics_path: /metrics
    scrape_interval: 15s
    static_configs:
      - targets: ['<host>:<port>']
        labels:
          application: '{application_tag}'
```

### Notes for the Prometheus operator

- Set `application` as a target label so it appears on every metric — this matches the `application_tag` convention used by [[byteforge-loki-logging]] so logs and metrics correlate
- 15s is a good default scrape interval; faster than 5s rarely pays off and inflates storage
- If the service is behind nginx/gatekeeper, the scrape config should hit the **internal** address (avoid the public URL and any `auth_request` layer) — alternatively, whitelist the Prometheus source IP in nginx for `/metrics`

## The Four Traps

Things that look fine in dev and break in prod. All four are real and have shipped to production before this skill existed.

| # | Trap | Symptom | Fix |
|---|------|---------|-----|
| 1 | No multiproc wiring under multi-worker gunicorn | `rate()` 5–10× too high; `process_start_time_seconds` has N values | Steps 3, 4, 5 — all three are needed; any one missing leaves the bug |
| 2 | Gauges declared without `multiprocess_mode` | Gauge disappears from `/metrics` after enabling multiproc | Add `multiprocess_mode='livesum'` (or `'liveall'`, `'max'`, `'min'`) |
| 3 | `PROMETHEUS_MULTIPROC_DIR` not cleaned on startup | Counter values appear pre-loaded from a prior container's shards; `rate()` initially negative then settles | `rm -rf $PROMETHEUS_MULTIPROC_DIR/*` in entrypoint BEFORE launching gunicorn |
| 4 | High-cardinality labels (user ID, request ID, full URL path) | Prometheus storage/memory blows up; queries slow to crawl | Use `group_by='endpoint'` not URL path; never label by user/request ID; for Redis collector, never key on high-cardinality dimensions |

## Failure Decoder

| Symptom | Cause | Fix |
|---------|-------|-----|
| `rate(flask_http_request_total[5m])` returns 5–10× the real traffic | Multi-worker gunicorn without multiproc — each worker keeps a private registry, scrapes bounce between them, PromQL reads the bouncing as counter resets and manufactures phantom traffic | Apply Steps 3, 4, 5 in full |
| `process_start_time_seconds` returns N distinct values where N matches worker count | Multiproc collector isn't being used — likely `PROMETHEUS_MULTIPROC_DIR` not set or `GunicornPrometheusMetrics` was never instantiated | Confirm env var is set in the running container (`docker exec ... env | grep PROMETHEUS`), confirm `GunicornPrometheusMetrics(app)` is called in `create_app()` |
| Gauge metric missing from `/metrics` entirely | Gauge was declared without `multiprocess_mode` — the multiproc collector drops aggregation-ambiguous gauges silently | Add `multiprocess_mode='livesum'` (or `'liveall'`/`'max'`/`'min'` as appropriate) |
| `/metrics` returns 500 with `FileNotFoundError` in logs pointing at `PROMETHEUS_MULTIPROC_DIR` | Env var is set, but the directory does not exist or is not writable by the gunicorn user | Add the `mkdir -p $PROMETHEUS_MULTIPROC_DIR` step to entrypoint/ExecStartPre; verify file permissions match the runtime user |
| Counter values appear inflated at container startup and slowly decrease | Stale shards from a previous container's exit weren't cleaned, multiproc collector summed them with the new worker shards | Add `rm -rf $PROMETHEUS_MULTIPROC_DIR/*` to entrypoint BEFORE launching gunicorn |
| `redis.exceptions.ConnectionError` in `/metrics` response | `RedisBusinessMetricsCollector` is registered but Redis is unreachable; the custom collector raises during scrape and the whole `/metrics` response fails | Wrap the `collect()` method body in a `try/except redis.RedisError` that logs and yields nothing — a Redis outage should degrade business metrics, not kill the scrape |
| Custom Redis-backed metric reports 0 even though `incr()` is being called | `application_tag` mismatch between `METRIC_KEY_PREFIX` in writes and reads, or wrong Redis DB number in `REDIS_URL` | `redis-cli KEYS 'metrics:*'` to inspect; align prefixes; verify `REDIS_URL` is identical across the app and the collector |
| Cardinality explosion — Prometheus storage 100×, queries time out | High-cardinality label in a metric (user ID, request ID, full URL path with IDs) | Find the offending metric in `/metrics` (look for thousands of unique label combinations on one metric); switch to `group_by='endpoint'`; never label by entity ID |

## Report Back

When done, report:

1. Files created/modified (with paths)
2. The values for application_tag, app file, gunicorn multi-worker (yes/no), Redis (yes/no)
3. The output of `curl /metrics | grep '^process_start_time_seconds'` from a real deploy — exactly one line confirms multiproc is wired
4. The output of `curl /metrics | grep '^flask_http_request_total{' | head -3` from two scrapes 2s apart — confirm counters are monotonically non-decreasing
5. Whether the starter dashboard was imported and is showing data

If any check fails, walk through the **Failure Decoder** — every row maps a real symptom back to the Step that fixes it.

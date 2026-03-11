---
name: byteforge-loki-logging
description: Configure Grafana Loki logging using byteforge-loki-logging library for Python/Flask applications. Use when setting up Loki logging, configuring centralized logging, or adding structured JSON logging to any Python project.
---

# Loki Logging with byteforge-loki-logging

This skill helps you integrate Grafana Loki logging using the `byteforge-loki-logging` library, which handles structured JSON logging and asynchronous Loki shipping with graceful fallback.

## When to Use This Skill

Use this skill when:
- Starting a new Python/Flask application
- You want centralized logging with Loki
- You need structured JSON logs for production
- You want easy local development with console logs

## What This Skill Creates

1. **requirements.txt entry** - Adds `byteforge-loki-logging` dependency (private GitHub library)
2. **Logging initialization** - Adds `configure_logging()` call to main application file
3. **CA certificate configuration** - Docker Compose volume mount for your Loki CA certificate
4. **Environment variable documentation** - All required Loki configuration

## Step 1: Gather Project Information

**IMPORTANT**: Before making changes, ask the user these questions:

1. **"What is your application tag/name?"** (e.g., "materia-server", "trading-api")
   - This identifies your service in Loki logs
   - This becomes the `application` label in Loki — all services across the stack (Python and TypeScript) **must** use `application` as the label name, never `app` or `service`

2. **"What is your main application file?"** (e.g., "app.py", "server.py", "materia_server.py")
   - Where to add the logging configuration

3. **"What is your CA certificate filename?"** (e.g., "loki-ca.pem", "my-org-ca.pem")
   - Required for secure Loki connection over TLS
   - If the user does not have one or their Loki endpoint does not use a private CA, this step can be skipped

## Step 2: Add byteforge-loki-logging to requirements.txt

Add this line to `requirements.txt`:

```txt
# Logging configuration with Loki support (private GitHub library)
byteforge-loki-logging @ git+https://${CR_PAT}@github.com/jmazzahacks/byteforge-loki-logging.git
```

Install the dependency:
```bash
pip install -r requirements.txt
```

**Note**: Requires the `CR_PAT` environment variable set to a GitHub personal access token with repo read access.

## Step 3: Configure Logging in Application

Add to the **top** of your main application file (e.g., `{app_file}.py`):

```python
import os
from byteforge_loki_logging import configure_logging

# Configure logging with byteforge-loki-logging
# Use debug_local=True for local development, False for production with Loki
debug_mode = os.environ.get('DEBUG_LOCAL', 'true').lower() == 'true'
log_level = os.environ.get('LOG_LEVEL', 'INFO')
configure_logging(
    application_tag='{application_tag}',
    debug_local=debug_mode,
    local_level=log_level
)
```

**CRITICAL**: Replace:
- `{app_file}` -> Your main application filename (e.g., "materia_server")
- `{application_tag}` -> Your service name (e.g., "materia-server")

Place this **before** creating your Flask app or any other initialization.

### Structured JSON Logging

JSON formatting is enabled by default (`json_format=True`). Log records are formatted as:

```json
{"logger": "myapp", "level": "INFO", "message": "Request processed", "user_id": "123", "latency_ms": 42}
```

Query in Grafana: `{application="my-service"} | json | user_id="123"`

### Graceful Fallback

If the Loki connection test fails at startup, logging automatically falls back to stdout with a warning on stderr. Your application never crashes due to logging issues.

## Step 4: Configure CA Certificate

If your Loki endpoint uses a private CA certificate, mount it into the container via Docker Compose as a read-only volume. **Do not** bake the certificate into the Dockerfile with `COPY`.

In `docker-compose.yaml`:

```yaml
services:
  {app_name}:
    volumes:
      - /path/to/{ca_cert_filename}:/app/certs/loki-ca.pem:ro
    environment:
      - LOKI_CA_BUNDLE_PATH=/app/certs/loki-ca.pem
```

**CRITICAL**: Replace:
- `{app_name}` -> Your service name in docker-compose
- `{ca_cert_filename}` -> Your actual CA certificate filename from Step 1

The certificate will be available at `/app/certs/loki-ca.pem` inside the container.

If your Loki endpoint does not use a private CA (e.g., uses a publicly trusted certificate), skip this step and omit `LOKI_CA_BUNDLE_PATH`.

## Step 5: Document Environment Variables

Add to README.md or .env.example:

### Environment Variables

**Logging Configuration (Local Development):**
- `DEBUG_LOCAL` - Set to 'true' for local development (console logs), 'false' for production (Loki)
  - Default: 'true'
  - Production: 'false'
- `LOG_LEVEL` - Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
  - Default: 'INFO'

**Loki Configuration (Production Only - required when DEBUG_LOCAL=false):**
- `LOKI_ENDPOINT` - Loki push API URL (e.g., https://loki.example.com/loki/api/v1/push)
- `LOKI_USER` - Loki username for HTTP Basic Auth
- `LOKI_PASSWORD` - Loki password for HTTP Basic Auth
- `LOKI_CA_BUNDLE_PATH` - Path to CA certificate (e.g., /app/certs/loki-ca.pem), or "false" to disable SSL verification

### Logging Behavior

**Local Development** (`DEBUG_LOCAL=true`):
- Logs output to console with human-readable formatting
- Easy to read during development
- No Loki connection required
- No need to set LOKI_* variables

**Production** (`DEBUG_LOCAL=false`):
- Logs output as structured JSON to Loki asynchronously (1-second batching)
- All LOKI_* variables must be set
- Queryable in Grafana
- Automatic fallback to stdout if Loki is unreachable at startup

## Step 6: Usage Examples

### Local Development

```bash
# In .env or shell
export DEBUG_LOCAL=true
export LOG_LEVEL=DEBUG

pip install -r requirements.txt
python {app_file}.py
```

### Production Deployment

Docker Compose example:

```yaml
services:
  {app_name}:
    build:
      context: .
    volumes:
      - /path/to/{ca_cert_filename}:/app/certs/loki-ca.pem:ro
    environment:
      - DEBUG_LOCAL=false
      - LOG_LEVEL=INFO
      - LOKI_ENDPOINT=${LOKI_ENDPOINT}
      - LOKI_USER=${LOKI_USER}
      - LOKI_PASSWORD=${LOKI_PASSWORD}
      - LOKI_CA_BUNDLE_PATH=/app/certs/loki-ca.pem
```

**NOTE**: Set these in your .env file:
```
LOKI_ENDPOINT=https://loki.example.com/loki/api/v1/push
LOKI_USER=your_loki_user
LOKI_PASSWORD=your_loki_password
```

## How It Works

The `byteforge-loki-logging` library provides:

1. **Automatic mode detection** - Console logs for local dev, Loki for production
2. **Structured JSON logging** - Consistent JSON format for Loki, enabled by default
3. **Async shipping** - Background thread with 1-second batching for minimal performance impact
4. **Secure connection** - Uses CA certificate for encrypted Loki communication
5. **Graceful fallback** - Falls back to stdout if Loki is unreachable, never crashes your app
6. **Application tagging** - Identifies your service in centralized logs via the `application` label

**You don't need to:**
- Write JSON formatters
- Configure logging handlers
- Manage Loki client setup
- Handle certificate validation
- Worry about logging crashing your application

**Just call `configure_logging()` and you're done!**

## Integration with Other Skills

### Flask API Server
If using **flask-smorest-api** skill, add logging **before** creating Flask app:

```python
import os
import logging
from flask import Flask
from byteforge_loki_logging import configure_logging

# Configure logging FIRST
debug_mode = os.environ.get('DEBUG_LOCAL', 'true').lower() == 'true'
configure_logging(application_tag='my-api', debug_local=debug_mode)

# Then create Flask app
app = Flask(__name__)

# IMPORTANT: Propagate Flask's logger to the root logger so unhandled
# exceptions in route handlers reach Loki. Without this, Flask catches
# exceptions internally and logs them via werkzeug to stdout/stderr,
# bypassing the root logger that configure_logging() set up.
app.logger.handlers.clear()
app.logger.propagate = True
app.logger.setLevel(logging.DEBUG)

# ... rest of setup
```

**Why this matters**: Flask catches exceptions in route handlers and returns a 500 response, but by default it logs the traceback through its own `app.logger` using werkzeug's error handling — not through Python's root logger. Since `configure_logging()` configures the root logger, those tracebacks never reach Loki unless you clear Flask's default handlers and set `propagate = True`.

### Flask + Gunicorn: Propagate All Dependency Loggers

When running Flask under gunicorn, werkzeug and gunicorn create their own loggers (`werkzeug`, `gunicorn.error`, `gunicorn.access`) with their own `StreamHandler` instances and set `propagate=False`. This means log messages from those loggers never reach the root logger — which is where `configure_logging()` attaches the Loki handler. All application logs go to stdout/stderr instead of Loki.

**Everything must be done inside `create_app()`** — not at module level — for two reasons:

1. **Logger override**: Flask and gunicorn set up their loggers during app initialization and would override anything done earlier.
2. **Gunicorn fork/SSL**: `configure_logging()` creates a Loki handler with a `requests.Session` and SSL context. If called at module level, this runs in gunicorn's **master process** before `fork()`. The SSL context doesn't survive the fork into worker processes, causing SSL errors on the first log messages until the session reconnects. Moving it into `create_app()` ensures the SSL context is created in the worker process where it will be used.

```python
import os
import logging
from flask import Flask
from byteforge_loki_logging import configure_logging

def create_app() -> Flask:
    # Configure logging inside create_app() so it runs post-fork in the
    # gunicorn worker process. Module-level init causes SSL context issues
    # with the Loki handler because the SSL session doesn't survive fork().
    debug_mode = os.environ.get('DEBUG_LOCAL', 'true').lower() == 'true'
    log_level = os.environ.get('LOG_LEVEL', 'INFO')
    configure_logging(
        application_tag='my-api',
        debug_local=debug_mode,
        local_level=log_level,
    )

    app = Flask(__name__)

    # Force Flask, werkzeug, and gunicorn loggers to propagate to root.
    # These loggers create their own StreamHandlers with propagate=False,
    # which bypasses the root logger's Loki handler.
    app.logger.handlers.clear()
    app.logger.propagate = True
    app.logger.setLevel(logging.DEBUG)

    for name in ('werkzeug', 'gunicorn', 'gunicorn.error', 'gunicorn.access'):
        dep_logger = logging.getLogger(name)
        dep_logger.handlers.clear()
        dep_logger.propagate = True

    # ... register blueprints, configure Api, etc.

    return app

# create_app() runs when gunicorn imports the module in the WORKER process
app = create_app()
```

**CRITICAL**: `configure_logging()` must be the first thing inside `create_app()`, before any code that logs. Do NOT call it at module level.

**CRITICAL**: The `for` loop clearing dependency loggers must run **after** Flask and Api are initialized (so their logger setup has already run), otherwise Flask/gunicorn will re-create their handlers and override your changes.

### Multiprocessing / Forked Child Processes

**The general rule: `configure_logging()` must be called in every process that logs.** The Loki handler uses a background `QueueListener` thread and a `requests.Session` with an SSL context — neither survives `fork()`. A child process inherits a copy of the logging config with a dead handler, and logs go into a queue that nobody reads. No errors are raised because the queue accepts writes silently.

This applies to:
- `multiprocessing.Process` target functions
- `os.fork()` child processes
- Any code that spawns child processes that emit logs

**Fix**: Call `configure_logging()` at the top of the child process entry point, before any logging:

```python
import os
import logging
import multiprocessing
from byteforge_loki_logging import configure_logging

def run_job(job_id: str) -> None:
    """Target function for multiprocessing.Process — runs in a forked child."""
    # CRITICAL: The parent's Loki handler (QueueListener thread + requests.Session)
    # does not survive fork(). Re-initialize logging in the child process so it
    # gets its own handler, thread, and SSL context.
    debug_mode = os.environ.get('DEBUG_LOCAL', 'true').lower() == 'true'
    log_level = os.environ.get('LOG_LEVEL', 'INFO')
    configure_logging(
        application_tag='my-worker',
        debug_local=debug_mode,
        local_level=log_level,
    )
    logger = logging.getLogger(__name__)

    logger.info(f"Starting job {job_id}")
    # ... do work ...
    logger.info(f"Finished job {job_id}")


# In the parent process:
process = multiprocessing.Process(target=run_job, args=(job_id,))
process.start()
```

**Summary of where `configure_logging()` must be called:**

| Process | Where to call | Why |
|---------|--------------|-----|
| Gunicorn worker | Inside `create_app()` | Runs post-fork in worker process |
| `multiprocessing.Process` child | Top of target function | QueueListener thread + SSL context don't survive fork |
| Direct `os.fork()` child | Immediately after fork in child branch | Same reason |

## Troubleshooting

**Logs not appearing in Loki (production):**
- Verify `DEBUG_LOCAL=false` is set
- Check all LOKI_* variables are correct
- Test CA certificate path is accessible in container
- Verify Loki endpoint is reachable from container
- Check stderr for fallback warnings — if you see "Falling back to stdout", the Loki connection failed at startup

**Missing CA certificate error:**
- Ensure the volume mount is correct in docker-compose.yaml
- Verify `LOKI_CA_BUNDLE_PATH` points to `/app/certs/loki-ca.pem`
- Check that the source file exists on the host at the mounted path

**Runtime error: Missing required environment variables:**
- Only occurs when `DEBUG_LOCAL=false`
- Ensure all LOKI_* variables are set
- Check spelling (LOKI_, not MZ_LOKI_ or MATERIA_LOKI_)

**Flask route exceptions not appearing in Loki:**
- Flask catches exceptions in route handlers and logs them via werkzeug to stdout/stderr, bypassing the root logger
- Fix: clear Flask's default handlers and propagate to root logger (see Flask integration section above)
- Symptoms: 500 errors appear in nginx/container logs but not in Grafana/Loki

**Loki SSL errors on first few startup log messages (gunicorn):**
- `configure_logging()` was called at module level, which runs in gunicorn's master process before `fork()`. The Loki handler's `requests.Session` and its SSL context were initialized pre-fork, then broke in the child worker because SSL contexts don't survive `fork()`.
- Fix: move `configure_logging()` inside `create_app()` so it runs post-fork in the worker process (see Flask + Gunicorn section above)
- Symptoms: SSL errors only on the first few startup log messages, then everything works fine after the session recovers

**Gunicorn/werkzeug logs going to stdout instead of Loki:**
- Werkzeug and gunicorn create their own loggers with `propagate=False` and their own `StreamHandler` instances
- Fix: clear handlers and set `propagate=True` on `werkzeug`, `gunicorn`, `gunicorn.error`, and `gunicorn.access` loggers inside `create_app()` (see Flask + Gunicorn section above)
- Symptoms: application logs visible in `docker logs` or container stdout but missing from Grafana/Loki

**Logs from multiprocessing.Process child processes not appearing in Loki:**
- The parent's QueueListener thread and requests.Session do not survive `fork()`. The child inherits a dead handler — logs go into a queue that nobody reads. No errors are raised.
- Fix: call `configure_logging()` at the top of the child process target function, before any logging (see Multiprocessing section above)
- Symptoms: parent process logs appear in Loki, but all child process logs vanish silently

**Import error for byteforge_loki_logging:**
- Ensure `CR_PAT` environment variable is set with a valid GitHub token
- Run `pip install -r requirements.txt`
- Verify installed: `pip list | grep byteforge-loki-logging`

## Example Implementation

```python
# materia_server.py
import os
import logging
from flask import Flask
from byteforge_loki_logging import configure_logging


def create_app() -> Flask:
    debug_mode = os.environ.get('DEBUG_LOCAL', 'true').lower() == 'true'
    log_level = os.environ.get('LOG_LEVEL', 'INFO')
    configure_logging(
        application_tag='materia-server',
        debug_local=debug_mode,
        local_level=log_level,
    )

    app = Flask(__name__)

    app.logger.handlers.clear()
    app.logger.propagate = True
    app.logger.setLevel(logging.DEBUG)

    for name in ('werkzeug', 'gunicorn', 'gunicorn.error', 'gunicorn.access'):
        dep_logger = logging.getLogger(name)
        dep_logger.handlers.clear()
        dep_logger.propagate = True

    # ... register blueprints, configure Api, etc.

    return app


app = create_app()
```

```yaml
# docker-compose.yaml
services:
  materia-server:
    volumes:
      - ./certs/loki-ca.pem:/app/certs/loki-ca.pem:ro
    environment:
      - DEBUG_LOCAL=false
      - LOG_LEVEL=INFO
      - LOKI_ENDPOINT=${LOKI_ENDPOINT}
      - LOKI_USER=${LOKI_USER}
      - LOKI_PASSWORD=${LOKI_PASSWORD}
      - LOKI_CA_BUNDLE_PATH=/app/certs/loki-ca.pem
```

This provides structured logging locally during development and automatic Loki shipping in production with secure encrypted connections.

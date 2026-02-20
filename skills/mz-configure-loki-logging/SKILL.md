---
name: mz-configure-loki-logging
description: Configure Grafana Loki logging using mazza-base library for Python/Flask applications with CA certificate (Mazza-specific). Use when setting up Loki logging for Mazza projects or configuring centralized logging.
---

# Loki Logging with mazza-base

This skill helps you integrate Grafana Loki logging using the mazza-base utility library, which handles structured JSON logging and Loki shipping.

## When to Use This Skill

Use this skill when:
- Starting a new Python/Flask application
- You want centralized logging with Loki
- You need structured logs for production
- You want easy local development with console logs

## What This Skill Creates

1. **requirements.txt entry** - Adds mazza-base dependency
2. **CA certificate file** - Places mazza.vc_CA.pem in project root
3. **Dockerfile updates** - Copies CA certificate to container
4. **Logging initialization** - Adds configure_logging() call to main application file
5. **Environment variable documentation** - All required Loki configuration

## Step 1: Gather Project Information

**IMPORTANT**: Before making changes, ask the user these questions:

1. **"What is your application tag/name?"** (e.g., "materia-server", "trading-api")
   - This identifies your service in Loki logs

2. **"What is your main application file?"** (e.g., "app.py", "server.py", "materia_server.py")
   - Where to add the logging configuration

3. **"Do you have the mazza.vc_CA.pem certificate file?"**
   - Required for secure Loki connection
   - If no, user needs to obtain it from Mazza infrastructure team

4. **"Do you have a CR_PAT environment variable set?"** (GitHub Personal Access Token)
   - Required to install mazza-base from private GitHub repo

## Step 2: Add mazza-base to requirements.txt

Add this line to `requirements.txt`:

```txt
# Logging configuration with Loki support
mazza-base @ git+https://${CR_PAT}@github.com/mazza-vc/python-mazza-base.git@main
```

**NOTE**: The `CR_PAT` environment variable must be set when running `pip install`:
```bash
export CR_PAT="your_github_personal_access_token"
pip install -r requirements.txt
```

## Step 3: Add CA Certificate File

Ensure `mazza.vc_CA.pem` file is in your project root:

```
{project_root}/
├── mazza.vc_CA.pem    # CA certificate for secure Loki connection
├── requirements.txt
├── Dockerfile
└── {app_file}.py
```

If you don't have this file, contact the Mazza infrastructure team.

## Step 4: Update Dockerfile

Add the CA certificate to your Dockerfile. Place this **before** installing requirements:

```dockerfile
FROM python:3.11-alpine

ARG CR_PAT
ENV CR_PAT=${CR_PAT}

WORKDIR /app

# Copy CA certificate
COPY mazza.vc_CA.pem .

# Copy requirements and install
COPY requirements.txt .
RUN pip install -r requirements.txt

# ... rest of Dockerfile
```

**CRITICAL**: The COPY line must appear before `pip install -r requirements.txt`

The certificate will be available at `/app/mazza.vc_CA.pem` in the container.

## Step 5: Configure Logging in Application

Add to the **top** of your main application file (e.g., `{app_file}.py`):

```python
import os
from mazza_base import configure_logging

# Configure logging with mazza_base
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
- `{app_file}` → Your main application filename (e.g., "materia_server")
- `{application_tag}` → Your service name (e.g., "materia-server")

Place this **before** creating your Flask app or any other initialization.

## Step 6: Document Environment Variables

Add to README.md or .env.example:

### Environment Variables

**Logging Configuration (Local Development):**
- `DEBUG_LOCAL` - Set to 'true' for local development (console logs), 'false' for production (Loki)
  - Default: 'true'
  - Production: 'false'
- `LOG_LEVEL` - Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
  - Default: 'INFO'

**Loki Configuration (Production Only - required when DEBUG_LOCAL=false):**
- `MZ_LOKI_ENDPOINT` - Loki server URL (e.g., https://loki.mazza.vc:8443/loki/api/v1/push)
- `MZ_LOKI_USER` - Loki username for authentication
- `MZ_LOKI_PASSWORD` - Loki password for authentication
- `MZ_LOKI_CA_BUNDLE_PATH` - Path to CA certificate (e.g., /app/mazza.vc_CA.pem)

**GitHub Access (for pip install):**
- `CR_PAT` - GitHub Personal Access Token with repo access
  - Required to install mazza-base from private repository

### Logging Behavior

**Local Development** (`DEBUG_LOCAL=true`):
- Logs output to console with pretty formatting
- Easy to read during development
- No Loki connection required
- No need to set MZ_LOKI_* variables

**Production** (`DEBUG_LOCAL=false`):
- Logs output as structured JSON to Loki
- All MZ_LOKI_* variables must be set
- Queryable in Grafana
- Secure connection via mazza.vc_CA.pem

## Step 7: Usage Examples

### Local Development

```bash
# In .env or shell
export DEBUG_LOCAL=true
export LOG_LEVEL=DEBUG
export CR_PAT=your_github_token

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
      args:
        - CR_PAT=${CR_PAT}
    environment:
      - DEBUG_LOCAL=false
      - LOG_LEVEL=INFO
      - MZ_LOKI_ENDPOINT=${MZ_LOKI_ENDPOINT}
      - MZ_LOKI_USER=${MZ_LOKI_USER}
      - MZ_LOKI_PASSWORD=${MZ_LOKI_PASSWORD}
      - MZ_LOKI_CA_BUNDLE_PATH=/app/mazza.vc_CA.pem
```

**NOTE**: Set these in your .env file:
```
MZ_LOKI_ENDPOINT=https://loki.mazza.vc:8443/loki/api/v1/push
MZ_LOKI_USER=your_loki_user
MZ_LOKI_PASSWORD=your_loki_password
```

## How It Works

The `mazza-base` library provides:

1. **Automatic mode detection** - Console logs for local dev, Loki for production
2. **Structured logging** - Consistent JSON format for Loki
3. **Secure connection** - Uses CA certificate for encrypted Loki communication
4. **Easy integration** - One function call to configure everything
5. **Application tagging** - Identifies your service in centralized logs

**You don't need to:**
- Write JSON formatters
- Configure logging handlers
- Manage Loki client setup
- Handle certificate validation

**Just call `configure_logging()` and you're done!**

## Integration with Other Skills

### Flask API Server
If using **flask-smorest-api** skill, add logging **before** creating Flask app:

```python
import os
import logging
from flask import Flask
from mazza_base import configure_logging

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
from mazza_base import configure_logging

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

### Docker Deployment
In your Dockerfile:

```dockerfile
ARG CR_PAT
ENV CR_PAT=${CR_PAT}
COPY mazza.vc_CA.pem .
COPY requirements.txt .
RUN pip install -r requirements.txt
```

## Troubleshooting

**Cannot install mazza-base:**
- Ensure `CR_PAT` environment variable is set
- Verify token has repo access to `mazza-vc/python-mazza-base`
- Check token is not expired

**Missing CA certificate error:**
- Ensure `mazza.vc_CA.pem` is in project root
- Verify file is copied in Dockerfile: `COPY mazza.vc_CA.pem .`
- Check MZ_LOKI_CA_BUNDLE_PATH points to correct location

**Runtime error: Missing required environment variables:**
- Only occurs when `DEBUG_LOCAL=false`
- Ensure all MZ_LOKI_* variables are set
- Check spelling (MZ_LOKI_, not LOKI_ or MATERIA_LOKI_)

**Logs not appearing in Loki (production):**
- Verify `DEBUG_LOCAL=false` is set
- Check all MZ_LOKI_* variables are correct
- Test CA certificate path is accessible in container
- Verify Loki endpoint is reachable from container

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

**Import error for mazza_base:**
- Run `pip install -r requirements.txt` with CR_PAT set
- Verify mazza-base installed: `pip list | grep mazza-base`

## Example Implementation

See the materia-server project for a reference implementation:

```python
# materia_server.py
import os
import logging
from flask import Flask
from mazza_base import configure_logging


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

```dockerfile
# Dockerfile
FROM python:3.11-alpine
ARG CR_PAT
ENV CR_PAT=${CR_PAT}
WORKDIR /app
COPY mazza.vc_CA.pem .
COPY requirements.txt .
RUN pip install -r requirements.txt
# ... rest of Dockerfile
```

```yaml
# docker-compose.yaml
services:
  materia-server:
    environment:
      - MZ_LOKI_USER=${MZ_LOKI_USER}
      - MZ_LOKI_ENDPOINT=${MZ_LOKI_ENDPOINT}
      - MZ_LOKI_PASSWORD=${MZ_LOKI_PASSWORD}
      - MZ_LOKI_CA_BUNDLE_PATH=/app/mazza.vc_CA.pem
```

This provides structured logging locally during development and automatic Loki shipping in production with secure encrypted connections.

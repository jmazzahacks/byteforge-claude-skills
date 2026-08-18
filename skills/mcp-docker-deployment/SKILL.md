---
name: mcp-docker-deployment
description: Set up Docker deployment for Python MCP servers (FastMCP or low-level mcp.server.Server SDK) with streamable-http transport (preferred) or legacy SSE, automated versioning, and container registry publishing. Use when dockerizing an MCP server, containerizing for remote access, deploying an MCP server behind nginx, or setting up a production MCP server with Docker. Covers Dockerfile, build scripts, docker-compose, and nginx reverse proxy.
---

# MCP Docker Deployment

Containerize Python MCP servers (FastMCP or low-level SDK) for remote deployment with streamable-http transport (preferred) or legacy SSE, nginx reverse proxy with HTTPS, and GHCR publishing.

## Transport choice — default to streamable-http

**Always pick `streamable-http` with `stateless_http=True` unless you have a specific reason to use SSE.** SSE has a wedge bug class with Claude Code as the client: when the long-lived SSE GET dies (container restart, network blip, idle close), Claude Code's MCP client auto-reconnects but does NOT re-run the `initialize` handshake. The new server-side session sees `tools/call` before `initialize`, raises `RuntimeError("Received request before initialization was complete")`, and the SDK's catch-all converts it to a generic `-32602 "Invalid request parameters"`. Claude Code treats `-32602` as unrecoverable; every subsequent call returns the same error until the user manually `/mcp` reloads.

Streamable-http with `stateless_http=True` has no per-session state to lose — every POST stands alone. The bug class is structurally impossible on this transport.

References: [anthropics/claude-code#60061](https://github.com/anthropics/claude-code/issues/60061) (open upstream issue tracking the wedge on the SSE side; multiple independent reporters, same diagnosis, same workaround).

Pick `sse` ONLY if you have a non-Claude-Code MCP client that explicitly requires it (rare).

## Step 1: Gather Project Information

Ask the user:

1. **"What is your MCP server entry point file?"** (e.g., `my_mcp_server.py`)
2. **"Does your server use FastMCP (`mcp.server.fastmcp.FastMCP`) or the low-level SDK (`mcp.server.Server`)?"**
3. **"Confirm transport: `streamable-http` (recommended, default) or `sse` (legacy)?"** — default to `streamable-http`. Only use `sse` if a non-Claude-Code client explicitly requires it. See the "Transport choice" section above for why. (Note: the two are NOT interchangeable — different endpoints, different SDK classes.)
4. **"What Python files/directories need to be copied into the container?"** (e.g., `tools/`, `models/`, `formatting.py`)
5. **"What container registry URL?"** (e.g., `ghcr.io/{org}/{project}`)
6. **"Does the MCP server need any environment variables?"** (list them for docker-compose and example.env)
7. **"Will this be behind an nginx reverse proxy with HTTPS?"** (yes/no - if yes, include nginx config)
8. **"Does it have private pip dependencies?"** (yes/no - if yes, needs CR_PAT via BuildKit secret mount)

## Step 2: Create Dockerfile

```dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code - adjust to match project structure
COPY {entry_point} .
# COPY additional files/directories as needed

# Non-root user
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Transport for Docker, bind to all interfaces
ENV MCP_TRANSPORT=streamable-http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000

# Healthcheck: probe socket.gethostname(), NOT 127.0.0.1. A loopback
# probe from inside the container succeeds even when the server is
# bound only to 127.0.0.1 — the exact bind trap this skill warns about
# on the FastMCP path. gethostname() resolves to the container's
# address on the docker network, which is the path nginx actually uses,
# so a false-healthy state on 127.0.0.1 becomes a real
# ConnectionRefusedError instead.
#
# Port resolution mirrors the FastMCP Path A fallback chain
# (FASTMCP_PORT → MCP_PORT → 8000), so a user who overrides only
# FASTMCP_PORT doesn't leave the healthcheck probing the wrong port.
# On Path B, FASTMCP_PORT is unset so the chain falls through to
# MCP_PORT — which is what the low-level SDK reads directly.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os,socket; socket.create_connection((socket.gethostname(), int(os.getenv('FASTMCP_PORT', os.getenv('MCP_PORT','8000')))), timeout=3).close()" || exit 1

CMD ["python", "{entry_point}"]
```

> **FastMCP note**: If the server uses FastMCP, also set `FASTMCP_HOST` and `FASTMCP_PORT` in the Dockerfile since FastMCP reads those specific env vars:
> ```dockerfile
> ENV FASTMCP_HOST=0.0.0.0
> ENV FASTMCP_PORT=8000
> ```

If private pip dependencies, replace the plain `pip install` line above with a
BuildKit secret mount + scrub block. CR_PAT enters via `--mount=type=secret`
(never recorded in `docker history`), and the RUN scrubs pip's install
metadata (both `direct_url.json` records and hatchling-baked `METADATA` lines)
and self-verifies — the build FAILS if any token byte survives in
site-packages. Requires BuildKit (default in Docker 23+; for older Docker,
`export DOCKER_BUILDKIT=1`).

```dockerfile
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
RUN --mount=type=secret,id=cr_pat \
    export CR_PAT="$(cat /run/secrets/cr_pat)" \
    && pip install --no-cache-dir -r requirements.txt \
    && find /usr/local/lib/python3.13/site-packages -name direct_url.json -delete \
    && grep -rl "${CR_PAT}" /usr/local/lib/python3.13/site-packages | xargs -r sed -i "s|${CR_PAT}|REDACTED|g" \
    && ! grep -rq "${CR_PAT}" /usr/local/lib/python3.13/site-packages
```

Do NOT use `ARG CR_PAT` + `--build-arg`: any layer that consumes the ARG
records the value verbatim in `docker history`, readable by anyone who can
pull the image. And never `ENV CR_PAT=...` — that bakes the live token into
`.Config.Env` where `docker inspect` prints it.

### requirements.txt

The template code in Step 3 imports from `mcp.server.fastmcp` (Path A) or
`mcp.server.*` submodules (Path B). Those import paths only exist in the
`mcp` package's 1.x line — the 2.0.0 release (2026-07-28) renamed
`FastMCP` → `MCPServer`, moved `mcp.server.fastmcp` → `mcp.server.mcpserver`,
and made other breaking API changes. **Bound the `mcp` requirement to
`<2.0`** so a fresh Docker build (especially with `--no-cache`) can't
silently resolve into 2.x and crash-loop on
`ModuleNotFoundError: No module named 'mcp.server.fastmcp'`:

```txt
# requirements.txt
# Bounded to <2.0 — the 2.0 rewrite renames FastMCP and moves the
# module paths this template uses. Unbounding without migrating the
# server code will build green locally (against a pre-existing 1.x
# venv) and crash-loop on the first --no-cache rebuild.
mcp>=1.3,<2.0
```

`mcp` 1.x is in maintenance mode (security fixes only); the 2.x rewrite is
far enough that migrating warrants a considered code change, not an
accidental resolve during a rebuild. Migrate by removing the upper bound
AND updating imports/constructor to the 2.x API in the same commit.

Low-level SDK (Path B) servers also need `uvicorn` and `starlette` in
requirements.txt — FastMCP bundles those, the low-level SDK does not.

## Step 3: Configure Transport in MCP Server

### Path A: FastMCP (`mcp.server.fastmcp.FastMCP`)

FastMCP's constructor defaults override env vars, so host/port **must** be passed explicitly:

```python
import os
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "my_mcp_server",
    # Honor MCP_HOST/MCP_PORT as fallbacks: the template sets both name
    # pairs in the Dockerfile/compose, so a user who edits MCP_PORT
    # expecting it to take effect isn't silently ignored on Path A.
    host=os.getenv("FASTMCP_HOST", os.getenv("MCP_HOST", "127.0.0.1")),
    port=int(os.getenv("FASTMCP_PORT", os.getenv("MCP_PORT", "8000"))),
    stateless_http=True,
)

# ... register tools ...

if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)
```

**CRITICAL**: Without explicit `host`/`port` args, the container binds to `127.0.0.1` and is unreachable despite `FASTMCP_HOST=0.0.0.0` being set. This is because FastMCP's pydantic-settings defaults take precedence over env vars when constructor args are provided.

**CRITICAL**: `stateless_http=True` is required for `streamable-http` to actually be stateless (it has no effect on `sse`, which has its own per-connection state). Without it, the server tracks sessions via `Mcp-Session-Id` headers; if the proxy drops that header or the connection breaks, clients get `"Session not found"` errors. The combination of `streamable-http` AND `stateless_http=True` is what makes the SSE wedge bug class (see "Transport choice" above) structurally impossible — every POST stands alone, with no per-session handshake state to lose.

Supported transports:
- `stdio` — Local development (Claude Code local MCP servers)
- `streamable-http` — **Recommended.** Single `/mcp` endpoint, supports `stateless_http=True`, avoids the SSE wedge bug class.
- `sse` — Legacy. Two-endpoint protocol (`/sse` + `/messages/`). Wedge-prone with Claude Code; use only if forced by client compatibility.

### Path B: Low-level SDK (`mcp.server.Server`)

The low-level SDK requires manual transport wiring with Starlette and uvicorn. Each transport type uses different SDK classes and different endpoints.

#### Required imports

```python
import asyncio
import contextlib
import os
from collections.abc import AsyncIterator
from typing import Any

import uvicorn
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.server.stdio import stdio_server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Mount, Route
```

#### Server instance

```python
app = Server("my_mcp_server")

# ... register tools with @app.list_tools(), @app.call_tool(), etc. ...
```

#### stdio transport (local development)

```python
async def main_stdio() -> None:
    """Run the MCP server over stdio transport (local development)."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )
```

#### SSE transport

```python
def main_sse() -> None:
    """Run the MCP server over SSE transport (Docker/remote deployment)."""
    host: str = os.environ.get("MCP_HOST", "0.0.0.0")
    port: int = int(os.environ.get("MCP_PORT", "8000"))

    sse_transport = SseServerTransport("/messages/")

    async def handle_sse(request: Any) -> Response:
        async with sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await app.run(
                streams[0],
                streams[1],
                app.create_initialization_options(),
            )
        return Response()

    starlette_app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse_transport.handle_post_message),
        ],
    )

    uvicorn.run(starlette_app, host=host, port=port)
```

#### streamable-http transport

```python
def main_streamable_http() -> None:
    """Run the MCP server over streamable-http transport."""
    host: str = os.environ.get("MCP_HOST", "0.0.0.0")
    port: int = int(os.environ.get("MCP_PORT", "8000"))

    session_manager = StreamableHTTPSessionManager(
        app=app,
        json_response=False,
        stateless=True,
    )

    @contextlib.asynccontextmanager
    async def lifespan(starlette_app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    starlette_app = Starlette(
        routes=[
            Mount("/mcp", app=session_manager.handle_request),
        ],
        lifespan=lifespan,
    )

    uvicorn.run(starlette_app, host=host, port=port)
```

#### Transport selection

```python
if __name__ == "__main__":
    transport: str = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "stdio":
        asyncio.run(main_stdio())
    elif transport == "sse":
        main_sse()
    elif transport == "streamable-http":
        main_streamable_http()
    else:
        raise SystemExit(f"Unknown MCP_TRANSPORT: {transport} (expected: stdio, sse, streamable-http)")
```

## Step 4: Create build-publish.sh

```bash
#!/bin/sh
# Build and publish MCP Docker image
# Usage: ./build-publish.sh [--no-cache]

# Anchor to the script's directory so VERSION, Dockerfile, and `.` all
# resolve to the project root — not the caller's cwd. Without this,
# running as `./myapp/build-publish.sh` from a parent directory writes
# a stray VERSION in the parent, uses the parent as build context (which
# in a multi-repo workspace can sweep sibling projects into the image),
# and corrupts this project's version tracking.
cd "$(dirname "$0")" || exit 1

REGISTRY="{registry_url}"

NO_CACHE=""
if [ "$1" = "--no-cache" ]; then
    NO_CACHE="--no-cache"
fi

# Seed at 0, not 1: the version published is CURRENT+1, so seeding
# at 1 makes the very first image :2 and leaves :1 permanently missing
# from the registry.
if [ ! -f VERSION ]; then
    echo "0" > VERSION
fi

CURRENT_VERSION=$(cat VERSION)

case "$CURRENT_VERSION" in
    ''|*[!0-9]*)
        echo "ERROR: VERSION file contains non-numeric value: $CURRENT_VERSION"
        exit 1
        ;;
esac

NEXT_VERSION=$((CURRENT_VERSION + 1))

echo "Building ${REGISTRY}:${NEXT_VERSION}..."

docker build \
    --platform linux/amd64 \
    $NO_CACHE \
    -t "${REGISTRY}:${NEXT_VERSION}" \
    .

if [ $? -ne 0 ]; then
    echo "ERROR: Docker build failed"
    exit 1
fi

docker tag "${REGISTRY}:${NEXT_VERSION}" "${REGISTRY}:latest"
if [ $? -ne 0 ]; then
    echo "ERROR: Docker tag failed"
    exit 1
fi

echo "Pushing ${REGISTRY}:${NEXT_VERSION}..."
docker push "${REGISTRY}:${NEXT_VERSION}"
if [ $? -ne 0 ]; then
    echo "ERROR: Push failed"
    exit 1
fi

echo "Pushing ${REGISTRY}:latest..."
docker push "${REGISTRY}:latest"
if [ $? -ne 0 ]; then
    echo "ERROR: Push failed"
    exit 1
fi

echo "$NEXT_VERSION" > VERSION
echo "Published ${REGISTRY}:${NEXT_VERSION} and :latest"
```

If private dependencies, add `--secret id=cr_pat,env=CR_PAT` to `docker build` — the
Dockerfile's `--mount=type=secret,id=cr_pat` will read the value from the env-backed
secret. Do NOT use `--build-arg CR_PAT=$CR_PAT`: it records the token in every
layer that consumes the ARG, visible via `docker history --no-trunc` to anyone
who can pull the image.

Make executable: `chmod +x build-publish.sh`

## Step 5: Create .dockerignore

```
bin/
lib/
lib64/
include/
pyvenv.cfg
.venv/
.Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
tests/
.pytest_cache/
.coverage
htmlcov/
.git/
.gitignore
.env
VERSION
*.md
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store
```

## Step 6: Create docker-compose.yaml

```yaml
services:
  {service_name}:
    image: {registry_url}:latest
    container_name: {container_name}
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      MCP_TRANSPORT: streamable-http
      MCP_HOST: 0.0.0.0
      MCP_PORT: 8000
      # Add all app-specific env vars from example.env
    # volumes:
    #   - /path/to/cert.pem:/app/ca.pem:ro
```

> **FastMCP note**: If using FastMCP, also add `FASTMCP_HOST: 0.0.0.0` and `FASTMCP_PORT: 8000` to the environment section.

Include **all** environment variables from the project's example.env.

## Step 7: Create example.env

```bash
# MCP transport: "stdio" for local dev; "streamable-http" (recommended) or "sse" (legacy) for Docker/remote
MCP_TRANSPORT=streamable-http

# MCP network settings (used with streamable-http or sse transport)
# MCP_HOST=0.0.0.0
# MCP_PORT=8000

# FastMCP only: FastMCP reads these specific env vars for host/port binding.
# Not needed for low-level SDK servers.
# FASTMCP_HOST=0.0.0.0
# FASTMCP_PORT=8000

# App-specific variables below
```

## Step 8: Update .gitignore

Add `VERSION` and `.env` entries.

## Step 9: Nginx Reverse Proxy (if applicable)

If the MCP server will be behind nginx with HTTPS, see [references/nginx-sse.md](references/nginx-sse.md) for the config snippet. The same `location` block works cleanly for **both** transports — `proxy_buffering off` plus long `proxy_read_timeout` are still useful for streamable-http's optional server→client streaming responses.

## MCP Endpoints

Streamable-http (recommended) exposes:
- `/mcp` - Single endpoint (POST for requests, optional GET for server→client streams)

SSE (legacy) exposes:
- `/sse` - SSE connection endpoint
- `/messages/` - Message posting endpoint

## Claude Code Client Configuration

Connect to a remote MCP server in `.mcp.json`:

```json
{
  "mcpServers": {
    "my-mcp": {
      "type": "http",
      "url": "https://server.example.com/my-mcp/mcp",
      "headers": {
        "Authorization": "Bearer <token>"
      }
    }
  }
}
```

Auth is handled at the nginx layer via Bearer token headers. The MCP server does not need to know about authentication.

## Troubleshooting

**Container binds to 127.0.0.1 instead of 0.0.0.0 (FastMCP)** - FastMCP constructor defaults override env vars. Pass host/port explicitly in the FastMCP constructor (see Step 3, Path A).

**SSE connection stale / wedged after container restart or network blip** - When Claude Code's SSE GET dies, it auto-reconnects but does NOT re-run the `initialize` handshake; the new server-side session sees `tools/call` before `initialize`, the SDK raises `RuntimeError("Received request before initialization was complete")`, and the wire-level error becomes a generic `-32602 "Invalid request parameters"`. Claude Code treats `-32602` as unrecoverable and stays wedged on every subsequent call. Workaround: `/mcp` reload in Claude Code to force a fresh handshake. Real fix: migrate to `streamable-http` with `stateless_http=True` — that's exactly what this bug class needs (see "Transport choice" near the top). Upstream issue: [anthropics/claude-code#60061](https://github.com/anthropics/claude-code/issues/60061).

**PyPI package version stale in Docker image** - Publish the new version to PyPI before running build-publish.sh. Verify with `docker exec {container} pip show {package}`.

**Missing uvicorn or starlette (low-level SDK)** - Low-level SDK servers need `uvicorn` and `starlette` in `requirements.txt`. FastMCP bundles these, but the low-level SDK does not.

**Wrong transport route (low-level SDK)** - SSE uses `/sse` and `/messages/`, streamable-http uses `/mcp`. These are NOT interchangeable. Make sure the client URL matches the transport configured on the server.

**"Session not found" errors behind nginx** - The MCP SDK's streamable-http transport is stateful by default. During initialization, the server assigns a session ID and expects the client to send it back via the `Mcp-Session-Id` header on every request. Behind a reverse proxy, this header can be dropped or the SSE connection that maintains the session can be interrupted, causing `"Session not found"` errors. Fix: set `stateless_http=True` (FastMCP) or `stateless=True` (low-level SDK `StreamableHTTPSessionManager`). This disables session tracking so each request is handled independently. See the "Transport choice" section near the top — streamable-http + stateless is the recommended default for exactly this reason.

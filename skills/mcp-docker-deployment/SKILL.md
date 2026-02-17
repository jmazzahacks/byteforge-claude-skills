---
name: mcp-docker-deployment
description: Set up Docker deployment for FastMCP (Python) servers with SSE/streamable-http transport, automated versioning, and container registry publishing. Use when dockerizing an MCP server, containerizing a FastMCP app for remote access, deploying an MCP server behind nginx, or setting up a production MCP server with Docker. Covers Dockerfile, build scripts, docker-compose, and nginx reverse proxy for SSE streaming.
---

# MCP Docker Deployment

Containerize Python FastMCP servers for remote deployment with SSE or streamable-http transport, nginx reverse proxy with HTTPS, and GHCR publishing.

## Step 1: Gather Project Information

Ask the user:

1. **"What is your MCP server entry point file?"** (e.g., `my_mcp_server.py`)
2. **"What Python files/directories need to be copied into the container?"** (e.g., `tools/`, `models/`, `formatting.py`)
3. **"What container registry URL?"** (e.g., `ghcr.io/{org}/{project}`)
4. **"Does the MCP server need any environment variables?"** (list them for docker-compose and example.env)
5. **"Will this be behind an nginx reverse proxy with HTTPS?"** (yes/no - if yes, include nginx config)
6. **"Does it have private pip dependencies?"** (yes/no - if yes, needs CR_PAT build arg)

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

# SSE transport for Docker, bind to all interfaces
ENV MCP_TRANSPORT=sse
ENV FASTMCP_HOST=0.0.0.0
ENV FASTMCP_PORT=8000

CMD ["python", "{entry_point}"]
```

If private pip dependencies, add before `pip install`:
```dockerfile
ARG CR_PAT
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/* \
    && git config --global url."https://${CR_PAT}@github.com/".insteadOf "https://github.com/" \
    && pip install --no-cache-dir -r requirements.txt \
    && git config --global --unset url."https://${CR_PAT}@github.com/".insteadOf
```

## Step 3: Configure Transport in MCP Server

FastMCP's constructor defaults override env vars, so host/port **must** be passed explicitly:

```python
import os
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "my_mcp_server",
    host=os.getenv("FASTMCP_HOST", "127.0.0.1"),
    port=int(os.getenv("FASTMCP_PORT", "8000")),
)

# ... register tools ...

if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)
```

**CRITICAL**: Without explicit `host`/`port` args, the container binds to `127.0.0.1` and is unreachable despite `FASTMCP_HOST=0.0.0.0` being set. This is because FastMCP's pydantic-settings defaults take precedence over env vars when constructor args are provided.

Supported transports:
- `stdio` - Local development (Claude Code local MCP servers)
- `sse` - Server-Sent Events, works behind nginx reverse proxy
- `streamable-http` - Newer HTTP transport

## Step 4: Create build-publish.sh

```bash
#!/bin/sh
# Build and publish MCP Docker image
# Usage: ./build-publish.sh [--no-cache]

REGISTRY="{registry_url}"

NO_CACHE=""
if [ "$1" = "--no-cache" ]; then
    NO_CACHE="--no-cache"
fi

if [ ! -f VERSION ]; then
    echo "1" > VERSION
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

If private dependencies, add `--build-arg CR_PAT=$CR_PAT` to `docker build`.

Make executable: `chmod +x build-publish.sh`

## Step 5: Create .dockerignore

```
bin/
lib/
lib64/
include/
pyvenv.cfg
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
      MCP_TRANSPORT: sse
      FASTMCP_HOST: 0.0.0.0
      FASTMCP_PORT: 8000
      # Add all app-specific env vars from example.env
    # volumes:
    #   - /path/to/cert.pem:/app/ca.pem:ro
```

Include **all** environment variables from the project's example.env.

## Step 7: Create example.env

```bash
# MCP transport: "stdio" for local dev, "sse" for Docker/remote
MCP_TRANSPORT=sse

# FastMCP network settings (only used with SSE/streamable-http)
# FASTMCP_HOST=0.0.0.0
# FASTMCP_PORT=8000

# App-specific variables below
```

## Step 8: Update .gitignore

Add `VERSION` and `.env` entries.

## Step 9: Nginx Reverse Proxy (if applicable)

If the MCP server will be behind nginx with HTTPS, see [references/nginx-sse.md](references/nginx-sse.md) for the config snippet. SSE requires specific proxy settings to work correctly.

## MCP Endpoints

SSE transport exposes:
- `/sse` - SSE connection endpoint
- `/messages/` - Message posting endpoint

Streamable-http transport exposes:
- `/mcp` - Single endpoint

## Claude Code Client Configuration

Connect to a remote MCP server in `.mcp.json`:

```json
{
  "mcpServers": {
    "my-mcp": {
      "type": "http",
      "url": "https://server.example.com/my-mcp/sse",
      "headers": {
        "Authorization": "Bearer <token>"
      }
    }
  }
}
```

Auth is handled at the nginx layer via Bearer token headers. The MCP server does not need to know about authentication.

## Troubleshooting

**Container binds to 127.0.0.1 instead of 0.0.0.0** - FastMCP constructor defaults override env vars. Pass host/port explicitly (see Step 3).

**SSE connection stale after container restart** - Claude Code caches SSE connections. Reload Claude Code to establish a fresh connection.

**PyPI package version stale in Docker image** - Publish the new version to PyPI before running build-publish.sh. Verify with `docker exec {container} pip show {package}`.

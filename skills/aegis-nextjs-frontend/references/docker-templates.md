# Docker Templates Reference

This file contains Docker deployment templates for Aegis-powered Next.js frontends, including a multi-stage Dockerfile, docker-compose example, and a health check API route.

---

## Dockerfile

Three-stage build optimized for production Next.js standalone output. Uses a BuildKit `cr_pat` secret to authenticate against private GitHub npm packages.

```dockerfile
# syntax=docker/dockerfile:1
# =============================================================
# Stage 1: Dependencies
# Install all npm dependencies, including private GitHub packages.
# =============================================================
FROM node:24-alpine AS deps
WORKDIR /app

# Install git for GitHub dependencies
RUN apk add --no-cache git

COPY package.json package-lock.json ./

# Secret and Git config exist only for this RUN. npm may normalize GitHub
# dependencies to SSH URLs, so rewrite both transports without an SSH key.
RUN --mount=type=secret,id=cr_pat,required=true \
    GIT_CONFIG_COUNT=3 \
    GIT_CONFIG_KEY_0=url.https://github.com/.insteadOf \
    GIT_CONFIG_VALUE_0=ssh://git@github.com/ \
    GIT_CONFIG_KEY_1=url.https://github.com/.insteadOf \
    GIT_CONFIG_VALUE_1=git@github.com: \
    GIT_CONFIG_KEY_2=http.https://github.com/.extraheader \
    GIT_CONFIG_VALUE_2="Authorization: Basic $(printf 'x-access-token:%s' "$(cat /run/secrets/cr_pat)" | base64 | tr -d '\n')" \
    npm ci

# =============================================================
# Stage 2: Builder
# Build the Next.js application with environment variables
# baked into the client-side bundle.
# =============================================================
FROM node:24-alpine AS builder
WORKDIR /app

# Build-time arguments for NEXT_PUBLIC_* env vars (baked into client bundle)
ARG NEXT_PUBLIC_AEGIS_API_URL={aegis_api_url}
ARG NEXT_PUBLIC_SITE_DOMAIN={site_domain}
# Sibling-backend variant only (public URL and UUID, never a tenant key)
ARG NEXT_PUBLIC_BACKEND_API_URL
ARG NEXT_PUBLIC_AEGIS_SITE_ID

# Set as environment variables for the build
ENV NEXT_PUBLIC_AEGIS_API_URL=$NEXT_PUBLIC_AEGIS_API_URL
ENV NEXT_PUBLIC_SITE_DOMAIN=$NEXT_PUBLIC_SITE_DOMAIN
ENV NEXT_PUBLIC_BACKEND_API_URL=$NEXT_PUBLIC_BACKEND_API_URL
ENV NEXT_PUBLIC_AEGIS_SITE_ID=$NEXT_PUBLIC_AEGIS_SITE_ID

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules

# Copy source code
COPY . .

# Build the application
RUN npm run build

# =============================================================
# Stage 3: Runner
# Minimal production image using Next.js standalone output.
# Runs as non-root user for security.
# =============================================================
FROM node:24-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV DEBUG_LOCAL=false
# Loki logging vars — set via docker-compose or deployment config
# ENV LOKI_URL=https://loki.example.com
# ENV LOKI_USER=
# ENV LOKI_PASS=
# ENV LOKI_CA_PATH=

# Create non-root user for security
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy built application
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/api/health || exit 1

CMD ["node", "server.js"]
```

---

## .dockerignore

Required before `COPY . .`: local secrets and host artifacts must not enter any
build stage. Runtime env files are injected by the deployment, not copied.

```dockerignore
.git
node_modules
.next
out
coverage
.env
.env.*
*.env
**/.env*
**/.npmrc
**/.gitconfig
**/*.pem
**/*.key
**/secrets
VERSION
build-publish.sh
```

---

## docker-compose.example.yaml

```yaml
services:
  {project-name}-frontend:
    image: {registry_url}:latest
    # Or build locally with custom configuration:
    # build:
    #   context: .
    #   secrets:
    #     - cr_pat
    #   args:
    #     - NEXT_PUBLIC_AEGIS_API_URL={aegis_api_url}
    #     - NEXT_PUBLIC_SITE_DOMAIN={site_domain}
    #     # Sibling-backend variant only:
    #     - NEXT_PUBLIC_BACKEND_API_URL=${NEXT_PUBLIC_BACKEND_API_URL}
    #     - NEXT_PUBLIC_AEGIS_SITE_ID=${NEXT_PUBLIC_AEGIS_SITE_ID}
    ports:
      - "3000:3000"
    environment:
      # Default Next.js proxy only. For the sibling-backend variant, omit
      # these three variables here and configure them on that backend.
      # Server-side Aegis config (NOT baked into the client bundle).
      # The /api/frontend/auth/* proxy routes use these to call Aegis on
      # behalf of the browser. AEGIS_TENANT_API_KEY must never be exposed
      # to the browser — keep these unprefixed (no NEXT_PUBLIC_).
      - AEGIS_API_URL=${AEGIS_API_URL}
      - AEGIS_TENANT_API_KEY=${AEGIS_TENANT_API_KEY}
      - AEGIS_SITE_ID=${AEGIS_SITE_ID}
      - DEBUG_LOCAL=false
      - LOKI_URL=${LOKI_URL}
      - LOKI_USER=${LOKI_USER}
      - LOKI_PASS=${LOKI_PASS}
      # - LOKI_CA_PATH=/app/ca.pem
    restart: unless-stopped

# Uncomment with the local build block above:
# secrets:
#   cr_pat:
#     environment: CR_PAT
```

---

## Reverse Proxy Contract

These containers must run behind a reverse proxy that forwards three headers — without them, the next-intl middleware emits broken absolute redirects (e.g., a 307 from `/` to `https://your-host:3000/en` containing the local listener port instead of the public port):

| Header | Why it matters |
|--------|----------------|
| `X-Forwarded-Proto` | Sets the public scheme on `Location` headers (so they use `https://`, not `http://`). |
| `X-Forwarded-Host`  | Sets the public hostname when the inbound `Host` header is rewritten by the proxy. |
| `X-Forwarded-Port`  | Sets the public port — **without this, Next.js falls back to the local listener port (`3000`).** |

The scaffolded `proxy.ts` ships a defensive fallback that rewrites a malformed redirect's host using the inbound `Host` header (see `i18n-templates.md`). That fallback covers misconfigured proxies that still forward `Host` correctly, plus direct-access development like `docker run -p 3000:3000`. It is **not** a substitute for setting the `X-Forwarded-*` headers — fix the proxy.

### nginx

```nginx
location / {
    proxy_pass http://{project-name}-frontend:3000;

    proxy_set_header Host              $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host  $host;
    proxy_set_header X-Forwarded-Port  $server_port;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;

    # Required for Next.js streaming responses and HMR in dev.
    proxy_http_version 1.1;
    proxy_set_header Upgrade    $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

### Caddy

```caddy
example.com {
    reverse_proxy {project-name}-frontend:3000 {
        # Caddy sets X-Forwarded-Proto / X-Forwarded-Host / X-Forwarded-For
        # automatically. X-Forwarded-Port must be added explicitly.
        header_up X-Forwarded-Port {server_port}
    }
}
```

### Symptom Reference

| 307 `Location` looks like | Likely cause |
|---------------------------|--------------|
| `https://your-host:3000/en` | Missing `X-Forwarded-Port` (Next.js fell back to listener port). |
| `http://your-host/en` (when site is HTTPS) | Missing `X-Forwarded-Proto`. |
| Redirects to a different hostname than the user requested | Missing `X-Forwarded-Host` and inbound `Host` was rewritten. |

---

## Health Check API Route

**File:** `app/api/health/route.ts`

```typescript
import { NextResponse } from 'next/server';

export async function GET(): Promise<NextResponse> {
  return NextResponse.json({
    status: 'healthy',
    service: '{ProjectName} Frontend',
    timestamp: Math.floor(Date.now() / 1000),
  });
}
```

---

## Placeholder Replacement Guide

All placeholders in these templates **must** be replaced before use. The table below lists every placeholder, what it represents, and an example value.

| Placeholder | Description | Example |
|-------------|-------------|---------|
| `{aegis_api_url}` | Full URL to the Aegis backend API | `https://api.example.com` |
| `{site_domain}` | The frontend domain (no protocol) | `app.example.com` |
| `{project-name}` | Kebab-case project name for the docker-compose service | `my-app` |
| `{registry_url}` | Docker registry image URL | `ghcr.io/org/my-app-frontend` |
| `{ProjectName}` | PascalCase project name for the health check response | `MyApp` |

---

## Critical Notes

### Private GitHub Dependencies and CR_PAT

The token is mounted for the dependency install only; command-scoped
`GIT_CONFIG_*` variables supply an HTTPS authorization header and rewrite SSH
GitHub URLs. No token is embedded in a URL, ARG, ENV, or global .gitconfig.
Use a token with access to the dependency repositories. Git dependencies can
execute reviewed prepare scripts during npm ci; pin revisions, review those
scripts, and verify dist entrypoints after installation.

npm may normalize git+https dependencies to git+ssh in package-lock.json. Keep
the committed lockfile; the two rewrites handle both SSH forms. Do not delete a
lockfile just to change its transport. See
[Docker build secrets](https://docs.docker.com/build/building/secrets/).

### Next.js Standalone Output

The Dockerfile assumes Next.js is configured with standalone output. Ensure `next.config.ts` (or `next.config.mjs`) includes:

```typescript
const nextConfig = {
  output: 'standalone',
};
```

Without this, the `.next/standalone` directory will not be generated and Stage 3 will fail.

### NEXT_PUBLIC_* Variables Are Baked at Build Time

`NEXT_PUBLIC_*` environment variables are embedded into the JavaScript bundle at build time. They **cannot** be changed at runtime. This is why they are declared as `ARG` values in Stage 2 rather than `ENV` values in Stage 3. If you need to change these values, you must rebuild the Docker image.

### Server-Side Aegis Variables Are Runtime, Not Build-Time

`AEGIS_API_URL`, `AEGIS_TENANT_API_KEY`, and `AEGIS_SITE_ID` are **runtime** env vars. They are read by the `/api/frontend/auth/*` proxy routes on the server side — not baked into the client bundle. Do **not** prefix them with `NEXT_PUBLIC_` (that would publish the tenant key to every browser, defeating the entire gate). Pass them through `docker-compose` `environment:` or your orchestrator's secret-management instead. Changing them does not require a rebuild — just restart the container.

### Build Command

```bash
docker build \
  --secret id=cr_pat,env=CR_PAT \
  --build-arg NEXT_PUBLIC_AEGIS_API_URL="https://api.example.com" \
  --build-arg NEXT_PUBLIC_SITE_DOMAIN="app.example.com" \
  -t my-app-frontend:latest .
```

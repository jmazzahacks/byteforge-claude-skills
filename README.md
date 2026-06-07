# Byteforge Claude Skills

A collection of Claude Code skills by @jmazzahacks that codify best practices and reusable patterns for software development.

## Available Skills

### postgres-setup

A skill that provides a standardized pattern for setting up PostgreSQL databases with proper separation of schema and setup logic.

**What it creates:**
- `database/schema.sql` - SQL schema definitions
- `dev_scripts/setup_database.py` - Python setup script with `load_dotenv` support
- Project-specific environment variable naming
- Idempotent operations (safe to run multiple times)

**Features:**
- ✅ Parameterized project naming (not hardcoded)
- ✅ Unix timestamp convention for dates (BIGINT, not TIMESTAMP)
- ✅ UUID primary keys with `gen_random_uuid()`
- ✅ Proper permissions and user creation
- ✅ Connection pooling pattern with ThreadedConnectionPool
- ✅ Stale-connection-safe driver with retry on disconnect
- ✅ RealDictCursor for easy dict conversion

**Design Principles:**
1. **Unix Timestamps Only** - Use `BIGINT` for all date/time storage
2. **UUID Primary Keys** - Better for distributed systems
3. **Idempotent Operations** - `CREATE TABLE IF NOT EXISTS`, safe to re-run
4. **Separation of Concerns** - Schema in SQL, setup logic in Python
5. **No Hardcoded Credentials** - Everything via environment variables

[View full postgres-setup documentation →](./skills/postgres-setup/SKILL.md)

---

### python-lib-setup

A skill that provides a modern, standardized pattern for setting up Python libraries for PyPI publishing or private GitHub distribution.

**What it creates:**
- `pyproject.toml` - Modern Python project configuration with hatchling
- `src/{package_name}/` - Source layout with explicit package discovery
- `.gitignore` - Comprehensive Python artifact exclusions
- `dev-requirements.txt` - Development dependencies (includes build/twine for PyPI only)
- `build-publish.sh` - Automated build and publish script (PyPI only)
- `README.md` - Basic project documentation

**Features:**
- ✅ Modern pyproject.toml-based configuration (PEP 517/518)
- ✅ Src layout pattern for better code organization
- ✅ Explicit package discovery with hatchling
- ✅ Comprehensive .gitignore for Python projects
- ✅ PyPI or GitHub distribution paths
- ✅ Automated build-publish script with venv activation (PyPI path)
- ✅ git+https:// install instructions with CR_PAT patterns (GitHub path)
- ✅ Parameterized project setup (interactive questions)
- ✅ License selection (Proprietary, MIT, O'Saasy)
- ✅ Proper PyPI classifiers and metadata

**Design Principles:**
1. **Modern Standards** - Follows PEP 517/518, no setup.py needed
2. **Src Layout** - Clean separation of source code in src/ directory
3. **Explicit Configuration** - Explicit package discovery, no magic
4. **Virtual Environment Convention** - Uses bin/ at project root
5. **Comprehensive .gitignore** - Covers all common Python artifacts
6. **Interactive Setup** - Asks user questions before generating files
7. **Flexible Distribution** - Supports PyPI publishing and private GitHub libraries

[View full python-lib-setup documentation →](./skills/python-lib-setup/SKILL.md)

---

### flask-smorest-api

A skill that provides a production-ready pattern for building Flask REST APIs with automatic OpenAPI/Swagger documentation.

**What it creates:**
- Main application file with Flask app factory pattern and dotenv support
- Blueprint architecture for modular endpoint organization
- Marshmallow schema files for validation and documentation
- Singleton manager for shared service instances
- `example.env` with all required environment variables
- CORS support and error handling
- `requirements.txt` with all dependencies (unpinned)

**Features:**
- ✅ Automatic OpenAPI/Swagger documentation via flask-smorest
- ✅ Blueprint architecture for modularity
- ✅ MethodView classes for clean HTTP method handling
- ✅ Type-safe request/response with Marshmallow schemas
- ✅ Singleton manager pattern for database/service initialization
- ✅ CORS support for frontend integration
- ✅ Application factory pattern for testing
- ✅ Gunicorn production server support
- ✅ python-dotenv for environment variable management
- ✅ example.env pattern for configuration

**Design Principles:**
1. **Blueprint Organization** - One blueprint per feature/resource
2. **Schema-Driven** - Marshmallow schemas for validation and docs
3. **Singleton Manager** - Centralized service initialization
4. **Application Factory** - `create_app()` pattern for flexibility
5. **OpenAPI/Swagger** - Automatic documentation generation
6. **Environment-Based Config** - All secrets via environment variables with example.env
7. **Production Ready** - Gunicorn support out of the box

[View full flask-smorest-api documentation →](./skills/flask-smorest-api/SKILL.md)

---

### flask-docker-deployment

A skill that provides a production-ready Docker deployment pattern for Flask applications with automated versioning and container registry publishing.

**What it creates:**
- `Dockerfile` - Production container with Python 3.13, Gunicorn, and security best practices
- `build-publish.sh` - Automated build script with version management and --no-cache support
- `example.env` - Environment variables for container configuration
- `VERSION` file - Auto-incrementing version tracking (gitignored)
- `.gitignore` entry - Excludes VERSION and .env files
- `.dockerignore` - Optimizes build context by excluding unnecessary files (including .env)

**Features:**
- ✅ Python 3.13-slim base image
- ✅ Production-grade Gunicorn WSGI server with configurable workers
- ✅ Automated version management (auto-increment VERSION file)
- ✅ Security hardening (non-root user, minimal base image)
- ✅ Support for private Git dependencies via build args
- ✅ Dual tagging (version number + latest)
- ✅ --no-cache flag for fresh builds
- ✅ Platform specification for compatibility (linux/amd64)
- ✅ Works with GitHub Container Registry, Docker Hub, AWS ECR
- ✅ example.env pattern for environment configuration
- ✅ docker run --env-file support

**Design Principles:**
1. **Automated Versioning** - VERSION file auto-increments, never manually managed
2. **Security First** - Non-root user, slim base image, build-time secrets only
3. **Production Ready** - Gunicorn with multiple workers for concurrent requests
4. **Idempotent Builds** - Safe to run multiple times, version always increments
5. **Flexible Workers** - Configurable for web APIs (4 workers) or background jobs (1 worker)
6. **Registry Agnostic** - Works with any container registry (GHCR, Docker Hub, ECR)
7. **Cache Control** - --no-cache option for forcing fresh dependency installation
8. **Environment Configuration** - example.env pattern with .env gitignored

[View full flask-docker-deployment documentation →](./skills/flask-docker-deployment/SKILL.md)

---

### byteforge-loki-logging

A skill that integrates Grafana Loki logging into Python and Flask applications via the `byteforge-loki-logging` library — structured JSON logs, asynchronous shipping, and graceful console fallback.

**What it creates:**
- `requirements.txt` entry for `byteforge-loki-logging`
- `configure_logging()` call wired into the main application file
- Docker Compose volume mount for the Loki CA certificate
- Environment variable documentation for all Loki settings

**Features:**
- ✅ Structured JSON logging with consistent fields
- ✅ Asynchronous Loki shipping (never blocks the request path)
- ✅ Graceful console fallback when Loki is unreachable
- ✅ Standardized `application` label for cross-service Loki queries
- ✅ TLS via private CA certificate
- ✅ `DEBUG_LOCAL` toggle for console-only local development
- ✅ Multiprocessing-safe (handles fork() correctly)

**Design Principles:**
1. **Structured JSON** - Easier to query and filter in Loki
2. **Async Shipping** - Logging never blocks application code
3. **Graceful Fallback** - Console output if Loki is unreachable
4. **Single Convention** - All services use `application` as the label name
5. **Local-Dev Friendly** - `DEBUG_LOCAL` removes the Loki dependency in dev

[View full byteforge-loki-logging documentation →](./skills/byteforge-loki-logging/SKILL.md)

---

### aegis-nextjs-frontend

A skill that scaffolds a complete Next.js 16 frontend integrated with ByteForge Aegis authentication, internationalization (next-intl), Tailwind CSS v4, and Docker deployment. The generated project ships with login, email verification, password reset, and a protected dashboard out of the box.

**What it creates:**
- Next.js 16 App Router project with `[locale]` dynamic segments
- Full auth flow — login, email verification, password reset, email change confirmation, welcome
- Protected dashboard with redirect-on-unauthenticated
- Internationalization via next-intl (English, easily extensible)
- Singleton `browserClient` AuthClient with proactive token refresh
- `useAuth` React hook with auto-logout on refresh failure
- Server-side `/api/frontend/auth/*` proxy routes for Aegis's tenant-key-gated endpoints
- Reverse-proxy-safe i18n middleware with Host-header fallback
- Multi-stage Dockerfile with standalone output and `build-publish.sh`
- `/api/health` endpoint and Loki logging integration
- Aegis user-verified webhook reference implementation

**Features:**
- ✅ Next.js 16 App Router with i18n by default
- ✅ Full ByteForge Aegis auth flow (register, login, verify, reset)
- ✅ Server-side `X-Tenant-Api-Key` proxy (key never reaches the browser)
- ✅ `/api/auth/me` bearer-token introspection helpers (TS + Flask)
- ✅ Proactive token refresh with 5-minute buffer
- ✅ Tailwind CSS v4 design system with light/dark mode
- ✅ Production-ready Dockerfile with standalone output
- ✅ Reverse-proxy header contract documented (`X-Forwarded-*`)
- ✅ Webhook provisioning reference implementation
- ✅ Loki structured logging out of the box

**Design Principles:**
1. **Server-Side Secrets** - Tenant API key lives in env, never in the browser bundle
2. **Backend-Proxy Pattern** - Browser calls local proxy routes that forward to Aegis with the tenant key attached
3. **Proactive Token Refresh** - 5-minute buffer prevents mid-session expiry
4. **i18n by Default** - Every route is locale-prefixed from day one
5. **Reverse-Proxy Safe** - `proxy.ts` rewrites malformed redirect Locations when upstream misconfigures `X-Forwarded-*`
6. **Production-Ready Out of Box** - Health check, structured logging, standalone Docker output

[View full aegis-nextjs-frontend documentation →](./skills/aegis-nextjs-frontend/SKILL.md)

---

### mcp-docker-deployment

A skill that containerizes Python MCP (Model Context Protocol) servers for remote deployment, supporting both FastMCP and the low-level SDK with SSE or streamable-http transport.

**What it creates:**
- Multi-stage Dockerfile (Python 3.13-slim, non-root user)
- `build-publish.sh` with automated versioning and registry publishing
- `docker-compose.yaml` example with environment configuration
- Optional nginx reverse proxy config tuned for HTTPS and SSE streaming
- `example.env` for environment variables
- `.dockerignore`

**Features:**
- ✅ Supports both FastMCP and low-level `mcp.server.Server` SDK
- ✅ SSE and streamable-http transports (different endpoints, handled correctly)
- ✅ Automated `VERSION` file management
- ✅ Non-root container user
- ✅ Private Git dependency support via `CR_PAT` build arg
- ✅ Dual tagging (version + `latest`)
- ✅ nginx config sized for SSE streaming (long timeouts, no buffering)
- ✅ Compatible with GHCR, Docker Hub, ECR, or any OCI registry

**Design Principles:**
1. **Transport-Aware** - SSE and streamable-http have different endpoints; the skill emits the correct one
2. **Reverse-Proxy Friendly** - nginx config tuned for SSE (long timeouts, disabled buffering)
3. **Automated Versioning** - Same `VERSION` pattern as `flask-docker-deployment`
4. **Security First** - Non-root user, slim base image
5. **Registry Agnostic** - Works with any OCI-compatible registry

[View full mcp-docker-deployment documentation →](./skills/mcp-docker-deployment/SKILL.md)

---

### python-project-scaffold

A skill that scaffolds a multi-repo Python workspace with shared models library, core library, Flask backend, and optional sub-projects.

**What it creates:**
- Directory skeleton under `{project}/` with sub-project directories
- Root `CLAUDE.md` describing each sub-project and which skills to use
- Workspace `.gitignore` for Python projects
- Next-steps documentation for running existing skills

**Features:**
- ✅ Multi-repo workspace layout (models, core, backend)
- ✅ Optional sub-projects (scripts, API clients, frontend)
- ✅ Root CLAUDE.md with dependency chain and setup instructions
- ✅ References existing skills for actual code generation
- ✅ Celery + Redis option for background tasks
- ✅ License selection (Proprietary, MIT, O'Saasy)

**Design Principles:**
1. **Skeleton Only** - Creates structure, defers code generation to existing skills
2. **Multi-Repo Pattern** - Each sub-project is independent with its own venv and git
3. **Dependency Chain** - Models → Core → Backend, clearly documented
4. **Skill Composition** - Tells users which skills to run next in each directory
5. **Convention Enforcement** - CLAUDE.md encodes project conventions upfront

[View full python-project-scaffold documentation →](./skills/python-project-scaffold/SKILL.md)

---

### gatekeeper-nginx-setup

A skill that produces a complete nginx vhost for a ByteForge Gatekeeper deployment behind Cloudflare (Flask backend + Next.js frontend), with the four production-tested traps documented inline so future edits don't accidentally simplify them away.

**What it creates:**
- HTTP→HTTPS redirect + TLS 443 server block with Cloudflare Origin certificate paths
- `location /api/` → Flask backend (broad prefix, not per-route)
- `location /` → Next.js frontend with i18n-safe `X-Forwarded-Host` / `X-Forwarded-Port`
- `resolver` check + drop-in directive for container or host nginx
- Optional `/authz` + `/health` + `/metrics` block for external consumers
- Optional `auth_request` + CORS configuration for protected upstream services
- Four `curl` smoke tests with an expected-status matrix
- Symptom→cause→fix failure-decoder table mapped to the trap numbers

**Features:**
- ✅ Variable-form `proxy_pass` + `resolver` for container-restart resilience
- ✅ `X-Forwarded-Host` / `X-Forwarded-Port: 443` to prevent `:3000` redirect leaks
- ✅ Broad `/api/*` prefix block to prevent Cloudflare Error 1000 loops
- ✅ Cloudflare Origin TLS, HSTS, security headers
- ✅ 30s upstream timeouts sized for Aegis cold starts
- ✅ Optional CORS via `auth_request` with the working architecture (no `auth_request_set` traps)
- ✅ Inline rationale for every load-bearing decision (the Traps section)

**Design Principles:**
1. **Document the traps inline** — each load-bearing decision has a comment explaining the outage it prevents
2. **Defer DNS to request time** — the `set $var; proxy_pass http://$var:port;` pattern survives container churn
3. **Catch-all `/api/`** — never per-route, so new backend endpoints don't accidentally route to the frontend
4. **Forward all the i18n headers** — `X-Forwarded-Host` and `X-Forwarded-Port: 443` are not optional
5. **CORS responsibility split** — Gatekeeper enforces the origin allowlist, the upstream emits the headers

[View full gatekeeper-nginx-setup documentation →](./skills/gatekeeper-nginx-setup/SKILL.md)

---

### byteforge-prometheus-metrics

A skill that wires Prometheus metrics into a Python/Flask app **safely under multi-worker gunicorn**, with optional Redis-backed business metrics and a starter Grafana dashboard.

**What it creates:**
- `requirements.txt` entries for `prometheus_client`, `prometheus_flask_exporter`, optional `redis`
- `GunicornPrometheusMetrics` wired inside `create_app()` (post-fork safe)
- `gunicorn_conf.py` with `child_exit` hook for multiproc shard cleanup
- Dockerfile/docker-compose/systemd snippets for `PROMETHEUS_MULTIPROC_DIR` + tmpfs + startup dir cleanup
- Custom-metric examples for both file-multiproc (with Gauge `multiprocess_mode`) and Redis-backed business metrics
- Starter Grafana dashboard JSON (request rate, p50/p95/p99 latency, error rate, memory, CPU)
- Prometheus scrape config snippet
- Symptom→cause→fix failure decoder for the multi-worker traps

**Features:**
- ✅ Multi-worker gunicorn safe (no phantom `rate()`, no `process_start_time_seconds` plurality)
- ✅ `application` label matches [[byteforge-loki-logging]] for correlated log/metric queries
- ✅ Redis-backed custom collector for cross-worker business counters/gauges
- ✅ Gauge `multiprocess_mode` documented (otherwise silently dropped)
- ✅ tmpfs for the multiproc shard directory (no disk I/O per metric increment)
- ✅ Startup `rm -rf` ensures no stale-shard inflation after redeploys
- ✅ Post-deploy verification checklist (counter monotonicity, scrape parity)
- ✅ Importable Grafana dashboard parameterized on `application`

**Design Principles:**
1. **Multi-worker by default** — every Step assumes gunicorn workers > 1
2. **No silent drops** — Gauges declare `multiprocess_mode`, never assume defaults
3. **Source-of-truth Redis for business metrics** — cross-worker counters survive worker recycling
4. **Correlate with logs** — share the `application` label with the Loki skill
5. **Verify in prod, not just dev** — counter monotonicity check is part of the skill flow

[View full byteforge-prometheus-metrics documentation →](./skills/byteforge-prometheus-metrics/SKILL.md)

---

### flask-telegram-bot

A skill that wires a Telegram bot webhook endpoint into a Flask service using the public `byteforge-telegram` library — secret-token validation, command routing, and outbound notifications.

**What it creates:**
- Flask `/telegram/webhook` route with `X-Telegram-Bot-Api-Secret-Token` validation (`hmac.compare_digest`)
- `/health` endpoint for orchestration probes
- `src/telegram_webhook_handler.py` — `TelegramWebhookHandler` class routing slash commands to per-command methods, returning typed `TelegramResponse` objects
- `src/telegram_notifier.py` — wrapper around `TelegramBotController` for outbound pushes from anywhere in the app
- `requirements.txt` updates (`flask`, `gunicorn`, `byteforge-telegram`)
- `example.env` entries for bot token, webhook secret, and optional admin chat ID
- Instructions for running `setup-telegram-webhook --url ...` to register the webhook with Telegram

**Features:**
- ✅ HTTPS webhook (not long-polling) — lower latency, no idle traffic
- ✅ `hmac.compare_digest` secret-token validation by default (rejects forged requests)
- ✅ Dispatch table of slash commands → handler methods, easy to unit-test in isolation
- ✅ Type-safe `TelegramResponse` replies via the public `byteforge-telegram` package
- ✅ Separate outbound notifier so non-webhook code paths can push messages
- ✅ No private dependencies — `byteforge-telegram` is on PyPI
- ✅ Composes with [[flask-docker-deployment]], [[byteforge-loki-logging]], [[byteforge-prometheus-metrics]], [[gatekeeper-nginx-setup]], and [[postgres-setup]]

**Design Principles:**
1. **Webhook over polling** — production-grade delivery semantics from day one
2. **Always validate the secret token** — the webhook URL alone is not a secret
3. **Command routing as a dispatch table** — one method per command, returning `TelegramResponse`
4. **Outbound is a separate concern** — webhooks reply via response body, async paths push via `TelegramNotifier`
5. **Public deps only** — no `CR_PAT` token plumbing required

[View full flask-telegram-bot documentation →](./skills/flask-telegram-bot/SKILL.md)

---

### mcp-server-nginx-gatekeeper

A skill that wires a Streamable-HTTP MCP server (FastMCP or low-level SDK) into an nginx vhost behind ByteForge Gatekeeper, emitting a shared `conf.d/snippets/mcp-location.conf` so adding the fourth MCP doesn't mean copy-pasting 30 lines for the fourth time.

**What it creates:**
- `conf.d/snippets/mcp-location.conf` — shared auth/proxy/streaming snippet every MCP location `include`s
- Per-MCP `location /mcp-<NAME>` block — 8 lines that set the upstream/port, run the three rewrites, and include the snippet
- (Greenfield) Full umbrella `mcp.<DOMAIN>` server block — HTTP→HTTPS redirect, TLS 443, resolver, gatekeeper `/auth` include, `.well-known` bypass
- (Brownfield, optional) Refactor of existing inline MCP location blocks down to the 8-line wrapper
- Three smoke-test `curl` commands (auth required, OAuth bypass, authenticated request)
- Symptom→cause→fix failure decoder mapped to the trap numbers

**Features:**
- ✅ Shared snippet eliminates 30-line duplication per MCP location
- ✅ `.well-known/oauth-authorization-server` returns 404 (not 401) to force Claude Code onto the static bearer in `.mcp.json`
- ✅ Three-rewrite trio (`^/mcp-<NAME>$`, `^/mcp-<NAME>/$`, `^/mcp-<NAME>/(.+)`) makes path-prefix routing survive Streamable-HTTP's absolute upstream endpoint
- ✅ `proxy_buffering off` + 3600s read/send timeouts keep streaming connections alive
- ✅ Variable-form `proxy_pass http://$mcp_upstream:$mcp_port` + `resolver` survives container restarts
- ✅ Inbound `Authorization` header stripped before proxy (gatekeeper already authenticated)
- ✅ Snippet lives under `conf.d/snippets/` to avoid nginx auto-loading it at http{} scope

**Design Principles:**
1. **Snippet over copy-paste** — invariants (auth, proxy headers, streaming) live in one file every location includes
2. **Streamable-HTTP, not SSE** — SSE's relative `/messages/` URL breaks under path prefixes; streamable-http has no such trap
3. **Document the traps inline** — each load-bearing decision has a comment explaining the outage it prevents
4. **Compose with [[gatekeeper-nginx-setup]]** — `/auth` is defined once by that skill; this skill never redefines it
5. **Brownfield-first** — most real use is "I want to add another MCP", so the skill makes that case the cheapest

[View full mcp-server-nginx-gatekeeper documentation →](./skills/mcp-server-nginx-gatekeeper/SKILL.md)

---

### uv-supply-chain-hardening

A skill that converts a Python project's Docker build from a loose `pip install` into a locked, hash-verified, release-age-gated install using [uv](https://github.com/astral-sh/uv) — the direct response to supply-chain attacks where a compromised maintainer account publishes a malicious package version to PyPI.

**What it creates / changes:**
- `requirements.in` — human-edited source-of-truth list of direct dependencies
- `requirements.txt` — machine-generated, fully-pinned, `--generate-hashes` lock of the whole transitive tree
- `pyproject.toml` — adds `[tool.uv] exclude-newer` (rolling release-age gate) and pins the build backend
- `Dockerfile` — installs via a digest-pinned `uv` instead of pip; private-dep token becomes a build `ARG` only (never baked into the image)

**Features:**
- ✅ Three-layer defense: exact pins + per-artifact hashes + release-age gate
- ✅ Pins to the **currently-installed** versions (via a `pip freeze` constraint), not "latest" — reproduces what you actually tested
- ✅ Rolling `exclude-newer = "7 days"` refuses freshly-uploaded (possibly compromised) releases on both compile and install
- ✅ Pins the whole chain — app deps, the build backend, the uv binary (by `@sha256` digest), and Git deps (by commit SHA)
- ✅ Keeps credentials out of artifacts — build-time `ARG`, never image `ENV`, with a `docker inspect` verification step
- ✅ Documents the `--require-hashes` / unhashable-Git-dep tradeoff so it's a conscious decision
- ✅ Composes with [[flask-docker-deployment]], [[mcp-docker-deployment]], and [[python-lib-setup]]

**Design Principles:**
1. **Reproduce what you tested** — pin to installed versions, not latest
2. **Make tampering detectable** — hashes on every PyPI artifact
3. **Buy time against fresh malware** — a rolling release-age gate
4. **Pin the whole chain** — one floating link defeats the rest
5. **Keep credentials out of artifacts** — verify the token isn't baked into the image

[View full uv-supply-chain-hardening documentation →](./skills/uv-supply-chain-hardening/SKILL.md)

---

## Installation

### From GitHub (Recommended)

```bash
# Add the marketplace
/plugin marketplace add https://github.com/jmazzahacks/byteforge-claude-skills

# Install a specific skill
/plugin install postgres-setup@byteforge-claude-skills
```

### Local Development

```bash
# Clone the repository
git clone https://github.com/jmazzahacks/byteforge-claude-skills.git
cd byteforge-claude-skills

# Add as local marketplace
/plugin marketplace add /path/to/byteforge-claude-skills

# Install skills
/plugin install postgres-setup@byteforge-claude-skills
```

## Usage

Once installed, invoke skills by describing what you want to do. Skills are automatically activated based on your request.

### postgres-setup example:
```
User: "Set up postgres database for my project"
```

Claude will recognize the postgres-setup skill and:
1. Ask for your project name
2. Create directory structure
3. Generate `database/schema.sql` with best practices
4. Generate `dev_scripts/setup_database.py` with project-specific naming
5. Document required environment variables

### python-lib-setup example:
```
User: "Set up a Python package for PyPI"
```

Claude will recognize the python-lib-setup skill and:
1. Ask for project details (name, description, author, license, etc.)
2. Create src/ directory structure with package
3. Generate `pyproject.toml` with proper configuration
4. Create comprehensive `.gitignore`
5. Generate `build-publish.sh` script
6. Create `README.md` with setup instructions

### flask-smorest-api example:
```
User: "Set up Flask API server for my project"
```

Claude will recognize the flask-smorest-api skill and:
1. Ask for project name, features/endpoints, database needs, and port
2. Create `{project_name}.py` with Flask app factory
3. Generate blueprint structure for each feature
4. Create Marshmallow schema files for validation
5. Set up singleton manager for shared services
6. Create `requirements.txt` with dependencies
7. Document environment variables and startup instructions
8. Configure Swagger UI at `/swagger`

### flask-docker-deployment example:
```
User: "Dockerize my Flask application"
```

Claude will recognize the flask-docker-deployment skill and:
1. Ask for Flask entry point, port, registry URL, worker count
2. Ask if you have private Git dependencies
3. Create `Dockerfile` with Gunicorn and security best practices
4. Generate `build-publish.sh` with automated versioning
5. Add `VERSION` to `.gitignore`
6. Create `.dockerignore` for optimized builds
7. Document build/publish commands and environment variables
8. Provide examples for local testing and deployment

## Repository Structure

```
byteforge-claude-skills/
├── .claude-plugin/              # Plugin marketplace metadata
│   ├── plugin.json
│   └── marketplace.json
├── skills/                      # All skills
│   ├── postgres-setup/
│   ├── python-lib-setup/
│   ├── flask-smorest-api/
│   ├── flask-docker-deployment/
│   ├── byteforge-loki-logging/
│   ├── aegis-nextjs-frontend/
│   ├── mcp-docker-deployment/
│   ├── python-project-scaffold/
│   ├── gatekeeper-nginx-setup/
│   ├── byteforge-prometheus-metrics/
│   ├── flask-telegram-bot/
│   ├── mcp-server-nginx-gatekeeper/
│   └── uv-supply-chain-hardening/
├── CLAUDE.md                    # Development guide
└── README.md                    # This file
```

## Contributing

This collection is created and maintained by [@jmazzahacks](https://github.com/jmazzahacks).

Skills in this repository codify proven patterns from real-world projects, not experimental approaches. Each skill should be:
- **Reusable** - Work across different projects with parameter substitution
- **Interactive** - Ask user questions before generating code
- **Idempotent** - Safe to run multiple times
- **Well-documented** - Clear instructions and examples
- **Best-practice focused** - Proven patterns only

See [CLAUDE.md](./CLAUDE.md) for detailed contribution guidelines.

## License

MIT

## Credits

Created by Jason Byteforge ([@jmazzahacks](https://github.com/jmazzahacks))

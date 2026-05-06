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
│   └── python-project-scaffold/
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

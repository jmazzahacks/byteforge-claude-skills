# Byteforge Claude Skills

A collection of Claude Code skills by @jmazzahacks that codify best practices and reusable patterns for software development.

## Available Skills

### postgres-setup

A skill that provides a standardized pattern for setting up PostgreSQL databases with proper separation of schema and setup logic.

**What it creates:**
- `database/schema.sql` - SQL schema definitions
- `dev_scripts/setup_database.py` - Python setup script with test DB support
- Project-specific environment variable naming
- Idempotent operations (safe to run multiple times)

**Features:**
- ✅ Parameterized project naming (not hardcoded)
- ✅ Unix timestamp convention for dates (BIGINT, not TIMESTAMP)
- ✅ UUID primary keys with `gen_random_uuid()`
- ✅ Test database support (`--test-db` flag)
- ✅ Proper permissions and user creation
- ✅ Connection pooling pattern with ThreadedConnectionPool
- ✅ RealDictCursor for easy dict conversion

**Design Principles:**
1. **Unix Timestamps Only** - Use `BIGINT` for all date/time storage
2. **UUID Primary Keys** - Better for distributed systems
3. **Idempotent Operations** - `CREATE TABLE IF NOT EXISTS`, safe to re-run
4. **Separation of Concerns** - Schema in SQL, setup logic in Python
5. **Test Database Support** - Easy isolated testing with `--test-db`
6. **No Hardcoded Credentials** - Everything via environment variables

[View full postgres-setup documentation →](./skills/postgres-setup/SKILL.md)

---

### python-pypi-setup

A skill that provides a modern, standardized pattern for setting up Python packages for PyPI publishing.

**What it creates:**
- `pyproject.toml` - Modern Python project configuration with hatchling
- `src/{package_name}/` - Source layout with explicit package discovery
- `.gitignore` - Comprehensive Python artifact exclusions
- `requirements.txt` - Development dependencies (build, twine)
- `build-publish.sh` - Automated build and publish script with venv activation
- `README.md` - Basic project documentation

**Features:**
- ✅ Modern pyproject.toml-based configuration (PEP 517/518)
- ✅ Src layout pattern for better code organization
- ✅ Explicit package discovery with hatchling
- ✅ Comprehensive .gitignore for Python projects
- ✅ Automated build-publish script with venv activation
- ✅ Parameterized project setup (interactive questions)
- ✅ License selection (MIT, Apache-2.0, GPL-3.0, BSD-3-Clause)
- ✅ Proper PyPI classifiers and metadata

**Design Principles:**
1. **Modern Standards** - Follows PEP 517/518, no setup.py needed
2. **Src Layout** - Clean separation of source code in src/ directory
3. **Explicit Configuration** - Explicit package discovery, no magic
4. **Virtual Environment Convention** - Uses bin/ at project root
5. **Comprehensive .gitignore** - Covers all common Python artifacts
6. **Interactive Setup** - Asks user questions before generating files
7. **Automated Publishing** - Simple script for build and PyPI upload

[View full python-pypi-setup documentation →](./skills/python-pypi-setup/SKILL.md)

---

### flask-smorest-api

A skill that provides a production-ready pattern for building Flask REST APIs with automatic OpenAPI/Swagger documentation.

**What it creates:**
- Main application file with Flask app factory pattern
- Blueprint architecture for modular endpoint organization
- Marshmallow schema files for validation and documentation
- Singleton manager for shared service instances
- CORS support and error handling
- `requirements.txt` with all dependencies

**Features:**
- ✅ Automatic OpenAPI/Swagger documentation via flask-smorest
- ✅ Blueprint architecture for modularity
- ✅ MethodView classes for clean HTTP method handling
- ✅ Type-safe request/response with Marshmallow schemas
- ✅ Singleton manager pattern for database/service initialization
- ✅ CORS support for frontend integration
- ✅ Application factory pattern for testing
- ✅ Gunicorn production server support

**Design Principles:**
1. **Blueprint Organization** - One blueprint per feature/resource
2. **Schema-Driven** - Marshmallow schemas for validation and docs
3. **Singleton Manager** - Centralized service initialization
4. **Application Factory** - `create_app()` pattern for flexibility
5. **OpenAPI/Swagger** - Automatic documentation generation
6. **Environment-Based Config** - All secrets via environment variables
7. **Production Ready** - Gunicorn support out of the box

[View full flask-smorest-api documentation →](./skills/flask-smorest-api/SKILL.md)

---

### configure-loki-logging

A skill that configures Grafana Loki logging using the mazza-base utility library for structured, centralized logging.

**What it creates:**
- requirements.txt entry for mazza-base library
- Logging initialization code with configure_logging()
- CA certificate setup (mazza.vc_CA.pem)
- Dockerfile updates to include certificate
- Environment variable documentation for Loki configuration

**Features:**
- ✅ Structured JSON logging via mazza-base utility
- ✅ Local development mode with console logs
- ✅ Production mode with Loki integration
- ✅ Secure connection using CA certificates
- ✅ Application tagging for log identification
- ✅ Automatic mode detection (debug vs production)
- ✅ Easy integration with Flask applications

**Design Principles:**
1. **Dual Mode Operation** - Console logs for dev, Loki for production
2. **Structured Logging** - Consistent JSON format for queryability
3. **Secure by Default** - Uses CA certificates for encrypted connections
4. **Environment-Based Config** - All settings via environment variables
5. **Zero Boilerplate** - Single function call to configure logging
6. **Centralized Logs** - All services log to same Loki instance

[View full configure-loki-logging documentation →](./skills/configure-loki-logging/SKILL.md)

---

### flask-docker-deployment

A skill that provides a production-ready Docker deployment pattern for Flask applications with automated versioning and container registry publishing.

**What it creates:**
- `Dockerfile` - Multi-stage production container with Gunicorn and security best practices
- `build-publish.sh` - Automated build script with version management and --no-cache support
- `VERSION` file - Auto-incrementing version tracking (gitignored)
- `.gitignore` entry - Excludes VERSION file from version control
- `.dockerignore` - Optimizes build context by excluding unnecessary files

**Features:**
- ✅ Production-grade Gunicorn WSGI server with configurable workers
- ✅ Automated version management (auto-increment VERSION file)
- ✅ Security hardening (non-root user, minimal base image)
- ✅ Support for private Git dependencies via build args
- ✅ Dual tagging (version number + latest)
- ✅ --no-cache flag for fresh builds
- ✅ Platform specification for compatibility (linux/amd64)
- ✅ Works with GitHub Container Registry, Docker Hub, AWS ECR

**Design Principles:**
1. **Automated Versioning** - VERSION file auto-increments, never manually managed
2. **Security First** - Non-root user, slim base image, build-time secrets only
3. **Production Ready** - Gunicorn with multiple workers for concurrent requests
4. **Idempotent Builds** - Safe to run multiple times, version always increments
5. **Flexible Workers** - Configurable for web APIs (4 workers) or background jobs (1 worker)
6. **Registry Agnostic** - Works with any container registry (GHCR, Docker Hub, ECR)
7. **Cache Control** - --no-cache option for forcing fresh dependency installation

[View full flask-docker-deployment documentation →](./skills/flask-docker-deployment/SKILL.md)

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

### python-pypi-setup example:
```
User: "Set up a Python package for PyPI"
```

Claude will recognize the python-pypi-setup skill and:
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

### configure-loki-logging example:
```
User: "Configure Loki logging for my application"
```

Claude will recognize the configure-loki-logging skill and:
1. Ask for application tag/name and main application file
2. Add mazza-base to `requirements.txt` with CR_PAT setup
3. Add `configure_logging()` call to main application file
4. Document mazza.vc_CA.pem certificate requirement
5. Update Dockerfile to copy CA certificate
6. Document all required environment variables (MZ_LOKI_*, DEBUG_LOCAL, LOG_LEVEL)
7. Provide examples for local development vs production

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
├── .claude-plugin/           # Plugin marketplace metadata
│   ├── plugin.json
│   └── marketplace.json
├── skills/                   # All skills
│   ├── postgres-setup/
│   │   └── SKILL.md
│   ├── python-pypi-setup/
│   │   └── SKILL.md
│   ├── flask-smorest-api/
│   │   └── SKILL.md
│   ├── flask-docker-deployment/
│   │   └── SKILL.md
│   └── [future-skills]/
├── CLAUDE.md                 # Development guide
└── README.md                 # This file
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

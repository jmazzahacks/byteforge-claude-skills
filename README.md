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

## Repository Structure

```
byteforge-claude-skills/
├── .claude-plugin/           # Plugin marketplace metadata
│   ├── plugin.json
│   └── marketplace.json
├── skills/                   # All skills
│   ├── postgres-setup/
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

# PostgreSQL Setup Skill for Claude Code

A Claude Code skill that provides a standardized pattern for setting up PostgreSQL databases with proper separation of schema and setup logic.

## What This Skill Does

Creates a complete PostgreSQL database setup following best practices:
- **`database/schema.sql`** - SQL schema definitions
- **`dev_scripts/setup_database.py`** - Python setup script with test DB support
- Project-specific environment variable naming
- Idempotent operations (safe to run multiple times)

## Features

### Database Setup:
- ✅ Parameterized project naming (not hardcoded)
- ✅ Unix timestamp convention for dates (BIGINT, not TIMESTAMP)
- ✅ UUID primary keys with `gen_random_uuid()`
- ✅ Test database support (`--test-db` flag)
- ✅ Proper permissions and user creation
- ✅ Idempotent schema application

### Database Driver Pattern (optional):
- ✅ Connection pooling with ThreadedConnectionPool
- ✅ Context managers for automatic commit/rollback
- ✅ RealDictCursor for easy dict conversion when loading data
- ✅ Proper connection cleanup on destruction

## Installation

### Option 1: Local Installation (for development/testing)

```bash
# Create a local marketplace
mkdir -p ~/.claude/marketplaces/local
cd ~/.claude/marketplaces/local

# Clone or copy this plugin
cp -r /path/to/postgres-setup-skill .

# In Claude Code, add the marketplace
/plugin marketplace add ~/.claude/marketplaces/local

# Install the plugin
/plugin install postgres-setup@local
```

### Option 2: GitHub Repository (for sharing)

1. Push this directory to a GitHub repository
2. In Claude Code:
```
/plugin marketplace add https://github.com/yourusername/postgres-setup-skill
/plugin install postgres-setup@github
```

## Usage

Once installed, invoke the skill in any project:

```
User: "Set up postgres database for my project"
```

Claude will:
1. Ask for your project name
2. Create directory structure
3. Generate `database/schema.sql` with best practices
4. Generate `dev_scripts/setup_database.py` with project-specific naming
5. Document required environment variables

### Example Session

```
User: "Use the postgres-setup skill for my new project"
Claude: "What is your project name?"
User: "trading-bot"
Claude: [Creates files with TRADING_BOT_PG_PASSWORD, trading_bot user/db, etc.]
```

## Environment Variables Pattern

The skill generates project-specific environment variables:

**Global (same across all projects):**
- `PG_PASSWORD` - PostgreSQL superuser password

**Project-specific (generated based on project name):**
- `{PROJECT}_PG_DB` - Database name
- `{PROJECT}_PG_USER` - Application user
- `{PROJECT}_PG_PASSWORD` - Application password

Example for project "trading-bot":
- `TRADING_BOT_PG_DB`
- `TRADING_BOT_PG_USER`
- `TRADING_BOT_PG_PASSWORD`

## Design Principles

This skill follows these database design principles:

1. **Unix Timestamps Only** - Use `BIGINT` for all date/time storage (not TIMESTAMP, not TIMESTAMPTZ)
2. **UUID Primary Keys** - Better for distributed systems
3. **Idempotent Operations** - `CREATE TABLE IF NOT EXISTS`, safe to re-run
4. **Separation of Concerns** - Schema in SQL, setup logic in Python
5. **Test Database Support** - Easy isolated testing with `--test-db`
6. **No Hardcoded Credentials** - Everything via environment variables

## Based On

This skill codifies the database setup pattern from the [crypto-arcana](https://github.com/yourusername/crypto-arcana) project, which has proven effective for:
- AI agent systems
- Trading strategy evaluation
- Multi-environment deployments (dev/test/prod)

## Contributing

This skill was created by @jmazzahacks. Contributions welcome!

## License

MIT

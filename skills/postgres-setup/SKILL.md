---
name: postgres-setup
description: Set up PostgreSQL database with standardized schema.sql pattern. Use when starting a new project that needs PostgreSQL, setting up database schema, or creating setup scripts for postgres.
---

# PostgreSQL Database Setup Pattern

This skill helps you set up a PostgreSQL database following a standardized pattern with proper separation of schema and setup scripts.

## When to Use This Skill

Use this skill when:
- Starting a new project that needs PostgreSQL
- You want a clean separation between schema definition (SQL) and setup logic (Python)
- You want consistent environment variable patterns

## What This Skill Creates

1. **`database/schema.sql`** - SQL schema with table definitions
2. **`dev_scripts/setup_database.py`** - Python setup script (uses `python-dotenv` to load `.env`)
3. **Documentation** of required environment variables

**Dependencies**: The setup script requires `psycopg2` and `python-dotenv`. Ensure both are in `requirements.txt`:
```txt
psycopg2-binary
python-dotenv
```

## Step 1: Gather Project Information

**IMPORTANT**: Before creating files, ask the user these questions:

1. **"What is your project name?"** (e.g., "arcana", "trading-bot", "myapp")
   - Use this to derive:
     - Database name: `{project_name}` (e.g., `arcana`)
     - User name: `{project_name}` (e.g., `arcana`)
     - Password env var: `{PROJECT_NAME}_PG_PASSWORD` (e.g., `ARCANA_PG_PASSWORD`)

2. **"What tables do you need in your schema?"** (optional - can create skeleton if unknown)

## Step 2: Create Directory Structure

Create these directories if they don't exist:
```
{project_root}/
├── database/
└── dev_scripts/
```

## Step 3: Create schema.sql

Create `database/schema.sql` with:

### Best Practices to Follow:
- Use `CREATE TABLE IF NOT EXISTS` for idempotency
- Use `UUID` for primary keys with `gen_random_uuid()` as default
- Use `BIGINT` (Unix timestamps) for all date/time fields (NOT TIMESTAMP, NOT TIMESTAMPTZ)
- Add proper foreign key constraints with `ON DELETE CASCADE` or `ON DELETE SET NULL`
- Add indexes on foreign keys and commonly queried fields
- Use `TEXT` instead of `VARCHAR` (PostgreSQL best practice)
- Add comments using `COMMENT ON COLUMN` for documentation

### Template Structure:
```sql
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Example table
CREATE TABLE IF NOT EXISTS example_table (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    created_at BIGINT NOT NULL DEFAULT extract(epoch from now())::bigint,
    updated_at BIGINT
);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_example_created_at ON example_table(created_at);

-- Add comments
COMMENT ON TABLE example_table IS 'Description of what this table stores';
COMMENT ON COLUMN example_table.created_at IS 'Unix timestamp of creation';
```

If user provides specific tables, create schema accordingly. Otherwise, create a skeleton with one example table.

## Step 4: Create setup_database.py

Create `dev_scripts/setup_database.py` using this template, **substituting project-specific values**:

```python
#!/usr/bin/env python
"""
Database setup script for {PROJECT_NAME}
Creates the {project_name} database and user with proper permissions, then applies database/schema.sql

Usage:
  python setup_database.py --pg-password <postgres_password>
  python setup_database.py --pg-password <postgres_password> --pg-user <superuser>
"""

import os
import sys
import argparse
import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def main():
    """Setup {project_name} database and user"""
    load_dotenv()

    parser = argparse.ArgumentParser(description='Setup {PROJECT_NAME} database')
    parser.add_argument('--pg-password', required=True,
                       help='PostgreSQL superuser password (required)')
    parser.add_argument('--pg-user', default='postgres',
                       help='PostgreSQL superuser name (default: postgres)')
    args = parser.parse_args()

    pg_host = os.environ.get('POSTGRES_HOST', 'localhost')
    pg_port = os.environ.get('POSTGRES_PORT', '5432')
    pg_user = args.pg_user
    pg_password = args.pg_password

    {project_name}_db = os.environ.get('{PROJECT_NAME}_PG_DB', '{project_name}')
    {project_name}_user = os.environ.get('{PROJECT_NAME}_PG_USER', '{project_name}')
    {project_name}_password = os.environ.get('{PROJECT_NAME}_PG_PASSWORD', None)

    if {project_name}_password is None:
        print("Error: {PROJECT_NAME}_PG_PASSWORD environment variable is required")
        sys.exit(1)

    print(f"Setting up database '{{project_name}_db}' and user '{{project_name}_user}'...")
    print(f"Connecting to PostgreSQL at {pg_host}:{pg_port} as {pg_user}")

    try:
        conn = psycopg2.connect(
            host=pg_host,
            port=pg_port,
            database='postgres',
            user=pg_user,
            password=pg_password
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", ({project_name}_user,))
            if not cursor.fetchone():
                print(f"Creating user '{{project_name}_user}'...")
                cursor.execute(f"CREATE USER {project_name}_user WITH PASSWORD %s", ({project_name}_password,))
                print(f"✓ User '{{project_name}_user}' created")
            else:
                print(f"✓ User '{{project_name}_user}' already exists")

            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", ({project_name}_db,))
            if not cursor.fetchone():
                print(f"Creating database '{{project_name}_db}'...")
                cursor.execute(f"CREATE DATABASE {{project_name}_db} OWNER {{project_name}_user}")
                print(f"✓ Database '{{project_name}_db}' created")
            else:
                print(f"✓ Database '{{project_name}_db}' already exists")

            print("Setting permissions...")
            cursor.execute(f"GRANT ALL PRIVILEGES ON DATABASE {{project_name}_db} TO {{project_name}_user}")
            print(f"✓ Granted all privileges on database '{{project_name}_db}' to user '{{project_name}_user}'")

        conn.close()

        print(f"\\nConnecting as '{{project_name}_user}' to apply schema...")
        {project_name}_conn = psycopg2.connect(
            host=pg_host,
            port=pg_port,
            database={project_name}_db,
            user={project_name}_user,
            password={project_name}_password
        )
        {project_name}_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        schema_path = os.path.join(repo_root, 'database', 'schema.sql')
        if not os.path.exists(schema_path):
            print(f"Error: schema file not found at {schema_path}")
            sys.exit(1)

        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        with {project_name}_conn.cursor() as cursor:
            print("Ensuring required extensions...")
            cursor.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
            print(f"Applying schema from {schema_path}...")
            cursor.execute(schema_sql)
            print("✓ Schema applied")

        {project_name}_conn.close()
        print("✓ Database setup complete")
        print(f"Database: {{project_name}_db}")
        print(f"User: {{project_name}_user}")
        print(f"Host: {pg_host}:{pg_port}")

    except psycopg2.Error as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**CRITICAL**: Replace ALL instances of:
- `{PROJECT_NAME}` → uppercase project name (e.g., `ARCANA`, `MYAPP`)
- `{project_name}` → lowercase project name (e.g., `arcana`, `myapp`)

## Step 5: Create Documentation

Add a section to the project's README.md (or create SETUP.md) documenting:

### Command Line Arguments

**Required:**
- `--pg-password` - PostgreSQL superuser password

**Optional:**
- `--pg-user` - PostgreSQL superuser name (default: postgres)

### Environment Variables

**PostgreSQL connection (optional)**:
- `POSTGRES_HOST` - PostgreSQL host (default: localhost)
- `POSTGRES_PORT` - PostgreSQL port (default: 5432)

**Project-specific**:
- `{PROJECT_NAME}_PG_DB` - Database name (default: {project_name})
- `{PROJECT_NAME}_PG_USER` - Application user (default: {project_name})
- `{PROJECT_NAME}_PG_PASSWORD` - Application user password (REQUIRED)

### Setup Instructions

```bash
# Set required environment variables
export {PROJECT_NAME}_PG_PASSWORD="your_app_password"

# Run setup script (pass postgres superuser password as argument)
python dev_scripts/setup_database.py --pg-password "your_postgres_password"

# With custom superuser name
python dev_scripts/setup_database.py --pg-password "your_postgres_password" --pg-user "admin"
```

## Step 6: Make Script Executable

Run:
```bash
chmod +x dev_scripts/setup_database.py
```

## Step 7: Create Resilient Database Driver (Recommended for any long-running Python process)

For any project with a long-running Python process (Flask app, background worker, daemon), create a database driver that **survives upstream Postgres restarts**. The naïve pattern — `ThreadedConnectionPool.getconn()` straight into a query — wedges the entire process the moment Postgres goes away, because the pool happily hands out dead sockets and `getconn()` does zero health checking. Every request returns `OperationalError: server closed the connection unexpectedly` until the process is restarted.

The pattern below is production-tested: in one incident, an upstream Postgres restart left a naïve pool holding corpses for ~50 minutes until a manual deploy shipped a fix. With this pattern in place, the same situation self-heals in a handful of requests.

**Stack scope**: psycopg2 (sync). For asyncpg / SQLAlchemy / other drivers, you need a different pattern — this one does not translate.

### Why a naïve pool wedges

`psycopg2.pool.ThreadedConnectionPool` (and `SimpleConnectionPool`) treat every connection as alive until proven otherwise. If Postgres restarts or kicks an idle connection:
- Every pooled socket becomes a dead FD.
- `pool.getconn()` returns one anyway.
- The first query raises `psycopg2.OperationalError` / `psycopg2.InterfaceError`.
- The caller usually does plain `pool.putconn(conn)` on cleanup — which puts the **dead** conn right back into the pool for the next caller. Pool never self-heals.

The fix has two parts:
1. **Pre-ping** every checkout with `SELECT 1`. If it fails, discard with `putconn(close=True)` (the pool refills with a fresh socket) and retry up to `MAX_HEALTH_RETRIES` times.
2. **Discard mid-flight deaths**. If the caller's query raises a dead-conn error inside the yielded body, do `putconn(close=True)` rather than plain `putconn`, so the corpse leaves the pool instead of being recycled.

A short retry budget (3) is enough to drain a pool full of corpses on the first request after Postgres comes back up, without spinning forever if Postgres is genuinely down.

### File location

For a project that also uses the `flask-smorest-api` skill, place this at:
```
src/{project_name}/database.py
```
That's the path `flask-smorest-api`'s singleton manager imports from (`from src.{project_name}.database import Database`). For other layouts, put it wherever your application code can `import Database`.

### Template — `database.py`

```python
"""
Resilient PostgreSQL connection pool.

Wraps psycopg2.pool.ThreadedConnectionPool with:
  - TCP keepalives so the OS detects silently dropped connections.
  - Pre-ping (`SELECT 1`) before every checkout, with a small retry budget,
    so a pool full of corpses self-heals after an upstream Postgres restart.
  - Mid-flight dead-conn detection: if a query raises OperationalError /
    InterfaceError inside the yielded context, the connection is discarded
    with `putconn(close=True)` rather than being recycled.
  - Best-effort cleanup — rollback / cursor.close / putconn never raise
    a dead-conn error over the original exception.
"""

import logging
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool


logger = logging.getLogger(__name__)


# Errors that mean "this socket is unusable — discard, do not recycle."
_DEAD_CONN_ERRORS = (psycopg2.OperationalError, psycopg2.InterfaceError)

# How many times to retry checkout when pre-ping fails. Enough to drain
# a pool full of corpses after Postgres restarts; not so high that we
# spin forever if Postgres is genuinely down.
MAX_HEALTH_RETRIES = 3


class Database:
    def __init__(
        self,
        db_host: str,
        db_name: str,
        db_user: str,
        db_passwd: str,
        min_conn: int = 2,
        max_conn: int = 10,
    ) -> None:
        self.pool = ThreadedConnectionPool(
            min_conn,
            max_conn,
            host=db_host,
            database=db_name,
            user=db_user,
            password=db_passwd,
            # TCP keepalives — let the OS detect a silently dropped conn
            # within ~80s instead of "until next reboot."
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=5,
        )

    @staticmethod
    def _check_alive(conn) -> None:
        """Cheap `SELECT 1` pre-ping. Raises on dead conn."""
        cur = conn.cursor()
        try:
            cur.execute("SELECT 1")
            cur.fetchone()
        finally:
            cur.close()
        # Reset transaction state so the caller gets a clean slate.
        conn.rollback()

    @contextmanager
    def get_connection(self):
        """
        Yield a healthy pooled connection.

        Pre-pings before yielding. If the pool hands out a dead conn,
        discards it (so the pool refills with a fresh socket) and retries
        up to MAX_HEALTH_RETRIES times. On retry exhaustion, raises
        RuntimeError chained from the last underlying error.
        """
        last_err = None
        for attempt in range(MAX_HEALTH_RETRIES):
            conn = None
            try:
                conn = self.pool.getconn()
                self._check_alive(conn)
            except _DEAD_CONN_ERRORS as e:
                # Dead socket. Discard so the pool refills, then retry.
                last_err = e
                if conn is not None:
                    try:
                        self.pool.putconn(conn, close=True)
                    except Exception:
                        pass
                logger.warning(
                    "DB checkout pre-ping failed (attempt %d/%d): %s",
                    attempt + 1, MAX_HEALTH_RETRIES, e,
                )
                continue
            except BaseException:
                # Any other failure during checkout/probe — discard and
                # propagate so callers see the real error (DatabaseError
                # from failed-tx state, OSError, KeyboardInterrupt, ...).
                if conn is not None:
                    try:
                        self.pool.putconn(conn, close=True)
                    except Exception:
                        pass
                raise

            # Healthy conn — yield it.
            try:
                yield conn
            except _DEAD_CONN_ERRORS:
                # Mid-flight death. Discard with close=True so the corpse
                # doesn't go back into the pool, then re-raise.
                try:
                    self.pool.putconn(conn, close=True)
                except Exception:
                    pass
                raise
            except BaseException:
                try:
                    conn.rollback()
                except _DEAD_CONN_ERRORS:
                    pass
                try:
                    self.pool.putconn(conn)
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass
                raise
            else:
                try:
                    self.pool.putconn(conn)
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass
            return

        # Retries exhausted.
        raise RuntimeError(
            f"Could not acquire a healthy DB connection after "
            f"{MAX_HEALTH_RETRIES} attempts"
        ) from last_err

    @contextmanager
    def get_cursor(self, commit: bool = True, cursor_factory=RealDictCursor):
        """
        Yield a cursor inside a healthy connection.

        Defaults to RealDictCursor (project convention). Pass
        `cursor_factory=None` for the plain tuple-returning cursor.
        Cleanup (rollback, cursor.close) suppresses dead-conn errors
        so the caller sees the original exception, not a follow-on.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
                if commit:
                    conn.commit()
            except BaseException:
                try:
                    conn.rollback()
                except _DEAD_CONN_ERRORS:
                    pass
                raise
            finally:
                try:
                    cursor.close()
                except _DEAD_CONN_ERRORS:
                    pass

    def close(self) -> None:
        if self.pool and not self.pool.closed:
            self.pool.closeall()

    def __del__(self):
        if hasattr(self, "pool"):
            try:
                self.close()
            except Exception:
                pass
```

### pgvector — optional opt-in

If the project uses pgvector, register the type once per connection so query results come back as numpy arrays / lists. The cheapest hook is right after `_check_alive` inside `get_connection`, on the freshly-validated conn:

```python
from pgvector.psycopg2 import register_vector
# ...
self._check_alive(conn)
register_vector(conn, globally=True)  # opt-in; remove this line if pgvector is not used
```

Skip this block entirely if pgvector is not in use.

### Example usage

```python
import os
import time

db = Database(
    db_host=os.environ["{PROJECT_NAME}_DB_HOST"],
    db_name=os.environ["{PROJECT_NAME}_DB_NAME"],
    db_user=os.environ["{PROJECT_NAME}_DB_USER"],
    db_passwd=os.environ["{PROJECT_NAME}_DB_PASSWORD"],
)

# Read with RealDictCursor (default)
with db.get_cursor(commit=False) as cursor:
    cursor.execute("SELECT * FROM items WHERE id = %s", (item_id,))
    row = cursor.fetchone()  # dict, not tuple
    return Item.from_dict(dict(row))

# Write
with db.get_cursor() as cursor:
    cursor.execute(
        "INSERT INTO items (name, created_at) VALUES (%s, %s) RETURNING id",
        (name, int(time.time())),
    )
    new_id = cursor.fetchone()["id"]
```

### Recovery-path tests (mocked pool, no live Postgres)

Drop into `tests/test_database.py`. These cover the three critical paths without needing a running database:

```python
import psycopg2
import pytest
from unittest.mock import MagicMock

from {project_name}.database import Database, MAX_HEALTH_RETRIES


def _make_db_with_mocked_pool(connections):
    """Build a Database whose pool returns the given pre-built mock conns."""
    db = Database.__new__(Database)  # skip __init__'s real ThreadedConnectionPool
    db.pool = MagicMock()
    db.pool.getconn.side_effect = list(connections)
    return db


def _alive_conn():
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = (1,)
    return conn


def _dead_conn():
    conn = MagicMock()
    conn.cursor.return_value.execute.side_effect = psycopg2.OperationalError("dead")
    return conn


def test_dead_conn_on_first_checkout_retries_and_recovers():
    dead, alive = _dead_conn(), _alive_conn()
    db = _make_db_with_mocked_pool([dead, alive])

    with db.get_connection() as conn:
        assert conn is alive

    # Dead conn was discarded with close=True so the pool refills.
    db.pool.putconn.assert_any_call(dead, close=True)


def test_pool_full_of_corpses_raises_after_max_retries():
    corpses = [_dead_conn() for _ in range(MAX_HEALTH_RETRIES)]
    db = _make_db_with_mocked_pool(corpses)

    with pytest.raises(RuntimeError) as excinfo:
        with db.get_connection():
            pass

    assert isinstance(excinfo.value.__cause__, psycopg2.OperationalError)
    assert db.pool.putconn.call_count == MAX_HEALTH_RETRIES


def test_mid_flight_death_discards_conn_with_close():
    alive = _alive_conn()
    db = _make_db_with_mocked_pool([alive])

    with pytest.raises(psycopg2.OperationalError):
        with db.get_connection() as conn:
            raise psycopg2.OperationalError("conn died mid-query")

    # Mid-flight death MUST close the conn, not recycle it.
    db.pool.putconn.assert_called_once_with(alive, close=True)
```

## Design Principles

This pattern follows these principles:

### Database Schema:
1. **Separation of concerns** - SQL in .sql files, setup logic in Python
2. **Idempotency** - Safe to run multiple times
3. **Unix timestamps** - Always use BIGINT for dates/times (not TIMESTAMP types)
5. **UUIDs for keys** - Better for distributed systems
6. **Environment-based config** - No hardcoded credentials

### Database Driver (if applicable):
1. **Connection pooling** - Use ThreadedConnectionPool for efficient connection reuse
2. **TCP keepalives** - Enable keepalives on all pooled connections so the OS detects silently dropped sockets within ~80s
3. **Pre-ping on every checkout** - Run `SELECT 1` before yielding a pooled connection; on failure, discard with `putconn(close=True)` so the pool refills with a fresh socket
4. **Retry budget** - Allow up to `MAX_HEALTH_RETRIES` (3) pre-ping retries so a pool full of corpses self-heals in one request after Postgres comes back up; final failure raises `from last_err`
5. **Mid-flight death detection** - If a query raises a dead-conn error inside the yielded context, discard with `putconn(close=True)` rather than recycling the corpse
6. **Best-effort cleanup** - rollback / cursor.close / putconn must not raise dead-conn errors over the caller's original exception
7. **Context managers** - Automatic commit/rollback and resource cleanup
8. **RealDictCursor for reads** - Default `get_cursor` to `RealDictCursor` so reads return dicts
9. **Unix timestamps** - Store as BIGINT, convert only for display
10. **Proper cleanup** - Close pool on destruction

## Example Usage in Claude Code

User: "Set up postgres database for my project"
Claude: "What is your project name?"
User: "trading-bot"
Claude:
1. Creates database/ and dev_scripts/ directories
2. Creates database/schema.sql with skeleton
3. Creates dev_scripts/setup_database.py with:
   - TRADING_BOT_PG_PASSWORD
   - trading_bot database and user
4. Documents environment variables needed
5. Makes script executable

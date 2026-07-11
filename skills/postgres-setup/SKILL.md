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

1. **"What is your project name?"** (e.g., "myapp")
   - Use this to derive:
     - Database name: `{project_name}` (e.g., `myapp`)
     - User name: `{project_name}` (e.g., `myapp`)
     - Password env var: `{PROJECT_NAME}_DB_PASSWORD` (e.g., `MYAPP_DB_PASSWORD`)

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

    # Read the SAME env vars the runtime app (Step 7 driver /
    # flask-smorest-api singleton) reads, so setup and runtime resolve
    # the same database and credentials. Do NOT introduce a separate
    # naming here — a mismatch silently provisions a DB the app can't
    # authenticate to.
    pg_host = os.environ.get('{PROJECT_NAME}_DB_HOST', 'localhost')
    pg_port = os.environ.get('{PROJECT_NAME}_DB_PORT', '5432')
    pg_user = args.pg_user
    pg_password = args.pg_password

    {project_name}_db = os.environ.get('{PROJECT_NAME}_DB_NAME', '{project_name}')
    {project_name}_user = os.environ.get('{PROJECT_NAME}_DB_USER', '{project_name}')
    {project_name}_password = os.environ.get('{PROJECT_NAME}_DB_PASSWORD', None)

    if {project_name}_password is None:
        print("Error: {PROJECT_NAME}_DB_PASSWORD environment variable is required")
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
- `{PROJECT_NAME}` → uppercase project name (e.g., `MYAPP`)
- `{project_name}` → lowercase project name (e.g., `myapp`)

## Step 5: Create Documentation

Add a section to the project's README.md (or create SETUP.md) documenting:

### Command Line Arguments

**Required:**
- `--pg-password` - PostgreSQL superuser password

**Optional:**
- `--pg-user` - PostgreSQL superuser name (default: postgres)

### Environment Variables

All connection env vars are project-scoped and match the runtime app
(Step 7 driver / flask-smorest-api singleton), so setup and runtime
resolve the same database.

- `{PROJECT_NAME}_DB_HOST` - PostgreSQL host (default: localhost)
- `{PROJECT_NAME}_DB_PORT` - PostgreSQL port (default: 5432)
- `{PROJECT_NAME}_DB_NAME` - Database name (default: {project_name})
- `{PROJECT_NAME}_DB_USER` - Application user (default: {project_name})
- `{PROJECT_NAME}_DB_PASSWORD` - Application user password (REQUIRED)

### Setup Instructions

```bash
# Set required environment variables
export {PROJECT_NAME}_DB_PASSWORD="your_app_password"

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

The fix has three parts:
1. **Pre-ping** every checkout with `SELECT 1`. If it fails, discard with `putconn(close=True)` (the pool refills with a fresh socket) and retry up to `MAX_HEALTH_RETRIES` times.
2. **Discard mid-flight deaths, recycle mid-flight app errors**. If the conn dies during the yielded body, do `putconn(close=True)` so the corpse leaves the pool. But if a *healthy* conn raised an app-level error (`SerializationFailure`, `DeadlockDetected`, `QueryCanceled`, `LockNotAvailable` — all `OperationalError` subclasses), recycle it with plain `putconn` so the next checkout doesn't pay a full TCP+TLS+auth handshake.
3. **Classify with `conn.closed`, not exception type alone**. `OperationalError` is the parent class of both real socket deaths and the healthy-conn app errors above, so the exception class can't be the discriminator. Use rollback success + `conn.closed` (psycopg2 sets it non-zero only when the socket is actually broken) to decide discard vs recycle.

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
  - Mid-flight discard-vs-recycle: app-level errors on healthy conns
    (psycopg2.errors.SerializationFailure / DeadlockDetected /
    QueryCanceled / LockNotAvailable — all OperationalError subclasses
    that fire on perfectly healthy conns) recycle the conn so the next
    checkout doesn't pay a full TCP+TLS+auth handshake. Only unsafe
    conns discard with `putconn(close=True)`: rollback raises ANY
    error (dead socket OR corrupt transaction state — psycopg2 only
    flips conn.closed on socket death, not on transaction-state
    corruption) OR conn.closed != 0.
  - Best-effort cleanup — rollback / cursor.close / putconn never raise
    a dead-conn error over the original exception. Unexpected failures
    inside swallow arms are logged via `logger.exception` so they don't
    vanish silently while still letting the caller's exception propagate.
  - Signal-safe — cleanup arms catch `Exception`, not `BaseException`, so
    `KeyboardInterrupt` / `SystemExit` raised during rollback or cursor
    close still propagate. The cost: a conn raised-through-by-signal may
    leak out of the pool (the bare re-raise won't run putback). Accepted
    tradeoff — silently absorbing a SIGINT during cleanup is the worse
    failure mode, and process exit reclaims the socket anyway.

If you add Prometheus or other instrumentation that increments counters
around the checkout, put the increment INSIDE the outer try: so a signal
arriving in the one-bytecode window between `getconn()` and the try
can't strand a counter or leak a conn.
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
            # Best-effort cursor close. If cur.close() raises an
            # unexpected error (rare — e.g. psycopg2 C-extension state
            # corruption outside _DEAD_CONN_ERRORS), swallow it so the
            # rollback below still runs. The SELECT 1 exception path is
            # unaffected: if execute/fetchone raised, that exception
            # propagates through this finally clause untouched.
            try:
                cur.close()
            except Exception:
                logger.exception("DB cursor close failed during pre-ping cleanup")
        # Reset transaction state so the caller gets a clean slate.
        conn.rollback()

    @staticmethod
    def _is_dead_conn_error(conn, exc) -> bool:
        """
        Decide whether `exc` indicates the underlying socket is dead.

        InterfaceError → always dead (operations on a closed conn/cursor).
        OperationalError → ambiguous: it's the parent class of
            SerializationFailure, DeadlockDetected, QueryCanceled, and
            LockNotAvailable, all of which fire on perfectly healthy
            conns. Use `conn.closed` as the discriminator: psycopg2 sets
            it to non-zero only when the socket is actually broken.
        Anything else → not a dead-conn signal.
        """
        if isinstance(exc, psycopg2.InterfaceError):
            return True
        if isinstance(exc, psycopg2.OperationalError):
            return conn is None or getattr(conn, "closed", 0) != 0
        return False

    @staticmethod
    def _safe_putback(pool, conn, close: bool) -> None:
        """Best-effort return-to-pool. Falls back to conn.close() on pool error."""
        if conn is None:
            return
        try:
            pool.putconn(conn, close=close)
        except Exception:
            logger.exception("Pool putconn failed; falling back to direct conn.close()")
            try:
                conn.close()
            except Exception:
                logger.exception("Fallback conn.close() also failed during pool return")

    @contextmanager
    def get_connection(self):
        """
        Yield a healthy pooled connection.

        Pre-pings before yielding. If the pool hands out a dead conn,
        discards it (so the pool refills with a fresh socket) and retries
        up to MAX_HEALTH_RETRIES times. On retry exhaustion, raises
        RuntimeError chained from the last underlying error.

        Mid-flight handling discriminates between unsafe conns —
        rollback raises ANY error (dead socket OR corrupt transaction
        state) OR `conn.closed != 0` → discard with close=True — and
        app-level errors on healthy conns like SerializationFailure
        or DeadlockDetected where rollback succeeds cleanly (recycle
        into the pool, no TCP+auth churn).
        """
        last_err = None
        for attempt in range(MAX_HEALTH_RETRIES):
            conn = None
            try:
                conn = self.pool.getconn()
                self._check_alive(conn)
            except BaseException as e:
                # Checkout/probe failed. Always discard with close=True —
                # we don't trust a conn that failed pre-ping. Decide
                # retry-vs-propagate from whether the error means
                # "dead socket" (retry until budget) or "something else"
                # like KeyboardInterrupt / OSError / a non-dead OperationalError
                # (propagate immediately so the caller sees the real cause).
                dead = self._is_dead_conn_error(conn, e)
                self._safe_putback(self.pool, conn, close=True)
                if dead:
                    last_err = e
                    logger.warning(
                        "DB checkout pre-ping failed (attempt %d/%d): %s",
                        attempt + 1, MAX_HEALTH_RETRIES, e,
                    )
                    continue
                raise

            # Healthy conn — yield it. Mid-flight handling has to decide
            # discard-vs-recycle without trusting the exception class
            # alone (SerializationFailure / DeadlockDetected / QueryCanceled
            # all inherit from OperationalError but the conn is alive).
            try:
                yield conn
            except BaseException:
                conn_dead = False
                try:
                    conn.rollback()
                except _DEAD_CONN_ERRORS:
                    # Rollback itself couldn't talk to the conn → it's dead.
                    conn_dead = True
                except Exception:
                    # Rollback failed for an unexpected reason (not in
                    # _DEAD_CONN_ERRORS). conn.closed is unlikely to be
                    # flipped — psycopg2 only flips it on socket death —
                    # but transaction state is now unknown, possibly with
                    # the caller's writes still pending. Don't recycle a
                    # conn whose rollback we can't trust; discard with
                    # close=True so the pool refills with a clean socket.
                    # The unexpected rollback error is swallowed (not
                    # re-raised) so the caller's original exception
                    # still propagates.
                    #
                    # NB: this arm catches Exception, NOT BaseException.
                    # KeyboardInterrupt / SystemExit raised during
                    # conn.rollback() must propagate — silently absorbing
                    # them here would let a SIGINT during cleanup turn
                    # into "process keeps running through the user's
                    # Ctrl-C." The cost of letting them through is that
                    # this conn leaks (the bare `raise` below never
                    # reaches _safe_putback), but signal-during-rollback
                    # almost always means process exit, where the OS
                    # reclaims the socket anyway.
                    logger.exception(
                        "Unexpected DB rollback failure during mid-flight cleanup; "
                        "discarding conn"
                    )
                    conn_dead = True
                if not conn_dead:
                    conn_dead = getattr(conn, "closed", 0) != 0
                self._safe_putback(self.pool, conn, close=conn_dead)
                raise
            else:
                # Success path: mirror the exception branch's `conn.closed`
                # check so a conn that was closed directly inside the `with`
                # block (caller misuse or future helper bug) is discarded
                # instead of re-entering the pool as a corpse for the next
                # caller to pay pre-ping latency on.
                conn_dead = getattr(conn, "closed", 0) != 0
                self._safe_putback(self.pool, conn, close=conn_dead)
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
        Cleanup (rollback, cursor.close) swallows `Exception` so the
        caller's original exception always propagates — standard
        Python finally-cleanup idiom. `KeyboardInterrupt` / `SystemExit`
        still propagate through the cleanup arms. The mid-flight rollback
        in get_connection still runs after this returns and will discard
        a tainted conn with close=True.
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
                except Exception:
                    # Swallow any rollback failure so the caller's
                    # exception isn't masked. get_connection's mid-flight
                    # handler will run its own rollback and discard the
                    # conn with close=True if needed.
                    logger.exception("DB rollback failed during get_cursor cleanup")
                raise
            finally:
                try:
                    cursor.close()
                except Exception:
                    # Standard finally-cleanup idiom — never raise from
                    # finally; the caller's exception must survive.
                    logger.exception("DB cursor close failed during get_cursor cleanup")

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
    # Explicit closed=0 is REQUIRED — MagicMock would otherwise auto-create
    # a truthy attribute, which makes the `getattr(conn, "closed", 0) != 0`
    # check in get_connection misclassify every healthy conn as dead.
    conn.closed = 0
    return conn


def _dead_conn():
    conn = MagicMock()
    conn.cursor.return_value.execute.side_effect = psycopg2.OperationalError("dead")
    # psycopg2 sets `closed` to non-zero when the socket is actually broken.
    conn.closed = 2
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
    """A conn that dies mid-query (rollback then fails, conn.closed flips) is discarded."""
    alive = _alive_conn()
    db = _make_db_with_mocked_pool([alive])

    with pytest.raises(psycopg2.OperationalError):
        with db.get_connection() as conn:
            # Simulate the conn actually dying mid-query: the subsequent
            # rollback in the mid-flight handler raises, and conn.closed flips.
            conn.rollback.side_effect = psycopg2.OperationalError("conn died")
            conn.closed = 2
            raise psycopg2.OperationalError("query failed on dead conn")

    # Mid-flight death MUST close the conn, not recycle it.
    db.pool.putconn.assert_called_once_with(alive, close=True)


def test_serialization_failure_on_healthy_conn_recycles():
    """SerializationFailure inherits from OperationalError but conn is alive — recycle, don't churn."""
    alive = _alive_conn()
    db = _make_db_with_mocked_pool([alive])

    with pytest.raises(psycopg2.errors.SerializationFailure):
        with db.get_connection() as conn:
            raise psycopg2.errors.SerializationFailure("conflict")

    # Healthy conn — must recycle (close=False), NOT destroy.
    db.pool.putconn.assert_called_once_with(alive, close=False)


def test_value_error_on_silently_dead_conn_discards():
    """Non-DB exception + silently-dead conn → close=True (don't recycle the corpse)."""
    alive = _alive_conn()
    db = _make_db_with_mocked_pool([alive])

    with pytest.raises(ValueError):
        with db.get_connection() as conn:
            conn.rollback.side_effect = psycopg2.OperationalError("dead")
            conn.closed = 2
            raise ValueError("app error while conn was dying")

    db.pool.putconn.assert_called_once_with(alive, close=True)


def test_unexpected_rollback_failure_discards_conn():
    """Rollback raises a non-_DEAD_CONN_ERRORS exception → discard (transaction state is unknown).

    Guards against silently recycling a conn whose rollback we couldn't
    trust — psycopg2 won't flip conn.closed on transaction-state
    corruption, so the conn looks healthy but may have the previous
    caller's uncommitted writes still pending. The caller's original
    exception (ValueError here) must still propagate; the rollback
    exception is swallowed.
    """
    alive = _alive_conn()
    db = _make_db_with_mocked_pool([alive])

    with pytest.raises(ValueError):
        with db.get_connection() as conn:
            # Alive conn (closed=0) but rollback raises something
            # outside _DEAD_CONN_ERRORS — e.g. a psycopg2 internal
            # state error or a buggy session.
            conn.rollback.side_effect = RuntimeError("unexpected rollback failure")
            raise ValueError("app error mid-transaction")

    # Tainted conn MUST be discarded (close=True), NOT recycled —
    # transaction state is unknown and may include uncommitted writes.
    db.pool.putconn.assert_called_once_with(alive, close=True)


def test_keyboard_interrupt_during_rollback_propagates():
    """A signal raised during mid-flight rollback must propagate, not be swallowed.

    Regression guard for the v1.18.5 → v1.18.6 narrowing: the inner
    cleanup arm catches `Exception`, not `BaseException`, so a SIGINT
    arriving during `conn.rollback()` reaches the caller as
    KeyboardInterrupt instead of being silently absorbed (which would
    let the process keep running through the user's Ctrl-C).
    """
    alive = _alive_conn()
    db = _make_db_with_mocked_pool([alive])

    with pytest.raises(KeyboardInterrupt):
        with db.get_connection() as conn:
            conn.rollback.side_effect = KeyboardInterrupt
            raise ValueError("app error mid-transaction")


def test_success_path_silent_close_discards_conn():
    """The success-path `conn.closed` check must discard a silently-broken socket.

    Regression guard for the v1.18.6 F2 fix: caller exits cleanly (no
    exception), `conn.commit()` succeeds, but by the time control
    returns from the with-body the socket has been silently closed —
    only `conn.closed` carries that signal; there's no exception class
    to discriminate by. Without this test, the success-branch
    `conn_dead = getattr(conn, "closed", 0) != 0` line has zero
    coverage, and a future refactor could silently drop it while every
    other test still passes.

    Symmetric with `test_mid_flight_silent_close_uses_closed_flag` /
    the exception-path silent-close tests — those exercise the
    exception branch's `conn.closed` check; this exercises the
    success branch's.
    """
    alive = _alive_conn()
    db = _make_db_with_mocked_pool([alive])

    with db.get_connection() as conn:
        # No exception raised. But the socket is silently closed
        # by the time control returns from the with-body — only
        # the `closed` flag carries that signal.
        conn.closed = 2

    # Success-path silent-close MUST discard (close=True), not recycle
    # a corpse for the next caller to eat pre-ping latency on.
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
5. **Mid-flight discard vs recycle** - Distinguish unsafe conns (rollback raises ANY error — dead socket OR transaction-state corruption — OR `conn.closed != 0`) from app-level errors on healthy conns where rollback succeeded cleanly (`SerializationFailure` / `DeadlockDetected` / `QueryCanceled` / `LockNotAvailable` — all `OperationalError` subclasses that fire on live conns). Healthy conns recycle into the pool; unsafe conns discard with `putconn(close=True)`. Note psycopg2 only flips `conn.closed` on actual socket death, not on transaction-state corruption — so the rollback-failure signal is what catches the case where the socket is alive but the previous caller's writes may still be pending. The naïve "any `OperationalError` → close=True" pattern churns the pool under serializable-isolation or timeout-bounded workloads.
6. **Best-effort cleanup** - rollback / cursor.close / putconn must not raise dead-conn errors over the caller's original exception. Catch `Exception`, not `BaseException`, so `KeyboardInterrupt` / `SystemExit` still propagate; log any swallowed failure with `logger.exception` so silent observability gaps don't compound under load.
7. **Context managers** - Automatic commit/rollback and resource cleanup
8. **RealDictCursor for reads** - Default `get_cursor` to `RealDictCursor` so reads return dicts
9. **Unix timestamps** - Store as BIGINT, convert only for display
10. **Proper cleanup** - Close pool on destruction

## Example Usage in Claude Code

User: "Set up postgres database for my project"
Claude: "What is your project name?"
User: "myapp"
Claude:
1. Creates database/ and dev_scripts/ directories
2. Creates database/schema.sql with skeleton
3. Creates dev_scripts/setup_database.py with:
   - MYAPP_DB_PASSWORD
   - myapp database and user
4. Documents environment variables needed
5. Makes script executable

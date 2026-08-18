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
                cursor.execute(f"CREATE USER {{project_name}_user} WITH PASSWORD %s", ({project_name}_password,))
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

        print(f"\nConnecting as '{{project_name}_user}' to apply schema...")
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
  - Signal-safe with no pool leak on the pre-ping arm — that arm catches
    `BaseException`, always returns the conn to the pool (close=True),
    then re-raises non-`Exception` (KeyboardInterrupt / SystemExit /
    gevent Timeout). Retries only Exception subclasses. Rationale: a
    gevent/eventlet per-request timeout derives from BaseException and
    fires exactly where a pre-ping on a stale socket blocks, so catching
    only `Exception` here strands one pooled slot per occurrence until
    the pool exhausts and the worker wedges. The inner rollback arm
    (mid-flight) still catches `Exception` for its narrower reason:
    a signal DURING rollback must propagate immediately (not be
    absorbed into the caller's original exception) — the tradeoff there
    is one conn leaked on signal, which is acceptable because that path
    almost always means process exit.

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

# How many times to retry checkout when pre-ping fails PER REQUEST.
# 3 is calibrated for the default pool (`min_conn=2`) — it drains a
# fully-dead pool in a single post-restart request. Consumers that
# raise `min_conn` above 3 (e.g. `min_conn=10` for concurrent Flask
# workers) accept that post-restart recovery then takes
# `ceil(min_conn / MAX_HEALTH_RETRIES)` requests to fully drain the
# corpse queue — the first few requests still 500 with the RuntimeError
# raised below. This constant is deliberately NOT tunable higher
# (would cause requests to spin under a genuine Postgres outage);
# a burst of post-restart 500s is the price of not compounding a real
# outage into a request-latency stampede. If your service can't
# tolerate a post-restart burst, put a smarter retry / circuit-breaker
# at the request layer, not here.
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
        *,
        db_port: int = 5432,
    ) -> None:
        # `db_port` MUST match what setup_database.py provisioned against —
        # both read `{PROJECT_NAME}_DB_PORT`. Anywhere Postgres isn't on 5432
        # (Docker-mapped 5433, multi-instance hosts), a missing `port=` here
        # silently dials 5432 via libpq's default and either fails outright
        # or — worse — talks to a *different* Postgres that happens to
        # listen there. Ticket 881aa10a fix (v1.18.23).
        #
        # Placement note: `db_port` sits AFTER `max_conn` and is guarded by
        # `*,` so it is keyword-only. If it were inserted between `db_passwd`
        # and `min_conn`, any existing caller using `Database(h, n, u, p, 5, 20)`
        # (positional min_conn/max_conn from a pre-v1.18.23 scaffold) would
        # silently rebind db_port=5 and dial TCP port 5. Keyword-only forces
        # the intent explicit and preserves every prior positional call site.
        self.pool = ThreadedConnectionPool(
            min_conn,
            max_conn,
            host=db_host,
            port=db_port,
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

        Pre-pings before yielding. Checkout is a two-arm try/except,
        both arms untyped:
        - `pool.getconn()` carves out `psycopg2.pool.PoolError` (pool
          exhaustion — a concurrency problem in our code that cycling
          three more times cannot fix; propagate unwrapped so on-call
          reads "pool exhausted" rather than "Postgres unreachable"),
          then retries on ANY other Exception. During refill,
          `psycopg2.connect()` can raise `OperationalError`,
          `InterfaceError`, the bare `DatabaseError` parent (EOF
          before `PQstatus` flips), or a class future psycopg2
          releases pick that we haven't seen — all are connection-
          setup failures by construction (no query, so query-failure
          classes are unreachable). A typed classifier here just left
          "psycopg2 picked a new class" as a future should-have-
          retried bug (ticket 36892a9a).
        - `_check_alive` catches `BaseException`, discards the
          checked-out conn first, then decides retry-vs-propagate —
          signals still propagate, the conn still goes back. `SELECT 1`
          has no legitimate non-dead failure mode, so any Exception on
          that arm is treated as dead regardless of psycopg2 exception
          class. This covers psycopg2 raising the bare `DatabaseError`
          parent (not `OperationalError`) when it detects EOF before
          `conn.closed` flips — pre-split it surfaced as a raw 500 on
          the caller (ticket 5193642b).

        BaseException handling on the pre-ping arm (v1.18.22): once
        `getconn()` returns, the conn is OUT of the pool. A signal or
        gevent/eventlet `Timeout` unwinding through `_check_alive` MUST
        hand it back or the slot strands permanently — after `maxconn`
        such events, the getconn arm above correctly propagates the
        resulting `PoolError` (see the `except PoolError: raise` arm)
        and the worker wedges. The pre-ping blocks on the *exact*
        condition where a per-request timeout would fire (stale
        socket), so this path is not theoretical. Ticket f8e4b747 fix.

        On dead-conn signals, discards with close=True and retries up
        to MAX_HEALTH_RETRIES times. On retry exhaustion, raises
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
            try:
                conn = self.pool.getconn()
            except psycopg2.pool.PoolError:
                # Pool exhausted — every slot is checked out and cannot
                # be freed by retrying. This is a concurrency / capacity
                # problem in OUR code (leaked conns, undersized
                # `maxconn`, or a genuine request-rate spike), NOT a
                # Postgres availability problem. Propagate the original
                # `PoolError` unchanged so on-call sees "pool exhausted"
                # and looks at request concurrency, rather than seeing
                # the wrapped `RuntimeError("could not acquire...")`
                # below and looking at Postgres. Motivated by hivemake-
                # server ticket 36892a9a: a wrapped `PoolError` sent
                # on-call to the wrong layer during a live incident.
                raise
            except Exception as e:
                # Any other checkout failure is by construction a
                # connection-setup problem: `psycopg2.connect()` inside
                # the refill path can raise `OperationalError`,
                # `InterfaceError`, the bare `DatabaseError` parent
                # (EOF detected before `PQstatus` flips — same class of
                # bug as the pre-ping arm's, one layer up), or a class
                # future psycopg2 releases pick that we haven't seen.
                # Query-failure classes (`IntegrityError`,
                # `ProgrammingError`, `DataError`) CANNOT happen here —
                # there is no query. So retry on ANY non-`PoolError`
                # `Exception` without classification; keeping a typed
                # classifier here just left "psycopg2 picked a new
                # class" as a future should-have-retried bug (ticket
                # 36892a9a's "grep for the classifier, not the try-
                # block" observation).
                # `except Exception` (not `BaseException`): signals
                # bypass this handler and propagate directly, matching
                # the pre-ping and mid-flight cleanup arms.
                #
                # Known cost of untyped-retry: a truly non-transient
                # misconfiguration (`AttributeError` from a monkey-
                # patched pool, `TypeError` from a wrong-shaped
                # argument, a custom `AuthError` subclass some
                # deployment adapter raises) is also retried
                # MAX_HEALTH_RETRIES times before wrapping in the
                # `RuntimeError("could not acquire...") from last_err`.
                # Bounded delay + a few extra log lines; the
                # `__cause__` chain still exposes the original class
                # so nothing is hidden — just slower to surface.
                last_err = e
                logger.warning(
                    "DB pool getconn failed (attempt %d/%d): %s",
                    attempt + 1, MAX_HEALTH_RETRIES, e,
                    exc_info=True,
                )
                continue

            try:
                self._check_alive(conn)
            except BaseException as e:
                # Pre-ping failed. `SELECT 1` has no legitimate failure
                # mode other than a dead socket — treat any exception
                # as dead regardless of psycopg2 exception class. This
                # covers the bare `DatabaseError` raised when psycopg2
                # detects EOF (PQgetResult NULL) before `PQstatus` flips
                # `conn.closed` to non-zero — a typed classifier
                # couldn't see that as dead (pre-split combined-try),
                # and it surfaced as a raw 500 on the caller (real prod
                # incident, ticket 5193642b).
                #
                # `except BaseException` (not `Exception`): by the time
                # `_check_alive` runs, `conn` is already checked OUT of
                # the pool. A BaseException-derived unwind through here
                # (gevent/eventlet `Timeout`, `KeyboardInterrupt`,
                # `SystemExit`) MUST hand the conn back or the slot is
                # stranded permanently — one leak per occurrence, and
                # after `maxconn` events the pool exhausts, the getconn
                # arm above's explicit `except PoolError: raise` carve-
                # out correctly propagates the exhaustion unwrapped (so
                # on-call sees "pool exhausted", not the RuntimeError
                # wrapper), and the worker wedges. The gevent/eventlet
                # `Timeout` case is
                # correlated with this codepath: a per-request timeout
                # fires exactly where a pre-ping on a stale socket
                # blocks, not independently. Discard first, then decide
                # retry-vs-propagate — signals still propagate, the
                # conn still goes back. Ticket f8e4b747 fix (v1.18.22).
                self._safe_putback(self.pool, conn, close=True)
                if not isinstance(e, Exception):
                    raise
                last_err = e
                logger.warning(
                    "DB checkout pre-ping failed (attempt %d/%d): %s",
                    attempt + 1, MAX_HEALTH_RETRIES, e,
                    exc_info=True,
                )
                continue

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
    db_port=int(os.environ.get("{PROJECT_NAME}_DB_PORT", "5432")),
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

> **Verify each new regression test against the UNPATCHED code first.**
> Before adding a test alongside a fix, revert the fix locally and run
> the test — it MUST fail. A test written *from* the fix, *after* the
> fix, tends to restate the implementation instead of pinning the
> behavior, and ends up certifying whatever shape the code happens to
> have. The v1.18.21 KI test (`..._propagates`) asserted only that the
> signal escaped; that passed against the leaky shape AND the correct
> shape, so it signed off on a defect that took a downstream agent to
> catch (ticket f8e4b747). The v1.18.22 replacement
> (`..._without_leaking_conn`) fails against the leaky shape — that is
> what makes it a regression guard rather than a description.

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


def _dead_conn_bare_database_error():
    """Reproduces psycopg2's bare DatabaseError-with-closed=0 state when
    PQgetResult returns NULL for an EOF socket BEFORE PQstatus flips
    conn.closed to non-zero. Pre-fix, this leaked past the class-based
    classifier and surfaced as a raw 500 on the caller.
    """
    conn = MagicMock()
    conn.cursor.return_value.execute.side_effect = psycopg2.DatabaseError(
        "server closed the connection unexpectedly")
    conn.closed = 0  # critical — psycopg2 hasn't marked it dead yet
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


def test_bare_database_error_on_check_alive_retries_and_recovers():
    """Pre-ping raising the bare `psycopg2.DatabaseError` parent (not
    `OperationalError`) is treated as dead by the Exception-catching
    pre-ping arm — the direct reason the combined-try was split.

    Regression guard for ticket 5193642b: prod incident where a webhook
    POST 500'd because the pre-split classifier only matched
    OperationalError. The pre-ping arm is now untyped (v1.18.22).
    """
    dead, alive = _dead_conn_bare_database_error(), _alive_conn()
    db = _make_db_with_mocked_pool([dead, alive])

    with db.get_connection() as conn:
        assert conn is alive

    db.pool.putconn.assert_any_call(dead, close=True)


def test_check_alive_generic_exception_treated_as_dead():
    """Any exception from pre-ping — even a non-psycopg2 error — is
    treated as dead. Locks in the Option A design: `SELECT 1` has no
    legitimate non-dead failure mode, so the pre-ping arm doesn't
    reach for the class-based classifier.
    """
    dead = MagicMock()
    dead.cursor.return_value.execute.side_effect = RuntimeError("unexpected")
    dead.closed = 0
    alive = _alive_conn()
    db = _make_db_with_mocked_pool([dead, alive])

    with db.get_connection() as conn:
        assert conn is alive

    db.pool.putconn.assert_any_call(dead, close=True)


def test_pool_getconn_operational_error_retries_and_recovers():
    """The getconn arm (separate from the pre-ping arm) retries on
    dead-conn signals raised BY pool.getconn() itself. Locks in the
    second code path created by the pre-ping split — the pre-fix
    combined-try covered this case but the split introduced a new
    arm that needs its own coverage.
    """
    alive = _alive_conn()
    # First checkout raises OperationalError (dead socket surfaced by
    # pool.getconn() itself, not by the subsequent pre-ping); second
    # returns the alive conn. MagicMock.side_effect handles a mixed
    # list of exception instances and return values.
    db = _make_db_with_mocked_pool([psycopg2.OperationalError("dead"), alive])

    with db.get_connection() as conn:
        assert conn is alive


def test_pool_getconn_bare_database_error_retries_and_recovers():
    """`psycopg2.connect()` inside `pool.getconn()`'s refill path can raise
    the bare `psycopg2.DatabaseError` parent instead of `OperationalError`
    (same PQgetResult-vs-PQstatus timing bug as the pre-ping arm, one
    layer up). The getconn arm is untyped (v1.18.29) so the retry loop
    drains the corpse regardless of which class psycopg2 picked.
    Regression guard for v1.18.22 (bare-DatabaseError coverage) and
    v1.18.29 (untyped-getconn generalization).
    """
    alive = _alive_conn()
    db = _make_db_with_mocked_pool(
        [psycopg2.DatabaseError("server closed the connection unexpectedly"), alive]
    )

    with db.get_connection() as conn:
        assert conn is alive


def test_pool_getconn_pool_error_propagates_unwrapped():
    """`PoolError` on pool exhaustion must propagate as-is — NOT wrapped
    in `RuntimeError("could not acquire...")` and NOT swallowed into the
    retry loop. Cycling three more times cannot free an already-checked-
    out slot, and burying `PoolError` under the RuntimeError points on-
    call at Postgres instead of at request-volume. Pins the explicit
    `except PoolError: raise` carve-out at the top of the getconn arm
    (v1.18.29). Motivated by hivemake-server ticket 36892a9a where a
    wrapped PoolError sent on-call to the wrong layer during a live
    incident.
    """
    from psycopg2.pool import PoolError
    db = _make_db_with_mocked_pool([PoolError("connection pool exhausted")])

    with pytest.raises(PoolError):
        with db.get_connection():
            pass


def test_pool_getconn_arbitrary_exception_retries_and_recovers():
    """The getconn arm retries on ANY non-PoolError Exception, not just
    the psycopg2 classes we've historically seen. Locks in the untyped
    design (v1.18.29) so a future psycopg2 release that picks a novel
    class on connection failure — or a wrapper/adapter that re-raises
    with a custom class — doesn't reintroduce the "should have retried"
    bug that motivated splitting the getconn arm in v1.18.21. Motivated
    by hivemake-server ticket 36892a9a: "grep for the classifier, not
    the try-block" — a typed classifier here left every unseen class
    as a future should-have-retried bug.
    """
    alive = _alive_conn()
    db = _make_db_with_mocked_pool([
        RuntimeError("hypothetical class we haven't seen from psycopg2"),
        alive,
    ])

    with db.get_connection() as conn:
        assert conn is alive


def test_keyboard_interrupt_during_check_alive_propagates_without_leaking_conn():
    """A signal raised during pre-ping must propagate AND hand the
    checked-out conn back to the pool.

    Regression guard for ticket f8e4b747 (v1.18.22): the v1.18.21 shape
    caught `Exception` on this arm, which let any `BaseException`
    (KeyboardInterrupt, SystemExit, gevent/eventlet `Timeout`) escape
    without running `_safe_putback`. One pool slot stranded per
    occurrence; after `maxconn` events the pool exhausts and the
    getconn arm above correctly refuses to retry, wedging the worker.
    A propagation-only assertion (the v1.18.21 test) passes with AND
    without the leak — asserting `putconn(conn, close=True)` is what
    turns this into an actual regression guard rather than a
    defect-certifier.
    """
    dead = MagicMock()
    dead.cursor.return_value.execute.side_effect = KeyboardInterrupt
    dead.closed = 0
    db = _make_db_with_mocked_pool([dead])

    with pytest.raises(KeyboardInterrupt):
        with db.get_connection():
            pass

    # NOT merely "propagates" — the slot must go back, discarded.
    db.pool.putconn.assert_called_once_with(dead, close=True)


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

    Symmetric with `test_value_error_on_silently_dead_conn_discards` —
    that test exercises the exception branch's `conn.closed` check
    (silent close observed after an exception in the with-body); this
    one exercises the success branch's (silent close observed after a
    clean exit from the with-body).
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
4. **Retry budget** - Allow up to `MAX_HEALTH_RETRIES` (3) pre-ping retries PER REQUEST. For the default pool (`min_conn=2`) this drains a fully-dead pool in a single post-restart request. Consumers that raise `min_conn > MAX_HEALTH_RETRIES` (e.g. `min_conn=10` for concurrent Flask workers) accept that post-restart recovery takes `ceil(min_conn / MAX_HEALTH_RETRIES)` requests to drain — the first few still 500 with the RuntimeError raised from `last_err`. The constant is deliberately not tunable higher: a large retry budget would cause requests to spin under a genuine Postgres outage. If a post-restart 500-burst is unacceptable for the service, put a smarter retry / circuit-breaker at the request layer, not here.
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

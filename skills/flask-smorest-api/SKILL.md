---
name: flask-smorest-api
description: Set up Flask REST API with flask-smorest, OpenAPI docs, blueprint architecture, and dataclass models. Use when creating a new Flask API server, building REST endpoints, or setting up a production API.
---

# Flask REST API with flask-smorest Pattern

This skill helps you set up a Flask REST API following a standardized pattern with flask-smorest for OpenAPI documentation, blueprint architecture, and dataclass models for request/response handling.

## When to Use This Skill

Use this skill when:
- Starting a new Flask REST API project
- You want automatic OpenAPI/Swagger documentation
- You need a clean, modular blueprint architecture
- You want type-safe data models using dataclasses with to_dict/from_dict patterns
- You're building a production-ready API server

## What This Skill Creates

1. **Main application file** - Flask app initialization with flask-smorest
2. **Blueprint structure** - Modular endpoint organization
3. **Data models** - Dataclasses with to_dict/from_dict methods and validation
4. **Singleton manager pattern** - Centralized service/database initialization
5. **CORS support** - Cross-origin request handling
6. **Requirements file** - All necessary dependencies

## Step 1: Gather Project Information

**IMPORTANT**: Before creating files, ask the user these questions:

1. **"What is your project name?"** (e.g., "myapp")
   - Use this to derive:
     - Main module: `{project_name}.py` (e.g., `myapp.py`)
     - Port number (suggest based on project, default: 5000)

2. **"What features/endpoints do you need?"** (e.g., "users", "tokens", "orders")
   - Each feature will become a blueprint

3. **"Do you need database integration?"** (yes/no)
   - If yes, reference the `postgres-setup` skill for the database layer. **Use its Step 7 ("Create Resilient Database Driver") to scaffold `src/{project_name}/database.py`** — the singleton manager below imports `Database` from that exact path. The resilient pattern (pre-ping + retry + mid-flight death detection) is what keeps the Flask process from wedging when Postgres restarts; the naïve `ThreadedConnectionPool` pattern returns 500s on every request until the process restarts.

4. **"What port should the server run on?"** (default: 5000)

5. **"Do you want a Swagger UI docs endpoint at `/swagger`?"** (yes/no — **default no**)
   - **Default is no.** Most internal services (tailnet-only, backend-only, no need for a browsable doc surface) should keep it off — an exposed Swagger UI is attack surface they never asked for, and `flask-smorest`'s `Api()` / `Blueprint` / `abort` machinery all still work without any `OPENAPI_URL_PREFIX` / `OPENAPI_SWAGGER_UI_*` config (as long as `API_TITLE` / `API_VERSION` / `OPENAPI_VERSION` are set, which they are in the base template).
   - Say **yes** only if the service genuinely wants a browsable UI (public API, dev-portal, etc.). If yes, you'll be responsible for **vendoring `swagger-ui-dist` assets** under `/static/swagger-ui/` (or an internal mirror) — this skill no longer defaults to a third-party CDN (previous versions pointed `OPENAPI_SWAGGER_UI_URL` at `cdn.jsdelivr.net`, which is a supply-chain surface and doesn't work in air-gapped/tailnet-only environments).

## Step 2: Create Directory Structure

Create these directories if they don't exist:
```
{project_root}/
├── blueprints/          # Blueprint modules (one per feature)
│   ├── __init__.py
│   └── {feature}.py
├── models/              # Dataclass models with to_dict/from_dict
│   ├── __init__.py
│   └── {feature}.py
└── {project_name}.py    # Main application file
```

## Step 3: Create Main Application File

Create `{project_name}.py` using this template:

```python
import os
import logging
from flask import Flask
from flask_cors import CORS
from flask_smorest import Api
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    # These three are ALWAYS required by flask-smorest's `Api()`, even
    # when no Swagger UI is served — `Api()` refuses to initialize without
    # them. They govern the OpenAPI spec object flask-smorest builds in
    # memory (used for validation and, if enabled, doc-surface serving).
    app.config['API_TITLE'] = '{Project Name} API'
    app.config['API_VERSION'] = 'v1'
    app.config['OPENAPI_VERSION'] = '3.0.2'

    CORS(app)
    api = Api(app)

    from blueprints.{feature} import blp as {feature}_blp
    api.register_blueprint({feature}_blp)

    logger.info("Flask app initialized")
    return app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', {port_number}))
    app = create_app()
    app.run(host='0.0.0.0', port=port)
```

**CRITICAL**: Replace:
- `{Project Name}` → Human-readable project name (e.g., "My App")
- `{project_name}` → Snake case project name (e.g., "myapp")
- `{port_number}` → Actual port number (e.g., 5151)
- `{feature}` → Feature name from user's response

### Swagger UI enrichment (only if the user answered YES to Step 1 Q5)

If the user opted in to a Swagger UI docs endpoint, add these three
config lines to `create_app()` immediately after `OPENAPI_VERSION`, and
add the startup-log line inside the `__main__` block:

```python
    # Only present when Swagger UI is opted in (Step 1 Q5).
    # Vendor `swagger-ui-dist` assets under `/static/swagger-ui/` (or an
    # internal mirror you control) and set OPENAPI_SWAGGER_UI_URL to the
    # path you're serving them from. DO NOT point this at cdn.jsdelivr.net
    # or any third-party CDN — prior skill versions did, which was both a
    # supply-chain surface and a hard break in air-gapped / tailnet-only
    # deployments.
    app.config['OPENAPI_URL_PREFIX'] = '/'
    app.config['OPENAPI_SWAGGER_UI_PATH'] = '/swagger'
    app.config['OPENAPI_SWAGGER_UI_URL'] = '/static/swagger-ui/'  # TODO: vendor
```

And inside the `if __name__ == '__main__':` block, immediately after
`app = create_app()`:

```python
    logger.info(f"Swagger UI: http://localhost:{port}/swagger")
```

**Vendoring reminder:** whichever path you point `OPENAPI_SWAGGER_UI_URL`
at, that path must actually serve the swagger-ui-dist JS/CSS bundle. The
usual approach is `pip install swagger-ui-bundle` (or copy the files from
the npm package) and configure Flask to serve them from `/static/swagger-ui/`.
If that path 404s, `/swagger` renders a broken shell.

## Step 4: Create Data Models

For each feature, create a models file with dataclasses that include `to_dict` and `from_dict` methods:

### File: `models/{feature}.py`

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class {Feature}:
    """
    {Feature} data model.

    Includes validation in from_dict and serialization via to_dict.
    """
    id: str
    name: str
    created_at: int
    updated_at: Optional[int] = None

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON response."""
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> "{Feature}":
        """
        Create instance from dictionary with validation.

        Args:
            data: Dictionary with {feature} data

        Returns:
            {Feature} instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        if "id" not in data:
            raise ValueError("id is required")
        if "name" not in data:
            raise ValueError("name is required")
        if "created_at" not in data:
            raise ValueError("created_at is required")

        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            created_at=int(data["created_at"]),
            updated_at=int(data["updated_at"]) if data.get("updated_at") else None
        )
```

**CRITICAL**: Replace:
- `{Feature}` → PascalCase feature name (e.g., "TradableToken")
- `{feature}` → Snake case feature name (e.g., "tradable_token")

## Step 5: Create Blueprint Files

For each feature/endpoint, create a blueprint file:

### File: `blueprints/{feature}.py`

```python
import logging
from flask import request, jsonify
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from models.{feature} import {Feature}

logger = logging.getLogger(__name__)

blp = Blueprint('{feature}', __name__, url_prefix='/api', description='{Feature} API')


@blp.route('/{feature}')
class {Feature}ListResource(MethodView):
    def get(self):
        """Get list of {feature}s."""
        try:
            limit = request.args.get('limit', 100, type=int)
            offset = request.args.get('offset', 0, type=int)

            # TODO: Implement logic to fetch {feature}s
            items = []

            return jsonify({
                "data": [item.to_dict() for item in items],
                "limit": limit,
                "offset": offset
            })
        except ValueError as e:
            logger.warning(f"Bad request: {e}")
            abort(400, message=str(e))
        except Exception as e:
            logger.exception(f"Error fetching {feature}s: {e}")
            abort(500, message="Internal server error")

    def post(self):
        """Create a new {feature}."""
        try:
            data = request.get_json()
            if not data:
                abort(400, message="Request body is required")

            item = {Feature}.from_dict(data)

            # TODO: Implement logic to save {feature}

            return jsonify(item.to_dict()), 201
        except ValueError as e:
            logger.warning(f"Validation error: {e}")
            abort(400, message=str(e))
        except Exception as e:
            logger.exception(f"Error creating {feature}: {e}")
            abort(500, message="Internal server error")


@blp.route('/{feature}/<string:item_id>')
class {Feature}Resource(MethodView):
    def get(self, item_id: str):
        """Get a single {feature} by ID."""
        try:
            # TODO: Implement logic to fetch {feature} by ID
            item = None

            if not item:
                abort(404, message=f"{Feature} not found: {item_id}")

            return jsonify(item.to_dict())
        except Exception as e:
            logger.exception(f"Error fetching {feature}: {e}")
            abort(500, message="Internal server error")

    def put(self, item_id: str):
        """Update a {feature}."""
        try:
            data = request.get_json()
            if not data:
                abort(400, message="Request body is required")

            # TODO: Implement logic to update {feature}

            return jsonify({"message": "Updated"})
        except ValueError as e:
            logger.warning(f"Validation error: {e}")
            abort(400, message=str(e))
        except Exception as e:
            logger.exception(f"Error updating {feature}: {e}")
            abort(500, message="Internal server error")

    def delete(self, item_id: str):
        """Delete a {feature}."""
        try:
            # TODO: Implement logic to delete {feature}

            return jsonify({"message": "Deleted"})
        except Exception as e:
            logger.exception(f"Error deleting {feature}: {e}")
            abort(500, message="Internal server error")
```

**CRITICAL**: Replace:
- `{Feature}` → PascalCase feature name (e.g., "TradableToken")
- `{feature}` → Snake case feature name (e.g., "tradable_token")

## Step 6: Create Common Singleton Manager (If Needed)

If the project needs shared services (database, API clients, etc.), create a singleton manager:

### File: `common.py`

```python
"""
Singleton manager for shared service instances.

Provides centralized initialization of database connections, API clients,
and other shared resources.
"""

import os
import logging


logger = logging.getLogger(__name__)


class ServiceManager:
    """
    Singleton manager for shared service instances.

    Ensures only one instance of each service is created and reused
    across all blueprints.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ServiceManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Initialize services
        self._db = None
        self._initialized = True
        logger.info("ServiceManager initialized")

    def get_database(self):
        """
        Get database connection instance.

        Returns:
            Database connection instance (lazy initialization)
        """
        if self._db is None:
            # Import database driver — see postgres-setup Step 7 for the
            # resilient implementation (pre-ping + retry; survives PG restart).
            from src.{project_name}.database import Database

            # Get connection parameters from environment
            db_host = os.environ.get('{PROJECT_NAME}_DB_HOST', 'localhost')
            db_name = os.environ.get('{PROJECT_NAME}_DB_NAME', '{project_name}')
            db_user = os.environ.get('{PROJECT_NAME}_DB_USER', '{project_name}')
            db_passwd = os.environ.get('{PROJECT_NAME}_DB_PASSWORD')

            if not db_passwd:
                raise ValueError("{PROJECT_NAME}_DB_PASSWORD environment variable required")

            self._db = Database(db_host, db_name, db_user, db_passwd)
            logger.info("Database connection initialized")

        return self._db


# Global singleton instance
service_manager = ServiceManager()
```

**CRITICAL**: Replace:
- `{PROJECT_NAME}` → Uppercase project name (e.g., "MYAPP")
- `{project_name}` → Snake case project name (e.g., "myapp")

## Step 7: Create Environment Configuration

### File: `example.env`

Create or update `example.env` with required environment variables:

```bash
# Server Configuration
PORT={port_number}
DEBUG=False

# Database Configuration (if applicable)
{PROJECT_NAME}_DB_HOST=localhost
{PROJECT_NAME}_DB_NAME={project_name}
{PROJECT_NAME}_DB_USER={project_name}
{PROJECT_NAME}_DB_PASSWORD=your_password_here

# Optional: CORS Configuration
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
```

**CRITICAL**: Replace:
- `{port_number}` → Actual port number (e.g., 5151)
- `{PROJECT_NAME}` → Uppercase project name (e.g., "MYAPP")
- `{project_name}` → Snake case project name (e.g., "myapp")

### File: `.env` (gitignored)

Instruct the user to copy `example.env` to `.env` and fill in actual values:

```bash
# Copy example.env to .env and update with actual values
cp example.env .env
```

### Update .gitignore

Add `.env` to `.gitignore` if not already present:

```
# Environment variables
.env
```

## Step 8: Create Requirements File

Create `requirements.txt` with dependencies (no version pinning):

```txt
# Flask and API framework
Flask
flask-smorest
flask-cors

# Environment variable management
python-dotenv

# Production server (optional but recommended)
gunicorn

# Database (if needed)
psycopg2-binary
```

## Step 9: Create Blueprints __init__.py

Create `blueprints/__init__.py`:

```python
"""
Blueprint modules for {Project Name} API.

Each blueprint represents a distinct feature or resource endpoint.
"""
```

## Step 10: Document Usage

Create or update README.md with:

### Setup

```bash
# Copy example environment file
cp example.env .env

# Edit .env and fill in actual values
# Then install dependencies
pip install -r requirements.txt
```

### Running the Server

```bash
# Development mode
python {project_name}.py

# Production mode with Gunicorn
gunicorn -w 4 -b 0.0.0.0:{port_number} '{project_name}:create_app()'
```

### Environment Variables

Copy `example.env` to `.env` and configure:

**Server Configuration:**
- `PORT` - Server port (default: {port_number})
- `DEBUG` - Enable debug mode (default: False)

**Database (if applicable):**
- `{PROJECT_NAME}_DB_HOST` - Database host (default: localhost)
- `{PROJECT_NAME}_DB_NAME` - Database name (default: {project_name})
- `{PROJECT_NAME}_DB_USER` - Database user (default: {project_name})
- `{PROJECT_NAME}_DB_PASSWORD` - Database password (REQUIRED)

### API Documentation

(Only applicable if Swagger UI was opted in during Step 1 Q5.)

If enabled, access Swagger UI at:
```
http://localhost:{port_number}/swagger
```
Requires `swagger-ui-dist` assets to be served under
`OPENAPI_SWAGGER_UI_URL`; see the Swagger UI enrichment note in Step 3.

## Design Principles

This pattern follows these principles:

### Architecture:
1. **Blueprint Organization** - Modular endpoint organization, one blueprint per feature
2. **MethodView Classes** - Class-based views for HTTP methods (get, post, put, delete)
3. **Separation of Concerns** - Routes, models, and business logic separated
4. **Singleton Manager** - Centralized service initialization prevents duplicate connections
5. **Application Factory** - `create_app()` pattern for testing and flexibility

### Data Models:
1. **Dataclasses** - Type-safe data models using Python dataclasses
2. **to_dict/from_dict** - Consistent serialization and deserialization pattern
3. **Validation in from_dict** - Input validation with clear error messages
4. **Self-Contained** - Each model handles its own validation and serialization

### API Design:
1. **OpenAPI/Swagger** - Automatic documentation via flask-smorest
2. **Error Handling** - Consistent error responses with proper HTTP status codes
3. **CORS Support** - Cross-origin requests for frontend consumption
4. **JSON Responses** - All endpoints return JSON via jsonify()

### Best Practices:
1. **Environment-Based Config** - All secrets via environment variables
2. **Logging** - Structured logging throughout
3. **Idempotent Operations** - Safe to call multiple times
4. **Production Ready** - Gunicorn support out of the box
5. **Testing Friendly** - Application factory enables easy testing

## Integration with Other Skills

### Database Integration
If database is needed, use **postgres-setup** skill first:
```
User: "Set up postgres database for my project"
```

**Important**: When running `postgres-setup`, also follow its **Step 7 ("Create Resilient Database Driver")** to scaffold `src/{project_name}/database.py`. The singleton manager above imports `Database` from that path. Skipping Step 7 and using a naïve `ThreadedConnectionPool` will wedge the Flask process every time Postgres restarts.

Then reference the database in your blueprints via the singleton manager:
```python
from common import service_manager

db = service_manager.get_database()
```

### Package Structure
If publishing as a package, use **python-lib-setup** skill:
```
User: "Set up Python package for PyPI"
```

## Example Usage in Claude Code

**User:** "Set up Flask API server for my project"

**Claude:** "What is your project name?"

**User:** "crypto-tracker"

**Claude:** "What features/endpoints do you need?"

**User:** "prices, tokens, portfolio"

**Claude:** "Do you need database integration?"

**User:** "yes"

**Claude:** "What port should the server run on?"

**User:** "8080"

**Claude:**
1. Creates `crypto_tracker.py` with Flask app
2. Creates `models/` directory with dataclass models:
   - `prices.py`, `tokens.py`, `portfolio.py`
3. Creates `blueprints/` directory with endpoint handlers:
   - `prices.py`, `tokens.py`, `portfolio.py`
4. Creates `common.py` with ServiceManager singleton
5. Creates `requirements.txt` with dependencies
6. Documents environment variables needed
7. Provides startup instructions

## Optional: Docker Support

If user requests Docker, reference the **flask-docker-deployment** skill for production-ready containerization with automated versioning and health checks.

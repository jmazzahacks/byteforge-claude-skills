---
name: flask-smorest-api
description: Set up Flask REST API with flask-smorest, OpenAPI/Swagger docs, and blueprint architecture
---

# Flask REST API with flask-smorest Pattern

This skill helps you set up a Flask REST API following a standardized pattern with flask-smorest for OpenAPI documentation, blueprint architecture, and best practices for production-ready APIs.

## When to Use This Skill

Use this skill when:
- Starting a new Flask REST API project
- You want automatic OpenAPI/Swagger documentation
- You need a clean, modular blueprint architecture
- You want type-safe request/response handling with Marshmallow schemas
- You're building a production-ready API server

## What This Skill Creates

1. **Main application file** - Flask app initialization with flask-smorest
2. **Blueprint structure** - Modular endpoint organization
3. **Schema files** - Marshmallow schemas for validation and docs
4. **Singleton manager pattern** - Centralized service/database initialization
5. **CORS support** - Cross-origin request handling
6. **Requirements file** - All necessary dependencies

## Step 1: Gather Project Information

**IMPORTANT**: Before creating files, ask the user these questions:

1. **"What is your project name?"** (e.g., "materia-server", "trading-api", "myapp")
   - Use this to derive:
     - Main module: `{project_name}.py` (e.g., `materia_server.py`)
     - Port number (suggest based on project, default: 5000)

2. **"What features/endpoints do you need?"** (e.g., "users", "tokens", "orders")
   - Each feature will become a blueprint

3. **"Do you need database integration?"** (yes/no)
   - If yes, reference postgres-setup skill for database layer

4. **"What port should the server run on?"** (default: 5000)

## Step 2: Create Directory Structure

Create these directories if they don't exist:
```
{project_root}/
├── blueprints/          # Blueprint modules (one per feature)
│   ├── __init__.py
│   ├── {feature}.py
│   └── {feature}_schemas.py
├── src/                 # Optional: for package code (database drivers, models, etc.)
│   └── {project_name}/
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.config['API_TITLE'] = '{Project Name} API'
    app.config['API_VERSION'] = 'v1'
    app.config['OPENAPI_VERSION'] = '3.0.2'
    app.config['OPENAPI_URL_PREFIX'] = '/'
    app.config['OPENAPI_SWAGGER_UI_PATH'] = '/swagger'
    app.config['OPENAPI_SWAGGER_UI_URL'] = 'https://cdn.jsdelivr.net/npm/swagger-ui-dist/'

    CORS(app)
    api = Api(app)

    from blueprints.{feature} import blp as {feature}_blp
    api.register_blueprint({feature}_blp)

    logger.info("Flask app initialized")
    return app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', {port_number}))
    app = create_app()
    logger.info(f"Swagger UI: http://localhost:{port}/swagger")
    app.run(host='0.0.0.0', port=port)
```

**CRITICAL**: Replace:
- `{Project Name}` → Human-readable project name (e.g., "Materia Server")
- `{project_name}` → Snake case project name (e.g., "materia_server")
- `{port_number}` → Actual port number (e.g., 5151)
- `{feature}` → Feature name from user's response

## Step 4: Create Blueprint and Schema Files

For each feature/endpoint, create two files:

### File: `blueprints/{feature}.py`

```python
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from .{feature}_schemas import {Feature}QuerySchema, {Feature}ResponseSchema, ErrorResponseSchema

blp = Blueprint('{feature}', __name__, url_prefix='/api', description='{Feature} API')

@blp.route('/{feature}')
class {Feature}Resource(MethodView):
    @blp.arguments({Feature}QuerySchema, location='query')
    @blp.response(200, {Feature}ResponseSchema)
    @blp.alt_response(400, schema=ErrorResponseSchema)
    @blp.alt_response(500, schema=ErrorResponseSchema)
    def get(self, query_args):
        try:
            # TODO: Implement logic
            return {"message": "Success", "data": []}
        except ValueError as e:
            abort(400, message=str(e))
        except Exception as e:
            abort(500, message=str(e))
```

### File: `blueprints/{feature}_schemas.py`

```python
from marshmallow import Schema, fields

class {Feature}QuerySchema(Schema):
    limit = fields.Integer(load_default=100, metadata={'description': 'Max results'})
    offset = fields.Integer(load_default=0, metadata={'description': 'Skip count'})

class {Feature}ResponseSchema(Schema):
    message = fields.String(required=True)
    data = fields.List(fields.Dict(), required=True)

class ErrorResponseSchema(Schema):
    code = fields.Integer(required=True)
    status = fields.String(required=True)
    message = fields.String()
```

**CRITICAL**: Replace:
- `{Feature}` → PascalCase feature name (e.g., "TradableTokens")
- `{feature}` → Snake case feature name (e.g., "tradable_tokens")

## Step 5: Create Common Singleton Manager (If Needed)

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
            # Import database driver
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
- `{PROJECT_NAME}` → Uppercase project name (e.g., "MATERIA_SERVER")
- `{project_name}` → Snake case project name (e.g., "materia_server")

## Step 6: Create Requirements File

Create `requirements.txt` with flask-smorest dependencies:

```txt
# Flask and API framework
Flask==3.0.0
flask-smorest==0.44.0
flask-cors==4.0.0

# Schema validation and serialization
marshmallow==3.20.1

# Production server (optional but recommended)
gunicorn==21.2.0

# Database (if needed)
psycopg2-binary==2.9.9
```

## Step 7: Create Blueprints __init__.py

Create `blueprints/__init__.py`:

```python
"""
Blueprint modules for {Project Name} API.

Each blueprint represents a distinct feature or resource endpoint.
"""
```

## Step 8: Document Usage

Create or update README.md with:

### Running the Server

```bash
# Development mode
python {project_name}.py

# Production mode with Gunicorn
gunicorn -w 4 -b 0.0.0.0:{port_number} '{project_name}:create_app()'
```

### Environment Variables

**Server Configuration:**
- `PORT` - Server port (default: {port_number})
- `DEBUG` - Enable debug mode (default: False)

**Database (if applicable):**
- `{PROJECT_NAME}_DB_HOST` - Database host (default: localhost)
- `{PROJECT_NAME}_DB_NAME` - Database name (default: {project_name})
- `{PROJECT_NAME}_DB_USER` - Database user (default: {project_name})
- `{PROJECT_NAME}_DB_PASSWORD` - Database password (REQUIRED)

### API Documentation

Once running, access Swagger UI at:
```
http://localhost:{port_number}/swagger
```

## Design Principles

This pattern follows these principles:

### Architecture:
1. **Blueprint Organization** - Modular endpoint organization, one blueprint per feature
2. **MethodView Classes** - Class-based views for HTTP methods (get, post, put, delete)
3. **Separation of Concerns** - Routes, schemas, and business logic separated
4. **Singleton Manager** - Centralized service initialization prevents duplicate connections
5. **Application Factory** - `create_app()` pattern for testing and flexibility

### API Design:
1. **OpenAPI/Swagger** - Automatic documentation via flask-smorest
2. **Schema-Driven** - Marshmallow schemas for validation and serialization
3. **Type Safety** - `@blp.arguments()` and `@blp.response()` decorators
4. **Error Handling** - Consistent error responses with proper HTTP status codes
5. **CORS Support** - Cross-origin requests for frontend consumption

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

Then reference the database in your blueprints via the singleton manager:
```python
from common import service_manager

db = service_manager.get_database()
```

### Package Structure
If publishing as a package, use **python-pypi-setup** skill:
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
2. Creates `blueprints/` directory with:
   - `prices.py` and `prices_schemas.py`
   - `tokens.py` and `tokens_schemas.py`
   - `portfolio.py` and `portfolio_schemas.py`
3. Creates `common.py` with ServiceManager singleton
4. Creates `requirements.txt` with dependencies
5. Documents environment variables needed
6. Provides startup instructions

## Optional: Docker Support

If user requests Docker, create `Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE {port_number}
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:{port_number}", "{project_name}:create_app()"]
```

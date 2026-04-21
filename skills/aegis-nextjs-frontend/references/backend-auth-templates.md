# Backend Token Validation Reference (`/api/auth/me`)

This file documents how a **backend** that receives Aegis-issued bearer tokens from the frontend should validate them using the `GET /api/auth/me` introspection endpoint. The frontend itself does not call `/me` — it already has user info from `/api/auth/login`. These patterns are for the backend services the frontend talks to.

## Why `/api/auth/me` Exists

Before this endpoint, a downstream service holding an Aegis `auth_token` had three bad options:

1. Query the Aegis DB directly (breaks the service boundary).
2. Force the user to re-authenticate against each service (bad UX).
3. Build a custom "exchange" endpoint that trusts a client-asserted `user_id` — **this is exploitable**: anyone who guesses a `user_id` can mint service credentials for that user.

`/api/auth/me` closes the hole. A service forwards the `Authorization: Bearer <aegis_token>` header it received, and Aegis returns the authenticated user. Standard pattern, no shared secrets, no client-asserted identities.

## When to Use It

**Use `/me`** when a backend service receives a request from the frontend (or any other Aegis-authenticated client) and needs to know which user is making the request.

**Do not use `/me`** for:
- The frontend itself on the login page — use `/api/auth/login` and store the user info from the response.
- Polling / keep-alive checks — the token's `expires_at` is available client-side, no round-trip needed.

## Caching Guidance

- Cache `token → user` with a short TTL (default `30` seconds here) keyed by the token string.
- Do not cache the HTTP response object — Aegis already sends `Cache-Control: no-store` and HTTP proxies must honor that.
- Invalidate the cache entry on any 401 from `/me` (the token was revoked or expired between calls).

## Endpoint Contract

**Request:**
```
GET /api/auth/me
Authorization: Bearer <aegis_auth_token>
```

**Response 200 — standard Aegis user shape:**
```json
{
  "id": 42,
  "site_id": 1,
  "email": "user@example.com",
  "is_verified": true,
  "role": "user",
  "created_at": 1745280000,
  "updated_at": 1745280000
}
```

**Response 401 — any auth failure:**
```json
{ "error": "<message>" }
```

Aegis returns 401 for every failure mode (missing header, malformed header, unknown token, expired token) with **no distinction between them**. This is intentional to avoid leaking which kind of failure occurred. Your middleware should treat all 401s as "not authenticated" without trying to parse the message.

---

## Next.js API Route Helper (TypeScript)

For backends that are Next.js API routes (either in the same project as the frontend or a separate Next.js service).

**Requires:** `byteforge-aegis-client-js@2.8.0` or newer.

**File:** `lib/aegisAuth.ts`

```typescript
import { AuthClient } from 'byteforge-aegis-client-js';
import type { NextRequest } from 'next/server';

const AEGIS_API_URL = process.env.AEGIS_API_URL || '{aegis_api_url}';
const CACHE_TTL_MS = 30_000;

export interface AegisUser {
  id: number;
  site_id: number;
  email: string;
  is_verified: boolean;
  role: string;
  created_at: number;
  updated_at: number;
}

interface CacheEntry {
  user: AegisUser;
  expiresAt: number;
}

const tokenCache = new Map<string, CacheEntry>();

function extractBearerToken(request: NextRequest): string | null {
  const header = request.headers.get('authorization');
  if (!header || !header.startsWith('Bearer ')) {
    return null;
  }
  return header.slice(7);
}

async function resolveUser(token: string): Promise<AegisUser | null> {
  const cached = tokenCache.get(token);
  if (cached && cached.expiresAt > Date.now()) {
    return cached.user;
  }

  const client = new AuthClient({ apiUrl: AEGIS_API_URL, autoRefresh: false });
  client.setAuthToken(token);
  const result = await client.me();

  if (!result.success) {
    tokenCache.delete(token);
    return null;
  }

  tokenCache.set(token, { user: result.data, expiresAt: Date.now() + CACHE_TTL_MS });
  return result.data;
}

export async function authenticateRequest(request: NextRequest): Promise<AegisUser | null> {
  const token = extractBearerToken(request);
  if (!token) {
    return null;
  }
  return resolveUser(token);
}
```

**Usage in a route handler:**

```typescript
// app/api/protected/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { authenticateRequest } from '@/lib/aegisAuth';

export async function GET(request: NextRequest): Promise<NextResponse> {
  const user = await authenticateRequest(request);
  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  return NextResponse.json({ message: `Hello ${user.email}`, user_id: user.id });
}
```

**Notes:**
- The in-process `Map` cache is per-server-instance. In a multi-replica deployment each replica hits `/me` independently on first request for a token — acceptable given the 30-second TTL and the low cost of `/me`. Swap to Redis if you need cross-replica sharing.
- `AEGIS_API_URL` is a **server-side** env var here, distinct from the client-side `NEXT_PUBLIC_AEGIS_API_URL`. They can have the same value, but the server one does not need to be public.

---

## Flask Decorator (Python)

For sibling Flask backends that receive Aegis-authenticated requests from the frontend.

**Requires:** `byteforge-aegis-client-python@1.2.0` or newer.

**File:** `app/decorators/aegis_auth.py`

```python
import os
import time
from functools import wraps
from typing import Callable

from flask import g, jsonify, request
from byteforge_aegis_client import AegisClient, AegisUnauthorized

AEGIS_API_URL = os.environ.get('AEGIS_API_URL', '{aegis_api_url}')
CACHE_TTL_SECONDS = 30

_token_cache: dict[str, tuple[dict, float]] = {}


def _extract_bearer_token() -> str | None:
    header = request.headers.get('Authorization', '')
    if not header.startswith('Bearer '):
        return None
    return header[7:]


def _resolve_user(token: str) -> dict | None:
    cached = _token_cache.get(token)
    if cached is not None and cached[1] > time.time():
        return cached[0]

    client = AegisClient(api_url=AEGIS_API_URL)
    client.set_auth_token(token)
    try:
        user = client.me()
    except AegisUnauthorized:
        _token_cache.pop(token, None)
        return None

    _token_cache[token] = (user, time.time() + CACHE_TTL_SECONDS)
    return user


def aegis_auth_required(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        token = _extract_bearer_token()
        if token is None:
            return jsonify({'error': 'Unauthorized'}), 401

        user = _resolve_user(token)
        if user is None:
            return jsonify({'error': 'Unauthorized'}), 401

        g.current_user = user
        return func(*args, **kwargs)

    return wrapper
```

**Usage on a flask-smorest view:**

```python
from flask import g
from flask.views import MethodView
from flask_smorest import Blueprint

from app.decorators.aegis_auth import aegis_auth_required

bp = Blueprint('protected', __name__, url_prefix='/api/protected')


@bp.route('/')
class ProtectedView(MethodView):
    @aegis_auth_required
    def get(self):
        user = g.current_user
        return {'message': f'Hello {user["email"]}', 'user_id': user['id']}
```

**Notes:**
- `g.current_user` is the dict Aegis returned. It has the standard user shape (`id`, `site_id`, `email`, `is_verified`, `role`, `created_at`, `updated_at`).
- `AegisUnauthorized` is a subclass of `AegisApiError`, so existing broad `except AegisApiError` handlers still catch it.
- The module-level `_token_cache` is per-worker. Under gunicorn with N workers you get N independent caches — fine for the 30-second TTL.

---

## Placeholder Replacement Guide

| Placeholder | Description | Example |
|-------------|-------------|---------|
| `{aegis_api_url}` | Full URL to the Aegis backend API | `https://aegis.reallybadapps.com` |

---

## Version Compatibility

| Component | Minimum Version |
|-----------|----------------|
| Aegis backend (`byteforge-aegis`) | Image version 39 (commit `c96b412` or later) |
| TypeScript client (`byteforge-aegis-client-js`) | `2.8.0` |
| Python client (`byteforge-aegis-client-python`) | `1.2.0` |

If the backend is older than image version 39, `/api/auth/me` returns 404 — upgrade Aegis before rolling out middleware based on this pattern.

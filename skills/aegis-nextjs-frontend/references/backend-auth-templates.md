# Backend Aegis Identity Resolution

Use the UUID-capable Aegis backend with JS client **4.2.0** or Python client
**3.3.0** (models **2.8.0**). These are the tested contracts, not the historical
versions that first introduced each endpoint. Site and user identifiers are UUID
strings. The request/config names `site_id`, `siteId`, and `user_id` still exist
in the SDK; their **values are strings**, never integers.

| Credential | Aegis call | Purpose |
|---|---|---|
| User bearer token | `GET /api/auth/me` | Authenticate the caller |
| Already validated local API key mapped to an Aegis user UUID | `GET /api/sites/{site_id}/users/{user_id}` with tenant key | Fetch current user/role |

A user UUID supplied by the caller is not proof of identity. Resolve it from a
credential your backend has validated before using the second endpoint.

The user response includes `uuid`, `site_uuid`, `email`, `is_verified`, `role`,
`created_at`, `updated_at`, and `deletion_protected`. Python returns a **User
model**, accessed as `user.uuid` and `user.email`; JS returns the typed User in
`result.data`. Both helpers below reject users outside the configured site.

## Configuration

In the **backend repository**, set:

```dotenv
AEGIS_API_URL={aegis_api_url}
AEGIS_SITE_ID={aegis_site_uuid}
# Required only for user lookup / public-auth proxy routes, not bearer /me:
AEGIS_TENANT_API_KEY=
```

Substitute the actual deployment URL and site UUID. There is no default host or
optional tenant check. Missing/invalid config must fail closed. Validate these
values during application startup; Next.js helpers also check at request time
so image builds do not need runtime secrets.

## Next.js helper: lib/aegisAuth.ts

```typescript
import 'server-only';
import { createHash } from 'node:crypto';
import { AuthClient, type User } from 'byteforge-aegis-client-js';
import type { NextRequest } from 'next/server';

export class AegisUnavailable extends Error {}
const UUID = /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i;
const cache = new Map<string, { user: User | null; expiresAt: number }>();

function configuration() {
  const apiUrl = process.env.AEGIS_API_URL?.trim();
  const siteId = process.env.AEGIS_SITE_ID?.trim().toLowerCase();
  if (!apiUrl || !siteId || !UUID.test(siteId)) {
    throw new AegisUnavailable('Aegis URL and site UUID are required');
  }
  return { apiUrl, siteId };
}

async function resolve(tokenOrUserUuid: string, lookup: boolean): Promise<User | null> {
  const config = configuration();
  const tenantApiKey = lookup ? process.env.AEGIS_TENANT_API_KEY : undefined;
  if (lookup && !tenantApiKey) throw new AegisUnavailable('Tenant key required');
  if (lookup && !UUID.test(tokenOrUserUuid)) return null;
  const key = `${config.apiUrl}:${config.siteId}:${lookup}:` +
    createHash('sha256').update(tokenOrUserUuid).digest('hex');
  const cached = cache.get(key);
  if (cached && cached.expiresAt > Date.now()) return cached.user;
  cache.delete(key);

  const client = new AuthClient({ ...config, tenantApiKey, autoRefresh: false });
  if (!lookup) client.setAuthToken(tokenOrUserUuid);
  const result = lookup ? await client.getUser(tokenOrUserUuid) : await client.me();
  let user: User | null = null;
  if (!result.success) {
    const status = result.statusCode ?? 0;
    if (!(status >= 400 && status < 500 && status !== 429)) {
      throw new AegisUnavailable('Authentication service unavailable');
    }
  } else if (result.data.site_uuid.toLowerCase() === config.siteId &&
             (!lookup || result.data.uuid.toLowerCase() === tokenOrUserUuid.toLowerCase())) {
    user = result.data;
  }
  // Bound both accepted and rejected entries, never cache outages.
  if (cache.size >= 5000) cache.clear();
  cache.set(key, { user, expiresAt: Date.now() + (user ? 30_000 : 10_000) });
  return user;
}

export async function authenticateRequest(request: NextRequest): Promise<User | null> {
  const header = request.headers.get('authorization') ?? '';
  const token = header.startsWith('Bearer ') ? header.slice(7).trim() : '';
  return token ? resolve(token, false) : null;
}

export async function getAegisUser(userUuid: string): Promise<User | null> {
  return resolve(userUuid, true);
}
```

### Route usage

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { AegisUnavailable, authenticateRequest } from '@/lib/aegisAuth';

export async function GET(request: NextRequest) {
  try {
    const user = await authenticateRequest(request);
    if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    // If this service mirrors users, consult the durable deletion tombstone
    // here even for a cached user, before provisioning or authorizing locally.
    return NextResponse.json({ user_uuid: user.uuid });
  } catch (error) {
    if (error instanceof AegisUnavailable) {
      return NextResponse.json({ error: 'Authentication service unavailable' }, { status: 503 });
    }
    throw error;
  }
}
```

For API-key authorization, first validate the local key, then pass its stored
user UUID to `getAegisUser`. Return 401 for an unknown identity, 403 for an
insufficient `user.role`, and 503 for `AegisUnavailable`. Never expose a
user-lookup proxy that accepts arbitrary browser-supplied user UUIDs.

## Flask: app/decorators/aegis_auth.py

```python
import hashlib
import os
import threading
import time
from functools import wraps
from uuid import UUID

from flask import g, jsonify, request
from byteforge_aegis_client import AegisApiError, AegisClient, AegisClientConfig, AegisError
from byteforge_aegis_models import User


class AegisTokenResolver:
    def __init__(self, api_url: str, site_id: str):
        if not api_url.strip():
            raise ValueError('AEGIS_API_URL is required')
        self.api_url = api_url.strip()
        self.site_id = str(UUID(site_id.strip()))  # Reject missing/integer IDs.
        self.cache: dict[str, tuple[User | None, float]] = {}
        self.lock = threading.Lock()

    def __call__(self, token: str) -> User | None:
        key = hashlib.sha256(token.encode()).hexdigest()
        with self.lock:
            cached = self.cache.get(key)
            if cached and cached[1] > time.monotonic():
                return cached[0]
            self.cache.pop(key, None)
        client = AegisClient(AegisClientConfig(
            api_url=self.api_url, site_id=self.site_id, auto_refresh=False,
        ))
        client.set_auth_token(token)
        try:
            user = client.me()
        except AegisApiError as error:
            if not (400 <= error.status_code < 500 and error.status_code != 429):
                raise  # 429/5xx: unavailable, not an invalid token.
            user = None  # Includes AegisUnauthorized (401) and other 4xx.
        if user is not None and str(user.site_uuid).lower() != self.site_id:
            user = None
        with self.lock:
            if len(self.cache) >= 5000:
                self.cache.clear()
            self.cache[key] = (user, time.monotonic() + (30 if user else 10))
        return user


# Import this module after dotenv/config initialization in the app factory.
# Required config fails at startup instead of accepting every Aegis tenant.
resolve_token = AegisTokenResolver(os.environ['AEGIS_API_URL'], os.environ['AEGIS_SITE_ID'])


def aegis_auth_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        header = request.headers.get('Authorization', '')
        token = header[7:].strip() if header.startswith('Bearer ') else ''
        if not token:
            return jsonify({'error': 'Unauthorized'}), 401
        try:
            user = resolve_token(token)
        except AegisError:
            return jsonify({'error': 'Authentication service unavailable'}), 503
        if user is None:
            return jsonify({'error': 'Unauthorized'}), 401
        # For local mirrored accounts, check durable deletion state here on
        # EVERY request, including cache hits; see webhook-templates.md.
        g.current_user = user
        return func(*args, **kwargs)
    return wrapper
```

Use `g.current_user.uuid`, `.email`, `.site_uuid`, and `.role` in views. The SDK
role may be an enum: compare `getattr(user.role, 'value', user.role)` to `'admin'`.
Each worker has a bounded cache; accepted identity/role changes may lag up to 30
seconds. Rejections are cached for 10 seconds. A negative cache helps repeated
bad tokens; it is not a substitute for rate limiting distinct-token sprays.

### User lookup for a validated local API key

```python
import os
from uuid import UUID
from byteforge_aegis_client import AegisApiError, AegisClient, AegisClientConfig


def get_aegis_user(user_uuid: str):
    site_id = str(UUID(os.environ['AEGIS_SITE_ID'].strip()))
    user_uuid = str(UUID(user_uuid))
    client = AegisClient(AegisClientConfig(
        api_url=os.environ['AEGIS_API_URL'], site_id=site_id,
        tenant_api_key=os.environ['AEGIS_TENANT_API_KEY'], auto_refresh=False,
    ))
    try:
        user = client.get_user(user_id=user_uuid)
    except AegisApiError as error:
        if 400 <= error.status_code < 500 and error.status_code != 429:
            return None
        raise
    if str(user.site_uuid).lower() != site_id or str(user.uuid).lower() != user_uuid:
        return None
    return user
```

The caller must catch `AegisError` and return 503, consult any local deletion
state, and authorize the requested operation using the returned role. Do not
share a mutable authenticated client across users or retain bearer tokens in
logs. Backend authorization remains required even when the UI hides a page.

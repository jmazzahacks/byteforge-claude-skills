# Tenant API Key Templates (Public Auth Endpoints)

This file documents the **required** backend-proxy pattern for Aegis's gated public auth endpoints. After backend image v40+, six Aegis endpoints require an `X-Tenant-Api-Key` header on every request:

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/request-password-reset`
- `POST /api/auth/reset-password`
- `POST /api/auth/verify-email`
- `POST /api/auth/check-verification-token`

> **Related — same key, different use case:** `GET /api/sites/{site_id}/users/{user_id}` is also tenant-key-gated, but it's a **server-to-server** lookup for backend authz (resolve a `user_id` to its current `role`). It is not proxied to the browser. See `backend-auth-templates.md` for that pattern.

The header is a per-tenant secret (64-char hex) issued by the Aegis admin dashboard. **It must live server-side in your Next.js deployment**, never in browser-shipped code, because the whole point of the gate is to prevent direct-to-Aegis abuse from automated callers. Browsers are public — anything in browser JS is publishable.

This means the scaffolded Next.js app must:

1. Hold `AEGIS_TENANT_API_KEY` in a server-only env var.
2. Expose `/api/frontend/auth/*` proxy routes that forward to Aegis with the header attached.
3. Have its `browserClient` call the local proxy routes instead of Aegis directly.

---

## CRITICAL — Substitution Notes

- Replace `{aegis_api_url}` with the tenant's Aegis backend URL (e.g., `https://aegis.example.com`).
- The tenant API key is per-site; each scaffolded app gets its own.
- `AEGIS_API_URL` (server-side) and `NEXT_PUBLIC_AEGIS_API_URL` (browser-side, used only for the *unprotected* `getSiteByDomain` lookup) can have the same value but the server-side one does not need to be public.

---

## 1. Environment Variables

Add to `.env.example` (server-side only, no `NEXT_PUBLIC_` prefix):

```
# Aegis backend URL (server-side only, used by proxy routes)
AEGIS_API_URL={aegis_api_url}

# Per-tenant secret for X-Tenant-Api-Key header on public auth endpoints.
# Get this from the Aegis admin dashboard. Never expose in browser code.
AEGIS_TENANT_API_KEY=

# Your site UUID string from Aegis (server-side, used by proxy routes for verify-email/etc.)
AEGIS_SITE_ID={aegis_site_uuid}
```

`NEXT_PUBLIC_AEGIS_API_URL` and `NEXT_PUBLIC_SITE_DOMAIN` from the original config still apply (browser uses them for the public `getSiteByDomain` bootstrap; that endpoint is not gated).

---

## 2. Server-Side Aegis Client Helper

**File:** `lib/serverAuthClient.ts`

```typescript
import 'server-only';
import { AuthClient } from 'byteforge-aegis-client-js';

// Read lazily: runtime secrets are deliberately absent during next build.
export function getServerAuthClient(): AuthClient {
  const apiUrl = process.env.AEGIS_API_URL?.trim();
  const tenantApiKey = process.env.AEGIS_TENANT_API_KEY?.trim();
  const siteId = process.env.AEGIS_SITE_ID?.trim();
  if (!apiUrl || !tenantApiKey || !siteId ||
      !/^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(siteId)) {
    throw new Error('Configure AEGIS_API_URL, AEGIS_TENANT_API_KEY, and AEGIS_SITE_ID (UUID)');
  }
  // A fresh client prevents mutable login tokens leaking between requests.
  return new AuthClient({ apiUrl, siteId, tenantApiKey, autoRefresh: false });
}
```

---

## 3. Proxy Route Templates

All six routes follow the same pattern: parse body, call the server-side AuthClient, return result. The AuthClient handles the `X-Tenant-Api-Key` header injection automatically.

**Requires:** `byteforge-aegis-client-js@4.2.0` or newer.

### `app/api/frontend/auth/register/route.ts`

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { getServerAuthClient } from '@/lib/serverAuthClient';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email, password } = body;

    if (!email) {
      return NextResponse.json({ error: 'email is required' }, { status: 400 });
    }

    const client = getServerAuthClient();
    const result = await client.register(email, password);

    if (result.success) {
      return NextResponse.json(result.data, { status: 201 });
    }
    return NextResponse.json(
      { error: result.error },
      { status: result.statusCode || 400 },
    );
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal error' },
      { status: 500 },
    );
  }
}
```

### `app/api/frontend/auth/login/route.ts`

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { getServerAuthClient } from '@/lib/serverAuthClient';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email, password } = body;

    if (!email || !password) {
      return NextResponse.json(
        { error: 'email and password are required' },
        { status: 400 },
      );
    }

    const client = getServerAuthClient();
    const result = await client.login(email, password);

    if (result.success) {
      return NextResponse.json(result.data);
    }
    return NextResponse.json(
      { error: result.error },
      { status: result.statusCode || 401 },
    );
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal error' },
      { status: 500 },
    );
  }
}
```

### `app/api/frontend/auth/request-password-reset/route.ts`

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { getServerAuthClient } from '@/lib/serverAuthClient';

export async function POST(request: NextRequest) {
  try {
    const { email } = await request.json();
    if (!email) {
      return NextResponse.json({ error: 'email is required' }, { status: 400 });
    }

    const client = getServerAuthClient();
    const result = await client.requestPasswordReset(email);

    if (result.success) {
      return NextResponse.json(result.data);
    }
    return NextResponse.json(
      { error: result.error },
      { status: result.statusCode || 400 },
    );
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal error' },
      { status: 500 },
    );
  }
}
```

### `app/api/frontend/auth/reset-password/route.ts`

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { getServerAuthClient } from '@/lib/serverAuthClient';

export async function POST(request: NextRequest) {
  try {
    const { token, new_password } = await request.json();
    if (!token || !new_password) {
      return NextResponse.json(
        { error: 'token and new_password are required' },
        { status: 400 },
      );
    }

    const client = getServerAuthClient();
    const result = await client.resetPassword(token, new_password);

    if (result.success) {
      return NextResponse.json(result.data);
    }
    return NextResponse.json(
      { error: result.error },
      { status: result.statusCode || 400 },
    );
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal error' },
      { status: 500 },
    );
  }
}
```

### `app/api/frontend/auth/verify-email/route.ts`

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { getServerAuthClient } from '@/lib/serverAuthClient';

export async function POST(request: NextRequest) {
  try {
    const { token, password } = await request.json();
    if (!token) {
      return NextResponse.json({ error: 'token is required' }, { status: 400 });
    }

    const client = getServerAuthClient();
    const result = await client.verifyEmail(token, password);

    if (result.success) {
      return NextResponse.json(result.data);
    }
    return NextResponse.json(
      { error: result.error },
      { status: result.statusCode || 400 },
    );
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal error' },
      { status: 500 },
    );
  }
}
```

### `app/api/frontend/auth/check-verification-token/route.ts`

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { getServerAuthClient } from '@/lib/serverAuthClient';

export async function POST(request: NextRequest) {
  try {
    const { token } = await request.json();
    if (!token) {
      return NextResponse.json({ error: 'token is required' }, { status: 400 });
    }

    const client = getServerAuthClient();
    const result = await client.checkVerificationToken(token);

    if (result.success) {
      return NextResponse.json(result.data);
    }
    return NextResponse.json(
      { error: result.error },
      { status: result.statusCode || 400 },
    );
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal error' },
      { status: 500 },
    );
  }
}
```

---

## 4. Browser Client Pattern

Use `lib/browserClient.ts` from `auth-templates.md`; it already contains the
complete typed `browserAuthProxy` shim. Do not generate a second copy here.
Auth pages call that shim for the six gated operations and initialize the
singleton from the returned login tokens. The refresh/session-generation guard
must remain in place when adapting either proxy variant.

---

## 4b. Alternative: Proxy Lives in a Sibling Backend (No Next.js API Routes)

If the project **already has a separate backend** (Flask, FastAPI, Express, etc.) that the frontend calls for non-auth business logic, host the 6 proxy endpoints there instead of in Next.js API routes. This avoids duplicating an API surface across two services. Reference implementation: `hivemake.ai` (Flask `hivemake-server` at `api.hivemake.ai`).

### When to use this variant

- The tenant has a backend that's already calling Aegis for other reasons (e.g., validating bearer tokens via `/api/auth/me`, see `backend-auth-templates.md`).
- The frontend already targets that backend for everything else; adding 6 thin proxy routes is cheaper than introducing a Next.js API layer.
- The backend can hold `AEGIS_TENANT_API_KEY` in its own env and inject it via `byteforge-aegis-client-python` or `byteforge-aegis-client-js`.

### Architecture differences

| | Skill default (Next.js routes) | Sibling-backend variant |
|---|---|---|
| Proxy host | `app/api/frontend/auth/*` in this Next.js | `/api/auth/*` in the sibling backend (e.g., `api.example.com`) |
| Tenant key holder | This Next.js's server-side env | The sibling backend's env |
| Frontend client | `browserAuthProxy` fetch shim → `/api/frontend/auth/*` | A second `AuthClient` configured with `apiUrl = <backend_url>` |
| `siteId` exposure | `AEGIS_SITE_ID` server-side | Either same, or baked as `NEXT_PUBLIC_AEGIS_SITE_ID` (site_id alone is not a secret — see note below) |

### Pattern: two AuthClients in the browser

The sibling-backend variant is cleaner because the second `AuthClient` reuses the typed Aegis interface — no fetch shim needed. The sibling backend's proxy routes mirror Aegis's API surface (`/api/auth/login` → forwards to Aegis's `/api/auth/login`).

```typescript
// lib/browserClient.ts — sibling-backend variant
import { AuthClient } from 'byteforge-aegis-client-js';

const AEGIS_API_URL = process.env.NEXT_PUBLIC_AEGIS_API_URL!;
const BACKEND_API_URL = process.env.NEXT_PUBLIC_BACKEND_API_URL!; // e.g. https://api.example.com
const SITE_ID = process.env.NEXT_PUBLIC_AEGIS_SITE_ID!;

let aegisSingleton: AuthClient | null = null;
let proxySingleton: AuthClient | null = null;

// Used for Bearer-gated calls (refresh, me, logout, confirm-email-change).
export function getAuthClient(): AuthClient {
  if (aegisSingleton) return aegisSingleton;
  aegisSingleton = new AuthClient({ apiUrl: AEGIS_API_URL, siteId: SITE_ID, autoRefresh: false });
  // ...hydrate tokens from localStorage...
  return aegisSingleton;
}

// Used for the 6 tenant-key-gated calls. Backend attaches the tenant key.
export function getProxyClient(): AuthClient {
  if (proxySingleton) return proxySingleton;
  proxySingleton = new AuthClient({ apiUrl: BACKEND_API_URL, siteId: SITE_ID, autoRefresh: false });
  return proxySingleton;
}
```

Auth pages call `getProxyClient().login(email, password)` etc. for the gated endpoints, and `getAuthClient().refreshAuthToken()` etc. for Bearer-gated ones. No `browserAuthProxy` shim, no `app/api/frontend/auth/*` routes.

### Flask client: lib/aegis.py

Read required runtime config after dotenv initialization. The UUID and key are
owned by the server; ignore any browser-supplied site_id. Use a fresh client per
request because login mutates the SDK's token state.

```python
import os
from uuid import UUID
from byteforge_aegis_client import AegisClient, AegisClientConfig


def aegis_tenant_client() -> AegisClient:
    api_url = os.environ['AEGIS_API_URL'].strip()
    site_id = str(UUID(os.environ['AEGIS_SITE_ID'].strip()))
    key = os.environ['AEGIS_TENANT_API_KEY'].strip()
    if not api_url or not key:
        raise ValueError('Aegis URL and tenant key are required')
    return AegisClient(AegisClientConfig(
        api_url=api_url, site_id=site_id, tenant_api_key=key, auto_refresh=False,
    ))
```

### Flask routes: blueprints/auth.py

Register this blueprint in the app factory. The fixed operation map covers all
six endpoints and drops unknown input fields, including client-supplied site_id.
For a cross-origin sibling backend, configure its CORS layer to allow the actual
frontend origin and OPTIONS/POST with Content-Type; do not put the tenant key in
browser requests. Apply the backend's usual public-auth rate limiting.

```python
from dataclasses import asdict
from flask import Blueprint, jsonify, request
from byteforge_aegis_client import AegisApiError, AegisError
from lib.aegis import aegis_tenant_client

blp = Blueprint('auth', __name__, url_prefix='/api/auth')
OPERATIONS = {
    'register': ('register', ('email',), ('password',)),
    'login': ('login', ('email', 'password'), ()),
    'request-password-reset': ('request_password_reset', ('email',), ()),
    'reset-password': ('reset_password', ('token', 'new_password'), ()),
    'verify-email': ('verify_email', ('token',), ('password',)),
    'check-verification-token': ('check_verification_token', ('token',), ()),
}


@blp.post('/<operation>')
def proxy_auth(operation):
    spec = OPERATIONS.get(operation)
    if spec is None:
        return jsonify({'error': 'Unknown auth operation'}), 404
    method, required, optional = spec
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({'error': 'Expected a JSON object'}), 400
    if any(not isinstance(body.get(key), str) or not body[key] for key in required):
        return jsonify({'error': 'Missing or invalid required fields'}), 400
    if any(body.get(key) is not None and not isinstance(body[key], str) for key in optional):
        return jsonify({'error': 'Invalid optional field'}), 400
    fields = {key: body[key] for key in required}
    fields.update({key: body[key] for key in optional if body.get(key) is not None})
    try:
        client = aegis_tenant_client()
        result = getattr(client, method)(**fields)
    except AegisApiError as error:
        status = error.status_code if 400 <= error.status_code < 500 else 503
        return jsonify({'error': 'Authentication request rejected' if status < 500 else
                        'Authentication service unavailable'}), status
    except (AegisError, KeyError, ValueError):
        return jsonify({'error': 'Authentication service unavailable'}), 503
    return jsonify(asdict(result)), 201 if operation == 'register' else 200
```

The tested client baseline is JS 4.2.0 / Python 3.3.0. Mirror JSON errors, including
401 and 429; do not let SDK exceptions turn invalid credentials into HTML 500s.

### Sibling frontend deployment

Export `AUTH_PROXY_MODE=sibling`, `NEXT_PUBLIC_BACKEND_API_URL`, and
`NEXT_PUBLIC_AEGIS_SITE_ID` when running build-publish.sh. The Dockerfile has
matching ARG/ENV declarations. They are public build-time values, alongside the
Aegis URL and site domain; runtime Compose env alone cannot populate browser JS.
Omit Next.js proxy routes and their runtime tenant key when using this variant.
Configure AEGIS_API_URL, AEGIS_SITE_ID, and AEGIS_TENANT_API_KEY on Flask instead.

### Gotcha: the JS AuthClient always sends `site_id` in the body

`byteforge-aegis-client-js` always includes `site_id` in the JSON body for `register`, `login`, `request_password_reset`, `reset_password`, `verify_email`, and `check_verification_token` (it pulls `siteId` from `AuthClientConfig` and adds it to the request payload). Your proxy doesn't *need* the value — the sibling backend uses its env-configured `site_id` via the tenant client — but a strict-validation framework will **reject the call with 422 "Unknown field"** if your input schema doesn't tolerate the extra field.

This bites:
- **flask-smorest / marshmallow** — default is to raise on unknown fields
- **FastAPI / pydantic** — when models are configured with `extra="forbid"`
- **Express + AJV / zod / yup** — when `additionalProperties: false` / `.strict()` is set

**Fix on the proxy side: silently drop unknown fields.**

Marshmallow:

```python
from marshmallow import EXCLUDE, Schema, fields

class _ProxyRequestSchema(Schema):
    class Meta:
        unknown = EXCLUDE  # JS client sends site_id; we ignore it.

class LoginRequestSchema(_ProxyRequestSchema):
    email = fields.Email(required=True)
    password = fields.String(required=True)
```

Pydantic:

```python
class LoginRequest(BaseModel):
    model_config = ConfigDict(extra='ignore')  # default in v2 anyway
    email: EmailStr
    password: str
```

zod / yup: use `.strip()` / non-strict mode (the default for both).

Symptom in the wild: the form-submit flow looks "stuck" — the AuthClient sees `response.ok === false` from a 422 and surfaces the marshmallow `Unknown field` error as a generic `Unknown error` to the React component, so the spinner clears with an unhelpful message. A direct `curl` probe (which doesn't include `site_id`) returns the expected 401 from Aegis, masking the real bug.

### Note on `NEXT_PUBLIC_AEGIS_SITE_ID`

Hivemake bakes `AEGIS_SITE_ID` into the client bundle as `NEXT_PUBLIC_AEGIS_SITE_ID` so the browser can construct the request body. This is **safe** — site_id alone gives a caller no auth power; the gate is the tenant key, which stays server-side. If the frontend already does `getSiteByDomain(NEXT_PUBLIC_SITE_DOMAIN)` to resolve the id at runtime, you don't need this var at all.

---

## 5. Migration Notes for Existing Scaffolds

If updating an existing scaffold from the old direct-to-Aegis pattern:

1. **Add env vars:** `AEGIS_API_URL`, `AEGIS_TENANT_API_KEY`, `AEGIS_SITE_ID` (server-side).
2. **Bump dependency:** `byteforge-aegis-client-js` to `>=4.2.0`.
3. **Add server helper:** `lib/serverAuthClient.ts` (above).
4. **Add 6 proxy routes** under `app/api/frontend/auth/*` *(or in your sibling backend — see section 4b)*.
5. **If using a sibling backend with strict input validation** (flask-smorest, FastAPI w/ `extra="forbid"`, AJV/zod with `additionalProperties: false`), make the proxy schemas tolerate unknown fields — the JS client always sends `site_id` in the body and a strict schema will 422 on it. See "Gotcha" in section 4b.
6. **Update auth pages** to call the proxy routes (via `browserAuthProxy` or equivalent) instead of `getAuthClient().login(...)` etc.
7. **Get the tenant key** from the Aegis admin dashboard (Site → Settings → Tenant API Key).
8. **Redeploy** with the env var set. The frontend will fail with 401 on every register/login/etc. call until the env var is in place.

---

## Why This Design

- **Server-side secret holding** — Browsers can't be trusted with credentials. The proxy is the only architecture where the secret can be reliably hidden.
- **Per-tenant key (not shared)** — Compromise of one tenant's key doesn't compromise others. Rotation is per-site via the admin dashboard.
- **Header-based, not body-based** — Easier to log/inspect/strip at gateways. Matches `MASTER_API_KEY` and `Authorization` patterns already in Aegis.
- **AuthClient handles header injection** — `byteforge-aegis-client-js@4.2.0+` reads `tenantApiKey` from `AuthClientConfig` and attaches `X-Tenant-Api-Key` automatically. No manual header management in proxy routes.

---

## Version Compatibility

| Component | Minimum Version |
|-----------|----------------|
| Aegis backend (`byteforge-aegis`) | UUID-capable backend with tenant-key gate |
| TypeScript client (`byteforge-aegis-client-js`) | `4.2.0` |
| Python client (`byteforge-aegis-client-python`) | `3.3.0` |

# Tenant API Key Templates (Public Auth Endpoints)

This file documents the **required** backend-proxy pattern for Aegis's gated public auth endpoints. After backend image v40+, six Aegis endpoints require an `X-Tenant-Api-Key` header on every request:

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/request-password-reset`
- `POST /api/auth/reset-password`
- `POST /api/auth/verify-email`
- `POST /api/auth/check-verification-token`

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
AEGIS_TENANT_API_KEY={paste_from_aegis_admin_dashboard}

# Your site_id from Aegis (server-side, used by proxy routes for verify-email/etc.)
AEGIS_SITE_ID={your_site_id}
```

`NEXT_PUBLIC_AEGIS_API_URL` and `NEXT_PUBLIC_SITE_DOMAIN` from the original config still apply (browser uses them for the public `getSiteByDomain` bootstrap; that endpoint is not gated).

---

## 2. Server-Side Aegis Client Helper

**File:** `lib/serverAuthClient.ts`

```typescript
import { AuthClient } from 'byteforge-aegis-client-js';

const AEGIS_API_URL = process.env.AEGIS_API_URL!;
const AEGIS_TENANT_API_KEY = process.env.AEGIS_TENANT_API_KEY!;
const AEGIS_SITE_ID = parseInt(process.env.AEGIS_SITE_ID!, 10);

/**
 * Server-side Aegis client preconfigured with the tenant API key and site ID.
 * The client auto-attaches X-Tenant-Api-Key on every request and includes
 * site_id in bodies that need it.
 */
export function getServerAuthClient(): AuthClient {
  return new AuthClient({
    apiUrl: AEGIS_API_URL,
    siteId: AEGIS_SITE_ID,
    tenantApiKey: AEGIS_TENANT_API_KEY,
    autoRefresh: false,
  });
}
```

---

## 3. Proxy Route Templates

All six routes follow the same pattern: parse body, call the server-side AuthClient, return result. The AuthClient handles the `X-Tenant-Api-Key` header injection automatically.

**Requires:** `byteforge-aegis-client-js@2.9.0` or newer.

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

## 4. Updated Browser Client Pattern

The browser-side `browserClient.ts` should call the local proxy routes for the six gated endpoints, **not Aegis directly**. The original singleton `AuthClient` pattern from `auth-templates.md` still works for unprotected endpoints (`getSiteByDomain`, `me`, `change-password`, `logout`, `refresh`).

**Recommended split:**

```typescript
// lib/browserClient.ts (new — proxies through backend)
async function postProxy<T>(path: string, body: unknown): Promise<{ success: true; data: T } | { success: false; error: string; statusCode: number }> {
  try {
    const response = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await response.json();
    if (response.ok) {
      return { success: true, data: data as T };
    }
    return { success: false, error: data.error || 'Unknown error', statusCode: response.status };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : 'Network error', statusCode: 0 };
  }
}

export const browserAuthProxy = {
  register: (email: string, password?: string) =>
    postProxy('/api/frontend/auth/register', { email, password }),
  login: (email: string, password: string) =>
    postProxy('/api/frontend/auth/login', { email, password }),
  requestPasswordReset: (email: string) =>
    postProxy('/api/frontend/auth/request-password-reset', { email }),
  resetPassword: (token: string, newPassword: string) =>
    postProxy('/api/frontend/auth/reset-password', { token, new_password: newPassword }),
  verifyEmail: (token: string, password?: string) =>
    postProxy('/api/frontend/auth/verify-email', { token, password }),
  checkVerificationToken: (token: string) =>
    postProxy('/api/frontend/auth/check-verification-token', { token }),
};
```

Auth pages (`login/page.tsx`, `verify-email/page.tsx`, etc.) call `browserAuthProxy.*` instead of the singleton `AuthClient` for these six methods. The login page still uses the singleton's `setTokensFromLoginResponse` after the proxy returns the login response, so token storage works the same way.

---

## 5. Migration Notes for Existing Scaffolds

If updating an existing scaffold from the old direct-to-Aegis pattern:

1. **Add env vars:** `AEGIS_API_URL`, `AEGIS_TENANT_API_KEY`, `AEGIS_SITE_ID` (server-side).
2. **Bump dependency:** `byteforge-aegis-client-js` to `>=2.9.0`.
3. **Add server helper:** `lib/serverAuthClient.ts` (above).
4. **Add 6 proxy routes** under `app/api/frontend/auth/*`.
5. **Update auth pages** to call the proxy routes (via `browserAuthProxy` or equivalent) instead of `getAuthClient().login(...)` etc.
6. **Get the tenant key** from the Aegis admin dashboard (Site → Settings → Tenant API Key).
7. **Redeploy** with the env var set. The frontend will fail with 401 on every register/login/etc. call until the env var is in place.

---

## Why This Design

- **Server-side secret holding** — Browsers can't be trusted with credentials. The proxy is the only architecture where the secret can be reliably hidden.
- **Per-tenant key (not shared)** — Compromise of one tenant's key doesn't compromise others. Rotation is per-site via the admin dashboard.
- **Header-based, not body-based** — Easier to log/inspect/strip at gateways. Matches `MASTER_API_KEY` and `Authorization` patterns already in Aegis.
- **AuthClient handles header injection** — `byteforge-aegis-client-js@2.9.0+` reads `tenantApiKey` from `AuthClientConfig` and attaches `X-Tenant-Api-Key` automatically. No manual header management in proxy routes.

---

## Version Compatibility

| Component | Minimum Version |
|-----------|----------------|
| Aegis backend (`byteforge-aegis`) | image v40+ (with `tenant_api_key` migration applied) |
| TypeScript client (`byteforge-aegis-client-js`) | `2.9.0` |
| Python client (`byteforge-aegis-client-python`) | `1.3.0` |

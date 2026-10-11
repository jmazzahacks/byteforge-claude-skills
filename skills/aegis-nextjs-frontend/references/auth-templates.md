# Auth Utility Templates

## CRITICAL - Substitution Notes

- Replace `{aegis_api_url}` with the actual Aegis API URL for the target project (e.g., `https://aegis.example.com/api`)
- Replace `{site_domain}` with the actual site domain for the target project (e.g., `myapp.example.com`)
- The `useAuth.ts` file is identical across all projects; no substitution is needed
- The templates target `byteforge-aegis-client-js` 4.2.0 (UUID IDs); refresh is managed explicitly
- The legacy localStorage key names `user_id` and `site_id` store UUID strings. When migrating numeric-ID sessions, clear auth storage and log in again.
- localStorage keys used: `auth_token`, `refresh_token`, `token_expires_at`, `user_id`, `site_id`, `site_name`

## Token Refresh Architecture

The `browserClient.ts` uses a **singleton AuthClient** that persists tokens in memory and syncs to localStorage on refresh. This ensures:

- Tokens are refreshed proactively (5-minute buffer before expiry)
- The `useAuth` hook checks expiry on mount and every 60 seconds
- Failed refresh (expired refresh token, network error) triggers automatic logout
- Login page uses `initAuthClientFromLogin()` to set up the singleton after successful login
- `clearAuthClient()` is the single source of truth for clearing all auth state

## Browser-vs-Backend Call Split

After Aegis backend v40+, six public auth endpoints are gated by `X-Tenant-Api-Key`. Browser code cannot call these directly; the scaffold ships a `browserAuthProxy` shim that posts to local `/api/frontend/auth/*` proxy routes (see `tenant-api-key-templates.md`).

- **Use `browserAuthProxy.*`** for: `login`, `register`, `requestPasswordReset`, `resetPassword`, `verifyEmail`, `checkVerificationToken`.
- **Use `getAuthClient()`** for: `getSiteByDomain` (public bootstrap), `me`, `changePassword`, `logout`, `refreshAuthToken`, `confirmEmailChange` (Bearer-token gated, unchanged).

---

## lib/browserClient.ts

```typescript
/**
 * Browser-side auth client using byteforge-aegis-client-js directly.
 * Uses a singleton AuthClient that persists tokens in memory and syncs to localStorage.
 */

import { AuthClient } from 'byteforge-aegis-client-js';
import type { LoginResponse, RefreshTokenResponse, ApiResponse } from 'byteforge-aegis-client-js';

const AEGIS_API_URL = process.env.NEXT_PUBLIC_AEGIS_API_URL || '{aegis_api_url}';
const SITE_DOMAIN = process.env.NEXT_PUBLIC_SITE_DOMAIN || '{site_domain}';

let singleton: AuthClient | null = null;
let sessionGeneration = 0;

/**
 * Returns the singleton AuthClient, hydrating from localStorage on first call.
 */
export function getAuthClient(): AuthClient {
  if (singleton) {
    return singleton;
  }

  const siteIdStr = typeof window !== 'undefined' ? localStorage.getItem('site_id') : null;
  const siteId = siteIdStr || undefined;

  singleton = new AuthClient({
    apiUrl: AEGIS_API_URL,
    siteId,
    autoRefresh: false,
  });

  if (typeof window !== 'undefined') {
    const authToken = localStorage.getItem('auth_token');
    const refreshToken = localStorage.getItem('refresh_token');

    if (authToken) {
      singleton.setAuthToken(authToken);
    }
    if (refreshToken) {
      singleton.setRefreshToken(refreshToken);
    }
  }

  return singleton;
}

/**
 * Called after login succeeds. Sets tokens on the singleton and stores everything in localStorage.
 */
export function initAuthClientFromLogin(loginResponse: LoginResponse, siteId: string, siteName: string): void {
  sessionGeneration += 1;
  localStorage.setItem('auth_token', loginResponse.auth_token.token);
  localStorage.setItem('refresh_token', loginResponse.refresh_token.token);
  localStorage.setItem('token_expires_at', loginResponse.auth_token.expires_at.toString());
  localStorage.setItem('user_id', loginResponse.auth_token.user_uuid);
  localStorage.setItem('site_id', siteId.toString());
  localStorage.setItem('site_name', siteName);

  // Reset singleton so it picks up the new siteId and tokens
  singleton = new AuthClient({
    apiUrl: AEGIS_API_URL,
    siteId,
    autoRefresh: false,
  });
  singleton.setTokensFromLoginResponse(loginResponse);
  window.dispatchEvent(new Event('aegis-auth-change'));
}

interface RefreshResult {
  success: boolean;
  expiresAt?: number;
  superseded?: boolean;
}

/**
 * Calls refreshAuthToken() on the singleton, updates localStorage on success.
 */
export async function refreshAuthTokens(): Promise<RefreshResult> {
  const client = getAuthClient();
  const generation = sessionGeneration;
  const startingToken = localStorage.getItem('auth_token');
  const startingRefreshToken = localStorage.getItem('refresh_token');
  const isCurrentSession = () => generation === sessionGeneration &&
    startingToken === localStorage.getItem('auth_token') &&
    startingRefreshToken === localStorage.getItem('refresh_token');
  let result: ApiResponse<RefreshTokenResponse>;
  try {
    result = await client.refreshAuthToken();
  } catch {
    return { success: false, superseded: !isCurrentSession() };
  }
  // Logout, replacement login, or another tab changed the session while this
  // request was in flight. Never restore its tokens or log out the new user.
  if (!isCurrentSession()) {
    if (singleton === client) singleton = null;
    return { success: false, superseded: true };
  }

  if (!result.success) {
    return { success: false };
  }

  const { auth_token, refresh_token } = result.data;

  localStorage.setItem('auth_token', auth_token.token);
  localStorage.setItem('token_expires_at', auth_token.expires_at.toString());
  client.setAuthToken(auth_token.token);

  if (refresh_token) {
    localStorage.setItem('refresh_token', refresh_token.token);
    client.setRefreshToken(refresh_token.token);
  }

  window.dispatchEvent(new Event('aegis-auth-change'));
  return { success: true, expiresAt: auth_token.expires_at };
}

/**
 * Returns true if the auth token is expired or expiring within the buffer window.
 */
export function isTokenExpired(bufferSeconds: number = 300): boolean {
  const expiresAtStr = localStorage.getItem('token_expires_at');
  if (!expiresAtStr) {
    return true;
  }

  const expiresAt = parseInt(expiresAtStr, 10);
  const nowSeconds = Math.floor(Date.now() / 1000);
  return !Number.isFinite(expiresAt) || nowSeconds >= (expiresAt - bufferSeconds);
}

/**
 * Clears the singleton tokens and all auth-related localStorage keys.
 */
export function clearAuthClient(): void {
  sessionGeneration += 1;
  if (singleton) {
    singleton.clearAllTokens();
  }
  singleton = null;

  localStorage.removeItem('auth_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('token_expires_at');
  localStorage.removeItem('user_id');
  localStorage.removeItem('site_id');
  localStorage.removeItem('site_name');
  window.dispatchEvent(new Event('aegis-auth-change'));
}

export function getSiteDomain(): string {
  return SITE_DOMAIN;
}

/**
 * Proxy shim for the six gated public auth endpoints. After Aegis backend v40+
 * these endpoints require an X-Tenant-Api-Key header that must live server-side
 * (see references/tenant-api-key-templates.md). The browser calls our local
 * /api/frontend/auth/* routes; the server attaches the header and forwards to
 * Aegis. Auth pages should call browserAuthProxy.* for these methods, not the
 * singleton AuthClient.
 */
type ProxyResult<T> =
  | { success: true; data: T }
  | { success: false; error: string; statusCode: number };

async function postProxy<T>(path: string, body: unknown): Promise<ProxyResult<T>> {
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
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Network error',
      statusCode: 0,
    };
  }
}

export const browserAuthProxy = {
  register: (email: string, password?: string) =>
    postProxy('/api/frontend/auth/register', { email, password }),
  login: (email: string, password: string) =>
    postProxy<LoginResponse>('/api/frontend/auth/login', { email, password }),
  requestPasswordReset: (email: string) =>
    postProxy('/api/frontend/auth/request-password-reset', { email }),
  resetPassword: (token: string, newPassword: string) =>
    postProxy('/api/frontend/auth/reset-password', { token, new_password: newPassword }),
  verifyEmail: (token: string, password?: string) =>
    postProxy('/api/frontend/auth/verify-email', { token, password }),
  checkVerificationToken: (token: string) =>
    postProxy<{ password_required: boolean; email: string }>(
      '/api/frontend/auth/check-verification-token',
      { token },
    ),
};

export { AuthClient };
export type { LoginResponse };
```

---

## lib/useAuth.ts

```typescript
'use client';

import { useEffect, useSyncExternalStore } from 'react';
import { clearAuthClient, isTokenExpired, refreshAuthTokens } from './browserClient';

interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  userId: string | null;
  siteId: string | null;
  siteName: string | null;
  token: string | null;
  refreshToken: string | null;
  tokenExpiresAt: number | null;
}

const serverState: AuthState = {
  isAuthenticated: false, isLoading: true, userId: null, siteId: null,
  siteName: null, token: null, refreshToken: null, tokenExpiresAt: null,
};
let lastSerialized: string | undefined;
let snapshot = serverState;

function getSnapshot(): AuthState {
  const values = ['auth_token', 'refresh_token', 'token_expires_at', 'user_id', 'site_id', 'site_name']
    .map((key) => localStorage.getItem(key));
  const serialized = JSON.stringify(values);
  if (serialized !== lastSerialized) {
    lastSerialized = serialized;
    const [token, refreshToken, expiresAt, userId, siteId, siteName] = values;
    snapshot = {
      isAuthenticated: !!token, isLoading: false, token, refreshToken,
      tokenExpiresAt: expiresAt ? Number(expiresAt) : null, userId, siteId, siteName,
    };
  }
  return snapshot;
}

function subscribe(listener: () => void): () => void {
  window.addEventListener('storage', listener);
  window.addEventListener('aegis-auth-change', listener);
  return () => {
    window.removeEventListener('storage', listener);
    window.removeEventListener('aegis-auth-change', listener);
  };
}

let pendingRefresh: Promise<void> | null = null;
function checkExpiry(): void {
  if (!localStorage.getItem('auth_token') || !isTokenExpired() || pendingRefresh) return;
  pendingRefresh = refreshAuthTokens()
    .then((result) => { if (!result.success && !result.superseded) logout(); })
    .catch(() => logout())
    .finally(() => { pendingRefresh = null; });
}

export function useAuth(): AuthState {
  const state = useSyncExternalStore(subscribe, getSnapshot, () => serverState);
  useEffect(() => {
    if (!state.isAuthenticated) return;
    checkExpiry();
    const timer = setInterval(checkExpiry, 60_000);
    return () => clearInterval(timer);
  }, [state.isAuthenticated]);
  return state;
}

export function logout(): void {
  clearAuthClient();
}
```

### Additional application credentials

Logout clears the shared auth store; protected pages observe the change and use their locale-aware router to redirect. If the project has additional API clients that cache credentials, clear those too:

```typescript
import { clearApplicationCredentials } from './applicationClient';

export function logout(): void {
  clearAuthClient();
  clearApplicationCredentials();
}
```

# Auth Utility Templates

## CRITICAL - Substitution Notes

- Replace `{aegis_api_url}` with the actual Aegis API URL for the target project (e.g., `https://aegis.example.com/api`)
- Replace `{site_domain}` with the actual site domain for the target project (e.g., `myapp.example.com`)
- The `useAuth.ts` file is identical across all projects; no substitution is needed
- `byteforge-aegis-client-js` v2.0 supports refresh tokens with auto-refresh enabled by default
- localStorage keys used: `auth_token`, `refresh_token`, `token_expires_at`, `user_id`, `site_id`, `site_name`

---

## lib/browserClient.ts

```typescript
/**
 * Browser-side auth client using byteforge-aegis-client-js directly.
 */

import { AuthClient } from 'byteforge-aegis-client-js';

const AEGIS_API_URL = process.env.NEXT_PUBLIC_AEGIS_API_URL || '{aegis_api_url}';
const SITE_DOMAIN = process.env.NEXT_PUBLIC_SITE_DOMAIN || '{site_domain}';

// Browser-side auth client (no siteId yet - used for site lookup)
export function getAuthClient(): AuthClient {
  return new AuthClient({ apiUrl: AEGIS_API_URL });
}

// Browser-side auth client with siteId (for login)
export function getAuthClientForSite(siteId: number): AuthClient {
  return new AuthClient({ apiUrl: AEGIS_API_URL, siteId });
}

export function getSiteDomain(): string {
  return SITE_DOMAIN;
}

export { AuthClient };
```

---

## lib/useAuth.ts

```typescript
'use client';

import { useState, useEffect } from 'react';

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

export function useAuth(): AuthState {
  const [state, setState] = useState<AuthState>({
    isAuthenticated: false,
    isLoading: true,
    userId: null,
    siteId: null,
    siteName: null,
    token: null,
    refreshToken: null,
    tokenExpiresAt: null,
  });

  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    const refreshToken = localStorage.getItem('refresh_token');
    const tokenExpiresAtStr = localStorage.getItem('token_expires_at');
    const userId = localStorage.getItem('user_id');
    const siteId = localStorage.getItem('site_id');
    const siteName = localStorage.getItem('site_name');

    setState({
      isAuthenticated: !!token,
      isLoading: false,
      userId,
      siteId,
      siteName,
      token,
      refreshToken,
      tokenExpiresAt: tokenExpiresAtStr ? parseInt(tokenExpiresAtStr, 10) : null,
    });
  }, []);

  return state;
}

export function logout(): void {
  localStorage.removeItem('auth_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('token_expires_at');
  localStorage.removeItem('user_id');
  localStorage.removeItem('site_id');
  localStorage.removeItem('site_name');
  window.location.href = '/';
}
```

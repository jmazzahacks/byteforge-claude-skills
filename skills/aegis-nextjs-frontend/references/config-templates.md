# Configuration File Templates for Aegis Next.js Frontend

These templates provide the baseline configuration files needed when scaffolding a new Next.js frontend project integrated with ByteForge Aegis authentication.

---

## CRITICAL: Placeholder Replacement Guide

Before using these templates, you MUST replace all `{placeholder}` values with project-specific values. Failure to replace any placeholder will result in a broken project.

| Placeholder | Description | Example |
|---|---|---|
| `{project-name}` | Hyphenated project name for package.json `name` field | `my-saas-app` |
| `{project_description}` | Short description of the project | `Frontend for My SaaS Application` |
| `{author_name}` | Author's full name | `Jason Byteforge` |
| `{author_email}` | Author's email address | `jason@example.com` |
| `{aegis_api_url}` | Full URL to the Aegis authentication API (must be browser-accessible) | `https://aegis.example.com` |
| `{aegis_site_uuid}` | Site UUID string from Aegis admin | `01900000-0000-7000-8000-000000000002` |
| `{site_domain}` | Domain of the site as registered in the Aegis site configuration | `myapp.example.com` |

CRITICAL: The `{project-name}` placeholder uses hyphens (for npm naming conventions), while other placeholders use underscores. Pay attention to this distinction.

CRITICAL: The `NEXT_PUBLIC_` prefix on environment variables is required by Next.js to expose them to the browser. Do not remove this prefix.

---

## 1. package.json

```json
{
  "name": "{project-name}",
  "version": "1.0.0",
  "description": "{project_description}",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint ."
  },
  "author": "{author_name} <{author_email}>",
  "license": "Proprietary",
  "dependencies": {
    "@tailwindcss/postcss": "^4.1.17",
    "byteforge-aegis-client-js": "git+https://github.com/jmazzahacks/byteforge-aegis-client-js.git#e3736429b0994d488f10f692129aa48e925c5594",
    "byteforge-loki-logging-ts": "git+https://github.com/jmazzahacks/byteforge-loki-logging-ts.git#6bf1526f8d7bd82f972560bfe2b898ae04f85250",
    "next": "^16.0.1",
    "next-intl": "^4.6.1",
    "react": "^19.2.3",
    "react-dom": "^19.2.3"
  },
  "devDependencies": {
    "@types/node": "^24.10.0",
    "@types/react": "^19.2.3",
    "@types/react-dom": "^19.2.3",
    "autoprefixer": "^10.4.22",
    "eslint": "^9.39.1",
    "eslint-config-next": "^16.0.1",
    "postcss": "^8.5.6",
    "tailwindcss": "^4.1.17",
    "typescript": "^5.9.3"
  }
}
```

---

## 2. next.config.ts

```typescript
import type { NextConfig } from 'next';
import createNextIntlPlugin from 'next-intl/plugin';

const withNextIntl = createNextIntlPlugin('./i18n/request.ts');

const nextConfig: NextConfig = {
  transpilePackages: ['byteforge-aegis-client-js', 'byteforge-loki-logging-ts'],
  output: 'standalone',
};

export default withNextIntl(nextConfig);
```

CRITICAL: The `transpilePackages` entries for `byteforge-aegis-client-js` and `byteforge-loki-logging-ts` are required because both packages are installed from GitHub repositories and must be transpiled by Next.js. Removing either will cause build failures.

CRITICAL: The `output: 'standalone'` setting is required for Docker deployments. It produces a self-contained build that does not depend on `node_modules` at runtime.

CRITICAL: The `next-intl` plugin path `'./i18n/request.ts'` must match the actual location of the i18n request configuration file in the project.

---

## 3. tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "react-jsx",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts", ".next/dev/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

CRITICAL: The `"moduleResolution": "bundler"` setting is required for Next.js 16+ compatibility. Do not change this to `"node"` or `"node16"`.

CRITICAL: The path alias `"@/*": ["./*"]` enables imports like `import { Foo } from '@/components/Foo'`. This convention must be used consistently throughout the project.

---

## 4. tailwind.config.ts

```typescript
import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};

export default config;
```

CRITICAL: The `content` array must include all directories that contain Tailwind CSS classes. If you add new directories with components (e.g., `./lib/`, `./layouts/`), you must add them to this array or their Tailwind classes will be purged from the production build.

---

## 5. postcss.config.mjs

```javascript
const config = {
  plugins: {
    '@tailwindcss/postcss': {},
  },
};

export default config;
```

CRITICAL: This uses the `@tailwindcss/postcss` plugin (Tailwind CSS v4 approach) rather than the legacy `tailwindcss` PostCSS plugin. This must match the dependency in `package.json`.

---

## 6. global.d.ts

```typescript
import en from './messages/en.json';

declare module 'next-intl' {
  interface AppConfig {
    Messages: typeof en;
  }
}
```

CRITICAL: This file provides TypeScript type safety for `next-intl` message keys. The import path `'./messages/en.json'` must point to the English (default) messages file. If the messages directory is located elsewhere, update this path accordingly.

CRITICAL: This file must be placed in the project root directory so the relative import to `./messages/en.json` resolves correctly.

---

## 7. .env.example

```
# Aegis Authentication API URL (browser-accessible — used only for the
# unprotected getSiteByDomain bootstrap)
NEXT_PUBLIC_AEGIS_API_URL={aegis_api_url}

# Site domain for authentication (must match aegis site configuration)
NEXT_PUBLIC_SITE_DOMAIN={site_domain}

# Sibling-backend variant only: required at build time for that variant.
# AUTH_PROXY_MODE=sibling
# NEXT_PUBLIC_BACKEND_API_URL=https://api.example.com
# NEXT_PUBLIC_AEGIS_SITE_ID={aegis_site_uuid}

# Default Next.js proxy: runtime config below. For the sibling-backend
# variant, put these three vars in the backend repo instead.
# Server-side Aegis URL (used by /api/frontend/auth/* proxy routes)
AEGIS_API_URL={aegis_api_url}

# Per-tenant secret for X-Tenant-Api-Key header. Get from the Aegis admin
# dashboard. SERVER-SIDE ONLY — never expose in browser code.
# See references/tenant-api-key-templates.md for the full pattern.
AEGIS_TENANT_API_KEY=

# Site UUID string from Aegis (server-side, used by proxy routes for verify-email/etc.)
AEGIS_SITE_ID={aegis_site_uuid}

# Logging: set DEBUG_LOCAL=true for console output, omit or set to false for Loki
DEBUG_LOCAL=true
# LOKI_URL=https://loki.example.com
# LOKI_USER=
# LOKI_PASS=
# LOKI_CA_PATH=
```

CRITICAL: Copy this file to `.env.local` for local development. Never commit `.env.local` to version control.

CRITICAL: The `NEXT_PUBLIC_AEGIS_API_URL` must be accessible from the user's browser, not just from the server. This means it cannot be an internal Docker network address in production -- it must be a publicly routable URL or a URL accessible from the client's network.

CRITICAL: The `NEXT_PUBLIC_SITE_DOMAIN` must exactly match the site domain configured in the Aegis backend. A mismatch will cause authentication failures.


## 8. eslint.config.mjs

```javascript
import { defineConfig, globalIgnores } from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTs from 'eslint-config-next/typescript';

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores(['.next/**', 'out/**', 'build/**', 'next-env.d.ts']),
]);
```

Run `eslint .` separately from the build; Next.js 16 removed `next lint`.
See [Next.js ESLint configuration](https://nextjs.org/docs/app/api-reference/config/eslint)
and [next-intl AppConfig augmentation](https://next-intl.dev/docs/workflows/typescript).

The Git revisions above pin the tested Aegis JS 4.2.0 and Loki 0.5.0 contracts.
Commit the generated package-lock.json. When updating either revision, review its
lifecycle scripts and re-run lint, typecheck, and build. Git dependencies may need
`prepare` to create dist/: inspect the installed package entrypoints. If npm's
script policy blocks a reviewed Git dependency, explicitly build that dependency
in an isolated install step and verify its exports; do not broadly enable scripts
for every dependency or assume allowScripts covers Git prepare scripts.

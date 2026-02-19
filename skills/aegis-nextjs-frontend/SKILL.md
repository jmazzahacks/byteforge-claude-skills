---
name: aegis-nextjs-frontend
description: This skill should be used when the user asks to "create a new website", "spin up a frontend", "set up a Next.js site with aegis auth", "scaffold a new web app with authentication", "create a site with login and i18n", or needs a production-ready Next.js frontend integrated with ByteForge Aegis authentication. Provides complete project scaffolding with auth pages, internationalization, Docker deployment, and a design system.
---

# Next.js Frontend with ByteForge Aegis Authentication

This skill scaffolds a complete Next.js 16 frontend with ByteForge Aegis authentication, internationalization (next-intl), Tailwind CSS v4, and Docker deployment. The generated project includes login, email verification, password reset, and protected dashboard pages out of the box.

## When to Use This Skill

- Starting a new web application that needs user authentication
- Creating a frontend for an existing ByteForge Aegis-powered backend
- Spinning up a new site with login, signup, i18n, and Docker support
- Needing a production-ready Next.js template with auth already wired up

## What This Skill Creates

1. **Next.js 16 project** with App Router and `[locale]` dynamic segments
2. **Full auth flow** - Login, email verification, password reset, email change confirmation, welcome page
3. **Protected dashboard** - Auth-gated page with redirect to login
4. **Internationalization** - next-intl with English translations (extensible to any language)
5. **Auth utilities** - `useAuth` hook, `browserClient` wrapper, `AuthCTA` component
6. **Language switcher** - Scalable dropdown component in header
7. **Design system** - CSS variables, light/dark mode, animations, card/button/input components
8. **Docker deployment** - Multi-stage Dockerfile with standalone output
9. **Health check endpoint** - `/api/health` for container orchestration
10. **Loki logging** - Structured server-side logging with Grafana Loki (production) and console fallback (local dev)

## Step 1: Gather Project Information

**IMPORTANT**: Before creating any files, ask the user these questions:

1. **"What is your project name?"** (e.g., "DevNotes", "TaskFlow", "ReleasePad")
   - Derive:
     - `{ProjectName}` - Display name (e.g., "DevNotes")
     - `{project-name}` - Kebab case for package.json, Docker, URLs (e.g., "devnotes")
     - `{project_name}` - Snake case for internal use (e.g., "dev_notes")

2. **"What is the site domain?"** (e.g., "devnotes.ai", "taskflow.reallybadapps.com")
   - Used for `NEXT_PUBLIC_SITE_DOMAIN`

3. **"What is the Aegis API URL?"** (default: `https://aegis.reallybadapps.com`)
   - Used for `NEXT_PUBLIC_AEGIS_API_URL`

4. **"What is the container registry URL?"** (e.g., `ghcr.io/org/project-frontend`)
   - Used in docker-compose and build scripts

5. **"What is a one-line description of the project?"** (e.g., "AI-powered release notes platform")
   - Used in metadata, home page subtitle, health check

## Step 2: Create Directory Structure

```
{project-name}-frontend/
├── app/
│   ├── layout.tsx
│   ├── globals.css
│   ├── [locale]/
│   │   ├── layout.tsx
│   │   ├── page.tsx                    # Home page (customize per project)
│   │   ├── login/page.tsx
│   │   ├── verify-email/page.tsx
│   │   ├── forgot-password/page.tsx
│   │   ├── reset-password/page.tsx
│   │   ├── confirm-email-change/page.tsx
│   │   ├── welcome/page.tsx
│   │   └── dashboard/page.tsx
│   └── api/health/route.ts
├── i18n/
│   ├── routing.ts
│   ├── request.ts
│   └── navigation.ts
├── lib/
│   ├── browserClient.ts
│   ├── logger.ts
│   └── useAuth.ts
├── components/
│   ├── AuthCTA.tsx
│   └── LanguageSwitcher.tsx
├── messages/
│   └── en.json
├── proxy.ts                            # next-intl middleware
├── package.json
├── next.config.ts
├── tsconfig.json
├── tailwind.config.ts
├── postcss.config.mjs
├── global.d.ts
├── .env.example
├── Dockerfile
└── docker-compose.example.yaml
```

## Step 3: Create Configuration Files

Generate each configuration file using the templates in `references/config-templates.md`. These files are mostly boilerplate with placeholder substitutions:

- `package.json` - Dependencies including `byteforge-aegis-client-js`, `byteforge-loki-logging-ts`, `next-intl`, Tailwind v4
- `next.config.ts` - next-intl plugin, transpilePackages for aegis client and loki logging, standalone output
- `tsconfig.json` - ES2017 target, strict mode, `@/*` path alias
- `tailwind.config.ts` - Content paths for app/ and components/
- `postcss.config.mjs` - `@tailwindcss/postcss` plugin
- `global.d.ts` - IntlMessages type declaration
- `.env.example` - `NEXT_PUBLIC_AEGIS_API_URL`, `NEXT_PUBLIC_SITE_DOMAIN`, and Loki logging variables

**CRITICAL**: Replace all instances of `{project-name}`, `{ProjectName}`, `{site_domain}`, `{aegis_api_url}`, and `{project_description}` in every file.

## Step 4: Create i18n Infrastructure

Generate files from `references/i18n-templates.md`:

- `i18n/routing.ts` - Locale definitions (start with `['en']`, add more as needed)
- `i18n/request.ts` - Server-side message loading
- `i18n/navigation.ts` - Locale-aware `Link`, `useRouter`, `usePathname`
- `proxy.ts` - next-intl middleware (matches all paths except `/api`, `/_next`, static files)

These files are identical across projects. No placeholder substitution needed.

## Step 5: Create Auth Utilities

Generate files from `references/auth-templates.md`:

- `lib/browserClient.ts` - Wraps `byteforge-aegis-client-js` with env-based configuration
- `lib/useAuth.ts` - React hook reading auth state from localStorage (supports refresh tokens)

These files are identical across projects except for the default env variable values.

## Step 6: Create Auth Pages

Generate all authentication pages from `references/auth-page-templates.md`:

- `app/[locale]/login/page.tsx` - Email/password form, site lookup, token storage
- `app/[locale]/verify-email/page.tsx` - Token validation, optional password setup
- `app/[locale]/forgot-password/page.tsx` - Email input, always shows success (security)
- `app/[locale]/reset-password/page.tsx` - New password form with confirmation
- `app/[locale]/confirm-email-change/page.tsx` - Auto-confirms on load
- `app/[locale]/welcome/page.tsx` - Success page with confetti animation

**CRITICAL**: In each auth page, replace the branded footer text. The pattern uses a split-color brand display:
```tsx
<span className="text-[var(--foreground)]">{BrandPart1}</span>
<span className="text-[var(--amber-glow)]">{BrandPart2}</span>
```
Replace these spans with the new project's brand name.

## Step 7: Create Components and Layouts

Generate from `references/component-templates.md`:

- `components/AuthCTA.tsx` - Smart button: shows "Sign In" or "Go to Dashboard" based on auth state
- `components/LanguageSwitcher.tsx` - Dropdown with globe icon, scales to any number of languages
- `app/layout.tsx` - Root layout with metadata
- `app/[locale]/layout.tsx` - Locale layout with NextIntlClientProvider

## Step 8: Create Dashboard and Home Page

Generate from `references/page-templates.md`:

- `app/[locale]/dashboard/page.tsx` - Protected page with header, logout, language switcher, placeholder content
- `app/[locale]/page.tsx` - **This page is project-specific**. Use the template as a starting point but customize the hero section, feature cards, and description for the actual project.

## Step 9: Create Design System

Generate `app/globals.css` from `references/design-system.md`.

The design system includes:
- CSS custom properties for colors (ink, paper, amber accent, status colors)
- Light and dark mode via `prefers-color-scheme`
- Google Fonts: Libre Baskerville (display) + DM Sans (body)
- Component classes: `.card`, `.input-field`, `.btn-primary`, `.btn-secondary`, `.spinner`
- Status classes: `.status-success`, `.status-error`
- Animation utilities: `fadeInUp`, `fadeIn`, `scaleIn`, delay classes
- Mesh gradient background and paper texture overlay

## Step 10: Create Translation File

Generate `messages/en.json` from `references/i18n-templates.md`.

Contains all translation keys organized by page: Common, Home, Welcome, Login, Verify, ForgotPassword, ResetPassword, ConfirmEmailChange, Dashboard.

**CRITICAL**: Replace `{ProjectName}` and `{project_description}` in the translation values.

## Step 11: Create Docker Files

Generate from `references/docker-templates.md`:

- `Dockerfile` - 3-stage build (deps → builder → runner) with CR_PAT for private GitHub packages
- `docker-compose.example.yaml` - Service definition with image URL and port mapping
- `app/api/health/route.ts` - Returns JSON with status, service name, and unix timestamp

## Step 12: Configure Loki Logging

Generate `lib/logger.ts` from `references/logging-templates.md`.

This provides a dual-mode logger:
- **Local dev** (`DEBUG_LOCAL=true`) — Formatted console output, no Loki connection needed
- **Production** (`LOKI_URL` set) — Structured JSON logs shipped to Grafana Loki with batching

After creating `lib/logger.ts`, import the `logger` singleton in all API route handlers (`app/api/**/route.ts`). Use `logger.info()` for success paths and `logger.error()` in catch blocks, always including the `route` field in extra for Loki filtering.

**CRITICAL**: Replace `{project-name}` in the logger template (appears in emitter tags and the default singleton).

**CRITICAL**: `byteforge-loki-logging-ts` is server-side only (uses `node:https`). Never import it in `'use client'` files or Edge Runtime routes.

## Step 13: Initialize and Verify

```bash
npm install
npm run build
```

Verify all 10 pages generate (3 locales × pages if multiple languages, or just `/en/*` for single language).

## Design Principles

### Authentication Pattern
- All auth state stored in localStorage (`auth_token`, `refresh_token`, `token_expires_at`, `user_id`, `site_id`, `site_name`)
- `byteforge-aegis-client-js` v2.0 with auto-refresh enabled by default
- Site lookup by domain on login page mount
- Protected pages redirect to `/login` when not authenticated

### Internationalization
- URL structure: `/{locale}/page` (e.g., `/en/login`, `/es/login`)
- `localePrefix: 'always'` ensures locale is always in the URL
- All user-facing text goes through translation keys, never hardcoded
- Language switcher preserves current pathname when switching

### Security
- Forgot password always shows success (never reveals if email exists)
- Tokens stored in localStorage with explicit cleanup on logout
- Non-root user in Docker container
- Health check endpoint for orchestration

## Integration with Other Skills

### Docker Deployment
For custom build scripts, reference **flask-docker-deployment** pattern for `build-publish.sh` with auto-versioning.

### Database
If the project needs a database, use **postgres-setup** skill.

### Loki Logging (Flask backends)
If the project also has a Flask backend on the same Loki infrastructure, use **mz-configure-loki-logging** skill for the Python side. Both skills push to the same Grafana Loki instance and can be queried together using the `app` label.

## Additional Resources

### Reference Files

All template code is organized in reference files for progressive loading:

- **`references/config-templates.md`** - package.json, next.config.ts, tsconfig.json, tailwind, postcss, .env
- **`references/i18n-templates.md`** - Routing, request config, navigation, translations (en.json)
- **`references/auth-templates.md`** - browserClient.ts, useAuth.ts
- **`references/auth-page-templates.md`** - All 6 authentication pages
- **`references/component-templates.md`** - AuthCTA, LanguageSwitcher, layouts
- **`references/page-templates.md`** - Dashboard, home page
- **`references/design-system.md`** - globals.css with full design system
- **`references/logging-templates.md`** - lib/logger.ts with Loki and console dual-mode logging
- **`references/docker-templates.md`** - Dockerfile, docker-compose, health endpoint

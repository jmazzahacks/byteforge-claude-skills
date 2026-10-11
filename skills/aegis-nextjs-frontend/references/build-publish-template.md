# Build & Publish Template

Use Bash and anchor to the script directory so invocation from a workspace root
uses the correct Dockerfile and VERSION. Public Next.js config is baked into the
client bundle; CR_PAT is passed only as a BuildKit secret. The script stops on a
failed build/tag/push and updates VERSION only after both pushes succeed.

## Choose a tier

- **Tier 1 (standard):** export all three variables; commit the script.
- **Tier 2 (single deployment):** uncomment the two public values at the top and
  substitute `{aegis_api_url}` and `{site_domain}`. Gitignore build-publish.sh and
  keep a sanitized build-publish.sh.example. Always obtain CR_PAT from the
  environment, never embed it in either file.

Replace `{registry_url}` with the target image repository (without a tag).

## build-publish.sh

```bash
#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

# Tier 2 only: put the two public deployment values here and gitignore this script.
# NEXT_PUBLIC_AEGIS_API_URL="{aegis_api_url}"
# NEXT_PUBLIC_SITE_DOMAIN="{site_domain}"

: "${CR_PAT:?Export CR_PAT for private Git dependencies}"
: "${NEXT_PUBLIC_AEGIS_API_URL:?Set the deployment Aegis URL}"
: "${NEXT_PUBLIC_SITE_DOMAIN:?Set the registered site domain}"
export CR_PAT

# Set AUTH_PROXY_MODE=sibling only when using the sibling-backend variant.
AUTH_PROXY_MODE=${AUTH_PROXY_MODE:-nextjs}
build_options=()
case "$AUTH_PROXY_MODE" in
    nextjs) ;;
    sibling)
        : "${NEXT_PUBLIC_BACKEND_API_URL:?Set the sibling backend URL}"
        : "${NEXT_PUBLIC_AEGIS_SITE_ID:?Set the site UUID for the browser proxy client}"
        if [[ ! "$NEXT_PUBLIC_AEGIS_SITE_ID" =~ ^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$ ]]; then
            echo "NEXT_PUBLIC_AEGIS_SITE_ID must be a UUID" >&2
            exit 1
        fi
        build_options+=(--build-arg "NEXT_PUBLIC_BACKEND_API_URL=$NEXT_PUBLIC_BACKEND_API_URL")
        build_options+=(--build-arg "NEXT_PUBLIC_AEGIS_SITE_ID=$NEXT_PUBLIC_AEGIS_SITE_ID")
        ;;
    *) echo "AUTH_PROXY_MODE must be nextjs or sibling" >&2; exit 1 ;;
esac
for arg in "$@"; do
    case "$arg" in
        --no-cache) build_options+=(--no-cache) ;;
        *) echo "Unknown argument: $arg" >&2; exit 1 ;;
    esac
done

VERSION_FILE="VERSION"
CURRENT_VERSION=0
if [[ -f "$VERSION_FILE" ]]; then
    CURRENT_VERSION=$(cat "$VERSION_FILE")
fi
if [[ ! "$CURRENT_VERSION" =~ ^[0-9]+$ ]]; then
    echo "Invalid VERSION: expected an integer" >&2
    exit 1
fi
VERSION=$((10#$CURRENT_VERSION + 1))

docker build "${build_options[@]}" \
    --secret id=cr_pat,env=CR_PAT \
    --build-arg NEXT_PUBLIC_AEGIS_API_URL="$NEXT_PUBLIC_AEGIS_API_URL" \
    --build-arg NEXT_PUBLIC_SITE_DOMAIN="$NEXT_PUBLIC_SITE_DOMAIN" \
    --platform linux/amd64 \
    -t "{registry_url}:$VERSION" .
docker tag "{registry_url}:$VERSION" "{registry_url}:latest"
docker push "{registry_url}:$VERSION"
docker push "{registry_url}:latest"
# Write only after both pushes succeed; the first successful publish is :1.
printf '%s\n' "$VERSION" > "$VERSION_FILE"
echo "Published {registry_url}:$VERSION and :latest"
```

After generating: `chmod +x build-publish.sh`, add `VERSION` to .gitignore, and
create `public/.gitkeep` so Docker's public-directory COPY succeeds. Include the
.dockerignore from docker-templates.md before building.

## Usage

```bash
# CR_PAT comes from your secret manager or an already-exported environment.
export NEXT_PUBLIC_AEGIS_API_URL="{aegis_api_url}"
export NEXT_PUBLIC_SITE_DOMAIN="{site_domain}"
./build-publish.sh
./build-publish.sh --no-cache
```

The runtime container also needs AEGIS_API_URL, AEGIS_SITE_ID (UUID), and
AEGIS_TENANT_API_KEY via Compose or the deployment's secret store. Do not pass
runtime secrets as build arguments. Changing NEXT_PUBLIC_* values requires a
rebuild; changing server runtime config requires a restart.


For the sibling-backend variant, also export `AUTH_PROXY_MODE=sibling`,
`NEXT_PUBLIC_BACKEND_API_URL` and `NEXT_PUBLIC_AEGIS_SITE_ID` (the public UUID).
The script validates and forwards those public build arguments; `.env.local` is
excluded from the Docker context. Tier 2 may hardcode these public values too.
The tenant key belongs only in the sibling backend's runtime environment.

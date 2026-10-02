---
name: uv-supply-chain-hardening
description: Harden a Python project's dependency supply chain by switching Docker builds from pip to uv, pinning every dependency to the currently-installed version with hashes, and adding a release-age gate so freshly-uploaded (possibly compromised) packages can't be pulled in. Use when locking down dependencies, defending against supply-chain attacks, or migrating a Dockerized Python build from pip to uv.
---

# uv Supply-Chain Hardening

This skill converts a Python project from a loose `pip install -r requirements.txt`
build into a **locked, hash-verified, release-age-gated** build using
[uv](https://github.com/astral-sh/uv). It is the response to the wave of
supply-chain attacks targeting Python (and especially crypto) projects, where a
maintainer account is compromised and a malicious version is published to PyPI.

The defense has three layers:

1. **Pin every dependency** to an exact version — no floating ranges, so a build
   can't silently pull a newer (compromised) release.
2. **Verify hashes** — every PyPI distribution is checked against a SHA256 in the
   lockfile, so a tampered-with artifact on the registry is rejected.
3. **Release-age gate** — refuse any distribution published in the last N days, so
   a freshly-uploaded malicious version isn't pulled in before the community has a
   chance to catch and yank it.

## When to Use This Skill

- You have a Python project (with `requirements.txt` and/or `pyproject.toml`) whose
  Docker build runs `pip install` against unpinned or loosely-pinned dependencies.
- You want reproducible, tamper-evident builds.
- You're worried about a dependency (or one of its transitive deps) being hijacked.
- You have private Git dependencies and need them to coexist with hash-locking.

## What This Skill Changes

1. **`requirements.in`** (NEW) — human-edited source-of-truth list of direct deps.
2. **`requirements.txt`** (REWRITTEN) — machine-generated, fully-pinned, hashed lock.
3. **`pyproject.toml`** — adds `[tool.uv] exclude-newer` and pins the build backend
   (or a root **`uv.toml`** if the repo has no `pyproject.toml`).
4. **`Dockerfile`** — installs via a digest-pinned `uv` instead of `pip`; private-dep
   token is passed through a BuildKit secret, with value-based artifact checks.
5. **`requirements-private.txt`** (NEW, *optional*) — first-party libs installed at
   HEAD when the user wants their own libraries to always track latest (Step 5b).
6. **`dev-requirements.in` / `dev-requirements.txt`** (NEW, *optional*) — same
   pinned+hashed+age-gated treatment for dev tooling like `pytest`/`black`/`mypy`
   (Step 5c).
7. **`dev_scripts/assert_no_secret.py`** (NEW, for private-dependency builds) —
   value-based checks before publishing, including saved image layers.

Nothing about the application code changes — this is purely the dependency pipeline.

---

## Step 0: Establish the Baseline

**IMPORTANT — pin to what is _installed_, not to "latest".** The whole point is
reproducing the environment you've actually been running and testing against. If
you just run `uv pip compile` with no constraints, it resolves to the newest
versions allowed, which can jump you across several releases you never tested
(and, worse, is exactly the surface a supply-chain attack rides in on).

First, confirm uv is available and capture the currently-installed versions:

```bash
# Inside the project's activated virtualenv
uv --version || pip install uv            # or: brew install uv / pipx install uv
pip freeze > /tmp/installed-constraints.txt
```

`/tmp/installed-constraints.txt` is the constraint set that anchors the compile to
exactly what you have installed today.

**Ask the user:**

1. **"How many days should the release-age gate be?"**
   - Default: **7 days**. Long enough that most malicious releases get caught and
     yanked; short enough you still get timely security patches.

2. **"Do you have private Git dependencies?"** (yes/no)
   - If yes, note the token env var name (commonly `CR_PAT` for a GitHub PAT).

3. **"Before we freeze, are there any of your own libraries you want to update
   first?"**
   - Pinning captures a moment in time. If the user maintains internal libs with
     pending fixes, pull those in and re-`pip install` _before_ freezing, so the
     lock captures the intended versions.

4. **"Should your own private libraries be pinned, or always track latest?"**
   - A common, legitimate stance: pin the **third-party** attack surface, but let
     your **first-party** libs (the ones you maintain) float to the latest
     commit on every build — you review your own code and want fixes without a
     manual SHA bump. If they choose this, those libs do **not** get pinned in the
     lock; they go in a separate `requirements-private.txt` installed at HEAD. See
     **Step 5b** — it changes Steps 1, 2, and 4.

5. **"What Python version, OS/libc, and architecture does the *container* run?"**
   - You must compile the lock for the container's Python (`--python-version`), not
     your laptop's. A local 3.14 venv resolving for a 3.13 image picks different
     wheels/markers. Read it off the `FROM python:X.Y` line. Also pass the target
     `--python-platform` on every compile: e.g. `x86_64-unknown-linux-musl` for
     x86_64 Alpine, `x86_64-unknown-linux-gnu` for x86_64 Debian, or the matching
     aarch64 target for ARM. Do not infer the container platform from the laptop.

---

## Step 1: Create `requirements.in` (source of truth)

`requirements.in` lists only your **direct** dependencies — the things you actually
import — with no version pins (the lock supplies those). This is the file a human
edits; `requirements.txt` is never hand-edited again.

```
# requirements.in — direct dependencies only. Edit this, then recompile
# requirements.txt with:
#   uv pip compile requirements.in --generate-hashes --python-version 3.13 \
#     --python-platform x86_64-unknown-linux-musl -o requirements.txt
#
# Pins and hashes for the full transitive tree live in requirements.txt.

example-http-client
example-db-driver
some-public-lib

# Private Git dependency — pinned to an immutable commit SHA, not a branch.
# The commit SHA is the integrity anchor (a branch can be force-pushed; a SHA
# can't). Keep URLs token-free; process-scoped Git configuration supplies auth.
internal-lib @ git+https://github.com/your-org/internal-lib.git@<commit-sha>
```

**CRITICAL replacements:**
- Direct dependency names → the user's actual top-level imports (mine these from the
  existing `pyproject.toml` `dependencies` and/or the un-hashed `requirements.txt`).
- `internal-lib @ git+...@<commit-sha>` → each private dep, **pinned by full commit
  SHA**. If it's currently pinned to a branch or unpinned, resolve the current commit
  (`git ls-remote https://github.com/your-org/internal-lib.git <branch>`) and pin it.
- `CR_PAT` in the authentication examples → the user's token env var name.

For local private-Git operations, define this Bash helper in the working shell
after loading the token securely. Use `with_private_git uv ...` for each compile
or install that fetches private repos, and `with_private_git git ls-remote ...`
when resolving a pin. It scopes credentials to a subshell and writes no gitconfig:

```bash
with_private_git() (
  set +x
  : "${CR_PAT:?Load the private Git token first}"
  export GIT_CONFIG_COUNT=1 \
    GIT_CONFIG_KEY_0="url.https://${CR_PAT}@github.com/.insteadOf" \
    GIT_CONFIG_VALUE_0="https://github.com/"
  "$@"
)
```

Replace the host/rewrite for the project's Git provider. If the environment already
uses `GIT_CONFIG_COUNT`, append to its entries instead of overwriting them. Do not
enable shell tracing or dump the environment/config while credentials are loaded.

> **Why a commit SHA for Git deps:** Git distributions cannot carry a PyPI-style
> hash in the lock (see Step 5). The commit SHA _is_ the hash — it's the only thing
> anchoring the integrity of a Git dependency, so it is non-negotiable for these.

> **⚠️ Token-baking via a library's OWN `pyproject.toml` (the subtle leak — check
> this every time).** Distinct from the Dockerfile `ENV` leak in Step 4/6. If one of
> your private libraries declares its *own* dependencies as
> `git+https://{env:CR_PAT}@github.com/...` (the hatch `{env:...}` context form),
> **hatchling expands the token at build time into the wheel's `Requires-Dist`
> metadata** — so a live PAT gets frozen into every image built from that lib, even
> with a flawless Dockerfile. Use token-free URLs in requirements, locks, and
> package metadata alike; keep authentication in Git's process configuration.
> **Fix the library:** declare its deps with token-free URLs
> (`git+https://github.com/...`) and let git `insteadOf` supply auth at install —
> this stays compatible with unpinned/always-latest deps. Then **rotate the PAT**,
> since older built images still carry it. Scan for it in Step 6.

---

## Step 2: Compile the Locked, Hashed `requirements.txt`

Compile from `requirements.in`, constrained to the installed versions, with hashes:

Apply the Step 3 release-age configuration **before this first compile** so its
resolution is already gated. For private Git dependencies use the Step 1 auth
helper around the compile command.

```bash
# A raw `pip freeze` includes VCS/editable lines (`pkg @ git+...`, `-e ...`,
# `pkg @ file://...`) that uv rejects as constraints — keep only `name==version`:
grep -E '^[A-Za-z0-9._-]+==[0-9]' /tmp/installed-constraints.txt > /tmp/constraints.txt

uv pip compile requirements.in \
  --generate-hashes \
  --python-version 3.13 --python-platform x86_64-unknown-linux-musl \
  -c /tmp/constraints.txt \
  -o requirements.txt
```

- `--generate-hashes` → writes a SHA256 (often several, one per wheel/sdist) for
  every PyPI distribution. This is what makes registry tampering detectable.
- `--python-version <X.Y>` → **resolve for the Python the container runs, not your
  laptop's.** Compiling under a different interpreter (local 3.14, image 3.13) can
  select different wheels/markers. Match the `FROM python:X.Y` in the Dockerfile.
- `--python-platform` → the container OS/libc and architecture from Step 0; all
  examples below use x86_64 Alpine. Replace this consistently for the actual target.
- `-c /tmp/constraints.txt` → **pins to the versions you already have installed**
  rather than resolving to latest. This is the step people forget; without it the
  lock can leap forward across untested releases.
- The output is the full transitive tree, every package pinned to `==` with hashes.

**Verify the pin matched the baseline.** Diff the new pins against what you had:

```bash
# Sanity check: the compiled versions should match installed ones (modulo
# package-name normalization like Flask -> flask, PyYAML -> pyyaml).
diff <(grep -oE '^[a-zA-Z0-9_.-]+==[0-9][^ ]*' requirements.txt | sort) \
     <(sort /tmp/installed-constraints.txt)
```

You will see two classes of legitimate right-side-only lines:
- **Name-case/separator normalization** (`Flask` → `flask`, `PyYAML` → `pyyaml`).
- **Dev-only tooling in the same venv** — under the standard project layout,
  `pytest` / `black` / `mypy` / `ruff` / etc. installed from `dev-requirements.txt`
  will appear on the right side because they aren't in the runtime lock. Expected;
  ignore. If dev tooling should also be hardened, see **Step 5c**.

What matters is a **runtime** package whose version actually _moved_ — that's what
this process exists to make visible, and it should never happen on the initial
constrained compile.

> **Reproducible header — one extra compile pass.** The initial compile records
> `-c /tmp/constraints.txt` in `requirements.txt`'s autogenerated header (and in
> every `# via -c ...` annotation), so a reader can't rerun the recorded command
> from the repo — the file it points at doesn't exist. Fix it in one pass by
> re-compiling with **no `-c` at all**; uv reads pins from the existing `-o
> requirements.txt` (see the "preserves pins" property below), so resolution is
> a no-op version-wise:
>
> ```bash
> uv pip compile requirements.in \
>   --generate-hashes --python-version 3.13 --python-platform x86_64-unknown-linux-musl \
>   -o requirements.txt
> ```
>
> The header and annotations now reference only `requirements.in` and
> `requirements.txt` — a fresh clone can rerun the recorded command as-is. Do
> this **only on the initial compile** (a routine recompile is already this shape).

> **uv preserves existing pins on recompile — in the single-lock flow.** Once
> `requirements.txt` exists and is the `-o` target, a later `uv pip compile`
> reads pins from it and keeps them unless you pass `--upgrade` (or
> `--upgrade-package NAME`). Routine recompiles (e.g. after adding one new dep to
> `requirements.in`) won't silently bump everything else. Document this in the
> file header so the next editor knows the lock is sticky.
>
> **This does NOT hold in the Step 5b split flow** — that variant compiles to a
> throwaway intermediate (`requirements.full.txt`) that gets `rm`'d, so the next
> recompile has nothing to preserve against. Step 5b handles that with an explicit
> `-c requirements.txt` on subsequent runs; see there.

---

## Step 3: Add the Release-Age Gate + Pin the Build Backend (`pyproject.toml`)

Two additions to `pyproject.toml`.

If the project already has `uv.toml`, put the age gate there as a top-level key
instead: uv reads it in preference to `[tool.uv]` in the same directory's
`pyproject.toml`. Preserve existing settings. See uv's
[configuration precedence](https://docs.astral.sh/uv/concepts/configuration-files/).

**(a) The release-age gate** under `[tool.uv]`:

```toml
[tool.uv]
# Supply-chain defense: refuse any distribution published in the last 7 days when
# resolving/locking, so a freshly-uploaded (possibly compromised) version can't be
# pulled in before the community catches and yanks it. Applies to BOTH
# `uv pip compile` and `uv pip install`. This is a rolling window evaluated at
# run time — not a fixed date — so it keeps protecting future installs.
exclude-newer = "7 days"
```

- `exclude-newer` accepts a friendly duration (`"7 days"`) or an ISO-8601 timestamp.
  Prefer the duration: it's a **rolling** gate that keeps working on every future
  build, whereas a fixed timestamp goes stale.
- Replace `7 days` with the answer from Step 0.

> **No `pyproject.toml`? (a Flask/service repo, not a package.)** Put the setting in
> a **`uv.toml`** at the repo root instead — uv reads it for both compile and
> install. In `uv.toml` the keys are top-level (no `[tool.uv]` table):
> ```toml
> # uv.toml
> exclude-newer = "7 days"
> ```
> And **skip part (b)** below — a repo that never builds a wheel has no build backend
> to pin.

**(b) Pin the build backend** under `[build-system]` — otherwise the backend itself
(e.g. hatchling/setuptools) is an unpinned dependency resolved at wheel-build time,
and is just as hijackable as any other:

```toml
[build-system]
# Pinned (not floating) so the build backend can't be swapped for a newer,
# potentially compromised release at build time. exclude-newer keeps it >=7 days
# old; bump deliberately when upgrading.
requires = ["hatchling==1.29.0"]
build-backend = "hatchling.build"
```

**CRITICAL:** use the backend the project already uses, pinned to its installed
version (`pip show hatchling` / `pip show setuptools`). Don't switch backends.

---

## Step 4: Convert the Dockerfile from pip to uv

Replace the install flow while preserving the project's base image, startup and
non-root user conventions. Private dependencies require a BuildKit secret mount;
`ARG` and `ENV` are not safe secret transports. Docker documents this distinction
in [Build secrets](https://docs.docker.com/build/building/secrets/).

Copy this skill's [scripts/assert_no_secret.py](scripts/assert_no_secret.py) to
`dev_scripts/assert_no_secret.py` in the target project. The stdlib-only helper
checks literal token values without printing matches and fails on scan errors.
Use the same helper inside the build and for the pre-push checks in Step 6.

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.13-alpine
COPY --from=ghcr.io/astral-sh/uv:0.9.28@sha256:<digest> /uv /uvx /bin/
RUN apk add --no-cache git gcc musl-dev postgresql-dev

WORKDIR /app
# Copy the configuration actually used in Step 3; add uv.toml if it takes precedence.
COPY requirements.txt pyproject.toml README.md ./
COPY src/ ./src/
COPY dev_scripts/assert_no_secret.py /usr/local/bin/assert_no_secret.py

RUN --mount=type=secret,id=cr_pat,required=true \
    set -eu; set +x; \
    CR_PAT="$(cat /run/secrets/cr_pat)"; test -n "$CR_PAT"; \
    export GIT_CONFIG_COUNT=1 \
      GIT_CONFIG_KEY_0="url.https://${CR_PAT}@github.com/.insteadOf" \
      GIT_CONFIG_VALUE_0="https://github.com/"; \
    uv pip install --system --no-cache -r requirements.txt; \
    uv pip install --system --no-cache --no-deps .; \
    uv pip check --system; \
    python /usr/local/bin/assert_no_secret.py --secret-file /run/secrets/cr_pat \
      /usr/local/lib /app /etc /root /tmp

# ... non-root user, ENV, EXPOSE, ENTRYPOINT as before ...
```

- Substitute the uv tag/digest, Python/platform, Git host, package paths and build
  packages. For a service that is not a Python package, omit the local `.` install
  and copy its application sources using its established layout.
- Keep all private URLs token-free, including transitive declarations. Authentication
  uses Git's [process configuration](https://git-scm.com/docs/git-config#Documentation/git-config.txt-GITCONFIGCOUNT),
  not `git config --global`. Do not persist the rewrite in any file. `--no-cache`
  here is uv's cache policy: it avoids retaining fetched source/build artifacts.
- The secret mount protects the input, not what build tools write or log. Keep
  tracing off; retain the scan after **every** secret-bearing install RUN, in that
  same RUN. Include other install prefixes/cache directories if the project uses
  them. A failed scan stops the build; fix the package/source that writes secrets
  instead of deleting metadata or blindly replacing bytes in installed packages.
- Remove token `ARG`/`ENV` declarations and `--build-arg` use from build scripts and
  CI. Pass `--secret id=cr_pat,env=CR_PAT` instead. Require BuildKit; if unavailable,
  configure a builder with secret support rather than falling back to build args.
- Add `.env`, `.env.*`, token files and verification output directories to
  `.dockerignore`; avoid copying credentials with application sources.
- For **public-only** builds with no token to verify, omit the secret mount, Git
  auth setup and secret scanner invocation; keep uv's lock/config, dependency
  checks and smoke tests. Omit Git only if no VCS deps need it.

Resolve `<digest>` for the selected uv tag without needing Docker daemon access:

```bash
docker buildx imagetools inspect ghcr.io/astral-sh/uv:0.9.28
# Use the top-level Digest (manifest/index), which supports the selected platforms.
```

This is a [registry inspection](https://docs.docker.com/reference/cli/docker/buildx/imagetools/inspect/),
not a local pull. If buildx is unavailable, `crane digest` against the same reference
or an already-reviewed matching tag/digest from a maintained sibling Dockerfile is
an alternative. Verify the selected image supports the target platform. Preserve
the existing digest when no uv upgrade is intended.

---

## Step 5: The `--require-hashes` / Git-dependency Tradeoff

You may consider adding `--require-hashes` to the install for maximum strictness. Be
aware of the catch and decide consciously:

- **PyPI deps** all carry hashes in the lock, so they're verified regardless.
- **Git dependencies cannot be hashed** — there's no immutable artifact hash for a
  `git+https://...` source, only the commit SHA (which you already pinned in Step 1).
- `--require-hashes` is **all-or-nothing**: it rejects the _entire_ requirements file
  if any single line lacks a hash. So you can't use it unless you split the install
  into two steps — hashed PyPI deps in one file, unhashable Git deps in another.

**Recommendation:** unless the user wants the split, **omit `--require-hashes`**. uv
still verifies every hash that _is_ present (all the PyPI deps), so registry tampering
is already caught; `--require-hashes` would only additionally block a _future
unhashed line_ from sneaking in. Note this as an accepted tradeoff rather than
silently skipping it.

If the user does want it, split. Run the Git install inside the Step 4 secret/auth/scan
block if any of those repos are private; these are the install commands only:
```bash
uv pip install --system --no-cache --require-hashes -r /app/requirements-pypi.txt
uv pip install --system --no-cache -r /app/requirements-git.txt
```

---

## Step 5b: First-Party Libraries That Should Track Latest (the `--override` split)

Use this **only if the user chose "always track latest" for their own libs** in
Step 0. The default model pins everything; this variant pins the **third-party**
attack surface but lets **first-party** libs float to the latest commit on every
build.

**Why a plain compile won't do it — two uv behaviors collide:**

1. **uv resolves the *entire* graph; pip deduped by name.** pip tolerated your
   private libs declaring each other with `{env:CR_PAT}`/unpinned URLs because the
   top-level requirement already "satisfied" them. uv actually fetches each
   transitive git URL from a library's metadata — and if it uses `{env:CR_PAT}` (uv
   can't expand it) or floats to `HEAD` (conflicting with a top-level pin), the
   compile fails with an auth or URL-conflict error.
2. uv pins a git dep to its **resolved HEAD commit** in the output even when the
   input had no SHA — so a single lock would freeze your first-party libs to
   compile-time HEAD, defeating "always latest."

**The split that solves both:**

`requirements-private.txt` — **all direct and transitive first-party libs**,
**token-free and unpinned**. Used
twice: as the `--override` for the compile *and* as the install list in Docker.
```
internal-core @ git+https://github.com/your-org/internal-core.git
internal-models @ git+https://github.com/your-org/internal-models.git
```

The list must include the entire first-party dependency graph: if `internal-core`
depends on `internal-models`, both need entries even if only core is a direct app
dependency. Inspect the baseline's VCS entries (`pip freeze | grep 'git+'`, locally
with credentials redacted), package dependency metadata, and the full compile
output. A baseline alone can miss newly added transitive libraries. Classify by
ownership, not by whether a URL needs authentication. Every first-party package
removed from the lock must appear in this list; every retained Git package must
keep its intended pin. Replace the removal regex's example names in every compile
below with that complete first-party list, using uv's normalized distribution names.
Confirm with `uv pip check` and import smoke tests.

`requirements.in` — third-party direct deps **plus** the private libs (token-free),
so the compile discovers and locks their third-party sub-tree. The private lines are
stripped from the output afterward.

Compile (token injected only into git's process config, never a committed file).
Use the Step 1 `with_private_git` helper below; if all Git URLs are public, invoke
`uv` directly. Choose the compile mode that matches what you're doing:

**Initial compile (first run, no `requirements.txt` yet):**
```bash
with_private_git uv pip compile requirements.in \
  --override requirements-private.txt \
  --generate-hashes --no-annotate --python-version 3.13 \
  --python-platform x86_64-unknown-linux-musl \
  -c /tmp/constraints.txt \
  -o requirements.full.txt
# Strip the first-party git lines → requirements.txt holds only the locked, hashed
# third-party tree (their PyPI sub-deps stay; the private libs themselves do not).
grep -vE '^(internal-core|internal-models) @ git\+' requirements.full.txt > requirements.txt
rm requirements.full.txt
```

**Routine recompile (later — adding one dep to `requirements.in`, or a periodic
refresh, when you DON'T want a mass upgrade):**
```bash
with_private_git uv pip compile requirements.in \
  --override requirements-private.txt --refresh \
  --generate-hashes --no-annotate --python-version 3.13 \
  --python-platform x86_64-unknown-linux-musl \
  -c requirements.txt \
  -o requirements.full.txt
grep -vE '^(internal-core|internal-models) @ git\+' requirements.full.txt > requirements.txt
rm requirements.full.txt
```

**Deliberate upgrade (bump one specific package):**
Prepare `/tmp/upgrade-constraints.txt` as a copy of `requirements.txt` with only the
target package's complete requirement entry removed (including continued hash
lines). Keep all other pins. Review that small constraints diff before compiling:
```bash
with_private_git uv pip compile requirements.in \
  --override requirements-private.txt --upgrade-package NAME \
  --generate-hashes --no-annotate --python-version 3.13 \
  --python-platform x86_64-unknown-linux-musl \
  -c /tmp/upgrade-constraints.txt \
  -o requirements.full.txt
grep -vE '^(internal-core|internal-models) @ git\+' requirements.full.txt > requirements.txt
rm requirements.full.txt
```
Replace `NAME` with the target distribution name. `--upgrade-package` does **not**
override explicit constraints; leaving its old pin in the temporary constraints
would prevent the upgrade. If the new version conflicts with another pinned
dependency, review and relax that pin deliberately too. Do not drop the constraints
file entirely: that would re-resolve the whole tree (see gotcha 16).

**Deliberate full-tree upgrade (bump everything to newest within the gate):**
```bash
with_private_git uv pip compile requirements.in \
  --override requirements-private.txt --upgrade \
  --generate-hashes --no-annotate --python-version 3.13 \
  --python-platform x86_64-unknown-linux-musl \
  -o requirements.full.txt
grep -vE '^(internal-core|internal-models) @ git\+' requirements.full.txt > requirements.txt
rm requirements.full.txt
```
The only mode with no third-party constraints — you *want* the mass re-resolve.
Review the resulting diff carefully; this is the mode that
loses the "reproduces what you tested" guarantee.

- `--override requirements-private.txt` forces uv to resolve those packages from
  your token-free URLs instead of the `{env:CR_PAT}@HEAD` ones in their metadata.
- `--refresh` on routine recompiles refreshes cached first-party HEAD metadata
  so changed dependency declarations are considered. It does not relax the
  third-party constraints in `-c requirements.txt`; resolve conflicts deliberately.
- **`-c requirements.txt` on the recompile is not optional in this flow.** The
  Step 2 "uv preserves pins on recompile" property does NOT apply here — uv reads
  pins from the `-o` output file, and Step 5b's output is a throwaway
  (`requirements.full.txt` that gets `rm`'d). Without `-c requirements.txt`,
  adding a single dep to `requirements.in` silently re-resolves the ENTIRE tree to
  newest-within-the-`exclude-newer`-gate. That is the exact exposure this skill
  exists to prevent, and the 7-day gate is your only remaining line of defense
  when it happens. Do not omit.
- **`--no-annotate` is not cosmetic here either.** The grep-strip above removes
  the private-lib lines but is not annotation-aware; with annotations enabled,
  those libs' multi-line `# via ...` blocks get orphaned and visually attach to
  the next alphabetical package (real observed case: three stacked `via` blocks
  including `--override requirements-private.txt` provenance ended up under
  `marshmallow`, which a reader would reasonably conclude is a direct private
  dependency). `--no-annotate` drops all `# via` blocks — you lose the provenance
  trail, which is the accepted trade for a lock that isn't a maintenance trap.
  If you want provenance back, replace the `grep -vE` with a range-aware awk that
  drops each matched line's trailing indented `# via` block too.
- Note any **transitive public git deps** that remain in the lock (e.g. a logging
  lib pulled from GitHub) — they're unhashable, which is why `--require-hashes`
  needs the Step 5 split. Leave them in `requirements.txt` so the `--no-deps`
  install below can satisfy them.

> **The drift rule — first-party lib dep changes must trigger a backend
> recompile.** The Dockerfile below installs first-party libs `--no-deps` at HEAD.
> Their third-party sub-tree was frozen into `requirements.txt` at compile time.
> So if a first-party lib adds a new PyPI dep (or bumps one meaningfully) and you
> merge that lib change WITHOUT rerunning the "routine recompile" above in the
> backend repo, the next backend deploy will pull the lib's new HEAD, install it
> with `--no-deps`, and fail `uv pip check` (or an import smoke test). This
> is the specific cost of "always-latest first-party + pinned third-party" — the
> two sides can silently diverge. Two options:
> - **Convention:** any change-set that adds a runtime dep to a first-party lib
>   also includes a `requirements.in` recompile in the backend, shipped together.
> - **CI check:** make `uv pip check --system` fail the image build on missing or
>   incompatible declared dependencies, then run a smoke
>   `python -c "import <backend_pkg>"` in the built image for import-time failures.

Dockerfile — replace the Step 4 install RUN with the following guarded split. Run from
the project working directory and copy the Step 3 configuration before installing
(`uv.toml` below; use `pyproject.toml` instead if it holds `[tool.uv]` and no
`uv.toml` takes precedence):
```dockerfile
COPY uv.toml requirements.txt requirements-private.txt ./
# Keep the scanner COPY from Step 4.
RUN --mount=type=secret,id=cr_pat,required=true \
    set -eu; set +x; \
    CR_PAT="$(cat /run/secrets/cr_pat)"; test -n "$CR_PAT"; \
    export GIT_CONFIG_COUNT=1 \
      GIT_CONFIG_KEY_0="url.https://${CR_PAT}@github.com/.insteadOf" \
      GIT_CONFIG_VALUE_0="https://github.com/"; \
    uv pip install --system --no-cache -r requirements.txt; \
    uv pip install --system --no-cache --no-deps -r requirements-private.txt; \
    uv pip check --system; \
    python /usr/local/bin/assert_no_secret.py --secret-file /run/secrets/cr_pat \
      /usr/local/lib /app /etc /root /tmp
```
- `--no-deps` assumes all runtime dependencies are already supplied by the lock
  and the complete private install list. If the application itself is a package,
  also install it with `--no-deps` inside this RUN before the check/scan.
  `--no-deps` does not disable isolated build dependencies.
- Keep configuration discovery enabled. `exclude-newer` applies to registry
  packages, including dependencies resolved for isolated builds, **not Git commit
  dates**. A new first-party commit can install while its registry build tools
  remain age-gated. `--no-config` would discard that gate along with other
  discovered settings. See uv's [resolution documentation](https://docs.astral.sh/uv/concepts/resolution/#reproducible-resolutions)
  and [install options](https://docs.astral.sh/uv/reference/cli/#uv-pip-install).
- If a registry build dependency is too new for the selected gate, retain the
  gate and use a compatible eligible version or wait for it to age in; do not
  bypass configuration to make the Git install pass.
- `uv pip check --system` detects missing or incompatible declared runtime
  dependencies after both installs. On failure, refresh/recompile the lock and
  rebuild; do not remove the check or resolve fresh runtime deps during the build.

**⚠️ The cache trap (bites every rebuild).** A `RUN uv pip install ... requirements-private.txt`
layer is cached on the command string + the file's contents — neither changes when
the upstream branch moves, so Docker **silently reuses the old commit** and "always
latest" quietly becomes "whatever was latest the first time." To actually pull the
newest first-party code you must `docker build --no-cache` (or bust the cache above
that layer, e.g. an `ARG GIT_REV` passed each build). This is also why, right after
merging a fix to a first-party lib, the next publish must be `--no-cache`.

**Implement this in `build-publish.sh` and CI when HEAD tracking is chosen.** Add
unconditional `--no-cache` to the build invocation (including buildx builds), while
retaining `--secret id=cr_pat,env=CR_PAT`. This trades build speed for freshness;
do not leave it as a flag humans must remember. An existing per-build cache-bust
that always invalidates the private-install layer is also valid. uv's `--no-cache`
inside the RUN cannot invalidate Docker's layer cache. Place the Step 6 verification
between build and push; do not use a combined `buildx --push` before local checks.

---

## Step 5c: Harden `dev-requirements.txt` Too (optional)

Steps 1–5b lock the **runtime** dependency install. Dev tooling
(`pytest` / `black` / `mypy` / `ruff` / etc.) installed via `dev-requirements.txt`
is outside that scheme entirely — unpinned, unhashable, ungated, and installed on
exactly the machines that have `CR_PAT` exported. A compromised pytest release
served to a CI runner has the same reach as a compromised runtime dep, and the
runtime hardening does nothing to catch it.

First inspect the existing dev file and all CI/local install commands. Move only
direct dev tooling into `dev-requirements.in`. Remove legacy runtime includes such
as `-r requirements.txt` from this input; constrain the dev compile against the
runtime lock instead. Regenerate `dev-requirements.txt` rather than hand-editing its
lock entries. Under Step 5b, update consumers to install all three files: the runtime
lock, dev lock and complete private list. Merely keeping the old runtime include
silently omits first-party packages removed from that lock.

The same recipe applies, one file over:

```
# dev-requirements.in — direct dev deps only.
pytest
pytest-cov
black
mypy
ruff
```

```bash
# Compile with the RUNTIME lock as a constraint so shared transitive deps
# (e.g. `packaging`) can't resolve to a conflicting version between the two
# files. This keeps `uv pip install -r requirements.txt -r dev-requirements.txt`
# internally consistent.
uv pip compile dev-requirements.in \
  --generate-hashes --no-annotate --python-version 3.13 \
  --python-platform x86_64-unknown-linux-musl \
  -c requirements.txt \
  -o dev-requirements.txt
```

Local install — use **`uv pip install`**, not plain `pip`:

```bash
# Without the Step 5b split:
uv pip install -r requirements.txt -r dev-requirements.txt
uv pip check

# With Step 5b (use the Step 1 auth helper for private repos):
with_private_git uv pip install -r requirements.txt -r dev-requirements.txt
with_private_git uv pip install --no-deps -r requirements-private.txt
uv pip check
```

- **Plain `pip` breaks on the Step 5b lock.** `requirements.txt` under the split
  flow intentionally retains unhashable transitive public git deps (see the note
  on transitive git deps above). pip enters hash-required mode as soon as it sees
  a hashed line and then aborts with `Hashes are required in --require-hashes
  mode` on the unhashable git line. uv is more forgiving — it verifies present
  hashes without demanding them on every line.
- **Plain `pip` does not honor `exclude-newer`.** That setting lives in
  `pyproject.toml`/`uv.toml` and only uv reads it. Running pip here would install
  fresh-off-PyPI dev tooling despite the rolling gate — the exact class of attack
  Step 3 was set up to block.
- Skip this step for projects with no dev-tooling install path (a service repo
  whose CI runs a prebuilt test image, say). The point is coverage of every
  install path where PyPI can reach the machine.

---

## Step 6: Verify the Build — and That the Token Did Not Leak

Build and verify **before pushing**. Use the token already loaded securely into
the environment; do not paste it into shell commands or enable tracing. Preserve
the project's registry/tag substitution and add these checks to its publish script.
This example is for private-dependency builds; public-only projects omit the secret
input and retain their build/dependency/smoke checks. Previously exposed credentials
still need artifact verification even if the current build no longer uses them.
The following Bash example uses a local test tag and a temporary directory whose
contents may contain a leak, so it is private and removed on exit:

```bash
set -euo pipefail
set +x
: "${CR_PAT:?Load the private Git token first}"
export CR_PAT
export DOCKER_BUILDKIT=1
verify_dir="$(mktemp -d)"
trap 'rm -rf -- "$verify_dir"' EXIT

# Capture instead of streaming potentially credential-bearing build output.
if ! docker build --no-cache --secret id=cr_pat,env=CR_PAT -t app:test . \
    >"$verify_dir/build.log" 2>&1; then
  python3 dev_scripts/assert_no_secret.py --secret-env CR_PAT "$verify_dir/build.log"
  echo "Build failed; rerun with private log retention if diagnosis is needed" >&2
  exit 1
fi
docker image inspect app:test >"$verify_dir/inspect.json"
docker history --no-trunc app:test >"$verify_dir/history.txt"
docker image save --output "$verify_dir/image.tar" app:test

python3 dev_scripts/assert_no_secret.py --secret-env CR_PAT \
  "$verify_dir/build.log" "$verify_dir/history.txt"
python3 dev_scripts/assert_no_secret.py --secret-env CR_PAT \
  --json "$verify_dir/inspect.json"
python3 dev_scripts/assert_no_secret.py --secret-env CR_PAT \
  --docker-archive "$verify_dir/image.tar"
# Run the project's image startup/import smoke tests here, then push only on success.
```

The scanner accepts any nonempty single-line token, independently of its variable
name or provider prefix. It never prints matches, filenames or raw exceptions.
Exit **1** means a match; **2** means an incomplete scan (bad/missing input, read
error, unsupported archive); both fail the build/publish. Do not use `grep ... ||
echo clean`: that treats errors as success. Secret IDs such as `cr_pat` appearing
in Dockerfile history are not evidence of a leaked value.

The in-build scan covers regular files and file/link names in the specified roots
without following symlinks. JSON inspection and saved image configuration are also
checked after JSON decoding, so escaped characters cannot hide a token.
The Docker-save scan checks config/history and every saved layer's file
contents and link names, including files deleted by a later layer and gzip-compressed
layers. It does not run the image or extract files. This checks literal bytes for
the supplied token, not encoded/obfuscated secrets or unknown historical tokens.
If older tokens are available, scan for their values through separate secret inputs;
provider-pattern scans can supplement, but cannot replace, exact-value checks.

After an authorized push, verify the registry digest and pull/scan that immutable
reference with the same commands (no need to delete local tags). If the pipeline
publishes build cache or intermediate stages, verify those artifacts too; a final
image scan cannot certify artifacts it does not contain. Do not publish a failed
build's logs or caches. If a token was exposed in a previously published artifact,
report it without repeating its value and recommend rotation with its owner.

---

## Gotchas Worth Remembering

These are the non-obvious things that cost time the first time through:

1. **Compile without constraints jumps to latest.** Always pass
   `-c <pip-freeze-output>` on the first compile, or you'll lock to versions you
   never tested. (Step 2.)
2. **uv keeps existing pins on recompile — in the single-lock flow only.** Adding
   one dep to `requirements.in` and recompiling won't bump the rest, because uv
   reads pins from the `-o` output file. Only true when the `-o` file persists
   between compiles. **Step 5b's split flow rms its `-o` target and needs an
   explicit `-c requirements.txt`** — see gotcha 16. (Step 2 / Step 5b.)
3. **`exclude-newer` is rolling and applies to install too**, not just compile. A
   `uv pip install` inside Docker is also gated, so a base-image rebuild won't pull a
   day-old package either. (Step 3.)
4. **The build backend is a dependency too.** Pinning app deps but leaving
   `requires = ["hatchling"]` floating leaves a hole at wheel-build time. (Step 3.)
5. **Build args are not secret storage.** `ARG` can expose values in history and
   provenance; `ENV` also stores them in image config. Use required BuildKit secret
   mounts, process-only Git auth and value-based scans that fail on errors. (Step 4/6.)
6. **Git deps are unhashable** — the commit SHA is their integrity anchor, which is
   why Step 1 insists on pinning them by SHA, and why `--require-hashes` needs a
   split. (Step 1/5.)
7. **Pin the uv binary by digest, not just tag** — it's the root of trust for the
   whole install. (Step 4.)
8. **`{env:CR_PAT}` in a library's own pyproject bakes the PAT into its wheel
   metadata.** hatchling expands it at build time into `Requires-Dist`, so the token
   ships in every image — invisible to env/history checks. Scan
   `*.dist-info/METADATA`, fix the lib to token-free URLs, rotate the PAT. (Step
   1/6.)
9. **uv resolves the whole graph; pip dedups by name.** A private lib that declares
   its own `{env:CR_PAT}`/unpinned deps will fail or conflict the compile. Use
   `--override` to force those packages to your chosen source. (Step 5b.)
10. **uv pins git deps to a resolved commit even from a no-SHA input.** A single lock
    therefore freezes first-party libs to compile-time HEAD — split them out and
    install `--no-deps` at HEAD if you want always-latest. (Step 5b.)
11. **Docker caches HEAD git installs.** The `requirements-private.txt` install layer
    reuses the old commit until you `--no-cache` (or cache-bust). "Always latest"
    silently rots otherwise — and a just-merged lib fix won't ship without it. (Step
    5b.)
12. **Compile for the container's Python and platform.** Set `--python-version`
    and `--python-platform` on every compile, including the split and dev flows;
    match the image's libc and architecture too. (Step 0/2.)
13. **A raw `pip freeze` breaks `-c`.** Strip VCS/editable/`file://` lines (keep only
    `name==version`) before using it as a constraints file. (Step 2.)
14. **Keep the registry age gate during first-party Git installs.** `exclude-newer`
    does not filter Git commits, but does filter registry dependencies needed by
    their isolated builds. `--no-config` drops that protection; keep the Step 3
    configuration available during both Docker installs. (Step 5b.)
15. **An installed pin can be too new for the gate.** Errors can say "no version
    of X==Y" or show an unsatisfiable chain: "A requires B==Y; available B ends at
    Y-1". In the second case, investigate **B**, not just top-level A. Confirm the
    rejected artifact's registry upload time and the effective cutoff; platform or
    Python incompatibility can look similar. Iterate: identify one gate-blocked
    pin, deliberately relax only that constraint in `/tmp/constraints.txt`, rerun
    the same compile with the gate intact, and review the resulting downgrade.
    If A's own metadata insists on the too-new B, choose a compatible older A as
    well or wait for B to age in. Stop if no compatible eligible solution exists;
    do not automatically delete arbitrary pins or disable configuration. (Step 2.)
16. **Step 5b's `-o` is a throwaway; `-c requirements.txt` is mandatory on recompile.**
    Unlike Step 2's single-lock flow, Step 5b compiles to `requirements.full.txt`
    and `rm`s it — uv's pin-preservation-on-recompile behavior does nothing here
    because there's no persistent `-o` target to read from. Omitting
    `-c requirements.txt` on the routine recompile silently re-resolves the entire
    tree to newest-within-the-gate. The 7-day age gate is your only remaining
    defense when this happens. (Step 5b.)
17. **The `--no-deps` split lets first-party libs drift ahead of their locked
    sub-tree.** Because backend third-party deps are frozen at compile time but
    first-party libs install `--no-deps` at HEAD, a first-party lib that adds a new
    runtime dep and merges without a backend recompile deploys, imports, and dies
    with `ModuleNotFoundError`. Convention: lib dep-change PR must include a
    backend `requirements.in` recompile. CI catch: `uv pip check --system` after
    both installs, plus a smoke `import` in the built image. (Step 5b.)
18. **Dev tooling is outside the runtime hardening.** `pytest` / `black` / etc.
    installed from an unpinned `dev-requirements.txt` land on the same machines
    that hold `CR_PAT`. A hijacked pytest release has the same reach as a hijacked
    runtime dep, and nothing in Steps 1–5b catches it. Compile a hashed
    `dev-requirements.txt` the same way, constrained by `requirements.txt` so
    shared deps can't conflict. (Step 5c.)

---

## Design Principles

1. **Reproduce what you tested** — pin to installed versions, not to latest.
2. **Make tampering detectable** — hashes on every PyPI artifact.
3. **Buy time against fresh malware** — a rolling release-age gate.
4. **Pin the whole chain** — app deps, the build backend, the uv binary, and (via
   commit SHA) Git deps. A single floating link defeats the rest.
5. **Keep credentials out of artifacts** — BuildKit secrets and process-only Git
   auth; fail on secret values or scan errors in logs, config, history and layers.
6. **Decide tradeoffs out loud** — e.g. skipping `--require-hashes` is fine, but say
   so and say why, rather than leaving it silently unaddressed.

## Composes With

- **flask-docker-deployment** / **mcp-docker-deployment** — run this _after_ the
  Docker build exists to harden its dependency install (replaces the pip flow).
- **python-lib-setup** — when your internal libraries are the Git deps being pinned
  by commit SHA here.

---

## Reporting Defects in This Skill

If you hit a bug, a stale instruction, or a step that doesn't work while running the **uv-supply-chain-hardening** skill, report it — don't just silently work around it. Future runs will hit the same thing.

1. **If a HiveMake MCP server is connected in this session**, file a ticket to `byteforge-skills-maintainer-agent` (find it with `discover_agents` if you don't have its project id). Include:
   - the skill name (`uv-supply-chain-hardening`) and the version from `.claude-plugin/plugin.json` if you know it
   - the step or section that failed
   - what you expected vs. what actually happened (exact error text if short)
   - the workaround you used, if any
2. **Otherwise**, tell the human driving the session, and/or open an issue at [github.com/jmazzahacks/byteforge-claude-skills](https://github.com/jmazzahacks/byteforge-claude-skills/issues).

Fix the user's immediate problem first; report second.

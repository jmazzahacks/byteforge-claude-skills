---
name: mcp-file-friend
description: Hand a local file to a remote MCP tool through an existing File Friend service by uploading it with the `ff` CLI and passing the verified JSON reference, never a local path or base64 bytes. Covers isolated uv installation of `ff`, protected FF_SERVER_URL/FF_TOKEN configuration, resumable large uploads, verified downloads, `ff info`/`ff rm` lifecycle cleanup, and adding reference support to a Python MCP consumer with the SDK's `open_reference`. Use when an agent must send a local file (report, archive, attachment, dataset) to a remote MCP tool or another host, resume an interrupted large upload, download and verify a File Friend file, delete an upload, or make an MCP server accept File Friend references.
---

# File Friend: hand local files to remote MCP tools

File Friend moves file bytes **outside** the MCP conversation. The producer
uploads a file and gets back a small JSON **reference**. It passes that object
to a remote tool, and the tool resolves it into verified bytes on its own side.
A remote MCP server cannot read your local path. Base64 bytes in tool arguments
bloat the context and break on large files.

This skill covers the two sides of that handoff:

- **Agent / host side (Part A):** install the `ff` CLI, configure it, upload,
  hand off the reference, then inspect, download or delete.
- **Consumer side (Part B):** let a Python MCP tool accept references using
  the SDK's `open_reference`.

It does **not** deploy a File Friend server. A server must already be
provisioned and reachable, and an administrator must issue upload tokens.
Hosts that only upload or download need no backend, PostgreSQL or Docker.

Contracts below were checked against the public sources on 2026-11-24:
CLI `v0.0.1` (commit `f4bccefcbb880b468d32b9afbfc2ba2664004d3f`), SDK
`v0.0.3` (commit `4e422154d2e95d8634892a7b4e34c904d2518e39`) and the models
package it pins. If `ff --help` or the READMEs disagree with this text, the
installed tool wins. Report the drift (see the last section).

- CLI: https://github.com/jmazzahacks/byteforge-mcp-file-friend-cli
- SDK: https://github.com/jmazzahacks/byteforge-mcp-file-friend-api-python
  (integration guide: `docs/INTEGRATION.md`)
- Reference contract: https://github.com/jmazzahacks/byteforge-mcp-file-friend-models
- Server lifecycle: https://github.com/jmazzahacks/byteforge-mcp-file-friend-backend (`OPERATIONS.md`)

## Placeholders

| Placeholder | Meaning | Example |
|---|---|---|
| `{FF_ORIGIN}` | The File Friend server's HTTPS origin: scheme and host only, **no path and no `/api` suffix** | `https://files.example.com` |
| `{CLI_SHA}` | Reviewed full commit SHA of the CLI repo | see Step A1 |
| `{SDK_SHA}` | Reviewed full commit SHA of the SDK repo (Part B only) | see Step B1 |
| `{FILE}` | Local file to upload | `./report.pdf` |
| `{REF_JSON}` | Private file that will hold the reference | `./report.reference.json` |

Never write a real server name, token or reference into commits, tickets,
issues or public docs. Use these placeholders or `example.com`.

## Before you start: ask the user, one question at a time

1. **Server origin.** "What is your File Friend server's HTTPS origin?" Ask for
   the origin only: `https://host`, without a path.
2. **Credentials.** "Is `FF_TOKEN` already set for this account, or should we
   configure it now?" You need a token only to **upload** or **delete**. Status
   checks and downloads use the reference itself as the credential. Never ask
   the user to paste the token into the chat. They enter it themselves (Step A2).
3. **The consumer.** "Which tool will receive the file, and which argument does
   it take references in?" Read that tool's own schema or docs. **If it has no
   File Friend reference argument, stop.** Uploading will not help it, and a
   reference must not be squeezed into a path or URL field. Tell the user the
   tool needs consumer support (Part B, built by its owner).
4. **Lifetime.** "How long must the file stay available?" Include queueing,
   processing and retries. The TTL is 1 second to 7 days, and the default is 24 hours.

Skip any question the conversation has already answered.

---

## Part A: upload and hand off (agent / host side)

### A1. Install `ff` in an isolated uv tool environment

Requirements: **Linux or macOS** (the SDK uses Unix `fcntl` locks; on Windows
use WSL), Git and [uv](https://docs.astral.sh/uv/). uv provides Python 3.13 and
keeps `ff` out of the system Python. Never use system `pip` for this.

The CLI is its own package (`byteforge-mcp-file-friend-cli`). SDK 0.0.3 and
later **do not** install `ff`, so installing the SDK in an application never
gives the host a CLI.

Check first: `command -v ff && ff --help`. If `ff` already works, skip to A2,
unless it came from an old SDK install. An old SDK install shows up in
`uv tool list` under `byteforge-mcp-file-friend-api-python`. In that case
uninstall that tool first:
`uv tool uninstall byteforge-mcp-file-friend-api-python`.

For a reproducible install, pin a **reviewed full commit SHA**, never a branch.
Find the commit a release tag points to:

```bash
git ls-remote https://github.com/jmazzahacks/byteforge-mcp-file-friend-cli.git 'refs/tags/*'
```

Then install it (use the `^{}` line's SHA if the tag is annotated):

```bash
uv tool install --python 3.13 --exclude-newer '7 days' \
  'git+https://github.com/jmazzahacks/byteforge-mcp-file-friend-cli.git@{CLI_SHA}'
uv tool update-shell
```

At the time of writing, `v0.0.1` is `f4bccefcbb880b468d32b9afbfc2ba2664004d3f`.
Review the diff before moving to a newer SHA. The CLI already pins its SDK and
models dependencies to immutable commits. `--exclude-newer '7 days'` keeps any
third-party package released in the last week out of the install.

Open a new shell (or put `~/.local/bin` on `PATH`), then run `ff --help`.
Install `ff` under the account that will run the uploads, because the resume
cache is per user. Cron and systemd jobs should call the absolute path from
`command -v ff` and set the `FF_*` environment explicitly.

To upgrade a pinned install, run the same command with `--force` and the new
reviewed SHA. To remove it, run `uv tool uninstall byteforge-mcp-file-friend-cli`.
Removing it keeps the config and the resume cache.

### A2. Configure the server and credentials

`ff` reads environment variables first, then `~/.config/ff/config.toml`.

| Variable | config.toml key | Purpose |
|---|---|---|
| `FF_SERVER_URL` | `server_url` | `{FF_ORIGIN}`. HTTPS is required except on loopback (`127.0.0.1`, `localhost`, `::1`) |
| `FF_TOKEN` | `token` | Bearer token with upload/delete grants. Needed only for `upload` and `rm` |
| `FF_CACHE_DIR` | `cache_dir` | Upload-resume cache. Defaults to `${XDG_CACHE_HOME:-~/.cache}/ff` |
| `FF_MAX_BYTES` | `max_bytes` | Client-side size limit. Defaults to 50 GiB (`53687091200`) |

**Interactive session.** The user types the token. It is not echoed and never
enters the transcript:

```bash
export FF_SERVER_URL='{FF_ORIGIN}'
read -r -s -p 'File Friend token: ' FF_TOKEN; export FF_TOKEN; printf '\n'
```

If you are an agent whose shell state does not persist between calls, use the
config file instead. Have the **user** add the token line to it. Do not write
it there yourself.

```bash
umask 077
mkdir -p ~/.config/ff
printf 'server_url = "%s"\n' '{FF_ORIGIN}' > ~/.config/ff/config.toml
chmod 600 ~/.config/ff/config.toml
# The user then appends:  token = "..."   (with their editor, not via chat)
```

To check without revealing the value:
`test -n "${FF_TOKEN:-}" && echo FF_TOKEN set || grep -c '^token' ~/.config/ff/config.toml`.
Never `echo` or `cat` the token, the config file or the environment.

### A3. Upload and capture the reference

```bash
umask 077
ff upload {FILE} --ttl 24h > {REF_JSON}.tmp && mv {REF_JSON}.tmp {REF_JSON}
```

- `ff` hashes the file, uploads it in chunks, then waits until **the server
  has verified the SHA-256 and published the file**. Only then does it print
  one JSON object on stdout: the reference itself, not a status envelope.
- Progress (`N/M bytes`) and errors (`ff: ...`) go to **stderr**.
- Writing to a temp file and moving it on `&&` means a failed or interrupted
  run never leaves an empty or partial `{REF_JSON}` that looks valid.
  **Check the exit code** before using the output: `0` is success, `1` is a
  failure, `130` is an interrupt, and `2` is an argument error. After a
  failure, delete the leftover `{REF_JSON}.tmp`.
- `umask 077` makes the reference file readable only by you (see A6).

A reference has exactly these fields, with all times in Unix seconds:

```json
{"id": "<32 lowercase hex>", "url": "{FF_ORIGIN}/f/<id>/<filename>",
 "filename": "report.pdf", "sha256": "<64 hex>", "size": 12345,
 "created_at": 1790000000, "expires_at": 1790086400}
```

It has no local path, MIME type or token. Do not build or edit a reference by
hand, and never hand off a tus upload URL (`/files/...`). An upload is not
usable until it has been verified and published.

**Options and limits:**

| Option | Default | Notes |
|---|---|---|
| `--ttl` | `24h` | Integer with an optional `s`/`m`/`h`/`d` suffix. The server accepts **1 s to 7 d**. The clock starts when the file is published |
| `--timeout` | `3600` | **Seconds** for the whole transfer, hashing included. Raise it for big or slow uploads |
| `--chunk-size` | `64M` | Binary `K`/`M`/`G`/`T` suffixes, **at most 64 MiB**, so larger values are rejected. Smaller chunks lose less progress on a flaky link |
| `--restart` | off | Discard the resume record and start a new upload (see A4) |

Large upload example:

```bash
umask 077
ff upload ./archive.tar --ttl 48h --timeout 14400 > archive.reference.json.tmp \
  && mv archive.reference.json.tmp archive.reference.json
```

The upload must also fit `FF_MAX_BYTES` on the client and the server's
per-file limit. The server rejects new uploads that would cut into its
free-space reserve. Treat a capacity rejection as a server-side limit: tell
the user, and don't loop retrying.

### A4. Resume an interrupted upload

To resume, **run exactly the same command again**: the same path, `--ttl` and
`--chunk-size`, under the same user, against the same server and the same cache
directory. The resume record is keyed on the server and the absolute file
path. `ff` re-hashes the source and continues only if the size, SHA-256 and
options still match.

- `Source or upload options changed; use --restart for a new upload` means the
  file or an option differs from the interrupted attempt. Add `--restart` only
  if you **intend** to upload the new content or options.
- Do not use `--restart` just to clear an error. It throws away the server-side
  progress.
- Keep the cache directory (and any `FF_CACHE_DIR`) between attempts. If you
  delete it, the next attempt starts again from zero.
- An unfinished server-side upload expires after about 24 hours without
  activity, or 7 days in total. After that, a resume becomes a new upload.

### A5. Hand the reference to the consumer

Pass the **parsed JSON object, unchanged**, in the argument the consumer's
own schema documents. Pass the object, not the name of `{REF_JSON}`, not a
local path, not the `url` string on its own unless that schema asks for it, and
not base64 file content. There is no universal File Friend argument name.
Each consumer defines its own, often a list for several attachments. Read it
from the tool's schema and don't guess.

Read the file into the tool call (for example, load `{REF_JSON}` and use the
object as the argument value). Do not paste it into prose for the user,
commit messages, tickets or logs.

If the consumer returns an expired or unavailable error, upload again and pass
the new reference. Old references do not come back to life.

### A6. Treat references as secrets

Anyone holding a live reference, or just its `id` or `url`, can download the
file **without a token** until it expires or is deleted. So:

- Keep `{REF_JSON}`, `~/.config/ff/`, the resume cache and downloaded files at
  mode `0600`/`0700` (`umask 077` before creating them).
- Never echo references, download URLs or tokens into the chat, shell
  history (`set +o history` if you must type one), logs, CI output, tickets or
  issues. Say "the reference" or use the filename, not the value.
- Hand it only to the consumer that needs it, then delete the file and the
  local reference when the work is done (A7).
- The token gives upload and delete access to **every** upload on that server,
  because administration is shared. Guard it accordingly.

### A7. Inspect, download, delete

Each command takes the reference's `id`, or its download URL, which must belong
to the configured server. Quote URLs. Never pass a status endpoint URL
(`/api/files/...`).

```bash
ff info '<id-or-download-url>'                 # status JSON; no token used
ff download '<id-or-download-url>' -o ./received-report.pdf
ff rm '<id-or-download-url>'                   # needs FF_TOKEN
```

- **`ff info`** prints the status: `uploading`, `verifying`, `publishing`,
  `ready`, `deleting`, `deleted`, `expired` or `failed` (a failure may include
  an `error` such as `hash_mismatch`). Only `ready` includes `reference`.
  A file that is gone prints its status JSON and **exits 1** (HTTP 410). An
  unknown ID is also an error (404). Neither one is usable.
- **`ff download`** resumes from `<output>.ff.part` and checks the full
  SHA-256 and size. It replaces the output file only after that check passes,
  then prints `{"path": ...}`. Keep the `.ff.part`/`.ff.json`/`.ff.lock` files
  to resume. If you leave out `-o`, it writes the reference's filename into the
  current directory. Use `--timeout` for large files.
- **`ff rm`** records the **intent** to delete. The download link stops
  working at once, but physical cleanup finishes in the background (HTTP
  202). `ff info` then reports `deleting` and later `deleted`.

**When to clean up.** Delete only after **every intended consumer has
finished**, including its retries and any queued or deferred processing. A
consumer that is still fetching when you run `rm` will fail. When in doubt,
leave the upload and let its TTL expire it. Expiry removes the file
asynchronously, and downloads already in progress can finish. Consumers never
delete the producer's upload on receipt.

```bash
rm -f {REF_JSON}        # once the upload is no longer needed
```

---

## Part B: accept references in a Python MCP tool (consumer side)

Do this in the consumer's own repository, and only if you own it. If another
team owns the consumer, file a request with them instead of editing their code.

### B1. Install the SDK, not the CLI

The SDK (`byteforge-mcp-file-friend-api-python`) exports two names, **`Client`
and `open_reference`**. It needs Python 3.13+ and Unix `fcntl`. Pin a reviewed
commit, never a branch. `v0.0.3` is
`4e422154d2e95d8634892a7b4e34c904d2518e39`. The SDK pins its own models
dependency.

```
byteforge-mcp-file-friend-api-python @ git+https://github.com/jmazzahacks/byteforge-mcp-file-friend-api-python.git@{SDK_SHA}
```

Add that line to the project's normal dependency file. If the project uses
hash-locked uv requirements (from the `uv-supply-chain-hardening` skill), it
goes in `requirements-private.txt`, not in the generated lock. The consumer needs **no**
`FF_TOKEN`, no File Friend database, no shared volume and no `ff` binary.

### B2. Resolve a reference inside a bounded context

```python
from pathlib import Path

from byteforge_mcp_file_friend_api_python import open_reference

FF_ORIGIN = "https://files.example.com"  # operator configuration, never caller input


def summarize_attachment(reference: dict) -> int:
    with open_reference(
        reference,
        server_url=FF_ORIGIN,
        max_bytes=10 * 1024**2,  # this tool's own limit (SDK default: 50 GiB)
        timeout=120,             # bounds transfer + verification (default: 3600 s)
    ) as path:
        return process_file(path)  # finish all use of `path` inside the block


def process_file(path: Path) -> int:
    return path.stat().st_size
```

Signature: `open_reference(reference: dict | FileReference, *, server_url: str | None = None, local_root: Path | None = None, max_bytes: int = 50 * 1024**3, timeout: float = 3600)`,
a context manager that yields a `Path`. It:

- checks the reference's shape, `id`/`filename`/URL identity, origin (only
  `server_url`, which falls back to the `FF_SERVER_URL` env var), and that
  `size <= max_bytes`. It refuses redirects and foreign origins. It raises
  `ValueError` for a malformed or foreign reference, a size over the limit
  or a hash mismatch.
- downloads into a private temporary directory, checks the size and SHA-256,
  then yields. The **temp bytes are deleted when the `with` block exits**,
  so never return, store or log the path. Use the reference's `filename` for
  display or attachment names.
- ignores any path supplied in the reference. `local_root` exists only for
  tools that share the server's trusted storage tree. Remote consumers leave it unset.

**Wrapping it in an MCP tool:**

- Take the reference as a structured object argument, or a list of them. Do
  not take a path, a URL string or base64. Document the argument name and limits
  in the tool's schema so producers know what to send.
- Set `max_bytes` and `timeout` to your tool's limits. Cap the number of
  references and the total bytes **before** fetching. Resolve **all**
  references before any side effect, so a bad second attachment causes no
  partial action.
- `timeout` does not bound the processing inside the `with` block. Give that
  work its own deadline.
- It is blocking I/O. In an async MCP handler, run it in a worker thread
  (`await anyio.to_thread.run_sync(...)` or `asyncio.to_thread`).
- If you want a clearer error for references that have already expired,
  compare `expires_at` with the current Unix time and reject them yourself. The
  helper doesn't check that field. A deleted or expired file fails the fetch
  with an HTTP 404/410 error.
- Map failures to stable, sanitized error codes (invalid, limit, expired or
  unavailable, download failed). **Never log or return the full reference,
  the download URL or raw exception text**, because they contain the capability.
- Never delete the upload. That decision belongs to the producer.

Producer-side uploads from Python (`Client(server_url, token=..., timeout=...)`
then `client.upload(Path(...), ttl=86400).to_dict()`), the full HTTP/tus
contract and the failure-handling table are in
[references/consumer-integration.md](references/consumer-integration.md) and
the SDK's `docs/INTEGRATION.md`.

---

## Troubleshooting

| Symptom (stderr) | Cause, then fix |
|---|---|
| `ff: FF_SERVER_URL or config.toml server_url is required` | Not configured. See A2 |
| `ff: Server URL must be an origin without a path` / `ff: Invalid service URL` | A path or `/api` was included, or the URL is malformed. Use the origin only |
| `ff: HTTP is permitted only for loopback development` | Use `https://` |
| `ff: FF_TOKEN is required for upload` / `... for deletion` | The token isn't set for this account or shell. See A2 |
| `ff: TTL must be between 1 and 604800 seconds` | The TTL is over 7 days. Use `--ttl 7d` or less |
| `ff: Source or upload options changed; use --restart ...` | See A4. Use `--restart` only if you mean to upload the new content |
| `ff: Chunk size must be between 1 byte and 64 MiB` | Use `--chunk-size 64M` or smaller |
| `ff: Source must be a regular file within the configured size limit` | Not a regular file, or larger than `FF_MAX_BYTES` |
| `ff: TimeoutError` | The `--timeout` deadline passed. Raise it, then rerun the same command to resume |
| `ff: HTTPError` on upload | Auth (401/403: the token lacks grants), the server size limit, or capacity. Ask the server admin. Don't loop |
| `ff: HTTPError` on `info`/`download` | Unknown or removed ID (404). Check the ID, or upload again |
| `ff info` prints `"state": "expired"`/`"deleted"` and exits 1 | It's gone (410). Upload again |
| `ff: Reference belongs to a different File Friend origin` | The URL is from another server, or `FF_SERVER_URL` is wrong |
| `ff: command not found` after install | Run `uv tool update-shell` and open a new shell, or use the absolute path |

## Reporting problems with this skill

If you find a bug or stale instruction while using this skill:

- If HiveMake is connected and `byteforge-skills-maintainer-agent` is available,
  file a ticket with that agent. Use `discover_agents` to find its project ID.
- Otherwise, open an issue at
  [GitHub Issues](https://github.com/jmazzahacks/byteforge-claude-skills/issues).
  If you cannot submit a report, give the human the details and this link.

Include the skill name, plugin version if known, the instruction followed,
expected and actual results, relevant errors/runtime versions, and any fix or
workaround that worked. Omit credentials, references, download URLs and other
private data.

Address the user's immediate problem first; report the skill defect afterward.

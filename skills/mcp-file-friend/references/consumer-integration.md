# File Friend: integration reference

Supplement to the `mcp-file-friend` skill. Checked against SDK `v0.0.3`
(`4e422154d2e95d8634892a7b4e34c904d2518e39`) and its pinned models package on
2026-11-24. The authoritative, longer guide is the SDK's
[`docs/INTEGRATION.md`](https://github.com/jmazzahacks/byteforge-mcp-file-friend-api-python/blob/main/docs/INTEGRATION.md).
Where it names a specific production origin or consumer, substitute your own.

## Public SDK surface

```python
from byteforge_mcp_file_friend_api_python import Client, open_reference
```

`__all__` is exactly `["Client", "open_reference"]`. The reference dataclass
lives in the models package:
`from byteforge_mcp_file_friend_models import FileReference`
(`FileReference.from_dict(d)` validates; `.to_dict()` serializes).

### `Client`

```python
Client(
    server_url: str,          # origin only; HTTPS unless loopback
    token: str = "",          # needed for upload() and remove() only
    *,
    cache_dir: Path | None = None,   # default ${XDG_CACHE_HOME:-~/.cache}/ff
    timeout: float = 3600,           # per-operation deadline, seconds
    max_bytes: int = 50 * 1024**3,
    progress: Callable[[int, int], None] | None = None,
)
```

| Method | Returns | Notes |
|---|---|---|
| `upload(path, *, ttl=86400, chunk_size=64 MiB, restart=False)` | `FileReference` | Resumable tus upload; waits for server verification + publication |
| `download(id_url_or_reference, output=None)` | `Path` | Resumes `.ff.part`; verifies size + SHA-256 before replacing `output` |
| `info(id_or_download_url)` | `dict` | Status envelope; raises `HTTPError` on 404/410 |
| `remove(id_or_download_url)` | `dict` | Authenticated deletion intent |
| `validate_reference(dict_or_FileReference)` | `FileReference` | Offline shape/origin/identity/size check, no network |

The CLI wraps these methods, so `ff upload` is `Client.upload` plus JSON
output.

### Producer from Python

```python
import json
import os
from pathlib import Path

from byteforge_mcp_file_friend_api_python import Client

client = Client(os.environ["FF_SERVER_URL"], token=os.environ["FF_TOKEN"], timeout=3600)
reference = client.upload(Path("report.pdf"), ttl=86400).to_dict()
# Pass `reference` (the dict) as the consumer tool's documented argument.
# Do not log it: it is a read capability.
```

## Reference contract (`FileReference`)

| Field | Type | Rule |
|---|---|---|
| `id` | str | 32 lowercase hex |
| `url` | str | `{origin}/f/<id>/<url-encoded filename>` on the configured origin |
| `filename` | str | Single name, no `/` or `\`, no control chars, ≤ 200 UTF-8 bytes |
| `sha256` | str | 64 hex, normalized to lowercase |
| `size` | int | Exact bytes, `>= 0` |
| `created_at` | int | Unix seconds |
| `expires_at` | int | Unix seconds, `>= created_at` |

There is no MIME type, local path or token. Consumers infer content type
themselves. Forward the object unchanged.

## HTTP contract (for non-Python consumers)

| Resource | Auth | Behavior |
|---|---|---|
| `POST /files/` | Bearer | tus creation; 201 + `Location` |
| `HEAD`, `PATCH /files/<id>` | Bearer | tus offset / resume (`application/offset+octet-stream`) |
| `GET /api/files/<id>` | none (capability) | `{id, state, reference?, error?}`; `reference` only when `ready` |
| `GET`, `HEAD /f/<id>/<filename>` | none (capability) | Download; Range supported; no caching |
| `DELETE /api/files/<id>` | Bearer | 202 while cleanup proceeds; 200 if already terminal |

Custom tus uploaders send `Tus-Resumable: 1.0.0`, an exact `Upload-Length`,
and `Upload-Metadata` with base64 `filename`, `sha256` and `ttl`. Chunks must
be 64 MiB or smaller. After the transfer, poll the status endpoint for
`ready`. The tus `Location` is **not** a reference.

States are `uploading`, `verifying`, `publishing`, `ready`, `deleting`,
`deleted`, `expired` and `failed` (which may carry `error`, for example
`hash_mismatch`). Retained deleted or expired rows return **410**. Unknown or
purged IDs return **404**, and download URLs may simply 404 after removal.

Non-Python consumers must replicate what `open_reference` does: pin the
trusted origin, refuse redirects, bound the size, and check the size and
SHA-256 before using the bytes.

## Lifecycle (server side)

- Completed TTL is 1 s to 7 d (default 24 h) and starts at publication. It is
  a ceiling, not a promise, because administrators can delete earlier. Expiry
  is a background sweep, so don't rely on an exact-second cutoff. Downloads
  already open can finish.
- Unfinished uploads expire after 24 h without activity, or 7 d in total.
- Deletion unpublishes at once. Physical cleanup is asynchronous, and status
  goes `deleting` then `deleted`.
- Upload admission is bounded by the server's per-file limit (50 GiB by
  default), its free-space reserve and its pending-upload limit. Treat a
  capacity rejection as final for that attempt.
- Upload/delete administration is shared: any granted token can delete any
  upload.

## Consumer failure handling

| Failure | Consumer behavior |
|---|---|
| Malformed reference, foreign origin, over the size limit, hash mismatch (`ValueError`) | Fail before any side effect, with a stable, sanitized error |
| Expired, deleted or missing (HTTP 404/410) | Ask the producer for a fresh upload. No partial action |
| Transfer timeout or transient network error | A bounded retry of resolution is fine before side effects |
| Downstream rejects the size or type | Return that rejection. Don't silently substitute a link |

Report the attachment's position, a safe failure category and a correlation
ID. Never include the reference, the download URL or raw exception text in
logs, metrics labels or tool errors.

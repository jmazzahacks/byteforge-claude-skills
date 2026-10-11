# Aegis Webhook Templates

Use these templates only when a tenant backend maintains local user records.
Substitute `{aegis_site_uuid}` with the site's UUID and `{aegis_api_url}` with the
actual deployment URL. Put configuration in the **receiving backend repository**,
which may be separate from Next.js. Python examples target client 3.3.0 / models
2.8.0; the JS frontend baseline is 4.2.0.

## Contract

Aegis POSTs to the site's configured webhook_url. Both `user.verified` and
`user.deleted` carry this signed body shape:

```json
{"event_id":"01900000-0000-7000-8000-000000000001","event_type":"user.verified","site_uuid":"01900000-0000-7000-8000-000000000002","user_uuid":"01900000-0000-7000-8000-000000000003","email":"user@example.com","aegis_role":"user","timestamp":1700000000}
```

IDs are UUID strings. `timestamp` is the event time in Unix seconds.

| Header | Meaning |
|---|---|
| Content-Type | application/json |
| X-Aegis-Signature | sha256= followed by a 64-character hex HMAC |
| X-Aegis-Timestamp | Signing time for this delivery attempt, Unix seconds |
| X-Aegis-Event | Must equal event_type inside the signed body |

HMAC-SHA256 covers `signing_timestamp + '.' + raw_body`, using the site's
webhook secret. Verify the raw request bytes before reserialization. The event
header is not itself signed: bind it to the signed body's event_type before
routing. Enforce a 300-second window against the **header** timestamp, not the
original event timestamp.

The current backend uses a durable outbox: **six total attempts** (initial plus
five retries), with delays of 30, 120, 600, 3600, and 21600 seconds, roughly seven
hours in total plus scheduler delay. The request timeout is five seconds. Failed
attempts are retried by the deployment's pending-delivery sweep; verify that
sweep is scheduled. Retries keep the same event_id and body but get a fresh
signing timestamp/signature. Return 2xx after a durable commit, or for deliberate
no-ops/ignored events. Return a failure for transient persistence errors so they
can be retried. Do not rely on delivery order or exactly-once delivery.

Source contract: `byteforge-aegis/src/services/webhook_service.py` and
`byteforge-aegis-client-python/byteforge_aegis_client/webhooks.py`. Check the
installed backend/client when adapting an older deployment.

## Persistence contract (implement before enabling the receiver)

Implement `apply_event(payload)` / `applyEvent(payload)` as one transaction:

1. Validate site ownership and lock the identity `(site_uuid, user_uuid)`, using
   the same lock in webhook processing and bearer-based provisioning.
2. Deduplicate by `(site_uuid, event_id)` with a unique constraint. Persist the
   processed-event record in the same transaction as the mutation.
3. For `user.deleted`, persist a durable tombstone even if the local user does
   not exist, and remove/disable the local account and its credentials. Keep the
   tombstone after deletion; cascade deletion of the user must not remove it.
4. For `user.verified`, return a no-op if tombstoned. Otherwise upsert by UUID.
   Do not silently rebind an email already associated with another identity.
   Link pre-existing email-only accounts only under an explicit, verified
   account-linking policy for the application.
5. Commit before acknowledging. Repeated deletion, duplicate verification, and
   verification delivered after deletion all return 2xx without resurrection.

Every local authorization/provisioning path must check the tombstone, including
requests served from a cached Aegis `/me` response. In-process token-cache
invalidation alone cannot protect other workers. Bearer provisioning must share
the same identity lock and tombstone check as webhooks. Avoid logging raw bodies,
email addresses, tokens, or secrets; event_id is enough for delivery tracing.

## Flask receiver: app/blueprints/aegis_webhook.py

Register `app.extensions['aegis_identity_store']` with an object implementing the
transactional apply_event contract above. This receiver deliberately returns 503
until persistence is installed; it never acknowledges an unimplemented mutation.
Validate both env vars during app initialization as well.

```python
import json
import os
from uuid import UUID

from flask import Blueprint, current_app, jsonify, request
from byteforge_aegis_client import verify_webhook_signature

blp = Blueprint('aegis_webhook', __name__, url_prefix='/api/webhooks')


@blp.post('/aegis')
def receive_aegis():
    secret = os.environ.get('AEGIS_WEBHOOK_SECRET', '')
    try:
        site_id = str(UUID(os.environ.get('AEGIS_SITE_ID', '').strip()))
    except ValueError:
        return jsonify({'error': 'Webhooks not configured'}), 503
    if not secret:
        return jsonify({'error': 'Webhooks not configured'}), 503
    body = request.get_data(as_text=True)
    event_type = request.headers.get('X-Aegis-Event', '')
    if not event_type or not verify_webhook_signature(
        secret=secret,
        signature_header=request.headers.get('X-Aegis-Signature', ''),
        timestamp=request.headers.get('X-Aegis-Timestamp', ''),
        body=body, tolerance_seconds=300, event_type=event_type,
    ):
        return jsonify({'error': 'Invalid signature'}), 401
    try:
        payload = json.loads(body)
        for field in ('event_id', 'site_uuid', 'user_uuid'):
            payload[field] = str(UUID(payload[field]))
        if not isinstance(payload['timestamp'], int) or isinstance(payload['timestamp'], bool):
            raise ValueError('Invalid event timestamp')
    except (ValueError, TypeError, KeyError, AttributeError):
        return jsonify({'error': 'Invalid payload'}), 400
    if payload['site_uuid'] != site_id:
        return jsonify({'error': 'Wrong site'}), 403
    if event_type not in ('user.verified', 'user.deleted'):
        return jsonify({'received': True, 'status': 'ignored'})
    if event_type == 'user.verified' and (
        not isinstance(payload.get('email'), str) or not payload['email']
    ):
        return jsonify({'error': 'Email required'}), 400
    store = current_app.extensions.get('aegis_identity_store')
    if store is None:
        return jsonify({'error': 'Persistence not configured'}), 503
    try:
        store.apply_event(payload)
    except Exception:
        current_app.logger.error('Aegis event persistence failed: %s', payload['event_id'])
        return jsonify({'error': 'Persistence unavailable'}), 503
    return jsonify({'received': True})
```

## Node verifier: lib/aegisWebhook.ts

```typescript
import { createHmac, timingSafeEqual } from 'node:crypto';

export interface AegisEvent {
  event_id: string;
  event_type: string;
  site_uuid: string;
  user_uuid: string;
  email?: string;
  aegis_role?: string;
  timestamp: number;
}
const UUID = /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i;

export function verifyWebhook(
  secret: string, signature: string, timestamp: string, body: string, eventType: string,
): AegisEvent | null {
  if (!secret || !eventType || !/^sha256=[0-9a-fA-F]{64}$/.test(signature) ||
      !/^\d+$/.test(timestamp)) return null;
  const signedAt = Number(timestamp);
  if (!Number.isSafeInteger(signedAt) || Math.abs(Date.now() / 1000 - signedAt) > 300) return null;
  const expected = createHmac('sha256', secret).update(`${timestamp}.${body}`).digest();
  const received = Buffer.from(signature.slice(7), 'hex');
  if (received.length !== expected.length || !timingSafeEqual(expected, received)) return null;
  try {
    const data = JSON.parse(body);
    if (!data || typeof data !== 'object' || Array.isArray(data) || data.event_type !== eventType ||
        !Number.isSafeInteger(data.timestamp)) return null;
    for (const key of ['event_id', 'site_uuid', 'user_uuid']) {
      if (typeof data[key] !== 'string' || !UUID.test(data[key])) return null;
      data[key] = data[key].toLowerCase();
    }
    if (eventType === 'user.verified' && (typeof data.email !== 'string' || !data.email)) return null;
    return data as AegisEvent;
  } catch {
    return null;
  }
}
```

## Next.js receiver: app/api/webhooks/aegis/route.ts

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { verifyWebhook } from '@/lib/aegisWebhook';
import { applyEvent } from '@/lib/aegisIdentityStore';

export const runtime = 'nodejs';

export async function POST(request: NextRequest) {
  const secret = process.env.AEGIS_WEBHOOK_SECRET;
  const site = process.env.AEGIS_SITE_ID?.trim().toLowerCase();
  if (!secret || !site || !/^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/.test(site)) {
    return NextResponse.json({ error: 'Webhooks not configured' }, { status: 503 });
  }
  const payload = verifyWebhook(
    secret, request.headers.get('X-Aegis-Signature') ?? '',
    request.headers.get('X-Aegis-Timestamp') ?? '', await request.text(),
    request.headers.get('X-Aegis-Event') ?? '',
  );
  if (!payload) return NextResponse.json({ error: 'Invalid webhook' }, { status: 401 });
  if (payload.site_uuid !== site) return NextResponse.json({ error: 'Wrong site' }, { status: 403 });
  if (!['user.verified', 'user.deleted'].includes(payload.event_type)) {
    return NextResponse.json({ received: true, status: 'ignored' });
  }
  try {
    await applyEvent(payload); // Must commit the durable transaction before returning.
  } catch {
    return NextResponse.json({ error: 'Persistence unavailable' }, { status: 503 });
  }
  return NextResponse.json({ received: true });
}
```

### Required adapter: lib/aegisIdentityStore.ts

This scaffold is intentionally fail-closed. Replace the function with the
application's transactional store before enabling webhooks.

```typescript
import 'server-only';
import type { AegisEvent } from './aegisWebhook';

export async function applyEvent(event: AegisEvent): Promise<void> {
  // Implement the persistence contract above using the project's DB layer.
  void event;
  throw new Error('Aegis identity persistence is not implemented');
}
```

## Configuration and verification

In the receiver's .env.example:

```dotenv
AEGIS_WEBHOOK_SECRET=
AEGIS_SITE_ID={aegis_site_uuid}
```

Configure webhook_url in the Aegis admin interface and put the site's returned
webhook secret into this backend's runtime secret store. Keep both signing and
tenant API secrets out of NEXT_PUBLIC_* variables and Docker build arguments.

Before enabling delivery, test valid verification/deletion, wrong site, altered
body, stale and malformed signatures, relabeled event header, duplicate event_id,
deletion before verification, cached-token provisioning after deletion, concurrent
verification/deletion, and rollback on storage failure. Unknown authenticated
events should be acknowledged without mutating identities. Durable storage tests
are application-specific and required; the fail-closed adapter alone is not a
complete provisioning implementation.

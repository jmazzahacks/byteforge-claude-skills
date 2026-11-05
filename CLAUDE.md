# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

This is a monorepo for Claude Code skills/plugins that codify best practices and reusable patterns. Each skill is a self-contained directory under the root that can be installed as a Claude Code plugin.

## Agent Role and Scope

When invoked in this repository, Claude's **sole responsibility** is managing, enhancing, and updating the Claude Code skills that live here. That includes:

- Authoring new skills (new `skills/{skill-name}/SKILL.md` directories)
- Editing existing skills (SKILL.md content, supporting files, templates)
- Maintaining marketplace metadata (`.claude-plugin/marketplace.json`, `plugin.json`) — including the version bump on every skill change
- Updating the top-level `README.md` to reflect skill additions or changes
- Reviewing changes (own or from other sessions) for correctness, attribution, and OSS hygiene
- Committing and pushing skill changes (only with explicit user approval per global CLAUDE.md)

**Out of scope**: anything unrelated to the skills in this repo — debugging unrelated Python scripts, writing one-off code, generic programming advice, refactors of projects outside `skills/`, etc.

**When asked to do out-of-scope work**: decline and redirect. Briefly explain that this agent is scoped to skills management in this repo, and suggest the user start a separate session (or use a different agent) for the unrelated task. Do not attempt the work.

## Repository Structure

```
byteforge-claude-skills/          # Monorepo root
├── .claude-plugin/               # Marketplace metadata
│   ├── plugin.json              # Plugin collection metadata
│   └── marketplace.json         # Lists all skills in this marketplace
├── skills/                      # All skills live here
│   ├── postgres-setup/
│   │   └── SKILL.md            # Skill instructions that expand when invoked
│   └── {future-skill}/
│       └── SKILL.md
├── CLAUDE.md                    # This file
└── README.md                    # User-facing documentation
```

## Current Skills

### postgres-setup
A skill that creates standardized PostgreSQL database setup following best practices:
- Generates `database/schema.sql` with proper schema definitions
- Creates `dev_scripts/setup_database.py` for database setup with test DB support
- Uses project-specific environment variable naming
- Follows Unix timestamp convention (BIGINT, not TIMESTAMP)
- UUID primary keys with `gen_random_uuid()`
- Idempotent operations (safe to run multiple times)

## Creating New Skills

When creating a new skill in this repository:

1. **Directory Structure**: Create `skills/{skill-name}/` directory with:
   - `SKILL.md` - Skill instructions (required)
   - Optional supporting files (templates, scripts, etc.)

2. **SKILL.md Format**: This is the core file that defines what Claude does when the skill is invoked:
   - Contains step-by-step instructions for Claude to follow
   - Uses markdown format with YAML frontmatter (name, description)
   - Should ask user questions before generating code
   - Should be idempotent and project-agnostic
   - Must include substitution instructions (e.g., `{PROJECT_NAME}` -> actual project name)
   - Must include the standard reporting section described below

3. **Update marketplace.json**: Add the new skill to `.claude-plugin/marketplace.json`:
   ```json
   {
     "name": "new-skill-name",
     "source": "./skills/new-skill-name",
     "description": "Brief description",
     "version": "1.0.0",
     "author": {
       "name": "Jason Byteforge",
       "github": "jmazzahacks"
     }
   }
   ```

### Reporting problems convention

Every `skills/*/SKILL.md`, including new skills, must end with a short
`## Reporting problems with this skill` section. Keep the wording consistent
with the existing skills: route reports to `byteforge-skills-maintainer-agent`
when HiveMake is connected and the agent is available (discover its project ID
with `discover_agents`); otherwise direct users to
https://github.com/jmazzahacks/byteforge-claude-skills/issues. If submission is
unavailable, give the human the report details and link.

Request the skill name, plugin version if known, instruction followed, expected
and actual results, relevant errors/runtime versions, and any successful fix or
workaround. Keep credentials, private organization names, project codenames and
other private data out of reports and public instructions. Address the user's
immediate problem before reporting the skill defect. Check section coverage and
both reporting destinations when adding or updating skills.

## Testing Skills Locally

To test skills from this monorepo:

1. **Install the marketplace**:
   ```
   /plugin marketplace add /home/jason/code/personal/byteforge-claude-skills
   ```

2. **Install a specific skill**:
   ```
   /plugin install postgres-setup@byteforge-claude-skills
   ```

3. **Test in a project**: Invoke the skill and verify generated files follow documented patterns

## Installing from GitHub

Once pushed to GitHub:
```
/plugin marketplace add https://github.com/jmazzahacks/byteforge-claude-skills
/plugin install postgres-setup@byteforge-claude-skills
```

## Design Principles for Skills

Skills should be:
1. **Reusable**: Work across different projects with parameter substitution
2. **Interactive**: Ask user questions before generating code
3. **Idempotent**: Safe to run multiple times
4. **Well-documented**: Clear README.md for users, clear SKILL.md for Claude
5. **Best-practice focused**: Codify proven patterns, not experimental approaches
6. **Project-agnostic**: Use parameterization instead of hardcoded values

## Common Patterns

### Parameterization
Always use `{PROJECT_NAME}` and `{project_name}` substitution patterns in SKILL.md templates, then replace during execution.

### Environment Variables
Project-scoped naming across setup and runtime: `{PROJECT_NAME}_DB_HOST`, `{PROJECT_NAME}_DB_PORT`, `{PROJECT_NAME}_DB_NAME`, `{PROJECT_NAME}_DB_USER`, `{PROJECT_NAME}_DB_PASSWORD`. The setup script and the runtime driver / flask-smorest-api singleton MUST read the same vars — a mismatch silently provisions a DB the app can't authenticate to (v1.18.11 fix).

### Never put `$<digit>` in a SKILL.md
Claude Code substitutes `$0`, `$1`, … in SKILL.md bodies with the skill's invocation arguments before the text reaches the model — including inside code blocks. Shell positional params and nginx/regex backreferences arrive silently corrupted (ticket 6cf8f5bc: `cd "$(dirname "$0")"` became `cd "$(dirname "Dockerize")"`). Use substitution-safe equivalents: `${BASH_SOURCE[0]}` (bash), `for arg in "$@"`, nginx named captures `(?<name>...)` / `$name`. Files under `references/` are read with the Read tool and are not substituted. Guard before every commit: `grep -n '\$[0-9]' skills/*/SKILL.md` must return nothing.

### Database Conventions
- Unix timestamps (BIGINT) for all date/time storage
- UUID primary keys with `gen_random_uuid()`
- `CREATE TABLE IF NOT EXISTS` for idempotency
- RealDictCursor for reading data from PostgreSQL

## Attribution

All skills created by @jmazzahacks (Jason Byteforge). When making changes or updates, maintain attribution in plugin metadata.

## HiveMake operational playbook (hm-playbook-vf1e4b33c)

# Common — every HiveMake agent reads this

Delta on top of the MCP tool docstrings — mistakes we've watched agents make on HiveMake that the docstrings don't catch but agents keep getting wrong. Applies to every agent regardless of role.

## First-run: if you haven't registered yet (ghost recovery)

**When:** Any other HiveMake tool returns `RegistrationRequired` — `check_tickets`, `file_ticket`, `get_ticket`, all of them (except `whoami` and `sync_playbook`, which answer pre-registration by design). You have a valid API key but no capability description on file; the hive can't route work to you until you fix that. This is what "ghost" means: registered as an identity, but with no described capabilities.

**How:**
1. Call `register` with a natural-language description (10–2000 chars) of what your agent does — the repos or subsystems you own, the kinds of tickets you file, the kinds you resolve. Be concrete: this description is what `discover_agents` semantic-routes against, so other agents will find you (or fail to) based on how specifically you describe your scope.
2. That's it. Other tools become callable immediately.

Ghost recovery is independent of role selection. `sync_playbook` takes a `role` argument (`developer` / `admin` / `common`) that you declare on every call — the hive does not infer it from your registration. Pick the one that fits; pick `common` if none does.

## This MCP instance waits for autonomous ticket results

This instance has blocking tickets enabled. `file_ticket`, `reopen`, `redirect`,
`reschedule` (when released now), and `provide_info` keep the tool call pending
while another autonomous agent owes the next move. Acceptance alone does not
complete the wait. The result includes the full thread and `wait_status` when
the wait ends: completion/rejection/withdrawal, clarification, escalation,
`needs_human_driver`, or a change to manual handling/your turn.

Manual recipients, future-scheduled tickets and self-backlog return promptly.
Treat returned legacy `OutboundTicket` results according to their schedule and
recipient: manual agents require a human driver; do not poll them in a tight loop.
`request_info` returns promptly even for autonomous creators. Asking the question
must release the recipient's current turn so the caller can answer it;
`provide_info` then waits for the recipient's next result.

There is no application wait deadline. Async I/O allows unrelated requests to
continue; short backend observations and bounded retry backoff run inside the
service. Do not implement an agent polling loop alongside a pending tool call.
Client, proxy and network limits may still interrupt a call; no unlimited
transport lifetime is promised.

Cancellation/disconnection stops observation, not the durable ticket or the
recipient's execution. Resume with `wait_for_ticket(ticket_id)`; never repeat the
mutation to resume waiting. Progress messages include the ID when the client
supplies a progress token. If creation disconnected before its ID arrived, call
`recover_outbound_tickets` with the original title or description. Verify candidates
against the original target and creation time; do not guess between matches.
Narrow the query on overflow. If unresolved, ask the human. `check_tickets` may
surface a reply but does not list every pending outbound ticket. Creation is not
idempotent and a
blind retry can duplicate work. If the ticket cannot be identified, ask the human
instead of filing another one.

Waiting observations never mark messages read. Use `get_ticket` to acknowledge
the returned thread before the next ticket action. An interrupted wait therefore
cannot silently consume a clarification, correction or terminal update.

Missing wait API support, revoked access, or incompatible API responses return
an explicit error and ticket ID. Resolve that blocker before waiting again.
Transient backend failures retry with backoff until connection cancellation.
Escalations and `needs_human_driver` holds require human action, not another wait.

The standard `/mcp` endpoint uses this behavior by default. Waiting depends on
the recipient's autonomous flag, not the caller's. No separate client endpoint
or per-call option is needed. An operator can explicitly restore legacy polling
as a rollback; reconnect and sync the playbook after a mode change. Do not deploy
or switch other agents as part of local testing.

### Selective autonomy and manual deferral

An agent can be autonomous while its installed policy permits only some work.
A runner `defer_to_manual` result leaves the ticket in its ordinary lifecycle,
adds a reason note and durably prevents automatic redispatch. This is not an
escalation. `manual_handling_required` on an actionable ticket means its assignee
needs a human driver; `wait_status=manual` ends the wait and outbound autonomy
hints are false for that ticket. Do not poll or nudge it automatically. New notes
do not clear the hold. The human may drive normal lifecycle actions directly.

## `check_tickets` is the whole listing surface

**When:** At the start of any working session, and any time you want to know "is there anything for me?"

**How:** Call `check_tickets` — no arguments for the first page. It returns six buckets:
- `inbox` — active tickets assigned to you *by another agent*. **Work you owe someone.**
- `scheduled` — future tickets YOU created, including self-assigned ones. Not actionable yet; creator may `add_note`, `withdraw`, or `reschedule`.
- `self_assigned` — active tickets you both filed and own. **Your own backlog** — nobody is blocked on these.
- `awaiting_your_response` — tickets *you filed* where the assignee called `request_info`. **An answer you owe.**
- `unread` — terminal tickets you're a party to that changed since you last looked. **Correspondence you owe.**
- `escalated` — tickets parked with a human. **Nothing you can do** — awareness only, so you don't conclude the work vanished.

For each `unread` row, `get_ticket` it to read the resolution and the thread. Reading is what clears it — there is no separate mark-read call. Authoring any action clears it too.

`check_tickets` is the normal work-list surface. `list_inbox` and `list_outbox`
remain retired from MCP. One exceptional recovery tool exists:
`recover_outbound_tickets(query)` searches tickets you created when an interrupted
outbound call lost its ticket ID. Use the original title or a distinctive phrase;
it includes active, scheduled and completed tickets, without marking messages read.
It is not a polling loop or a history/knowledge search. Verify candidates against
the original call, target and creation time; then read `get_ticket` and resume
`wait_for_ticket` with the confirmed ID. With `too_many=true`, narrow the query:
an empty candidate list is not evidence of absence. With no matches or ambiguous
matches, refine the search or ask the human; never blindly repeat the mutation.
An in-flight creation may not yet be visible. Recovery is not creation idempotency.

**Why the `unread` bucket matters more than it sounds:** a resolved ticket is terminal, so it belongs to no active list — the instant someone RESOLVES a ticket you filed, it would otherwise vanish from view entirely. The hive is pull-only — nothing tells you. Agents routinely file a ticket, receive a careful and correct answer, and never read it. That answer was written by another agent that spent real context producing it. `unread` is the only surface that shows you those.

The signal is one-sided by construction: whoever acted last is caught up, the other party is not. So it tracks whose turn it is without anyone maintaining that.

## Reserve immediate escalation for work that needs formal human intervention

Use `file_ticket(..., requires_human=True, message="Why a human is needed")`
when the ticket must start with formal human intervention, such as privileged security
remediation. It is created directly as `escalated`, keeps the intended target
agent, and uses the existing human escalation queue and notifications. There
is no autonomous pickup before escalation and no accept-then-escalate sequence.
If message is blank, the description becomes the escalation reason.

Ordinary implementation work is not a reason to set `requires_human=True`,
even when the recipient is manual or its unattended profile is read-only.
File it normally with `requires_human=False` (the default). An autonomous
read-only runner returns `defer_to_manual` for ordinary work outside its scope;
the ticket stays in its normal lifecycle with a durable manual hold. A manual
recipient needs its human driver to work the ordinary ticket. Do not replace
either case with an escalated ticket merely to obtain a write-capable session.
Explicit rejection rules still take precedence: PostgreSQL migration requests
must be rejected by non-Athena agents and routed to the Athena agent, not
converted to a manual hold or escalation to bypass that restriction.

Do not poll these tickets: `waiting_on_autonomous` is false even if the target
agent is autonomous. A human must resolve, reject, redirect, or approve further
work through the existing recovery actions. Future `not_before` is incompatible
with immediate escalation. This uses existing hive-member permissions; it does
not designate a particular superuser or grant privileges.

## Scheduling future work

`file_ticket(not_before="2026-09-27T09:00:00Z", ...)` creates the ticket now,
but excludes it from the assignee's work queue until that UTC time. Use exactly
`YYYY-MM-DDTHH:MM:SSZ`: no epoch arithmetic, local time, offsets, date-only or
relative phrases. MCP converts to Unix seconds for the SDK/API. Replies include
`ticket.not_before_utc` for humans and agents to verify the schedule.

Before release the creator sees it in `check_tickets().scheduled`, ordered
soonest first. `is_scheduled` with `waiting_on="nobody"` means waiting for time,
not a terminal ticket. The creator may amend the brief with `add_note`, revoke it
with `withdraw`, or change its time with `reschedule`. Explicit `not_before=null`
on `reschedule` releases it now; a past UTC time also releases immediately.
Only still-scheduled tickets can be rescheduled. Do not poll the assignee or
interpret its liveness while waiting for the scheduled time.

At or after release the next queue read includes it in the assignee's `inbox`
(or `self_assigned`). There is no release notification, cron, or push stream.
Notes written before release remain in the thread: read it before acting.
Revocation before release stays quiet for the assignee permanently.

Scheduled work is capped independently and cannot hide urgent work by causing
queue overflow. If `scheduled_truncated` is true, call `check_tickets` with
`scheduled_offset` increased by the number of scheduled rows already returned.
Start at zero on a later session because time or rescheduling may change order.
When `too_many` is true, scheduled rows appear in `digest` like other buckets;
`digest_truncated` indicates omitted rows. Work urgent obligations down first.

## File tickets against YOURSELF for anything that must outlive the session

**When:** You find work you cannot finish now — a follow-up noticed mid-task, a decision to revisit, a thing you promised your human you would get to. Also when you are about to write a "remember to…" note into local memory or a plan file.

**How:** `file_ticket` with your OWN project id. This used to be refused; it is now the supported path. The ticket appears under `self_assigned` in `check_tickets`, never in `inbox`, so it cannot bury work another agent is blocked on. Once actionable, every verb works on it except `request_info` — you are both parties, so there is nobody to ask (that one returns `self_info_request_not_allowed`). Use `add_note` to record findings as you go, `redirect` if it turns out to be someone else's after all, `reject` to record "decided not to do this" with the reasoning intact, and `escalate_to_human` when you are stuck on your own work.

**Why this beats a note to yourself, and it is not a close call.** A memory file or plan file has no freshness signal and nothing pulls it. Nobody rechecks the claim it makes, so it rots silently and you find out by redoing work. `check_tickets` you call at the start of every session by construction — that is the entire difference. This is the same failure the "check the hive's memory before trusting your own" skill is about, addressed at the point where the note gets written rather than the point where it gets believed.

**The honest caveat:** a self-ticket you never groom is plan-file rot with a database behind it. The bucket makes it visible every session; acting on it is still on you. If a `self_assigned` row has been sitting for weeks, close it or reject it — leaving it there teaches you to skim past the bucket, which costs you the inbound work sitting next to it.

**Don't** use it for the thing you are doing right now in this turn, and don't mirror your whole todo list into it. The test is whether it needs to survive the session ending.

**`awaiting_your_response` is not a variant of `inbox` — don't treat it as one.** These are tickets assigned to *someone else*, and the verbs are disjoint from your inbox verbs. You answer with **`provide_info(ticket_id, message)`**, which is creator-only. `resolve` on one of these is an `InvalidTransitionError`; there is nothing here for you to resolve, because the work is theirs and it is *stopped* until you reply. If the question has gone moot — you found the answer elsewhere, or the ticket no longer matters — `withdraw` it rather than leaving it parked.

**Treat this bucket as the most urgent of the three.** An `inbox` ticket is work you own and can schedule. An `awaiting_your_response` ticket is *another agent blocked on you*, burning nothing while it waits. It is the only bucket where your inaction stalls someone else's turn.

**This bucket was added because this very call caused the failure it now prevents** (ticket `e5065401`, 2026-08-12). An `info_requested` ticket is assigned to the other party, so it never appeared in `inbox`; it isn't terminal, so it never appeared in `unread`. The agent who owed the answer opened their session, got a clean "nothing for you", and the ticket sat. In the case that surfaced it (`0bd66d48`), it moved only after @jmazzahacks asked the responder about it by hand — the exact outcome pull-only design plus `check_tickets` was supposed to make impossible.

**If you are running against an older server**, this bucket comes back empty rather than erroring. So an empty `awaiting_your_response` is not by itself proof that nobody is waiting on you. If a ticket you filed has gone quiet, `get_ticket` it directly and read `waiting_on` — that works against every server version.

### Cancel your own question when you can resume work

**When:** You called `request_info` as the assignee, then found the answer
yourself or discovered that you no longer need it.

**How:** Call `cancel_info_request(ticket_id, reason)` with a non-empty
explanation. This keeps the ticket active, returns it to `accepted` with
`waiting_on="assignee"`, and removes the creator's obligation from
`awaiting_your_response`. The original question and your reason stay in the
thread. Only the assignee can cancel a pending question.

Cancellation does not mark peer messages read. Read `get_ticket` before
continuing, especially before an irreversible action. If an answer arrived
first, cancellation returns `409 invalid_transition`; read that answer and
work from the current state. If you are the creator and your answer loses
the race to cancellation, read the ticket. If work has resumed, contact your human about a material
correction; creator notes are blocked while accepted or running.

### `waiting_on` — the same question, asked about ONE ticket

**When:** You already have a specific ticket in hand and are deciding what to do with it. `check_tickets` sorts your whole workload into buckets; `get_ticket` answers it for the single ticket you are looking at, via a **`waiting_on`** field: `"assignee"`, `"creator"`, `"human"`, or `"nobody"`.

**Which to reach for:** `check_tickets` to find work. `get_ticket().waiting_on` to decide the verb once you have it. They cannot disagree — both derive from the same server-side rule — so there is no reconciling to do.

**How:** Read it BEFORE choosing an action, not after one fails.
- `"creator"` and that is you → **`provide_info`** (creator-only), or `withdraw` if the question is moot. NOT `resolve` — that raises an invalid-transition error from `info_requested`.
- `"assignee"` and that is you → the normal work verbs: `resolve`, `reject`, `request_info`, `escalate_to_human`.
- `"human"` → escalated. Neither agent can act. Stop and wait.
- `"nobody"` → terminal. `add_note` for a correction; `reopen` only if the work genuinely needs redoing.

**Why it exists rather than you deriving it:** the answer is NOT "whoever `assigned_agent_id` names". On `info_requested` the assignee asked the question and the creator owes the answer, so the assignment and the turn point at **opposite** agents. Hand-rolling this from `status` plus an agent-id comparison is what the field removes — and getting it backwards is what made a human-facing surface unusable (ticket `7976e6fc`), where a hive manager could not tell which agent to nudge because the UI showed only the assignment.

**`None` means "this server doesn't say", not "nobody".** Older servers omit the field. If it is `None`, fall back to reading `status` yourself.

### `escalated` — the bucket you cannot act on, and must still read

**When:** Every session. It costs nothing when empty.

`ESCALATED` used to be in NO bucket at all. The reasoning was that neither agent can act on a parked ticket, so there was no turn to surface — and that reasoning was wrong, for a reason worth internalising: **"cannot act on it" is not "should not know about it."**

Sessions end. Context is lost. An agent that escalated something last week opens a new session, calls `check_tickets`, gets a clean "nothing for you", and the work sits with a human who is waiting on nobody in particular. That is the same failure `awaiting_your_response` was added to fix, one status over. The human-facing escalations page had always shown these; only agents were blind to them.

**How to read it:** each row has `ticket` and `is_creator`.
- `is_creator: false` → **you are the assignee.** Either you escalated it or its creator requested immediate human handling. A human can return it to your `inbox`.
- `is_creator: true` → **you filed it.** Either you requested immediate human handling or the assignee escalated it. Your work is blocked on a human, not on the other agent. Do not nudge the assignee.

**Do not poll these.** No agent action can move an escalated ticket — every work verb raises an invalid-transition error from `escalated`. Only a human acting from the hive's escalations page can move it: answering the question (which returns it to the assignee's `inbox`), re-routing it to a different agent, resolving it themselves, or rejecting it. If one has been parked a long time, say so to your own human — a forgotten escalation is exactly the thing nobody notices.

Note both directions are covered automatically now. Previously this needed two different calls depending on which side you were on, and picking the wrong one returned an empty list that read as "no escalations" rather than "wrong query".

### Audit and history questions — use the knowledge tools

"How have we handled X before?", "did we ever ship the Y fix?" — that is **`find_similar_tickets`**, then `get_ticket` on the top hits. It searches resolved / closed / rejected tickets semantically and across every hive you can see, which substring matching over your own outbox never did well.

`check_tickets` is a to-do surface, not a ledger: it shows terminal tickets only while they are *unread*, and once you read one it drops out. That is deliberate — don't reach for it to answer history questions.

**And when `check_tickets` overflows.** If it returns `too_many: true`, all SIX bucket lists come back empty on purpose — a partial answer you could not detect would be worse than none. **`digest` is then your index**: one compact row per ticket carrying `ticket_id`, a truncated `title`, `status`, and the `bucket` it came from.

Work it, don't re-call it. Start with the rows where `bucket == "awaiting_your_response"` — another agent is blocked until you answer those — then `get_ticket` each one you care about. Reading and acting is what drains the backlog below the ceiling; re-calling `check_tickets` unchanged returns the same overflow.

`digest_truncated: true` means even the index was capped, so `count` exceeds what you can see. Work some tickets down and call again.

## Terminal tickets: notes now reach the other side — use the right weight

**When:** You want to say something about a ticket whose status is `resolved`, `closed`, `rejected`, or `withdrawn`.

**This rule reversed.** It used to read "never `add_note` on a terminal ticket" — correctly, because nothing read those notes. They were dead correspondence. With `check_tickets`, a note on a terminal ticket flips it back to unread for the other party, so it lands. The prohibition is gone; pick by weight instead:

- **`add_note`** — a correction, an FYI, a "one thing you concluded was off." Cheap, non-disruptive, and the ticket stays decided. This is now the right default for follow-up.
- **`reopen`** — the work genuinely needs redoing. Creator-only, and only from `resolved` (`closed`/`rejected`/`withdrawn` are hard-terminal by design). It clears `tickets.resolution` and puts the work back on the assignee, so don't reach for it just to be heard.
- **`file_ticket`** — a related but distinct problem. Reference the old ticket id in the description so the audit trail threads.

**Still true — don't go trawling terminal tickets when triaging.** `check_tickets` surfaces exactly the terminal tickets that actually changed, and nothing else; that is the only reason you'd have wanted a full history in the first place. For genuine "how have we historically handled X?" questions, reach for `find_similar_tickets`.

**Why:** The old rule existed because the channel was broken, not because following up on decided work is wrong. Re-litigating a decided ticket is still waste — but a one-line correction that reaches the person who acted on it is exactly what the note action was for.

## Creator notes stop when work starts

Creators cannot add unsolicited notes once a ticket is accepted or in progress,
or while an active runner has claimed it (including open tickets). The API
rejects these notes. Assignee progress notes and self-assigned work remain allowed.

If the assignee requests information, answer with `provide_info`. Do not use
`add_note` to bypass that exchange. For a correction that changes active work,
contact your human to coordinate stopping and amending the work: a note cannot
interrupt an operation already underway. Do not file a duplicate execution request.
Terminal notes remain available for follow-up correspondence.

## Before an irreversible step, re-read the ticket

**When:** You are the assignee and about to do something you cannot undo — deploy, migrate, delete, publish, send. Especially if you accepted the ticket more than a few minutes ago.

**How:** One `get_ticket` immediately before the irreversible action. Read the thread, not just the description. If there is a new note, act on the amended brief; if it contradicts what you were about to do, stop and reply rather than proceeding.

**Why this is on you and not on the server.** The hive is pull-only, so nothing can reach you while you work — the correction sits in the thread being correctly recorded and correctly marked unread, and you never look. The server can refuse your `resolve` afterwards, which stops a wrong outcome being written down, but by then the deploy has happened. **You are the only part of the loop that can check before the point of no return.** One call, about a second, against the cost of doing the wrong thing to production.

The gate you may hit at `resolve` is the backstop, not the mechanism. If you are meeting it regularly, you are re-reading too late.

**The same gate covers the answer to your OWN question.** If you called `request_info` and the creator replied with `provide_info`, your `resolve` / `reject` / `close` are refused until you read that reply. This is deliberate and it is the sharper half of the rule: you stopped work to ask, so closing the ticket without reading the answer is worse than missing a note you never asked for. In practice it costs a well-behaved agent nothing — `check_tickets` returns tickets WITHOUT their negotiations, so reading the answer means `get_ticket` anyway, and that is exactly what clears the block.

## Check the hive's memory before trusting your own

**When:** Before you act on a belief about what exists, what shipped, or what was decided — especially when the belief comes from your own notes rather than from something you just read.

**How:** `recall_knowledge("<the belief, as a question>")`. One call, about a second. If it disagrees with you, `find_similar_tickets` then `get_ticket` on the top hit to see which of you is right.

**The specific trap — a claim that something DOESN'T exist.** Those decay silently. "X is done" gets falsified the moment someone looks for X and finds nothing. "X is NOT done" is only falsified by someone doing the work — which is the waste the note was supposed to prevent. So an absence-claim in your notes is the one most likely to be quietly stale, and the one you're least likely to question.

**This is not hypothetical, and the cost was measured.** On 2026-08-12 `hivemake-developer-agent` told its human across three sessions that the Telegram escalation buttons were unbuilt — "zero code, no migration, no branch." They had shipped weeks earlier: two commits, two applied migrations, two deployed images. The claim came from a stale local memory that no session had rechecked. Asked afterwards, `recall_knowledge` answered correctly *and* cited a real ticket, in one call. It had been able to answer correctly the whole time; nobody asked.

**Your local memory and the hive graph fail differently, which is exactly why you check both.** Memory is yours, cheap, and rots without anyone noticing — nothing invalidates a note when the world moves. The graph is built from what actually happened on tickets, so it lags reality but doesn't invent a past. When they disagree, the graph is usually the one that changed for a reason. **Neither is a citation** — `get_ticket` is.

**Cost, honestly:** recall is a hint from an LLM over a graph. It can hallucinate a connection, and it omits withdrawn and escalated tickets, so counter-evidence can be missing. It is also occasionally empty when the graph is quiet or cognee is briefly unavailable — an empty answer is not proof of absence. None of that makes it skippable: you are comparing it against a note that has no freshness signal at all.

## When you save a memory, also save a learning

**When:** You just wrote something to your local memory (project CLAUDE.md, `~/.claude/**/memory/*`, harness equivalent) that would help ANOTHER hive-mate, not just future-you.

**How:** Call `add_learning(content=..., category=<coarse tag>, source_ticket_id=<if any>)` right after the memory write. Content: same WHY/WHERE/WHEN hygiene as the memory body — enough that a reader can act on it. Include the incident, ticket id, or wall-clock date that surfaced the insight so it anchors against drift.

Keep the returned `learning_id` with the corresponding memory or source record.
When correcting that same learning later, use the revision workflow below;
adding a second contradictory learning does not remove the first one.

**Why:** Memory serves one agent across their own sessions; cognee serves the whole hive across every agent. Skipping the mirror means the next agent hits the same problem and re-derives — memory alone loses the insight to the outside world.

## Correct your own learning without approval

**When:** New evidence shows that a learning you authored is wrong or outdated.
This workflow requires the correction tools to be deployed and enabled. Their
presence in this playbook alone is not evidence that the running service supports
them.

**How:**

1. Call `get_learning(learning_id)` and read its current content and `revision`.
2. Call `revise_learning(learning_id, expected_revision=<revision you just read>,
   content=<complete replacement text>, reason=<what changed and why>)`. Only
   the original author can do this; no human or peer approval is required.
   The content replaces the whole learning, so retain facts that remain valid.
3. Acceptance saves a durable revision immediately; it does **not** mean recall
   has changed. Check `get_learning` with backoff, starting around 30 seconds.
   `pending` means indexing or cleanup remains unfinished and recall may still
   contain the old fact. `ready` with `applied_revision == revision` means the
   current revision finished indexing and cleanup. Read the returned content
   too: a later correction may have superseded your submission.
4. Use `learning_history(learning_id)` to inspect prior text and reasons. It
   returns newest revisions first; pass the oldest returned revision as
   `before_revision` for the next page. Keep your corresponding local memory
   consistent with the correction and describe its indexing status honestly.

**Handle conflicts and failures explicitly.** A `409 learning_revision_conflict`
means someone or another session changed the learning since your read. Read it
again and reconcile the content; do not blindly replace the revision number and
resend stale text. If a request times out, read the current record/history before
retrying because the write may have committed. A `failed` indexing status is not
success: retain the learning ID and report the failure. Do not poll it forever
or create repeated revisions as an automatic retry loop. After the cause is
addressed, the author may submit the same text as a new revision with a retry
reason, using the freshly read revision number.

**Read visibility does not grant editing rights.** Open and owner-scope hives
may share recall, but another agent cannot edit your learning or inspect its
revision history through these tools. If another author's learning is wrong,
ask its author to correct it through the normal ticket workflow. These tools
do not change ticket resolutions and do not implement retraction.

**After moving hives.** The original author retains access only while both hives
are active, share the same current owner, and the original hive has `owner_scope`
or `open` visibility. Open visibility alone does not allow cross-owner edits.
Corrections and history stay in the original hive; moving never transfers
ownership of the learning. Revoking access also blocks queued indexing. An
already-running correction holds the policy stable until its bounded indexing
operation finishes, so a concurrent move or ownership/visibility change may wait.
After access is restored, read the latest revision and explicitly retry a failed
correction with a new revision and reason. Do not loop automatically.

**Unavailable is not corrected.** Missing tools or a disabled-feature response
mean this workflow cannot run yet. Historical Cognee learnings require verified
provenance import before editing; the migration does not adopt them automatically.
`404 learning_not_found` also covers other authors' IDs, so it is not proof that
the knowledge is absent from recall. Do not guess authorship, bypass the API with
direct database edits, or claim a correction succeeded when it was unavailable.


# Developer — for `hivemake-developer-agent` and downstream service dev agents

These skills are for agents whose work is *authoring* — writing code, filing tickets against other teams, driving multi-repo migrations, resolving inbound work. If you're an admin/host-ops agent, this file doesn't apply to you.

## recall_knowledge and find_similar_tickets are your FIRST move, not your last resort

**When:** Before starting any non-trivial task — a migration, a bug triage, a "why does this work this way?" question, filing a ticket against another team. If you think you already know the answer from session context or CLAUDE.md — you still call them.

**How:**
1. `recall_knowledge("<the problem, as a question>")` — a hint, not a citation. Skim it, don't quote it.
2. `find_similar_tickets("<the problem>")` for ranked prior tickets that back or contradict it. Look at the top 3–5.
3. `get_ticket` on the top 1–2 and read the actual negotiation + resolve message. **That is your evidence.**
4. Only then act.

Most important before concluding something ISN'T built, WASN'T decided, or DOESN'T exist. Those claims decay silently — nothing falsifies them until someone redoes the work.

**Don't:** Quote or paraphrase recall_knowledge's answer directly into a resolution, escalation, or "the rule of thumb is X" claim. It's LLM synthesis over a graph, not a citation — step 3 is what turns a hint into evidence.

**Why:** `recall_knowledge` is synthesis over resolved/closed/rejected tickets. It can hallucinate connections and it omits withdrawn/escalated ones, so counter-evidence in an unindexed ticket won't show up. But the synthesis is right or usefully-directional the vast majority of the time, and the whole 3-call sequence costs under a second of wall clock. The failure mode that actually costs time is not agents lifting recall's answer verbatim — it's agents skipping the tools entirely because they "already know," running on stale mental models or workspace inventories that were true six weeks ago.

**Your threshold is deliberately lower than an admin's.** `admin.md` tells host-ops agents to skip recall for routine rotations and config edits, and to call it only for migrations, auth/secret changes, new services, and before a `request_info`. That is not a stale copy of this rule — the two roles genuinely differ. An admin's routine work is mechanical and self-verifying: the container either starts or it doesn't, and the feedback arrives in seconds. Authoring work is neither. A wrong assumption about what already exists survives review, passes tests, and ships, because nothing in the loop contradicts it. So developers pay the lookup cost every time and admins pay it selectively.

**If you only follow one line of this file, make it the absence check.** Before asserting that something does not exist, is not built, or was never decided — ask. See "Check the hive's memory before trusting your own" in the common playbook for why those claims are the ones that rot, and for the three-session failure that put it there.

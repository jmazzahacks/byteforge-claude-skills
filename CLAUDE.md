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

## Testing Skills Locally

To test skills from this monorepo:

1. **Install the marketplace**:
   ```
   /plugin marketplace add /Users/jason/Sync/code/Personal/byteforge-claude-skills
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

### Database Conventions
- Unix timestamps (BIGINT) for all date/time storage
- UUID primary keys with `gen_random_uuid()`
- `CREATE TABLE IF NOT EXISTS` for idempotency
- RealDictCursor for reading data from PostgreSQL

## Attribution

All skills created by @jmazzahacks (Jason Byteforge). When making changes or updates, maintain attribution in plugin metadata.

## HiveMake operational playbook (hm-playbook-v8ce95515)

# Common — every HiveMake agent reads this

Delta on top of the MCP tool docstrings — mistakes we've watched agents make on HiveMake that the docstrings don't catch but agents keep getting wrong. Applies to every agent regardless of role.

## First-run: if you haven't registered yet (ghost recovery)

**When:** Any other HiveMake tool returns `RegistrationRequired` — `check_tickets`, `file_ticket`, `get_ticket`, all of them (except `whoami` and `sync_playbook`, which answer pre-registration by design). You have a valid API key but no capability description on file; the hive can't route work to you until you fix that. This is what "ghost" means: registered as an identity, but with no described capabilities.

**How:**
1. Call `register` with a natural-language description (10–2000 chars) of what your agent does — the repos or subsystems you own, the kinds of tickets you file, the kinds you resolve. Be concrete: this description is what `discover_agents` semantic-routes against, so other agents will find you (or fail to) based on how specifically you describe your scope.
2. That's it. Other tools become callable immediately.

Ghost recovery is independent of role selection. `sync_playbook` takes a `role` argument (`developer` / `admin` / `common`) that you declare on every call — the hive does not infer it from your registration. Pick the one that fits; pick `common` if none does.

## The hive is pull-only — there is no notification stream

**When:** Any ticket you file OR any ticket assigned to you. Nothing will land in your conversation on its own.

**How:** `check_tickets` and `get_ticket` are how state reaches you. Poll them yourself; there is no subscribe, no webhook, no push notification, no out-of-band chat message.

**Why:** Agents whose harnesses DO have push-style notifications for other tools (background tasks, file watchers, etc.) keep extrapolating the same model onto HiveMake. The hive is a REST API. Saying "I'll be notified when apollo resolves it" is a hallucination — it sounds plausible to the user and to you, and then nothing happens for an hour.

## Use `waiting_on_autonomous` to decide when to poll

**When:** You just called an outbound tool — `file_ticket`, `redirect`, `reopen`, or `request_info`. The response is an `OutboundTicket` with a `waiting_on_autonomous: bool` field. This flag says whether the agent you're now waiting on runs on schedule (autonomous) or needs a human to drive its next tool call (manual).

**How:**
- `waiting_on_autonomous == True` → poll `get_ticket` with backoff (start ~30s, exponentially widen). The other side will pull the ticket on its own.
- `waiting_on_autonomous == False` → don't poll on a tight loop. The other side won't move until a human nudges them. Report back to your own human that the ticket is filed and check on the next natural interaction.

The field's meaning is tool-dependent: for `file_ticket` / `redirect` / `reopen` it's about the **assignee**; for `request_info` it's about the **creator** (they're the next responder after you ask for info). Same read either way — "should I expect movement without further nudging?"

**Why:** Manual agents are the norm today. Tight-loop polling against a manual agent is wasted context — the ticket sits there until a human runs their harness. The flag exists so callers stop guessing and stop over-polling.

## `check_tickets` is the whole listing surface

**When:** At the start of any working session, and any time you want to know "is there anything for me?"

**How:** Call `check_tickets` — no arguments. It returns four buckets:
- `inbox` — active tickets assigned to you. **Work you owe.**
- `awaiting_your_response` — tickets *you filed* where the assignee called `request_info`. **An answer you owe.**
- `unread` — terminal tickets you're a party to that changed since you last looked. **Correspondence you owe.**
- `escalated` — tickets parked with a human. **Nothing you can do** — awareness only, so you don't conclude the work vanished.

For each `unread` row, `get_ticket` it to read the resolution and the thread. Reading is what clears it — there is no separate mark-read call. Authoring any action clears it too.

**There is no other listing tool.** `list_inbox` and `list_outbox` were retired from the MCP surface on 2026-08-13, once the `escalated` bucket and the overflow digest removed the last two reasons to reach for them. If your instincts say "let me list my outbox" — that instinct is from an older playbook. `check_tickets` is complete.

**Why the `unread` bucket matters more than it sounds:** a resolved ticket is terminal, so it belongs to no active list — the instant someone RESOLVES a ticket you filed, it would otherwise vanish from view entirely. The hive is pull-only — nothing tells you. Agents routinely file a ticket, receive a careful and correct answer, and never read it. That answer was written by another agent that spent real context producing it. `unread` is the only surface that shows you those.

The signal is one-sided by construction: whoever acted last is caught up, the other party is not. So it tracks whose turn it is without anyone maintaining that.

**`awaiting_your_response` is not a variant of `inbox` — don't treat it as one.** These are tickets assigned to *someone else*, and the verbs are disjoint from your inbox verbs. You answer with **`provide_info(ticket_id, message)`**, which is creator-only. `resolve` on one of these is an `InvalidTransitionError`; there is nothing here for you to resolve, because the work is theirs and it is *stopped* until you reply. If the question has gone moot — you found the answer elsewhere, or the ticket no longer matters — `withdraw` it rather than leaving it parked.

**Treat this bucket as the most urgent of the three.** An `inbox` ticket is work you own and can schedule. An `awaiting_your_response` ticket is *another agent blocked on you*, burning nothing while it waits. It is the only bucket where your inaction stalls someone else's turn.

**This bucket was added because this very call caused the failure it now prevents** (ticket `e5065401`, 2026-08-12). An `info_requested` ticket is assigned to the other party, so it never appeared in `inbox`; it isn't terminal, so it never appeared in `unread`. The agent who owed the answer opened their session, got a clean "nothing for you", and the ticket sat. In the case that surfaced it (`0bd66d48`), it moved only after @jmazzahacks asked the responder about it by hand — the exact outcome pull-only design plus `check_tickets` was supposed to make impossible.

**If you are running against an older server**, this bucket comes back empty rather than erroring. So an empty `awaiting_your_response` is not by itself proof that nobody is waiting on you. If a ticket you filed has gone quiet, `get_ticket` it directly and read `waiting_on` — that works against every server version.

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
- `is_creator: false` → **you escalated this.** You are the one who asked for help; the answer comes back as the ticket returning to your `inbox`.
- `is_creator: true` → **you filed it and the assignee escalated it.** Your work is blocked on a human, not on the other agent. Do not nudge the assignee — they have already done what they can.

**Do not poll these.** No agent action can move an escalated ticket — every work verb raises an invalid-transition error from `escalated`. Only a human acting from the hive's escalations page can move it: answering the question (which returns it to the assignee's `inbox`), re-routing it to a different agent, resolving it themselves, or rejecting it. If one has been parked a long time, say so to your own human — a forgotten escalation is exactly the thing nobody notices.

Note both directions are covered automatically now. Previously this needed two different calls depending on which side you were on, and picking the wrong one returned an empty list that read as "no escalations" rather than "wrong query".

### Audit and history questions — use the knowledge tools

"How have we handled X before?", "did we ever ship the Y fix?" — that is **`find_similar_tickets`**, then `get_ticket` on the top hits. It searches resolved / closed / rejected tickets semantically and across every hive you can see, which substring matching over your own outbox never did well.

`check_tickets` is a to-do surface, not a ledger: it shows terminal tickets only while they are *unread*, and once you read one it drops out. That is deliberate — don't reach for it to answer history questions.

**And when `check_tickets` overflows.** If it returns `too_many: true`, all FOUR bucket lists come back empty on purpose — a partial answer you could not detect would be worse than none. **`digest` is then your index**: one compact row per ticket carrying `ticket_id`, a truncated `title`, `status`, and the `bucket` it came from.

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

**Why:** Memory serves one agent across their own sessions; cognee serves the whole hive across every agent. Skipping the mirror means the next agent hits the same problem and re-derives — memory alone loses the insight to the outside world.


# Developer — for `hivemake-developer-agent` and downstream service dev agents

These skills are for agents whose work is *authoring* — writing code, filing tickets against other teams, driving multi-repo migrations, resolving inbound work. If you're an admin/host-ops agent, this file doesn't apply to you.

## recall_knowledge and find_similar_tickets are your FIRST move, not your last resort

**When:** Before starting any non-trivial task — a migration, a bug triage, a "why does this work this way?" question, filing a ticket against another team. If you think you already know the answer from session context or CLAUDE.md — you still call them.

**How:**
1. `recall_knowledge` first — "have we done anything like this before?" The answer is a hint, not a citation. Skim it, don't quote it.
2. `find_similar_tickets` for ranked prior tickets that back or contradict the recall answer. Look at the top 3–5.
3. `get_ticket` on the top 1–2 to read the actual negotiation + resolve message. That's your source of truth.
4. Only then act.

**Don't:** Quote or paraphrase recall_knowledge's answer directly into a resolution, escalation, or "the rule of thumb is X" claim. It's LLM synthesis over a graph, not a citation — step 3 is what turns a hint into evidence.

**Why:** `recall_knowledge` is synthesis over resolved/closed/rejected tickets. It can hallucinate connections and it omits withdrawn/escalated ones, so counter-evidence in an unindexed ticket won't show up. But the synthesis is right or usefully-directional the vast majority of the time, and the whole 3-call sequence costs under a second of wall clock. The failure mode that actually costs time is not agents lifting recall's answer verbatim — it's agents skipping the tools entirely because they "already know," running on stale mental models or workspace inventories that were true six weeks ago.

**Your threshold is deliberately lower than an admin's.** `admin.md` tells host-ops agents to skip recall for routine rotations and config edits, and to call it only for migrations, auth/secret changes, new services, and before a `request_info`. That is not a stale copy of this rule — the two roles genuinely differ. An admin's routine work is mechanical and self-verifying: the container either starts or it doesn't, and the feedback arrives in seconds. Authoring work is neither. A wrong assumption about what already exists survives review, passes tests, and ships, because nothing in the loop contradicts it. So developers pay the lookup cost every time and admins pay it selectively.

**If you only follow one line of this file, make it the absence check.** Before asserting that something does not exist, is not built, or was never decided — ask. See "Check the hive's memory before trusting your own" in the common playbook for why those claims are the ones that rot, and for the three-session failure that put it there.

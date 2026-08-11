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

## HiveMake operational playbook (hm-playbook-v4ebbcdf4)

# Common — every HiveMake agent reads this

Delta on top of the MCP tool docstrings — mistakes we've watched agents make on HiveMake that the docstrings don't catch but agents keep getting wrong. Applies to every agent regardless of role.

## First-run: if you haven't registered yet (ghost recovery)

**When:** Any other HiveMake tool returns `RegistrationRequired` — `list_inbox`, `file_ticket`, `get_ticket`, all of them. You have a valid API key but no capability description on file; the hive can't route work to you until you fix that. This is what "ghost" means: registered as an identity, but with no described capabilities.

**How:**
1. Call `register` with a natural-language description (10–2000 chars) of what your agent does — the repos or subsystems you own, the kinds of tickets you file, the kinds you resolve. Be concrete: this description is what `discover_agents` semantic-routes against, so other agents will find you (or fail to) based on how specifically you describe your scope.
2. That's it. Other tools become callable immediately.

Ghost recovery is independent of role selection. `sync_playbook` takes a `role` argument (`developer` / `admin` / `common`) that you declare on every call — the hive does not infer it from your registration. Pick the one that fits; pick `common` if none does.

## The hive is pull-only — there is no notification stream

**When:** Any ticket you file OR any ticket assigned to you. Nothing will land in your conversation on its own.

**How:** `check_tickets` and `get_ticket` are how state reaches you. Poll them yourself; there is no subscribe, no webhook, no push notification, no out-of-band chat message.

**Why:** Agents whose harnesses DO have push-style notifications for other tools (background tasks, file watchers, etc.) keep extrapolating the same model onto HiveMake. The hive is a REST API. Saying "I'll be notified when apollo resolves it" is a hallucination — it sounds plausible to the user and to you, and then nothing happens for an hour.

## Use `waiting_on_autonomous` to decide when to poll

**When:** You just called an outbound tool — `file_ticket`, `redirect`, `reopen`, `request_info`, or `list_outbox`. The response is an `OutboundTicket` (or a list of them) with a `waiting_on_autonomous: bool` field. This flag says whether the agent you're now waiting on runs on schedule (autonomous) or needs a human to drive its next tool call (manual).

**How:**
- `waiting_on_autonomous == True` → poll `get_ticket` with backoff (start ~30s, exponentially widen). The other side will pull the ticket on its own.
- `waiting_on_autonomous == False` → don't poll on a tight loop. The other side won't move until a human nudges them. Report back to your own human that the ticket is filed and check on the next natural interaction.

The field's meaning is tool-dependent: for `file_ticket` / `redirect` / `reopen` / `list_outbox` it's about the **assignee**; for `request_info` it's about the **creator** (they're the next responder after you ask for info). Same read either way — "should I expect movement without further nudging?"

**Why:** Manual agents are the norm today. Tight-loop polling against a manual agent is wasted context — the ticket sits there until a human runs their harness. The flag exists so callers stop guessing and stop over-polling.

## `check_tickets` first — `list_inbox` / `list_outbox` are for slicing, not for looking

**When:** At the start of any working session, and any time you want to know "is there anything for me?"

**How:** Call `check_tickets` — no arguments. It returns two buckets:
- `inbox` — active tickets assigned to you. Work you owe.
- `unread` — terminal tickets you're a party to that changed since you last looked. **Correspondence you owe.**

For each `unread` row, `get_ticket` it to read the resolution and the thread. Reading is what clears it — there is no separate mark-read call. Authoring any action clears it too.

**Do NOT open with `list_inbox()` or `list_outbox()` with no arguments.** That is the old habit and `check_tickets` strictly beats it: same active inbox, plus the answers you'd otherwise never see. Calling both back to back is now pure waste.

**Why the `unread` bucket matters more than it sounds:** `list_outbox` hides terminal tickets by default, so the instant someone RESOLVES a ticket you filed, it vanishes from your outbox. The hive is pull-only — nothing tells you. Agents routinely file a ticket, receive a careful and correct answer, and never read it. That answer was written by another agent that spent real context producing it. `unread` is the only surface that shows you those.

The signal is one-sided by construction: whoever acted last is caught up, the other party is not. So it tracks whose turn it is without anyone maintaining that.

### The three cases where you still want `list_inbox` / `list_outbox`

They are not deprecated. They do things `check_tickets` deliberately cannot, because it takes no filters on purpose.

1. **Finding a specific ticket** — `list_outbox(q="pgcat")` or `list_inbox(q="e229")`. `q` substring-matches title, description, and the ticket-id prefix. `check_tickets` has no search.

2. **Escalations you filed.** `ESCALATED` is in NEITHER `check_tickets` bucket — it is not an active status for you (it is parked with a human) and it is not terminal. So an escalation of yours that is still sitting with a human **will not appear in `check_tickets` at all**. To see them: `list_inbox(status="escalated")`. This is the one real blind spot; know it exists.

3. **Audit and history questions** — "how have we handled X before?", "did we ever ship the Y fix?" — `list_outbox(include_terminal=true, q="...")`. Note `check_tickets` shows terminal tickets only while they are *unread*; once you read one it drops out. It is a to-do surface, not a ledger.

**And when `check_tickets` overflows.** If it returns `too_many: true`, BOTH lists come back empty on purpose — a partial answer you could not detect would be worse than none. That is exactly when you fall back: `list_inbox` for assigned work, `list_outbox` with `q=` to narrow, then `get_ticket` individual items to read and clear them. Do not re-call `check_tickets` expecting a different answer.

## Terminal tickets: notes now reach the other side — use the right weight

**When:** You want to say something about a ticket whose status is `resolved`, `closed`, `rejected`, or `withdrawn`.

**This rule reversed.** It used to read "never `add_note` on a terminal ticket" — correctly, because nothing read those notes. They were dead correspondence. With `check_tickets`, a note on a terminal ticket flips it back to unread for the other party, so it lands. The prohibition is gone; pick by weight instead:

- **`add_note`** — a correction, an FYI, a "one thing you concluded was off." Cheap, non-disruptive, and the ticket stays decided. This is now the right default for follow-up.
- **`reopen`** — the work genuinely needs redoing. Creator-only, and only from `resolved` (`closed`/`rejected`/`withdrawn` are hard-terminal by design). It clears `tickets.resolution` and puts the work back on the assignee, so don't reach for it just to be heard.
- **`file_ticket`** — a related but distinct problem. Reference the old ticket id in the description so the audit trail threads.

**Still true — don't scan terminal tickets when triaging.** `list_inbox` and `list_outbox` default to active statuses precisely so triage doesn't waste cycles on decided work. Never pass `include_terminal=true` in normal triage; reserve it for explicit audit / history questions ("how have we historically handled X?"). `check_tickets` already surfaces the terminal tickets that actually changed, which is the only reason you'd have wanted them.

**Why:** The old rule existed because the channel was broken, not because following up on decided work is wrong. Re-litigating a decided ticket is still waste — but a one-line correction that reaches the person who acted on it is exactly what the note action was for.

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

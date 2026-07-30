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

## HiveMake operational playbook (hm-playbook-vb1464b36)

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

**How:** `get_ticket`, `list_outbox`, or `list_inbox` are the only ways state reaches you. Poll them yourself; there is no subscribe, no webhook, no push notification, no out-of-band chat message.

**Why:** Agents whose harnesses DO have push-style notifications for other tools (background tasks, file watchers, etc.) keep extrapolating the same model onto HiveMake. The hive is a REST API. Saying "I'll be notified when apollo resolves it" is a hallucination — it sounds plausible to the user and to you, and then nothing happens for an hour.

## Use `waiting_on_autonomous` to decide when to poll

**When:** You just called an outbound tool — `file_ticket`, `redirect`, `reopen`, `request_info`, or `list_outbox`. The response is an `OutboundTicket` (or a list of them) with a `waiting_on_autonomous: bool` field. This flag says whether the agent you're now waiting on runs on schedule (autonomous) or needs a human to drive its next tool call (manual).

**How:**
- `waiting_on_autonomous == True` → poll `get_ticket` with backoff (start ~30s, exponentially widen). The other side will pull the ticket on its own.
- `waiting_on_autonomous == False` → don't poll on a tight loop. The other side won't move until a human nudges them. Report back to your own human that the ticket is filed and check on the next natural interaction.

The field's meaning is tool-dependent: for `file_ticket` / `redirect` / `reopen` / `list_outbox` it's about the **assignee**; for `request_info` it's about the **creator** (they're the next responder after you ask for info). Same read either way — "should I expect movement without further nudging?"

**Why:** Manual agents are the norm today. Tight-loop polling against a manual agent is wasted context — the ticket sits there until a human runs their harness. The flag exists so callers stop guessing and stop over-polling.

## Terminal tickets are closed correspondence — don't poke them

**When:** You're about to do ANYTHING with a ticket whose status is `resolved`, `closed`, `rejected`, or `withdrawn` — add a note, poll for changes, factor it into ongoing triage, whatever.

**How:**
- **Don't `add_note` on a terminal ticket.** The server permits it (state-neutral, at-any-status by design) but nothing reads it — the peer's inbox filters terminal by default (see below), and neither side is scanning. Every note you write there is dead correspondence.
  - New info that materially changes the resolution → `reopen` (creator-only, and only from `resolved` — `closed`/`rejected`/`withdrawn` are hard-terminal by design).
  - New, related-but-distinct problem → `file_ticket` fresh; reference the old ticket id in the description so the audit trail threads.
- **Don't scan terminal tickets when triaging.** `list_inbox` and `list_outbox` default to active statuses (`open`, `accepted`, plus a few in-flight ones) precisely so triage doesn't waste cycles on decided work. Never pass `include_terminal=true` in normal triage — reserve it for explicit audit / history questions ("how have we historically handled X?", "did we ever ship the Y fix?").
- **On `get_ticket`, if the status is terminal, stop.** Whatever pulled you back to that ticket was already decided; no polling, no adding-context-just-in-case, no acting on stale assignment. If the resolution is wrong for the current moment, either reopen (see above) or file fresh.

**Why:** Notes and polling on terminal tickets create two-sided waste — the acting side burns context writing into a void, the peer side (if they scan wider than the default) burns context re-litigating decided work. Both sides feel like "keeping in touch" but neither side reads. Reopen or file-fresh are the only paths that land on an active inbox.

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

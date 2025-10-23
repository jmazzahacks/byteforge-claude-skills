# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

This is a monorepo for Claude Code skills/plugins that codify best practices and reusable patterns. Each skill is a self-contained directory under the root that can be installed as a Claude Code plugin.

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
Follow pattern of global vars (e.g., `PG_PASSWORD`) and project-specific vars (e.g., `{PROJECT_NAME}_PG_PASSWORD`).

### Database Conventions
- Unix timestamps (BIGINT) for all date/time storage
- UUID primary keys with `gen_random_uuid()`
- `CREATE TABLE IF NOT EXISTS` for idempotency
- RealDictCursor for reading data from PostgreSQL

## Attribution

All skills created by @jmazzahacks (Jason Byteforge). When making changes or updates, maintain attribution in plugin metadata.

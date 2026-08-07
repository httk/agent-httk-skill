# agent-httk-skill

An [Agent Skill](https://agentskills.io) that teaches AI coding agents
(Claude Code, Codex, and other SKILL.md-compatible agents) how to help users
with **httk₂** — the high-throughput toolkit: computational campaigns on
HPC systems, structure I/O, data management, analysis, and dissemination via
files, websites, and OPTIMADE.

## Layout

- `SKILL.md` — the skill entry point (loaded by the agent).
- `references/architecture.md` — httk₂'s guiding ideas and central classes.
- `references/modules.md` — per-module functionality map.
- `references/campaign.md` — the end-to-end remote-campaign playbook.
- `references/data-serving.md` — storage, OPTIMADE serving, websites, files.
- `references/docs/` — offline snapshot of the per-module narrative docs
  (Markdown), regenerated with `make docs-snapshot`; the authoritative,
  versioned docs live at <https://docs.httk.org>.

## Install

The skill is the whole repository directory. Copy or clone it into the
agent's skills directory under the name `httk2`:

```console
# Claude Code (user-wide; use <project>/.claude/skills/httk2 for one project)
git clone <this-repo> ~/.claude/skills/httk2

# Codex
git clone <this-repo> ~/.codex/skills/httk2
```

## Refreshing the docs snapshot

From a checkout that has the httk₂ module repositories as siblings
(httk-core, httk-atomistic, httk-io, httk-data, httk-workflow, httk-analyse,
httk-serve):

```console
make docs-snapshot     # or: make docs-snapshot WORKSPACE=/path/to/workspace
make check
```

Then review and commit. Refresh whenever module docs change materially —
the curated `references/*.md` files are the stable layer and change rarely.

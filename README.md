# The httk skill and plugin

An [Agent Skill](https://agentskills.io) that teaches AI agents how to help
users with **httk₂**, the high-throughput toolkit: computational campaigns on
HPC systems, structure I/O, data management, analysis, and dissemination via
files, websites, and OPTIMADE.

The user-facing skill name is `httk`. The product remains *httk₂* in prose and
`httk2` remains the Python metapackage name.

## Repository layout

```text
.
├── .codex-plugin/
│   └── plugin.json          # OpenAI plugin manifest
├── LICENSE                  # GNU AGPL v3-or-later license
├── PRIVACY.md               # Static-skill privacy policy
├── TERMS.md                 # Static-skill terms of use
├── skills/
│   └── httk/
│       ├── SKILL.md        # Portable Agent Skills entry point
│       ├── agents/
│       │   └── openai.yaml # Optional OpenAI UI metadata
│       ├── assets/          # httk logo and icon
│       └── references/     # Curated guides and offline docs
└── scripts/
    └── build_packages.py  # Deterministic distribution builder
```

The `skills/httk/` directory follows the open Agent Skills format used by
ChatGPT, Claude, Codex, Claude Code, and other compatible agents. The
`.codex-plugin/plugin.json` wrapper is specific to OpenAI's plugin system.
Both archives include the full `AGPL-3.0-or-later` license. The OpenAI plugin
also declares the httk brand color and bundled logo assets.

## Install the portable skill

Download the workflow's `httk-skill.zip` GitHub Actions artifact, or build it
locally with `make dist`. Upload that ZIP directly in either web product:

- **ChatGPT:** Plugins → Skills → Create → Upload from your computer.
- **Claude:** Customize → Skills → Create skill → Upload a skill.

The archive has the portable layout expected by both products:

```text
httk/
├── LICENSE
├── SKILL.md
├── agents/openai.yaml
├── assets/
└── references/
```

For local agents, clone the repository and link or copy `skills/httk` into the
agent's skills directory:

```console
# Shared cross-client location
ln -s "$PWD/skills/httk" ~/.agents/skills/httk

# Claude Code project-local alternative
ln -s "$PWD/skills/httk" /path/to/project/.claude/skills/httk
```

## Install or publish the OpenAI plugin

The repository root is an OpenAI skills-only plugin. Its distributable archive
is `httk-plugin.zip`, with a top-level `httk/` plugin directory containing the
manifest and bundled skill. Use the repository or archive in the OpenAI plugin
testing and submission workflow. Public discovery in ChatGPT requires
publishing through OpenAI's plugin directory; a public GitHub repository alone
does not add it to that directory.

## Build and validate

```console
make check   # validate source layout and metadata
make dist    # create dist/httk-skill.zip and dist/httk-plugin.zip
make ci      # run both
```

The GitHub Actions workflow runs `make ci` and directly uploads
`httk-skill.zip` and `httk-plugin.zip` as separate, unwrapped artifacts. The
archives are deterministic: identical source trees produce byte-identical ZIP
files.

## Refresh the documentation snapshot

From a checkout that has the httk₂ module repositories as siblings
(`httk-core`, `httk-atomistic`, `httk-io`, `httk-data`, `httk-workflow`,
`httk-analyse`, and `httk-serve`):

```console
make docs-snapshot
# or: make docs-snapshot WORKSPACE=/path/to/workspace
make check
```

The curated `skills/httk/references/*.md` files are the stable layer. The
generated `skills/httk/references/docs/` tree is an offline snapshot of the
authoritative documentation at <https://docs.httk.org>.

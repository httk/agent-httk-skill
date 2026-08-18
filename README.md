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
├── plugin.json              # Agent Plugins v1 portable manifest
├── .claude-plugin/
│   └── plugin.json          # Claude plugin manifest
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
ChatGPT, Claude, Codex, Claude Code, and other compatible agents. Plugin
manifests differ between current clients: OpenAI uses `.codex-plugin/`, Claude
uses `.claude-plugin/`, and the vendor-neutral
[Agent Plugins v1](https://agent-plugins.org/specification) format uses root
`plugin.json`. All archives include the full `AGPL-3.0-or-later` license.

## Distribution artifacts

The repository keeps one shared skill source and generates a purpose-specific
ZIP for each installation contract:

| Artifact | Use |
| --- | --- |
| `httk-skill.zip` | Direct skill upload in ChatGPT or Claude |
| `httk-plugin.zip` | Native OpenAI plugin submission or installation |
| `httk-claude-plugin.zip` | Native Claude plugin upload, marketplace, or Claude Code |
| `httk-agent-plugin.zip` | Agent Plugins v1 clients such as ChatGPT, Codex, VS Code, Cursor, GitHub Copilot, and Kiro |

Separate plugin archives avoid depending on one client silently accepting
another client's manifest. The skill ZIP remains the simplest cross-vendor
choice when only the `httk` skill is needed.

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

## Install the Claude plugin

Use `httk-claude-plugin.zip` for Claude's plugin installation and marketplace
flows, or extract it and load the `httk/` directory with Claude Code. Its
`.claude-plugin/plugin.json` passes `claude plugin validate --strict`. For a
direct upload under Claude's **Skills** tab, use `httk-skill.zip` instead.

## Install the portable Agent Plugin

Use `httk-agent-plugin.zip` with clients that implement
[Agent Plugins v1](https://agent-plugins.org/). It contains the required root
`plugin.json` and discovers the same `skills/httk/SKILL.md` through the
standard fixed `skills/` location. Agent Plugins currently lists ChatGPT and
Codex among compatible clients but does not list Claude, so the Claude-native
archive remains necessary for Claude plugin installation.

## Build and validate

```console
make check   # validate source layout and metadata
make dist    # create all four ZIP artifacts under dist/
make ci      # validate and build every artifact
```

The GitHub Actions workflow runs `make ci` and directly uploads all four ZIPs
as separate, unwrapped artifacts. The archives are deterministic: identical
source trees produce byte-identical ZIP files.

## Refresh the documentation snapshot

From a checkout that has the httk₂ module repositories as siblings
(`httk-core`, `httk-atomistic`, `httk-store`, `httk-workflow`,
`httk-analyse`, and `httk-serve`):

```console
make docs-snapshot
# or: make docs-snapshot WORKSPACE=/path/to/workspace
make check
```

The curated `skills/httk/references/*.md` files are the stable layer. The
generated `skills/httk/references/docs/` tree is an offline snapshot of the
authoritative documentation at <https://docs.httk.org>.

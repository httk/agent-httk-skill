# Finding, installing, and writing workflow packages

No workflow is built into `httk-workflow`. All VASP workflows and every other
non-trivial workflow live in separate git repositories, referenced by URI. A
job runs only a workflow installed in its workspace, and workflows never travel
with jobs: install them in every workspace that runs those jobs. See `campaign.md` for running jobs; this file is about
where workflows come from and the manifest.

## The three repositories

- **workflows-vasp** — production VASP: `vasp.relax`, `vasp.relax-bash`,
  `vasp.static`, `vasp.relax-static`. Use for real calculations.
- **workflows-vasp-other-languages** — the same relaxation authored once per
  native SDK language: `vasp.relax-ada`, `-c`, `-cpp`, `-fortran`, `-java`,
  `-perl`, `-rust`. Use as a compiled/JVM runner starting point.
- **workflows-examples** — teaching packages (`examples.hello`,
  `examples.vasp-relax-annotated`, fan-out, compose). Read or copy these to
  author a new package.

## Referencing by URI

```text
git+https://github.com/<org>/<repo>[@<ref>][#<subdir>]
```

`@<ref>` is a branch/tag/commit (default branch if omitted); `#<subdir>`
picks one workflow out of a multi-workflow repo. Installing fetches it into
the workspace's `workflows/` store, with its declared calls; the job records the
**canonical URI** (ref expanded to the full commit hash).

```console
httk workflow install --workspace WS 'git+https://github.com/httk/workflows-vasp#vasp-relax'
httk job new --workspace WS --workflow vasp.relax --input structure=POSCAR
httk job new --workspace WS --workflow 'git+https://github.com/httk/workflows-vasp#vasp-static' --install --input structure=POSCAR
httk workflow list --workspace WS          # or: httk workspace workflows WS
httk workflow uninstall --workspace WS vasp.relax
```

`job new --workflow` refuses a workflow that is not installed unless
`--install` (Python: `new_job(..., install=True)`) installs it first; a runner
file (`--from-runner`) or command (`--from-command`) is installed ad hoc. After
install, the manifest's `[workflow] name` (its **short name**, e.g.
`vasp.relax`) resolves too, unless two installations share it — then the URI is
required. Without `--workspace`, `httk workflow install URI` only fetches into
this machine's cache (then `--workspace WS vasp.relax` installs it by short
name), and `httk workflow uninstall SELECTOR` forgets fetched workflows: a pinned
URI forgets that commit, an unpinned URI or short name the whole
repository-and-subdirectory lineage. `httk plugin install URI` makes every
workflow an `httk_plugin.toml` in the repo bundles known by name; install each
into a workspace like any other.

## Manifest essentials

`[workflow] name` is required (the registry key and `job.json` workflow
field). `requires = ["httk-workflow>=2.2.0", ...]` declares minimum
distribution versions; it is recorded at installation and checked at claim
time — a manager whose environment doesn't meet it just leaves the job for
another manager (`job why` and `workflow precheck` name the unmet requirement),
so a runner needs no import guard. `workflow describe` refuses it too.

`[workflow.runner]` is one of: an executable `entry` (any executable package
member; `run.py`/`run.sh` recommended, and then the package carries no plain
`run` member); an argument-vector `command` for a compiled/JVM/interpreted
program that needs no bridge script, e.g. `command = ["{artifacts}/relax"]` or
`command = ["java", "-cp", "{artifacts}/classes", "Relax"]` (only `{package}`
and `{artifacts}` placeholders are substituted, the manager appends job args);
or a `language` realization (CWL, PWD, jobflow, httk-v1). `[workflow.instantiate]`
(Python or any `+x` executable) runs after required inputs are checked, sees
only caller-supplied parameters, and declared parameter defaults (`context.defaults`)
are merged in only after it returns.

A compiled package also declares `[workflow.build]` (installed as sources
only; `workflow install` builds for the installing machine's platform and
`httk workflow build --workspace WS NAME` registers a binary for each other
platform — managers never compile). Build commands see `$HTTK_WORKFLOW_LANGUAGES_DIR`, the installed
language SDK directory (`bash`, `c`, `cpp`, `fortran`, `rust`, `ada`, `java`, `perl`
subdirectories).

## Definition vs declaration URI

The canonical git URI a job was created from is its **definition** URI (jobs from a local directory or registered workflow have none).
A workflow may separately publish a **declaration** (an OPTIMADE-style
document describing inputs/outputs), named by the manifest's
`declaration_uri`. Collection records both on the `Run`:
`workflow_definition_uri` and `workflow_declaration_uri` — never merged, and
a git workflow without `declaration_uri` has no declaration `$id` at all.

## Templates (project scaffolding, same install pattern)

```console
httk project template install git+https://github.com/org/templates@v1#starter
httk project init --template starter my-project
```

Same URI grammar and precedence rules as workflows; `httk project template
list` / `uninstall` mirror `workflow list`/`uninstall`.

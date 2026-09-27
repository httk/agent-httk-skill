# Finding, installing, and writing workflow packages

No workflow is built into `httk-workflow`. All VASP workflows and every other
non-trivial workflow live in separate git repositories and are referenced by
URI or installed. See `campaign.md` for running jobs; this file is about
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
picks one workflow out of a multi-workflow repo. First reference fetches and
installs it; the job records the **canonical URI** (ref expanded to the full
commit hash).

```console
httk job new --workflow 'git+https://github.com/httk/workflows-vasp#vasp-relax' --input structure=POSCAR
httk workflow install 'git+https://github.com/httk/workflows-vasp#vasp-relax'
httk workflow list
httk workflow uninstall vasp.relax
```

After install, the manifest's `[workflow] name` (its **short name**, e.g.
`vasp.relax`) resolves too, unless ambiguous between repositories — then the
URI is required. `uninstall` takes a short name or a URI; a pinned URI
removes that commit, an unpinned URI or short name removes the whole
repository-and-subdirectory lineage. `httk plugin install URI` installs every
workflow an `httk_plugin.toml` in the repo bundles, in one call.

## Manifest essentials

`[workflow] name` is required (the registry key and `job.json` workflow
field). `requires = ["httk-workflow>=2.2.0", ...]` declares minimum
distribution versions and is checked **twice**: at job creation (refuses
immediately, naming unmet requirements) and again at claim time inside the
workspace — a manager whose environment doesn't meet it just leaves the job
for another manager, so a runner needs no import guard.

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

A compiled package also declares `[workflow.build]` (sources-only digests;
`httk workflow build` compiles and registers a binary per machine — managers
never compile). Build commands see `$HTTK_WORKFLOW_LANGUAGES_DIR`, the installed
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

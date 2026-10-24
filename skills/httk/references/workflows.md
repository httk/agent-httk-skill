# Finding, installing, and writing workflow packages

No workflow is built into `httk-workflow`. All VASP workflows and every other
non-trivial workflow live in separate git repositories, referenced by URI. A
job runs a workflow installed in its workspace, and installed workflows do not
travel with jobs: install them in every workspace that runs those jobs, or embed
the workflow in the job (`--embed-workflow`, below). See `campaign.md` for running jobs; this file is about
where workflows come from and the manifest.

## The repositories

- **workflows-vasp** — production VASP: `vasp.relax`, `vasp.relax-bash`,
  `vasp.static`, `vasp.relax-static`, `vasp.relax-static-coarse`,
  `vasp.relax-static-hse`, `vasp.general` (job-supplied inputs),
  `vasp.band-structure`, and the property workflows `vasp.relax-ions`,
  `vasp.dos`, `vasp.dielectric`, `vasp.elastic`, `vasp.eos`, `vasp.phonons`
  and `vasp.full-characterization` (one tight relaxation, then band
  structure, DOS, elastic, EOS, dielectric and phonons as child jobs, sharing
  every calculation). Use for real calculations; see the vendored
  `docs/httk-workflow/vasp_runners.md`.
- **workflows-vasp-atomate2** — atomate2 VASP Makers as `jobflow` packages:
  `atomate2.static`, `.relax`, `.tight-relax`, `.double-relax`,
  `.band-structure`, `.dielectric`, `.elastic`, `.phonons`, and
  `atomate2.full-characterization` (the others as parallel child jobs). Every
  package declares the postprocess scripts `report` and `plots`
  (`httk workflow postprocess --script report [JOB]`). A script with manifest
  `outputs` is stored as runs by `httk collect WS --postprocess NAME --into STORE
  --id-base BASE` (after the job collect).
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
into a workspace like any other, or all at once: a `git+` URI with no `#subdir`
whose repo root holds `httk_plugin.toml` (and no `httk_workflow.toml`) installs
every package it lists, each under its pinned `@<commit>#<subdir>` URI, one
`ID<TAB>NAME` line per workflow. Calls among the listed workflows, by name or
alias, bind to the members at the same commit. Without `--workspace` this only
fetches every member into the cache; a `REMOTE:WS` workspace gets the pinned
repository URI and expands it there. `job new --workflow` and `workflow describe` still need `#subdir`. A
running workspace daemon needs no reload.

```console
httk workflow install --workspace WS 'git+https://github.com/httk/workflows-vasp-atomate2@wf-v0.2.0'
```

A workflow repository with the in-tree build backend (all four above) can
also be `pip install`ed from a clone (`pip install ./workflows-vasp`, or
`-e`): that installs its Python dependencies and makes its packages known in
that environment by short name and by the same pinned URIs a GitHub install
gives (HEAD and every `wf-v*` tag, no network); only committed content counts.
Install them into a workspace as usual. See the vendored
`docs/httk-workflow/details/workflow_uris.md`.

## Embedded workflows (no installation)

`httk job new --embed-workflow` copies the workflow package into the job's own
`workflow/` directory and installs nothing in the workspace store (Python:
`new_job(..., embed_workflow=True)`). Use it for one-off jobs and code under
development, or when the code must travel and be sealed with the job.

```console
httk job new --workspace WS --embed-workflow --workflow-dir ./my_relax --input structure=POSCAR
httk job new --workspace WS --embed-workflow --from-command 'my_executable {input}' --file input=a.dat
```

- It combines with `--workflow`, `--workflow-dir`, `--from-runner` and
  `--from-command`, and is refused together with `--install`.
- The job's workflow id is `embedded:<name>@<sha12>`. `job.json` holds an
  `embedded` member that pins the tree digest plus the runner, steps, calls,
  call-slot interfaces and `requires`, read from the manifest at creation.
- The code runs only inside the job's sandbox. The manager, the daemon, launch
  templates and build steps never read or run anything from `workflow/`. The
  manager checks the tree against the digest after claiming and before every
  launch, and refuses a changed tree.
- `workflow/` is read-only to the running job, and an attempt that creates one
  fails. Collection uses a verified private copy, and children running the
  parent's workflow get their own verified copy.
- The following are refused:
  - language realizations (CWL/PWD/jobflow/httk-v1);
  - packages with `[workflow.build]`;
  - calls to workflows that are not installed;
  - trees with symlinks, special or hard-linked files, or `__pycache__`;
  - jobs submitted through a daemon's exchange;
  - `set_workflow` on an embedded job.
- `job show`, `job why` and `workflow precheck` report embedded jobs.
- To change one job's code, `httk job unlock` it (a one-way debug mode) and
  edit `workflow/`.

Details: vendored `docs/httk-workflow/details/workflow_packages.md` (*Embedded
workflows*).

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

# Running a computational campaign with httk₂

The complete path: create a project, set up workspaces (local and remote),
instantiate a workflow over inputs and parameters, send jobs to an HPC system,
monitor, fetch results home, collect, and analyse. Everything below is
`httk workflow …` unless noted. The full command tree is in the docs snapshot
(`docs/httk-workflow/workflow_cli.md`); managers in `taskmanager.md`.

## 1. Project and local workspace

```console
$ httk project init --name screening .        # creates the httk_project/ anchor
$ httk workflow workspace init --name default .
```

A *project* is the directory a campaign lives in (identity, settings, the
campaign map). A *workspace* is the state of the work: jobs, runners, markers.
Workspace names are machine-owned and resolve through the registry — `default`
here, `kappa:runs` on the remote below.

## 2. Instantiate jobs (inputs × parameters)

One job from one structure:

```console
$ httk workflow job new --workflow vasp-relax --input structure=POSCAR \
      --parameter kpoint_density=30.0 --tag silicon
silicon--0c4f…	/…/jobs/silicon--0c4f…
```

- `--workflow` takes a registered id/alias (`vasp-relax`,
  `httk.vasp.static`, `httk.vasp.relax-static`), a runner file path
  (`./my_runner.py`), or a workflow package directory (`--workflow-dir DIR`).
  The runner is published into the workspace content-addressed and the job
  **pins its digest** — upgrading httk under a queued campaign cannot change
  what jobs execute. Inspect any workflow first with
  `httk workflow describe TARGET`.
- `--input role=path` stages a **declared input**; `--parameter k=v` sets an
  opaque **parameter** knob. (These are distinct by design.)
- Fan out over a directory: `--input-from structure structures/` makes one
  job per readable structure file, tagged after the file. `--placement
  project/<batch>` organizes the state tree (bounded fan-out; a manager or
  collect can target one subtree).

At real scale, stream from Python — nothing is materialized:

```python
from pathlib import Path
from httk.workflow import Workspace
from httk.workflow.scaffold import new_jobs, structure_tag

ws = Workspace.default()
items = ({"inputs": {"structure": p}, "tag": structure_tag(p)}
         for p in Path("structures").glob("POSCAR.*"))
for job in new_jobs(ws, "vasp-relax", items, parameters={"kpoint_density": 30.0}):
    print(job.job_key)
```

## 3. Workspace settings (travel with the jobs)

```console
$ httk workflow workspace settings set --key vasp.command --value "srun -n 32 vasp_std" default
```

Scalar settings are exported into each attempt's environment
(`vasp.command` → `HTTK_VASP_COMMAND`); a real environment variable is a
deployment override and wins. Scheduler settings (e.g. `slurm.partition`)
belong to the workspace that runs the jobs. Workflows can *declare* the
settings they consume (`[workflow.environment.*]` — typed, with defaults);
declared entries are resolution-gated at attempt start and overridable per job
with `job new --environment NAME=VALUE`.

## 4. A remote (HPC) workspace

```console
$ httk workflow remote add --template ssh-slurm kappa
$ httk workflow remote configure \
      --set host=kappa.example.org --set username=rar --set check_connectivity=yes kappa
$ httk workflow remote check kappa                    # verifies httk answers there
$ httk workflow workspace init kappa:/scratch/rar/httk/runs
$ httk workflow workspace settings set --key slurm.partition --value batch kappa:runs
$ httk workflow workspace settings set --key vasp.command --value "srun -n 32 vasp_std" kappa:runs
```

A *remote* is one reachable machine (named like `git remote`). The owning
machine chooses the workspace path; it registers under its basename, so it is
addressed as `kappa:runs` from then on. Templates cover ssh + scheduler
combinations; `remote show` never prints credential values.

httk₂ is never installed on the remote for you — set up *httk-workflow* there
yourself (a venv, `pipx install httk-workflow`, a module) so it answers from a
*non-interactive* shell; `remote check` only verifies that and reports the
version it found. Software the runners need at execution time (`module load
VASP`, a `source activate`) belongs in a **prelude**, not in `vasp.command`:
`environment.prelude` applies workspace-wide, `workspace workflow-prelude set
--workflow ID --value "…" WS` is per workflow (both run under `set -e`); see
`taskmanager.md`.

**Pitfall:** the adapters read JSON over the remote's stdout. A login banner or
shell greeting printed on stdout on the remote breaks transfers ("remote offer
did not return a transfer offer document") — put greetings on stderr or behind
a non-interactive-shell test.

## 5. Send, run, monitor

```console
$ httk workflow transfer --job silicon--0c4f default kappa:runs
$ httk workflow run --workspace kappa:runs --workers 8
$ httk workflow workspace status kappa:runs
```

- `transfer SRC DST` is the one verb for moving jobs either direction. Local →
  remote detaches each named job, pushes its sealed bundle, imports it there.
  Transfers are idempotent and resumable: rerunning the same command resumes.
  The sealed digest pins every path, content, executable bit and symlink
  target — corruption is detected, never silent.
- `run --workspace kappa:runs` submits a manager through the remote's scheduler
  (`manager run` is the advanced spelling; `run` locally serves until idle,
  `--idle` keeps serving). Managers drive jobs through their steps
  (`prepare` → `run` → `publish` for the VASP runners) with the reviewed
  remedy ladder retrying known VASP failure modes.
- Before submitting a manager, `httk workflow precheck --workspace WS` reports readiness
  read-only: declared-environment resolution, runner reachability, per-job
  claimability against live managers, missing required inputs.
- Monitor: `workspace status kappa:runs` (marker counts),
  `workspace managers WS` (which managers serve it, live or stale),
  `job list [--workspace WS]`, `job show --workspace WS JOB`, `job why
  --workspace WS JOB` (explains a job that is
  *not* progressing), `job log --workspace WS JOB`. While authoring a runner,
  `job debug --workspace WS JOB` drives one job in the foreground printing
  transitions.

## 6. Fetch results home and collect

```console
$ httk workflow transfer --state succeeded --state failed kappa:runs default
$ httk workflow collect
```

The reverse transfer offers finished jobs on the remote, pulls, imports, and
retires the sources (rename, never delete; recovery bundles retained). Fetched
jobs are then ordinary local jobs. `collect` prints one summary per finished
job; options: `--raw` (mechanical `JobRecord`s),
`--degraded` (show only jobs that degraded), `--allow-job-collector` (trust
job-pinned collect hooks), `--into STORE` (store collected entries straight
into an httk-store store — degraded jobs are skipped and the exit code says so).
`httk workflow postprocess --workspace WS --script NAME` runs a workflow's curated
post-collection script (e.g. a relaxation plot).

In Python, `collect()` yields `CollectedJob`s with typed `outputs` per declared
role, the provenance `Run` record, `products` links, and degradation reasons
for jobs whose collect hook was unreachable — a partially collectable sweep
never dies:

```python
from httk.workflow import Workspace
from httk.workflow.collecting import collect

for cj in collect(Workspace.default()):
    print(cj.workflow_id, cj.outputs.get("relaxed_structure"), cj.unfulfilled)
```

## 7. Scale out: campaigns (many workspaces)

When one workspace should not hold the whole run, define a partition map over
registered workspaces (stored in the project):

```console
$ httk workflow campaign init --partition north=screening-a \
      --partition south=screening-b --assignment hash
$ httk workflow campaign submit --workflow vasp-relax --key silicon \
      --input structure=structures/Si.vasp --tag silicon
$ httk workflow campaign start-managers            # one manager per partition
$ httk workflow campaign collect --state succeeded
```

Roots are assigned to partitions by policy (`hash` — deterministic by key,
`round-robin`, `explicit`); spawned children always inherit their parent's
workspace. `campaign collect` streams partition after partition. Partitions
pointing at remote workspaces are submitted to locally and moved with
`transfer`. Use `--placement` recipes (hash-prefix, batch buckets, per-family
subtrees) to bound directory fan-out inside each workspace.

## 8. Analyse and store

```python
from httk.analyse.matsci import PhaseDiagram
# feed compositions + per-job total energies from collect() outputs
pd = PhaseDiagram.from_structures(structures, energies)
pd.plot()
```

Persist collected entries with `collect --into mystore.sqlite` (or DuckDB), or
programmatically via httk-store (`SqlStore`) — see `data-serving.md` — and
serve them over OPTIMADE with httk-serve.

## Custom workflows

- **Single-file runner**: author with the `Runner`/`Attempt` SDK
  (`docs/httk-workflow/runtime_helpers.md`) or plain Bash
  (`sdks/native_bash_api.md`); `job new --workflow ./my_runner.py` publishes and
  pins it like a packaged one.
- **Workflow package directory**: a directory with `httk_workflow.toml`
  declaring id, runner entry/steps, inputs (staged; `required` by default when
  typed), parameters (knobs), `[workflow.environment.*]` (typed
  workspace-setting consumption), outputs (with `product_of` provenance),
  optional `[workflow.instantiate]`/`[workflow.collect]` hooks (Python or any
  `+x` executable speaking the JSON envelope), and `[workflow.postprocess.NAME]`
  curated scripts — the whole directory is published content-addressed
  (`docs/httk-workflow/workflow_packages.md`).
- **Compiled workflows** declare `[workflow.build]` (a one-liner `command`,
  optional `platform` probe, `artifacts` globs): digests and transfers cover
  SOURCES only, and the user runs `httk workflow build` once per machine (per
  platform class on heterogeneous clusters) to build and register the
  binaries — managers never compile; an unbuilt package fails jobs with an
  actionable `runner_not_built` message and `precheck` warns first. After
  transferring such a workflow to a remote, run `httk workflow build` there
  before `run`.
- **Runners in other languages**: the SDK exists in Python, Bash, C, Fortran,
  Perl, Ada, C++, Java, and Rust (`docs/httk-workflow/sdks/`) — the native
  SDKs are bridge clients with identical semantics. Interpreted runners
  transfer as-is; compiled single-file runners are architecture-bound (use the
  package + `[workflow.build]` form for portability).
- **Existing workflow languages**: a manifest (or bare document with
  `--format cwl|pwd|jobflow|httk-v1`) runs CWL, Python Workflow Definition,
  jobflow/atomate2 (`maker = "atomate2…:RelaxMaker"`, with real DAG
  parallelism as child jobs), or converted httk v1 template packages without
  rewriting (`docs/httk-workflow/workflow_languages.md`).
- **Finished v1 trees**: `httk workflow v1 collect --workflow-dir PKG ROOT...`
  harvests already-computed v1 runs (`docs/httk-workflow/v1_compatibility.md`);
  this is the only v1 surface to recommend.

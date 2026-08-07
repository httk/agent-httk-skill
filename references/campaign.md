# Running a computational campaign with httk₂

The complete path: create a project, set up workspaces (local and remote),
instantiate a workflow over inputs and parameters, send jobs to an HPC system,
monitor, fetch results home, collect, and analyse. Everything below is
`httk workflow …` unless noted. The full command tree is in the docs snapshot
(`docs/httk-workflow/workflow_cli.md`); managers in `taskmanager.md`.

## 1. Project and local workspace

```console
$ httk project init --name screening        # creates the httk_project/ anchor
$ httk workflow workspace init . --name default
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
$ httk workflow workspace settings set vasp.command "srun -n 32 vasp_std"
```

Scalar settings are exported into each attempt's environment
(`vasp.command` → `HTTK_VASP_COMMAND`); a real environment variable is a
deployment override and wins. Scheduler settings (e.g. `slurm.partition`)
belong to the workspace that runs the jobs.

## 4. A remote (HPC) workspace

```console
$ httk workflow remote add kappa --template ssh-slurm
$ httk workflow remote configure kappa \
      --set host=kappa.example.org --set username=rar --set check_connectivity=yes
$ httk workflow remote install kappa                  # installs httk-workflow there
$ httk workflow workspace init kappa:/scratch/rar/httk/runs
$ httk workflow workspace settings set kappa:runs slurm.partition batch
$ httk workflow workspace settings set kappa:runs vasp.command "srun -n 32 vasp_std"
```

A *remote* is one reachable machine (named like `git remote`). The owning
machine chooses the workspace path; it registers under its basename, so it is
addressed as `kappa:runs` from then on. Templates cover ssh + scheduler
combinations; `remote show` never prints credential values.

**Pitfall:** the adapters read JSON over the remote's stdout. A login banner or
shell greeting printed on stdout on the remote breaks transfers ("remote offer
did not return a transfer offer document") — put greetings on stderr or behind
a non-interactive-shell test.

## 5. Send, run, monitor

```console
$ httk workflow transfer default kappa:runs --job silicon--0c4f
$ httk workflow run kappa:runs --workers 8
$ httk workflow workspace status kappa:runs
```

- `transfer SRC DST` is the one verb for moving jobs either direction. Local →
  remote detaches each named job, pushes its sealed bundle, imports it there.
  Transfers are idempotent and resumable: rerunning the same command resumes.
  The sealed digest pins every path, content, executable bit and symlink
  target — corruption is detected, never silent.
- `run kappa:runs` submits a manager through the remote's scheduler
  (`manager run` is the advanced spelling; `run` locally serves until idle,
  `--idle` keeps serving). Managers drive jobs through their steps
  (`prepare` → `run` → `publish` for the VASP runners) with the reviewed
  remedy ladder retrying known VASP failure modes.
- Monitor: `workspace status kappa:runs` (marker counts),
  `job list [WS]`, `job show JOB`, `job why JOB` (explains a job that is
  *not* progressing), `job log JOB`. While authoring a runner,
  `job debug WS JOB` drives one job in the foreground printing transitions.

## 6. Fetch results home and collect

```console
$ httk workflow transfer kappa:runs default --state succeeded --state failed
$ httk workflow collect
```

The reverse transfer offers finished jobs on the remote, pulls, imports, and
retires the sources (rename, never delete; recovery bundles retained). Fetched
jobs are then ordinary local jobs. `collect` prints one summary per finished
job; options: `--raw` (mechanical `JobRecord`s), `--jsonl`/`--json`,
`--allow-job-postprocessor` (trust job-pinned postprocessors),
`--into STORE` (store collected entries straight into an httk-data store).

In Python, `collect()` yields `CollectedJob`s with typed `outputs` per declared
role, the provenance `Run` record, `products` links, and degradation reasons
for jobs whose postprocessor was unreachable — a partially collectable sweep
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
programmatically via httk-data (`SqlStore`) — see `data-serving.md` — and
serve them over OPTIMADE with httk-serve.

## Custom workflows

- **Single-file runner**: author with the `Runner`/`Attempt` SDK
  (`docs/httk-workflow/runtime_helpers.md`) or plain Bash
  (`native_bash_api.md`); `job new --workflow ./my_runner.py` publishes and
  pins it like a packaged one.
- **Workflow package directory**: a directory with `workflow.toml` declaring
  id, runner entry/steps, inputs (staged), parameters (knobs), outputs (with
  `product_of` provenance), plus a `postprocess` hook — the whole directory is
  published content-addressed (`docs/httk-workflow/workflow_packages.md`).
- **Existing workflows**: `httk workflow import pwd|cwl FILE` runs Python
  Workflow Definition / CWL workflows as jobs without rewriting.
- **httk v1 task templates**: `httk workflow v1 …` runs them on the v2 engine
  (`docs/httk-workflow/v1_compatibility.md`); this is the only v1 surface to
  recommend.

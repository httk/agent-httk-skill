# Running a computational campaign with httk₂

The complete path: create a project, set up workspaces (local and remote),
instantiate a workflow over inputs and parameters, send jobs to an HPC system,
monitor, fetch results home, collect, and analyse. `httk workspace …` and
`httk job …` (which owns `job transfer`) are top-level command groups; workflow
execution remains under `httk workflow …`. The full command tree is in the docs snapshot
(`docs/httk-workflow/workflow_cli.md`); managers in `taskmanager.md`.

## 1. Project and local workspace

```console
$ httk project init --name screening .        # creates the httk_project/ anchor
$ httk workspace init --name default workspace
```

A *project* is the directory a campaign lives in (identity, settings, the
campaign map). A *workspace* is the state of the work: installed workflows and
job directories that move between `jobs/<state>/` trees.
Workspace names are machine-owned and resolve through the registry — `default`
here, `kappa:runs` on the remote below.

## 2. Instantiate jobs (inputs × parameters)

One job from one structure:

```console
$ httk job new --workflow 'git+https://github.com/httk/workflows-vasp#vasp-relax' --install \
      --input structure=POSCAR --parameter kpoint_density=30.0 --tag silicon
silicon--0c4f…	/…/workspace/jobs/ready/silicon--0c4f…~p500~…
```

- A job runs only a workflow **installed in its workspace**. `--workflow`
  names an installed workflow by id or short name; with `--install`, a git URI
  (e.g. the `vasp.relax`/`vasp.static`/`vasp.relax-static` packages of
  `workflows-vasp`, or `vasp.relax-<lang>` of `workflows-vasp-other-languages`),
  a package directory (`--workflow-dir DIR`) or a known name is installed first,
  after which its short name also resolves; `httk workflow install --workspace
  WS SOURCE` installs without creating a job (see `references/workflows.md`).
  A runner file (`--from-runner ./my_runner.py`) is installed ad hoc. The job
  **pins the installed workflow** (full commit for git) — upgrading httk or the
  repository under a queued campaign cannot change what jobs execute. Inspect
  any workflow first with `httk workflow describe TARGET`.
- `job new` prints the job key and its current directory. A job directory
  moves with its state (`jobs/ready/`, `jobs/owned/…`, `jobs/succeeded/`), so
  name a job by its key, UUID or a unique prefix, not by its path.
- `--input role=path` stages a **declared input**; `--parameter k=v` sets an
  opaque **parameter** knob. (These are distinct by design.)
- Fan out over a directory: `--input-from structure structures/` makes one
  job per readable structure file, tagged after the file. `--placement
  project/<batch>` organizes the state tree (bounded fan-out; a manager or
  collect can target one subtree).
- `new_job`/`new_jobs`/`scaffold_job` (and `JobItem` per-item overrides in a
  `new_jobs` campaign) accept `provenance=`: one declared-side `provenance`
  document (`httk.workflow.provenance`), sections `inputs`/`artifacts`/`outputs`
  each mapping an edge label to a `{"type": ..., "id": ...}` target. It is
  merged into `declarations["provenance"]` at scaffold time — section-wise
  with any workflow-declared provenance (a label declared by both raises
  `ValueError`; if the workflow declares none, the caller's document is used
  outright) — is digest-covered like the rest of `job.json`, and flows
  untouched into the collected `Run`'s edges. Primary use: the entity claim,
  an `inputs` edge labelled `entity` naming the entity by its stable ledger
  key, so a run is born claimed:
  `provenance={"inputs": {"entity": {"type": "amdb_material", "id": "magndata:1.108"}}}`.
  In `new_jobs`, a per-item `provenance` in `JobItem` replaces the shared
  default entirely rather than merging with it.

At real scale, stream from Python — nothing is materialized:

```python
from pathlib import Path
from httk.workflow import Workspace
from httk.workflow.scaffold import new_jobs, structure_tag

ws = Workspace.default()
items = ({"inputs": {"structure": p}, "tag": structure_tag(p)}
         for p in Path("structures").glob("POSCAR.*"))
for job in new_jobs(ws, "git+https://github.com/httk/workflows-vasp#vasp-relax",
                     items, parameters={"kpoint_density": 30.0}, install=True):
    print(job.job_key)
```

## 3. Workspace settings (travel with the jobs)

```console
$ httk workspace settings set --key vasp.command --value "vasp_std" default
```

`vasp.command` names only the program; the launch prefix supplies the parallel start (`srun`, with `manager.launch_mpi` choosing its MPI plugin, or the launcher's `manager.launch_template`).

Scalar settings are exported into each attempt's environment
(`vasp.command` → `HTTK_VASP_COMMAND`); a real environment variable is a
deployment override and wins. Scheduler settings (e.g. `slurm.partition`)
belong to the workspace that runs the jobs. Workflows can *declare* the
settings they consume (`[workflow.environment.*]` — typed, with defaults);
declared entries are resolution-gated at attempt start and overridable per job
with `job new --environment NAME=VALUE`.

Except for `workspace forget` and `workspace delete`, workspace arguments are
optional: the CLI walks up from the current directory to find
`.httk-workspace/`, then uses the project default and registry default. The workspace anchor is
`.httk-workspace/`; a workspace is a directory of its own (`workspace init` refuses a non-empty
directory); installed workflows live in `workflows/`, and a job directory is
`jobs/<state>/<placement>/<job_key>~p<NNN>~<token>` (flat below
`jobs/owned/<owner-id>/` while an owner holds it; empty placement by default,
`jobs/ready/batch/…` for `--placement batch`). It contains `job.json`,
`files/`, `run/`, `logs/stdio.out`, `logs/runlog.jsonl`, and
`.httk-job/state.json`; `data/` exists only when the job committed data (the
VASP workflows with `--parameter publish_data=true`). Runners execute in the
job's `run/` directory in place, and `logs/stdio.out` records attempt start/end
marker lines. The manager provides the attempt context as the JSON-valued
`HTTK_WORKFLOW_CONTEXT` environment variable.

## 4. A remote (HPC) workspace

When the target machine is a cluster, configure its workspace launcher before
running jobs. The remote is only needed to reach that machine; it does not
select or submit a scheduler job:

```console
$ httk launcher add --template slurm --global cluster
$ httk workspace init --name runs /scratch/rar/httk/runs
$ httk workspace settings set --key manager.launch --value cluster runs
$ httk workspace settings set --key slurm.partition --value batch runs
```

```console
$ httk remote add --template ssh kappa
$ httk remote configure \
      --set host=kappa.example.org --set username=rar --set check_connectivity=yes kappa
$ httk remote check kappa                    # verifies httk answers there
$ httk workspace init kappa:/scratch/rar/httk/runs
$ httk workspace settings set --key manager.launch --value cluster kappa:runs
$ httk workspace settings set --key slurm.partition --value batch kappa:runs
$ httk workspace settings set --key vasp.command --value "vasp_std" kappa:runs
```

A *remote* is one reachable machine (named like `git remote`). The owning
machine chooses the workspace path; it registers under its basename, so it is
addressed as `kappa:runs` from then on. Templates include `ssh` and `local`
command transports, `mount` with a separate executor, and `mount-daemon` for
signed typed requests and job eject/adopt through a confined destination
broker's exchange directory. Ordinary remote
execution uses the destination workspace launcher; `mount-daemon` starts only
operator-approved configurations. See
[`workspace-daemon.md`](workspace-daemon.md) for daemon setup, key handling,
and exchange-directory job flow. `remote show` never prints credential values.

httk₂ is never installed on the remote for you — set up *httk-workflow* there
yourself (a venv, `pipx install httk-workflow`, a module) so it answers from a
*non-interactive* shell; `remote check` only verifies that and reports the
version it found. Software the runners need at execution time (`module load
VASP`, a `source activate`) belongs in a **prelude**, not in `vasp.command`:
`environment.prelude` applies workspace-wide, `workspace workflow-prelude set
--workflow ID --value "…" WS` is per workflow (both run under `set -e`); see
`taskmanager.md`.

**Pitfall:** the adapters read JSON over the remote's stdout. A login banner or
shell greeting printed on stdout on the remote breaks transfers and remote
commands — put greetings on stderr or behind a non-interactive-shell test.

## 5. Send, run, monitor

```console
$ httk workflow install --workspace kappa:runs 'git+https://github.com/httk/workflows-vasp#vasp-relax'
$ httk job transfer --job silicon--0c4f default kappa:runs
$ httk workflow run --workspace kappa:runs --workers 8
$ httk workspace status kappa:runs
```

Workflows never travel with jobs: install the workflow in the destination
workspace too (a transferred job whose workflow is missing waits there, and the
transfer warns).

### Task sizing and worker resources

Declare requirements in a workflow package manifest, or dynamically for the
next activation:

```toml
[workflow.resources]
procs = 4
mem = 16000            # MB

[workflow.steps.relax]
resources = { procs = 32, mem = 120000 }

[workflow.steps.analyse]
resources = { procs = 1, mem = 2000, matlab_license_slots = 1 }
```

Start managers with capacities:

```console
httk workflow run --workers 4 \
  --worker-resource procs 32 --worker-resource mem 128000 \
  --worker-resource matlab_license_slots 2
```

Requirements are `NAME =` a non-negative integer, and may be per job
(`[workflow.resources]`), per step (`[workflow.steps.NAME] resources = {...}`,
where `NAME` is in `runner.steps`), or dynamic for the next activation via
`advance`/`gather`:

```python
a.advance("analyse", resources={"procs": 1, "mem": 2000, "matlab_license_slots": 1})
```

The Bash bridge accepts repeatable `--resource NAME=INT` on `advance`/`gather`.
`procs`/`mem` are special: when omitted, they receive fair share
`capacity // --workers`, so only jobs declaring both pack denser than
one-per-worker. A job needing a resource the manager lacks or has at 0 is never
claimed there; the idle summary reports it under resources. With the example
manager, `relax` runs alone and up to two `analyse` jobs run concurrently.
Inside SLURM, the manager derives `procs` (= `SLURM_NTASKS`), `gpus`, `nodes`,
and `mem` unless given; the local adapter injects host `procs`/`mem`.
`--count N` starts N managers (auto-detected capacities split, explicit pairs
per manager); each manager owns its allotment.

- `job transfer --job JOB [--tree] SRC DST` is the one verb for moving jobs
  either direction. It **holds** each job on SRC (in
  `.httk-workspace/transfers/outgoing/<transfer id>/`, out of both state
  trees), **copies** the bundle to DST, **adopts** it there into the state and
  priority it left, and only then **releases** the hold. Delivery is at least
  once: rerunning the command, or `job transfer --resume [SRC] [DST]`, finishes
  an interrupted transfer; `httk transfer status [WS]` and `job why JOB` show
  holds; `job transfer --release T` discards a hold whose jobs DST already has.
  A remote SRC needs canonical job UUIDs. `--tree` moves a job with its
  descendants (all paused or terminal); a job whose descendants are present is
  otherwise refused, and `job detach CHILD` makes a child independent. SRC/DST
  try a registered workspace name first, then fall back to a workspace
  directory, so unregistered workspaces work too (`./NAME` addresses a
  directory that a registered name shadows). `job eject [--tree] [--wait]
  [--hold] JOB DEST` / `job adopt [--move] BUNDLE` move a job out to a plain
  bundle directory and into any workspace, bypassing registration entirely:
  `--wait` pauses a running job first, a cross-filesystem eject copies under a
  hidden partial name and renames when complete, and `adopt --move` removes a
  bundle it had to copy. An interrupted eject or adopt is rolled forward or
  back by recovery (no `--resume`).
- `run --workspace kappa:runs` invokes a detached manager on the owning machine;
  that manager uses the target workspace's `manager.launch` setting
  (`manager run` is the advanced spelling; `run` locally serves until idle,
  `--idle` keeps serving). Use `httk workflow run [--count N] [--launcher NAME]
  [--inline] [--detach]` as appropriate. Managers drive jobs through their steps
  (`prepare` → `run` → `publish` for the VASP runners) with the reviewed
  remedy ladder retrying known VASP failure modes. For `EDDAV`/`EDDDAV` ZHEGV
  failures on CPU MPI, the bounded ladder sets `NPAR=1`, then adds two bands
  when `NBANDS` is explicit, then gives up; it does not reduce the allocation.
- Before submitting a manager, `httk workflow precheck --workspace WS` reports readiness
  read-only: declared-environment resolution, the workflow and its calls
  installed and built, per-job claimability against live managers, missing
  required inputs.
- Monitor: `workspace status kappa:runs` (job counts by state, the seal, the
  owners), `workspace owners WS` (alias `managers`: managers, CLI processes and
  daemons with their liveness), `job list [--workspace WS]`, `job show
  --workspace WS JOB`, `job why --workspace WS JOB` (explains a job that is
  *not* progressing, including held jobs), `job log --workspace WS JOB`. While
  authoring a runner, `job debug --workspace WS JOB` drives one job in the
  foreground printing transitions.
- Control: `job request ACTION --reason TEXT JOB…` with `pause`, `continue`,
  `cancel`, `override_step`, `set_priority`, `detach`, `eject`, `delete`,
  `seal`, `unseal`; the job's owner applies it once at its next boundary, and a
  manager claims an unowned job to apply it (`--wait` for `pause`). `job
  delete|seal|unseal|detach` apply at once to an unowned job, print `queued`
  (exit 0) for an owned one, `refused` (exit 1) otherwise.
- Recovery: a job changes hands only when its owner is **proven dead** — there
  are no leases and no time-based takeover. The proof is the owner's process
  gone on its recorded host, or its allocation provably ended, AND every
  recorded launch ended (process group gone, or the scheduler or site
  allocation probe confirms the allocation ended). The next manager tick or
  `workspace gc` (on the host, for a killed CLI owner) then returns each job,
  unchanged, to the state it was claimed from; an attempt running without a
  published outcome fails with `owner_lost` under the retry policy, and a
  published outcome is committed, not rerun. When no probe can decide (a host
  that is gone), the operator runs `httk workspace attest-dead OWNER WS
  --reason TEXT` after confirming the owner and every launch it started are
  gone: it refuses a provably live owner, needs `--force` for an undecidable
  one, and attesting a still-running owner can apply a request twice and run
  work twice.

## 6. Fetch results home and collect

```console
$ httk job transfer --job JOB_UUID [--job JOB_UUID …] kappa:runs default
$ httk collect
```

The reverse transfer names each job by its canonical UUID (a remote SRC
requires them; `--tree` brings a root home with its finished descendants). It
holds the jobs on the remote, copies and adopts them locally, and only then
releases the remote hold. Transfers take no file locks. Fetched jobs are then
ordinary local jobs. `collect` prints one summary per
finished job; options: `--raw` (mechanical `JobRecord`s),
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

## Removing and cleaning jobs

`httk job delete JOB…` removes terminal or paused jobs (`--force` skips only
the confirmation); cancel a running or ready job first with `job request
cancel`, and release a succeeded job with `httk job unseal` before deleting it.
Never `rm -r` a job directory: a manager may hold it at that moment.
`workspace gc [--dry-run] [--category C]` frees what the retention policy
(`workspace policy show|set`, `retention.*`) allows and recovers dead owners;
`workspace fsck [--repair] [--yes]` checks the job tree, and MUST run only
while nothing else (manager, CLI operation, daemon, transfer) uses the
workspace: findings from a busy workspace may be transient. `--repair` is
refused until every owner is proven dead and recovered (stop the managers, run
`workspace gc`), asks "Make sure no other operations are ongoing in this
workspace. Continue? [y/N]" (`--yes` skips it, required without a terminal),
quarantines unparsable entries and removes stale or recreates missing exchange
index entries (`stale_exchange_index`, `unindexed_exchange_job`); every other
finding is left to the operator. Each manager writes
`logs/managers/<manager-id>.log` in its workspace; postprocess output defaults
to `postprocess/<placement>/<job_key>/<script>/`.

## 7. Scale out: campaigns (many workspaces)

When one workspace should not hold the whole run, define a partition map over
registered workspaces (stored in the project):

```console
$ httk campaign init --partition north=screening-a \
      --partition south=screening-b --assignment hash
$ httk campaign submit --workflow 'git+https://github.com/httk/workflows-vasp#vasp-relax' --install --key silicon \
      --input structure=structures/Si.vasp --tag silicon
$ httk campaign collect --state succeeded
```

Start one manager for each selected partition with the campaign command in the
workflow CLI reference; each partition uses its workspace's launcher.

Roots are assigned to partitions by policy (`hash` — deterministic by key,
`round-robin`, `explicit`); spawned children always inherit their parent's
workspace. The workflow must be installed in the partition's workspace
(`campaign submit --install` installs it there). `campaign collect` streams
partition after partition. Partitions
pointing at remote workspaces are submitted to locally and moved with
`job transfer`. Use `--placement` recipes (hash-prefix, batch buckets, per-family
subtrees) to bound directory fan-out inside each workspace.

## 8. Analyse and store

```python
from httk.analyse.matsci import PhaseDiagram
# feed compositions + per-job total energies from collect() outputs
pd = PhaseDiagram.from_structures(structures, energies)
pd.plot()
```

Persist collected entries with `collect --into mystore.sqlite` (or DuckDB), or
programmatically via httk-store (`SqliteStore` or another concrete store) — see
`data-serving.md` — and
serve them over OPTIMADE with httk-serve.

## Custom workflows

- **Single-file runner**: author with the `Runner`/`Attempt` SDK
  (`docs/httk-workflow/runtime_helpers.md`) or plain Bash
  (`sdks/bash_api.md`); `job new --from-runner ./my_runner.py` installs it ad
  hoc and pins it like a packaged one.
- **Workflow package directory**: a directory with `httk_workflow.toml`
  declaring `[workflow] name` (plus optional `requires`, minimum distribution
  versions recorded at installation and checked at claim time by the claiming
  manager), runner entry/steps, inputs (staged; `required` by default when
  typed), parameters (knobs), `[workflow.environment.*]` (typed
  workspace-setting consumption), outputs (with `product_of` provenance),
  optional `[workflow.instantiate]`/`[workflow.collect]` hooks (Python or any
  `+x` executable speaking the JSON envelope), and `[workflow.postprocess.NAME]`
  curated scripts — the whole directory is installed into the workspace's
  `workflows/` store (`httk workflow install --workspace WS DIR`, or
  `job new --workflow-dir DIR --install`) and pinned by its tree digest
  (`docs/httk-workflow/workflow_packages.md`).
- **Compiled workflows** declare `[workflow.build]` (a one-liner `command`,
  optional `platform` probe, `artifacts` globs): the installed tree digest
  covers SOURCES only. `workflow install` builds for the installing machine's
  platform, and the user runs `httk workflow build --workspace WS NAME` once on
  each other platform (per platform class on heterogeneous clusters) to build
  and register the binaries — managers never compile; a job whose workflow is
  not built for a manager's platform stays `ready` and unclaimed there, and
  `job why`/`precheck` name the build to run. Installing on a remote
  (`--workspace kappa:runs`) builds there.
- **Composing workflows**: a package declares what it calls in
  `[workflow.calls]` (`relax = "vasp.relax"`, or a git URI pinned to a full
  commit); installing the package installs its calls too, and a manager claims
  a job only when the whole call graph is installed. A step calls by alias —
  `a.call("relax", label="relax", files={"POSCAR": path})` then
  `a.gather("after_relax")`, reading the child's `a.children["relax"].data` /
  `.workdir` in the gathered step (Bash: `httk_workflow_call LABEL ALIAS
  --file NAME=PATH`). An undeclared or uninstalled workflow is refused at the
  call, and an ad hoc runner file declares no calls.
  File plumbing between calls is explicit; declarations are provenance, not
  wiring (`docs/httk-workflow/details/composing_workflows.md`). `scaffold_job()` is
  `new_job()` stopped short of submission (a payload directory for `spawn`).
- **Runners in other languages**: the SDK exists in Python, Bash, C, Fortran,
  Perl, Ada, C++, Java, and Rust (`docs/httk-workflow/sdks/`) — the native
  SDKs are bridge clients with identical semantics. Interpreted runners
  transfer as-is; compiled single-file runners are architecture-bound (use the
  package + `[workflow.build]` form for portability).
- **Existing workflow languages**: a manifest (or bare document with
  `--format cwl|pwd|jobflow|httk-v1`) runs CWL, Python Workflow Definition,
  jobflow/atomate2 (`maker = "atomate2…:RelaxMaker"`, with real DAG
  parallelism as child jobs), or converted httk v1 template packages without
  rewriting (`docs/httk-workflow/workflow_compat.md`).
- **Finished v1 trees**: `httk v1 collect --workflow-dir PKG ROOT...`
  harvests already-computed v1 runs (`docs/httk-workflow/details/v1_compatibility.md`);
  this is the only v1 surface to recommend.

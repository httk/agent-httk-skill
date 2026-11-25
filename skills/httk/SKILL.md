---
name: httk
description: >-
  Work with the high-throughput toolkit (httk₂) to prepare and run large-scale
  distributed computational projects, and to analyze, store, and disseminate
  the results.
---

# httk₂ — the high-throughput toolkit

httk₂ is a modular Python (3.12+) toolkit for computational materials science:
preparing, running, storing, analysing, and serving atomistic calculations at
scale. It is distributed as a family of packages sharing the `httk` namespace:

| Package | Import | What it gives you |
| --- | --- | --- |
| httk-core | `httk.core` | contracts and shared vocabulary: exact math, vectors, datastreams, records, registries, `load`/`save`/`fetch` (stdlib-only) |
| httk-atomistic | `httk.atomistic` | crystal structures: cells, sites, species, symmetry/ASU, trajectories, ASE/pymatgen/VASP integrations, and file formats (CIF/mCIF, POSCAR, OUTCAR, XDATCAR, OSZICAR, EIGENVAL, POTCAR, WAVECAR, trajectory JSONL), HPKOT band paths |
| httk-store | `httk.store` | data management: SQL stores (SQLite/DuckDB/PostgreSQL/ClickHouse) and MongoDB, validation, query, federation, versioning + named alternative representations, provenance serving, remote OPTIMADE client (`httk.store.optimade`) |
| httk-workflow | `httk.workflow` | campaigns: projects, workspaces, runners, remotes/HPC, transfers, collection |
| httk-analyse | `httk.analyse` | analysis: convex hulls (`generic`); phase diagrams, equations of state, elasticity, phonons, MD, electronic properties, defects, MLIP validation (`matsci`); results as typed definition-bound records |
| httk-serve | `httk.serve` | dissemination: websites (`httk.serve.web`) and a generic OPTIMADE server (`httk.serve.optimade`) |

`pip install httk2` installs the standard set, including serving. Simulation-code
support is separate: `httk-workflow-{abinit,cp2k,gromacs,lammps,orca,phonopy,qe,vasp}`
(namespace `httk.codes.<code>`; phonopy needs vasp). Only vasp is on PyPI
(`pip install httk-workflow-vasp` or `"httk2[vasp]"`); install the others with
`pip install "httk-workflow-<code> @ git+https://github.com/httk/httk-workflow-<code>"`.
Metapackage name is ASCII `httk2`; the project is written *httk₂* in prose.

`workspace` and `job` are top-level CLI groups. Except for `workspace forget`
and `workspace delete`, workspace commands resolve the enclosing
`.httk-workspace/` found by walking up from the current directory, then the
project default and registry default; pass an explicit workspace when operating
elsewhere.

## How to help — task routing

- **"Run calculations / a campaign / on a cluster"** → read
  `references/campaign.md`. For a confined file-mounted Slurm broker (exchange directory), also read
  `references/workspace-daemon.md`. This is the toolkit's center of gravity:
  project →
  workspace → jobs → (remote) → run → monitor → transfer back → collect →
  analyse. A short version is below.
- **"Find/install a workflow (VASP or otherwise) / write a workflow
  package / what does `requires`/`command` do"** → `references/workflows.md`:
  the four workflow repositories (VASP, atomate2, other languages, examples),
  referencing by git URI, install/uninstall (also a whole repository, or by
  `pip install` of a clone), and the manifest essentials.
- **"Load/convert/write a structure file"** → `httk.core.load(path)` returns the
  file's native representation; expand with view constructors
  (`UnitcellStructureView(load("x.cif"))`); `httk.core.save(obj, path)` writes.
  Details: `references/modules.md` (httk-atomistic section).
- **"Store results / build a database / validate / provenance / multiple
  representations of one entry (conventional vs primitive cells)"** →
  `references/data-serving.md` (httk-store). Start with `SqliteStore` or the
  appropriate concrete store; query through `search.results(...)`. For a small
  served dataset, see its `DataEntryRecord` / `@entry_record` example and the
  note about matching development versions.
- **"Phase diagram / convex hull / stability"** → `references/modules.md`
  (httk-analyse section).
- **"Summarize / triage many jobs or entries"** → *Working at scale* below:
  one script that aggregates, not one call per item.
- **"Serve an OPTIMADE API / build a website"** → `references/data-serving.md`
  (httk-serve). To start a *new website project*, copy the
  `example_website_httk` repository as the template. To create a *new
  httk-style module*, instantiate `httk-module-template`.
- **"How is httk₂ designed / why does X behave this way"** →
  `references/architecture.md` (guiding ideas, backend/view pattern, exact
  numerics, registries).
- **legacy httk v1**: out of scope except the v2 compatibility layer —
  converted v1 template packages run as `format = "httk-v1"` workflow
  packages, `httk v1 collect` harvests finished v1 trees, and
  `httk project import-v1` / `httk remote import-v1` migrate v1
  projects and computer bundles. Do not recommend v1 APIs.

## The five-minute campaign (local)

From an empty directory containing a VASP-5 `POSCAR` (with
`pip install "httk2[vasp]"` or `pip install httk-workflow-vasp` installed):

```console
$ httk project init --name myproject .
$ httk workspace init --name default workspace
$ httk job new 'git+https://github.com/httk/workflows-vasp#vasp-relax' --install --input structure=POSCAR --tag silicon
$ httk workspace set -w default vasp.command=vasp_std
$ httk run
$ httk collect
```

`vasp.command` names only the program; the attempt's launch prefix (`HTTK_WORKFLOW_LAUNCH`) supplies the parallel start.

A job runs only a workflow installed in its workspace: `job new --install`
installs the relaxation workflow there first (`httk workflow install --workspace
WS URI` does it on its own; `httk workflow fetch URI` only fetches into the
machine cache), and the job pins the installed commit and digest (upgrading
httk cannot change queued jobs); `run` drives every job
until idle; `collect` prints one JSON `CollectedJob` summary per finished job
(`--raw` emits mechanical `JobRecord` summaries). `httk collect DIR --into results.sqlite --id-base BASE` also
collects a tree of finished calculations that were *not* run through httk:
collectors registered by the installed `httk-workflow-<code>` distributions
(vasp, qe, abinit, cp2k, orca, gromacs, lammps, phonopy; a code's collectors
exist only once its distribution is installed) recognize each calculation directory; `--dry-run` lists what would be
collected. Packaged VASP workflows keep
results in the persistent `run/` workdir by default; add
`--parameter publish_data=true` to `job new` when a curated `data/` copy is also
required.

`job new` takes either a positional `SOURCE` (a workflow installed in the
workspace, by id or short name; with `--install`, a git URI, known name or
package directory is installed first; a single-file Python or Bash runner is
installed ad hoc) or `--command 'srun
my_executable {n}'` (wrap one command line as a one-step workflow, installed ad
hoc; `{n}` is filled from `--parameter n=…`). Inputs:
`--file NAME=PATH` stages one file and `--files DIR` every file of a directory
(e.g. INCAR/KPOINTS/POSCAR/POTCAR); both land in the job's `files/` and are
copied into the working directory before the command runs. For a
plain "run this program N times through SLURM" task, `--command` plus a
`slurm` launcher is the whole recipe — see the vendored `launchers.md`.
Add `--embed-workflow` to keep the workflow in the job's own `workflow/` instead
of installing it in the workspace (see `references/workflows.md`).
Workers can enforce per-job and per-step resource requirements; start them with
capacities such as:

```console
httk run --workers 4 \
  --worker-resource procs 32 --worker-resource mem 128000 \
  --worker-resource matlab_license_slots 2
```

See `references/campaign.md` for manifest and dynamic-resource declarations.
Monitor with `job list`, `job show JOB`, `job why JOB` (explains a stuck job),
`job debug --workspace WS JOB` (foreground single-job loop), or interactively with
`httk monitor` (a paged terminal UI over local and remote workspaces —
counts per state, job pages, details, cancel/pause/resume, transfer, removal;
scales to 100k-job workspaces; `job list --json --limit N --after CURSOR` is the
same paged data path for scripts). `JOB` is a job UUID, `tag--uuid` key or
unique prefix of either, or an in-workspace path or glob; a job directory moves
between `jobs/<state>/` trees with its state, so from the project root after the
quickstart `workspace/jobs/succeeded/silicon*` names the finished job. Change a
job's course with `httk job cancel|pause|resume|restart JOB…` (`--reason TEXT` is
optional) and `httk job set JOB… priority=N step=STEP workflow=NAME@REF
budget.max_attempts_per_activation=N budget.max_total_attempts=N
budget.max_activations=N` (budgets accept `unlimited`, to go beyond the declared
retry limits; `workflow=` switches jobs to another installed version of the same
declared workflow, with `--state ready`; not via the daemon). A failed or paused job keeps its files
(edit all but `job.json` first; `job why JOB` names the remedy): `resume`
puts a `dependency_failure` parent back to waiting on its children (no new
attempt, no budget used) and otherwise reruns the step as a new attempt;
`restart` always reruns the step as a new attempt (a parent reuses its children
by label, so it refuses while one is failed or cancelled: `resume --tree` the
parent or delete the child, or `--force`); a revived step reruns from its top, so edit the file it reads from. Revivals
restore the declared retry allowance automatically (`--keep-budget` opts out).
See `references/docs/httk-workflow/restarting_jobs.md`.
Remove terminal or paused jobs with `httk job delete JOB…` (`--yes` skips only
the confirmation; a succeeded job needs `httk job unseal` first). Never `rm -r` a
job directory: a manager may hold it at that moment. VASP workflow packages
(`vasp.relax`, `vasp.relax-bash`, `vasp.static`, `vasp.relax-static`, the
property workflows through `vasp.full-characterization`; `atomate2.*` in
`workflows-vasp-atomate2`) are not
built in — they live in workflow repositories and are installed into
each workspace that runs them, by `job new --install` (as above) or
`httk workflow install --workspace WS URI`; after that the short name resolves.
See `references/workflows.md`.

For a cluster campaign, configure the workspace's manager launcher first; use
a remote only when transport to another machine is needed. For the full
remote/HPC path (`kappa:runs` colon workspaces, `push`/`pull`/`job move`, `campaign`
partitioning, Python `new_jobs` streaming, `collect --into` a store), follow
`references/campaign.md`. For the confined `mount-daemon` workflow, including
identity keys and exchange-directory job eject/adopt, see
`references/workspace-daemon.md`.

## Working at scale: script it, don't chain it

When a task spans many jobs, store entries, or OPTIMADE results, do not issue
one CLI call per item and read each full output. Write one short Python (or
shell) script that loops, filters and aggregates, and print only the summary
the user needs: counts, a table of the interesting rows, the few job keys that
need action. The bulk of the data should never reach the conversation.

- **Use the machine-readable output.** Most `httk` commands take `--json`;
  parse it instead of scraping text. For workspaces, `job list --json` returns
  `jobs` (rows with `job_key`, `job_id`, `state`, `step`, `phase`,
  `placement`, …) and `next_after`. Pass `next_after` to `--after` with a
  `--limit` until it is null. Paging is weakly consistent, so deduplicate by
  `job_id`. Filter with `--state`, `--step`, `--tag-contains` rather than
  fetching everything; `--counts` gives per-state totals. The same loop works
  for a remote workspace (`--workspace kappa:runs`).
- **Query stores through the searcher, not by dumping tables.** Declare only
  the outputs you need in `search.results(...)`; rows are lazy, so unused
  fields are never loaded. Use `search.count()` when only the number matters.
- **Print aggregates, then drill down.** Report the shape first (how many
  failed, at which step; how many entries per chemical system) and inspect
  individual jobs (`job show`, `job why`, `job log`) or records only for the
  handful the summary points at.
- **Keep actions out of bulk loops unless the user asked.** Reading and
  summarizing in a loop is safe. Cancel, delete, restart, `job set` and
  transfers change state: list the affected jobs and confirm before running
  them over a batch.

Tally a large workspace by state and step:

```python
import json, subprocess
from collections import Counter

seen, tally, after = set(), Counter(), None
while True:
    cmd = ["httk", "job", "list", "--workspace", "default", "--json", "--limit", "1000"]
    if after:
        cmd += ["--after", after]
    page = json.loads(subprocess.run(cmd, check=True, capture_output=True, text=True).stdout)
    for job in page["jobs"]:
        if job["job_id"] not in seen:
            seen.add(job["job_id"])
            tally[job["state"], job["step"]] += 1
    after = page["next_after"]
    if after is None:
        break
for (state, step), n in tally.most_common():
    print(f"{n:7d}  {state:12s}  {step}")
```

Summarize a store without materializing records (`Result` and its fields are
illustrative; use the stored record class's own):

```python
from collections import Counter

search = store.searcher()
v = search.variable(Result)
search.add(v.energy_above_hull <= 0)
per_system = Counter(row.system for row in search.results(system=v.chemical_system))
print(search.count(), "stable entries in", len(per_system), "systems")
for system, n in per_system.most_common(10):
    print(f"{n:5d}  {system}")
```

## Core ideas to keep in mind (details: references/architecture.md)

- **Exact by default.** Structures hold exact rational/surd numbers
  (`FracVector`, `SurdVector`, `Fraction`); nothing is lossy behind the user's
  back. Floats appear only at explicit presentation boundaries
  (`.to_floats()`, `float()`, the `Numeric*` layer, OPTIMADE records).
- **Backend/View.** A backend owns the original data; views present it through
  other interfaces, lazily, and round-trips recover the original backend
  exactly. Class construction *is* the conversion idiom:
  `UnitcellStructureView(asu_structure)` — there are no `to_X()`/`from_X()`
  methods. `unwrap` recovers the backend, `unview` sheds to a plain value.
- **Immutable by default** unless the class name starts with `Mutable`.
- **Contracts in core, capabilities in modules.** `httk.core` is stdlib-only
  and holds shared vocabulary; anything that *does* work lives in a module.
- **One entry point for files:** `httk.core.load(path)` / `save(obj, path)` /
  `fetch(url)` with transparent compression (`.gz`/`.bz2`/`.xz`) and a
  registry of readers/writers modules extend.
- **OPTIMADE definitions are the semantic vocabulary** for properties and entry
  types across storage and serving; content ids are storage identity only —
  public entry ids, immutable ids, and alternative ids are a separate,
  store-minted identity axis.

## Documentation

- **Online (authoritative, versioned):** https://docs.httk.org — aggregate
  reference at the root, per-module subsites at `/httk-core/`,
  `/httk-atomistic/`, `/httk-workflow/`, etc.
- **Offline (this skill):** `references/docs/<repo>/` holds a snapshot of each
  module's narrative documentation (Markdown), with each module's example
  pages merged into one `examples.md`. Grep it freely — e.g. the
  complete CLI tree is `references/docs/httk-workflow/workflow_cli.md`, runner
  authoring is `runtime_helpers.md`, the normative on-disk workspace protocol
  (job directories as tokens, owners and the death proof, commits, operator
  requests, confined launches, eject/adopt and transfer holds, the exchange and
  its daemon mailbox) is
  `references/docs/httk-workflow/details/workflow_filesystem_api.md`, storage is
  `references/docs/httk-store/db.md`. The remote OPTIMADE client is documented
  under `references/docs/httk-store/details/db-optimade-client.md`; the
  `httk-serve` client page is only a relocation note because the client belongs
  to *httk-store*. The snapshot is refreshed with `make docs-snapshot` from a
  workspace checkout and may trail the online docs; when the two disagree, the
  online docs win.
- The curated files under `references/` (architecture, modules, campaign,
  workflows, workspace-daemon, data-serving) are the distilled, stable layer — start there, drop into the
  snapshot or online docs for exhaustive detail.

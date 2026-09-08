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
| httk-atomistic | `httk.atomistic` | crystal structures: cells, sites, species, symmetry/ASU, trajectories, ASE/pymatgen/VASP integrations, and file formats (CIF/mCIF, POSCAR, OUTCAR, XDATCAR, OSZICAR, POTCAR, WAVECAR, trajectory JSONL) |
| httk-store | `httk.store` | data management: SQL stores (SQLite/DuckDB/PostgreSQL), validation, query, federation, versioning + named alternative representations, provenance serving |
| httk-workflow | `httk.workflow` | campaigns: projects, workspaces, runners, remotes/HPC, transfers, collection |
| httk-analyse | `httk.analyse` | analysis: convex hulls (`generic`), phase diagrams + plotting (`matsci`) |
| httk-serve | `httk.serve` | dissemination: websites (`httk.serve.web`) and a generic OPTIMADE server (`httk.serve.optimade`) |

`pip install httk2` installs the standard set, including serving.
Metapackage name is ASCII `httk2`; the project is written *httk₂* in prose.

`workspace` and `job` are top-level CLI groups. Except for `workspace forget`
and `workspace delete`, workspace commands resolve the enclosing
`.httk-workspace/` found by walking up from the current directory, then the
project default and registry default; pass an explicit workspace when operating
elsewhere.

## How to help — task routing

- **"Run calculations / a campaign / on a cluster"** → read
  `references/campaign.md`. This is the toolkit's center of gravity: project →
  workspace → jobs → (remote) → run → monitor → transfer back → collect →
  analyse. A short version is below.
- **"Load/convert/write a structure file"** → `httk.core.load(path)` returns the
  file's native representation; expand with view constructors
  (`UnitcellStructureView(load("x.cif"))`); `httk.core.save(obj, path)` writes.
  Details: `references/modules.md` (httk-atomistic section).
- **"Store results / build a database / validate / provenance / multiple
  representations of one entry (conventional vs primitive cells)"** →
  `references/data-serving.md` (httk-store).
- **"Phase diagram / convex hull / stability"** → `references/modules.md`
  (httk-analyse section).
- **"Serve an OPTIMADE API / build a website"** → `references/data-serving.md`
  (httk-serve). To start a *new website project*, copy the
  `example_website_httk` repository as the template. To create a *new
  httk-style module*, instantiate `httk-module-template`.
- **"How is httk₂ designed / why does X behave this way"** →
  `references/architecture.md` (guiding ideas, backend/view pattern, exact
  numerics, registries).
- **legacy httk v1**: out of scope except the v2 compatibility layer —
  converted v1 template packages run as `language = "httk-v1"` workflow
  packages, `httk workflow v1 collect` harvests finished v1 trees, and
  `httk project import-v1` / `httk workflow remote import-v1` migrate v1
  projects and computer bundles. Do not recommend v1 APIs.

## The five-minute campaign (local)

From an empty directory containing a VASP-5 `POSCAR`:

```console
$ httk project init --name myproject .
$ httk workspace init --name default .
$ httk job new --workflow vasp-relax --input structure=POSCAR --tag silicon
$ httk workspace settings set --key vasp.command --value "srun -n 32 vasp_std" default
$ httk workflow run
$ httk workflow collect
```

`job new` publishes the packaged relaxation runner into the workspace and pins
its digest (upgrading httk cannot change queued jobs); `run` drives every job
until idle; `collect` prints one JSON `CollectedJob` summary per finished job
(`--raw` emits mechanical `JobRecord` summaries).
`job new` takes exactly one of `--workflow NAME` (a registered or packaged
workflow), `--workflow-dir DIR`, `--from-runner FILE` (a single-file Python or
Bash runner), or `--from-command 'srun my_executable {n}'` (wrap one command
line as a one-step workflow; `{n}` is filled from `--parameter n=…`). Inputs:
`--file NAME=PATH` stages one file and `--files DIR` every file of a directory
(e.g. INCAR/KPOINTS/POSCAR/POTCAR); both land in the job's `files/` and are
copied into the working directory before the command runs. For a
plain "run this program N times through SLURM" task, `--from-command` plus a
`slurm` launcher is the whole recipe — see the vendored `launchers.md`.
Workers can enforce per-job and per-step resource requirements; start them with
capacities such as:

```console
httk workflow run --workers 4 \
  --worker-resource procs 32 --worker-resource mem 128000 \
  --worker-resource matlab_license_slots 2
```

See `references/campaign.md` for manifest and dynamic-resource declarations.
Monitor with `job list`, `job show JOB`, `job why JOB` (explains a stuck job),
`job debug --workspace WS JOB` (foreground single-job loop), or interactively with
`httk workflow monitor` (a paged terminal UI over local and remote workspaces —
counts per state, job pages, details, cancel/pause/continue, transfer, removal;
scales to 100k-job workspaces; `job list --json --limit N --after CURSOR` is the
same paged data path for scripts). `JOB` may also be an in-workspace path or glob
(`jobs/silicon*`). Remove finished or queued jobs cleanly with `httk job delete JOB…`
(`--force` skips the confirmation and the join-parent guard); `rm -r` of a finished
job's directory is also fine — the next manager run or `workspace gc` clears its
marker. Registered VASP workflows:
`vasp-relax`, `httk.vasp.static`, `httk.vasp.relax-static`, `vasp-relax-bash`.

For a cluster campaign, configure the workspace's manager launcher first; use
a remote only when transport to another machine is needed. For the full
remote/HPC path (`kappa:runs` colon workspaces, `transfer`, `campaign`
partitioning, Python `new_jobs` streaming, `collect --into` a store), follow
`references/campaign.md`.

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
  module's narrative documentation (Markdown). Grep it freely — e.g. the
  complete CLI tree is `references/docs/httk-workflow/workflow_cli.md`, runner
  authoring is `runtime_helpers.md`, storage is
  `references/docs/httk-store/db.md`. The snapshot is refreshed with
  `make docs-snapshot` from a workspace checkout and may trail the online docs;
  when the two disagree, the online docs win.
- The curated files under `references/` (architecture, modules, campaign,
  data-serving) are the distilled, stable layer — start there, drop into the
  snapshot or online docs for exhaustive detail.

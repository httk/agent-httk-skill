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
| httk-atomistic | `httk.atomistic` | crystal structures: cells, sites, species, symmetry/ASU, trajectories, ASE/pymatgen/VASP integrations |
| httk-io | `httk.io` | file formats: CIF/mCIF, POSCAR, OUTCAR, XDATCAR, OSZICAR, POTCAR, WAVECAR, trajectory JSONL |
| httk-data | `httk.data` | data management: SQL stores (SQLite/DuckDB), validation, query, federation, provenance serving |
| httk-workflow | `httk.workflow` | campaigns: projects, workspaces, runners, remotes/HPC, transfers, collection |
| httk-analyse | `httk.analyse` | analysis: convex hulls (`generic`), phase diagrams + plotting (`matsci`) |
| httk-serve | `httk.serve` | dissemination: websites (`httk.serve.web`) and a generic OPTIMADE server (`httk.serve.optimade`) |

`pip install httk2` installs the standard set; `httk2[serve]` adds serving.
Metapackage name is ASCII `httk2`; the project is written *httk₂* in prose.

## How to help — task routing

- **"Run calculations / a campaign / on a cluster"** → read
  `references/campaign.md`. This is the toolkit's center of gravity: project →
  workspace → jobs → (remote) → run → monitor → transfer back → collect →
  analyse. A short version is below.
- **"Load/convert/write a structure file"** → `httk.core.load(path)` returns the
  file's native representation; expand with view constructors
  (`UnitcellStructureView(load("x.cif"))`); `httk.core.save(obj, path)` writes.
  Details: `references/modules.md` (httk-io, httk-atomistic sections).
- **"Store results / build a database / validate / provenance"** →
  `references/data-serving.md` (httk-data).
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
  `httk workflow v1 …` runs v1 task templates on the v2 engine, and
  `httk project import-v1` / `httk workflow remote import-v1` migrate v1
  projects and computer bundles. Do not recommend v1 APIs.

## The five-minute campaign (local)

From an empty directory containing a VASP-5 `POSCAR`:

```console
$ httk project init --name myproject
$ httk workflow workspace init . --name default
$ httk workflow job new --workflow vasp-relax --input structure=POSCAR --tag silicon
$ httk workflow workspace settings set vasp.command "srun -n 32 vasp_std"
$ httk workflow run
$ httk workflow collect
```

`job new` publishes the packaged relaxation runner into the workspace and pins
its digest (upgrading httk cannot change queued jobs); `run` drives every job
until idle; `collect` prints one JSON `JobRecord` summary per finished job.
Monitor with `job list`, `job show JOB`, `job why JOB` (explains a stuck job),
`job debug WS JOB` (foreground single-job loop). Registered VASP workflows:
`vasp-relax`, `httk.vasp.static`, `httk.vasp.relax-static`, `vasp-relax-bash`.

For a remote/HPC campaign (remotes, `kappa:runs` colon workspaces, `transfer`,
`campaign` partitioning, Python `new_jobs` streaming, `collect --into` a store)
follow `references/campaign.md`.

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
  types across storage and serving; content-addressed records give stable ids.

## Documentation

- **Online (authoritative, versioned):** https://docs.httk.org — aggregate
  reference at the root, per-module subsites at `/httk-core/`,
  `/httk-atomistic/`, `/httk-workflow/`, etc.
- **Offline (this skill):** `references/docs/<repo>/` holds a snapshot of each
  module's narrative documentation (Markdown). Grep it freely — e.g. the
  complete CLI tree is `references/docs/httk-workflow/workflow_cli.md`, runner
  authoring is `runtime_helpers.md`, storage is
  `references/docs/httk-data/db.md`. The snapshot is refreshed with
  `make docs-snapshot` from a workspace checkout and may trail the online docs;
  when the two disagree, the online docs win.
- The curated files under `references/` (architecture, modules, campaign,
  data-serving) are the distilled, stable layer — start there, drop into the
  snapshot or online docs for exhaustive detail.

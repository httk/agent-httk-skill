# httk₂ module map — what lives where, with entry points

## httk-core (`httk.core`) — stdlib-only foundation

Public root surface (~76 names). The ones users touch most:

- `load(path, **kw)` / `save(obj, dest)` / `fetch(url)` — universal file I/O
  with transparent `.gz`/`.bz2`/`.xz` handling; dispatch by extension or exact
  basename (`POSCAR`, `OUTCAR`, `WAVECAR`, …); `raw=True` returns the neutral
  payload instead of the domain object. `fetch` requires the explicit
  `DatastreamURL` consent for network sources.
- Exact numerics: `FracVector`, `MutableFracVector`, `SurdVector`,
  `SurdScalar`, `httk.core.exactmath` (sqrt/cos/sin/…, exact or
  correctly-rounded Decimal), `to_numeric`/`to_numeric_scalar`, `precision`
  helpers (`decimal_precision`, `combined_precision`).
- View grammar: `unwrap`, `unview`, `coerce_view`, `coerce`.
- Records/definitions: `Reference`, `File`, `Calculation`, `Run`,
  `ProductLink`, `DataRecord`, `PropertyDefinition`, `EntryTypeDefinition`,
  `load_entry_type_definition`, `register_definition_prefix`.
- Registries: `register_reader`, `register_writer`, `register_entry_provider`,
  `register_entry_family`, `register_entry_record`, `register_citation`.
- Datastreams: `TextstreamFileView`/`BytestreamFileView` etc. (open anything,
  decompress transparently), `DatastreamURL`.
- Storage author vocabulary: `StorageInfo`, `Indexed`/`Unique`/`Skip`/
  `IdentitySkip`/`Shape`/`Related`, `stored_property`, `content_id`.
- `DatasetLoader` — lazy packaged datasets for module authors.
- Subpackages (import directly, not re-exported): `httk.core.optimade`
  (OPTIMADE documents + filter parser), `httk.core.storage`,
  `httk.core.crypto`, `httk.core.report`, `httk.core.docs` (the versioned-docs
  tooling and `httk docs` CLI).
- Project anchor: `httk project init|show|import-v1`; `httk_project/`
  directory marks a project root (Ed25519 identity/trust).

## httk-atomistic (`httk.atomistic`) — crystal structures

- Root exports (~68 names): `UnitcellStructure`, `UnitcellStructureView`,
  `ASUStructure`, `ASUStructureView`, `Cell`, `CellView`, `CellParams`,
  `Sites`, `Species`, `Spacegroup`, `SettingTransform`, `recognize_asu`,
  `same_crystal`, `build_supercell`, `conventional_cell`, composition tools,
  `structure_tolerance`, trajectory family (`Trajectory`, `JsonlTrajectory`,
  …), `PlaneWaveFunctions` (WAVECAR wavefunctions, numpy), and conditionally
  `ASEAtomsView` / `PymatgenStructureView`.
- Loading is native-representation: `load("x.cif")` → `ASUStructure` (the
  file's declared symmetry), `load("POSCAR")` → `UnitcellStructure`,
  `load("OUTCAR"|"XDATCAR")` → `VASPTrajectory`. Expand/convert with view
  constructors.
- Integrations (`httk.atomistic.integrations.{ase,pymatgen,vasp}`): bridges
  follow *reject-don't-drop* — state a representation cannot encode raises.
  `VASPStructure("POSCAR")` is a lazy backend whose save round-trip is
  byte-exact via the raw channel. Neither ase nor pymatgen is a dependency.
- Symmetry tools in `httk.atomistic.symmetry` (spacegroups: all 527 tabulated
  settings vendored; xyz/xyzt symop parsing). spglib is optional (only needed
  to *recognize* symmetry, never to expand it).
- OPTIMADE serving layer in `httk.atomistic.entries`:
  `StructureEntryProvider` serves `structures` with auto-derived composition
  fields plus custom prefixed properties; `TrajectoryEntryProvider` serves
  `trajectories`.
- Extras: `httk-atomistic[numpy]` for the numeric layer, `[default]` for
  spglib.

## httk-io (`httk.io`) — file formats

Registered into `httk.core.load`/`save`; direct APIs also public:

- CIF/mCIF: `read_cif`, exact dual-channel payloads
  (`_httk_*_exact` companion tags preserve exactness through write/read);
  magnetic mCIF parsed to neutral payloads.
- VASP: POSCAR read/write (string-preserving, byte-exact `raw` round-trip),
  `OutcarFile` (lazy, streaming `frames()`, stress conventions via
  `stress_gpa_voigt()`), `XdatcarFile`, `read_oszicar`,
  `read_potcar_summary` (never retains POTCAR text — license), `VASPOutputs`
  (lazy directory composite), `WavecarFile` (lazy per-band coefficients;
  refuses compressed files), `write_vasp_volumetric` (VESTA-readable grids).
  OUTCAR/XDATCAR accept compressed input (streaming).
- Trajectory holding format: `httk-trajectory-jsonl` (OPTIMADE
  partial-data-compatible JSON Lines; streaming writer, lazy reader).
- numpy only via the optional `httk-io[numpy]` extra (WAVECAR).

## httk-workflow (`httk.workflow`) — campaigns and execution

See `campaign.md` for the end-to-end playbook. Summary of the model:

- **Project** (`httk project init`) anchors everything; **workspaces** hold
  jobs and state (machine-owned names; `NAME` local, `REMOTE:NAME` remote).
- **Workflows**: packaged providers (`vasp-relax`, `httk.vasp.static`,
  `httk.vasp.relax-static`), a single runner file
  (`--workflow ./my_runner.py`), or a **workflow package directory** with
  `workflow.toml` (declared inputs/outputs/parameters, hooks, any-language
  runner) — published content-addressed and digest-pinned per job.
- Lifecycle: **instantiate → run → collect**, with `postprocess` the
  workflow-owned substep of collect. *Inputs* are declared staged objects;
  *parameters* are opaque knobs (`--parameter k=v`, `Attempt.parameter()`).
- SDK: `Runner`/`Attempt` for authoring runners (`docs snapshot:
  runtime_helpers.md`, `native_bash_api.md` for Bash); `Workspace`,
  `new_jobs()` streaming job creation; `collect()` yields `CollectedJob`
  (outputs, provenance `Run`, products); `job_records()` the mechanical
  readout.
- `httk workflow import pwd|cwl` runs Python Workflow Definition / CWL
  workflows unmodified; `httk workflow v1 …` runs httk v1 task templates on
  the v2 engine (the only supported v1 surface).
- Provenance: `run_record(job_record)` → `httk.core.Run`; collect assembles
  provenance in the framework.

## httk-analyse (`httk.analyse`) — analysis

- `from httk.analyse.generic import LowerConvexHull` — immutable, exact-input
  tolerant generic lower convex hull: `hull_indices`, `value_above_hull`,
  supported segments, convex decompositions (deterministic simplex).
- `from httk.analyse.matsci import PhaseDiagram` — normalizes formulas or
  `StructureLike`s + total energies to atomic fractions and per-atom
  energies, delegates to `LowerConvexHull`, owns Matplotlib plotting (binary
  and higher-component).
- Depends on numpy + matplotlib by design. Import from the submodules; the
  root exports only `generic` and `matsci`.

## httk-serve (`httk.serve`) — dissemination

See `data-serving.md`. In one line each: `httk.serve.web` (Jinja2 sites,
widgets, static publishing, Starlette ASGI runtime — used by httk.org);
`httk.serve.optimade` (a generic OPTIMADE v1.3 protocol server fed by
`EntryProvider`s, plus `OptimadeStore`, a read-only client of remote OPTIMADE
APIs).

## Starting new things

- **New httk-style module** → instantiate `httk-module-template` (Makefile
  gates, PEP 639 packaging, docs with vendored inventories, registry
  self-registration stub, DatasetLoader + reporting examples).
- **New website** → copy the `example_website_httk` repository (an
  httk-serve site with table widgets, an OPTIMADE service over CSV+CONTCAR
  data, custom `_anyt_`-style property definitions — rename the prefix).

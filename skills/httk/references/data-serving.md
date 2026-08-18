# Data management, storage, and dissemination

## httk-store: stores and validation

### SqlStore — the backend-agnostic SQL store

```python
from httk.store import Backend, SqlStore
from httk.atomistic import UnitcellStructure  # families register their records

store = SqlStore(Backend.sqlite("results.sqlite"),   # or Backend.duckdb(...)
                 entry_records={...})                  # family → record classes
sid = store.save(structure)
back = store.fetch_by_content_id(UnitcellStructure, cid)
```

- Built on SQLAlchemy Core; SQLite, DuckDB, and PostgreSQL supported (plus a
  MongoDB backend — see `docs/httk-store/mongo.md`); bulk loads via
  `store.bulk_ingest()` (optionally `workers=N` for parallel encoding)
  (`httk-store[duckdb]` / `httk-store[postgresql]`). Domain objects stay
  ordinary frozen dataclasses; the store consumes their declared record classes.
- The `entry_records` declaration is **required on first open**, stamped into
  the store, and **trusted on reopen** (byte-identical check; a mismatch
  raises `StorageLayoutUpgradeRequiredError` — rebuild, no migration).
- DDL happens only on write; read paths treat missing tables as empty.
- Identity: `content_id` (content addressing) + local integer `sid`;
  duplicate saves dedup exactly, with metadata-conflict detection.
- Append-only versioning: every row carries a `logical_id` lineage.
  `store.replace(predecessor, obj)` saves a successor sharing that lineage
  (nothing is updated or deleted), `store.history()` walks a lineage
  oldest-first, and `searcher(only_latest=True)` restricts roots to the latest
  row of each. Store-managed timestamps + `searcher(as_of=T)` historic search
  are on by default.
- Queries: the neutral query layer (`httk.store.query`) — expressions,
  portable queries, OPTIMADE filter *translation*
  (`httk.store.query.optimade_filters`) — plus `Searcher`/`Store` protocols
  every backend implements.
- Federation: `FederatedStore` (live fan-out over already-open stores,
  read-only union) vs `httk.store.backend.sql.stored_federation` (a persisted registry of
  (store, family, prefix) sources with audits). `searcher(as_of=, only_latest=)`
  are forwarded to every child; a child without store timestamps raises
  `FederatedSourceError` on `as_of` rather than silently serving current state.

### Validation and provenance serving

- `validate_property(definition, value)` / `validate_record(entry_type,
  record)` — jsonschema (Draft 2020-12) validation built directly from
  OPTIMADE property definitions; fully offline; raises
  `PropertyValidationError`.
- In-memory `EntryProvider`s for the standard `references`/`files`/
  `calculations` entry types, plus `RunEntryProvider`/`DataRecordEntryProvider`
  serving provenance (`_httk_runs`/`_httk_records`) with relationships derived
  from run edges, and `product_relationships()` for data→data product links.

## httk-serve: the OPTIMADE server

`httk.serve.optimade` is a **generic OPTIMADE v1.3 implementation** with no
materials knowledge: everything served comes from `EntryProvider`s.

```python
from httk.serve.optimade import adapter_from_providers, create_asgi_app, serve
from httk.atomistic.entries import StructureEntryProvider

provider = StructureEntryProvider(structures)   # or None-entries, custom props
adapter = adapter_from_providers([provider])
serve(adapter, port=8080)                       # development server …
app = create_asgi_app(adapter)                  # … or uvicorn/hypercorn ASGI
```

- Providers describe themselves with `EntryTypeDefinition`s; custom prefixed
  properties (`_myprefix_*`) are validated against extended definitions;
  register your prefix with `httk.core.register_definition_prefix`.
- Filtering, pagination, relationships (`include=`), versioned/unversioned
  base URLs, and `meta.warnings` (from the httk report channel) are handled by
  the engine. Mount-aware links; CORS strictly opt-in via
  `OptimadeConfig(cors_origins=(...))`.
- `--validate`-style checking: run `httk.store.validate_record` over records
  before serving (see the `example_website_httk` repo's `serve_optimade.py`
  for a complete worked service: CSVs + CONTCAR.bz2 → exact structures → 180
  served entries with custom properties and linked references).
- Serve a store directly with `StoreEntryProvider` (registered as
  `store-db-store`): each record also exposes its lineage as the integer
  property `_httk_logical_id`, filterable like any field; pass
  `only_latest=True` to serve only the latest row of each lineage.
- `OptimadeStore` is the read-only *client*: point it at any OPTIMADE API and
  query it through the same neutral Store/Searcher protocols; combine remote
  and local stores with `FederatedStore`.

## httk-serve: websites

`httk.serve.web` (`from httk.serve.web import publish, serve,
create_asgi_app`) is the site engine behind httk.org:

- Jinja2 templating with RST/Markdown renderers; static publishing
  (`publish`) or a live Starlette app (`serve`).
- **Widgets**: reusable trusted components invoked as one literal-only content
  line — `{{ widget("httk.serve.table", provider="site.results") }}`. The
  table widget pages through a site-provided backend (opaque cursors, signed
  expiring state tokens; set `HTTK_SERVE_WEB_TABLE_TOKEN_SECRET` in
  multi-worker deployments). `httk.serve.optimade_table` is a browser-side
  widget that queries any OPTIMADE API directly.
- **To start a new site**: copy the `example_website_httk` repository — it
  contains a working site + data model (httk-store `SqlStore`-backed with
  in-memory fallback), the search table wired to the widget, per-material
  detail pages, plot-file records, custom OPTIMADE property definitions in
  YAML (rendered to JSON), and an optional combined mount of the site plus
  the OPTIMADE app.

## Dissemination via files

- `httk.core.save(obj, "structure.cif")` — CIF written with dual-channel
  exactness (standard tags are valid decimals; `_httk_*_exact` companions
  carry exact values and win on re-read). POSCAR round-trips byte-exactly via
  the raw channel when the source was a POSCAR.
- Trajectories: `save(traj, "run.traj.jsonl")` streams to the
  `httk-trajectory-jsonl` holding format (frames are never stored in
  databases — records hold summaries + a source locator).
- Compressed destinations (`.cif.bz2`, …) compress transparently.

# Data management, storage, and dissemination

## httk-store: stores and validation

### SqlStore — the backend-agnostic SQL store

```python
from httk.store import Backend, EntryIdScheme, SqlStore
from httk.atomistic import StructureEntry, UnitcellStructure, UnitcellStructureRecord

structure = UnitcellStructure(
    cell=[[5, 0, 0], [0, 5, 0], [0, 0, 5]],
    sites=[[0, 0, 0]], species_at_sites=["Si"],
)
backend = Backend.sqlite("results.sqlite")  # or Backend.duckdb(...)
store = SqlStore(backend, entry_records={StructureEntry: UnitcellStructureRecord},
                 entry_ids=EntryIdScheme("example", "structures"))
sid = store.save(structure)
back = store.fetch(UnitcellStructureRecord, sid)
assert back.id == "example-structures-1"
backend.dispose()
```

- Built on SQLAlchemy Core; SQLite, DuckDB, PostgreSQL, and ClickHouse supported (plus a
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
- Public identity (supply explicit IDs or declare `entry_ids=EntryIdScheme(...)`
  when writing entry records): the
  store mints an `id` shared across a lineage plus a per-row `immutable_id`
  `<id>~<n>`. Content ids are storage identity only — this is a separate axis
  (the old "id property returns content_id" behaviour is gone).
- `IdLedger` (`httk.store.id_ledger`): the signed, append-only id ledger that
  maps a stable opaque source key to a public id forever — `assign`/`alias`/
  `lookup`, plus `bindings()` (a full snapshot enumeration, key → id/family/
  is_alias) and `IdLedger.open(..., read_only=True)` (lock-free, verification
  intact, mutators refuse) for reporting alongside a live writer. Key
  convention: an intrinsic identity key (e.g. `run:<source_id>`) plus binding
  keys aliased onto the same id when other sources dedup onto that row.
- Alternatives: `store.save(obj, alternative_of=<main id>, alternative_kind=…)`
  saves a named sibling representation (a `conventional`/`primitive` cell beside
  the main) sharing the main's `id`, with its own lineage and composite ids
  `<id>~<kind>[~<n>]`; both args are required together, one kind per group, and
  bulk ingest saves mains only.
- **Mains-only is the silent default:** `searcher()` sets `only_main_alt=True`,
  so ordinary *and* revision queries never surface saved alternatives (nor do
  their revisions enter a revision stream) — pass `only_main_alt=False` to
  include them.
- Queries: the neutral query layer (`httk.store.query`) — expressions,
  portable queries, OPTIMADE filter *translation*
  (`httk.store.query.optimade_filters`) — plus `Searcher`/`Store` protocols
  every backend implements.
- Federation: `FederatedStore` (live fan-out over already-open stores,
  read-only union) vs `httk.store.backend.sql.stored_federation` (a persisted registry of
  (store, family, prefix) sources with audits). The stored federation serves and
  filters relationships (exposed weak links + `StrongLink` run edges both
  directions); Mongo-backed federation sources serve none (empty per-row
  relationships channel). `searcher(as_of=, only_latest=)`
  are forwarded to every child; `only_main_alt` is *not* a `FederatedStore`
  searcher parameter, so each child applies its own mains-only default. A child
  without store timestamps raises `FederatedSourceError` on `as_of` rather than
  silently serving current state.

### Validation and provenance serving

- `validate_property(definition, value)` / `validate_record(entry_type,
  record)` — jsonschema (Draft 2020-12) validation built directly from
  OPTIMADE property definitions; fully offline; raises
  `PropertyValidationError`.
- In-memory `EntryProvider`s for the standard `references`/`files`/
  `calculations` entry types, plus `RunEntryProvider`/`DataRecordEntryProvider`
  serving provenance (`_httk_runs`/`_httk_records`). Run edges serve as semantic
  relationships in **both** directions — forward `_httk_has_*` on runs, derived
  reverse `_httk_is_*` on targets — from the SQL and Mongo `StoreEntryProvider`
  and the stored federation alike. `product_relationships()` emits a
  forward-only `_httk_has_product` (provider path only, no reverse).

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
- Default responses (no `response_fields`) omit unknown-valued (null)
  properties unless the definition marks them response-level `must`/`always`
  — spec-conformant; an explicit `response_fields` always serves the requested
  set with nulls kept.
- `adapter_from_stores(..., default_includes={served_type: (entry types...)})`
  sets each served type's default `include` for single-entry responses
  (`references` is always unioned in); an explicit `include=` (even empty)
  overrides it, and a list response is unaffected.
- `_httk_relationships.<key>.id` is a filter-grammar extension (not a property —
  no `/info` entry, not sortable) for filtering by any served relationship key,
  the semantic provenance keys included. `HAS` family only (`HAS`/`HAS ALL`/
  `HAS ANY`/`HAS ONLY`); an unknown own-prefix key is a `400`.
- `--validate`-style checking: run `httk.store.validate_record` over records
  before serving (see the `example_website_httk` repo's `serve_optimade.py`
  for a complete worked service: CSVs + CONTCAR.bz2 → exact structures → 180
  served entries with custom properties and linked references).
- Serve a store directly with `StoreEntryProvider` (registered as
  `store-db-store`): each record also exposes its lineage as the integer
  property `_httk_logical_id`, filterable like any field. It serves mains only
  (alternatives never appear) and, by default, the latest row of each lineage
  (`only_latest=True`); `only_latest=False` requires an `id_of` override to keep
  served ids unique across revisions. `StrongLink` reverse edges are matched by
  raw id, so a provider with a custom `id_of` mapping gets empty reverse blocks.
- Store-backed adapters also expose revision and alternative sub-endpoints:
  `/<entry>/<id>/_httk_revs[/<n>]` and `/_httk_<entry>~revs[/<immutable_id>]`
  list revisions (resource `id` is the immutable id `<id>~<n>`, `_httk_id` the
  shared lineage id); `/<entry>/<id>/_httk_alts[/<kind>]` and
  `/_httk_<entry>~alts[/<id>~<kind>]` list named alternatives at their latest
  revision per kind (composite `id` `<id>~<kind>`, plus filterable/sortable
  `_httk_id` and `_httk_kind`). Both families are store-backed only.
- `OptimadeStore` (imported from `httk.store.optimade` — it is a *httk-store*
  capability, not a serving one) is the read-only *client*: point it at any
  OPTIMADE API and query it through the same neutral Store/Searcher protocols;
  combine remote and local stores with `FederatedStore`. Provider-prefixed properties
  (`_prefix_name`) resolve in filter/sort expressions and as scalar output
  projections, including on a generic (unregistered) entry type; an absent
  attribute projects as `None`. A pandas-style bracket layer rides on top:
  `store.slicer("<entry type>")` gives masks (`mats[mats["_x"] > 0.5]`),
  `len()` counts server-side, and selections project columns
  (`hits[["id", "_x"]]` yields named rows); it deliberately offers no
  sorting -- use the searcher for that.
- Relationships use one `links` namespace, shared by the local stores and the
  remote client. `v.links.<name>.<field> ...` is a depth-1 relationship filter
  predicate; `v.links.<name>` is a set-valued `results()` output (each matched
  row yields a tuple of related records); and every returned record exposes
  `record.links.<name>` to walk one hop further. The remote client auto-adds the
  `include=` its link outputs need, resolves them from the response, and fetches
  by id only when a provider did not include them — there is no separate
  `include()`/`related()` call. Store-side link outputs cover weak links; the
  remote client's `links` also spans reference-field and `StrongLink`
  relationships (`StrongLink` wire keys resolve as outputs but are not
  field-chainable in filters).

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
  widget that queries any OPTIMADE API directly: its filter/sort pills are
  individually removable (×); a `summary` field's `clears: [url params]` makes
  removing its pill also clear those host-form params; sort is tri-state —
  absent means the authored default, an explicit empty `sort=` means store
  order, and the authored default itself renders as a removable pill.
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

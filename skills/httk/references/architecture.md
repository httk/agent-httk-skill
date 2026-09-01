# httk₂ architecture — guiding ideas and central classes

## Layering: contracts in core, capabilities in modules

`httk` is a PEP 420 namespace package; by itself it provides nothing. The core
functionality lives in **httk-core** (`httk.core`), which is deliberately
lightweight and **stdlib-only**: it holds the shared *vocabulary* used in
cross-module signatures — the vector family, the datastream families, the
property/entry-type definition model, record models, registries, and the
blessed `DatasetLoader` for modules that ship static data. Anything imported to
**declare** (types in signatures across module boundaries) goes in core;
anything imported to **do** goes in a capability module (structures and file
parsing in httk-atomistic, storage in httk-store, serving in httk-serve,
execution in httk-workflow).
Modules register their capabilities under reserved registry tiers
(`httk.registry.{cli,entries,io,schemas}.<module>`), discovered automatically
at `import httk.core`.

## Backend/View — the one data-representation pattern

Every representation family follows the same grammar: an abstract `*API`
declares the interface, a **backend** owns the original representation and
data, and **views** expose that backend through other public interfaces.

- **Views are lazy**: constructing a view converts nothing; data converts on
  request.
- **Round-trips are exact**: building View B from View A and going back
  recovers the *original backend object*, even if B presented an
  approximation.
- **Class construction is the conversion idiom**: `CellView(cell_like)`,
  `UnitcellStructureView(anything_structure_like)`. There are no
  `to_X()`/`from_X()` methods between httk classes.
- **Domain classes are their own backends** (folded form): `UnitcellStructure`
  *is* a `StructureBackend`; a view named `XView` presents an `X`.
- The four verbs (exported from `httk.core`): `unwrap(x)` recovers the
  backend; `unview(x)` sheds the view wrapper to a plain presented value;
  `coerce_view(cls, x)` is backend-aware coercion; `coerce(cls, x)` strictly
  returns a non-View instance of the target or raises `TypeError`.

## Exact by default

Never perform a lossy conversion behind the user's back. The exact numeric
stack, all in `httk.core`:

- **`FracVector`** — immutable N-dimensional tensors of exact rationals
  (nested integer numerators over one shared denominator); all algebra exact;
  `MutableFracVector` is the mutable variant.
- **`SurdVector`/`SurdScalar`** — the squarefree-radical field
  ℚ[√n]: exact hexagonal bases, exact `det`/`inv`/lengths; `sqrt` closed over
  positive rationals; exact degree-mode trig for the 15°/36° angle families.
- **`exactmath`** (`httk.core.exactmath`) — type-preserving exact
  transcendentals: results are `Decimal` iff any input is `Decimal` or
  `digits=` is passed, else exact `Fraction`; `exact=True` returns surds.
- **The vector family** — kinds `"frac"`/`"surd"`/`"native"`/`"numpy"` with a
  `Fraction`-based exact interchange hub; `VectorNumpyView(ndarray)` is
  zero-copy adoption; numpy ops shed the view. `to_numeric(x)` is the
  numpy-only convenience presentation (requires the `[numpy]` extra).

Floats appear only at explicit presentation boundaries: `.to_floats()` on any
vector, `float()` on exact scalars, the `Plain*View`s, the `Numeric*` layer
(numpy, eager `ImportError` without the extra), and OPTIMADE records.
**Immutable by default**: treat everything as immutable unless the class name
begins with `Mutable`.

## Structures (httk-atomistic essentials)

- `UnitcellStructure` = `cell` / `sites` / `species` / `species_at_sites`.
  `Cell` holds lattice vectors as a `SurdVector` factored `scale ×
  unscaled_basis`; exact lengths/volume/angles/metric. `Sites` holds exact
  fractional coordinates. `Species` supports mixed occupancy plus optional
  charges/spins/labels decorations; structures carry an optional explicitly
  assigned `charge`.
- `ASUStructure` (a `FundamentalDomainStructure`) holds a structure as its
  asymmetric unit: cell + space group in its IT standard setting + Wyckoff
  sites + a stored `SettingTransform`. **Expansion is exact and
  tolerance-free** (`UnitcellStructureView(asu)`); **recognition is the only
  tolerant step** (`ASUStructureView(structure, …)`, optionally via spglib).
  `expand→recognize→expand` is idempotent; `recognize→expand` is not identity.
- `same_crystal(a, b)` is the crystallographic round-trip predicate (ignores
  site order and lattice translation); `__eq__` is stricter.
- Precision (`cell.precision`, `sites.precision`) is an exact absolute bound
  derived from source digits; `periodicity` is a bool triple per basis row
  (non-periodic rows are coordinate-frame vectors, never wrapped; symmetry and
  supercells refuse non-3D). File decimals embed as written: `0.3333` is
  exactly `3333/10000`.
- Lazy file-backed views: `UnitcellStructureView("x.cif")` parses on first
  access; `httk.core.DatastreamURL(url)` is the explicit consent token for
  network-backed loading.

## Records, definitions, and identity

- **OPTIMADE property/entry-type definitions** (`PropertyDefinition`,
  `EntryTypeDefinition` in `httk.core`) are the semantic vocabulary: field
  identity, type, shape, units, meaning — shared by storage and serving.
  Custom properties live under registered prefixes (`_httk_`, or register your
  own with `register_definition_prefix`).
- **Storage contracts** (`httk.core.storage`): domain classes opt into storage
  via record dataclasses; `content_id` gives versioned, layout-independent
  content addressing; field markers (`Indexed`, `Unique`, `IdentitySkip`, …)
  and `stored_property` declare per-property storage/query behavior neutrally
  — no SQL leaks into domain modules. Stores layer a separate public-identity
  axis on top (a store-minted `id`, per-revision `immutable_id`, and
  alternative ids), distinct from content addressing.
- **Provenance** (`httk.core`): `Run` (one workflow execution with
  input/artifact/output edges as loose string triples), `ProductLink`
  (data→data curation edge), `DataRecord` (one declared-property value).
  Served as `_httk_runs`/`_httk_records` entry types.
- **`EntryProvider`** is the neutral contract by which any module supplies
  described, queryable entries to consumers (the OPTIMADE server, stores)
  without depending on them. Store-backed providers serve mains only and, by
  default, the latest revision of each lineage.

## The reporting channel

All diagnostics ride one stdlib-logging hierarchy under `"httk"`. Library code
only calls `logging.getLogger(__name__)`. Users opt in with
`httk.core.report.configure_reporting(...)`; per-task capture uses
`with collect_reports(...) as c:` (async-safe; captures `warnings.warn`). The
OPTIMADE server runs every request inside a collection and merges it into the
response `meta.warnings`.

## Citations

`print(httk.core.credits)` shows the citations relevant to what was actually
imported/used; modules register theirs via `register_citation`.

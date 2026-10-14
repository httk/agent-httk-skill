<!-- examples/coerce_quickstart.md -->

# Coercion quickstart

Four verbs cover moving between httk views, backends, and plain values:

- ``coerce_view(value, target)`` is backend-aware: the result may be an httk view that retains
  the exact backend (recoverable with ``unwrap``).
- ``coerce(value, target)`` is strict: for non-View targets other than ``"natural"``, the result is a plain, non-view instance of the target; a View-class target deliberately returns a view.
- ``unview(value)`` sheds an httk view wrapper, keeping the presented representation.
- ``unwrap(value)`` recovers the original backend/source object.

A function that works with vectors can do its arithmetic exactly and hand the result back in the
caller's own kind: a numpy matrix in, a numpy-compatible result out.

```{literalinclude} ../../examples/coerce_quickstart.py
:language: python
:lines: 14-
```

<!-- examples/datastreams_quickstart.md -->

# Datastreams quickstart

Views accept natural inputs and present them through the interface an algorithm needs.
The same file view also opens gzip-compressed text transparently from its filename.

```{literalinclude} ../../examples/datastreams_quickstart.py
:language: python
:lines: 6-
```

<!-- examples/entry_provider.md -->

# Implementing an `EntryProvider`: the contract *httk-core* owns

`httk.core.EntryProvider` is the neutral seam between a module that *has* data
and a module that *serves* it. A domain module (say a materials database)
implements the contract; a serving module (say *httk-serve*) consumes it.
Neither imports the other — they meet at this abstract base class and its small
registry. Nothing in the contract is specific to materials science, or even to
OPTIMADE.

A provider answers three questions per entry type, and optionally a fourth
and fifth:

`entry_types()`
    *What do you serve, and what does it mean?* Returns a mapping of entry-type
    name to `EntryTypeDefinition` — the same first-class definition objects
    described in the OPTIMADE definitions guide. A definition may describe more
    properties than the provider actually serves; it is the schema, not the
    selection.

`property_keys(entry_type)`
    *Where does each served property live in a record?* Maps a served property
    name onto the key it is stored under. This is the selection: exactly these
    property names are served, and every one of them must be described by the
    entry type's definition. The map must always cover at least `id` and
    `type`. The indirection matters — a provider's records usually already
    exist in some internal shape, and the map lets `id` be read from a record
    key called `__id` without renaming anything.

`records(entry_type)`
    *The data.* Plain JSON-able mappings keyed by the record keys named above:
    strings, numbers, booleans, `None`, and nested lists/dicts of those. An
    iterable, so a real provider can stream from a database instead of
    materializing everything.

`relationships(entry_type)`
    *Optional.* Maps an entry id to a flat tuple of `RelatedEntry` values, each
    naming a related entry by its type and id, with optional `description` and
    `role` metadata (OPTIMADE v1.2 and v1.3 respectively), an optional `label`
    (the OPTIMADE relation-object label, served as `meta._httk_label`), and an
    optional `relationship` — a wire-form semantic relationship key. It is flat
    on purpose: the serving layer groups by `relationship or entry_type` (a
    `None` relationship falls back to grouping by the target's entry type). The
    base-class default returns an empty mapping.

`reverse_relationships()`
    *Optional, and takes no argument.* The derived reverse of edges a provider
    owns (e.g. run provenance edges), for entries that *other* types serve.
    Unlike `relationships` it is one level deeper and not scoped to a single
    entry type: it returns a nested mapping keyed first by the *target* entry
    type, then by target id, to a flat tuple of `RelatedEntry` values. The
    serving layer append-merges these onto those targets' forward blocks so a
    provider can expose both directions of a semantic edge. The base-class
    default returns an empty mapping.

The example below implements a `widgets` provider with two records and a
relationship to a `references` entry, then exercises the contract exactly as a
consumer would: definitions first, then the property-key map, then the records
extracted through that map.

Finally it shows the **registry**. `register_entry_provider` records a *lazy*
`"module:callable"` reference to a factory, never a live provider, because
providers need data and only the application knows where that data comes from.
A consumer lists what is available with `known_entry_providers()` and resolves
the reference only when it decides to build one.

```{literalinclude} ../../examples/entry_provider.py
:language: python
:lines: 66-
```

<!-- examples/entry_records.md -->

# Define a frozen served record with explicit scientific property metadata.

```{literalinclude} ../../examples/entry_records.py
:language: python
:lines: 2-
```

<!-- examples/exactmath_quickstart.md -->

# Exact math quickstart

By default exactmath returns a symbolically exact value where one exists (square roots and the
supported degree angles), a rational where the answer is rational, and otherwise a deterministic
Fraction approximation. Decimal inputs or ``digits=`` select correctly-rounded Decimals instead.

```{literalinclude} ../../examples/exactmath_quickstart.py
:language: python
:lines: 7-
```

<!-- examples/index.md -->

# Examples

Runnable scripts from the repository's `examples/` directory.

```{toctree}
:maxdepth: 1

datastreams_quickstart
vectors_quickstart
exactmath_quickstart
load_and_dataset_loader
property_definitions
entry_provider
optimade_filter
coerce_quickstart
entry_records
```

<!-- examples/load_and_dataset_loader.md -->

# Getting data into httk: the `load` dispatcher and the `DatasetLoader`

*httk-core* offers two quite different doors into "read this data": a
**dispatcher** for file formats, and a **lazy dataset loader** for httk's own
JSON/JSON-LD data files. This example runs both, end to end, against files it
writes into a temporary directory, so it needs no network and no data package.

**`httk.core.load` — dispatch by file type.** `load("some/file.cif")` does not
itself know any file format. It resolves *which reader to call* and hands the
original filename over. Resolution has three steps, and they are worth knowing
because they explain what a format module has to register:

1. At most one recognized *compression* suffix is stripped off the name
   (`.gz`, `.bz2`, ...), giving an *inner* name. The reader still receives the
   original, still-compressed path — the datastream layer decompresses
   transparently when the reader opens it.
2. The inner name's *extension* is looked up in the extension registry
   (`.cif`, `.poscar`, ...).
3. Failing that, the inner name's *exact basename* is looked up, case
   insensitively, in a separate basename registry. This is how extension-less
   files such as `POSCAR` and `CONTCAR` dispatch at all.

*httk-core* ships **no** readers of its own — it is the contract
layer, not a format library. The registries are filled by sibling modules:
importing `httk.core` walks the `httk.registry` namespace package and imports
every handler package it finds there, and each of those calls
`httk.core.register.register_reader` to claim its extensions and basenames. So
what `known_extensions()` reports is a *statement about the installation*: with
only *httk-core* installed both registries are empty, and with *httk-atomistic*
alongside it they list that module's formats. This example prints whichever is
the case here, then shows the explicit error `load` raises when
nothing matches — it names the file and lists everything that *is* registered,
which is usually the fastest way to notice a module is missing.

**`DatasetLoader` — httk's dataset files.** A `DatasetLoader` is a *declare-time
placeholder*: constructing one records its arguments and performs no I/O
whatsoever. The file is read the first time `.data`, `.meta`, or `.index` is
touched. That makes it cheap for a module to declare its reference datasets at
import time and pay for them only if someone actually uses them. Loaders that
share an `identifier` deduplicate: the first load wins and later loaders with
that identifier hand back the same object.

The file itself may be either shape:

- **Plain JSON** — any JSON value at all. It comes back as-is through `.data`,
  with `.meta` and `.index` both `None`.
- **Structured JSON-LD** — a document with `@context`, `@id`, `@type`, header
  fields, a `data` object and an optional `indicies` object. Then `.meta` is a
  `DatasetMeta` carrying the header, the per-dataset `@id`s and the per-field
  property URLs harvested from the context; `.data` and `.index` are
  `DatasetLoaderRecord` views whose top-level keys are reachable both as attributes
  (`data.spacegroups`) and as items (`data["spacegroups"]`).

Compression is invisible to all of this: `symmetry.json.gz` loads exactly like
`symmetry.json`, because the format is decided from the name *after* the
compression suffix is stripped.

```{literalinclude} ../../examples/load_and_dataset_loader.py
:language: python
:lines: 58-
```

<!-- examples/optimade_filter.md -->

# Parsing OPTIMADE filter strings into an abstract syntax tree

An OPTIMADE query arrives as a string — `elements HAS ALL "Ga","Ti" AND
nelements=3`. Before anything can be done with it, it has to become structure.
`httk.core.optimade.parse_optimade_filter` does exactly that and nothing more: it runs
the filter string against the OPTIMADE grammar (transcribed from the
specification's appendix and vendored inside *httk-core*) and returns the query
as a tree of plain Python tuples. It does not evaluate, optimize, or translate
the query — a database backend does that, by walking the tree this function
returns.

The tree contains only tuples and strings. Every node is
`(operator, *operands)`:

- **Leaves** are two-element tuples tagging a token with its kind:
  `('Identifier', 'nelements')`, `('Number', '3')`, `('String', 'Ga')`,
  `('Boolean', 'TRUE')`. Values stay as *text*; interpreting `'3'` as an
  integer is the backend's business, since the right numeric type depends on
  the property being compared.
- A **nested identifier** simply grows more elements:
  `cartesian_site_positions.x` becomes
  `('Identifier', 'cartesian_site_positions', 'x')`.
- **Comparisons** are `(op, left, right)` where `op` is one of `=`, `!=`, `<`,
  `<=`, `>`, `>=`, or one of the string operators `CONTAINS`, `STARTS`, `ENDS`.
  Either side may be the constant — `"Ga" = chemical_formula_descriptive`
  parses with the string on the left, exactly as written.
- **Boolean structure** is `('AND', left, right)`, `('OR', left, right)` and
  `('NOT', operand)`. `AND` binds tighter than `OR`, so `a AND b OR c` comes
  back as `('OR', ('AND', a, b), c)`.
- **List operators** carry an extra tuple of per-value operators, because
  OPTIMADE allows a comparison operator per value: `elements HAS ALL "Ga","Ti"`
  becomes `('HAS_ALL', ('=', '='), identifier, (value, value))` — one `'='` per
  value. `HAS ANY`, `HAS ONLY` and the operator form `elements HAS < 3` follow
  the same shape.
- **Presence and length** get their own nodes: `('IS_KNOWN', identifier)`,
  `('IS_UNKNOWN', identifier)`, and `('LENGTH', identifier, op, value)`.

Because the shape is uniform, walking it is a short recursive function — the
`describe` function below renders any tree as an indented outline, and it needs
no knowledge of the individual operators.

A filter the grammar rejects raises `ParserSyntaxError`, a subclass of
`ParserError`. The failures are all genuine grammar violations, not
type errors: `nelements == 3` (OPTIMADE spells equality with one `=`),
`Elements = "Ga"` (property names are lower-case), `LENGTH elements = 2`
(`LENGTH` is a postfix operator on the identifier).

```{literalinclude} ../../examples/optimade_filter.py
:language: python
:lines: 48-
```

<!-- examples/property_definitions.md -->

# Building a custom OPTIMADE entry type end to end

The OPTIMADE definitions guide walks through the pieces of the definition model
one at a time. This example does the opposite: it plays out the whole job a
database faces when it wants to serve properties of its own, start to finish, in
one runnable script, and prints the actual JSON that comes out at the end.

The scenario: a fictitious database, *Exampledb*, serves the standard OPTIMADE
`calculations` entry type but wants to attach three properties of its own to it
— a total energy, a lattice-vector array, and a classification string. Serving
custom properties correctly takes four steps.

**1. Claim a prefix.** OPTIMADE reserves unprefixed property names for the
standard; a database-specific property must be named `_<db>_<property>`. The
prefix is what routes the property's canonical `$id` to a URL the database
controls, so `register_definition_prefix` pairs the prefix with a base URL. The
prefix itself must be a lower-case alphanumeric token wrapped in single
underscores — `_exmpl_` is fine, `exmpl`, `_Exmpl_` and `_exmpl` are not.
`_httk_` comes pre-registered under httk's ad-hoc namespace at
`schemas.httk.org/ad-hoc/`; generated httk custom names use its
`_httk_custom_*` sub-namespace. This is separate from the
published definitions at `schemas.httk.org/defs/`: a synthesized `$id` names a
property that is not published anywhere, and should not pretend otherwise.

**2. Generate the property definitions.** `PropertyDefinition.from_simple`
builds a full, self-describing definition from a compact description: a name, a
human-readable `description`, and a `fulltype`. The `fulltype` grammar covers
`string`, `integer`, `float`, `boolean`, `timestamp`, `dict`, and nested lists
spelled out in words — `list of list of float` for a 3x3 array. Array
properties additionally take `dimensions` (named axes and their sizes) and a
`unit`; both surface in the generated document, and `dimensions` also causes a
`list_axes` metadata definition to be generated automatically.

The result is *implementation-neutral*: it describes the property,
not how any one deployment serves it. Per-deployment flags — is this property
sortable? is it in the response by default? — are layered on separately with
`with_implementation`, which returns a new definition and leaves the original
untouched.

**3. Extend the entry type.** `EntryTypeDefinition.extended` merges the custom
properties into a *copy* of the standard definition. It refuses a name that
collides with an existing property, and refuses an unprefixed custom name
unless you explicitly pass `allow_unprefixed=True` — which is why step 1 has to
happen first. Both refusals are demonstrated below.

**4. Emit it.** `as_optimade()` renders a definition as the JSON document
OPTIMADE actually specifies: `$schema`, `$id`, `title`, `description`,
`x-optimade-type`, the JSON `type` (with `null` included exactly when the
property is nullable), `items` for lists, `x-optimade-unit`,
`x-optimade-dimensions`, and the `x-optimade-definition` format stamp. The
stamp reads `"1.2"` even for a v1.3 entry type such as `calculations`: the
definition *format* is versioned separately from the specification, and
httk-core's generator only emits features that already exist in format 1.2.

```{literalinclude} ../../examples/property_definitions.py
:language: python
:lines: 55-
```

<!-- examples/vectors_quickstart.md -->

# Vectors quickstart

Mixed numeric input can enter the exact-rational vector surface without converting through floats.
After exact arithmetic, choose a native or numpy view when a numerical presentation is needed.

```{literalinclude} ../../examples/vectors_quickstart.py
:language: python
:lines: 6-
```


<!-- examples/example.md -->

# Serving records and validating them against their OPTIMADE definitions

This is the smallest useful tour of *httk-store*: the two capabilities that need
no database at all. A **provider** takes data you already have and answers the
neutral `httk.core.EntryProvider` contract about it; **validation** checks
concrete values against the OPTIMADE property definitions that describe them.
Both run fully offline — no network, no server, no registry lookup.

## The in-memory providers

`ReferenceEntryProvider`, `FileEntryProvider` and `CalculationEntryProvider`
each wrap a plain `{id: record}` mapping of one of httk-core's stdlib-only
record models (`Reference`, `File`, `Calculation`) and serve it as the
corresponding OPTIMADE entry type. A record may be given as a model instance or
as a mapping — the provider calls `Reference.from_obj(...)` on whatever it gets,
so the two forms below are interchangeable.

Reading a provider is always the same three steps, and this example does them
in order:

1. `entry_types()` — what is served, described by an `EntryTypeDefinition`. The
   providers use the *vendored standard* definition (`standard_entry_type`), so
   the descriptions and types are the ones in the OPTIMADE specification, not
   ad-hoc local guesses.
2. `property_keys(entry_type)` — the map from a served property name to the key
   it occupies in a record. It exists so records can keep whatever internal
   shape they already had: here `id` lives under the record key `__id`.
3. `records(entry_type)` — JSON-able mappings, read *through* that map.

`relationships(entry_type)` is the optional fourth step, mapping an entry id to
a flat tuple of `RelatedEntry` values (each optionally carrying a `label`, served
as `meta._httk_label`, and a wire-form `relationship` semantic key that the
serving layer groups by). `reverse_relationships()` (which takes no argument) is an optional fifth step:
it returns a nested mapping — target entry type → target id → `RelatedEntry`
tuple — declaring the derived reverse of edges this provider owns, for entries
that other types serve.

## Validation

`validate_record(entry_type, record)` checks a whole record: every key must be
a property the entry type describes, `id` and `type` must be present, and every
value present is validated against its property definition. `validate_property`
does one value on its own. Both raise `PropertyValidationError`, which carries
the offending property `name`.

The definitions *are* JSON Schema documents (that is what
`PropertyDefinition.as_optimade()` returns), so validation is a plain
`jsonschema` Draft 2020-12 run against a self-contained schema. The one subtle
point the failures below illustrate: OPTIMADE's `references.year` is a
**string** property, so the integer `2021` is rejected while `"2021"` passes —
a mistake that is easy to make, and easy to catch here.

For storing and querying data in a database rather than holding it in memory,
see the other examples, which build on `httk.store.backend.sql`.

```{literalinclude} ../../examples/example.py
:language: python
:lines: 56-
```

<!-- examples/index.md -->

# Examples

Runnable scripts from the repository's `examples/` directory.

```{toctree}
:maxdepth: 1

example
optimade_filters
searching
slicing
storable_records
```

<!-- examples/optimade_filters.md -->

# Querying stored dataclasses with OPTIMADE filter strings

`optimade_filter_searcher(store, cls, filter_string)` takes an **OPTIMADE
filter string** — the query language of the OPTIMADE API, as it arrives in a
URL — and returns a searcher over the stored rows of `cls`. It is the bridge
between the text a user (or a remote client) writes and the search DSL of the
*searching* example: the filter is parsed by httk-core's OPTIMADE grammar,
translated by `httk.store.query.optimade_filters` against a handler table derived from
the class's storage schema, and executed as an ordinary search. Each match
is available as a row of the `searcher.results()` stream.

This is useful well before you serve anything: it lets a filter string be
evaluated against a local database with no HTTP server, no adapter and no
OPTIMADE endpoint in sight. (For the full serving path, see the
*serve as OPTIMADE* example.)

## Property names are the *served* names

An OPTIMADE filter may only mention properties the API declares, and a
database-specific property must carry a registered provider prefix. The stored
fields of `cls` are therefore filterable as `_httk_custom_<field>` — `_httk_custom_name`,
`_httk_custom_x`, `_httk_custom_symbols` — and **not** as the bare field name. This holds
inside dotted relationship paths too: `refs._httk_custom_doi`, not `refs.doi`.

The rules for names that do not resolve follow the OPTIMADE specification
rather than being uniformly strict:

- an unknown name *carrying* the prefix is an error
  (`FilterTranslationError`, category `"unrecognized-property"`), because a
  client asking for `_httk_bananas` has made a mistake worth reporting;
- an unknown name *without* a prefix matches nothing, silently, because it may
  be a standard property this implementation does not support.

## Operators

Everything the grammar offers is available. Comparisons on numeric and string
properties; `STARTS WITH`, `ENDS WITH` and `CONTAINS` for substrings; and the
list operators `HAS`, `HAS ALL`, `HAS ANY`, `HAS ONLY` on variable-length
fields, which map onto the set semantics described in the *searching* example.
`NOT` negates, with the same set reading: `NOT _httk_custom_symbols HAS "O"` selects
the records where *no* symbol is O.

Rational fields (`Fraction` and friends) are stored exactly but compared on
their float companion columns, so a numeric filter on one is
documented-approximate.

## Relationship filters

`related_classes={"refs": Publication}` declares that the relationship type
`refs` is served from the `Publication` field of `cls` — either a reference
field or a `list[Publication]` child field. That unlocks depth-1 dotted
filters, resolved as a **two-phase semi-join**: a nested filter search over
`Publication` collects the sids of the matching publications, and those are
then matched against the relationship's own column. Two consequences worth
knowing:

- `NOT refs._httk_custom_year >= 2000` is the complement over the *parent* rows, so it
  includes rows with no related publication at all.
- A related filter matching nothing yields an empty result, not an error.

Relationship *ids* are filterable as `refs.id HAS "refs-<sid>"`, using the same
`"<entry type>-<sid>"` ids `StoreEntryProvider` mints by default. `refs.id HAS
ALL "a" "b"` now requires *every* listed id (a collapse-to-`HAS ANY` bug in this
reference/child id handler was fixed this series). Nesting deeper than one level
(`refs.other._httk_custom_x`) raises `FilterTranslationError` with category
`"not-implemented"`.

The `_httk_relationships.<key>.id` filter root — which also reaches the semantic
provenance keys — is *not* part of this library `optimade_filter_searcher` API;
it exists only on the served stored route and the in-memory serving adapter (see
[the serving example](https://docs.httk.org/httk-serve/examples/serve_as_optimade.html)
and *httk-serve*'s *how it works* guide).

```{literalinclude} ../../examples/optimade_filters.py
:language: python
:lines: 74-
```

<!-- examples/searching.md -->

# Querying a store with the search DSL

Once frozen dataclasses are stored (see the *storable records* example), you
query them with `store.searcher()`. The DSL is deliberately not SQL and not an
ORM: it is a small backend-agnostic protocol (`httk.store.query`) that the SQL
layer implements and that other stores — including *httk-serve*'s in-memory
reference store — implement identically, so the same query program runs
unchanged against either.

A search is built, not written. Three calls do everything:

`variable(cls)`
: Bind a class to a query variable. Two variables of the same class self-join,
  so "another record with the same spacegroup" is expressible.

`add(expression)`
: Add a condition. Expressions come from comparing a variable's fields;
  `&`, `|` and `~` combine them. Several `add()` calls are ANDed.

`results(name=variable_or_field, ...)` / `count()`
: Run it. `results()` declares what each match yields — the whole
  reconstructed object, one field, or a weak-link set (see below), keyword
  order is result order — and returns named rows; `count()` returns how many
  matches there are, ignoring `set_limit`/`add_offset`.

## What the fields give you

Comparisons (`==`, `!=`, `<`, `<=`, `>`, `>=`) work on scalar fields. String
fields add `contains`, `startswith` and `endswith`, and these always match
**literal** text: `%` and `_` are ordinary characters, not wildcards. `is_in`
is membership on a root field.

A reference field *chains*: `v.ref.doi == "10.1/a"` joins the referenced table
automatically, and every condition written through the same reference field
shares one join. `v.ref == None` is the IS NULL test, and `v.ref == some_object`
compares against an already-stored instance.

## Variable-length fields are sets

A `list[...]` field lives in a child table, so a condition on it is a statement
about a *set* of rows, and the DSL says which one you mean:

- `v.symbols.has_any("O", "Ca")` — at least one element is in the set.
- `v.symbols.has_only("O", "Ca", "Ti")` — every element is in the set (a
  record with no elements at all satisfies this: the empty set is a subset of
  anything). `is_in` on a child field means exactly the same thing.
- `~` negates the *set* statement rather than the row: `~v.symbols.has_any("O")`
  is "no element is O". For the same reason `~(v.symbols == "O")` also means
  "no element is O", not "some element is not O".

`has_any(a) & has_any(b)` is the "HAS ALL" pattern, and works because each
access to a child field mints an independent join.

## Weak links

Weak links are store-managed associations between record lineages, declared in
`StorageInfo.links` on the source class and reached through a `links` namespace:

- `v.links.<name>.<field> == value` chains into the linked target as a set
  predicate, exactly like a child field; `~`, `has_any` and `has_only` behave
  set-wise, and each access mints an independent join.
- `v.links.<name>` on its own is a set-valued output:
  `results(projects=v.links.projects)` yields, per matched row, a tuple of the
  currently linked targets (latest revision, first-link order), resolved after
  the query and honouring `as_of`. Chaining a field onto a link *output* stays
  rejected — that is a set predicate, not a projectable value.

The full weak-link contract is in the versioned database guide.

## Results

`results()` yields named lazy rows: `row.name`, `row["name"]` or `row[0]`
address a declared output, and `row.names`/`row.values` give the full tuple.
Result rows bypass the identity cache; `fetch()` returns lazy rows too
(`eager=True` materializes), and repeated default fetches of one live sid
return the same object.

Sorting on a rational field runs on its float companion column, so it is
documented-approximate; the values themselves are still exact.

```{literalinclude} ../../examples/searching.py
:language: python
:lines: 81-
```

<!-- examples/slicing.md -->

# Pandas-style slicer indexing over a store

`store.searcher().slicer(cls)` wraps the search DSL (see the *searching*
example) in a `[]` indexing surface that reads like pandas. It compiles bracket
indexing into the same `variable`/`add`/`output`/`results` calls and adds no
query capability of its own — so anything the slicer expresses, the plain
searcher expresses too.

```python
note = store.searcher().slicer(Structure)
list(note["formula"])          # one field's values
list(note[note["energy"] < 0]) # the records a boolean mask selects
len(note[note["spacegroup"] == 225])
```

Two indexing keys are accepted, and nothing else:

`note["field"]`
: A field-name string gives a *column* — iterate it for that field's decoded
  values. Comparisons on a column (`==`, `!=`, `<`, `<=`, `>`, `>=`) and the
  helpers `isin`, `isna`, `notna`, `between`, and `.str.contains`/`startswith`/
  `endswith` build a boolean *mask*. String matching is literal: `%` and `_`
  match themselves, never as wildcards.

`note[mask]`
: A boolean mask gives a *selection* — iterate it for the matching
  reconstructed records, or take its `len()`. Masks combine with `&`, `|`, `^`
  and `~` (both operands must be masks of the same slicer).

Every operation runs against a *fresh* searcher, so operations never share
filter state: a filtered selection never leaks its condition into the next one.
Iterating the slicer itself yields every record; `len(note)` counts them.

The slicer never sorts (some stores reject ordering), and it does not offer
`.loc`/`.iloc`, integer or slice indexing, or multi-column selection — reach for
the plain searcher when you need those.

```{literalinclude} ../../examples/slicing.py
:language: python
:lines: 38-
```

<!-- examples/storable_records.md -->

# Storing frozen dataclasses in a database, exactly

`httk.store.backend.sql` stores **plain frozen dataclasses**. There is no base class to
inherit, no metaclass, no ORM session: any frozen dataclass whose field types
resolve is storable, and the vocabulary that fine-tunes how it is stored lives
in *httk-core* (`Indexed`, `Unique`, `Skip`, `Shape`, `StorageInfo`,
`stored_property`) so that a domain module can declare storable classes without
depending on httk-store at all.

This example declares one such class and then does, in order, the five things
you actually do with a store.

## Declaring

The markers below are `typing.Annotated` metadata plus one class variable:

- `Annotated[str, Indexed()]` — put a single-column index on this field.
- `__httk_storage__: ClassVar[StorageInfo]` — table-level settings: composite
  indexes, and the deduplication policy (`"content_id"` by default).
- `Annotated[FracVector, Shape(3, 3)]` — a fixed-shape tensor, flattened into
  nine columns of the parent table.
- `Annotated[FracVector, Shape(0, 3)]` — a *variable* number of 3-vectors; `0`
  means "any length", so this becomes a child table with one row per vector.
- `list[str]` — likewise a child table. `Author | None` becomes a nullable
  foreign key, and the referenced `Author` is saved recursively first.
- `Annotated[str, Skip()]` — not stored at all; it comes back as the field's
  default.
- `@stored_property` — a *derived* value that is computed once, written into
  its own column (so it is queryable and indexable), and recomputed rather than
  read back when the instance is reconstructed.

## Round-tripping, exactly

`fetch` gives back an equal instance — a lazy row by default, decoded field by
field on access (`eager=True` materializes it up front) — and for rational
values it gives back an *exactly* equal one. `Fraction(1, 3)` is not representable as a float, so the
example prints both the reconstructed value and what a float round-trip would
have cost. This is not an accident of the encoding: every rational field is
stored as a canonical exact text column (the round-trip source of truth)
alongside float companion columns that exist only so that SQL can compare and
sort. Comparisons on rational fields are therefore documented-approximate,
while the values themselves are lossless.

## Content identity and deduplication

The default policy is `dedup="content_id"`: before inserting, the store hashes
the instance's canonical form and looks for a row with that hash. Saving an
*equal* instance therefore returns the sid of the existing row instead of
writing a second one — which the row count below shows. `content_id(obj)` is a
pure function you can compute without a database, and `fetch_by_content_id`
looks a row up by it. (The alternatives are `dedup="by_value"`, matching on the
parent columns only, and `dedup="none"`, which always inserts.)

## Join classes and `referring`

A "tag" or "link" class is just another storable dataclass holding a reference.
`store.referring(Tag, field="measurement", to=measurement)` returns every
stored `Tag` whose `measurement` field points at that instance — the reverse of
the foreign key, without writing a query.

## Persistence

`Backend.sqlite(path)` is a file; `Backend.sqlite()` is in memory. The last
section saves into a file, disposes the database entirely, reopens it in a
second `Backend`/`SqlStore` pair, and fetches the same sid back.

```{literalinclude} ../../examples/storable_records.py
:language: python
:lines: 67-
```


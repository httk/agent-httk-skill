<!-- examples/in_memory_backend.md -->

# Standing up a backend from plain dict rows, without writing a provider

An `EntryProvider` is the neutral contract a *data* package implements so that
any serving module can expose it. But when the data is already sitting in
memory — rows loaded from a JSON file, records built in a notebook, fixtures in
a test — there is a shorter path: hand the rows to `InMemoryStore`, describe
what is served, and wire the two together with a `BackendAdapter`. That is the
whole backend, and it is what this example does in about forty lines.

Four pieces, and no others:

`InMemoryStore`
: A ready-made implementation of the backend `Store` protocol over
  `{target: [row, ...]}`, where a row is any plain mapping. It supports the
  same search-expression surface a SQL store does, so it is not a toy: it is
  the store `adapter_from_providers` itself loads provider records into, and
  the one the SQL backend in *httk-store* is checked against for parity.

`EntrySource`
: Where an entry endpoint's rows come from, and how a row becomes a response.
  `target` is the store key to search; `fields` maps each served OPTIMADE
  property to a function extracting it from a row — which is where a backend
  key gets renamed (`__id` to `id`), a constant gets injected (`type`), or a
  value gets computed on the fly. `sort_keys` maps a property to the row key to
  sort on.

`build_served_schema`
: The declaration of what exists: which entry types, which of their properties
  are served, which come back by default, and which may be sorted on. The
  property definitions themselves are the vendored OPTIMADE standard, loaded
  with `standard_entry_type` — so `/v1/info/files` documents types, units and
  descriptions without a line of schema written here.

`BackendAdapter`
: The binding of store to endpoints. Note what is *not* passed: no
  `field_handlers` table. When it is omitted, the adapter derives filter
  handlers from the schema, assuming each property is filtered against a row
  key of the same name. That assumption holds here (`size`, `name` and
  `media_type` are stored under those names), so filtering works with no
  handler code. A backend whose row keys differ supplies its own tables —
  `examples/optimade/demo_server/` shows that, along with relationships, partial data
  and a custom entry type.

The query at the end goes through `execute_query`, i.e. the engine directly,
skipping HTTP. The same adapter can equally be handed to `serve(adapter)` or
`create_asgi_app(adapter)` — see `examples/optimade/query_in_process.py`, which walks
the HTTP surface of an adapter built this way.

Run it with `python examples/optimade/in_memory_backend.py`.

```{literalinclude} ../../examples/optimade/in_memory_backend.py
:language: python
:lines: 51-
```

<!-- examples/index.md -->

# Examples

Runnable scripts from the repository's `examples/` directory.

```{toctree}
:maxdepth: 1

demo_server/serve
existing_database/serve
in_memory_backend
provider_server/serve
query_in_process
serve_as_optimade
store_server/serve
```

<!-- examples/query_in_process.md -->

# Query a live store-native OPTIMADE application without binding a port.

The ASGI application discovers ``StructureEntry`` from ``SqlStore`` and runs
each filter, sort, count, and page bound against the database. Saving another
structure after application construction demonstrates that no provider
snapshot or in-memory serving dataset exists.

```{literalinclude} ../../examples/optimade/query_in_process.py
:language: python
:lines: 8-
```

<!-- examples/serve_as_optimade.md -->

# Serving a database as an OPTIMADE API

The last step of the chain: a store full of frozen dataclasses becomes an
OPTIMADE API. `StoreEntryProvider` implements httk-core's neutral
`httk.core.EntryProvider` contract over an `SqlStore`; *httk-serve*'s
`adapter_from_providers` consumes that contract. *httk-store* does not depend on
*httk-serve*. The provider handoff uses the httk-core contract, while
*httk-serve* also consumes *httk-store*'s neutral query and store APIs.

## What the provider derives from the schema

`StoreEntryProvider(store, {"books": Book, "writers": Writer})` needs nothing
but the mapping from entry-type name to storable class. From each class's
storage schema it derives:

- an `EntryTypeDefinition` with one OPTIMADE property per servable stored
  field, named with a registered database-specific prefix (`_httk_` by
  default), plus the mandatory `id` and `type`. You may pass your own
  `definitions=` instead, as long as they describe everything served.
- JSON-able records: rationals are served as their nearest floats (the exact
  values stay in the database), datetimes as ISO text, fixed-shape tensors as
  nested lists, and `stored_property` values as ordinary properties.
- relationships, for reference fields and `list[Storable]` fields **whose
  target class is also served**. A `Related` marker on the field adds the
  OPTIMADE `role`/`description` metadata; exposed `WeakLink` declarations in
  `StorageInfo.links` contribute store-managed relationships. A
  `StrongLink` marker on a run's provenance edge fields is served as a semantic
  relationship in both directions (forward on the run, derived reverse on each
  targeted served class).

Fields with no OPTIMADE value representation — `bytes`, custom codecs — are
simply not served, and a reference field whose target class is not served
becomes neither a property nor a relationship.

## Running a query

`adapter_from_providers([provider])` builds a backend adapter: it reads the
definitions, loads the records, and wires the filter handlers and the
relationship id fields. `execute_query(adapter, entries, response_fields, ...)`
is then the whole OPTIMADE query pipeline minus HTTP — the same call an
OPTIMADE web endpoint makes after parsing a request. It takes the filter as an
already-parsed AST from `parse_optimade_filter`, so this example goes
end to end from a filter *string* to served records.

Note the difference from the *OPTIMADE filters* example: there the filter runs
as SQL against the store and yields dataclass instances; here it runs through
the serving layer and yields **records** — id, type and the selected response
fields — which is what an API actually returns.

## Ids

By default an entry uses its stored `id`; this example assigns identifiers
such as `books-1` and `writers-3` explicitly. An `id_of` callback replaces those ids
everywhere at once, including inside reference, child, and weak-link
relationships. `StrongLink` run edges are the exception: they are matched by
raw id, so a custom `id_of` provider gets empty reverse relationship blocks.

```{literalinclude} ../../examples/optimade/serve_as_optimade.py
:language: python
:lines: 58-
```


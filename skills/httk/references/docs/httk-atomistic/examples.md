<!-- examples/asu_from_cif.md -->

# Asymmetric units: reading a CIF, expanding it, and going back again

A crystal is mostly repetition. A structure with 192 atoms in its cell may have
only two that are genuinely independent — the rest are copies placed by
symmetry. The *asymmetric unit* is that irreducible part, and
`httk.atomistic.ASUStructure` is httk's representation of it: a space group, one
site per orbit, and the values of each site's free parameters.

This example reads a CIF into an ASU, expands it to the full cell, recovers the
ASU from the expansion, and checks the crystal survived the trip.

## Why not just store the atoms?

Three reasons, and the third is the interesting one.

- It is smaller, and it says what the structure *means*: "sodium on Wyckoff `a`"
  rather than four coordinates that happen to be related.
- Symmetry is preserved rather than inferred. Expanding and re-detecting a
  structure is lossy in a way that storing the ASU is not.
- **It is exact.** Reduced coordinates, symmetry operations, and Wyckoff
  parameters are all rationals, and httk keeps them that way — as
  `Fraction`s, never as floats. Expanding an ASU is affine arithmetic over the
  rationals followed by an exact equality test, so it needs no coordinate grid,
  no snapping, and no tolerance at all.

## Any setting, including ones in no table

A space group can be written in many *settings* — different axis choices,
different origins. They are genuinely different coordinate systems: Wyckoff
letter `e` of space group 15 is `0,y,1/4` in the standard setting `15:b1` and
`1/4,0,z` in `15:c1`.

httk always records the Wyckoff data against the International Tables
**standard** setting, and carries a `SettingTransform` saying how to get from
there to the setting the structure is actually in. Because that transform is
*stored* rather than looked up, a setting that appears in no table is
representable just as well as a tabulated one — which is the point.

The transform is never *derived*. Searching for one that maps a group onto
itself is massively underdetermined: for space group 15 alone there are 192
valid candidates among just the small integer matrices, and they describe
*different crystals*. So httk stores the transform it was given and refuses to
guess one it was not.

## Where tolerance lives

In exactly one place: recognizing a structure that does not already carry its
symmetry.

A file writes `0.3333`. httk embeds that as the rational 3333/10000 — what the
file says — not as `float("0.3333")`, whose exact value is
6004199023210345/18014398509481984 and claims a precision nobody stated. The
recognition step then decides which Wyckoff position each site is *meant* to be
on, and the position supplies exact values for its fixed components. After that
everything is exact again.

So the two directions are not symmetric, and the example prints both:

- **expansion is lossless**, and
- **recognition is lossy at the tolerance level** — it snaps a measured structure onto an
  idealised one.

Run this file to see every step printed.

```{literalinclude} ../../examples/asu_from_cif.py
:language: python
:lines: 65-
```

<!-- examples/build_a_structure.md -->

# Building a UnitcellStructure three ways, and reading its geometry back out exactly

A `UnitcellStructure` in *httk-atomistic* is always the same canonical quartet — a
`cell` of three lattice vectors, `sites` of reduced (fractional) coordinates, a
tuple of `species`, and the `species_at_sites` naming which species occupies
each site. What varies is how you *hand it in*. The cell argument dispatches on
type and shape, so all three constructions below produce the same kind of
object and are inspected with exactly the same code:

1. **An explicit 3x3 matrix** — rows are the lattice vectors $\mathbf{a}$,
   $\mathbf{b}$, $\mathbf{c}$. This is the direct route, and the only one that
   pins down the cell's orientation in space.
2. **Cell parameters** — the flat 6-tuple
   $(a, b, c, \alpha, \beta, \gamma)$, angles in degrees, accepted directly by
   `Cell` and `UnitcellStructure`. A basis is built for you using the standard
   orientation convention: $\mathbf{a}$ along $x$, $\mathbf{b}$ in the $xy$-plane.
3. **An spglib-style triple** — `(lattice, positions, numbers)`, the shape
   symmetry libraries speak. `UnitcellStructureView` presents it as a `UnitcellStructure`,
   inventing one species per distinct atomic number.

The second half of this script is about the one thing that most often surprises
people, and it is worth being precise about: **cell parameters carry no
orientation.** Lengths and angles are invariant under rotation, so a cell and a
rotated copy of it have *identical* parameters. Going cell → parameters → cell
therefore cannot return the matrix you started from; it returns a
*different-but-equivalent* one, in the standard orientation, with the same
lengths, the same angles, and the same volume. If your workflow cares about how
the cell sits relative to a surface, a field, or a supercell it was cut from,
keep the matrix; if it only cares about the crystal, parameters are enough.

Inspection stays in the **exact** numeric model throughout. `cell.lengths` and
`cell.volume` are exact `SurdScalar`s in the squarefree-radical field,
`cell.angles` are exact `Fraction` degrees, `cell.metric()` is the exact Gram
matrix $G_{ij} = \mathbf{a}_i \cdot \mathbf{a}_j$ (rational for any cell
whose parameters are), and `structure.cartesian_sites()` multiplies the rational
reduced coordinates by the surd basis, so a hexagonal cell's $\sqrt3$ survives
into Cartesian space instead of decaying into 0.8660254. Floats are produced
only at the very end, by rendering: `.to_floats()` on any exact vector,
`float(...)` on any exact scalar.

The related guide page {doc}`../structures` covers the same model in reference
form; this script is the runnable counterpart.

```{literalinclude} ../../examples/build_a_structure.py
:language: python
:lines: 44-
```

<!-- examples/build_a_supercell.md -->

# Build exact general, orthogonal, and cubic supercells

The v1 Step 2 tutorial demonstrated a particularly useful feature: starting
from a skewed primitive cell, httk could build an exact integer supercell and
search for rectangular or nearly cubic choices automatically.

The v2 interface separates those two jobs. `UnitcellStructure.supercell()` applies a
transformation you already know. `orthogonal_supercell()` and
`cubic_supercell()` search at an explicitly requested **multiplier** — the
number of original cells, and therefore the factor by which the site count
grows. This replaces v1's `tolerance` argument, which was a search knob rather
than a geometric tolerance.

Every returned `SupercellResult` includes the materialized structure, the exact
integer transformation, and exact dimensionless shape scores. A score of zero
is a proof that the corresponding target was reached exactly.

```{literalinclude} ../../examples/build_a_supercell.py
:language: python
:lines: 18-
```

<!-- examples/disorder_and_vacancies.md -->

# Disorder, vacancies, and attached species: what a site can actually hold

Most crystal-structure libraries assume a site holds exactly one atom, and
encode a structure as a list of atomic numbers. Real materials modelling breaks
that assumption constantly — a substitutional alloy has a site that is 50% Fe
and 50% Ni, an off-stoichiometric compound has a site that is 90% occupied and
10% empty, and an adsorbed methyl group is a carbon with three hydrogens hanging
off it that nobody wants to place explicitly. *httk-atomistic* follows OPTIMADE
here: the object at a site is a **`Species`**, not an element, and a `Species`
is rich enough to say all three things.

A `Species` has a `name` (its label within the structure — it need *not* be a
chemical symbol), a tuple of `chemical_symbols`, and a matching tuple of
`concentration` values:

`Species(name="M", chemical_symbols=("Fe", "Ni"), concentration=(0.5, 0.5))`
: **Substitutional disorder.** The site is occupied, but by Fe half the time
  and Ni the other half. This is a statistical statement about an ensemble,
  not a statement about one particular atom.

`Species(name="Ti", chemical_symbols=("Ti", "vacancy"), concentration=(0.9, 0.1))`
: **A partial vacancy.** `"vacancy"` is one of the two pseudo-symbols OPTIMADE
  allows (the other is `"X"`, for *unknown*), and it names the *absence* of an
  atom. This site is empty 10% of the time. Note what this is not: it is not a
  Ti atom with a strange charge, and it is not a defect at a known location —
  it is an occupancy.

`Species(name="CH3", chemical_symbols=("C",), concentration=(1.0,), attached=("H",), nattached=(3,))`
: **Attached particles.** The site holds one carbon, fully occupied, with
  three hydrogens attached to it whose positions are deliberately not given.
  `attached` and `nattached` must always be supplied together and share a
  length. This is how you record a methyl group, a hydroxyl, or bound water
  without inventing coordinates you do not have.

**Which representations can carry this?** The Unitcell representation — a `UnitcellStructure`, and the
`UnitcellStructureView` over any backend — carries all of it, because it stores
the `Species` objects themselves. The OPTIMADE species dict (via
`PlainSpeciesView`) carries all of it too, because that is where the model
came from. But the **primitive** representation is the spglib-style
`(lattice, positions, numbers)` triple, and `numbers` is a list of bare atomic
numbers: there is no integer that means "90% Ti", and no integer that means
"carbon plus three hydrogens". So `PlainStructureView` does not silently
round, drop, or approximate — it raises `TypeError`, naming the species it
could not express.

`Species.is_single_element` is the predicate behind that check, and it is worth
knowing about directly: it is true only for a species made of exactly one *real*
element symbol (so not `"X"` and not `"vacancy"`) with nothing attached. Test it
before you reach for a symmetry library, a force field, or anything else that
speaks in atomic numbers.

Keep disordered structures in the Unitcell representation, and convert to
primitive only at the boundary of a tool that cannot represent disorder; a
`TypeError` reports unsupported species at that boundary.

```{literalinclude} ../../examples/disorder_and_vacancies.py
:language: python
:lines: 56-
```

<!-- examples/index.md -->

# Examples

Runnable scripts from the repository's `examples/` directory.

```{toctree}
:maxdepth: 1

asu_from_cif
build_a_structure
build_a_supercell
disorder_and_vacancies
load_from_poscar
parse_cif
parse_poscar
parse_vasp_outputs
precision
serve_structures_as_optimade
```

<!-- examples/load_from_poscar.md -->

# Reading VASP POSCAR and CONTCAR files into a UnitcellStructure

Getting a structure off disk is the first thing most workflows do, and VASP's
POSCAR/CONTCAR is the format a great many of them meet first. `httk.core.load`
is the loading entry point:

`load(path)`
: **The loading entry point.** It picks a reader by file type, transparently
  decompresses `.bz2` and `.gz`, and returns the native `UnitcellStructure`.

**The values stay exact.** The file's numbers are read as *strings* and turned
into exact rationals, never into floats first, so a lattice row written as
`5.3982999999999999` is that exact decimal and a coordinate written as `1/3`
would be that exact third. Direct coordinates become reduced coordinates
verbatim. Cartesian coordinates are converted exactly as `cart * basis.inv()`,
and the VASP universal scaling factor cancels in that expression (it scales the
lattice vectors and the Cartesian positions alike), so the reduced coordinates
come out exact either way. The one place exactness is unavoidably lost is a
*negative* scale line, which encodes a target cell **volume**: the resulting
overall scale is a cube root, which leaves the squarefree-radical field, so it
is a deterministic rational approximation — the basis rows themselves stay
exact.

VASP-4 POSCAR files have no species line, so the elements are simply not in the
file; the loader raises `ValueError` rather than guessing.

```{literalinclude} ../../examples/load_from_poscar.py
:language: python
:lines: 27-
```

<!-- examples/parse_cif.md -->

# Reading, inspecting and writing CIF files

The Crystallographic Information File (CIF) format is the standard exchange
format for crystal structures. *httk-atomistic* provides a low-level CIF stack that
treats a CIF as what it literally is — a sequence of named data blocks, each a
set of tag/value pairs plus tabular `loop_` sections — and refuses to guess what
any of it *means*. Interpreting the tags (turning a cell and an asymmetric unit
into a structure) is a separate, higher-level job.

Three pieces make up that stack, and this example walks through all of them.

## `read_cif(source)`

Parses a CIF and returns a `(data_blocks, header)` tuple. `data_blocks` is a
list of `(name, block)` pairs — CIF permits several `data_` blocks in one file,
so this is a list, not a dict. `header` is the run of comment lines at the very
top of the file, kept verbatim so that it survives a round trip.

A `block` is a flat mapping from *lowercased tag name without its leading
underscore* to value. Two rules make that mapping worth knowing:

- **Values are strings.** `_cell_length_a 5.6402(3)` becomes the string
  `"5.6402(3)"`, not a float. Nothing is rounded, nothing is discarded, and the
  parenthesised standard uncertainty is still there for whoever wants it.
- **Loops become columns.** Each `loop_` contributes one list-valued entry per
  column, all of equal length, plus a bookkeeping key `loop_0`, `loop_1`, …
  listing that loop's column names in file order. Those bookkeeping keys are
  what let `write_cif` reconstruct the loops, and what let a reader tell a
  one-row loop from a plain tag.

`source` may be a filename (`str` or `os.PathLike`), an already-open text
stream, or any iterable of lines. Filenames are opened through
`httk.core.TextstreamFileView`, so `structure.cif.bz2` and `structure.cif.gz`
are decompressed transparently.

## `parse_cif_float(token)` and `parse_cif_int(token)`

These convert one of the preserved strings into a number, honouring the numeric
conventions CIF actually uses:

- `"5.6402(3)"` — a value with a standard uncertainty (esd) on its last digits.
  The plain call returns just the central value `5.6402`; passing `meta=True`
  returns `(value, {"esd": ..., "precision": ...})`, where `esd` is the
  uncertainty in the value's own units (`3/10000` here) and `precision` is the
  precision implied by how the number was *written* (`0.0001` for four
  decimals). The two are independent: a value with no esd still has a stated
  precision.
- `"?"` — "unknown", a legal CIF value. It parses to `None` rather than raising,
  so a missing measurement stays representable. Its sibling `"."` ("not
  applicable") is an error instead: there is no number to return.
- `"1/3"` — a fraction, common in symmetry operations. Parsed exactly and
  reported with precision `None`, i.e. a stated value rather than a rounded decimal.

`parse_cif_int` follows the same conventions and returns the integral central
value: `"295(2)"` is `295`, `"3E2"` is `300`. It is strict by default, so a
genuinely fractional token such as `"1.5"` raises `ValueError` instead of
silently rounding.

## `write_cif(target, data_blocks, header)`

Writes the parsed structure back out: the header comments first, then each block
as `data_<name>` followed by its tags and its reconstructed loops. Values the
writer cannot recognise as bare CIF numbers are quoted, which is why an
esd-bearing string such as `5.6402(3)` comes back out as `'5.6402(3)'` —
re-reading strips the quotes, so the value is unchanged. Demonstrating that is
the point of the round-trip section below: read → write → read yields an
identical mapping.

The final section shows the same file arriving through `httk.core.load`, which
dispatches `.cif` (and `.cif.bz2`) to the atomistic CIF reader because importing `httk.core`
discovers the `httk.registry.io.atomistic` registry package. By default, `load(path)` returns
the native `ASUStructure` when *httk-atomistic* is installed. This example uses
`load(path, raw=True)`, which returns the neutral payload mapping instead. Blocks
that are not structures are reported rather than raising, since a CIF may hold
anything.

Run this file to see every step printed.

```{literalinclude} ../../examples/parse_cif.py
:language: python
:lines: 79-
```

<!-- examples/parse_poscar.md -->

# Reading VASP POSCAR and CONTCAR files

A POSCAR (or its relaxed sibling CONTCAR) is VASP's structure file: a comment
line, a scaling factor, three lattice vectors, the species and how many atoms of
each, a coordinate-mode line, and then the coordinates. It is a small format
with a surprising number of variants, and `read_poscar` handles them
while making one strong promise: **it never converts a number**. Every numeric
field comes back as the verbatim string found in the file, so no rounding
happens at the I/O layer. Turning that mapping into an exact `UnitcellStructure`
is the job of `httk.core.load`.

`read_poscar(source)` accepts a filename (`str` or `os.PathLike`), an open text
stream, or a plain iterable of lines, and returns a neutral, JSON-able mapping:

`format`
    Always `"vasp-poscar"` — a tag identifying which reader produced the mapping.
`comment`
    Line 1, stripped. VASP itself attaches no meaning to it.
`scale` / `volume`
    Line 2, and **exactly one of the two is a string while the other is `None`.**
    A positive universal scaling factor is a multiplier on the lattice vectors
    and lands in `scale`. A *negative* one is VASP's shorthand for "scale the
    cell so its volume equals |this|", which is a completely different physical
    instruction — so it lands in `volume` instead, sign stripped. Collapsing the
    two into one signed number would force every consumer to re-derive the
    distinction, so the reader keeps them apart.
`cell`
    Three rows of three coordinate strings.
`symbols`
    The species line, as `list[str]` — or `None` for a VASP-4 file, where line 6
    holds the atom counts and no species names are recorded anywhere. `None`
    means "this file does not say", not "no species".
`counts`
    Atoms per species, as `list[int]`. These *are* parsed as integers: they are
    counts, not measurements.
`cartesian`
    `True` when the coordinate-mode line begins with C/c/K/k, `False` for
    Direct/fractional. VASP looks only at the first character, and so does this.
`coords`
    One row of three coordinate strings per atom, in file order — `sum(counts)`
    rows.
`selective_dynamics`
    The per-atom T/F flags as booleans when the file declares selective
    dynamics, otherwise `None`.

Two kinds of trailing content are read past and dropped: per-line species labels
after the three coordinates on a coordinate row (some tools write them, VASP
ignores them), and the velocity or predictor-corrector blocks that follow the
coordinates in a CONTCAR. Only `sum(counts)` coordinate rows are ever consumed.

Malformed input raises `ValueError` naming the offending line number, so a
truncated file points at where it stopped making sense rather than failing
somewhere far away.

The last section shows the reader reached through `httk.core.load` instead of
directly. Importing `httk.core` discovers the `httk.registry.io.atomistic` registry
package, which registers this loader under the extensions `.poscar` / `.vasp`
*and* under the exact basenames `POSCAR` / `CONTCAR` — because the canonical
VASP files have no extension at all. `load` therefore dispatches a plain
`CONTCAR`, and also a `CONTCAR.bz2`: the compression suffix is stripped before
the basename is matched, and the file is decompressed transparently on read.

Run this file to see each variant parsed and printed.

```{literalinclude} ../../examples/parse_poscar.py
:language: python
:lines: 65-
```

<!-- examples/parse_vasp_outputs.md -->

# Read a small synthetic VASP output directory.

```{literalinclude} ../../examples/parse_vasp_outputs.py
:language: python
:lines: 2-
```

<!-- examples/precision.md -->

# Data precision: letting the file choose the tolerance

Every tolerance in a structure pipeline is a guess about how good the data is.
Match two coordinates within `1e-3`? Hand spglib a `symprec` of `1e-5`? Those
numbers usually come from habit rather than from the data, and when they are
wrong they are wrong silently.

But a file already says how good it is. A coordinate written `0.3333` claims a
precision of about `1e-4` of a cell edge; written `0.33` it claims only `1e-2`.
A cell edge written `5.6402(3)` states its uncertainty outright. httk records
those claims and derives its tolerances from them.

This example shows where the numbers come from, how they are converted, and one
case where deriving the tolerance changes the answer from wrong to right.

## The two values

A structure records two precisions, each on the object that owns the numbers it
describes:

- **coordinate precision** on `Sites`, in *fractional* units — reduced
  coordinates are dimensionless, and a `Sites` has no cell to convert with;
- **basis precision** on `Cell`, in the cell's *length* units.

Both are exact rationals, so nothing picks up binary noise on the way to
becoming a tolerance. `None` means unknown, which is a real answer and not the
same as claiming exactness.

`UnitcellStructure.cartesian_precision()` combines them into the number a tolerance
actually wants: a distance. That conversion is not cosmetic — the same `1e-4`
coordinates mean `5e-4` in a 5 A cell and `3e-3` in a 30 A one.

## The rules

Three, and each exists because the naive alternative is wrong:

- **The coarsest value wins.** A structure is only as precisely stated as its
  least precisely stated number.
- **A stated uncertainty widens the claim.** `5.6402(3)` is good to `3e-4`, not
  to the `1e-4` its four decimals alone suggest.
- **An exact rational makes no claim at all.** `1/3` states a value rather than a
  measurement, and must not drag a table down to the width of its last digit.

Run this file to see every step printed.

```{literalinclude} ../../examples/precision.py
:language: python
:lines: 46-
```

<!-- examples/serve_structures_as_optimade.md -->

# Serving structures as OPTIMADE, with derived fields and custom properties

`StructureEntryProvider` is the adapter that turns a plain `{id: UnitcellStructure}`
mapping into something an OPTIMADE server can query. It implements the neutral
`httk.core.EntryProvider` contract — `entry_types()`, `property_keys()`,
`records()` — and nothing about it is specific to any particular server. That is
the point of the seam: *httk-atomistic* has the data, *httk-serve* serves it,
and neither imports the other. They meet at the contract.

**What the provider derives for you.** Beyond the structural fields it reads
straight off the `UnitcellStructure` (`lattice_vectors`, `cartesian_site_positions`,
`species`, `species_at_sites`, `nsites`, `elements`, `nelements`), it computes
the standard OPTIMADE composition fields:

- `chemical_formula_reduced` — element counts divided by their gcd, elements in
  alphabetical order. Four Fe, twelve O and four Sm reduce by 4 to `FeO3Sm`.
- `chemical_formula_anonymous` — the same stoichiometry with the elements
  replaced by `A`, `B`, `C`, ... assigned by *descending* amount, so the same
  formula gives `A3BC`.
- `elements_ratios` — each element's fraction of the sites, ordered to match
  `elements`.
- `nperiodic_dimensions` and `dimension_types` — 3 and `[1, 1, 1]`, since a
  `UnitcellStructure` is a fully periodic crystal.
- `structure_features` — the OPTIMADE flag list. A site with mixed occupancy
  makes this `["disorder"]`; a species with attached particles adds
  `"site_attachments"`; a fully ordered structure gets `[]`.

**Limits of derivation.** The composition fields are only
meaningful when every species is a single, unattached element — there is no
sensible integer count of Fe in a site that is half Fe and half Ni. So for a
disordered structure the provider serves `null` for those derived fields rather
than inventing a number, while still serving `elements`, `nelements`, `nsites`,
and the honest `structure_features: ["disorder"]`. Compare the two entries in
the output below; this asymmetry is the interesting part.

**Entries with no structure.** Passing `None` for an id is legal and means "this
entry exists, but I have no structure for it". Every structural and derived
field then serves `null`. It keeps a known id queryable instead of making it
vanish.

**Custom properties.** A database usually has more to say than the standard
fields — a total energy, a provenance tag. Pass a `PropertyDefinition` per
custom name in `extra_definitions` (the name needs a registered database prefix,
hence the leading `_httk_`), and the per-entry values in `properties`. The
provider validates that every value you supply is described by the extended
definition, so a typo is an error at construction time rather than a silently
missing field at query time.

The last section runs an actual query: `adapter_from_providers` wraps the
provider for *httk-serve*'s backend, and `execute_query` runs a parsed
OPTIMADE filter against it. *httk-serve* is an optional peer distribution,
not a dependency.

```{literalinclude} ../../examples/serve_structures_as_optimade.py
:language: python
:lines: 54-
```


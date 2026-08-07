# Materials phase diagrams

`httk.analyse.matsci.PhaseDiagram` builds a lower convex hull in composition
space. It normalizes compositions and evaluates energies per atom, so entries
with differently sized formula units can be compared directly. Inputs may be
composition mappings or compatible `StructureLike` objects from
*httk-atomistic*.

## Build a binary diagram

Use `from_compositions` when the compositions are already known. The optional
IDs label entries in decompositions and plots:

```python
from httk.analyse.matsci import PhaseDiagram

diagram = PhaseDiagram.from_compositions(
    [{"A": 1}, {"B": 1}, {"A": 1, "B": 1}],
    [0.0, 0.0, -2.0],
    ids=["A", "B", "AB"],
)

assert tuple(diagram.hull_indices) == (0, 1, 2)
assert diagram.energy_above_hull[2] == 0.0
```

`energy_above_hull` is the per-atom energy above the stable lower envelope.
`hull_indices` retains the order of the supplied entries. Phase boundaries are
exposed directly as `phase_lines`, which delegates to the generic hull's
`supported_segments`.

## Plotting

Binary diagrams plot as a line diagram. Higher-dimensional composition spaces
plot their supported polygonal regions when possible. `plot()` returns a
Matplotlib axes object, making it straightforward to add labels or incorporate
the diagram into an existing figure:

```python
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ax = diagram.plot()
plt.close(ax.figure)
```

### Unknown-energy phases

An energy of `None` keeps a phase in the diagram's separate unknown-energy
channel. Its normalized composition is available through `unknown_compositions`
and its identifier through `unknown_ids`; the phase is not included in
`compositions`, `energies_per_atom`, or any hull calculation. This lets a
diagram retain composition candidates whose energies are not known yet without
changing stable phases, decompositions, or tie-lines. At least one phase must
have a known energy: an input whose energies are all `None` is rejected by both
factory methods and by `PhaseDiagramBuilder.build()`.

Unknown phases are shown by `plot()` by default as open gray squares. They are
visual markers and never participate as hull points or in energy references,
but they do contribute their elements to the global `elements` union. An
unknown phase introducing a new element can therefore widen the composition
space and change how the diagram is drawn, such as turning a known A-B binary
plot into a ternary polygon. Pass `show_unknown=False` to hide the markers. In
a binary plot they are placed at `y=0.0`; in a polygon plot their positions use
the normalized composition fractions as the same corner-weighted coordinates as
the known phases.

### Incremental building

`PhaseDiagramBuilder` is useful when phases arrive incrementally. `add_phase`
and `add_structure` return the builder, so additions can be chained, and
`build()` creates a `PhaseDiagram` snapshot:

```python
from httk.analyse.matsci import PhaseDiagramBuilder

builder = (
    PhaseDiagramBuilder()
    .add_phase({"A": 1}, 0.0, "A")
    .add_phase({"B": 1}, 0.0, "B")
    .add_phase({"A": 1, "B": 1}, -2.0, "AB")
    .add_phase({"A": 1, "B": 2}, None, "unknown-AB2")
)
diagram = builder.build()
assert diagram.unknown_ids == ("unknown-AB2",)
```

Each call to `build()` is independent of later additions. Earlier snapshots
retain the phases and element coordinates present when they were built, while
the next snapshot includes all phases currently accumulated by the builder.

The plotting API is a presentation layer: use `energy_above_hull` and
`phase_lines` for programmatic analysis. For hulls over non-materials
coordinates, see {doc}`generic-hulls`.

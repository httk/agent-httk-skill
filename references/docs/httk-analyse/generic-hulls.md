# Generic lower convex hulls

`httk.analyse.generic.LowerConvexHull` represents the lower convex envelope of
scalar values sampled at arbitrary-dimensional coordinates. It stores the input
as immutable float64 data and exposes indices into the original input order.
The class is useful whenever a value is meaningful only relative to the best
convex combination of sampled states.

## Build a one-dimensional hull

Pass one coordinate tuple per point and one value per tuple. Here the middle
point is stable and lies below the straight line between the endpoints:

```python
from httk.analyse.generic import LowerConvexHull

hull = LowerConvexHull(
    [(0.0,), (0.5,), (1.0,)],
    [0.0, -1.0, 0.0],
)

assert tuple(hull.hull_indices) == (0, 1, 2)
assert hull.value_above_hull[1] == 0.0
```

`value_above_hull` reports each input value relative to its lower-envelope
value. A point is considered on the hull when this excess is less than or equal
to the configured tolerance, so a small positive excess may still be treated
as stable. Values above that tolerance denote unstable points. `hull_indices`
always refers to the original point and value sequences, not to a reordered
presentation.

## Decompositions and supported segments

For an input point `i`, `decomposition(i)` gives its convex decomposition on
the lower hull. The decomposition contains the contributing hull points and
their convex weights. `supported_segments` exposes the geometric support
segments of the hull for plotting or further analysis.

In more than one coordinate dimension, decompositions are found using every
coordinate constraint as well as the convex-weight constraint. Consequently,
weights reproduce the full coordinate tuple rather than only one selected
composition axis. This is important for multidimensional chemical spaces and
for generic optimization problems with several conserved quantities.

For a materials-science wrapper that normalizes compositions and supplies
phase-diagram plotting, see {doc}`phase-diagrams`.

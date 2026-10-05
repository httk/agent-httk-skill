# Molecular-dynamics structure analysis

`httk.analyse.matsci.structure` contains small NumPy-based kernels for periodic
geometry and static structure statistics. Inputs are copied to finite float64
arrays; returned summaries use immutable tuples. Positions, cells, and radial
distances use angstrom, and wavevectors use inverse angstrom. Cell vectors are
rows of the cell matrix.

## Minimum images and neighbor geometry

`minimum_image(displacements, cell, periodicity)` returns the true nearest
lattice image, including for skew cells. Exactly orthogonal cell vectors use
vectorized fractional rounding. For skew cells, it starts from a rounded fractional
candidate, then enumerates every integer shift that could improve the current
distance. Nonperiodic directions are never shifted. Exact enumeration stops
with `ValueError` when a cell and displacement would require more than 100,000
candidates. This limit makes pathological inputs explicit; it does not switch
to an incomplete 27-image search. The result has the input shape and is nested
tuples.

`coordination_numbers(positions, cell, cutoff, periodicity)` returns one
integer count per atom. `bond_angles` returns one tuple of angles in degrees
per center atom; each tuple lists unordered neighbor pairs in input order. Both
exclude self-neighbors, include neighbors exactly at the cutoff, and use true
minimum images. Their cutoff must be strictly below half the shortest nonzero periodic
translation, so each counted neighbor has a unique image. Mixed periodic and
nonperiodic directions are supported; no boundary correction is implied.

The row-vector cell convention and partial-periodicity semantics match the
geometry vocabulary used by [ASE's official geometry documentation](https://wiki.fysik.dtu.dk/ase/ase/geometry.html).
The optional test suite compares minimum-image distances to `ase.geometry` when
ASE is installed. ASE is not a runtime or test dependency.

The raw samples retain every count. Use NumPy directly when a normalized
distribution is useful:

```python
import numpy as np

from httk.analyse.matsci.structure import bond_angles, coordination_numbers

cell = np.eye(3) * 6.0
positions = np.asarray([(x, y, z) for x in (0.0, 2.0, 4.0) for y in (0.0, 2.0, 4.0) for z in (0.0, 2.0, 4.0)])
coordination = coordination_numbers(positions, cell, 2.01)
coordination_counts = np.bincount(coordination)
coordination_probability = coordination_counts / len(coordination)

angles = bond_angles(positions, cell, 2.01)
angle_samples = [angle for center in angles for angle in center]
angle_edges = np.linspace(0.0, 180.0, 19)
angle_counts, _ = np.histogram(angle_samples, bins=angle_edges)
angle_probability = angle_counts / len(angle_samples)
assert coordination_probability[6] == 1.0
assert angle_counts.sum() == len(angle_samples)
```

`coordination_counts[k]` retains the number of atoms with coordination `k`;
`angle_counts.sum()` retains the total number of sampled neighbor-pair angles.

## Radial distribution

```python
from httk.analyse.matsci.structure import radial_distribution

result = radial_distribution(frames, cells, [0.0, 1.0, 2.0, 3.0])
assert result.frame_count > 0
```

`frames` is consumed once. `cells` may be one fixed 3 by 3 matrix or a
single-pass iterable with exactly one matrix per frame. The returned
`RadialDistribution` holds bin `edges`, midpoint `centers`, normalized values
`g`, raw `hist_counts`, `frame_count`, `mean_coordination`, and the ordered
`pair` of a partial RDF (`None` for the total RDF). `mean_coordination` is the
number of counted directed neighbors divided by the number of selected
central atoms over all frames, so it integrates only over the supplied bins.
As a record (see {doc}`records`) it binds to `radial_distribution_function`
with `bin_edges`, `g` and, for a partial RDF, `pair`.

Only full three-dimensional periodicity has a homogeneous bulk RDF
normalization. Bin edges must be increasing and nonnegative. The largest edge
must be strictly below half the shortest periodic translation for every frame. Shell
volume is `4*pi/3 * (r_hi**3 - r_lo**3)`. Counts are directed and exclude self
pairs. Each frame contributes its own finite-size ideal-gas normalization
`N_A * (N_B - delta_AB) / V`; for a total RDF this is `N * (N - 1) / V`, not
`N**2 / V`. The implementation accumulates expected shell counts frame by
frame before dividing the total observed counts.

For a partial RDF, provide a fixed label for every atom and one explicit
ordered pair:

```python
partial = radial_distribution(
    frames,
    cells,
    [0.0, 1.0, 2.0],
    species=("A", "B", "A"),
    pair=("A", "B"),
)
```

This counts neighbors of B around A. No species order or composition is
inferred. Missing labels and frames with no distinct selected pairs raise
`ValueError`.

## Static structure factor

`static_structure_factor(positions, wavevectors, weights=None)` evaluates the
direct sum

`S(q) = |sum_j w_j exp(i q.r_j)|**2 / sum_j w_j**2`.

With unit weights the denominator is atom count. The zero-wavevector value is
retained, and callers select a species by passing only its positions. Weights
must be real and have positive squared norm. This routine is a direct finite
configuration sum; it does not average over directions, configurations, or
reciprocal-lattice shells.

## Scope

These functions accept arrays and do not parse or adapt trajectory files. RDF
can consume a frame stream with bounded per-frame geometry storage. Neighbor
counts and angles use pairwise atom distances. The direct structure factor
scales with the number of atoms times the number of supplied wavevectors.

## Optional bond order

`httk.analyse.matsci.local_order.bond_order` computes per-atom Steinhardt
`q_l` and global `Q_l` from an explicit degree and neighbor cutoff, using
[SciPy spherical harmonics](https://docs.scipy.org/doc/scipy/reference/generated/scipy.special.sph_harm_y.html).
Install `httk-analyse[scipy]` to use this routine. It uses polar theta and
azimuthal phi and the standard rotational invariant
`sqrt(4*pi/(2*l+1) * sum_m |mean(Y_lm)|**2)`.
The global value pools directed bonds, weighting atoms by their coordination;
it is bond-weighted (Steinhardt), not atom-averaged as in Lechner-Dellago or
pyscal, so it differs from those codes for non-uniform coordination. Because
each pair contributes both `r` and `-r` and `Y_lm(-r) = (-1)^l Y_lm(r)`, the
global `Q_l` is identically zero (to rounding) for odd `l`; use even `l` for
it. Per-atom `q_l` remains valid for odd `l`.
`BondOrder` records its `cutoff` and binds to `steinhardt_bond_order` through
`records()`.
Isolated atoms return `None`; coincident atoms raise. No empirical phase
classification or neighbor-averaged variant is inferred. The definition follows
[Steinhardt, Nelson and Ronchetti](https://doi.org/10.1103/PhysRevB.28.784).

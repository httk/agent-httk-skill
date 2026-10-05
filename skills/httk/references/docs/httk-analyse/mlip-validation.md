# Validate MLIP predictions

The routines in `httk.analyse.matsci.mlip` compare already paired prediction
and reference arrays. They use prediction minus reference, preserve raw energy
errors, and return immutable summaries with the underlying residual tuples.
Values must already use the documented units: total energy in eV, forces in
eV/angstrom, and tensile-positive stress in GPa.

## Energy

`energy_errors` divides total energies by each configuration's atom count. Its
95th percentile is the unweighted NumPy linear-interpolation percentile across configurations. By
default, mean and RMS statistics weight each configuration equally. Pass
`weighting="atom"` to give each atom equal weight. Raw statistics always remain
available. Pass `offset_per_atom` only when an explicitly chosen calibration
offset should be applied to predicted per-atom energies; the function never
estimates a shift from the evaluation set.

```python
from httk.analyse.matsci.mlip import energy_errors

energy = energy_errors(
    reference=[0.0, 0.0],
    predicted=[0.25, 1.0],
    atom_counts=[2, 8],
    offset_per_atom=0.0625,
    weighting="atom",
)
assert energy.residuals == (0.125, 0.125)
assert energy.corrected_residuals == (0.0625, 0.0625)
assert energy.statistics.mae == 0.125
```

The chosen offset should come from training or a separate calibration set. A
constant per-atom energy shift can be physically harmless for some comparisons,
but reporting only shift-corrected errors hides that model bias and may conceal
composition-dependent errors.

## Forces

`force_errors` accepts one `(atoms, 3)` array for each configuration. Arrays
must use identical atom order on both sides, and each species label must refer
to the atom at the same position. The helper cannot match atoms, detect
permutations, or identify train/test leakage. It reports x/y/z component
statistics, Euclidean vector errors, each configuration's metrics, and
component statistics grouped by species. The `atom` weighting gives each atom
equal weight. The `configuration` weighting gives each configuration equal
total weight and divides that weight equally among its atoms. Species summaries
condition and renormalize the selected weights on that species. The 95th
percentile remains unweighted.

```python
from httk.analyse.matsci.mlip import force_errors

forces = force_errors(
    reference=[[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]],
    predicted=[[[3.0, 4.0, 0.0], [0.0, 0.0, 0.0]]],
    species=[["Si", "O"]],
)
assert forces.component_statistics[0].mae == 1.5
assert forces.mean_vector_error == 2.5
assert abs(forces.rms_vector_error - 5.0 / 2.0**0.5) < 1e-12
assert dict(forces.per_species_component_statistics)["Si"][0].maximum_absolute_error == 3.0
```

Force errors are sensitive to physical atom pairing and to whether reference
and predicted forces use the same coordinate frame, constraints, electronic
convergence, and force convention. Do those checks before comparing metrics.

`rms_vector_error` is the root mean square Euclidean norm of the per-atom
residual vectors. The pooled per-component force RMSE common in the literature
equals `rms_vector_error / sqrt(3)` for `weighting="atom"` (every atom equal),
so compare `rms_vector_error` with published values only after that division.

## Stress

`stress_errors` accepts matching `(configurations, 3, 3)` symmetric tensors. It
uses tensile-positive stress in GPa and reports the independent
components in `xx, yy, zz, yz, xz, xy` order. It checks symmetry within a
relative and absolute tolerance of `1e-12`, reads the listed upper-triangle
shear components, and does not symmetrize tensors. Convert virials, pressure
signs, and unit conventions in the source adapter before calling it.

The `1e-12` symmetry check is intentional and strict. Typical float32 model
outputs and virial (`-sum(r (x) F)`) stresses carry asymmetry of order `1e-8`
GPa and are rejected. Inspect the asymmetry magnitude, then
symmetrize explicitly, for example `(stress + stress.swapaxes(1, 2)) / 2`,
before calling `stress_errors`.

```python
import numpy as np

from httk.analyse.matsci.mlip import stress_errors

reference = np.zeros((1, 3, 3))
predicted = np.array([[[1, 2, 3], [2, 4, 5], [3, 5, 6]]], dtype=float)
stress = stress_errors(reference, predicted)
assert stress.residuals == ((1.0, 4.0, 6.0, 5.0, 3.0, 2.0),)
```

## Property bindings

Each result always binds one dictionary-valued summary that carries its conditions
as members, so differently weighted or offset-corrected summaries are distinct
values of the same definition:

- `EnergyErrors` binds `energy_prediction_errors` (`validation/energy_prediction_errors`):
  `weighting`, `offset_per_atom` (null, the raw comparison), `count`, `bias`, `mae`,
  `rmse`, `maximum_absolute_error`, `percentile95_absolute_error` (eV/atom) and the
  per-configuration `residuals`. When an offset was applied it also binds
  `corrected_energy_prediction_errors`, the same definition with `offset_per_atom`
  set and the corrected statistics and residuals; it is a separate record with its
  own content id.
- `ForceErrors` binds `force_prediction_errors`: `weighting`, atom `count`, the five
  component statistics as `(x, y, z)` vectors, `mean_vector_error`, `rms_vector_error`,
  per-configuration vector errors and component RMSE, and per-species statistics
  aligned with `species_labels` (the code-point sorted labels of the result's
  per-species statistics).
- `StressErrors` binds `stress_prediction_errors`: `count`, the five component
  statistics as six-vectors in `xx, yy, zz, yz, xz, xy` order (GPa) and `residuals`.

The summaries are always bound, so `records()` never warns about an empty binding
for these types. Maximum and 95th-percentile errors are unweighted under every
weighting.

In addition, the natural populations keep queryable derivation records, which
equal the matching summary members. A statistic's population is part of its
meaning and derivation terms do not carry the weighting, so the raw
`EnergyErrors.statistics` (`rmse`, `mae`, `bias`, `maximum_absolute_error`) bind to
`total_energy_per_atom` (eV/atom) with the matching derivation term only when
`weighting="configuration"`. `ForceErrors.component_statistics` binds to the core
`atomic_force` (eV/angstrom) with the same four derivation terms, each value the
`(x, y, z)` vector, only when `weighting="atom"`. The four
`StressErrors.component_statistics` metrics bind to the core `stress_tensor` (GPa) as
lists of six in `xx, yy, zz, yz, xz, xy` order, again with derivation terms, always.
Atom-weighted energy errors and configuration-weighted force errors therefore bind
only the summary.

```python
from httk.analyse.matsci.mlip import energy_errors
from httk.analyse.records import bound_values

bound = bound_values(energy_errors([0.0, 0.0], [1.0, 1.0], atom_counts=[1, 1]))
assert [b.field for b in bound][0] == "statistics.rmse"
assert bound[0].value == 1.0
assert bound[-1].field == "energy_prediction_errors"
assert bound[-1].value["offset_per_atom"] is None
```

These summaries describe residuals on the supplied samples; they do not
estimate uncertainty or establish transferability. Keep validation structures
and configurations independent of training, inspect residual distributions,
and report the selected weighting, units, and any explicit energy calibration.

## Derived properties and conservation

`httk.analyse.matsci.validation.property_parity` compares paired scalar
properties with explicit labels and a property-definition IRI (`definition`,
not loaded; `None` when no definition is published). It retains both inputs and raw
residuals. Compare EOS volumes/moduli, elastic components, positive phonon
frequencies, RDF curves or diffusion coefficients only on matched structures,
normalizations, grids and sampling protocols. The values must already be in the unit that definition fixes; there is no
automatic unit conversion.

`energy_drift` requires `ensemble="NVE"`, selected increasing times in ps,
total energies in eV and a constant atom count. It reports a fitted slope in
eV/atom/ps, the intercept at the first time, residual RMS and observed endpoint
change. Thermostat/barostat energy exchange is not a model conservation test.
`records()` stores the result as one `nve_energy_drift` dictionary (slope,
intercept at `start`, residual RMS, observed endpoint change, `start`, `stop`
and `samples`).

```python
import numpy as np
from httk.analyse.matsci.validation import energy_drift
from httk.analyse.records import bound_values

drift = energy_drift(np.arange(5.0), 2.0 * np.arange(5.0), atom_count=2, ensemble="NVE")
assert bound_values(drift)[0].value["samples"] == 5
```

`force_energy_consistency` evaluates `-dE/dx` using central differences at an
explicit displacement in angstrom and compares with forces in eV/angstrom.
Check at multiple displacement sizes: truncation error falls with the square
of the step until cancellation or energy noise dominates. The energy callable
receives independent position copies. It must implement the same cell,
periodicity, atomic ordering, units and model as the supplied force evaluation.

`committee_spread` returns per-entry means and model standard deviations for
a common property-definition IRI. This describes disagreement, not calibrated predictive
uncertainty. Shared training data and model bias can make every committee member
agree while all are wrong.

For holdout validation, split complete independent trajectories or material
families before extracting frames. Adjacent frames from one trajectory must not
be randomly scattered between training and test sets. Keep temperature,
composition, strain and defect coverage visible in the reported labels.

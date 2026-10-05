# Recording results

Every public value of an analysis result is in the unit of its property
definition, and values never carry unit strings. The definitions (IRIs in
`httk.analyse.definitions`, core quantities such as temperature in
`httk.core.definition_ids`) fix the name, unit, shape and meaning. Statistics of
a property, such as a mean or a standard error, keep the base definition and add
a derivation term (`MEAN`, `STANDARD_ERROR`, `RMSE`, ...) instead of defining a
new property.

## Records

`httk.analyse.records.records(result, *, product_of=(), **selection)` returns one
record per bound value of a result, each checked against its definition first.
A property value (scalar, fixed-size or a series) becomes an
`httk.core.DataRecord`; a statistic of a property becomes an
`httk.core.DerivedDataRecord` whose `definition_id` and `name` are the base
property's and whose `derivation` is the derivation-term IRI:

```python
import numpy as np
from httk.core import DerivedDataRecord
from httk.core.units import default_registry
from httk.analyse import definitions as defs
from httk.analyse.matsci import fit_birch_murnaghan
from httk.analyse.records import bound_values, records

volumes = np.linspace(8.5, 11.5, 9)
strain = (10.0 / volumes) ** (2 / 3) - 1
energies = -5.0 + 9 * 10.0 * 0.2 / 16 * (2 * strain**2 + 0.5 * strain**3)
fit = fit_birch_murnaghan(volumes, energies)
made = records(fit)
assert [record.name for record in made] == [
    "equilibrium_volume", "equilibrium_energy", "bulk_modulus", "bulk_modulus_pressure_derivative", "total_energy",
]
assert isinstance(made[-1], DerivedDataRecord) and made[-1].derivation == defs.RMSE
# Input energies use eV and angstrom^3; the fitted bulk modulus is in GPa.
assert abs(fit.bulk_modulus - default_registry().convert(0.2, "angstrom^-3*eV", "GPa")) < 1e-6
```

`bound_values(result, **selection)` lists every binding as
`BoundValue(field, binding, value)`, where `binding` is a
`FieldBinding(definition, derivation=None)`. `field` is a binding
name, not necessarily an attribute path: `isotropic` of a diffusion fit,
`integrals[4]` or `isotropic[4]` of a transport result at the selected lag,
`standard_errors.<name>` of an equilibrium response, and the definition name of
a series are computed or selected values. The EOS `rmse` is bound to the core
total energy with the `RMSE` derivation. Passing an object that has no bindings
raises `TypeError`.

Bound result types: `BirchMurnaghanFit`, `EOSFit`, `ElasticTensor` (stiffness,
compliance, Voigt/Reuss/Hill moduli, universal anisotropy), `FormationEnergy`,
`BandEdges` (gaps are 0.0 for a metal), `EquilibriumResponse`,
`HarmonicThermodynamics`, `QuasiHarmonicResult`, `DiffusionFit`,
`TensorSeries`, `RadialDistribution`, `TransportResult`, `ReplicaTransport`,
`PropertyParity` (statistics of its `definition`) and the spin-summed
`httk.analyse.integrations.vasp.VaspDOS`.

Scalar, dictionary and statistic bindings of the electronic, defect, kinetics
and MLIP results:

| Result | Field | Definition |
| --- | --- | --- |
| `EffectiveMassFit` | `mass_tensor` | `relative_effective_mass` (`center`, `tensor`) |
| `DielectricSummary` | `mean` | `static_relative_permittivity` or `high_frequency_relative_permittivity`; the selection `kind="static"` or `"high_frequency"` is required |
| `MagneticMoments` | `total` | `total_magnetic_moment` |
| `DefectFormationEnergy` | `energy` | `charged_defect_formation_energy` (one dictionary with the inputs the formula used) |
| `ChargeTransition` | `fermi_level` | `charge_transition_level` (`charges`, `fermi_level`) |
| `SurfaceEnergy` | `surface_energy` | `surface_energy` (J/m²) |
| `NEBProfile` | `forward_barrier`, `reverse_barrier` | `migration_barrier_forward`, `migration_barrier_reverse` |
| `ArrheniusFit` | `activation_energy` | `activation_energy` |
| `EnergyErrors` | `statistics.<stat>` | `total_energy_per_atom` with `RMSE`, `MAE`, `BIAS`, `MAXIMUM_ABSOLUTE_ERROR` |
| `StressErrors` | `component_statistics.<stat>` | `stress_tensor` (Voigt list of six) with the same four derivations |

Not bound: `ForceErrors`, the offset-corrected energy statistics and the
Arrhenius prefactor (its unit is caller-chosen).

```python
from httk.analyse.matsci.mlip import energy_errors

made = records(energy_errors([0.0, 0.0], [1.0, 3.0], atom_counts=[1, 1]))
assert [record.derivation for record in made] == [defs.RMSE, defs.MAE, defs.BIAS, defs.MAXIMUM_ABSOLUTE_ERROR]
```

## Series

A function-valued result is one value of a dictionary-typed definition whose
members are plain lists sharing a dimension, in the definition's units. Its
binding name is the definition name:

| Result | Definition | Members |
| --- | --- | --- |
| `HarmonicThermodynamics` | `vibrational_thermodynamics` | `temperatures`, `helmholtz_free_energies`, `internal_energies`, `entropies`, `heat_capacities` |
| `QuasiHarmonicResult` | `quasiharmonic_thermodynamics` | `temperatures`, `equilibrium_volumes`, `total_helmholtz_free_energies` (static energy included), `bulk_moduli`, `volumetric_thermal_expansions` |
| `TensorSeries` (`msd`) | `mean_squared_displacement` | `lag_times`, `msd`, `origin_counts` |
| `TensorSeries` (`vacf`) | `velocity_autocorrelation` | `lag_times`, `vacf`, `origin_counts` |
| `TensorSeries` (`vacf_integral`) | `diffusion_running_integral` | `lag_times`, `diffusion_tensors` (converted to m²/s) |
| `RadialDynamics` | `self_van_hove_function` or `distinct_van_hove_function` by `kind` | `lag_time`, `bin_edges`, `density`, `counts`, `samples` |
| `ScatteringSeries` | `self_intermediate_scattering_function` or `intermediate_scattering_function` by `kind` | `lag_times`, `wavevectors`, `real`, `imaginary` (complex values split), `origin_counts` |
| `VelocitySpectrum` | `velocity_power_spectrum` | `frequencies`, `power`, `window`, `mean_removed`, `mean_square` |
| `BondOrder` | `steinhardt_bond_order` | `degree`, `cutoff`, `global_order`, `local_orders`, `coordination_numbers` (`null` for isolated atoms) |
| `RadialDistribution` | `radial_distribution_function` | `bin_edges`, `g`, and `pair` for a partial RDF |
| `TransportResult` | `thermal_conductivity_running_integral` or `shear_viscosity_running_integral` | `lag_times`, `thermal_conductivity_tensors` (3×3 per lag) or `shear_viscosities` (xy, xz, yz per lag) |
| `VaspDOS` (spin-summed) | `electronic_density_of_states` | `energies`, `density`, `integrated_density` |

The harmonic zero-point energy and the DOS Fermi energy are separate scalar
records. A `RadialDistribution` needs exactly one more bin edge than `g` value,
and a spin-resolved `VaspDOS` has no definition; both raise `ValueError`.

```python
import json

from httk.analyse.matsci import harmonic_thermodynamics

result = harmonic_thermodynamics([2.0, 4.0], [0.0, 300.0])
series = {record.name: record for record in records(result)}["vibrational_thermodynamics"]
assert sorted(json.loads(series.value_json)) == [
    "entropies", "heat_capacities", "helmholtz_free_energies", "internal_energies", "temperatures",
]
```

## Explicit plateau selection

Running Green–Kubo integrals have no inferred plateau. A `TransportResult`
always records its running-integral series, temperature and volume; with
`lag_index=`, the caller's choice of lag, it also records the plateau
coefficients:

```python
from httk.analyse.matsci import thermal_conductivity

current = np.random.default_rng(0).normal(size=(40, 3))
result = thermal_conductivity(current, 0.01, temperature=300, volume=125, max_lag=6)
assert [record.name for record in records(result)] == [
    "thermal_conductivity_running_integral", "temperature", "volume",
]
recorded = {record.name for record in records(result, lag_index=4)}
assert recorded == {
    "thermal_conductivity_running_integral", "thermal_conductivity_tensor", "thermal_conductivity",
    "temperature", "volume",
}
```

A `ReplicaTransport` requires `lag_index=` and records the replica mean and
standard error at that lag as derived data records (`MEAN`, `STANDARD_ERROR`).
Omitting it raises `TypeError`, and an index outside the lag grid raises
`ValueError`.

## Summaries

`analysis_summary(result, ...)` stores the same bindings, keyed by binding name
and each with its value, in its `fields` object, so the summary and the records
agree. See {doc}`analysis-artifacts`, and {doc}`analysis-recipes` for storing
both in SQLite.

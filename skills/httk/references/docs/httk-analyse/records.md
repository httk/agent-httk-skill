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
checked record per bound value of a result. A property value becomes the typed
record kind generated from its definition: `httk.analyse.property_records` has
one per analyse definition (`BulkModulusRecord`, `EnergyPredictionErrorsRecord`,
...), `httk.core.property_records` the core ones (`TemperatureRecord`,
`VolumeRecord`, ...), and total energy uses `httk.core.TotalEnergyRecord`. A
typed record's `definition_id` is the definition IRI and its `value` the value
shaped as the definition says. A statistic of a fixed base property becomes its
generated statistic kind (`TotalEnergyRmseRecord`,
`TotalEnergyPerAtomMaeRecord`, ...), whose `definition_id` is the base IRI and
whose `derivation` is the derivation-term IRI. A statistic of a caller-chosen base
(`PropertyParity`) becomes an `httk.core.DerivedDataRecord` with the same
`definition_id` and `derivation`. A null value becomes a generic
`httk.core.DataRecord`, the catch-all that keeps a value as JSON:

```python
import numpy as np
from httk.core.definition_ids import TOTAL_ENERGY
from httk.core.units import default_registry
from httk.analyse import definitions as defs
from httk.analyse.matsci import fit_birch_murnaghan
from httk.analyse.records import bound_values, records

volumes = np.linspace(8.5, 11.5, 9)
strain = (10.0 / volumes) ** (2 / 3) - 1
energies = -5.0 + 9 * 10.0 * 0.2 / 16 * (2 * strain**2 + 0.5 * strain**3)
fit = fit_birch_murnaghan(volumes, energies)
made = records(fit)
assert [type(record).__name__ for record in made] == [
    "EquilibriumVolumeRecord", "EquilibriumEnergyRecord", "BulkModulusRecord", "BulkModulusPressureDerivativeRecord",
    "TotalEnergyRmseRecord",
]
assert made[2].definition_id == defs.BULK_MODULUS and made[2].value == fit.bulk_modulus
assert (made[-1].definition_id, made[-1].derivation, made[-1].value) == (TOTAL_ENERGY, defs.RMSE, fit.rmse)
# Input energies use eV and angstrom^3; the fitted bulk modulus is in GPa.
assert abs(fit.bulk_modulus - default_registry().convert(0.2, "angstrom^-3*eV", "GPa")) < 1e-6
```

A store serves each typed value as the OPTIMADE property `_httk_<name>` and
filters on it: scalars compare (`_httk_bulk_modulus > 100`; float equality is
exact), dictionary members filter by nested name
(`_httk_energy_prediction_errors.weighting = "configuration" AND _httk_energy_prediction_errors.rmse < 0.005`),
one-dimensional list members take `HAS`, `HAS ALL`, `HAS ANY` and `HAS ONLY`, and
`LENGTH` is the outer length of a list. A statistic kind is served as
`_httk_<base>_<derivation>` (`_httk_total_energy_per_atom_rmse < 0.005`) under an
ad-hoc definition synthesized from the base, which is not a published
definition. Generic `DataRecord` and `DerivedDataRecord` values are not served.
A store declares the kinds it holds in the records family; declaring all
generated kinds is fine, and reopening an existing store with a longer
declaration and `upgrade=True` adds kinds (an additive change). With
*httk-store* installed:

```python
from httk.core import DataRecord, DataRecordEntry
from httk.store import EntryIdScheme
from httk.store.backend.sql import Backend, SqlStore

kinds = (DataRecord, *dict.fromkeys(type(record) for record in made))
with Backend.sqlite() as database:
    store = SqlStore(database, entry_records={DataRecordEntry: kinds}, entry_ids=EntryIdScheme("example", "1"))
    for record in made:
        store.save(record)
    searchers = store.stored_property_plan(DataRecordEntry).filter_searchers("_httk_bulk_modulus > 20")
    assert [row[0].value for searcher in searchers for row in searcher.results()] == [fit.bulk_modulus]
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
`PropertyParity` (statistics of its `definition`, as `DerivedDataRecord`),
`ElasticFit` (delegates to
its `tensor`, so an unstable or singular tensor raises as `ElasticTensor` does),
`GruneisenFit`, `ChemicalPotentialRegion`, `PhaseDiagram` and
`httk.analyse.integrations.vasp.VaspDOS` (spin-summed or one collinear spin channel).

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
| `EnergyDrift` | `nve_energy_drift` | `nve_energy_drift` (one dictionary) |
| `EnergyErrors` | `statistics.<stat>` | `total_energy_per_atom` with `RMSE`, `MAE`, `BIAS`, `MAXIMUM_ABSOLUTE_ERROR` (configuration weighting only) |
| `EnergyErrors` | `energy_prediction_errors`, and `corrected_energy_prediction_errors` when an offset was applied | `energy_prediction_errors` (always; the two values are distinct records) |
| `ForceErrors` | `component_statistics.<stat>` | `atomic_force` with the same four derivations (atom weighting only) |
| `ForceErrors` | `force_prediction_errors` | `force_prediction_errors` (always) |
| `StressErrors` | `component_statistics.<stat>` | `stress_tensor` (Voigt list of six) with the same four derivations |
| `StressErrors` | `stress_prediction_errors` | `stress_prediction_errors` (always) |

The prediction-error dictionaries carry weighting, offset and species conditions
as members; the derivation records are the natural-population equivalents of
their members and are kept for querying. Not bound: the Arrhenius prefactor (its
unit is caller-chosen).

```python
from httk.analyse.matsci.mlip import energy_errors

made = records(energy_errors([0.0, 0.0], [1.0, 3.0], atom_counts=[1, 1]))
assert [getattr(record, "derivation", None) for record in made] == [defs.RMSE, defs.MAE, defs.BIAS, defs.MAXIMUM_ABSOLUTE_ERROR, None]
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
| `VaspDOS` (up or down channel) | `spin_channel_electronic_density_of_states` | `spin`, `energies`, `density`, `integrated_density` |
| `GruneisenFit` | `mode_gruneisen_parameters` | `reference_volume`, `values` (per mode), `degree` |
| `ChemicalPotentialRegion` | `chemical_potential_region` | `elements`, `host_coefficients`, `host_energy`, `competing_coefficients`, `competing_energies` (competing lists may be empty) |
| `PhaseDiagram` | `convex_hull_phase_diagram` | `elements`, `phase_ids`, `compositions`, `energies_per_atom`, `energies_above_hull_per_atom`, `stable` and `tolerance`, for the phases with known energy |

The harmonic zero-point energy and the DOS Fermi energy are separate scalar
records for every DOS channel. A `RadialDistribution` needs exactly one more bin
edge than `g` value, otherwise `ValueError` is raised; a non-collinear `VaspDOS`
is not bound.

```python
from httk.analyse.matsci import harmonic_thermodynamics

result = harmonic_thermodynamics([2.0, 4.0], [0.0, 300.0])
series = {record.definition_id: record for record in records(result)}[defs.VIBRATIONAL_THERMODYNAMICS]
assert sorted(series.value) == [
    "entropies", "heat_capacities", "helmholtz_free_energies", "internal_energies", "temperatures",
]
```

## Explicit plateau selection

Running Green–Kubo integrals have no inferred plateau. A `TransportResult`
always records its running-integral series, temperature and volume; with
`lag_index=`, the caller's choice of lag, it also records the plateau
coefficients:

```python
from httk.core.definition_ids import TEMPERATURE, VOLUME
from httk.analyse.matsci import thermal_conductivity

current = np.random.default_rng(0).normal(size=(40, 3))
result = thermal_conductivity(current, 0.01, temperature=300, volume=125, max_lag=6)
assert [type(record).__name__ for record in records(result)] == [
    "ThermalConductivityRunningIntegralRecord", "TemperatureRecord", "VolumeRecord",
]
recorded = {record.definition_id for record in records(result, lag_index=4)}
assert recorded == {
    defs.THERMAL_CONDUCTIVITY_RUNNING_INTEGRAL, defs.THERMAL_CONDUCTIVITY_TENSOR, defs.THERMAL_CONDUCTIVITY,
    TEMPERATURE, VOLUME,
}
```

A `ReplicaTransport` requires `lag_index=` and records the replica mean and
standard error at that lag as statistic kinds (`MEAN`, `STANDARD_ERROR`).
Omitting it raises `TypeError`, and an index outside the lag grid raises
`ValueError`.

## Summaries

`analysis_summary(result, ...)` stores the same bindings, keyed by binding name
and each with its value, in its `fields` object, so the summary and the records
agree. See {doc}`analysis-artifacts`, and {doc}`analysis-recipes` for storing
both in SQLite.

# Defects, surfaces, and kinetics

`httk.analyse.matsci.defects` contains explicit-reference energy summaries.
All energies use eV, chemical potentials use eV per atom, surface energies
are reported in J/m² (converted once from eV/angstrom² by the unit engine; the total energy stays in eV and the exposed area in
angstrom²), and Arrhenius temperatures use K. The functions do not
decide whether calculations or references are physically comparable.

## Defect formation energy

`defect_formation_energy` evaluates

```text
Edef - Ehost - sum(delta_n * mu) + q * (EF + VBM + alignment) + correction
```

The caller supplies every reference and additive correction. Positive integer
atom deltas mean atoms were added to the defect cell; negative deltas mean
atoms were removed. Positive integer charge means electrons were removed.
The result retains the signed terms so the total can be audited. The API does
not select a charged-defect correction scheme.

`alignment` is the potential alignment ΔV = V_def(far from defect) -
V_host(far) (Van de Walle and Neugebauer), entering as `q * alignment`.
Freysoldt- or Kumagai-type `correction` values often already include the
`-q * ΔV` alignment term, so it must not be counted twice.

```python
from httk.analyse.matsci.defects import defect_formation_energy

formation = defect_formation_energy(
    defect_energy=-12.0,
    host_energy=-10.0,
    atom_deltas={"O": 1},
    chemical_potentials={"O": -2.0},
    charge=1,
    fermi_level=0.4,
    vbm=0.0,
    alignment=0.1,
    correction=0.2,
)
assert formation.energy == 0.7
```

`charge_transition_levels` takes line intercepts at `EF=0` and an explicit
finite Fermi-level interval. It reports only crossings on the lower envelope;
metastable pair crossings are omitted. Ties list every charge state within
the requested absolute energy tolerance. Endpoint crossings are excluded.

The intercepts must be formation energies at `E_F = 0` measured from the VBM,
that is `defect_formation_energy(..., fermi_level=0.0).energy` for each charge.
The bound `charge_transition_level` defines its `fermi_level` relative to the
VBM, and this cannot be checked, so other intercept scales are mislabelled.
Its `charges` are `[q, q']` with q > q': the stable charge at lower and at
higher Fermi level.

`DefectFormationEnergy` also retains the `fermi_level`, `vbm`, `alignment`,
`correction` and `chemical_potentials` (element and eV-per-atom pairs for the
elements of `atom_deltas`) that the formula used, so the result is
self-describing.

## Property bindings

`httk.analyse.records.bound_values(result)` returns the property-definition
bindings of these results (values are plain JSON data in the definition units):

| Result | Field | Definition |
| --- | --- | --- |
| `DefectFormationEnergy` | `energy` | `charged_defect_formation_energy` dictionary: `charge`, `energy`, `fermi_level`, `vbm`, `alignment`, `correction`, and lists `elements`, `atom_changes`, `chemical_potentials` ordered by element |
| `ChargeTransition` | `fermi_level` | `charge_transition_level`: `charges` `[left, right]` (the lower-envelope charges either side of the crossing) and `fermi_level` |
| `SurfaceEnergy` | `surface_energy` | `surface_energy` (J/m²) |
| `NEBProfile` | `forward_barrier`, `reverse_barrier` | `migration_barrier_forward`, `migration_barrier_reverse` |
| `ArrheniusFit` | `activation_energy` | `activation_energy`; `prefactor` as `arrhenius_prefactor` (`s^-1`) when `rate_unit` has dimension `s^-1`, or `diffusion_prefactor` (`m^2*s^-1`) when it has dimension `m^2*s^-1`, converted from `rate_unit`; for any other unit only the activation energy is bound |

```python
from httk.analyse.matsci.defects import surface_energy
from httk.analyse.records import bound_values

surface = surface_energy(-3.0, -1.0, 4, {}, {}, total_exposed_area=2.0)
(bound,) = bound_values(surface)
assert abs(bound.value - 0.5 * 16.02176634) < 1e-9
```

## Surfaces and adsorption

`surface_energy` computes

```text
E_slab - N_bulk * E_bulk_per_atom - sum(delta_n * mu)
```

`bulk_reference_atom_count` is `N_bulk`: the stoichiometric atom count in the
bulk reference **before** adding or removing the excess atoms. It need not
equal the actual slab count. For an AB bulk reference with four atoms,
`delta_n["A"] = 1` refers to a five-atom A-rich slab, while
`delta_n["A"] = -1` refers to a three-atom A-deficient slab. This avoids
counting the excess atoms once in the bulk reference and again in the
chemical-potential term. Supply the **total exposed area** in angstrom²,
including all faces whose energy is being reported. This makes the two-face
factor explicit in the supplied area. `adsorption_energy`
returns combined minus clean substrate minus the counted adsorbate references;
negative values favor binding. `segregation_energy(source, target)` returns
target minus source energy for two caller-matched defect environments.

## NEB profile

`neb_profile` requires one strictly increasing reaction coordinate per image.
It reports the maximum sampled image and forward/reverse barriers measured
from the two endpoints. A tied maximum retains all image indices. It does not
interpolate an unsampled saddle or reorder images.

## Arrhenius fit

`fit_arrhenius` fits `ln(rate) = ln(prefactor) - Ea/(kB*T)` by ordinary or
positive-weight least squares. Rates and the prefactor share the required
`rate_unit`, an OPTIMADE unit expression such as `s^-1` (malformed expressions
such as `1/s` raise). The result includes log-rate residuals, matrix rank, a condition number for the scaled fit design, and weighted log
RMSE. Every supplied point is used; choose a physically justified linear fit
window before calling the function. The diagnostics do not establish that the
mechanism is Arrhenius over that range.

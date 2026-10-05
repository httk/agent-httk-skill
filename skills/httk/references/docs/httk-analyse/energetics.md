# Static energy bookkeeping

`httk.analyse.matsci.energetics` provides small immutable results for comparing
static calculations and combining phase energies. Energies are in eV. Each
total energy must use the same extensive basis as its composition; divide by
atom count only where the function explicitly reports per-atom values.

## Convergence tables

Choose the reference row explicitly. The function retains input order and
reports signed differences relative to that row. It does not infer convergence
from parameter ordering or judge whether two calculations are comparable.
Compare calculations only after checking that they use compatible structures,
electronic settings, energy definitions, and normalization. For example, basis
cutoff scans should keep composition, pseudopotentials, smearing, and k-point
sampling fixed while changing the cutoff.

```python
from math import isclose

from httk.analyse.matsci.energetics import convergence_table

table = convergence_table(
    parameters=(400, 500, 600),  # plane-wave cutoff labels, eV
    energies=(-20.0, -20.4, -20.5),  # total eV for two-atom cells
    reference_index=2,
    atom_counts=(2, 2, 2),
)
assert all(isclose(actual, expected) for actual, expected in zip(table.differences_per_atom, (0.25, 0.05, 0.0)))
```

## Reactions and formation energies

Reaction coefficients are signed: negative values are reactants and positive
values are products. Every element must balance within the explicit absolute
atom-count tolerance. `reaction_energy` returns the same products-minus-
reactants linear combination of total energies; it does not rescale energies.

```python
from httk.analyse.matsci.energetics import reaction_energy, formation_energy

# 2 Al + 3/2 O2 -> Al2O3, with E(Al) = -3 eV/atom and E(O2) = -4 eV (mu_O = -2 eV/atom)
delta_e = reaction_energy(
    energies=(-3.0, -4.0, -17.0),
    coefficients=(-2.0, -1.5, 1.0),
    compositions=({"Al": 1}, {"O": 2}, {"Al": 2, "O": 3}),
)
assert delta_e == -5.0  # equals the formation energy below

formation = formation_energy(
    energy=-17.0,
    composition={"Al": 2, "O": 3},
    chemical_potentials={"Al": -3.0, "O": -2.0},
)
assert formation.total == -5.0 and formation.per_atom == -1.0
```

Formation energy uses exactly the elemental reservoirs supplied by the caller.
Every element with positive composition needs a finite chemical potential, in
eV per atom. No zero reference or elemental energy is assumed implicitly.

## Chemical-potential regions

For a host phase, the region stores the equality
`sum(n_i * mu_i) = E_host`. Every competitor adds an upper bound
`sum(n_i * mu_i) <= E_competitor`. Add elemental reference phases to the
competitor list explicitly to impose their bounds. The `contains` method checks
these linear constraints for supplied potentials; it does not calculate a
phase hull or prove that omitted phases are irrelevant.

```python
from httk.analyse.matsci.energetics import chemical_potential_region

region = chemical_potential_region(
    host_composition={"A": 1, "B": 1},
    host_energy=-3.0,
    competing_compositions=({"A": 1}, {"B": 1}),  # explicit elemental phases
    competing_energies=(0.0, 0.0),
)
assert region.contains({"A": -1.0, "B": -2.0})
```

## Pressure enthalpy

`enthalpy` computes `E + P*V`. Use eV for energy, angstrom³ for volume, and
GPa for pressure (VASP prints pressure in kB; multiply by 0.1 to get GPa). Pressure is positive under compression, so it is
the negative volume derivative of energy under the usual convention. A scalar
pressure broadcasts across the input rows; vector pressures must match the
energy and volume vectors. Decide whether structures, branches, and electronic
protocols are comparable before comparing their enthalpies.

```python
from math import isclose

from httk.analyse.matsci.energetics import enthalpy

values = enthalpy(
    energies=(-2.0, -2.0),
    volumes=(10.0, 12.0),
    pressures=16.02176634,  # GPa, equal to 0.1 eV/angstrom³
)
assert all(isclose(actual, expected) for actual, expected in zip(values, (-1.0, -0.8)))
```

# Elasticity

`httk.analyse.matsci.elasticity` works with finite strain and stress arrays in
one explicit convention. Stiffness and stress use GPa (the units of the OPTIMADE `elastic_tensor` and
`stress_tensor` definitions), stress is
tensile-positive, and Voigt components are ordered `xx, yy, zz, yz, xz, xy`.
The strain shear entries are engineering strains `2*epsilon_ij`; stress shear
entries are tensor components `sigma_ij`. Convert signs, units, cell bases and
strain definitions in the data source before fitting. No cell-change strain or
stress convention is inferred.

## Elastic tensors

`ElasticTensor` copies its input into an immutable tuple-backed symmetric 6 by
6 matrix. It accepts unstable finite matrices so their eigenvalues and
pressure-corrected stability can be inspected. Its compliance property
inverts the matrix and raises for a singular stiffness. Voigt, Reuss and Hill
bulk and shear moduli use the conventional uniform-strain and uniform-stress
averages. Reuss quantities and the universal anisotropy index are undefined
when their compliance denominators are not positive.

The full fourth-rank stiffness uses the same values for all minor-symmetry
copies. The full compliance applies `1/(m_I*m_J)` to the inverse Voigt matrix,
where `m=(1,1,1,2,2,2)`. `rotate` applies an active proper Cartesian rotation
to all four tensor indices and rejects reflections and nonorthogonal matrices.

Directional Young's modulus uses a nonzero loading direction. Directional
shear modulus and Poisson ratio also require a nonzero perpendicular direction.
These calculations require a nonsingular compliance and positive longitudinal
or shear compliance where the corresponding modulus is defined.

```python
import numpy as np

from httk.analyse.matsci.elasticity import ElasticTensor

stiffness = np.zeros((6, 6))
stiffness[:3, :3] = 100.0
np.fill_diagonal(stiffness[:3, :3], 200.0)
stiffness[3:, 3:] = np.eye(3) * 50.0
elastic = ElasticTensor(stiffness)

assert np.isclose(elastic.bulk_modulus_hill, 400.0 / 3.0)
assert np.isclose(elastic.shear_modulus_hill, 50.0)
assert np.isclose(elastic.young_modulus((1.0, 0.0, 0.0)), 400.0 / 3.0)
assert np.isclose(elastic.poisson_ratio((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)), 1.0 / 3.0)
```

Zero-pressure stability tests positive definiteness using Kelvin-basis
eigenvalues and the caller’s absolute eigenvalue tolerance. `pressure_stability_eigenvalues` and
`is_stable_under_pressure` use the incremental correction

```text
B_ijkl = C_ijkl + P*(delta_ij*delta_kl - delta_ik*delta_jl - delta_il*delta_jk)
```

with hydrostatic compression positive and pressure in GPa. This is
Wallace's stress-strain coefficient tensor B for `sigma = -P*I`; in Voigt form
a cubic crystal gives `C11-P, C12+P, C44-P`. It is a hydrostatic incremental
criterion; it does not claim general finite-strain stability for arbitrary
prestress.

The correction is correct only when the input is the thermodynamic stiffness
`C`: the second derivative of energy with respect to Lagrangian strain about
the pressurised reference state. Stress-strain coefficients are already B.
That covers the output of `fit_stress_strain` and elastic constants a code
computes from stresses under pressure. Test those with `is_stable()`;
applying the pressure correction to them double-counts the pressure and can
report a stable crystal as unstable.

## Source stress conventions

This module is tensile-positive, in GPa, with components ordered
`xx, yy, zz, yz, xz, xy`. VASP OUTCAR "in kB" stresses are compressive-positive,
in kBar and ordered `XX YY ZZ XY YZ ZX`. To convert them, flip the sign,
multiply kBar by 0.1 to get GPa,
and reorder with the index list `[0, 1, 2, 4, 5, 3]`. LAMMPS pressure tensors
are also compressive-positive.

Raw code output is rarely exactly symmetric: for example the VASP "TOTAL
ELASTIC MODULI" matrix is asymmetric at about 0.1 kBar. `ElasticTensor` checks
symmetry to relative and absolute tolerance 1e-12 and rejects such input. Inspect the
asymmetry magnitude and symmetrize explicitly with `(C + C.T)/2` before
constructing an `ElasticTensor`.

## Fitting

`fit_stress_strain(strains, stresses, fit_offset=True)` jointly fits the 21
symmetric stiffness entries and, by default, six constant stress offsets. Each
input is a finite `(samples, 6)` array. The fit requires the complete design to
have full numerical rank.

`fit_energy_strain(strains, energies, volume, fit_offset=True)` fits

```text
E = E0 + volume*(stress_offset @ strain + 0.5*strain @ C @ strain)
```

where energies are total eV and `volume` is a positive reference volume in
angstrom³. The fitted tensor and stress offset are returned in GPa (converted
once from eV/angstrom³); energy residuals stay in eV. The default fits a constant energy and six linear stress terms. Set
`fit_offset=False` only when the energy reference and stress are explicitly
zero; that option fixes both offsets to zero. Neither fit infers strain from
cell changes.

`fit_stress_strain` returns the stress-strain coefficient tensor, which at
finite pressure is B rather than the thermodynamic stiffness C. At finite
pressure `fit_energy_strain` recovers C only from Lagrangian strains; small
linear strains give neither C nor B.

Both functions return the tensor, fitted offsets, input-order observed-minus-
fitted residuals, RMSE, condition number and per-component strain range. The
condition number is for the column-scaled design matrix; it describes the
linear solve and is not parameter confidence. Inspect the strain window and
fit stability under changed sampling. These are small-strain linear models,
not finite-pressure or nonlinear elasticity fits.

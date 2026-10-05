# Static equation-of-state fitting

Use {py:func}`httk.analyse.matsci.eos.fit_birch_murnaghan` for a third-order
Birch–Murnaghan fit of static energies against volume. At least five distinct
positive volumes are required. The result is an immutable
{py:class}`httk.analyse.matsci.eos.BirchMurnaghanFit`.

```python
from httk.analyse.matsci import fit_birch_murnaghan

# volumes: angstrom³; energies: eV, both per cell or both per atom.
fit = fit_birch_murnaghan(volumes, energies)
print(fit.equilibrium_volume, fit.equilibrium_energy)
print(fit.bulk_modulus, fit.bulk_modulus_derivative)
print(fit.rmse, fit.residuals)
pressure = fit.pressure(fit.equilibrium_volume)  # GPa
```

## Prepare a consistent volume scan

Use one composition and phase branch with consistent electronic settings,
energy definition, and relaxation protocol. Fixed-shape scaling and relaxation
of internal coordinates or cell shape at fixed volume need not give the same
response. Document the protocol alongside the result. A DFT scan must converge
energies with respect to basis size and Brillouin-zone sampling before its
curvature can be trusted.

The inputs determine normalization; the fitter cannot detect a total-energy
array paired with per-atom volumes. Scale both together. The modulus remains
unchanged when both extensive quantities are divided by the same atom count.

Mean total or potential energies from finite-temperature MD do not define an
isothermal pressure EOS. That requires the volume derivative of Helmholtz free
energy or a separately specified pressure-volume analysis. This routine does
not perform that analysis.

## Model and diagnostics

For $q=(V_0/V)^{2/3}-1$, the model is

$$E(V)=E_0+\frac{9B_0V_0}{16}\left[2q^2+(B'_0-4)q^3\right].$$

The implementation fits a cubic in $(V_\mathrm{ref}/V)^{2/3}$ using centered,
scaled linear least squares, then derives the equilibrium parameters. It
requires a stable minimum strictly inside the sampled volume interval. Invalid
or rank-deficient inputs and absent interior minima raise `ValueError`.

- `bulk_modulus` and `pressure(volume)` are in GPa (energies eV, volumes
  angstrom³). Pressure is positive under compression and equals $-dE/dV$.
- `bulk_modulus_derivative` is dimensionless, $dB/dP$ at equilibrium.
- `residuals` are observed minus predicted energies in original input order;
  `rmse` is their root mean square in eV.
- `condition_number` describes the **scaled polynomial design**. It measures
  the linear solve, not how well the physical parameters are constrained.

A small residual and good design condition do not establish accurate $B_0$ or
$B'_0$. Inspect residuals, vary the fit window, and increase volume coverage.
The pressure derivative is especially sensitive to noise in a narrow window.
No parameter confidence intervals or fit-quality certification are returned.
`energy(volume)` and `pressure(volume)` allow extrapolation to positive finite
volumes; physical accuracy beyond the sampled interval is not established.

See the executed {doc}`notebooks/materials-toolbox` for a synthetic scan and
the [ASE EOS documentation](https://ase.gitlab.io/ase/ase/eos.html) for other
standard EOS families. The NumPy-only routine implements BM3; optional nonlinear models are described below.

## Weighted fits and model comparison

Install `httk-analyse[scipy]` to use `matsci.eos_models.fit_eos`. Select
`model="birch-murnaghan"`, `"murnaghan"`, or `"vinet"` explicitly. Positive
relative weights multiply squared residuals; equal weights are the default.
Results report both weighted and unweighted RMSE and the weighted Jacobian's
condition number. These remain numerical diagnostics, not confidence intervals.

```python
import numpy as np
from httk.analyse.matsci.eos_models import fit_eos

volumes = np.linspace(14.0, 18.0, 13)
# Synthetic static branch, consistent per-atom eV / angstrom³ basis.
energies = -4.0 + 0.02 * (volumes - 16.0)**2
models = [fit_eos(volumes, energies, model=name)
          for name in ("birch-murnaghan", "murnaghan", "vinet")]
for fitted in models:
    print(fitted.model, fitted.equilibrium_volume, fitted.bulk_modulus,
          fitted.rmse)
```

The nonlinear solver starts from the algebraic BM3 solution, constrains a
positive modulus and bracketed equilibrium volume, and rejects failed or
rank-deficient fits. Energy evaluation integrates the model's dimensionless
analytic pressure with SciPy quadrature. This avoids removable singularities
at Murnaghan B′=0/1 and Vinet B′=1. These limits are tested along with independent
ASE energy values and finite-difference pressure derivatives. Model comparison
uses the same observations and weighting; a smaller residual alone does not
establish which model extrapolates accurately.

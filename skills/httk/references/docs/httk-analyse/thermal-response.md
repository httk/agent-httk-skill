# Equilibrium response and transport

## Ensemble fluctuations

`httk.analyse.matsci.thermodynamics.equilibrium_response` accepts an explicit
ensemble and temperature in K. NVT uses total energy in eV for
`Cv = var(E)/(kB*T**2)`. NPT uses enthalpy in eV and volume in angstrom³ for
`Cp = var(H)/(kB*T**2)`, isothermal compressibility
`var(V)/(kB*T*mean(V))`, and volumetric expansion
`cov(V,H)/(kB*T**2*mean(V))`. Results are named after property definitions: `heat_capacity_constant_volume` and
`heat_capacity_constant_pressure` are extensive eV/K; `isothermal_compressibility`
is GPa⁻¹; `volumetric_thermal_expansion` is K⁻¹. Inputs must describe a
stationary equilibrated ensemble. Potential energy alone generally does not
give the total heat capacity.

E, H and V are whole-system totals of the simulated cell, never per-atom or
normalized values; divide results by N afterwards. Per-atom inputs (for
example LAMMPS `thermo_modify norm yes`) divide Cv and Cp by N² and
compressibility and expansion by N, so Cp per atom is Cp(total)/N, not the
value computed from per-atom data.

NPT enthalpy is `H = E_total + P_ext*V`, where `E_total` includes kinetic
energy and `P_ext` is the fixed barostat set-point pressure. The LAMMPS
`enthalpy` thermo keyword is `etotal + press*vol` with the *instantaneous*
pressure, which biases Cp and the expansion; build H from `etotal`, the
set-point and `vol` instead. For a classical NVT system, `Cv` can optionally be
obtained from the potential energy as `Var(U)/(kB*T**2) + (N_f/2)*kB`, with
`N_f` the number of kinetic degrees of freedom; this is a note only and is not
implemented.

Moments use population normalization. An optional explicit `block_size`
returns estimates per nonoverlapping block and their standard errors. At least
two complete blocks are required. A partial tail raises unless
`remainder="drop"` is supplied; the result reports dropped samples. Block
independence and convergence with block length remain scientific checks for
the caller. Each block uses population moments about its own mean, so short
blocks are biased low by a factor `(n_b - 1)/n_b` plus about `2*tau/n_b`, with
`tau` the integrated correlation time in samples and `n_b` the block length in
samples; use block lengths much longer than `tau`.

## Green–Kubo transport

`httk.analyse.matsci.transport.thermal_conductivity` consumes **extensive heat
current** in eV*angstrom/ps, uniform spacing in ps, temperature in K and fixed
volume in angstrom³. It returns the full running tensor in W/(m*K) (the unit of the
`thermal_conductivity` definition; viscosity results are in Pa*s):

`kappa_ij(t) = integral <J_i(0) J_j(tau)> d tau / (kB*T**2*V)`.

`viscosity` consumes symmetric tensile-positive stress in GPa and
returns running xy, xz and yz shear responses in Pa*s, using `V/(kB*T)` times
their autocorrelation integrals. Their mean over these three components only
is the isotropic estimate; the five-component traceless (Daivis–Evans)
estimator is not implemented, nor a complete anisotropic viscosity tensor. Correlations use all
available time origins with lag-specific counts. Both functions subtract the
temporal mean by default, retain the raw dimensionful correlations, and use
trapezoidal running integration starting at zero.

[LAMMPS compute heat/flux](https://docs.lammps.org/compute_heat_flux.html)
returns a quantity that has **not** been divided by volume. In `metal` units
it is directly usable as the extensive current in eV*angstrom/ps; in `real`
units (kcal/mol*angstrom/fs) multiply by 43.3641 (0.0433641 eV per kcal/mol
times 1000 fs/ps). The LAMMPS pressure tensor is compressive-positive and in
bar: negate it and multiply by `1e-4` to obtain tensile-positive GPa stress. Its microscopic
stress and current definitions require special care for many-body potentials.
The toolkit requires the caller to establish that the supplied current is
physically valid for the MLIP and engine implementation. Ordinary energy and
velocity output is insufficient to reconstruct it.

As records (see {doc}`records`), a transport result always binds its running
integral, as `thermal_conductivity_running_integral` (one 3×3 tensor per lag)
or `shear_viscosity_running_integral` (xy, xz, yz per lag), with temperature and
volume; the plateau tensor and isotropic coefficient are recorded only for an
explicit `lag_index=`. Replica means and standard errors at a `lag_index=` are
statistic records (`MEAN`, `STANDARD_ERROR`) of their base properties.

No automatic plateau is selected. Compare running integrals, lag truncation,
sampling interval, trajectory duration, system size and independent replicas.
`replica_transport` returns means and standard errors for matching protocols.
Explicit block analysis uses the same API:

```python
import numpy as np
from httk.analyse.matsci.transport import thermal_conductivity, replica_transport

current = np.random.default_rng(71).normal(size=(400, 3))
blocks = [thermal_conductivity(block, .001, temperature=300, volume=1000,
                              max_lag=20)
          for block in np.split(current, 4)]
summary = replica_transport(blocks)
assert summary.replicas == 4
```

This example checks the API; random currents are not a materials prediction.
Blocks must be long enough to support the desired correlation time and
sufficiently independent for the reported standard error to be meaningful.

# Dynamics and diffusion

`httk.analyse.matsci.dynamics` uses angstrom, ps, and persistent atom order.
Displacement routines require unwrapped positions. The caller chooses the
laboratory/material frame; a changing cell needs an explicit frame convention.
The file adapters currently require fixed cells and uniformly increasing times.

`mean_squared_displacement` averages displacement outer products over every
origin and atom. It returns the full symmetric tensor, its trace and time-origin
counts. Optional COM removal requires explicit masses and subtracts each frame's
mass-weighted center. `diffusion_from_msd` fits each tensor component to
`MSD_ij = 2 D_ij t + intercept` on an explicit inclusive lag-index window.
The fitted tensor and its scalar estimate (one third of the trace) are in m²/s,
the unit of the `diffusion_tensor` definition; intercepts and residuals stay in
angstrom², the MSD unit. Select a
physically diffusive window and compare neighboring windows; a linear regression
cannot establish that the motion is diffusive. Negative noisy fits are retained.

```python
import numpy as np
from httk.analyse.matsci.dynamics import mean_squared_displacement

# A simple ballistic path; this is deliberately not interpreted as diffusion.
v = np.array([[1., 0., 0.], [-1., 0., 0.]])
positions = np.arange(10)[:, None, None] * .1 * v
msd = mean_squared_displacement(positions, .1, max_lag=4)
assert abs(msd.trace[4] - .16) < 1e-12
```

`velocity_autocorrelation` returns dimensionful `C_ij=mean[v_i(t)v_j(t+lag)]`,
averaged over atoms and all origins, with optional per-atom/component temporal
mean removal (off by default; see below). The lagged matrix can be nonsymmetric. `integrate_vacf` gives a
running trapezoid integral in angstrom²/ps; it does not select a plateau. These
pair-count correlations are not themselves positive spectral-density estimates.

As records (see {doc}`records`), a `TensorSeries` binds by `kind`: an MSD to
`mean_squared_displacement` and a VACF to `velocity_autocorrelation`, both with
lag times and origin counts, and a VACF integral to `diffusion_running_integral`
with its tensors converted to m²/s.

## Distributions and scattering

`van_hove_self` gives a spherical-shell density of self displacement probability.
The integral over the reported range may be below one; out-of-range samples
remain in the denominator. `van_hove_distinct` counts atom i at the origin
against atom j at the lag, excluding i=j. It returns a neighbor number density,
whose full spatial integral is N−1. Its minimum-image radial range is limited
to strictly below half the shortest periodic translation of a fixed bulk cell.

`intermediate_scattering` requires explicit Cartesian wavevectors in inverse
angstrom. The self correlation averages `exp(+i q·displacement)`. The coherent
correlation is `mean[conj(rho(t))*rho(t+lag)]/N`, where rho sums atom phases.
Both retain complex phase information; at q=0 they equal one and N respectively.
Wrapped and unwrapped phases agree only at wavevectors commensurate with the
fixed periodic cell. No powder/orientational average is inferred.

`velocity_spectrum` is a one-sided velocity periodogram in
(angstrom/ps)² per THz. Choose a rectangular or Hann window and whether to remove
the temporal mean (`remove_mean`, default `False`). Summing the spectral bins times frequency spacing reproduces
the window-weighted mean-square velocity. This spectrum is not automatically a
normalized phonon DOS, and masses/species contributions are not inferred.

`RadialDynamics` (self or distinct van Hove), `ScatteringSeries` and
`VelocitySpectrum` bind to the `self_van_hove_function` /
`distinct_van_hove_function`, `self_intermediate_scattering_function` /
`intermediate_scattering_function` and `velocity_power_spectrum` definitions
through `records()`; the complex scattering values are stored as separate
`real` and `imaginary` lists.

Per-atom temporal mean removal, in `velocity_spectrum` and
`velocity_autocorrelation`, also removes each atom's net displacement over the
trajectory divided by its duration, which is the diffusive signal. It biases the
integrated-VACF estimate of the diffusion coefficient low by about the plateau
time over the trajectory length, drives the full-length integral to zero, and
with the rectangular window zeroes the zero-frequency bin that is proportional
to the diffusion coefficient. Both functions therefore default to
`remove_mean=False`; use `True` only for non-diffusive (solid) systems.

## From trajectories

`httk.analyse.integrations.trajectory` supplies `rdf_from_trajectory`,
`msd_from_trajectory` and `vacf_from_trajectory`. RDF streams structures and cells
through one traversal. Dynamic adapters read canonical `time`, `atom_ids` and
`unwrapped_positions` or `velocities` through synchronized `samples`; they reject
changed IDs, changed cells, missing required observables, and irregular times.
They explicitly approximate exact source values for the numerical calculation.

Dynamic kernels store O(T*N) selected data and use O(T*N*max_lag) work; coherent
scattering also stores O(T*N*Q) phases. Select the source segment and a manageable
frame/atom selection before use. The RDF implementation streams frames but uses
pairwise neighbor work per frame. No routine silently reconstructs winding
numbers from a sparse wrapped trajectory.

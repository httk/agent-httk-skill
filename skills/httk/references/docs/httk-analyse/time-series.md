# Simulation time series

{py:func}`httk.analyse.generic.timeseries.block_average` and
{py:func}`httk.analyse.generic.timeseries.autocorrelation` consume finite real
scalar sequences. They explicitly compute approximate float64 statistics and
return immutable values. Select an equilibrated, regularly sampled stationary
segment before calling them. They do not infer equilibration or combine runs.

## Block averages

```python
from httk.analyse.generic import block_average

summary = block_average([1, 3, 5, 7, 9, 11], block_size=2)
assert summary.block_means == (2.0, 6.0, 10.0)
assert summary.mean == 6.0
print(summary.standard_error)
```

For $M$ complete non-overlapping blocks with means $b_j$, the returned
`standard_deviation` is the sample standard deviation of the **block means**
(denominator $M-1$), and `standard_error` is this value divided by $\sqrt M$.
All three statistics have the units of the input observable.

At least two complete blocks are required. An incomplete final block raises
by default. Pass `remainder="drop"` to explicitly omit it; `used_samples` and
`dropped_samples` report what happened. The mean then describes retained
samples only. The input arrays are never modified.

The standard error assumes independent block means. Choose blocks longer than
the relevant correlation time and compare several block sizes while retaining
enough blocks. Two blocks satisfy the arithmetic requirement but provide little
evidence for a reliable uncertainty estimate. The routine does not certify a
plateau or independence. The executed {doc}`notebooks/materials-toolbox`
demonstrates block-size sensitivity on a seeded correlated series. For the
statistical motivation, see [Flyvbjerg and Petersen (1989)](https://doi.org/10.1063/1.457480).

## Autocorrelation

```python
from httk.analyse.generic import autocorrelation

correlation = autocorrelation([1, -1, 1, -1], max_lag=2)
assert correlation == (1.0, -1.0, 1.0)
```

The series is centered using its whole-series mean. For $N$ samples, lag $k$
uses the $N-k$ available pairs:

$$C_k=\frac{1}{N-k}\sum_{i=0}^{N-k-1}(x_i-\bar x)(x_{i+k}-\bar x),
\qquad \rho_k=C_k/C_0.$$

The result contains lags zero through `max_lag`, inclusive; the default reaches
$N-1$. Lag zero is exactly one. Constant input has undefined normalized
autocorrelation and raises `ValueError`. Lag indices correspond to time only
after multiplication by the known regular sampling interval.

This pair-count normalization can produce values outside [-1, 1] at long lags
and does not guarantee a positive-semidefinite covariance sequence. It must
not be treated as a spectral density or an implicit Green–Kubo integration
kernel. Transport analysis needs dimensionful correlations and explicit
window/normalization conventions. FFT evaluation uses zero padding to avoid
circular wraparound and scales centered data before forming products.

## Simulation output boundary

Prepare scalar inputs with explicit source units and sample selection. LAMMPS
`metal` and `real` styles use different energy, time and pressure units, and
thermodynamic normalization can change by command and column. Consult
[LAMMPS units](https://docs.lammps.org/units.html) and
[thermo_modify](https://docs.lammps.org/thermo_modify.html). These routines do
not parse LAMMPS output, align dump/log segments, unwrap coordinates, compute
diffusion, or assess MLIP quality; those capabilities require additional input
contracts and estimators.

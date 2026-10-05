# Harmonic phonon thermodynamics

`httk.analyse.matsci.phonons.harmonic_thermodynamics` evaluates the harmonic
oscillator free energy, internal energy, entropy and constant-volume heat
capacity from signed frequencies in THz. Energies use eV and entropies and heat
capacities use eV/K. Results are extensive in the supplied mode weights; the
routine does not infer a `3N` normalization or normalize weights.

```python
from httk.analyse.matsci.phonons import harmonic_thermodynamics

properties = harmonic_thermodynamics(
    [1.0, 2.0, 3.0], [0.0, 100.0, 300.0],
    weights=[1.0, 1.0, 1.0],
)
print(properties.free_energy, properties.heat_capacity)
```

At zero kelvin, `free_energy` and `internal_energy` equal the zero-point energy;
entropy and heat capacity are exactly zero. Frequencies at zero and below zero
raise by default. `zero_modes="omit"` and `imaginary="omit"` explicitly remove
those modes, with their summed weights reported in the result. Imaginary modes
are never converted to absolute frequencies. Weights may be zero, but must be
nonnegative with positive total. Input arrays are copied and left unchanged.

## Zero modes and the cutoff frequency

A mode counts as a zero mode only when its frequency is exactly `0.0`, but real
Γ-point acoustic modes come out of a calculation as numerical noise of roughly
±1e-6 to ±1e-3 THz. Negative noise raises by default, and positive noise is kept
and adds a log-divergent `kT ln(x)` term. On a 4×4×4 mesh (Γ weight 1/64) with
three acoustic modes at 1e-6 THz and 300 K, keeping them changes the free energy
by about −19.0 meV per cell and the entropy by about +0.78 kB per cell relative
to omitting them; at 1e-2 THz the free-energy error is still about −7.8 meV.

Pass `cutoff_frequency` (THz, default `0.0`) to classify such modes as zero
modes, as Phonopy's `cutoff_frequency` option does. Modes with
`|frequency| < cutoff_frequency` are zero modes whatever their sign; remaining
negative modes are imaginary, and the rest are retained. The default `0.0`
reproduces the exact-zero behaviour. Zero-classified weight is reported in
`excluded_zero_weight` under the `zero_modes` policy, so use
`zero_modes="omit"` with a cutoff. The cutoff is validated (finite, nonnegative)
and recorded as `cutoff_frequency` on the result. It is accepted by
`harmonic_thermodynamics`, `harmonic_thermodynamics_from_dos`, `quasiharmonic`
and `harmonic_from_phonopy`. Choose it well below the lowest physical frequency,
for example 1e-3 to 1e-2 THz, and use it whenever Γ acoustic modes are
included.

```python
from httk.analyse.matsci.phonons import harmonic_thermodynamics

noisy = harmonic_thermodynamics(
    [1e-6, -1e-6, 1e-6, 1.0, 2.0, 3.5], [300.0],
    weights=[1 / 64] * 3 + [0.25, 0.5, 0.25],
    zero_modes="omit", cutoff_frequency=1e-3,
)
print(noisy.excluded_zero_weight, noisy.cutoff_frequency)
```

`harmonic_thermodynamics_from_dos` accepts density in states/THz and uses
trapezoid node weights, including half weights at grid endpoints. The reported
retained weight is the integrated number of states. A zero-frequency endpoint
has quadrature weight and therefore follows the same explicit zero-mode policy.

## Volume response

`mode_gruneisen` fits log frequency against log volume for modes already
matched by the caller. It uses a local quadratic with at least three volumes
and a linear fit with two. Its derivative is
`-d(log(frequency))/d(log(volume))`; no branch matching is inferred.

`quasiharmonic` combines static energies and harmonic free energies at every
sampled volume, then fits the existing Birch–Murnaghan model independently at
each temperature. Provide at least five distinct volumes that bracket a stable
minimum, a common frequency column layout, and at least three strictly
increasing temperatures. The frequencies and static energies must use the same
cell or per-atom normalization. If a mode is omitted at one volume, the same
matched modes must be omitted at every volume. `bulk_moduli` are in GPa. `volumetric_expansion` is
`(1/V) dV/dT` from `numpy.gradient` on the nonuniform temperature grid, with
the library's second-order endpoint convention. A `cutoff_frequency` applies the
same classification at every volume, so Γ noise that changes sign between volumes
no longer makes the exclusions differ.

Some caveats on the temperature response. `volumetric_expansion` at 0 K is not
forced to zero: the second-order `numpy.gradient` endpoints can leave a small
nonzero value (a test model gave alpha_V(0 K) of about −1.3e-6 per K). Coarse
temperature grids also bias alpha_V, because the derivative is a finite
difference of the equilibrium volume (100 K spacing gave −13% at 100 K in the
same model). Use a dense grid, about 10 K spacing or finer, and treat endpoint
values with care. `quasiharmonic` minimises `F(V, T) = E_static + F_harmonic`,
which equals the Gibbs energy only at zero pressure; there is no pressure
argument.

As records (see {doc}`records`), a harmonic result binds its zero-point energy
and one `vibrational_thermodynamics` series (temperatures, Helmholtz free,
internal energies, entropies and heat capacities). A quasi-harmonic result binds
one `quasiharmonic_thermodynamics` series whose
`total_helmholtz_free_energies` are the minimized `free_energies`, static energy
included, with `equilibrium_volumes`, `bulk_moduli` and
`volumetric_thermal_expansions`.

## Phonopy mesh

`httk.analyse.integrations.phonopy.harmonic_from_phonopy` consumes an already sampled public Phonopy mesh result.
It normalizes q-point multiplicities to sum to one and preserves each branch,
so the result is per primitive-cell mode set. It does not create displacements,
force constants, or a mesh. Phonopy's default frequency unit is THz; if the
object was configured with another frequency conversion factor, convert its
frequencies before calling the adapter.

These are harmonic and quasi-harmonic approximations. The quasi-harmonic fit
does not account for explicit anharmonicity or validate the volume dependence
of the force constants. Mesh convergence, phase stability and mode matching
remain scientific checks for the caller.

The equations and mesh normalization follow the
[Phonopy formulation](https://phonopy.github.io/phonopy/formulation.html) and
[public Python mesh/thermal API](https://phonopy.github.io/phonopy/phonopy-module.html).
The oscillator constants here use exact SI h, kB and e. Phonopy versions using
older constants can differ by a few parts per million, amplified at low
occupation. Install `httk-analyse[phonopy]` when constructing Phonopy objects;
the numerical kernels themselves require only NumPy.

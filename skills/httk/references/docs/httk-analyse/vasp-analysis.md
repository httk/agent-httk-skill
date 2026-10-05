# VASP electronic analysis adapters

`httk.analyse.integrations.vasp.dos_from_vasp` presents an exact DOSCAR result
as immutable float tuples for numerical analysis. `spin="total"` keeps a
nonmagnetic DOS unchanged and sums the two channels for a collinear DOS;
`spin="up"` and `spin="down"` select a collinear channel. The result records
the selected channel and whether its spin basis is spin-summed or resolved.
No degeneracy factor is applied to DOSCAR's nonmagnetic total. As records (see
{doc}`records`), a spin-summed result binds to `electronic_density_of_states`
(`energies`, `density`, `integrated_density`) and `fermi_energy`; a
collinear `up` or `down` channel binds to
`spin_channel_electronic_density_of_states` (`spin`, `energies`, `density`,
`integrated_density`, per cell and per eV in that channel) and `fermi_energy`.

`band_edges_from_wavefunctions(wavefunctions, spin, occupation_tolerance=..., energy_reference=...)`
selects one zero-based spin channel from an existing `PlaneWaveFunctions`
object. WAVECAR stores eigenvalues and occupations with axes
`(spin, k point, band)`; the adapter supplies `(band, k point)` arrays to
`matsci.electronic.band_edges`. WAVECAR occupations are per state on a 0..1
scale for every spin channel (OUTCAR prints occupations on a 0..2 scale for
ISPIN=1; EIGENVAL and vasprun.xml use the same 0..1 per-state scale), so the maximum occupation is fixed at one and
`occupation_tolerance` is on that scale. Occupation tolerance and energy
reference are required explicitly. Only the selected channel is analysed: for
ISPIN=2 the material gap is the minimum CBM over both channels minus the
maximum VBM over both channels. For metals the returned VBM and CBM are
tolerance artifacts; `metallic` is the meaningful flag. The result describes
sampled k points; it does not infer a Fermi reference or inspect WAVECAR
coefficients for weights.

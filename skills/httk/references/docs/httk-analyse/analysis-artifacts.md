# Summaries and figures

`httk.analyse.summary.analysis_summary` serializes a numerical result alongside
its algorithm identifier, installed software versions, field meanings,
parameters, sample selection and scientific assumptions. Each source file is read in chunks
to record its locator, byte size and SHA-256 digest. Source frames are not
embedded. Keep source files unchanged from calculation through hashing; a hash
of a later modified file would not describe the calculation's input.

The returned `AnalysisSummary` stores canonical JSON, and `.value` returns a
fresh decoded copy. `.write(path)` writes a selected output file. Standard
frozen result dataclasses are supported; complex numbers have named `real` and
`imaginary` fields. Nonfinite values and unsupported objects raise instead of
being silently converted to strings. Installed versions identify distributions;
record an unreleased source commit in `parameters` when analyzing a development
checkout.

The envelope's `fields` object says what each result field means. For a result
type bound to property definitions (see {doc}`records`), every bound field maps
to `{"definition": <property IRI>, "derivation": <derivation IRI or null>,
"content_id": <id of the record>, "value": <bound value>}`, built from the
records `records()` emits (a value failing its definition raises);
`content_id` links the envelope to the stored record. Pass `product_of=` the same
provenance edges you store the records with: ids depend on them, and the
envelope keeps only the ids, not the edges (so a summary written before its
source files are stored cannot carry the final ids). `field_values=False` omits
`value` from each entry for long series (the `result` dump and ids remain);
selection keywords such as `lag_index=` are passed through. The keys are
binding names, not paths into `result`: `isotropic[4]` or
`standard_errors.heat_capacity_constant_pressure` name a derived or selected
value, and a series is keyed by its definition name (such as
`vibrational_thermodynamics`) with a dictionary of member lists as its value,
so each entry carries its own value. A value with a derivation is the
statistic `records()` stores as a `DerivedDataRecord`. Fields without a
published definition (van Hove, scattering or velocity-spectrum series, bond
order, fit diagnostics) may get
an OPTIMADE unit expression through `units=`, validated against the vendored
OPTIMADE unit definitions and stored as `{"unit": ..., "unit_definitions":
[<unit IRIs>]}`. `dimensionless` is accepted; malformed expressions (such as
`eV/angstrom`; write `angstrom^-1*eV`) and units for fields that have a
definition raise `ValueError`.

```python
from httk.analyse.matsci.phonons import harmonic_thermodynamics
from httk.analyse.summary import analysis_summary

result = harmonic_thermodynamics([2, 3, 4], [0, 300])
summary = analysis_summary(
    result, algorithm="httk.analyse.matsci.phonons.harmonic_thermodynamics",
    units={"cutoff_frequency": "THz"},
    parameters={"frequencies_THz": [2, 3, 4]}, selection={"modes": "all"},
    sources=[], assumptions=["synthetic three-mode example"],
)
assert summary.value["result"]["retained_mode_weight"] == 3
series = summary.value["fields"]["vibrational_thermodynamics"]["value"]
assert series["helmholtz_free_energies"] == list(result.free_energy)
```

## Plotting

`httk.analyse.plotting` returns Matplotlib figures and axes. It never opens a
window or saves a file implicitly; callers own figure closure and choose output
paths. Helpers include `plot_eos` (data, fit and residuals),
`plot_convergence`, `plot_rdf`, `plot_msd`, `plot_transport`, `plot_phonons`
and `plot_parity`. Axes of quantities with a property definition are labelled
with the definition's title and unit, for example `Bulk modulus (GPa)`;
`plot_parity` uses the result's `definition` and omits the unit when it is
`None`. Plotting a running transport integral does not select a plateau.

`plot_chemical_potential_slice` takes a host/competitor region, two plotted
elements, one dependent element eliminated by the host equality, and fixed
potentials for every remaining element. Both plot ranges are explicit.
Feasibility shading is sampled on a declared grid; use the original region's
`contains` method for numerical membership, not pixels near a drawn boundary.

The executable materials-response notebook illustrates these routines. The
analysis recipes show file-backed summaries and storage with provenance.

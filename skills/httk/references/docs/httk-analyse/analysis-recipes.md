# Analysis recipes

These commands write canonical JSON summaries with algorithm and software versions,
field bindings to property definitions (or OPTIMADE unit expressions for fields
without one), parameters, sample selection, assumptions, and SHA-256 hashes of
the source files. The JSON contains numerical results and metadata; trajectory
frames stay in their source files. Run the commands in an environment with
*httk-analyse* and its relevant optional dependencies installed. Install
`httk-analyse[scipy]` for the nonlinear EOS options and
`httk-analyse[phonopy]` for the separate phonon adapter. The SQLite recipe
requires `httk-store[db]`. The benchmark's dump/log join lives in
`httk-workflow-lammps` (`httk.codes.lammps.lammps_samples`), which must be installed.

## Static volume scan

Use a CSV with `volume_angstrom3,energy_eV` columns. All rows must describe the
same composition, electronic state, relaxation protocol and total-energy basis.
The default NumPy fit is algebraic Birch–Murnaghan third order (BM3):

```sh
python examples/volume_scan.py scan.csv scan.json
```

Pass `--model birch-murnaghan`, `murnaghan`, or `vinet` for the corresponding
SciPy nonlinear fit. These models share the same inputs but can yield different
minima and residuals. The fit routine rejects a minimum outside the sampled
range. Inspect the scan and fitted residuals before comparing properties.

For a batch, run one command per independent scan and keep one summary per scan:

```sh
for scan in scans/*.csv; do
    python examples/volume_scan.py "$scan" "${scan%.csv}.json"
done
```

## LAMMPS trajectory

The native dump must include atom `id`, `type`, unwrapped `xu yu zu` for MSD,
and `vx vy vz` for VACF. A typical bulk command is:

```sh
python examples/md_properties.py atoms.dump md.json \
  --species 1:Ar --units metal --dimension 3 --segment 0 --timestep 0.001 \
  --cutoff 8 --bin-spacing 0.1 --max-lag 100 --msd --vacf
```

The timestep is per source step in the declared LAMMPS unit style (`metal` ps,
`real` fs); canonical lag times are ps. The segment, type mapping and timestep
must describe the actual run. RDF streams selected frames, using a periodic
three-dimensional bulk normalization. MSD and VACF load their selected vectors
in memory and require fixed cell, persistent atom order and regular physical
times. MSD requires known unwrapped coordinates; sparse wrapped coordinates
cannot establish a displacement. Choose a cutoff below half the shortest
periodic translation, and select a lag window appropriate to the observation
time. The command does not select a diffusion fit window or infer equilibrium.

An optional CSV with columns `time_ps,Jx_eV_angstrom_per_ps,`
`Jy_eV_angstrom_per_ps,Jz_eV_angstrom_per_ps` adds a running Green–Kubo thermal
conductivity:

```sh
python examples/md_properties.py atoms.dump md.json \
  --species 1:Ar --units metal --dimension 3 --segment 0 --timestep 0.001 \
  --cutoff 8 --bin-spacing 0.1 --max-lag 100 \
  --heat-current current.csv --temperature 300 --volume 64000
```

The current must be the **extensive total microscopic heat current** in
eV·angstrom/ps, with regular `time_ps`, a fixed volume in angstrom³ and an
equilibrium temperature in K. Heat current from a many-body model needs its own
validated physical definition; energy and velocity columns alone do not define
it. The output retains the running integral. It does not choose a plateau or
estimate finite-time uncertainty.

## MLIP property and conservation checks

`mlip_properties.py` takes separate reference and prediction EOS CSV files, each
with `volume_angstrom3,energy_eV,composition,protocol,energy_basis`, in *the
same row order and volume grid*. It requires the three metadata fields to be
nonempty and identical across every row of both curves. It fits
both curves and reports parity of equilibrium volume and bulk modulus. Supply
an NVE CSV with `time_ps,total_energy_eV`, a committee CSV with two or more
`prediction_1`, `prediction_2`, ... columns in eV, and a named independent
holdout group:

```sh
python examples/mlip_properties.py reference.csv prediction.csv nve.csv \
  committee.csv mlip.json --atom-count 64 --spring-constant 2 \
  --displacement 0.01 --holdout-group family-A
```

The force check uses a declared synthetic harmonic energy callback and its
analytical force at two displacement sizes. Replace that callback with the
model's energy and force calls when validating an actual MLIP. A harmonic pass
only checks the finite-difference workflow. NVE drift is total eV/atom/ps on
the selected time interval, and committee spread is uncalibrated disagreement.
Hold out whole trajectories or material families from training; adjacent frames
from one trajectory are correlated and should remain in the same group. Record
model version, electronic settings, atom matching, constraints and source-unit
conversions alongside external model results.

## SQLite provenance

The optional *httk-store* recipe stores a summary as a local
`_httk_analysis_summary` `DataRecord` definition plus `FileRecord` metadata for
the hashed sources. An analysis `Run` consumes the source file entries and
outputs the result record. The result's `product_of` links also identify its
source entries. The command closes the database, reopens it, queries records by
property name and verifies the summary and edges:

```sh
python examples/store_analysis.py scan.json analysis.sqlite \
  --source-id workspace:existing-job
```

`--source-id` records an existing workflow job identifier; it never launches a
simulation. `--upstream-run-id` can link an already stored run in the same
database. Entry edges use public IDs minted by that database, and the canonical
summary retains source checksums. Store revisions preserve the edge content.
When the summary's result is a bound result type, such as the EOS fit from
`volume_scan.py`, the recipe also rebuilds the result and stores
`httk.analyse.records.records(result)`: one `DataRecord` per property
(`equilibrium_volume`, `equilibrium_energy`, `bulk_modulus`,
`bulk_modulus_pressure_derivative`) in its definition's unit, and a
`DerivedDataRecord` for the fit RMSE (base property `total_energy`, `RMSE`
derivation), linked to the same sources and listed as run outputs. See
{doc}`records`. Results whose bindings need an explicit selection (replica
transport `lag_index`) are stored as the summary only. The SQLite file contains only numerical summary JSON, property records and
file metadata, never source trajectory frames. The ad hoc property definition is local to this
recipe and does not change global entry schemas.

## Scale benchmark

```sh
python benchmarks/run_materials_benchmarks.py --frames 100 --atoms 256 \
  --max-lag 25 --output benchmark.json
```

The benchmark generates a synthetic native dump and matching log, then times a
strict dump/log join, streaming RDF, selected MSD and VACF. It records input
sizes, Python, NumPy and *httk-analyse* versions, wall time and `tracemalloc`
peak Python allocations.
`tracemalloc` may omit native NumPy buffers and operating-system cache, so its
peak is not process RSS. The log parser retains its thermo table; RDF retains
bins and pair counts while its frame path streams. Dynamic adapters currently
hold O(frames × atoms) selected vectors and perform O(frames × max_lag × atoms)
pair work. RDF pair work is O(frames × atoms²) for this direct method. These
figures are measurements, not performance thresholds; rerun on the intended
system size and hardware.

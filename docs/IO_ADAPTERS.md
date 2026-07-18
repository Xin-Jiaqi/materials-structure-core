# Structure I/O adapter contracts

## Design boundary

`materials-structure-core` owns the normalized in-memory contract and loss policy. It does not maintain another crystallographic text parser. The `io` extra delegates POSCAR/CONTCAR and CIF syntax to ASE, then validates the result as a `StructureRecord`.

The public adapter surface is:

- `read_structure(...) -> StructureReadResult`;
- `write_structure(...) -> Path`;
- `from_ase_atoms(...)` and `to_ase_atoms(...)`;
- `structure-core inspect` and `structure-core convert`.

Every read result records the source SHA-256, normalized format name, and backend version. These fields are sufficient to construct a `ProvenanceManifest`; they do not automatically sanitize a user-supplied source URI.

## Accepted in 0.0.2

- VASP 5-style POSCAR with explicit chemical symbols;
- Direct or Cartesian positions;
- positive, non-unit scale factors;
- negative target-volume scale factors;
- per-site Selective-dynamics flags, with `T = motion allowed`;
- all-periodic PBC;
- CIF without Selective-dynamics flags;
- write/read checks of lattice, Cartesian positions, species order, and supported flags.

## Explicit refusals and deferred cases

- A write fails if POSCAR/CIF would discard a non-periodic PBC flag.
- A CIF write fails if Selective-dynamics flags are present.
- An ASE object with an unsupported constraint fails conversion instead of losing that constraint.
- VASP 4 files without externally supplied, trustworthy species names are not part of the acceptance envelope.
- Velocity, lattice-velocity, and predictor-corrector blocks are not represented by `StructureRecord`; any non-empty POSCAR tail after the declared coordinate rows is rejected before conversion.
- Partial/mixed CIF occupancy and non-zero site charge data are rejected rather than promoted to the full-occupancy model.
- CIF symmetry operators, asymmetric-unit labels, oxidation annotations and presentation metadata are not preserved; this adapter represents only the expanded, full-occupancy periodic structure.
- VASP 4 species recovery and broader CIF symmetry cases still need committed golden fixtures before v0.1.

## Coordinate and constraint mapping

ASE exposes scaled positions and a row-vector cell, which matches the package contract `cartesian = fractional @ lattice`. ASE `FixScaled.mask=True` means fixed; the core model stores the inverse semantic, `selective_dynamics=True` means motion allowed. This inversion is tested for free, mixed, and fully fixed sites.

## Primary interface references

- [VASP POSCAR format specification](https://vasp.at/wiki/POSCAR)
- [ASE POSCAR/CONTCAR reader and writer](https://wiki.fysik.dtu.dk/ase/ase/io/formatoptions.html#vasp)
- [ASE constraint semantics](https://wiki.fysik.dtu.dk/ase/ase/constraints.html)
- [pymatgen `Poscar` API, used as an interoperability reference](https://pymatgen.org/pymatgen.io.vasp.html#pymatgen.io.vasp.inputs.Poscar)
- [pymatgen structure-format usage examples](https://pymatgen.org/usage.html#reading-and-writing-structures-molecules)

The references define upstream capabilities; this package only claims behavior covered by its own fixtures and tests.

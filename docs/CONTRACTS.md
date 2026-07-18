# Scientific contracts

## Coordinate convention

- Lattice vectors are stored as rows.
- Lengths are Angstrom in schema v0.0; other units are rejected rather than inferred.
- Fractional coordinates are dimensionless.
- Cartesian coordinates use the same length unit as the lattice.
- Conversion is `cartesian = fractional @ lattice`.
- Periodic wrapping uses strict modulo only on axes whose `pbc` flag is true.

## `StructureRecord`

Required invariants:

- finite, non-singular `3×3` lattice;
- one non-empty species label and one fractional coordinate per site;
- optional Selective-dynamics flag triplets remain aligned with site order;
- `True` in a Selective-dynamics triplet means that movement is allowed along that POSCAR lattice-coordinate direction; text adapters must parse `T/F` explicitly and never use string truthiness;
- exactly three explicit PBC flags.

The initial ordered hash is a deterministic content identifier using Angstrom, periodic wrapping, decimal rounding to 12 places, and a versioned payload that records this quantization. It intentionally does not claim permutation, translation, basis, or crystallographic symmetry equivalence. A future `canonical_structure_hash`, if added, must define sorting, basis/origin, wrapping, tolerance, and equivalence contracts with reference tests; the current hash must not be used for non-equivalent-configuration deduplication.

Public provenance export must remove credentials, usernames, private absolute paths, restricted database URIs, and unpublished material identifiers. A manifest binds its source checksum to a required result structure ID and hash schema.

## Future adapter acceptance

A POSCAR or CIF adapter is accepted only when read/write/read round trips preserve, within a documented tolerance:

- lattice and Cartesian site positions;
- composition, site order or an explicit old/new index map;
- Selective-dynamics and other supported site properties;
- POSCAR positive/negative/non-unit scale semantics;
- provenance and original-file SHA-256.

Unknown or unsupported fields must produce a warning/error record; they must not be silently discarded in a production path. The v0 adapter rejects optional POSCAR velocity, lattice-velocity and predictor-corrector tails, partial/mixed CIF occupancy, and non-zero site charge data because the normalized model cannot preserve them.

The `0.0.2` adapters implement this as a strict error for unsupported ASE constraints, POSCAR tail blocks, partial/mixed CIF occupancy, non-zero site charges, CIF Selective dynamics, and non-periodic PBC writes. See `IO_ADAPTERS.md` for the tested acceptance envelope; deferred cases remain explicit release blockers.

# Roadmap

## v0.0 — contract bootstrap

- [x] Validated structure record.
- [x] Explicit fractional/Cartesian conversion.
- [x] PBC-aware wrapping.
- [x] Angstrom-only, fixed-quantization, order-sensitive deterministic content hash.
- [x] Output-bound, JSON-safe immutable provenance manifest and file checksum helper.
- [ ] Independent API and numerical review.

## v0.0.2 — maintained-backend I/O candidate

- [x] Add an optional ASE bridge rather than a handwritten parser.
- [x] Add source checksum/backend metadata to read results.
- [x] Cover positive scale, Direct/Cartesian, Selective dynamics, POSCAR and CIF round trips.
- [x] Refuse known lossy writes and unsupported constraints.
- [x] Add `inspect` and `convert` CLI commands.
- [x] Add a negative target-volume golden fixture and malformed-input rejection tests.
- [ ] Add a safe VASP 4 species-resolution policy before promoting the adapter to stable.

## v0.1 — reliable structure I/O

- [ ] Add the documented synthetic fixture matrix and golden manifests.
- [x] Adopt a maintained parser backend rather than another handwritten POSCAR/CIF parser.
- [ ] Support POSCAR scale, Direct/Cartesian, VASP 4/5, species order, Selective dynamics, and round trips.
- [ ] Add an optional CIF adapter and ASE/pymatgen bridges.
- [ ] Add minimum-image distance, collisions, vacuum, layer thickness, and layer-spacing reports.
- [ ] Publish a versioned JSON schema and compatibility policy.

## First consumers

1. Migrate `batch-symmetry-checker` file parsing and provenance.
2. Replace the duplicated structure logic in `extension-to-BSF` after golden tests exist.
3. Use the same contracts in the Python 3 `heterojunction` redesign.

## Release gate

The repository is licensed under BSD-3-Clause and its current fixtures are synthetic. A v0.1 release additionally requires Python 3.10–3.12 CI, complete format round trips, and independent verification of the numerical conventions.

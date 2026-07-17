# Roadmap

## v0.0 — contract bootstrap

- [x] Validated structure record.
- [x] Explicit fractional/Cartesian conversion.
- [x] PBC-aware wrapping.
- [x] Angstrom-only, fixed-quantization, order-sensitive deterministic content hash.
- [x] Output-bound, JSON-safe immutable provenance manifest and file checksum helper.
- [ ] Independent API and numerical review.

## v0.1 — reliable structure I/O

- [ ] Add the documented synthetic fixture matrix and golden manifests.
- [ ] Adopt a maintained parser backend rather than another handwritten POSCAR/CIF parser.
- [ ] Support POSCAR scale, Direct/Cartesian, VASP 4/5, species order, Selective dynamics, and round trips.
- [ ] Add an optional CIF adapter and ASE/pymatgen bridges.
- [ ] Add minimum-image distance, collisions, vacuum, layer thickness, and layer-spacing reports.
- [ ] Publish a versioned JSON schema and compatibility policy.

## First consumers

1. Migrate `batch-symmetry-checker` file parsing and provenance.
2. Replace the duplicated structure logic in `extension-to-BSF` after golden tests exist.
3. Use the same contracts in the Python 3 `heterojunction` redesign.

## Release gate

No v0.1 release until code/data ownership is confirmed, a license decision is recorded, Python 3.10–3.12 CI passes, all format fixtures round-trip, and an independent reviewer verifies numerical conventions.

# Regression fixture plan

Fixtures must be synthetic, self-authored, or clearly redistributable. Each fixture requires an ID, generation/source record, license status, SHA-256, expected invariants, and intentional failure behavior.

## Format and coordinate matrix

- VASP 4 and VASP 5 style inputs;
- Direct and Cartesian equivalent pairs;
- scale `1.0`, non-unit positive scale, and negative target-volume scale;
- Selective dynamics and optional trailing velocity data;
- species grouped in POSCAR fixtures, plus deliberately ungrouped in-memory/CIF inputs to test explicit reorder maps;
- boundary coordinates at, below, and above `0/1`;
- triclinic cells and 60°/120° hexagonal settings;
- same formula with distinct structures to prevent filename collisions;
- malformed count, singular lattice, non-finite coordinate, and truncated input cases.

Implemented in `tests/fixtures/manifest.json` for the `0.0.2` integration candidate:

- [x] VASP 5 Direct with positive non-unit scale and a triclinic cell;
- [x] VASP 5 Cartesian with positive non-unit scale;
- [x] negative target-volume scale;
- [x] mixed and fully fixed Selective-dynamics flags;
- [x] POSCAR Direct/Cartesian write-read paths;
- [x] a programmatically generated unconstrained CIF round trip;
- [ ] VASP 4 with caller-supplied species names;
- [x] malformed/truncated POSCAR rejection cases;
- [ ] velocities/predictor-corrector preservation policy;
- [ ] warning-capture expectations for upstream parser diagnostics.

## Dimensional matrix

- synthetic cubic, bcc, fcc, tetragonal, orthorhombic, monoclinic, triclinic, trigonal, and hexagonal bulk prototypes;
- monolayers with different vacuum directions and whole-layer translations;
- AA/AB/slid/flipped homobilayers and one synthetic heterobilayer;
- ABA/ABC-style synthetic trilayers;
- a long-axis bulk counterexample that must not be classified as 2D;
- a layer crossing a periodic boundary.

External database structures are not committed unless redistribution rights are verified. Prefer a retrieval script plus identifier, version, license, retrieval date, and checksum.

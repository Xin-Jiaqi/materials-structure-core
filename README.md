# materials-structure-core

[![tests](https://github.com/Xin-Jiaqi/materials-structure-core/actions/workflows/tests.yml/badge.svg)](https://github.com/Xin-Jiaqi/materials-structure-core/actions/workflows/tests.yml)

Contract-first foundations for reproducible crystal-structure software.

This pre-release defines a validated `StructureRecord`, explicit fractional/Cartesian conversion, periodic wrapping, an order-sensitive structure hash, and a serializable provenance manifest. Version `0.0.2` adds an opt-in ASE-backed POSCAR/CIF bridge with synthetic golden fixtures and explicit loss checks. It is a tested integration candidate, not yet a production converter.

## Why this repository exists

Several research workflows currently maintain separate structure readers and coordinate transforms. That duplication has already produced scale-factor, Direct/Cartesian, species-order, wrapping, and provenance risks. This package will become their common structure contract while keeping symmetry inference and application workflows in separate repositories.

## Current API

```python
from materials_structure_core import StructureRecord

structure = StructureRecord.from_fractional(
    lattice=[[3.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 20.0]],
    species=["B", "N"],
    fractional_coordinates=[[0.0, 0.0, 0.5], [1 / 3, 2 / 3, 0.5]],
    pbc=[True, True, False],
)

cartesian = structure.cartesian_coordinates()
wrapped = structure.wrapped()
structure_id = structure.ordered_hash()
```

Coordinate convention: lattice vectors are rows and `cartesian = fractional @ lattice`. `ordered_hash()` is a content-oriented identifier that preserves site order; it is **not** a canonical, symmetry-equivalence, permutation-invariant, or translation-invariant hash.

## Implemented now

- a validated immutable fractional-coordinate structure record;
- Angstrom-only v0.0 units and explicit row-lattice coordinate conversion;
- PBC-aware wrapping and an order-sensitive, fixed-quantization content hash;
- an output-bound provenance manifest and SHA-256 helper;
- regression tests for numerical and immutability contracts.
- ASE-backed POSCAR/CIF read/write adapters, provenance-friendly read results, and a small CLI;
- direct/Cartesian, positive-scale, Selective-dynamics, POSCAR round-trip, and CIF round-trip fixtures;
- refusal to silently discard unsupported ASE constraints, non-periodic PBC flags, or CIF Selective-dynamics flags.

## Optional structure I/O

```bash
python -m pip install -e '.[io]'
structure-core inspect POSCAR
structure-core convert POSCAR structure.cif
```

The bridge intentionally delegates parsing to the maintained [ASE format implementation](https://wiki.fysik.dtu.dk/ase/ase/io/formatoptions.html#vasp). The current acceptance envelope and known gaps are documented in [I/O adapter contracts](docs/IO_ADAPTERS.md). Positive and negative scale semantics are fixture-tested. VASP 4 files without trustworthy species names and velocity/predictor-corrector blocks remain release blockers rather than silently accepted claims.

## Planned ownership

Owned here:

- POSCAR/CIF adapters and their round-trip contracts;
- species/site-property synchronization;
- minimum-distance and collision checks;
- small synthetic/self-authored monolayer, bilayer, bulk, and malformed fixtures.

Not owned here:

- point/layer-group knowledge or symmetry inference;
- stacking or heterostructure candidate enumeration;
- VASP/Slurm orchestration and energy extraction;
- unpublished screening objectives or candidate materials.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
pytest
```

See [the scientific contracts](docs/CONTRACTS.md), [I/O adapter contracts](docs/IO_ADAPTERS.md), [fixture plan](docs/DATASET_PLAN.md), and [roadmap](ROADMAP.md).

For research use, cite the exact version using [`CITATION.cff`](CITATION.cff). A DOI or preferred paper citation will be added only when a corresponding release or publication exists.

## Status and rights

Status: `0.0.2` integration candidate / pre-alpha. Do not treat this version as a production POSCAR/CIF converter. No open-source license has been selected; public visibility does not grant reuse rights. Code, test data, documentation, and external examples require separate ownership/licensing review before v0.1.

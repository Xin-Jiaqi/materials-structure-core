"""Validated structure contracts for materials research software."""

from .model import ORDERED_HASH_SCHEMA, StructureRecord
from .io import (
    StructureIOError,
    StructureReadResult,
    from_ase_atoms,
    read_structure,
    to_ase_atoms,
    write_structure,
)
from .provenance import ProvenanceManifest, Transformation, sha256_file

__all__ = [
    "ProvenanceManifest",
    "ORDERED_HASH_SCHEMA",
    "StructureRecord",
    "StructureIOError",
    "StructureReadResult",
    "Transformation",
    "sha256_file",
    "from_ase_atoms",
    "read_structure",
    "to_ase_atoms",
    "write_structure",
]

__version__ = "0.0.2"

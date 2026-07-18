"""Maintained-backend structure I/O with explicit loss boundaries.

The core model deliberately does not implement crystallographic text parsers.
This module adapts ASE objects to :class:`StructureRecord` and keeps format
limitations visible to callers.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from io import StringIO
from numbers import Real
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import numpy as np

from .model import StructureRecord


class StructureIOError(ValueError):
    """Raised when an adapter cannot preserve the structure contract."""


@dataclass(frozen=True, slots=True)
class StructureReadResult:
    """A parsed structure plus the minimum source identity needed downstream."""

    structure: StructureRecord
    source_sha256: str
    format: str
    backend: str


def _ase() -> tuple[Any, Any, Any, Any]:
    try:
        from ase import Atoms
        from ase.constraints import FixAtoms, FixScaled
        from ase.io import read, write
    except ImportError as exc:  # pragma: no cover - exercised without the extra
        raise StructureIOError(
            "ASE is required for structure I/O; install materials-structure-core[io]"
        ) from exc
    return Atoms, FixAtoms, FixScaled, (read, write)


def _backend_version() -> str:
    try:
        return f"ase/{version('ase')}"
    except PackageNotFoundError:  # pragma: no cover - guarded by _ase
        return "ase/unknown"


def _format_name(path: Path, requested: str | None) -> str:
    if requested:
        name = requested.strip().lower()
    elif path.name.upper() in {"POSCAR", "CONTCAR"} or path.suffix.lower() in {
        ".vasp",
        ".poscar",
    }:
        name = "vasp"
    elif path.suffix.lower() == ".cif":
        name = "cif"
    else:
        raise StructureIOError(
            "cannot infer format; pass format='vasp' or format='cif' explicitly"
        )
    aliases = {"poscar": "vasp", "contcar": "vasp"}
    name = aliases.get(name, name)
    if name not in {"vasp", "cif"}:
        raise StructureIOError(f"unsupported format {name!r}; supported: vasp, cif")
    return name


def _assert_supported_vasp_payload(path: Path, text: str | None = None) -> None:
    """Reject POSCAR sections that the public model cannot round-trip."""

    if text is None:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise StructureIOError("POSCAR must be UTF-8 text") from exc
    lines = text.splitlines()
    if len(lines) < 8:
        return  # The maintained backend will provide the parse failure.
    # ASE accepts a ``!`` comment after the count list.  Mirror that lexical
    # rule here so a commented VASP 4 count line cannot bypass this guard.
    species_or_counts = lines[5].split("!", 1)[0].split()
    try:
        [int(token) for token in species_or_counts]
    except ValueError:
        counts_index = 6
    else:
        raise StructureIOError(
            "VASP 4 POSCAR without an explicit species line is unsupported"
        )
    try:
        counts = [int(token) for token in lines[counts_index].split("!", 1)[0].split()]
    except (IndexError, ValueError):
        return  # The maintained backend will provide the parse failure.
    if not counts or any(count < 0 for count in counts):
        return
    cursor = counts_index + 1
    if cursor < len(lines) and lines[cursor].strip().lower().startswith("s"):
        cursor += 1
    if cursor >= len(lines):
        return
    coordinate_mode = lines[cursor].strip().lower()
    if not coordinate_mode.startswith(("d", "c", "k")):
        return
    tail_start = cursor + 1 + sum(counts)
    if tail_start > len(lines):
        return
    if any(line.strip() for line in lines[tail_start:]):
        raise StructureIOError(
            "unsupported POSCAR data follows the coordinate block "
            "(velocities, lattice velocities and predictor-corrector data "
            "cannot be preserved)"
        )


def _assert_supported_ase_metadata(atoms: Any) -> None:
    occupancy = atoms.info.get("occupancy")
    if occupancy is not None:
        if not isinstance(occupancy, dict):
            raise StructureIOError("CIF occupancy metadata is malformed")
        for site in occupancy.values():
            if not isinstance(site, dict):
                raise StructureIOError("CIF occupancy metadata is malformed")
            if any(
                not isinstance(value, Real) or isinstance(value, (bool, np.bool_))
                for value in site.values()
            ):
                raise StructureIOError("CIF occupancy metadata is malformed")
            try:
                values = [float(value) for value in site.values()]
            except (TypeError, ValueError, OverflowError) as exc:
                raise StructureIOError("CIF occupancy metadata is malformed") from exc
            if (
                len(values) != 1
                or any(not np.isfinite(value) for value in values)
                or any(abs(value - 1.0) > 1.0e-12 for value in values)
            ):
                raise StructureIOError(
                    "partial or mixed CIF occupancy is unsupported; refusing "
                    "to convert it to a full-occupancy StructureRecord"
                )
    charges = np.asarray(atoms.get_initial_charges(), dtype=float)
    if charges.size and (
        np.any(~np.isfinite(charges)) or np.any(np.abs(charges) > 1.0e-12)
    ):
        raise StructureIOError(
            "non-finite or non-zero site charges/oxidation data cannot be preserved"
        )


def from_ase_atoms(atoms: Any) -> StructureRecord:
    """Convert one ASE ``Atoms`` object without silently dropping constraints."""

    _, FixAtoms, FixScaled, _ = _ase()
    _assert_supported_ase_metadata(atoms)
    species = tuple(atoms.get_chemical_symbols())
    allowed = np.ones((len(species), 3), dtype=bool)
    has_constraints = False
    for constraint in atoms.constraints:
        has_constraints = True
        indices = np.asarray(constraint.get_indices(), dtype=int)
        if isinstance(constraint, FixAtoms):
            allowed[indices, :] = False
        elif isinstance(constraint, FixScaled):
            mask = np.asarray(constraint.mask, dtype=bool)
            if mask.shape != (3,):
                raise StructureIOError("ASE FixScaled mask must contain three booleans")
            allowed[indices, :] &= ~mask
        else:
            raise StructureIOError(
                f"unsupported ASE constraint {type(constraint).__name__}; "
                "refusing to discard it"
            )
    return StructureRecord.from_fractional(
        lattice=atoms.cell.array,
        species=species,
        fractional_coordinates=atoms.get_scaled_positions(wrap=False),
        pbc=tuple(bool(value) for value in atoms.pbc),
        selective_dynamics=allowed.tolist() if has_constraints else None,
    )


def to_ase_atoms(structure: StructureRecord) -> Any:
    """Convert a record to ASE, translating allowed-motion flags to constraints."""

    Atoms, FixAtoms, FixScaled, _ = _ase()
    try:
        atoms = Atoms(
            symbols=list(structure.species),
            cell=structure.lattice_array(),
            scaled_positions=structure.fractional_array(),
            pbc=structure.pbc,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise StructureIOError(
            "ASE-backed formats require valid chemical element symbols"
        ) from exc

    if structure.selective_dynamics is not None:
        constraints: list[Any] = []
        fully_fixed: list[int] = []
        for index, motion_allowed in enumerate(structure.selective_dynamics):
            fixed = tuple(not value for value in motion_allowed)
            if all(fixed):
                fully_fixed.append(index)
            elif any(fixed):
                constraints.append(FixScaled(index, mask=fixed))
        if fully_fixed:
            constraints.append(FixAtoms(indices=fully_fixed))
        atoms.set_constraint(constraints)
    return atoms


def read_structure(
    path: str | Path,
    *,
    format: str | None = None,
) -> StructureReadResult:
    """Read one POSCAR/CONTCAR or CIF through ASE.

    POSCAR has no field for non-periodic axes, so ASE correctly returns three
    periodic axes. Callers that use vacuum as an application-level 2D marker
    must record that interpretation separately.
    """

    source = Path(path)
    if not source.is_file():
        raise StructureIOError(f"input file does not exist: {source}")
    format_name = _format_name(source, format)
    try:
        source_bytes = source.read_bytes()
        source_text = source_bytes.decode("utf-8")
    except OSError as exc:
        raise StructureIOError(f"could not read input file: {source}") from exc
    except UnicodeDecodeError as exc:
        raise StructureIOError(f"{format_name} input must be UTF-8 text") from exc
    if format_name == "vasp":
        _assert_supported_vasp_payload(source, source_text)
    _, _, _, (ase_read, _) = _ase()
    try:
        atoms = ase_read(StringIO(source_text), index=0, format=format_name)
    except Exception as exc:
        raise StructureIOError(f"ASE could not read {source} as {format_name}") from exc
    return StructureReadResult(
        structure=from_ase_atoms(atoms),
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        format=format_name,
        backend=_backend_version(),
    )


def write_structure(
    structure: StructureRecord,
    path: str | Path,
    *,
    format: str | None = None,
    direct: bool = True,
    overwrite: bool = False,
) -> Path:
    """Atomically write a POSCAR or CIF through ASE.

    A format write is rejected when it would silently discard non-periodic PBC
    flags or Selective-dynamics flags (CIF has no equivalent contract here).
    """

    target = Path(path)
    format_name = _format_name(target, format)
    if target.exists() and not overwrite:
        raise StructureIOError(f"output file already exists: {target}")
    if not all(structure.pbc):
        raise StructureIOError(
            f"{format_name} adapter cannot preserve non-periodic PBC flags"
        )
    if format_name == "cif" and structure.selective_dynamics is not None:
        raise StructureIOError("CIF adapter cannot preserve Selective-dynamics flags")
    if not target.parent.is_dir():
        raise StructureIOError(f"output directory does not exist: {target.parent}")

    atoms = to_ase_atoms(structure)
    _, _, _, (_, ase_write) = _ase()
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w", prefix=f".{target.name}.", dir=target.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
        options = {"direct": direct, "vasp5": True} if format_name == "vasp" else {}
        ase_write(temporary, atoms, format=format_name, **options)
        if overwrite:
            temporary.replace(target)
        else:
            try:
                os.link(temporary, target)
            except FileExistsError as exc:
                raise StructureIOError(f"output file already exists: {target}") from exc
            temporary.unlink()
            temporary = None
    except Exception as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if isinstance(exc, StructureIOError):
            raise
        raise StructureIOError(f"ASE could not write {target} as {format_name}") from exc
    return target

"""Core structure record with explicit coordinate conventions."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Sequence

import numpy as np
import numpy.typing as npt


FloatArray = npt.NDArray[np.float64]
_HASH_DECIMALS = 12
ORDERED_HASH_SCHEMA = "materials-structure-core/ordered-hash-v1"
_MAX_LATTICE_CONDITION = 1.0e12


def _matrix3(values: Sequence[Sequence[float]], *, name: str) -> FloatArray:
    array = np.asarray(values, dtype=np.float64)
    if array.shape != (3, 3):
        raise ValueError(f"{name} must have shape (3, 3), got {array.shape}")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite numbers")
    return array


def _coordinates(values: Sequence[Sequence[float]], *, name: str) -> FloatArray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 2 or array.shape[1:] != (3,):
        raise ValueError(f"{name} must have shape (N, 3), got {array.shape}")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite numbers")
    return array


def _tuples(array: FloatArray) -> tuple[tuple[float, float, float], ...]:
    return tuple(tuple(float(value) for value in row) for row in array)  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class StructureRecord:
    """A validated periodic structure using fractional coordinates.

    Lattice vectors are rows. Cartesian coordinates are calculated as
    ``fractional @ lattice``. Site order is meaningful and preserved.
    """

    lattice: tuple[tuple[float, float, float], ...]
    species: tuple[str, ...]
    fractional_coordinates: tuple[tuple[float, float, float], ...]
    pbc: tuple[bool, bool, bool] = (True, True, True)
    selective_dynamics: tuple[tuple[bool, bool, bool], ...] | None = None
    length_unit: str = "angstrom"

    def __post_init__(self) -> None:
        lattice = _matrix3(self.lattice, name="lattice")
        determinant = float(np.linalg.det(lattice))
        if abs(determinant) <= 1.0e-12:
            raise ValueError("lattice must be non-singular")
        if float(np.linalg.cond(lattice)) > _MAX_LATTICE_CONDITION:
            raise ValueError("lattice is too ill-conditioned for reliable conversion")

        coordinates = _coordinates(
            self.fractional_coordinates, name="fractional_coordinates"
        )
        species = tuple(self.species)
        pbc = tuple(self.pbc)
        dynamics = (
            None
            if self.selective_dynamics is None
            else tuple(tuple(flags) for flags in self.selective_dynamics)
        )
        if len(species) != len(coordinates):
            raise ValueError("species and fractional_coordinates must have equal length")
        if not species:
            raise ValueError("structure must contain at least one site")
        if any(not isinstance(symbol, str) or not symbol.strip() for symbol in species):
            raise ValueError("every species entry must be a non-empty string")
        if len(pbc) != 3 or any(type(value) is not bool for value in pbc):
            raise ValueError("pbc must contain exactly three booleans")
        if dynamics is not None:
            if len(dynamics) != len(species):
                raise ValueError("selective_dynamics must contain one flag triplet per site")
            if any(
                len(flags) != 3 or any(type(value) is not bool for value in flags)
                for flags in dynamics
            ):
                raise ValueError("each selective_dynamics entry must contain three booleans")
        if self.length_unit != "angstrom":
            raise ValueError("length_unit must be 'angstrom' in schema version 0.0")

        object.__setattr__(self, "lattice", _tuples(lattice))
        object.__setattr__(self, "species", species)
        object.__setattr__(self, "fractional_coordinates", _tuples(coordinates))
        object.__setattr__(self, "pbc", pbc)
        object.__setattr__(self, "selective_dynamics", dynamics)

    @classmethod
    def from_fractional(
        cls,
        *,
        lattice: Sequence[Sequence[float]],
        species: Iterable[str],
        fractional_coordinates: Sequence[Sequence[float]],
        pbc: Sequence[bool] = (True, True, True),
        selective_dynamics: Sequence[Sequence[bool]] | None = None,
        length_unit: str = "angstrom",
    ) -> StructureRecord:
        lattice_array = _matrix3(lattice, name="lattice")
        coordinate_array = _coordinates(
            fractional_coordinates, name="fractional_coordinates"
        )
        dynamics = (
            None
            if selective_dynamics is None
            else tuple(tuple(value for value in row) for row in selective_dynamics)
        )
        return cls(
            lattice=_tuples(lattice_array),
            species=tuple(species),
            fractional_coordinates=_tuples(coordinate_array),
            pbc=tuple(pbc),  # type: ignore[arg-type]
            selective_dynamics=dynamics,  # type: ignore[arg-type]
            length_unit=length_unit,
        )

    @classmethod
    def from_cartesian(
        cls,
        *,
        lattice: Sequence[Sequence[float]],
        species: Iterable[str],
        cartesian_coordinates: Sequence[Sequence[float]],
        pbc: Sequence[bool] = (True, True, True),
        selective_dynamics: Sequence[Sequence[bool]] | None = None,
        length_unit: str = "angstrom",
    ) -> StructureRecord:
        lattice_array = _matrix3(lattice, name="lattice")
        cartesian = _coordinates(cartesian_coordinates, name="cartesian_coordinates")
        try:
            fractional = np.linalg.solve(lattice_array.T, cartesian.T).T
        except np.linalg.LinAlgError as exc:
            raise ValueError("lattice must be non-singular") from exc
        return cls.from_fractional(
            lattice=lattice_array,
            species=species,
            fractional_coordinates=fractional,
            pbc=pbc,
            selective_dynamics=selective_dynamics,
            length_unit=length_unit,
        )

    def lattice_array(self) -> FloatArray:
        return np.asarray(self.lattice, dtype=np.float64).copy()

    def fractional_array(self) -> FloatArray:
        return np.asarray(self.fractional_coordinates, dtype=np.float64).copy()

    def cartesian_coordinates(self) -> FloatArray:
        return self.fractional_array() @ self.lattice_array()

    def wrapped(self) -> StructureRecord:
        fractional = self.fractional_array()
        for axis, periodic in enumerate(self.pbc):
            if periodic:
                fractional[:, axis] = fractional[:, axis] - np.floor(fractional[:, axis])
        return StructureRecord.from_fractional(
            lattice=self.lattice,
            species=self.species,
            fractional_coordinates=fractional,
            pbc=self.pbc,
            selective_dynamics=self.selective_dynamics,
            length_unit=self.length_unit,
        )

    def ordered_hash(self) -> str:
        """Return a deterministic, site-order-sensitive SHA-256 identifier.

        The hash wraps periodic axes and rounds numerical fields. It does not
        establish translation, basis, permutation, or symmetry equivalence.
        """

        wrapped = self.wrapped()

        def rounded(values: FloatArray) -> list[list[float]]:
            result = np.round(values, _HASH_DECIMALS)
            result[result == 0.0] = 0.0
            return result.tolist()

        payload = {
            "schema": ORDERED_HASH_SCHEMA,
            "length_unit": wrapped.length_unit,
            "quantization": {"method": "decimal-round", "decimals": _HASH_DECIMALS},
            "lattice": rounded(wrapped.lattice_array()),
            "species": list(wrapped.species),
            "fractional_coordinates": rounded(wrapped.fractional_array()),
            "pbc": list(wrapped.pbc),
            "selective_dynamics": wrapped.selective_dynamics,
        }
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

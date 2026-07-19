import numpy as np
import pytest
import json
from dataclasses import FrozenInstanceError

from materials_structure_core import StructureRecord


def test_fractional_to_cartesian_uses_row_lattice_convention() -> None:
    structure = StructureRecord.from_fractional(
        lattice=[[2, 0, 0], [0, 3, 0], [0, 0, 4]],
        species=["Si"],
        fractional_coordinates=[[0.5, 0.25, 0.75]],
    )
    np.testing.assert_allclose(structure.cartesian_coordinates(), [[1.0, 0.75, 3.0]])


def test_cartesian_round_trip_for_triclinic_lattice() -> None:
    lattice = [[3.0, 0.0, 0.0], [0.4, 2.8, 0.0], [0.2, 0.3, 5.0]]
    fractional = [[0.1, 0.2, 0.3], [0.9, 0.8, 0.7]]
    original = StructureRecord.from_fractional(
        lattice=lattice, species=["B", "N"], fractional_coordinates=fractional
    )
    recovered = StructureRecord.from_cartesian(
        lattice=lattice,
        species=original.species,
        cartesian_coordinates=original.cartesian_coordinates(),
    )
    np.testing.assert_allclose(recovered.fractional_array(), fractional)


def test_wrapping_applies_only_to_periodic_axes() -> None:
    structure = StructureRecord.from_fractional(
        lattice=np.eye(3),
        species=["H"],
        fractional_coordinates=[[-0.2, 1.2, 1.4]],
        pbc=[True, True, False],
    )
    np.testing.assert_allclose(structure.wrapped().fractional_array(), [[0.8, 0.2, 1.4]])


def test_rejects_singular_lattice() -> None:
    with pytest.raises(ValueError, match="non-singular"):
        StructureRecord.from_fractional(
            lattice=[[1, 0, 0], [2, 0, 0], [0, 0, 1]],
            species=["H"],
            fractional_coordinates=[[0, 0, 0]],
        )


def test_rejects_site_count_mismatch() -> None:
    with pytest.raises(ValueError, match="equal length"):
        StructureRecord.from_fractional(
            lattice=np.eye(3),
            species=["H", "He"],
            fractional_coordinates=[[0, 0, 0]],
        )


def test_rejects_selective_dynamics_count_mismatch() -> None:
    with pytest.raises(ValueError, match="one flag triplet"):
        StructureRecord.from_fractional(
            lattice=np.eye(3),
            species=["H"],
            fractional_coordinates=[[0, 0, 0]],
            selective_dynamics=[],
        )


def test_rejects_non_boolean_selective_dynamics() -> None:
    with pytest.raises(ValueError, match="three booleans"):
        StructureRecord.from_fractional(
            lattice=np.eye(3),
            species=["H"],
            fractional_coordinates=[[0, 0, 0]],
            selective_dynamics=[[1, 0, 1]],
        )


def test_direct_constructor_deeply_normalizes_mutable_inputs() -> None:
    lattice = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    species = ["H"]
    coordinates = [[0.0, 0.0, 0.0]]
    structure = StructureRecord(lattice, species, coordinates)  # type: ignore[arg-type]
    original_hash = structure.ordered_hash()
    lattice[0][0] = 2.0
    species[0] = "He"
    coordinates[0][0] = 0.5
    assert structure.ordered_hash() == original_hash
    assert isinstance(structure.lattice, tuple)
    with pytest.raises(FrozenInstanceError):
        structure.species = ("He",)  # type: ignore[misc]


def test_schema_rejects_non_angstrom_length_unit() -> None:
    with pytest.raises(ValueError, match="angstrom"):
        StructureRecord.from_fractional(
            lattice=np.eye(3),
            species=["H"],
            fractional_coordinates=[[0, 0, 0]],
            length_unit="bohr",
        )


def test_ordered_hash_is_stable_under_periodic_wrapping() -> None:
    first = StructureRecord.from_fractional(
        lattice=np.eye(3), species=["H"], fractional_coordinates=[[-0.2, 0, 0]]
    )
    second = StructureRecord.from_fractional(
        lattice=np.eye(3), species=["H"], fractional_coordinates=[[0.8, 0, 0]]
    )
    assert first.ordered_hash() == second.ordered_hash()


def test_ordered_hash_preserves_site_order() -> None:
    first = StructureRecord.from_fractional(
        lattice=np.eye(3),
        species=["B", "N"],
        fractional_coordinates=[[0, 0, 0], [0.5, 0.5, 0.5]],
    )
    second = StructureRecord.from_fractional(
        lattice=np.eye(3),
        species=["N", "B"],
        fractional_coordinates=[[0.5, 0.5, 0.5], [0, 0, 0]],
    )
    assert first.ordered_hash() != second.ordered_hash()


def test_ordered_hash_v1_golden_digest() -> None:
    structure = StructureRecord.from_fractional(
        lattice=np.eye(3), species=["H"], fractional_coordinates=[[0, 0, 0]]
    )
    assert structure.ordered_hash() == (
        "f6fb14183a0290b41c60a1ad7e05657"
        "f9ae6ab8924d0bd6d6e10105bd77cd169"
    )


def test_structure_record_json_round_trip_preserves_contract() -> None:
    structure = StructureRecord.from_fractional(
        lattice=[[3, 0, 0], [0.2, 4, 0], [0, 0, 12]],
        species=["B", "N"],
        fractional_coordinates=[[0.1, 0.2, 0.3], [0.6, 0.7, 0.8]],
        pbc=[True, True, False],
        selective_dynamics=[[True, True, False], [False, False, True]],
    )
    payload = json.loads(json.dumps(structure.to_dict()))
    restored = StructureRecord.from_dict(payload)
    assert restored == structure
    assert restored.ordered_hash() == structure.ordered_hash()


def test_structure_record_from_dict_rejects_unknown_schema() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        StructureRecord.from_dict({"schema_version": "99"})

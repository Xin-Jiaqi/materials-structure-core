from __future__ import annotations

import json
from pathlib import Path

from ase import Atoms
from ase.constraints import Hookean
import numpy as np
import pytest

from materials_structure_core import (
    StructureIOError,
    StructureRecord,
    from_ase_atoms,
    read_structure,
    sha256_file,
    write_structure,
)


FIXTURES = Path(__file__).parent / "fixtures"


def test_fixture_manifest_binds_every_committed_poscar() -> None:
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    entries = manifest["fixtures"]
    assert len({entry["id"] for entry in entries}) == len(entries)
    assert {entry["path"] for entry in entries} == {
        path.name for path in FIXTURES.glob("*.vasp")
    }
    for entry in entries:
        assert sha256_file(FIXTURES / entry["path"]) == entry["sha256"]
        assert entry["expected"]


def test_reads_direct_positive_scale_fixture() -> None:
    result = read_structure(FIXTURES / "POSCAR_direct_scaled.vasp")
    np.testing.assert_allclose(
        result.structure.lattice_array(),
        [[3.0, 0.0, 0.0], [0.4, 2.8, 0.0], [0.2, 0.6, 8.0]],
    )
    np.testing.assert_allclose(
        result.structure.fractional_array(), [[0.1, 0.2, 0.3], [0.9, 0.8, 0.7]]
    )
    assert result.structure.species == ("B", "N")
    assert len(result.source_sha256) == 64
    assert result.backend.startswith("ase/")


def test_reads_cartesian_scale_semantics() -> None:
    result = read_structure(FIXTURES / "POSCAR_cartesian_scaled.vasp")
    np.testing.assert_allclose(
        result.structure.cartesian_coordinates(), [[0.5, 1.0, 1.5]]
    )


def test_reads_negative_target_volume_semantics() -> None:
    result = read_structure(FIXTURES / "POSCAR_negative_volume.vasp")
    assert abs(np.linalg.det(result.structure.lattice_array())) == pytest.approx(64.0)
    np.testing.assert_allclose(result.structure.fractional_array(), [[0.25, 0.5, 0.75]])


def test_selective_dynamics_allowed_motion_contract() -> None:
    result = read_structure(FIXTURES / "POSCAR_selective.vasp")
    assert result.structure.selective_dynamics == (
        (False, False, False),
        (True, False, True),
        (True, True, True),
    )


@pytest.mark.parametrize("direct", [True, False])
def test_poscar_write_read_round_trip(tmp_path: Path, direct: bool) -> None:
    original = read_structure(FIXTURES / "POSCAR_selective.vasp").structure
    output = tmp_path / f"roundtrip-{direct}.vasp"
    write_structure(original, output, direct=direct)
    recovered = read_structure(output).structure
    assert recovered.species == original.species
    assert recovered.selective_dynamics == original.selective_dynamics
    np.testing.assert_allclose(recovered.lattice_array(), original.lattice_array())
    np.testing.assert_allclose(
        recovered.cartesian_coordinates(), original.cartesian_coordinates(), atol=1e-12
    )


def test_cif_round_trip_for_unconstrained_structure(tmp_path: Path) -> None:
    original = StructureRecord.from_fractional(
        lattice=[[3, 0, 0], [0.2, 3.2, 0], [0.1, 0.3, 5]],
        species=["B", "N"],
        fractional_coordinates=[[0, 0, 0], [0.25, 0.5, 0.75]],
    )
    output = tmp_path / "structure.cif"
    write_structure(original, output)
    recovered = read_structure(output).structure
    assert recovered.species == original.species
    np.testing.assert_allclose(recovered.lattice_array(), original.lattice_array(), atol=1e-9)
    np.testing.assert_allclose(
        recovered.cartesian_coordinates(), original.cartesian_coordinates(), atol=1e-9
    )


def test_refuses_lossy_cif_and_pbc_writes(tmp_path: Path) -> None:
    selective = read_structure(FIXTURES / "POSCAR_selective.vasp").structure
    with pytest.raises(StructureIOError, match="Selective"):
        write_structure(selective, tmp_path / "lossy.cif")
    nonperiodic = StructureRecord.from_fractional(
        lattice=np.eye(3),
        species=["H"],
        fractional_coordinates=[[0, 0, 0]],
        pbc=[True, True, False],
    )
    with pytest.raises(StructureIOError, match="non-periodic"):
        write_structure(nonperiodic, tmp_path / "lossy.vasp")


def test_refuses_unknown_ase_constraint() -> None:
    atoms = Atoms("H2", positions=[[0, 0, 0], [0, 0, 0.8]], cell=np.eye(3), pbc=True)
    atoms.set_constraint(Hookean(a1=0, a2=1, rt=0.8, k=1.0))
    with pytest.raises(StructureIOError, match="refusing to discard"):
        from_ase_atoms(atoms)


def test_output_requires_explicit_overwrite(tmp_path: Path) -> None:
    structure = read_structure(FIXTURES / "POSCAR_direct_scaled.vasp").structure
    output = tmp_path / "POSCAR"
    write_structure(structure, output)
    with pytest.raises(StructureIOError, match="already exists"):
        write_structure(structure, output)
    write_structure(structure, output, overwrite=True)


def test_no_overwrite_is_atomic_against_a_late_competing_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from materials_structure_core import io as io_module

    structure = read_structure(FIXTURES / "POSCAR_direct_scaled.vasp").structure
    output = tmp_path / "POSCAR"

    def competing_link(source: Path, target: Path) -> None:
        target.write_text("competing writer\n", encoding="utf-8")
        raise FileExistsError(target)

    monkeypatch.setattr(io_module.os, "link", competing_link)
    with pytest.raises(StructureIOError, match="already exists"):
        write_structure(structure, output)
    assert output.read_text(encoding="utf-8") == "competing writer\n"
    assert not list(tmp_path.glob(".POSCAR.*"))


@pytest.mark.parametrize(
    "content",
    [
        "too short\n",
        "bad scale\nnot-a-number\n1 0 0\n0 1 0\n0 0 1\nH\n1\nDirect\n0 0 0\n",
        "truncated\n1\n1 0 0\n0 1 0\n0 0 1\nH\n2\nDirect\n0 0 0\n",
    ],
)
def test_malformed_poscar_is_rejected(tmp_path: Path, content: str) -> None:
    source = tmp_path / "malformed.vasp"
    source.write_text(content, encoding="utf-8")
    with pytest.raises(StructureIOError, match="could not read"):
        read_structure(source)


@pytest.mark.parametrize("mode", ["Direct", "Cartesian"])
def test_poscar_velocity_tail_is_rejected(tmp_path: Path, mode: str) -> None:
    source = tmp_path / "with-velocities.vasp"
    coordinate = "0 0 0" if mode == "Direct" else "0.1 0.2 0.3"
    source.write_text(
        "velocity fixture\n1.0\n1 0 0\n0 1 0\n0 0 1\nH\n1\n"
        f"{mode}\n{coordinate}\n\nCartesian\n0.01 0.02 0.03\n",
        encoding="utf-8",
    )
    with pytest.raises(StructureIOError, match="velocities"):
        read_structure(source)


def test_commented_count_line_cannot_bypass_velocity_tail_guard(tmp_path: Path) -> None:
    source = tmp_path / "commented-counts.vasp"
    source.write_text(
        "velocity fixture\n1.0\n1 0 0\n0 1 0\n0 0 1\nH\n"
        "1 ! one hydrogen\nDirect\n0 0 0\nCartesian\n0.01 0.02 0.03\n",
        encoding="utf-8",
    )
    with pytest.raises(StructureIOError, match="velocities"):
        read_structure(source)


def test_poscar_predictor_tail_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "predictor.vasp"
    source.write_text(
        "predictor fixture\n1.0\n1 0 0\n0 1 0\n0 0 1\nH\n1\n"
        "Direct\n0 0 0\nPREDICTOR-CORRECTOR\n",
        encoding="utf-8",
    )
    with pytest.raises(StructureIOError, match="predictor-corrector"):
        read_structure(source)


@pytest.mark.parametrize(
    "rows",
    [
        ["C1 C 0 0 0 0.5"],
        ["C1 C 0 0 0 0.5", "N1 N 0 0 0 0.5"],
    ],
)
def test_partial_or_mixed_cif_occupancy_is_rejected(
    tmp_path: Path, rows: list[str]
) -> None:
    source = tmp_path / "disordered.cif"
    source.write_text(
        "data_disordered\n_cell_length_a 3\n_cell_length_b 3\n"
        "_cell_length_c 3\n_cell_angle_alpha 90\n_cell_angle_beta 90\n"
        "_cell_angle_gamma 90\nloop_\n_atom_site_label\n"
        "_atom_site_type_symbol\n_atom_site_fract_x\n_atom_site_fract_y\n"
        "_atom_site_fract_z\n_atom_site_occupancy\n"
        + "\n".join(rows)
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(StructureIOError, match="occupancy"):
        read_structure(source)


@pytest.mark.parametrize(
    "metadata",
    [
        ["bad"],
        {"0": {"H": float("nan")}},
        {"0": "bad"},
        {"0": {"H": True}},
        {"0": {"H": "1"}},
    ],
)
def test_malformed_ase_occupancy_metadata_is_rejected(metadata: object) -> None:
    atoms = Atoms("H", positions=[[0, 0, 0]], cell=np.eye(3), pbc=True)
    atoms.info["occupancy"] = metadata
    with pytest.raises(StructureIOError, match="occupancy"):
        from_ase_atoms(atoms)


def test_non_finite_ase_site_charge_is_rejected() -> None:
    atoms = Atoms("H", positions=[[0, 0, 0]], cell=np.eye(3), pbc=True)
    atoms.set_initial_charges([float("nan")])
    with pytest.raises(StructureIOError, match="charges"):
        from_ase_atoms(atoms)

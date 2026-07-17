from pathlib import Path
import json

import pytest

from materials_structure_core import (
    ProvenanceManifest,
    StructureRecord,
    Transformation,
    sha256_file,
)


def test_manifest_serializes_transformations() -> None:
    structure = StructureRecord.from_fractional(
        lattice=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        species=["H"],
        fractional_coordinates=[[0, 0, 0]],
    )
    manifest = ProvenanceManifest(
        source_uri="synthetic://fixture/cubic-v1",
        source_sha256="a" * 64,
        result_structure_id=structure.ordered_hash(),
        created_at="2026-07-17T00:00:00Z",
        producer="fixture-generator/0.1",
        transformations=(Transformation("wrap", {"axes": [0, 1, 2]}),),
    )
    assert manifest.to_dict()["transformations"][0]["name"] == "wrap"
    json.dumps(manifest.to_dict())
    manifest.verify_result(structure)
    with pytest.raises(TypeError):
        manifest.transformations[0].parameters["changed"] = True  # type: ignore[index]


def test_manifest_rejects_non_sha256_value() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        ProvenanceManifest(
            source_uri="synthetic://fixture",
            source_sha256="not-a-hash",
            result_structure_id="b" * 64,
            created_at="2026-07-17T00:00:00Z",
            producer="test",
        )


def test_transformation_rejects_non_json_parameters() -> None:
    with pytest.raises(ValueError, match="only JSON values"):
        Transformation("bad", {"value": object()})


def test_transformation_requires_mapping_at_top_level() -> None:
    with pytest.raises(ValueError, match="must be a mapping"):
        Transformation("bad", [1, 2])  # type: ignore[arg-type]


def test_manifest_rejects_non_utc_timestamp() -> None:
    with pytest.raises(ValueError, match="ISO-8601|UTC"):
        ProvenanceManifest(
            source_uri="synthetic://fixture",
            source_sha256="a" * 64,
            result_structure_id="b" * 64,
            created_at="not-a-date",
            producer="test",
        )


def test_manifest_detects_result_mismatch() -> None:
    structure = StructureRecord.from_fractional(
        lattice=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        species=["H"],
        fractional_coordinates=[[0, 0, 0]],
    )
    manifest = ProvenanceManifest(
        source_uri="synthetic://fixture",
        source_sha256="a" * 64,
        result_structure_id="b" * 64,
        created_at="2026-07-17T00:00:00Z",
        producer="test",
    )
    with pytest.raises(ValueError, match="does not match"):
        manifest.verify_result(structure)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("parser", Path("parser"), "parser"),
        ("schema_version", Path("0.1"), "schema_version"),
        ("hash_schema", Path("hash"), "hash_schema"),
    ],
)
def test_manifest_rejects_non_json_string_fields(
    field: str, value: object, message: str
) -> None:
    kwargs = {
        "source_uri": "synthetic://fixture",
        "source_sha256": "a" * 64,
        "result_structure_id": "b" * 64,
        "created_at": "2026-07-17T00:00:00Z",
        "producer": "test",
        field: value,
    }
    with pytest.raises(ValueError, match=message):
        ProvenanceManifest(**kwargs)  # type: ignore[arg-type]


def test_sha256_file(tmp_path: Path) -> None:
    target = tmp_path / "input.txt"
    target.write_bytes(b"abc")
    assert sha256_file(target) == (
        "ba7816bf8f01cfea414140de5dae2223"
        "b00361a396177a9cb410ff61f20015ad"
    )

"""Serializable provenance records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from types import MappingProxyType
from typing import Any, Mapping

from .model import ORDERED_HASH_SCHEMA, StructureRecord


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _freeze_json(value: Any) -> Any:
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("JSON numbers must be finite")
        return value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("transformation parameter keys must be strings")
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    raise ValueError("transformation parameters must contain only JSON values")


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _validate_utc_timestamp(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("created_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("created_at must include a UTC offset")


@dataclass(frozen=True, slots=True)
class Transformation:
    name: str
    parameters: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("transformation name must not be empty")
        if not isinstance(self.parameters, Mapping):
            raise ValueError("transformation parameters must be a mapping")
        frozen = _freeze_json(self.parameters)
        json.dumps(_thaw_json(frozen), ensure_ascii=False, sort_keys=True)
        object.__setattr__(self, "parameters", frozen)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "parameters": _thaw_json(self.parameters)}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Transformation:
        if not isinstance(value, Mapping):
            raise ValueError("transformation must be a mapping")
        try:
            return cls(name=value["name"], parameters=value["parameters"])
        except KeyError as exc:
            raise ValueError(f"transformation is missing {exc.args[0]!r}") from exc


@dataclass(frozen=True, slots=True)
class ProvenanceManifest:
    source_uri: str
    source_sha256: str
    result_structure_id: str
    created_at: str
    producer: str
    parser: str | None = None
    parent_structure_id: str | None = None
    transformations: tuple[Transformation, ...] = ()
    schema_version: str = "0.1"
    hash_schema: str = ORDERED_HASH_SCHEMA

    def __post_init__(self) -> None:
        if not isinstance(self.source_uri, str) or not self.source_uri.strip():
            raise ValueError("source_uri must not be empty")
        if not isinstance(self.source_sha256, str) or not _SHA256.fullmatch(
            self.source_sha256
        ):
            raise ValueError("source_sha256 must be a lowercase 64-character SHA-256")
        if not isinstance(self.result_structure_id, str) or not _SHA256.fullmatch(
            self.result_structure_id
        ):
            raise ValueError("result_structure_id must be a lowercase 64-character SHA-256")
        if self.parent_structure_id is not None and (
            not isinstance(self.parent_structure_id, str)
            or not _SHA256.fullmatch(self.parent_structure_id)
        ):
            raise ValueError("parent_structure_id must be a lowercase 64-character SHA-256")
        if not isinstance(self.producer, str) or not self.producer.strip():
            raise ValueError("producer must not be empty")
        if self.parser is not None and not isinstance(self.parser, str):
            raise ValueError("parser must be a string or None")
        if not isinstance(self.schema_version, str) or not self.schema_version.strip():
            raise ValueError("schema_version must be a non-empty string")
        if self.hash_schema != ORDERED_HASH_SCHEMA:
            raise ValueError(f"hash_schema must be {ORDERED_HASH_SCHEMA!r}")
        _validate_utc_timestamp(self.created_at)
        transformations = tuple(self.transformations)
        if any(not isinstance(item, Transformation) for item in transformations):
            raise ValueError("transformations must contain Transformation records")
        object.__setattr__(self, "transformations", transformations)

    def verify_result(self, structure: StructureRecord) -> None:
        if self.hash_schema != ORDERED_HASH_SCHEMA:
            raise ValueError(f"unsupported hash schema: {self.hash_schema}")
        if self.result_structure_id != structure.ordered_hash():
            raise ValueError("manifest result_structure_id does not match the structure")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_uri": self.source_uri,
            "source_sha256": self.source_sha256,
            "result_structure_id": self.result_structure_id,
            "hash_schema": self.hash_schema,
            "created_at": self.created_at,
            "producer": self.producer,
            "parser": self.parser,
            "parent_structure_id": self.parent_structure_id,
            "transformations": [item.to_dict() for item in self.transformations],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ProvenanceManifest:
        """Construct and validate a manifest from its public JSON mapping."""

        if not isinstance(value, Mapping):
            raise ValueError("manifest must be a mapping")
        required = {
            "source_uri",
            "source_sha256",
            "result_structure_id",
            "created_at",
            "producer",
        }
        missing = sorted(required - value.keys())
        if missing:
            raise ValueError("manifest is missing: " + ", ".join(missing))
        transformations = value.get("transformations", ())
        if not isinstance(transformations, (list, tuple)):
            raise ValueError("transformations must be an array")
        return cls(
            source_uri=value["source_uri"],
            source_sha256=value["source_sha256"],
            result_structure_id=value["result_structure_id"],
            created_at=value["created_at"],
            producer=value["producer"],
            parser=value.get("parser"),
            parent_structure_id=value.get("parent_structure_id"),
            transformations=tuple(
                Transformation.from_dict(item) for item in transformations
            ),
            schema_version=value.get("schema_version", "0.1"),
            hash_schema=value.get("hash_schema", ORDERED_HASH_SCHEMA),
        )

    @classmethod
    def read_json(cls, path: str | Path) -> ProvenanceManifest:
        """Read a manifest without accepting non-object JSON values."""

        try:
            value = json.loads(Path(path).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid manifest JSON: {exc}") from exc
        return cls.from_dict(value)

    def write_json(self, path: str | Path, *, overwrite: bool = False) -> Path:
        """Atomically write a manifest, refusing replacement unless requested."""

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not overwrite:
            raise FileExistsError(f"manifest already exists: {target}")
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(self.to_dict(), handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            if target.exists() and not overwrite:
                raise FileExistsError(f"manifest already exists: {target}")
            os.replace(temporary, target)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        return target


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()

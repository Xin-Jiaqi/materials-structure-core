"""Command-line interface for inspected, provenance-aware structure conversion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .io import StructureIOError, read_structure, write_structure


def _inspect(args: argparse.Namespace) -> int:
    result = read_structure(args.input, format=args.format)
    structure = result.structure
    payload = {
        "source": str(Path(args.input)),
        "source_sha256": result.source_sha256,
        "format": result.format,
        "backend": result.backend,
        "ordered_hash": structure.ordered_hash(),
        "formula": _formula(structure.species),
        "site_count": len(structure.species),
        "pbc": list(structure.pbc),
        "has_selective_dynamics": structure.selective_dynamics is not None,
        "length_unit": structure.length_unit,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _formula(species: tuple[str, ...]) -> str:
    order: list[str] = []
    counts: dict[str, int] = {}
    for symbol in species:
        if symbol not in counts:
            order.append(symbol)
            counts[symbol] = 0
        counts[symbol] += 1
    return "".join(f"{symbol}{counts[symbol] if counts[symbol] != 1 else ''}" for symbol in order)


def _convert(args: argparse.Namespace) -> int:
    result = read_structure(args.input, format=args.input_format)
    output = write_structure(
        result.structure,
        args.output,
        format=args.output_format,
        direct=not args.cartesian,
        overwrite=args.force,
    )
    print(output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="structure-core")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="emit a JSON structure summary")
    inspect_parser.add_argument("input")
    inspect_parser.add_argument("--format", choices=("vasp", "cif"))
    inspect_parser.set_defaults(handler=_inspect)

    convert_parser = subparsers.add_parser("convert", help="convert POSCAR/CIF through ASE")
    convert_parser.add_argument("input")
    convert_parser.add_argument("output")
    convert_parser.add_argument("--input-format", choices=("vasp", "cif"))
    convert_parser.add_argument("--output-format", choices=("vasp", "cif"))
    convert_parser.add_argument("--cartesian", action="store_true", help="write POSCAR Cartesian coordinates")
    convert_parser.add_argument("--force", action="store_true")
    convert_parser.set_defaults(handler=_convert)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except StructureIOError as exc:
        parser.error(str(exc))
    return 2

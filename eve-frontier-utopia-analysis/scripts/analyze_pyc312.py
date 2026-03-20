#!/usr/bin/env python3
from __future__ import annotations

import argparse
import dis
import importlib
import io
import json
import marshal
import os
import sys
import types
from pathlib import Path

from google.protobuf.descriptor import FieldDescriptor


HIGH_VALUE_PYC_MODULES = [
    "frontier/station_hud/undock/controller.pyc",
    "frontier/smart_assemblies/client/window/cargo.pyc",
    "frontier/base_building/client/construction_site/ui/window.pyc",
    "frontier/signatures_and_scanning/client/scanning_service.pyc",
    "frontier/jump_drive/client/service.pyc",
    "frontier/jump_drive/client/jump_drive.pyc",
    "frontier/crdata/common/objects/cr_stargate.pyc",
]

HIGH_VALUE_PB2_MODULES = [
    "eveProto.generated.eve.assembly.gate.api.requests_pb2",
    "eveProto.generated.eve.assembly.gate.api.events_pb2",
    "eveProto.generated.eve.assembly.gate.gate_pb2",
    "eveProto.generated.eve.solarsystem.solarsystem_pb2",
    "eveProto.generated.eve.character.hacking.container_pb2",
    "eveProto.generated.eve.deadspace.datasite.data_site_pb2",
    "eveProto.generated.eve.deadspace.datasite.event_pb2",
    "eveProto.generated.eve.deadspace.relicsite.relic_site_pb2",
    "eveProto.generated.eve.deadspace.relicsite.event_pb2",
    "eveProto.generated.eve.character.operation.operation_pb2",
    "eveProto.generated.eve.sponsoredtransaction.api.requests_pb2",
    "eveProto.generated.eve.sponsoredtransaction.preparedtransaction.api.requests_pb2",
    "eveProto.generated.eve.sponsoredtransaction.preparedtransaction.preparedtransaction_pb2",
    "eveProto.generated.eve.sponsoredtransaction.reservation.reservation_pb2",
    "eveProto.generated.eve.sponsoredtransaction.result_pb2",
    "eveProto.generated.eve.planet.planet_pb2",
    "eveProto.generated.eve.planet.pin_pb2",
    "eveProto.generated.eve.planetinteraction.collector.collector_pb2",
    "eveProto.generated.eve.planetinteraction.colony.colony_pb2",
    "eveProto.generated.eve.planetinteraction.factory.factory_pb2",
    "eveProto.generated.eve.planetinteraction.link.link_pb2",
    "eveProto.generated.eve.planetinteraction.pin.pin_pb2",
    "eveProto.generated.eve.planetinteraction.route.route_pb2",
    "eveProto.generated.eve.planetinteraction.schematic.schematic_pb2",
    "eveProto.generated.eve.planetinteraction.storage.storage_pb2",
]

FIELD_TYPE_NAMES = {
    FieldDescriptor.TYPE_DOUBLE: "double",
    FieldDescriptor.TYPE_FLOAT: "float",
    FieldDescriptor.TYPE_INT64: "int64",
    FieldDescriptor.TYPE_UINT64: "uint64",
    FieldDescriptor.TYPE_INT32: "int32",
    FieldDescriptor.TYPE_FIXED64: "fixed64",
    FieldDescriptor.TYPE_FIXED32: "fixed32",
    FieldDescriptor.TYPE_BOOL: "bool",
    FieldDescriptor.TYPE_STRING: "string",
    FieldDescriptor.TYPE_GROUP: "group",
    FieldDescriptor.TYPE_MESSAGE: "message",
    FieldDescriptor.TYPE_BYTES: "bytes",
    FieldDescriptor.TYPE_UINT32: "uint32",
    FieldDescriptor.TYPE_ENUM: "enum",
    FieldDescriptor.TYPE_SFIXED32: "sfixed32",
    FieldDescriptor.TYPE_SFIXED64: "sfixed64",
    FieldDescriptor.TYPE_SINT32: "sint32",
    FieldDescriptor.TYPE_SINT64: "sint64",
}

FIELD_LABEL_NAMES = {
    FieldDescriptor.LABEL_OPTIONAL: "optional",
    FieldDescriptor.LABEL_REQUIRED: "required",
    FieldDescriptor.LABEL_REPEATED: "repeated",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze extracted EVE Frontier 3.12 .pyc files and selected pb2 modules."
    )
    parser.add_argument(
        "--extracted-root",
        type=Path,
        required=True,
        help="Root folder containing extracted .pyc files from code.ccp.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output folder for analysis JSON and disassembly files.",
    )
    parser.add_argument(
        "--module",
        action="append",
        default=[],
        help="Relative .pyc path to analyze. Can be repeated. Defaults to a curated high-value set.",
    )
    parser.add_argument(
        "--pb2-module",
        action="append",
        default=[],
        help="Import path for a pb2 module to export. Can be repeated. Defaults to a curated high-value set.",
    )
    return parser.parse_args()


def ensure_python312() -> None:
    if sys.version_info < (3, 12):
        raise RuntimeError("This script requires Python 3.12 or newer to load 3.12 .pyc files.")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def load_code_object(pyc_path: Path) -> types.CodeType:
    with pyc_path.open("rb") as handle:
        handle.read(16)
        code_obj = marshal.load(handle)
    if not isinstance(code_obj, types.CodeType):
        raise TypeError(f"Expected a code object in {pyc_path}")
    return code_obj


def code_strings(code_obj: types.CodeType) -> list[str]:
    return [value for value in code_obj.co_consts if isinstance(value, str)]


def collect_code_objects(code_obj: types.CodeType, prefix: str = "<module>") -> list[dict[str, object]]:
    objects = [
        {
            "qualname": prefix,
            "co_name": code_obj.co_name,
            "names": list(code_obj.co_names),
            "strings": code_strings(code_obj),
        }
    ]
    for const in code_obj.co_consts:
        if isinstance(const, types.CodeType):
            child_name = const.co_name if prefix == "<module>" else f"{prefix}.{const.co_name}"
            objects.extend(collect_code_objects(const, prefix=child_name))
    return objects


def disassemble(code_obj: types.CodeType) -> str:
    buffer = io.StringIO()
    dis.dis(code_obj, file=buffer)
    return buffer.getvalue()


def analyze_module(pyc_path: Path, extracted_root: Path) -> tuple[dict[str, object], str]:
    code_obj = load_code_object(pyc_path)
    rel_path = pyc_path.relative_to(extracted_root)
    payload = {
        "path": str(rel_path),
        "top_level_names": list(code_obj.co_names),
        "top_level_strings": code_strings(code_obj),
        "code_objects": collect_code_objects(code_obj),
    }
    return payload, disassemble(code_obj)


def message_descriptor_to_dict(message) -> dict[str, object]:
    return {
        "name": message.name,
        "full_name": message.full_name,
        "fields": [
            {
                "number": field.number,
                "name": field.name,
                "type": FIELD_TYPE_NAMES.get(field.type, str(field.type)),
                "label": FIELD_LABEL_NAMES.get(
                    getattr(field, "label", FieldDescriptor.LABEL_OPTIONAL),
                    str(getattr(field, "label", FieldDescriptor.LABEL_OPTIONAL)),
                ),
                "type_name": field.message_type.full_name if field.message_type else None,
                "enum_name": field.enum_type.full_name if field.enum_type else None,
            }
            for field in message.fields
        ],
        "nested_messages": [message_descriptor_to_dict(nested) for nested in message.nested_types],
        "enum_types": [
            {
                "name": enum.name,
                "full_name": enum.full_name,
                "values": [{"name": value.name, "number": value.number} for value in enum.values],
            }
            for enum in message.enum_types
        ],
    }


def file_descriptor_to_dict(file_desc) -> dict[str, object]:
    return {
        "name": file_desc.name,
        "package": file_desc.package,
        "dependencies": [dependency.name for dependency in file_desc.dependencies],
        "messages": [message_descriptor_to_dict(message) for message in file_desc.message_types_by_name.values()],
        "enum_types": [
            {
                "name": enum.name,
                "full_name": enum.full_name,
                "values": [{"name": value.name, "number": value.number} for value in enum.values],
            }
            for enum in file_desc.enum_types_by_name.values()
        ],
    }


def install_pb2_stubs() -> dict[str, types.ModuleType | None]:
    saved_modules = {"uthread2": sys.modules.get("uthread2")}
    uthread2_stub = types.ModuleType("uthread2")
    uthread2_stub.StartTasklet = lambda *args, **kwargs: None
    uthread2_stub.Sleep = lambda *args, **kwargs: None
    sys.modules["uthread2"] = uthread2_stub
    return saved_modules


def restore_modules(saved_modules: dict[str, types.ModuleType | None]) -> None:
    for module_name, previous in saved_modules.items():
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous


def export_pb2(import_name: str, pb2_root: Path) -> dict[str, object]:
    os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
    managed_roots = ("eveProto", "monolithconfig")
    for module_name in [
        name for name in list(sys.modules) if any(name == root or name.startswith(f"{root}.") for root in managed_roots)
    ]:
        sys.modules.pop(module_name, None)
    saved_modules = install_pb2_stubs()
    sys.path.insert(0, str(pb2_root))
    try:
        module = importlib.import_module(import_name)
        descriptor = getattr(module, "DESCRIPTOR")
        return {"import_name": import_name, "status": "ok", "descriptor": file_descriptor_to_dict(descriptor)}
    finally:
        for module_name in [
            name for name in list(sys.modules) if any(name == root or name.startswith(f"{root}.") for root in managed_roots)
        ]:
            sys.modules.pop(module_name, None)
        restore_modules(saved_modules)
        if sys.path and sys.path[0] == str(pb2_root):
            sys.path.pop(0)


def module_output_path(base: Path, rel_path: str, suffix: str) -> Path:
    return base / (rel_path + suffix)


def pb2_output_path(base: Path, import_name: str) -> Path:
    return base / (import_name.replace(".", "/") + ".json")


def main() -> int:
    ensure_python312()
    args = parse_args()
    extracted_root = args.extracted_root.expanduser().resolve()
    output_root = args.output.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    module_targets = args.module or HIGH_VALUE_PYC_MODULES
    pb2_targets = args.pb2_module or HIGH_VALUE_PB2_MODULES

    module_results: list[dict[str, object]] = []
    pb2_results: list[dict[str, object]] = []

    for rel_path in module_targets:
        pyc_path = extracted_root / rel_path
        try:
            payload, disassembly = analyze_module(pyc_path, extracted_root)
            write_json(module_output_path(output_root / "pyc_metadata", rel_path, ".json"), payload)
            write_text(module_output_path(output_root / "pyc_disassembly", rel_path, ".dis.txt"), disassembly)
            module_results.append({"path": rel_path, "status": "ok"})
        except Exception as exc:  # pragma: no cover - defensive fallback
            error = {"path": rel_path, "status": "error", "error": str(exc)}
            module_results.append(error)
            write_json(module_output_path(output_root / "pyc_metadata", rel_path, ".error.json"), error)

    for import_name in pb2_targets:
        try:
            payload = export_pb2(import_name, extracted_root)
            write_json(pb2_output_path(output_root / "pb2", import_name), payload["descriptor"])
            pb2_results.append({"import_name": import_name, "status": "ok"})
        except Exception as exc:  # pragma: no cover - defensive fallback
            error = {"import_name": import_name, "status": "error", "error": str(exc)}
            pb2_results.append(error)
            write_json(
                pb2_output_path(output_root / "pb2", import_name.replace("_pb2", "_pb2_error")),
                error,
            )

    summary = {
        "python": sys.version,
        "extracted_root": str(extracted_root),
        "module_results": module_results,
        "pb2_results": pb2_results,
    }
    write_json(output_root / "summary.json", summary)
    print(f"Wrote Python 3.12 analysis output to: {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

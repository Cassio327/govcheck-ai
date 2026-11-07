import argparse
import json
from pathlib import Path
from typing import Any

from govcheck.main import app

PUBLIC_SCHEMAS = (
    "DocumentResponse",
    "CitationResponse",
    "ChatAnswerResponse",
    "AnalysisJobResponse",
    "FindingCitationResponse",
    "FindingResponse",
)


def _typescript_type(schema: dict[str, Any]) -> str:
    reference = schema.get("$ref")
    if isinstance(reference, str):
        return reference.rsplit("/", 1)[-1]
    enum = schema.get("enum")
    if isinstance(enum, list):
        return " | ".join(json.dumps(value, ensure_ascii=False) for value in enum)
    variants = schema.get("anyOf")
    if isinstance(variants, list):
        return " | ".join(_typescript_type(variant) for variant in variants)
    schema_type = schema.get("type")
    if schema_type == "array":
        return f"Array<{_typescript_type(schema.get('items', {}))}>"
    if schema_type in {"integer", "number"}:
        return "number"
    if schema_type == "boolean":
        return "boolean"
    if schema_type == "null":
        return "null"
    if schema_type == "object":
        return "Record<string, unknown>"
    return "string"


def render_contracts() -> str:
    schemas = app.openapi()["components"]["schemas"]
    lines = [
        "// Generated from FastAPI OpenAPI. Do not edit by hand.",
        "// Run `make generate-contracts` after changing API schemas.",
        "",
    ]
    for name in PUBLIC_SCHEMAS:
        schema = schemas[name]
        required = set(schema.get("required", []))
        lines.append(f"export interface {name} {{")
        for property_name, property_schema in schema.get("properties", {}).items():
            optional = "" if property_name in required else "?"
            lines.append(
                f"  {property_name}{optional}: {_typescript_type(property_schema)};"
            )
        lines.extend(("}", ""))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate TypeScript contracts from OpenAPI")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_contracts(), encoding="utf-8")


if __name__ == "__main__":
    main()

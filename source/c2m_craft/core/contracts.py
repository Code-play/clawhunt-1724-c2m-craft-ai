"""JSON Schema 2020-12 subset validator plus the contract registry.

Why a hand-written validator instead of a dependency: the delivery must run on a
clean machine with the Python standard library only.  The supported keyword set
is exactly what the twenty-three contracts in ``contracts/`` use, and the validator is
exercised by both the positive and the negative sample suite, so it cannot
silently degrade into a no-op.

Supported: $ref (local and cross-document, by $id urn), type (string or list),
required, properties, additionalProperties, enum, const, pattern, minimum,
maximum, exclusiveMinimum, exclusiveMaximum, minLength, maxLength, minItems,
maxItems, uniqueItems, items, minProperties, maxProperties, propertyNames,
allOf, anyOf, oneOf, not, and the custom ``x-invariants`` extension.

Not supported on purpose: remote $ref, format assertions, unevaluated* keywords.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from . import invariants as invariants_mod
from .canonical import canonical_json

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = ROOT / "contracts"
REGISTRY_FILE = CONTRACTS_DIR / "registry.json"
MAX_DEPTH = 48


@dataclass(frozen=True)
class Issue:
    path: str
    message: str
    keyword: str = "schema"
    invariant: str | None = None

    def as_dict(self) -> dict:
        data = {"path": self.path, "message": self.message, "keyword": self.keyword}
        if self.invariant:
            data["invariant"] = self.invariant
        return data


def _is_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


class SchemaStore:
    """Loads the contracts directory and validates instances against it."""

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root else ROOT
        self.dir = self.root / "contracts"
        self.schemas: dict[str, dict] = {}
        self.files: dict[str, str] = {}
        self.registry: dict = {"version": "0.0.0", "contracts": []}
        self._reload()

    # -- loading ---------------------------------------------------------
    def _reload(self) -> None:
        self.schemas.clear()
        self.files.clear()
        if self.dir.exists():
            for path in sorted(self.dir.glob("*.schema.json")):
                self.register_file(path)
        if REGISTRY_FILE.exists():
            self.registry = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        else:
            candidate = self.dir / "registry.json"
            if candidate.exists():
                self.registry = json.loads(candidate.read_text(encoding="utf-8"))

    def reload(self) -> None:
        self._reload()

    @staticmethod
    def json_load(path: Path | str) -> dict:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def register_file(self, path: Path | str) -> str:
        path = Path(path)
        schema = json.loads(path.read_text(encoding="utf-8"))
        key = str(schema.get("$id") or path.name)
        self.schemas[key] = schema
        self.files[key] = path.name
        return key

    # -- registry --------------------------------------------------------
    @property
    def contract_ids(self) -> list[str]:
        return [str(item["id"]) for item in self.registry.get("contracts", [])]

    def entry(self, contract_id: str) -> dict:
        for item in self.registry.get("contracts", []):
            if item.get("id") == contract_id:
                return item
        raise KeyError(f"contract not registered: {contract_id}")

    def urn(self, contract_id: str) -> str:
        return str(self.entry(contract_id)["urn"])

    def schema(self, contract_id: str) -> dict:
        return self.schemas[self.urn(contract_id)]

    def _key_for(self, doc: str) -> str:
        if doc in self.schemas:
            return doc
        for key, filename in self.files.items():
            if filename == doc:
                return key
        raise KeyError(f"unresolvable reference document: {doc}")

    def resolve(self, ref: str, base_key: str) -> tuple[Any, str]:
        if ref.startswith("#"):
            key, fragment = base_key, ref[1:]
        elif "#" in ref:
            doc, _, fragment = ref.partition("#")
            key = self._key_for(doc)
        else:
            key, fragment = self._key_for(ref), ""
        node: Any = self.schemas[key]
        for raw in (part for part in fragment.split("/") if part):
            part = raw.replace("~1", "/").replace("~0", "~")
            node = node[part]
        return node, key

    # -- validation ------------------------------------------------------
    def validate(
        self,
        contract_id: str,
        instance: Any,
        *,
        ctx: dict | None = None,
        semantic: bool = True,
    ) -> list[Issue]:
        urn = self.urn(contract_id)
        return self.validate_key(urn, instance, ctx=ctx, semantic=semantic)

    def validate_key(
        self,
        key: str,
        instance: Any,
        *,
        ctx: dict | None = None,
        semantic: bool = True,
    ) -> list[Issue]:
        if key not in self.schemas:
            raise KeyError(f"schema not loaded: {key}")
        issues: list[Issue] = []
        self._walk(key, self.schemas[key], instance, "$", issues, 0)
        if semantic and not issues:
            for inv_id in self.schemas[key].get("x-invariants", []) or []:
                for message in invariants_mod.run(str(inv_id), instance, ctx or {}):
                    issues.append(Issue("$", message, "x-invariants", str(inv_id)))
        return issues

    def assert_valid(self, contract_id: str, instance: Any, *, ctx: dict | None = None) -> None:
        issues = self.validate(contract_id, instance, ctx=ctx)
        if issues:
            from .errors import ContractError

            raise ContractError(contract_id, [issue.as_dict() for issue in issues])

    def validate_pointer(
        self, doc_urn: str, pointer: str, instance: Any, *, semantic: bool = False
    ) -> list[Issue]:
        """Validate against a nested schema such as ``#/$defs/order_event``."""
        node, key = self.resolve(f"{doc_urn}#{pointer}", doc_urn)
        issues: list[Issue] = []
        self._walk(key, node, instance, "$", issues, 0)
        return issues

    # -- internals -------------------------------------------------------
    def _walk(
        self,
        base_key: str,
        schema: Any,
        value: Any,
        path: str,
        issues: list[Issue],
        depth: int,
    ) -> None:
        if depth > MAX_DEPTH:
            issues.append(Issue(path, "schema recursion limit reached", "$ref"))
            return
        if schema is True or schema == {}:
            return
        if not isinstance(schema, dict):
            return

        if "$ref" in schema:
            target, target_key = self.resolve(str(schema["$ref"]), base_key)
            self._walk(target_key, target, value, path, issues, depth + 1)
            rest = {key: item for key, item in schema.items() if key != "$ref"}
            if rest:
                self._walk(base_key, rest, value, path, issues, depth + 1)
            return

        expected = schema.get("type")
        if expected is not None:
            options = [expected] if isinstance(expected, str) else list(expected)
            if not any(_is_type(value, option) for option in options):
                wanted = " or ".join(options)
                issues.append(Issue(path, f"expected {wanted}, got {_type_name(value)}", "type"))
                return

        if "const" in schema and value != schema["const"]:
            issues.append(Issue(path, f"must equal {schema['const']!r}", "const"))
        if "enum" in schema and value not in schema["enum"]:
            issues.append(
                Issue(path, f"must be one of {sorted(schema['enum'])!r}, got {value!r}", "enum")
            )

        if isinstance(value, str):
            self._walk_string(schema, value, path, issues)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            self._walk_number(schema, value, path, issues)
        if isinstance(value, list):
            self._walk_array(base_key, schema, value, path, issues, depth)
        if isinstance(value, dict):
            self._walk_object(base_key, schema, value, path, issues, depth)

        for sub in schema.get("allOf", []) or []:
            self._walk(base_key, sub, value, path, issues, depth + 1)

        if schema.get("anyOf"):
            if not any(self._matches(base_key, sub, value, depth) for sub in schema["anyOf"]):
                issues.append(Issue(path, "does not match any allowed shape", "anyOf"))

        if schema.get("oneOf"):
            matched = sum(
                1 for sub in schema["oneOf"] if self._matches(base_key, sub, value, depth)
            )
            if matched != 1:
                issues.append(
                    Issue(path, f"must match exactly one shape, matched {matched}", "oneOf")
                )

        if "not" in schema and self._matches(base_key, schema["not"], value, depth):
            issues.append(Issue(path, "matches a forbidden shape", "not"))

    def _matches(self, base_key: str, schema: Any, value: Any, depth: int) -> bool:
        probe: list[Issue] = []
        self._walk(base_key, schema, value, "$", probe, depth + 1)
        return not probe

    def _walk_string(self, schema: dict, value: str, path: str, issues: list[Issue]) -> None:
        if "minLength" in schema and len(value) < int(schema["minLength"]):
            issues.append(Issue(path, f"length {len(value)} < {schema['minLength']}", "minLength"))
        if "maxLength" in schema and len(value) > int(schema["maxLength"]):
            issues.append(Issue(path, f"length {len(value)} > {schema['maxLength']}", "maxLength"))
        if "pattern" in schema and not re.search(str(schema["pattern"]), value):
            issues.append(
                Issue(path, f"does not match pattern {schema['pattern']}", "pattern")
            )

    def _walk_number(self, schema: dict, value: Any, path: str, issues: list[Issue]) -> None:
        if "minimum" in schema and value < schema["minimum"]:
            issues.append(Issue(path, f"{value} < minimum {schema['minimum']}", "minimum"))
        if "maximum" in schema and value > schema["maximum"]:
            issues.append(Issue(path, f"{value} > maximum {schema['maximum']}", "maximum"))
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            issues.append(
                Issue(path, f"{value} <= exclusiveMinimum {schema['exclusiveMinimum']}",
                      "exclusiveMinimum")
            )
        if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
            issues.append(
                Issue(path, f"{value} >= exclusiveMaximum {schema['exclusiveMaximum']}",
                      "exclusiveMaximum")
            )

    def _walk_array(
        self,
        base_key: str,
        schema: dict,
        value: list,
        path: str,
        issues: list[Issue],
        depth: int,
    ) -> None:
        if "minItems" in schema and len(value) < int(schema["minItems"]):
            issues.append(Issue(path, f"{len(value)} item(s) < minItems {schema['minItems']}",
                                "minItems"))
        if "maxItems" in schema and len(value) > int(schema["maxItems"]):
            issues.append(Issue(path, f"{len(value)} item(s) > maxItems {schema['maxItems']}",
                                "maxItems"))
        if schema.get("uniqueItems"):
            seen: set[str] = set()
            for index, item in enumerate(value):
                key = canonical_json(item)
                if key in seen:
                    issues.append(Issue(f"{path}[{index}]", "duplicate item", "uniqueItems"))
                seen.add(key)
        items = schema.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(value):
                self._walk(base_key, items, item, f"{path}[{index}]", issues, depth + 1)
        elif isinstance(items, list):
            for index, item in enumerate(value[: len(items)]):
                self._walk(base_key, items[index], item, f"{path}[{index}]", issues, depth + 1)

    def _walk_object(
        self,
        base_key: str,
        schema: dict,
        value: dict,
        path: str,
        issues: list[Issue],
        depth: int,
    ) -> None:
        properties = schema.get("properties") or {}
        for name in schema.get("required", []) or []:
            if name not in value:
                issues.append(Issue(path, f"missing required property '{name}'", "required"))
        if "minProperties" in schema and len(value) < int(schema["minProperties"]):
            issues.append(Issue(path, f"{len(value)} < minProperties", "minProperties"))
        if "maxProperties" in schema and len(value) > int(schema["maxProperties"]):
            issues.append(Issue(path, f"{len(value)} > maxProperties", "maxProperties"))

        additional = schema.get("additionalProperties", True)
        for name, item in value.items():
            child = f"{path}.{name}"
            if name in properties:
                self._walk(base_key, properties[name], item, child, issues, depth + 1)
            elif additional is False:
                issues.append(Issue(path, f"unexpected property '{name}'", "additionalProperties"))
            elif isinstance(additional, dict):
                self._walk(base_key, additional, item, child, issues, depth + 1)

        names_schema = schema.get("propertyNames")
        if isinstance(names_schema, dict):
            for name in value:
                if not self._matches(base_key, names_schema, name, depth):
                    issues.append(Issue(path, f"invalid property name '{name}'", "propertyNames"))


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def format_issues(issues: Iterable[Issue]) -> str:
    return "; ".join(f"{issue.path}: {issue.message}" for issue in issues)

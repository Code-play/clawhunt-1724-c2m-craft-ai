"""Canonical JSON and hashing.

The ledger, the determinism manifest and the assessment reproducibility record
all depend on one canonical serialisation: sorted keys, no insignificant
whitespace, UTF-8 kept as-is, newline free.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

ENCODING = "utf-8"


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode(ENCODING)).hexdigest()


def content_hash(value: Any) -> str:
    return sha256_hex(canonical_json(value))


def short_hash(value: Any, length: int = 12) -> str:
    return content_hash(value)[:length]


def file_sha256(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dump_json(path, value: Any) -> None:
    """Write canonical-pretty JSON with LF endings (byte-stable across runs)."""
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=1, allow_nan=False)
    with open(path, "w", encoding=ENCODING, newline="\n") as handle:
        handle.write(text)
        handle.write("\n")


def dump_jsonl(path, rows) -> None:
    with open(path, "w", encoding=ENCODING, newline="\n") as handle:
        for row in rows:
            handle.write(canonical_json(row))
            handle.write("\n")


def append_jsonl(path, row) -> None:
    with open(path, "a", encoding=ENCODING, newline="\n") as handle:
        handle.write(canonical_json(row))
        handle.write("\n")


def read_json(path):
    with open(path, "r", encoding=ENCODING) as handle:
        return json.load(handle)


def read_jsonl(path) -> list:
    rows = []
    with open(path, "r", encoding=ENCODING) as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_text(path, text: str) -> None:
    with open(path, "w", encoding=ENCODING, newline="\n") as handle:
        handle.write(text)
        if not text.endswith("\n"):
            handle.write("\n")

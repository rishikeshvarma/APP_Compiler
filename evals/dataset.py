"""Versioned dataset loader.

File format: JSONL. First line is a header ``{"_schema_version": 1, "_name": ...}``.
Every following line is a `Case`. A version mismatch or a bad row raises
`DatasetSchemaError` with the line number, so a dataset change can never silently
change what an eval measures.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from .models import DATASET_SCHEMA_VERSION, Case


class DatasetSchemaError(ValueError):
    pass


def load_dataset(path: str | Path) -> list[Case]:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise DatasetSchemaError(f"{path}: cannot read dataset ({e.strerror})") from e
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise DatasetSchemaError(f"{path}: empty dataset")
    try:
        header = json.loads(lines[0])
    except json.JSONDecodeError as e:
        raise DatasetSchemaError(f"{path}:1: header is not valid JSON ({e})") from e
    if "_schema_version" not in header:
        raise DatasetSchemaError(f"{path}:1: missing '_schema_version' header")
    if header["_schema_version"] != DATASET_SCHEMA_VERSION:
        raise DatasetSchemaError(
            f"{path}: dataset schema v{header['_schema_version']} but harness expects "
            f"v{DATASET_SCHEMA_VERSION}. Migrate the dataset before running evals."
        )
    cases: list[Case] = []
    seen: set[str] = set()
    for i, raw in enumerate(lines[1:], start=2):
        try:
            case = Case.model_validate_json(raw)
        except (ValidationError, json.JSONDecodeError) as e:
            raise DatasetSchemaError(f"{path}:{i}: invalid case ({e})") from e
        if case.id in seen:
            raise DatasetSchemaError(f"{path}:{i}: duplicate case id {case.id!r}")
        seen.add(case.id)
        cases.append(case)
    return cases

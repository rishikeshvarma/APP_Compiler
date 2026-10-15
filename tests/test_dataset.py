import json

import pytest

from evals.dataset import DatasetSchemaError, load_dataset

HEADER = json.dumps({"_schema_version": 1})
ROW = json.dumps({"id": "a", "prompt": "p"})


def write(tmp_path, *lines):
    p = tmp_path / "d.jsonl"
    p.write_text("\n".join(lines) + "\n")
    return p


def test_shipped_dataset_loads_and_has_unique_ids():
    cases = load_dataset("evals/datasets/cases.v1.jsonl")
    assert len(cases) == 13 and len({c.id for c in cases}) == 13
    assert any(c.id == "healthcare-hipaa" and c.expectations.requires_audit_log for c in cases)


def test_version_mismatch_fails_loudly(tmp_path):
    with pytest.raises(DatasetSchemaError, match="expects v1"):
        load_dataset(write(tmp_path, json.dumps({"_schema_version": 2}), ROW))


def test_missing_header_fails(tmp_path):
    with pytest.raises(DatasetSchemaError, match="_schema_version"):
        load_dataset(write(tmp_path, ROW))


def test_bad_row_reports_line_number(tmp_path):
    with pytest.raises(DatasetSchemaError, match=r":3:"):
        load_dataset(write(tmp_path, HEADER, ROW, json.dumps({"id": "b"})))  # missing prompt


def test_duplicate_ids_rejected(tmp_path):
    with pytest.raises(DatasetSchemaError, match="duplicate"):
        load_dataset(write(tmp_path, HEADER, ROW, ROW))

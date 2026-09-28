import json
from pathlib import Path


def _read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_example_preservation_record_shape():
    row = _read_jsonl(Path("examples/minimal-package/preservation_records.jsonl"))[0]
    assert row["record_type"] == "preservation_record"
    assert row["storage"]["media_type"] == "application/json"


def test_example_preservation_bundle_shape():
    row = _read_jsonl(Path("examples/minimal-package/preservation_bundles.jsonl"))[0]
    assert row["record_type"] == "preservation_bundle"
    assert row["bundle_items"][1]["media_type"] == "text/html"

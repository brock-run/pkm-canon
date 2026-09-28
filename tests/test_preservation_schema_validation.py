from pkmcanon.schema_validation import default_schema_store


def test_preservation_records_jsonl_validate_against_schema():
    store = default_schema_store()
    store.validate_jsonl_file("examples/minimal-package/preservation_records.jsonl", "preservation-record")


def test_preservation_bundles_jsonl_validate_against_schema():
    store = default_schema_store()
    store.validate_jsonl_file("examples/minimal-package/preservation_bundles.jsonl", "preservation-bundle")

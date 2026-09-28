from pkmcanon.schema_validation import default_schema_store


def test_schema_store_short_name_resolution():
    store = default_schema_store()
    assert store.resolve_short_name("documents").name == "documents.schema.json"
    assert store.resolve_short_name("preservation-record").name == "preservation-record.schema.json"

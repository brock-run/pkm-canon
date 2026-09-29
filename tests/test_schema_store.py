from pkmcanon.schema_validation import default_schema_store


def test_schema_store_short_name_resolution():
    store = default_schema_store()
    assert store.resolve_short_name("documents").name == "documents.schema.json"
    assert store.resolve_short_name("preservation-record").name == "preservation-record.schema.json"


def test_default_schema_store_does_not_depend_on_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = default_schema_store()
    store.validate_instance_with_short_name(
        {"document_id": "doc", "source_version_id": "source", "kind": "page", "title": "Title"},
        "documents",
    )
    assert store.resolve_short_name("documents").is_file()

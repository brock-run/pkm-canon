from pkmcanon.schema_validation import default_schema_store


def test_documents_jsonl_validates():
    store = default_schema_store()
    store.validate_jsonl_file("examples/minimal-package/documents.jsonl", "documents")


def test_nodes_jsonl_validates():
    store = default_schema_store()
    store.validate_jsonl_file("examples/minimal-package/nodes.jsonl", "nodes")


def test_spans_jsonl_validates():
    store = default_schema_store()
    store.validate_jsonl_file("examples/minimal-package/spans.jsonl", "spans")


def test_relations_jsonl_validates():
    store = default_schema_store()
    store.validate_jsonl_file("examples/minimal-package/relations.jsonl", "relations")


def test_attributes_jsonl_validates():
    store = default_schema_store()
    store.validate_jsonl_file("examples/minimal-package/attributes.jsonl", "attributes")

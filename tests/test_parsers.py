import hashlib
import json

import pytest

from pkmcanon.adapters import stable_id
from pkmcanon.models import Document, Node, PreservationRecord, Relation, Span
from pkmcanon.parsers.markdown import MarkdownAdapter
from pkmcanon.parsers.roam import RoamParser


def parse_roam(pages):
    return RoamParser().parse(
        json.dumps(pages).encode(), source_scope="graph",
        source_version_id="version", native_id="export.json",
    )


def parse_markdown(data):
    return MarkdownAdapter().parse(
        data, source_scope="repo", source_version_id="version", native_id="docs/page.md",
    )


@pytest.mark.parametrize("data,code", [
    (b"not json", "INVALID_ROAM_JSON"),
    (b"\xff", "INVALID_ROAM_JSON"),
    (b"{}", "INVALID_ROAM_ROOT"),
    (b"[null]", "INVALID_ROAM_ROOT"),
    (b'[{"children": {}}]', "INVALID_ROAM_CHILDREN"),
    (b'[{"children": [null]}]', "INVALID_ROAM_CHILDREN"),
    (b'[{"children": [{"children": false}]}]', "INVALID_ROAM_CHILDREN"),
])
def test_roam_rejects_invalid_source_shapes(data, code):
    with pytest.raises(ValueError, match=f"^{code}$"):
        RoamParser().parse(data, source_scope="graph", source_version_id="v", native_id="x")


def test_roam_sorts_siblings_but_retains_source_paths_and_parents():
    result = parse_roam([{"uid": "P", "title": "Page", "children": [
        {"uid": "late", "order": 9, "string": "Late"},
        {"uid": "first", "order": -1, "string": "First", "children": [
            {"uid": "child", "string": "Child"},
        ]},
        {"uid": "tied", "order": -1, "string": "Tied"},
    ]}])
    nodes = {row.plain_text: row for row in result.records if isinstance(row, Node)}
    assert [nodes[name].position for name in ("First", "Tied", "Late")] == [0, 1, 2]
    assert nodes["Child"].parent_node_id == nodes["First"].node_id
    assert nodes["First"].facets["pkm/source-roam"].model_extra["json_pointer"] == "/0/children/1"
    assert result.source_object_count == 5
    assert result.diagnostics == []


def test_roam_embeds_and_tags_do_not_also_create_page_or_block_refs():
    result = parse_roam([
        {"uid": "P", "title": "Page", "children": [
            {"uid": "B", "string": "{{embed: [[Target]]}} {{embed: ((T))}} #[[Target]] #work [[Target]] ((T))"},
        ]},
        {"uid": "Q", "title": "Target", "children": [{"uid": "T", "string": "Evidence"}]},
    ])
    relations = [row for row in result.records if isinstance(row, Relation)]
    assert sorted(row.relation_type for row in relations) == ["block_ref", "embed", "embed", "page_ref", "tag", "tag"]
    assert {row.target_id for row in relations if row.target_kind == "tag"} == {"tag:Target", "tag:work"}
    assert result.diagnostics == []


def test_roam_ambiguous_and_missing_references_are_preserved_without_guessing():
    block = {"uid": "B", "string": "[[Duplicate]] ((missing))"}
    result = parse_roam([
        {"uid": "P", "title": "Duplicate", "children": [block]},
        {"uid": "Q", "title": "Duplicate"},
    ])
    assert not any(isinstance(row, Relation) for row in result.records)
    assert {row.code for row in result.diagnostics} == {"UNRESOLVED_PAGE_REF", "UNRESOLVED_BLOCK_REF"}
    preserved = [row for row in result.records if isinstance(row, PreservationRecord)]
    assert len(preserved) == 1
    assert json.loads(preserved[0].storage.inline_utf8) == block
    assert all(row.preservation_id == preserved[0].id for row in result.diagnostics)


def test_roam_duplicate_uids_have_distinct_repeatable_ids_and_ambiguous_refs():
    source = [{"uid": "P", "title": "Page", "children": [
        {"uid": "B", "string": "First"}, {"uid": "B", "string": "Second"},
        {"uid": "R", "string": "((B))"},
    ]}]
    result = parse_roam(source)
    nodes = [row for row in result.records if isinstance(row, Node)]
    assert len({row.node_id for row in nodes}) == 3
    assert result == parse_roam(source)
    assert {row.code for row in result.diagnostics} == {"DUPLICATE_UID", "UNRESOLVED_BLOCK_REF"}
    assert not any(isinstance(row, Relation) for row in result.records)


def test_markdown_keeps_unicode_text_line_ranges_and_external_links():
    result = parse_markdown("# Café\r\n\r\nOwner: Équipe\r\nSee [guide](../guide.md).\r\n".encode())
    document = next(row for row in result.records if isinstance(row, Document))
    nodes = [row for row in result.records if isinstance(row, Node)]
    assert document.title == "Café"
    assert [row.plain_text for row in nodes] == ["# Café", "Owner: Équipe\nSee [guide](../guide.md)."]
    assert [(row.facets["pkm/source-markdown"].model_extra["line_start"], row.facets["pkm/source-markdown"].model_extra["line_end"]) for row in nodes] == [(1, 1), (3, 4)]
    spans = [row for row in result.records if isinstance(row, Span)]
    assert [(row.start, row.end, row.text) for row in spans] == [(0, len(row.plain_text), row.plain_text) for row in nodes]
    relation = next(row for row in result.records if isinstance(row, Relation))
    assert (relation.target_kind, relation.target_id, relation.source_representation) == ("external", "../guide.md", "[guide](../guide.md)")
    assert result.source_object_count == 3


@pytest.mark.parametrize("text,code", [
    ("```\nprint('café')\n```", "CODE_STRUCTURE_NOT_NORMALIZED"),
    ("~~~\nexample\n~~~", "CODE_STRUCTURE_NOT_NORMALIZED"),
    ("| A | B |\n| - | - |", "TABLE_STRUCTURE_NOT_NORMALIZED"),
    ("---\ntitle: Café\n---", "FRONTMATTER_NOT_NORMALIZED"),
    ("<div>Café</div>\n\n<div>Again</div>", "HTML_NOT_NORMALIZED"),
])
def test_markdown_partial_structures_preserve_exact_bytes_once(text, code):
    data = text.encode()
    result = parse_markdown(data)
    preserved = [row for row in result.records if isinstance(row, PreservationRecord)]
    assert len(preserved) == 1
    assert preserved[0].storage.inline_utf8 == text
    assert preserved[0].storage.byte_length == len(data)
    assert preserved[0].storage.hashes[0].digest == hashlib.sha256(data).hexdigest()
    assert [row.code for row in result.diagnostics] == [code]
    assert result.diagnostics[0].preservation_id == preserved[0].id


@pytest.mark.parametrize("data,count", [(b"", 1), (b"\n \n", 1), (b"No heading", 2)])
def test_markdown_without_heading_uses_source_path(data, count):
    result = parse_markdown(data)
    assert next(row for row in result.records if isinstance(row, Document)).title == "docs/page.md"
    assert result.source_object_count == count


def test_markdown_rejects_non_utf8():
    with pytest.raises(ValueError, match="INVALID_MARKDOWN_ENCODING"):
        parse_markdown(b"\xff")


def test_stable_identity_preserves_component_boundaries_and_unicode():
    assert stable_id("node", "café", "a:b") == stable_id("node", "café", "a:b")
    assert stable_id("node", "a:b", "c") != stable_id("node", "a", "b:c")
    assert stable_id("node", "café") != stable_id("node", "cafe")
    assert stable_id("node", "a", "b") != stable_id("node", "b", "a")


@pytest.mark.parametrize("timestamp,expected", [
    (0, "1970-01-01T00:00:00+00:00"),
    (-1000, "1969-12-31T23:59:59+00:00"),
    (1500, "1970-01-01T00:00:01.500000+00:00"),
])
def test_roam_page_and_block_timestamps_use_epoch_milliseconds(timestamp, expected):
    result = parse_roam([{
        "uid": "P", "title": "Page", "create-time": timestamp, "edit-time": timestamp,
        "children": [{"uid": "B", "string": "Text", "create-time": timestamp, "edit-time": timestamp}],
    }])
    document = next(row for row in result.records if isinstance(row, Document))
    node = next(row for row in result.records if isinstance(row, Node))
    assert document.created_at == document.updated_at == expected
    details = node.facets["pkm/source-roam"].model_extra
    assert details["created_at"] == details["updated_at"] == expected
    assert result.diagnostics == []


def test_roam_uid_identity_survives_reordering_and_content_edits():
    original = parse_roam([
        {"uid": "P", "title": "Page", "children": [{"uid": "B", "string": "Before"}]},
        {"uid": "Q", "title": "Other"},
    ])
    edited = parse_roam([
        {"uid": "Q", "title": "Renamed"},
        {"uid": "P", "title": "Page", "children": [{"uid": "B", "string": "After"}]},
    ])
    def identities(result, record_type, id_field):
        return {
            row.facets["pkm/source-roam"].model_extra["roam_uid"]: getattr(row, id_field)
            for row in result.records if isinstance(row, record_type)
        }
    assert identities(original, Document, "document_id") == identities(edited, Document, "document_id")
    assert identities(original, Node, "node_id") == identities(edited, Node, "node_id")
    assert next(row for row in edited.records if isinstance(row, Node)).plain_text == "After"


@pytest.mark.parametrize("adapter,data,native_id", [
    (RoamParser(), b'[{"uid":"P","title":"Page","children":[{"uid":"B","string":"Text"}]}]', "export.json"),
    (MarkdownAdapter(), b"# Page\n\nText", "page.md"),
])
def test_source_scope_separates_document_and_node_identities(adapter, data, native_id):
    results = [adapter.parse(data, source_scope=scope, source_version_id="version", native_id=native_id) for scope in ("one", "two")]
    for record_type, id_field in ((Document, "document_id"), (Node, "node_id")):
        ids = [{getattr(row, id_field) for row in result.records if isinstance(row, record_type)} for result in results]
        assert ids[0] and ids[1]
        assert ids[0].isdisjoint(ids[1])


def test_markdown_adjacent_headings_split_paragraphs_without_blank_lines():
    result = parse_markdown(b"Intro\n# First\n## Second\nBody\nlast line")
    nodes = [row for row in result.records if isinstance(row, Node)]
    assert [(row.node_type, row.plain_text, row.position) for row in nodes] == [
        ("block", "Intro", 0), ("heading", "# First", 1),
        ("heading", "## Second", 2), ("block", "Body\nlast line", 3),
    ]
    assert [row.facets["pkm/source-markdown"].model_extra["line_start"] for row in nodes] == [1, 2, 3, 4]
    assert next(row for row in result.records if isinstance(row, Document)).title == "First"


def test_roam_parse_file_uses_explicit_graph_or_file_stem(tmp_path):
    path = tmp_path / "graph.json"
    path.write_bytes(b'[{"uid":"P","title":"Page"}]')
    for configured, expected_scope in ((None, "graph"), ("custom", "custom")):
        parser = RoamParser(configured)
        assert parser.parse_file(path, source_version_id="snapshot") == parser.parse(
            path.read_bytes(), source_scope=expected_scope,
            source_version_id="snapshot", native_id="graph.json",
        )

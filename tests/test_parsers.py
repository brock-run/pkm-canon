import hashlib
import json

import pytest

from pkmcanon.adapters import stable_id
from pkmcanon.models import Document, Node, PreservationRecord, Relation, Span
from pkmcanon.parsers.markdown import MarkdownAdapter
from pkmcanon.parsers.roam import RoamParser


def parse_roam(pages):
    """Parse JSON-encoded pages with fixed graph and source-version identifiers."""
    return RoamParser().parse(
        json.dumps(pages).encode(), source_scope="graph",
        source_version_id="version", native_id="export.json",
    )


def parse_markdown(data):
    """Parse Markdown bytes with a fixed repository path and source version."""
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
    """Verify malformed Roam exports raise the expected stable error codes."""
    with pytest.raises(ValueError, match=f"^{code}$"):
        RoamParser().parse(data, source_scope="graph", source_version_id="v", native_id="x")


def test_roam_sorts_siblings_but_retains_source_paths_and_parents():
    """Verify sibling ordering preserves parent links and original JSON pointers."""
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
    """Verify embeds and tags produce distinct relations without duplicate references."""
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
    """Verify unresolved references retain their raw block and linked diagnostics."""
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
    """Verify duplicate UIDs yield stable distinct nodes and unresolved references."""
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


def test_roam_maps_actor_reference_and_presentation_fields_with_defined_semantics():
    result = parse_roam([
        {"uid": "P", "title": "Page", ":create/user": {":user/uid": "creator"},
         "refs": [{"uid": "B"}], ":block/refs": [{":block/uid": "B"}],
         "children": [{"uid": "B", "string": "Heading", "heading": 2,
                       ":edit/user": {":user/uid": "editor"}, "text-align": "left",
                       ":children/view-type": ":numbered", ":block/view-type": ":outline",
                       "refs": [{"uid": "P"}], ":block/refs": [{":block/uid": "P"}]}]},
    ])
    assert result.diagnostics == []
    document = next(row for row in result.records if isinstance(row, Document))
    node = next(row for row in result.records if isinstance(row, Node))
    assert document.facets["pkm/source-roam"].model_extra["created_by_uid"] == "creator"
    facet = node.facets["pkm/source-roam"].model_extra
    assert node.semantic_kind == "heading"
    assert (facet["heading_level"], facet["edited_by_uid"], facet["text_align"]) == (2, "editor", "left")
    assert (facet["children_view_type"], facet["block_view_type"]) == (":numbered", ":outline")
    native = [row for row in result.records if isinstance(row, Relation) and row.relation_type == "native_ref"]
    assert {(row.source_id, row.target_id) for row in native} == {
        (document.document_id, node.node_id), (node.node_id, document.document_id),
    }


def test_roam_rejects_conflicting_or_invalid_interpreted_fields_with_raw_preservation():
    raw = {"uid": "B", "string": "Text", ":create/user": {":user/uid": ""},
           "refs": [{"uid": "P"}], ":block/refs": [{":block/uid": "other"}],
           "heading": 7, "text-align": "diagonal", ":children/view-type": ":grid"}
    result = parse_roam([{"uid": "P", "title": "Page", "children": [raw]}])
    assert {row.code for row in result.diagnostics} == {
        "INVALID_CREATE_USER", "CONFLICTING_NATIVE_REFS", "INVALID_HEADING",
        "INVALID_TEXT_ALIGN", "INVALID_CHILDREN_VIEW_TYPE",
    }
    preserved = [row for row in result.records if isinstance(row, PreservationRecord)]
    assert len(preserved) == 1
    assert json.loads(preserved[0].storage.inline_utf8) == raw
    assert all(row.preservation_id == preserved[0].id for row in result.diagnostics)
    assert not any(isinstance(row, Relation) for row in result.records)


def test_roam_unresolved_native_reference_is_diagnosed_and_preserved():
    result = parse_roam([{"uid": "P", "title": "Page", "refs": [{"uid": "missing"}]}])
    assert [row.code for row in result.diagnostics] == ["UNRESOLVED_NATIVE_REF"]
    assert result.diagnostics[0].outcome == "unresolved_reference"
    assert result.diagnostics[0].preservation_id is not None


def test_markdown_keeps_unicode_text_line_ranges_and_external_links():
    """Verify Unicode text, source line ranges, spans, and external links survive parsing."""
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
    """Verify unsupported structures retain one exact payload with a matching diagnostic."""
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
    """Verify heading-free input uses the source path as its title and counts objects."""
    result = parse_markdown(data)
    assert next(row for row in result.records if isinstance(row, Document)).title == "docs/page.md"
    assert result.source_object_count == count


def test_markdown_rejects_non_utf8():
    """Verify invalid UTF-8 raises the Markdown encoding error."""
    with pytest.raises(ValueError, match="INVALID_MARKDOWN_ENCODING"):
        parse_markdown(b"\xff")


def test_stable_identity_preserves_component_boundaries_and_unicode():
    """Verify stable IDs distinguish component order, boundaries, and Unicode text."""
    assert stable_id("node", "café", "a:b") == stable_id("node", "café", "a:b")
    assert stable_id("node", "a:b", "c") != stable_id("node", "a", "b:c")
    assert stable_id("node", "café") != stable_id("node", "cafe")
    assert stable_id("node", "a", "b") != stable_id("node", "b", "a")

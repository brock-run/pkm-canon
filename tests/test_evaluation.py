import json
from pathlib import Path

import pytest

from pkmcanon.evaluation import (
    evaluate_retrieval,
    propose_retrieval_changes,
    read_evaluation_cases,
    write_evaluation_results,
)
from pkmcanon.index import build_index
from pkmcanon.models import EvaluationCase
from pkmcanon.package import PackageValidationError
from pkmcanon.parsers.markdown import MarkdownAdapter
from pkmcanon.products import validate_proposal
from pkmcanon.writer import build_package


def test_retrieval_failure_becomes_grounded_review_proposal(tmp_path: Path) -> None:
    """Verify missed gold evidence yields a valid proposal and empty results permit abstention."""
    source = tmp_path / "service.md"
    source.write_text("# Service\n\nOwner: Platform Team\n")
    package = build_package(MarkdownAdapter(), source, tmp_path / "package", source_scope="platform")
    index = build_index(package)
    owner_node = next(node for node in package.nodes if "Owner:" in node.plain_text)
    cases = [
        EvaluationCase(
            case_id="owner-synonym", source_package_id=package.manifest.package_id,
            query="stewardship", task_type="ownership", principal_id="local-operator",
            expected_node_ids=[owner_node.node_id], expected_coverage="complete",
        ),
        EvaluationCase(
            case_id="abstain", source_package_id=package.manifest.package_id,
            query="nonexistent", task_type="lookup", principal_id="local-operator",
            expected_node_ids=[], expected_coverage="none",
        ),
    ]
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text("".join(json.dumps(case.model_dump(mode="json")) + "\n" for case in cases))
    loaded = read_evaluation_cases(cases_path)
    results = evaluate_retrieval(package, index, loaded)
    assert not results[0].passed and results[0].missing_node_ids == [owner_node.node_id]
    assert results[1].passed
    write_evaluation_results(tmp_path / "results.jsonl", results)
    proposals = propose_retrieval_changes(package, loaded, results)
    assert len(proposals) == 1
    validate_proposal(package, proposals[0])
    assert proposals[0].evidence[0].node_id == owner_node.node_id
    assert proposals[0].payload["evaluation_case_id"] == "owner-synonym"
    with pytest.raises(PackageValidationError, match="EVALUATION_RESULTS_EXIST"):
        write_evaluation_results(tmp_path / "results.jsonl", results[1:])


def test_evaluation_records_coverage_mismatch_without_missing_evidence(tmp_path: Path) -> None:
    source = tmp_path / "service.md"
    source.write_text("# Service\n\nOwner: Platform Team\n")
    package = build_package(MarkdownAdapter(), source, tmp_path / "package", source_scope="platform")
    owner_node = next(node for node in package.nodes if "Owner:" in node.plain_text)
    case = EvaluationCase(
        case_id="coverage-only", source_package_id=package.manifest.package_id,
        query="owner", task_type="ownership", principal_id="local-operator",
        expected_node_ids=[owner_node.node_id], expected_coverage="partial",
    )
    result = evaluate_retrieval(package, build_index(package), [case])[0]
    assert result.missing_node_ids == []
    assert result.coverage == "complete"
    assert not result.coverage_matched
    assert not result.passed


def test_evaluation_cannot_label_inaccessible_evidence_as_expected(tmp_path: Path) -> None:
    """Verify gold labels cannot require evidence inaccessible to the evaluation principal."""
    source = tmp_path / "service.md"
    source.write_text("# Service\n\nOwner: Platform Team\n")
    package = build_package(MarkdownAdapter(), source, tmp_path / "package", source_scope="platform")
    owner_node = next(node for node in package.nodes if "Owner:" in node.plain_text)
    case = EvaluationCase(
        case_id="inaccessible", source_package_id=package.manifest.package_id,
        query="owner", task_type="ownership", principal_id="stranger",
        expected_node_ids=[owner_node.node_id], expected_coverage="complete",
    )
    with pytest.raises(PackageValidationError, match="EVALUATION_ACCESS_DENIED"):
        evaluate_retrieval(package, build_index(package), [case])


@pytest.fixture
def evaluation_context(tmp_path):
    source = tmp_path / "page.md"
    source.write_text("Owner: Team\n\nOwner: Other\n")
    package = build_package(MarkdownAdapter(), source, tmp_path / "package", source_scope="repo")
    case = EvaluationCase(
        case_id="owners", source_package_id=package.manifest.package_id,
        query="owner", task_type="ownership", principal_id="local-operator",
        expected_node_ids=sorted(row.node_id for row in package.nodes), expected_coverage="complete",
    )
    return package, build_index(package), case


def test_partial_recall_proposes_only_missing_evidence(evaluation_context):
    package, index, case = evaluation_context
    result = evaluate_retrieval(package, index, [case], limit=1)[0]
    assert result.recall == 0.5
    assert not result.passed
    assert result.coverage == "complete"
    assert result.retrieved_node_ids == case.expected_node_ids[:1]
    assert result.missing_node_ids == case.expected_node_ids[1:]
    proposals = propose_retrieval_changes(package, [case], [result])
    assert len(proposals) == 1
    assert proposals[0].confidence == 0.5
    assert [item.node_id for item in proposals[0].evidence] == result.missing_node_ids
    validate_proposal(package, proposals[0])


@pytest.mark.parametrize("query,expected,coverage,recall,passed", [
    ("owner", True, "complete", 1.0, True),
    ("owner", True, "partial", 1.0, False),
    ("owner", False, "complete", 0.0, False),
    ("absent", False, "none", 1.0, True),
])
def test_evaluation_requires_both_expected_evidence_and_coverage(evaluation_context, query, expected, coverage, recall, passed):
    package, index, case = evaluation_context
    case = case.model_copy(update={"query": query, "expected_node_ids": case.expected_node_ids if expected else [], "expected_coverage": coverage})
    result = evaluate_retrieval(package, index, [case])[0]
    assert result.recall == recall
    assert result.passed is passed
    assert propose_retrieval_changes(package, [case], [result]) == []


@pytest.mark.parametrize("change,code", [
    ({"source_package_id": "other"}, "EVALUATION_PACKAGE_MISMATCH"),
    ({"expected_node_ids": ["absent"]}, "EVALUATION_DANGLING_NODE"),
])
def test_invalid_evaluation_cases_fail_before_scoring(evaluation_context, change, code):
    package, index, case = evaluation_context
    with pytest.raises(PackageValidationError, match=code):
        evaluate_retrieval(package, index, [case.model_copy(update=change)])


def test_duplicate_expected_nodes_and_foreign_index_are_rejected(evaluation_context):
    package, index, case = evaluation_context
    duplicate = case.model_copy(update={"expected_node_ids": [case.expected_node_ids[0]] * 2})
    with pytest.raises(PackageValidationError, match="DUPLICATE_EXPECTED_NODE"):
        evaluate_retrieval(package, index, [duplicate])
    with pytest.raises(PackageValidationError, match="INDEX_PACKAGE_MISMATCH"):
        evaluate_retrieval(package, index.model_copy(update={"source_package_id": "other"}), [case])


def test_case_reader_ignores_blanks_but_rejects_duplicate_ids_and_bad_lines(evaluation_context, tmp_path):
    _, _, case = evaluation_context
    path = tmp_path / "cases.jsonl"
    row = case.model_dump_json()
    path.write_text("\n" + row + "\n\n")
    assert read_evaluation_cases(path) == [case]
    path.write_text(row + "\n" + row)
    with pytest.raises(PackageValidationError, match="DUPLICATE_EVALUATION_CASE"):
        read_evaluation_cases(path)
    path.write_text("\n{}\n")
    with pytest.raises(PackageValidationError, match="EVALUATION_CASE_INVALID: line 2"):
        read_evaluation_cases(path)

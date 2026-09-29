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

"""Gold-case retrieval evaluation and evidence-backed improvement proposals."""

from __future__ import annotations

import json
from pathlib import Path

from .adapters import stable_id
from .evidence import can_access, evidence_for_node
from .index import search_index
from .models import (
    EvaluationCase,
    EvaluationResult,
    IndexProjection,
    Proposal,
    RetrievalChange,
)
from .package import CanonicalPackage, PackageValidationError
from .schema_validation import default_schema_store

CHANGE_SCHEMA = "urn:pkm-rosetta:schema:v1:knowledge:retrieval-change"


def read_evaluation_cases(path: Path) -> list[EvaluationCase]:
    cases = []
    ids = set()
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            default_schema_store().validate_instance_with_short_name(raw, "evaluation-case")
            case = EvaluationCase.model_validate(raw)
        except Exception as exc:
            raise PackageValidationError("EVALUATION_CASE_INVALID", f"line {number}: {exc}") from exc
        if case.case_id in ids:
            raise PackageValidationError("DUPLICATE_EVALUATION_CASE", case.case_id)
        ids.add(case.case_id)
        cases.append(case)
    return cases


def evaluate_retrieval(
    package: CanonicalPackage, index: IndexProjection, cases: list[EvaluationCase],
    *, limit: int = 8,
) -> list[EvaluationResult]:
    if index.source_package_id != package.manifest.package_id:
        raise PackageValidationError("INDEX_PACKAGE_MISMATCH", index.index_id)
    nodes = {item.node_id: item for item in package.nodes}
    docs = {item.document_id: item for item in package.documents}
    sources = {item.source_version_id: item for item in package.manifest.source_versions}
    results = []
    for case in cases:
        if case.source_package_id != package.manifest.package_id:
            raise PackageValidationError("EVALUATION_PACKAGE_MISMATCH", case.case_id)
        if len(set(case.expected_node_ids)) != len(case.expected_node_ids):
            raise PackageValidationError("DUPLICATE_EXPECTED_NODE", case.case_id)
        for node_id in case.expected_node_ids:
            if node_id not in nodes:
                raise PackageValidationError("EVALUATION_DANGLING_NODE", node_id)
            source = sources[docs[nodes[node_id].document_id].source_version_id]
            if not can_access(source, case.principal_id):
                raise PackageValidationError("EVALUATION_ACCESS_DENIED", case.case_id)
        bundle = search_index(
            package, index, case.query,
            principal_id=case.principal_id, task_type=case.task_type, limit=limit,
        )
        retrieved = [item.node_id for item in bundle.evidence]
        missing = sorted(set(case.expected_node_ids) - set(retrieved))
        recall = (len(case.expected_node_ids) - len(missing)) / len(case.expected_node_ids) if case.expected_node_ids else (1.0 if not retrieved else 0.0)
        passed = not missing and bundle.coverage == case.expected_coverage
        if not case.expected_node_ids and retrieved:
            passed = False
        result = EvaluationResult(
            case_id=case.case_id, source_package_id=package.manifest.package_id,
            index_id=index.index_id, retrieved_node_ids=retrieved,
            expected_node_ids=case.expected_node_ids, missing_node_ids=missing,
            coverage=bundle.coverage, recall=recall, passed=passed,
        )
        default_schema_store().validate_instance_with_short_name(result.model_dump(mode="json"), "evaluation-result")
        results.append(result)
    return results


def propose_retrieval_changes(
    package: CanonicalPackage, cases: list[EvaluationCase], results: list[EvaluationResult],
) -> list[Proposal]:
    by_id = {case.case_id: case for case in cases}
    proposals = []
    for result in results:
        if not result.missing_node_ids:
            continue
        case = by_id[result.case_id]
        evidence = [evidence_for_node(package, node_id) for node_id in result.missing_node_ids]
        change = RetrievalChange(
            change_id=stable_id("change", package.manifest.package_id, case.case_id, "retrieval-v1"),
            evaluation_case_id=case.case_id, query=case.query,
            action="Review retrieval aliases, metadata, or indexing for the missed evidence.",
            missing_node_ids=result.missing_node_ids,
            source_trace_ids=result.missing_node_ids,
        )
        proposals.append(Proposal(
            proposal_id=stable_id("prop", package.manifest.package_id, change.change_id),
            proposal_type="retrieval_change", payload_schema=CHANGE_SCHEMA,
            payload=change.model_dump(mode="json"), evidence=evidence,
            confidence=1.0 - result.recall,
            source_package_id=package.manifest.package_id,
            run_id=stable_id("run", package.manifest.package_id, result.index_id, "evaluation-v1"),
        ))
    return proposals


def write_evaluation_results(path: Path, results: list[EvaluationResult]) -> None:
    path = Path(path)
    content = "".join(
        json.dumps(item.model_dump(mode="json"), sort_keys=True, ensure_ascii=False) + "\n"
        for item in results
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise PackageValidationError("EVALUATION_RESULTS_EXIST", str(path))
    if not path.exists():
        with path.open("x", encoding="utf-8") as stream:
            stream.write(content)

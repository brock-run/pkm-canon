"""Portable records shared by source adapters and knowledge products."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceProfile(StrictModel):
    source_system: str
    profile_version: str


class AccessPolicy(StrictModel):
    visibility: Literal["private", "restricted", "public"] = "private"
    principal_ids: list[str] = Field(default_factory=list)
    classification: str = "personal"


class HashDescriptor(StrictModel):
    algorithm: Literal["sha256", "sha512", "md5"]
    digest: str


class SourceNativeReference(StrictModel):
    storage_kind: Literal["relative_path", "embedded_utf8", "embedded_base64", "external_uri"]
    relative_path: str | None = None
    external_uri: str | None = None
    inline_utf8: str | None = None
    inline_base64: str | None = None
    byte_length: int | None = Field(default=None, ge=0)
    hashes: list[HashDescriptor] = Field(default_factory=list)
    media_type: str | None = None
    charset: str | None = None
    content_language: str | None = None
    role: Literal["primary", "source_export", "attachment", "preview", "thumbnail", "sidecar", "transcript", "metadata"] | None = None
    label: str | None = None

    @model_validator(mode="after")
    def storage_locator_matches_kind(self) -> SourceNativeReference:
        fields = {
            "relative_path": self.relative_path,
            "external_uri": self.external_uri,
            "embedded_utf8": self.inline_utf8,
            "embedded_base64": self.inline_base64,
        }
        if not fields[self.storage_kind] or sum(value is not None for value in fields.values()) != 1:
            raise ValueError("storage_kind requires exactly its matching locator")
        return self


class SourceVersion(StrictModel):
    source_version_id: str
    source_system: str
    source_scope: str
    native_id: str
    content_hash: str
    storage: SourceNativeReference
    source_uri: str | None = None
    source_event_time: str | None = None
    observed_at: str | None = None
    access: AccessPolicy = Field(default_factory=AccessPolicy)


class ContentItem(StrictModel):
    item_id: str
    source_version_id: str
    kind: str
    title: str
    source_event_time: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    observed_at: str | None = None
    access: AccessPolicy


class ContentElement(StrictModel):
    element_id: str
    item_id: str
    parent_element_id: str | None = None
    kind: str
    position: int = Field(ge=0)
    text: str


class NativeLink(StrictModel):
    link_id: str
    source_id: str
    target_id: str
    kind: str
    target_kind: Literal["canonical", "tag", "external"]
    source_representation: str | None = None


class SharedContentSnapshot(StrictModel):
    contract_version: str
    source_package_id: str
    source_versions: list[SourceVersion]
    items: list[ContentItem]
    elements: list[ContentElement]
    native_links: list[NativeLink]


class ParserDescriptor(StrictModel):
    name: str
    version: str


class FileInventoryEntry(StrictModel):
    sha256: str
    byte_length: int = Field(ge=0)
    record_count: int | None = Field(default=None, ge=0)


class FidelitySummary(StrictModel):
    source_object_count: int = Field(ge=0)
    normalized: int = Field(ge=0)
    partial: int = Field(ge=0)
    preserved_only: int = Field(ge=0)
    unsupported: int = Field(ge=0)
    rejected: int = Field(ge=0)
    unresolved_reference_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    error_count: int = Field(ge=0)


class Manifest(StrictModel):
    package_id: str
    package_schema_version: str
    created_at: str
    source_profiles: list[SourceProfile]
    source_versions: list[SourceVersion]
    parser: ParserDescriptor
    adapter_contracts: dict[str, str] = Field(default_factory=dict)
    files: dict[str, FileInventoryEntry]
    fidelity: FidelitySummary


class FacetEnvelope(BaseModel):
    schema_url: str = Field(alias="_schemaURL")
    producer: str | None = Field(default=None, alias="_producer")
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class Document(StrictModel):
    document_id: str
    source_version_id: str
    kind: str
    title: str
    created_at: str | None = None
    updated_at: str | None = None
    facets: dict[str, FacetEnvelope] = Field(default_factory=dict)


class Node(StrictModel):
    node_id: str
    document_id: str
    parent_node_id: str | None = None
    node_type: str
    semantic_kind: str | None = None
    position: int = Field(default=0, ge=0)
    plain_text: str = ""
    facets: dict[str, FacetEnvelope] = Field(default_factory=dict)


class Mention(StrictModel):
    kind: str
    target_id: str


class Span(StrictModel):
    span_id: str
    node_id: str
    kind: Literal["text", "mention", "link", "equation", "code"]
    text: str
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)
    marks: list[str] = Field(default_factory=list)
    mention: Mention | None = None
    facets: dict[str, FacetEnvelope] = Field(default_factory=dict)


class Relation(StrictModel):
    relation_id: str
    source_id: str
    target_id: str
    relation_type: str
    target_kind: Literal["canonical", "tag", "external"] = "canonical"
    subtype: str | None = None
    source_representation: str | None = None
    facets: dict[str, FacetEnvelope] = Field(default_factory=dict)


class Attribute(StrictModel):
    attribute_id: str
    subject_kind: str
    subject_id: str
    key: str
    value_type: str
    value: Any
    facets: dict[str, FacetEnvelope] = Field(default_factory=dict)


class SourceLocator(StrictModel):
    source_uid: str | None = None
    parent_source_uid: str | None = None
    graph: str | None = None
    workspace: str | None = None
    path: str | None = None
    uri: str | None = None
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)


class GeneratedByActivity(StrictModel):
    activity_id: str | None = None
    activity_type: str | None = None
    agent: str | None = None
    used_inputs: list[str] = Field(default_factory=list)


class ExtractionByteRange(StrictModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class ExtractionHints(StrictModel):
    json_pointer: str | None = None
    dom_selector: str | None = None
    byte_range: ExtractionByteRange | None = None


class PreservationRecord(StrictModel):
    record_type: Literal["preservation_record"]
    schema_version: str
    id: str
    subject_id: str
    source_system: str
    source_profile_version: str | None = None
    source_object_type: str
    source_locator: SourceLocator | None = None
    capture_type: Literal["raw_json", "raw_html", "raw_markdown", "raw_xml", "plain_text", "rich_text_fragment", "binary_blob", "rendered_preview", "unsupported_object", "adapter_sidecar"]
    storage: SourceNativeReference
    normalization_status: Literal["unprocessed", "partial", "normalized", "deferred", "unsupported"]
    preservation_reason: list[Literal["loss_prevention", "future_replay", "source_audit", "unsupported_feature", "adapter_roundtrip", "binary_attachment", "legal_archive", "debugging"]] = Field(default_factory=list)
    derived_from_preservation_id: str | None = None
    generated_by_activity: GeneratedByActivity | None = None
    extraction_hints: ExtractionHints | None = None
    notes: str | None = None


class PreservationBundle(StrictModel):
    record_type: Literal["preservation_bundle"]
    schema_version: str
    id: str
    subject_id: str
    source_system: str
    source_profile_version: str | None = None
    bundle_strategy: Literal["multi_payload_single_subject", "compound_source_object", "primary_plus_derivatives"]
    source_locator: SourceLocator | None = None
    normalization_status: Literal["unprocessed", "partial", "normalized", "deferred", "unsupported"]
    preservation_reason: list[Literal["loss_prevention", "future_replay", "source_audit", "unsupported_feature", "adapter_roundtrip", "binary_attachment", "legal_archive", "debugging"]] = Field(default_factory=list)
    bundle_items: list[SourceNativeReference] = Field(min_length=1)
    primary_item_index: int | None = Field(default=None, ge=0)
    generated_by_activity: GeneratedByActivity | None = None
    notes: str | None = None


class Diagnostic(StrictModel):
    diagnostic_id: str
    code: str
    severity: Literal["info", "warning", "error"]
    outcome: Literal["partial", "preserved_only", "unsupported", "rejected", "unresolved_reference"]
    source_locator: SourceLocator
    subject_id: str | None = None
    preservation_id: str | None = None
    detail: str | None = None


class EvidenceRef(StrictModel):
    evidence_id: str
    source_version_id: str
    node_id: str
    source_locator: SourceLocator
    source_content_hash: str
    span_id: str | None = None
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)
    quote: str | None = None


class EvidenceBundle(StrictModel):
    bundle_id: str
    source_package_id: str
    requester_principal_id: str
    task_type: str
    query: str
    retrieval_profile_version: str
    evidence: list[EvidenceRef]
    coverage: Literal["complete", "partial", "none"]


class MethodologyRule(StrictModel):
    rule_id: str
    rule_type: Literal["attribute_convention", "tag_convention", "link_convention"]
    statement: str
    confidence: float = Field(ge=0, le=1)
    source_trace_ids: list[str] = Field(min_length=1)
    status: Literal["proposed", "approved", "rejected"] = "proposed"


class DomainClaim(StrictModel):
    claim_id: str
    subject: str
    predicate: Literal["owned_by", "described_as"]
    object: str
    source_trace_ids: list[str] = Field(min_length=1)
    status: Literal["proposed", "approved", "rejected"] = "proposed"
    valid_from: str | None = None
    valid_to: str | None = None


class RetrievalChange(StrictModel):
    change_id: str
    evaluation_case_id: str
    query: str
    action: str
    missing_node_ids: list[str] = Field(min_length=1)
    source_trace_ids: list[str] = Field(min_length=1)
    status: Literal["proposed", "approved", "rejected"] = "proposed"


class EvaluationCase(StrictModel):
    case_id: str
    source_package_id: str
    query: str
    task_type: str
    principal_id: str
    expected_node_ids: list[str]
    expected_coverage: Literal["complete", "partial", "none"]


class EvaluationResult(StrictModel):
    case_id: str
    source_package_id: str
    index_id: str
    retrieved_node_ids: list[str]
    expected_node_ids: list[str]
    missing_node_ids: list[str]
    coverage: Literal["complete", "partial", "none"]
    recall: float = Field(ge=0, le=1)
    passed: bool


class Proposal(StrictModel):
    proposal_id: str
    proposal_type: Literal["methodology_rule", "domain_claim", "documentation_change", "retrieval_change"]
    payload_schema: str
    payload: dict[str, Any]
    evidence: list[EvidenceRef] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    status: Literal["proposed", "approved", "rejected"] = "proposed"
    source_package_id: str
    run_id: str


class ReviewPolicy(StrictModel):
    policy_version: str
    approved_reviewers: list[str] = Field(min_length=1)


class ReviewEvent(StrictModel):
    event_id: str
    proposal_id: str
    reviewer_id: str
    run_id: str
    decision: Literal["approved", "rejected"]
    decided_at: str
    rationale: str | None = None
    policy_version: str


class MethodologyManifest(StrictModel):
    manifest_id: str
    source_package_id: str
    rules: list[MethodologyRule]
    review_event_ids: list[str]
    generated_at: str


class ProjectionManifest(StrictModel):
    projection_id: str
    adapter_name: str
    adapter_contract_version: str
    source_package_id: str
    files: dict[str, FileInventoryEntry]
    issue_count: int = Field(ge=0)


class IndexProjection(StrictModel):
    index_id: str
    source_package_id: str
    profile_version: str
    terms: dict[str, list[str]]
    native_links: list[NativeLink]


PreservationArtifact = Annotated[PreservationRecord | PreservationBundle, Field(discriminator="record_type")]
preservation_artifact_adapter = TypeAdapter(PreservationArtifact)

from __future__ import annotations
from typing import Any, Annotated, Literal
from pydantic import BaseModel, Field, TypeAdapter


class SourceProfile(BaseModel):
    source_system: str
    profile_version: str

class Manifest(BaseModel):
    package_id: str
    package_schema_version: str
    created_at: str
    source_profiles: list[SourceProfile]
    adapter_contracts: dict[str, str] = Field(default_factory=dict)

class FacetEnvelope(BaseModel):
    schemaURL: str = Field(alias="_schemaURL")
    producer: str | None = Field(default=None, alias="_producer")
    # Allow extra fields for the actual facet payload properties
    model_config = {"extra": "allow"}

class Document(BaseModel):
    document_id: str
    kind: str
    title: str
    created_at: str | None = None
    updated_at: str | None = None
    facets: dict[str, FacetEnvelope] = Field(default_factory=dict)

class Node(BaseModel):
    node_id: str
    document_id: str
    parent_node_id: str | None = None
    node_type: str
    semantic_kind: str | None = None
    position: int = 0
    plain_text: str = ""


class Mention(BaseModel):
    kind: str
    target_id: str


class Span(BaseModel):
    span_id: str
    node_id: str
    kind: Literal["text", "mention", "link", "equation", "code"]
    text: str
    marks: list[str] = Field(default_factory=list)
    mention: Mention | None = None


class Relation(BaseModel):
    relation_id: str
    source_id: str
    target_id: str
    relation_type: str
    subtype: str | None = None
    source_representation: str | None = None


class Attribute(BaseModel):
    attribute_id: str
    subject_kind: str
    subject_id: str
    key: str
    value_type: str
    value: Any


class HashDescriptor(BaseModel):
    algorithm: Literal["sha256", "sha512", "md5"]
    digest: str


class SourceNativeReference(BaseModel):
    storage_kind: Literal["relative_path", "embedded_utf8", "embedded_base64", "external_uri"]
    relative_path: str | None = None
    external_uri: str | None = None
    inline_utf8: str | None = None
    inline_base64: str | None = None
    byte_length: int | None = None
    hashes: list[HashDescriptor] = Field(default_factory=list)
    media_type: str | None = None
    charset: str | None = None
    content_language: str | None = None
    role: Literal["primary", "source_export", "attachment", "preview", "thumbnail", "sidecar", "transcript", "metadata"] | None = None
    label: str | None = None


class SourceLocator(BaseModel):
    source_uid: str | None = None
    parent_source_uid: str | None = None
    graph: str | None = None
    workspace: str | None = None
    path: str | None = None
    uri: str | None = None


class GeneratedByActivity(BaseModel):
    activity_id: str | None = None
    activity_type: str | None = None
    agent: str | None = None
    used_inputs: list[str] = Field(default_factory=list)


class ExtractionByteRange(BaseModel):
    start: int
    end: int


class ExtractionHints(BaseModel):
    json_pointer: str | None = None
    dom_selector: str | None = None
    byte_range: ExtractionByteRange | None = None


class PreservationRecord(BaseModel):
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


class PreservationBundle(BaseModel):
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
    bundle_items: list[SourceNativeReference]
    primary_item_index: int | None = None
    generated_by_activity: GeneratedByActivity | None = None
    notes: str | None = None


PreservationArtifact = Annotated[PreservationRecord | PreservationBundle, Field(discriminator="record_type")]
preservation_artifact_adapter = TypeAdapter(PreservationArtifact)

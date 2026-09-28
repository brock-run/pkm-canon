from pkmcanon.models import FacetEnvelope


def test_facet_envelope_accepts_extra_payload():
    facet = FacetEnvelope.model_validate({
        "_schemaURL": "https://example.org/facets/demo/v1",
        "_producer": "unit-test",
        "custom": "value"
    })
    dumped = facet.model_dump(by_alias=True)
    assert dumped["_schemaURL"] == "https://example.org/facets/demo/v1"
    assert dumped["_producer"] == "unit-test"
    assert dumped["custom"] == "value"

from pathlib import Path
from pkmcanon.package import CanonicalPackage
from pkmcanon.models import PreservationRecord, PreservationBundle


def test_preservation_models_load():
    pkg = CanonicalPackage(Path("examples/minimal-package"))
    assert isinstance(pkg.preservation_records[0], PreservationRecord)
    assert isinstance(pkg.preservation_bundles[0], PreservationBundle)


def test_preservation_artifact_union_loader():
    pkg = CanonicalPackage(Path("examples/minimal-package"))
    assert {a.record_type for a in pkg.preservation_artifacts} == {"preservation_record", "preservation_bundle"}

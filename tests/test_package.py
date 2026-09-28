from pathlib import Path
from pkmcanon.package import CanonicalPackage


def test_package_loads():
    pkg = CanonicalPackage(Path("examples/minimal-package"))
    assert pkg.manifest.package_id == "pkg_demo_001"
    assert len(pkg.documents) == 2
    assert len(pkg.nodes) == 2

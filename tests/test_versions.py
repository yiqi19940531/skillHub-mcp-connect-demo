import pytest

from backend.app.security.packages import SEMVER
from backend.app.services.registry import version_key


def test_semver_precedence_does_not_use_pep440_rules():
    versions = [
        "1.0.0-alpha",
        "1.0.0-alpha.1",
        "1.0.0-alpha.beta",
        "1.0.0-beta",
        "1.0.0-beta.2",
        "1.0.0-beta.11",
        "1.0.0-rc.1",
        "1.0.0",
        "1.0.1-hotfix",
        "1.0.1",
        "2.0.0",
    ]
    assert sorted(reversed(versions), key=version_key) == versions
    assert version_key("1.0.0+build.1") == version_key("1.0.0+build.2")


@pytest.mark.parametrize("value", ["1", "01.0.0", "1.0.0-01", "1.0.0-foo..bar", "1.0.0+", "../1.0.0"])
def test_invalid_versions_are_rejected(value):
    assert SEMVER.fullmatch(value) is None

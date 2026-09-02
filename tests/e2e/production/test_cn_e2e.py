import os
import pytest

pytestmark = pytest.mark.skipif(os.getenv("MEITI_PRODUCTION_E2E") != "true", reason="real credentials required")


def test_requires_real_credentials():
    assert os.getenv("MEITI_PRODUCTION_E2E") == "true"

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations defined in the test repository."""
    yield


@pytest.fixture
def platforms() -> list[str]:
    """Fixture for platforms to be loaded."""
    return ["conversation"]

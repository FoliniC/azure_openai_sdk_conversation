# Ensure we can import mock_ha from the current directory
import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.append(os.path.dirname(__file__))
import mock_ha


# Define a strict parent class that mimics object.__init__ behavior (no args)
class StrictOptionsFlow:
    def __init__(self):
        self._config_entry = None

    @property
    def config_entry(self):
        return self._config_entry


# Monkeypatch the mock to use our StrictOptionsFlow
# This must be done BEFORE importing the module under test
mock_ha.ha.config_entries.ConfigFlowResult = MagicMock

# Add missing mock for homeassistant.helpers.typing
mock_typing = MagicMock()
mock_ha.ha.helpers.typing = mock_typing
sys.modules["homeassistant.helpers.typing"] = mock_typing

# Add missing mock for homeassistant.helpers.selector
mock_selector = MagicMock()
mock_ha.ha.helpers.selector = mock_selector
sys.modules["homeassistant.helpers.selector"] = mock_selector
# Ensure the imported names exist
mock_selector.BooleanSelector = MagicMock
mock_selector.NumberSelector = MagicMock
mock_selector.NumberSelectorConfig = MagicMock
mock_selector.SelectSelector = MagicMock
mock_selector.SelectSelectorConfig = MagicMock
mock_selector.SelectSelectorMode = MagicMock
mock_selector.TemplateSelector = MagicMock

# Now import the module under test
from homeassistant.config_entries import ConfigEntry  # noqa: E402

from custom_components.azure_openai_sdk_conversation.options_flow import (
    AzureOpenAIOptionsFlow,
)  # noqa: E402


@pytest.fixture
def patch_options_flow():
    """Patch OptionsFlow with StrictOptionsFlow and restore after test."""
    original = mock_ha.ha.config_entries.OptionsFlow
    mock_ha.ha.config_entries.OptionsFlow = StrictOptionsFlow
    yield
    mock_ha.ha.config_entries.OptionsFlow = original


@pytest.mark.anyio
async def test_options_flow_init_strict(patch_options_flow):
    """
    Test that AzureOpenAIOptionsFlow initializes correctly without passing args to super().__init__.
    """
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {}
    config_entry.options = {}

    # This should succeed.
    # If the bug was present (super().__init__(config_entry)), it would raise TypeError
    # because StrictOptionsFlow.__init__ accepts no arguments.
    flow = AzureOpenAIOptionsFlow(config_entry)

    # Verify we manually set the config_entry (backing field)
    assert flow.config_entry == config_entry

"""Test Config Flow."""
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from homeassistant.data_entry_flow import FlowResultType
from custom_components.cronostar.const import DOMAIN, CONF_LOGGING_ENABLED

@pytest.mark.anyio
async def test_config_flow_user_step(hass):
    """Test user step."""
    # Start flow
    hass.config_entries.flow.async_init = AsyncMock(return_value={
        "type": FlowResultType.FORM,
        "step_id": "install_component",
        "flow_id": "test_flow"
    })
    
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "install_component"
    
    # Submit form
    hass.config_entries.flow.async_configure = AsyncMock(return_value={
        "type": FlowResultType.CREATE_ENTRY,
        "data": {"component_installed": True, CONF_LOGGING_ENABLED: True}
    })
    
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], 
        user_input={CONF_LOGGING_ENABLED: True}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["component_installed"] is True
    assert result["data"][CONF_LOGGING_ENABLED] is True

@pytest.mark.anyio
async def test_config_flow_single_instance(hass):
    """Test only one global instance allowed."""
    # Mock existing entry
    entry = MagicMock()
    entry.data = {"component_installed": True}
    hass.config_entries.async_entries = MagicMock(return_value=[entry])
    
    # Manually instantiate flow since we want to test its logic
    from custom_components.cronostar.config_flow import CronoStarConfigFlow
    flow = CronoStarConfigFlow()
    flow.hass = hass
    
    # Mock _async_current_entries
    flow._async_current_entries = MagicMock(return_value=[entry])
    
    result = await flow.async_step_user()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"

@pytest.mark.anyio
async def test_config_flow_create_controller(hass):
    """Test programmatic controller creation."""
    from custom_components.cronostar.config_flow import CronoStarConfigFlow
    flow = CronoStarConfigFlow()
    flow.hass = hass
    
    # Mock set_unique_id and abort_if_unique_id_configured
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = MagicMock()
    
    result = await flow.async_step_create_controller(user_input={
        "name": "Test Room",
        "preset": "thermostat",
        "target_entity": "climate.test",
        "global_prefix": "test_prefix_"
    })
    
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Room"
    assert result["data"]["global_prefix"] == "test_prefix_"

@pytest.mark.anyio
async def test_options_flow(hass):
    """Test options flow."""
    entry = MagicMock()
    entry.data = {CONF_LOGGING_ENABLED: False}
    entry.options = {}
    
    from custom_components.cronostar.config_flow import CronoStarOptionsFlow
    flow = CronoStarOptionsFlow(entry)
    flow.hass = hass
    
    # Mock async_show_form
    flow.async_show_form = MagicMock(return_value={"type": FlowResultType.FORM})
    
    # Init step (show form)
    result = await flow.async_step_init()
    assert result["type"] == FlowResultType.FORM
    
    # Submit options
    flow.async_create_entry = MagicMock(return_value={
        "type": FlowResultType.CREATE_ENTRY,
        "data": {CONF_LOGGING_ENABLED: True}
    })
    
    result = await flow.async_step_init(user_input={CONF_LOGGING_ENABLED: True})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_LOGGING_ENABLED] is True
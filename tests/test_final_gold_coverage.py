"""Test Final Gold Coverage."""
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from homeassistant.data_entry_flow import FlowResultType
from custom_components.cronostar.const import DOMAIN, CONF_LOGGING_ENABLED, CONF_NAME, CONF_TARGET_ENTITY
from custom_components.cronostar.exceptions import ScheduleApplicationError
from custom_components.cronostar.setup.services import setup_services

# === Config Flow Tests ===

@pytest.mark.anyio
async def test_config_flow_reconfigure_global(hass):
    """Test reconfigure flow for global component."""
    from custom_components.cronostar.config_flow import CronoStarConfigFlow
    flow = CronoStarConfigFlow()
    flow.hass = hass
    
    # Mock entry
    entry = MagicMock()
    entry.entry_id = "test_global"
    entry.title = "CronoStar"
    entry.data = {"component_installed": True, CONF_LOGGING_ENABLED: False}
    hass.config_entries.async_get_entry = MagicMock(return_value=entry)
    flow.context = {"entry_id": "test_global"}
    
    # Step 1: Show form
    result = await flow.async_step_reconfigure()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    
    # Step 2: Submit
    flow.async_update_reload_and_abort = MagicMock(return_value={"type": "abort", "reason": "reconfigure_successful"})
    result = await flow.async_step_reconfigure(user_input={CONF_LOGGING_ENABLED: True})
    assert result["type"] == "abort"
    assert flow.async_update_reload_and_abort.call_args[1]["data"][CONF_LOGGING_ENABLED] is True

@pytest.mark.anyio
async def test_config_flow_reconfigure_controller(hass):
    """Test reconfigure flow for controller."""
    from custom_components.cronostar.config_flow import CronoStarConfigFlow
    flow = CronoStarConfigFlow()
    flow.hass = hass
    
    # Mock entry
    entry = MagicMock()
    entry.entry_id = "test_controller"
    entry.title = "My Controller"
    entry.data = {"component_installed": False, CONF_NAME: "My Controller", CONF_TARGET_ENTITY: "climate.old"}
    hass.config_entries.async_get_entry = MagicMock(return_value=entry)
    flow.context = {"entry_id": "test_controller"}
    
    # Step 1: Show form
    result = await flow.async_step_reconfigure()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    
    # Step 2: Submit
    flow.async_update_reload_and_abort = MagicMock(return_value={"type": "abort", "reason": "reconfigure_successful"})
    result = await flow.async_step_reconfigure(user_input={CONF_NAME: "New Name", CONF_TARGET_ENTITY: "climate.new"})
    assert result["type"] == "abort"
    data = flow.async_update_reload_and_abort.call_args[1]["data"]
    assert data[CONF_NAME] == "New Name"
    assert data[CONF_TARGET_ENTITY] == "climate.new"

# === Services Tests ===

@pytest.mark.anyio
async def test_apply_now_edge_cases(hass):
    """Test apply_now service edge cases."""
    await setup_services(hass, MagicMock())
    handler = next(c[0][2] for call in [hass.services.async_register.call_args_list] for c in call if c[0][1] == "apply_now")
    
    ps = hass.data[DOMAIN]["profile_service"]
    
    # 1. Invalid points in schedule
    ps.get_profile_data = AsyncMock(return_value={
        "schedule": [
            {"time": "bad", "value": 20.0}, # Invalid time
            {"time": "08:00", "value": None}, # Invalid value
            {"time": "09:00", "value": 21.0} # Valid
        ]
    })
    call = MagicMock()
    call.data = {"target_entity": "climate.test", "profile_name": "P1"}
    await handler(call)
    # Should work and use the valid point
    assert hass.services.async_call.called

    # 2. No points at all
    ps.get_profile_data = AsyncMock(return_value={"schedule": []})
    await handler(call)
    
    # 3. Points exist but none valid (empty after filtering)
    ps.get_profile_data = AsyncMock(return_value={
        "schedule": [{"time": "bad", "value": 20}]
    })
    await handler(call) # Should warn and return
    
    # 4. Wrap around logic
    # Set time to 23:00, schedule has 08:00 (10) and 20:00 (20)
    # Current value should be 20. Next change at 08:00 (wrap around)
    with patch("custom_components.cronostar.setup.services.datetime") as mock_dt:
        mock_dt.now.return_value.hour = 23
        mock_dt.now.return_value.minute = 0
        
        ps.get_profile_data = AsyncMock(return_value={
            "schedule": [
                {"time": "08:00", "value": 10.0},
                {"time": "20:00", "value": 20.0}
            ]
        })
        await handler(call)
        # Verify call made
        assert hass.services.async_call.called

    # 5. Unsupported domain
    call.data = {"target_entity": "unsupported.entity", "profile_name": "P1"}
    await handler(call)
    
    # 6. Exception handling
    ps.get_profile_data = AsyncMock(side_effect=Exception("Boom"))
    with pytest.raises(ScheduleApplicationError):
        await handler(call)


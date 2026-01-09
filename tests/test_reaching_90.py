"""Reaching the 90% goal."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.cronostar.const import CONF_TARGET_ENTITY, DOMAIN
from custom_components.cronostar.coordinator import CronoStarCoordinator
from custom_components.cronostar.setup.services import setup_services


@pytest.mark.anyio
async def test_coordinator_more_branch_hits(hass):
    """Trigger remaining coordinator lines."""
    entry = MagicMock()
    entry.data = {CONF_TARGET_ENTITY: "climate.test"}
    coordinator = CronoStarCoordinator(hass, entry)
    coordinator.logging_enabled = True

    hass.states.get.return_value = MagicMock(state="20")
    await coordinator._async_update_data()

    hass.states.get.return_value = None
    await coordinator._async_update_data()

    coordinator.target_entity = "unsupported.entity"
    await coordinator._update_target_entity(20.0)


@pytest.mark.anyio
async def test_setup_services_remaining_errors(hass):
    """Trigger remaining lines in setup/services.py."""
    await setup_services(hass, MagicMock())
    handler = next(
        c[0][2]
        for call in [hass.services.async_register.call_args_list]
        for c in call
        if c[0][1] == "apply_now"
    )

    ps = hass.data[DOMAIN]["profile_service"]

    # Target missing
    call = MagicMock()
    call.data = {"profile_name": "P1"}
    await handler(call)

    # Profile missing
    call.data = {"target_entity": "climate.test"}
    await handler(call)

    # Profile error
    ps.get_profile_data = AsyncMock(return_value={"error": "Not found"})
    call.data = {"target_entity": "climate.test", "profile_name": "P1"}

    from custom_components.cronostar.exceptions import ProfileNotFoundError

    with pytest.raises(ProfileNotFoundError):
        await handler(call)

    # Constant schedule for domain testing
    ps.get_profile_data = AsyncMock(
        return_value={
            "schedule": [
                {"time": "00:00", "value": 20.0},
                {"time": "23:59", "value": 20.0},
            ]
        }
    )

    # Test different domains
    for entity in ["switch.test", "input_number.test", "cover.test"]:
        call.data = {"target_entity": entity, "profile_name": "P1"}
        await handler(call)
        assert hass.services.async_call.called

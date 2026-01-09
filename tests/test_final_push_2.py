"""The final final push for coverage."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.cronostar.const import CONF_TARGET_ENTITY, DOMAIN
from custom_components.cronostar.coordinator import CronoStarCoordinator
from custom_components.cronostar.setup.services import setup_services


@pytest.mark.anyio
async def test_coordinator_unsupported_domain_trigger(hass):
    """Trigger lines 210-216 in coordinator."""
    entry = MagicMock()
    entry.data = {CONF_TARGET_ENTITY: "sensor.test"}  # Unsupported
    coordinator = CronoStarCoordinator(hass, entry)
    coordinator.logging_enabled = True

    # Target entity exists but domain is sensor
    hass.states.get.return_value = MagicMock(state="20")

    # We need to call _update_target_entity directly
    await coordinator._update_target_entity(20.0)


@pytest.mark.anyio
async def test_coordinator_next_change_edge(hass):
    """Trigger lines 390, 395-396 in coordinator."""
    entry = MagicMock()
    entry.data = {CONF_TARGET_ENTITY: "climate.test"}
    coordinator = CronoStarCoordinator(hass, entry)

    # Schedule with no differing values to hit 395-396
    schedule = [{"time": "08:00", "value": 20.0}]
    assert coordinator._get_next_change(schedule, 20.0) is None

    # Trigger line 390 wrap around loop
    schedule = [{"time": "08:00", "value": 20.0}, {"time": "20:00", "value": 18.0}]
    from datetime import datetime

    with patch("custom_components.cronostar.coordinator.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2023, 1, 1, 21, 0, 0)
        # Value is 18.0. Next change is 08:00 (value 20.0)
        res = coordinator._get_next_change(schedule, 18.0)
        assert res[0] == "08:00"


@pytest.mark.anyio
async def test_setup_services_more_handlers(hass):
    """Trigger more lines in setup/services.py."""
    await setup_services(hass, MagicMock())

    # list_all_profiles_handler - empty container branch (line 103)
    handler = next(
        c[0][2]
        for call in [hass.services.async_register.call_args_list]
        for c in call
        if c[0][1] == "list_all_profiles"
    )

    storage = MagicMock()
    storage.list_profiles = AsyncMock(return_value=["f1.json"])
    storage.load_profile_cached = AsyncMock(return_value={})  # No meta

    # We need to ensure list_all_profiles uses our mock_storage
    hass.data[DOMAIN]["storage_manager"] = storage

    await handler(MagicMock())

    # apply_now_handler - more error paths
    handler = next(
        c[0][2]
        for call in [hass.services.async_register.call_args_list]
        for c in call
        if c[0][1] == "apply_now"
    )

    ps = hass.data[DOMAIN]["profile_service"]

    # Empty schedule (line 149-150)
    ps.get_profile_data = AsyncMock(return_value={"schedule": []})
    call = MagicMock()
    call.data = {"target_entity": "climate.test", "profile_name": "P1"}
    await handler(call)

    # Invalid points in apply_now (lines 163-164)
    ps.get_profile_data = AsyncMock(return_value={"schedule": [{"time": "invalid"}]})
    await handler(call)

"""The very last lines for 90%."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.cronostar.const import CONF_TARGET_ENTITY, DOMAIN
from custom_components.cronostar.coordinator import CronoStarCoordinator
from custom_components.cronostar.setup.services import setup_services


@pytest.mark.anyio
async def test_coordinator_next_change_no_diff(hass):
    """Trigger lines 395-396 in coordinator (no differing value found)."""
    entry = MagicMock()
    entry.data = {CONF_TARGET_ENTITY: "climate.test"}
    coordinator = CronoStarCoordinator(hass, entry)

    schedule = [{"time": "08:00", "value": 20.0}]
    assert coordinator._get_next_change(schedule, 20.0) is None


@pytest.mark.anyio
async def test_setup_services_list_all_bad_data(hass):
    """Trigger setup/services.py line 103 (empty container)."""
    await setup_services(hass, MagicMock())

    handler = next(
        c[0][2]
        for call in [hass.services.async_register.call_args_list]
        for c in call
        if c[0][1] == "list_all_profiles"
    )

    mock_storage = MagicMock()
    mock_storage.list_profiles = AsyncMock(return_value=["f1.json"])
    mock_storage.load_profile_cached = AsyncMock(return_value={})  # No meta

    # We need to ensure list_all_profiles uses our mock_storage
    hass.data[DOMAIN]["storage_manager"] = mock_storage

    await handler(MagicMock())


@pytest.mark.anyio
async def test_coordinator_init_no_profiles_found_log(hass):
    """Trigger line 153 logging branch."""
    entry = MagicMock()
    entry.data = {CONF_TARGET_ENTITY: "climate.test"}
    coordinator = CronoStarCoordinator(hass, entry)
    coordinator.logging_enabled = True

    storage = MagicMock()
    storage.list_profiles = AsyncMock(return_value=[])
    hass.data[DOMAIN]["storage_manager"] = storage

    await coordinator.async_initialize()

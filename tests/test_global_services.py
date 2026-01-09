"""Test Global Services Registration and Execution."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.cronostar.setup.services import setup_services


@pytest.mark.anyio
async def test_setup_services(hass):
    """Test service registration."""
    storage_manager = MagicMock()
    await setup_services(hass, storage_manager)

    # Check that services were registered
    assert hass.services.async_register.called
    registered_services = [
        call[0][1] for call in hass.services.async_register.call_args_list
    ]
    assert "save_profile" in registered_services
    assert "load_profile" in registered_services
    assert "apply_now" in registered_services


def get_handler(hass, service_name):
    """Utility to extract handler from registered services."""
    for call in hass.services.async_register.call_args_list:
        if call[0][1] == service_name:
            return call[0][2]
    return None


@pytest.mark.anyio
async def test_save_profile_service(hass):
    storage_manager = MagicMock()
    await setup_services(hass, storage_manager)
    handler = get_handler(hass, "save_profile")

    profile_service = hass.data["cronostar"]["profile_service"]
    profile_service.save_profile = AsyncMock()

    call = MagicMock()
    call.data = {"profile_name": "Test"}
    await handler(call)
    profile_service.save_profile.assert_called_with(call)


@pytest.mark.anyio
async def test_load_profile_service(hass):
    storage_manager = MagicMock()
    await setup_services(hass, storage_manager)
    handler = get_handler(hass, "load_profile")

    profile_service = hass.data["cronostar"]["profile_service"]
    profile_service.load_profile = AsyncMock()

    call = MagicMock()
    await handler(call)
    profile_service.load_profile.assert_called_with(call)


@pytest.mark.anyio
async def test_add_profile_service(hass):
    storage_manager = MagicMock()
    await setup_services(hass, storage_manager)
    handler = get_handler(hass, "add_profile")

    profile_service = hass.data["cronostar"]["profile_service"]
    profile_service.add_profile = AsyncMock()

    call = MagicMock()
    await handler(call)
    profile_service.add_profile.assert_called_with(call)


@pytest.mark.anyio
async def test_delete_profile_service(hass):
    storage_manager = MagicMock()
    await setup_services(hass, storage_manager)
    handler = get_handler(hass, "delete_profile")

    profile_service = hass.data["cronostar"]["profile_service"]
    profile_service.delete_profile = AsyncMock()

    call = MagicMock()
    await handler(call)
    profile_service.delete_profile.assert_called_with(call)


@pytest.mark.anyio
async def test_apply_now_service(hass):
    """Test apply_now service handler."""
    storage_manager = MagicMock()
    await setup_services(hass, storage_manager)
    handler = get_handler(hass, "apply_now")

    profile_service = hass.data["cronostar"]["profile_service"]
    profile_service.get_profile_data = AsyncMock(
        return_value={
            "schedule": [
                {"time": "00:00", "value": 20.0},
                {"time": "23:59", "value": 20.0},
            ]
        }
    )

    call = MagicMock()
    call.data = {"target_entity": "climate.test", "profile_name": "Default"}

    await handler(call)
    hass.services.async_call.assert_called_with(
        "climate",
        "set_temperature",
        {"entity_id": "climate.test", "temperature": 20.0},
        blocking=False,
    )

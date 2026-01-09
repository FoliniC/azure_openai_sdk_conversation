"""Final coverage push."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.cronostar.const import DOMAIN
from custom_components.cronostar.services.profile_service import ProfileService


@pytest.fixture
def profile_service(hass, mock_storage_manager):
    settings_manager = MagicMock()
    settings_manager.load_settings = AsyncMock(return_value={})
    return ProfileService(hass, mock_storage_manager, settings_manager)


@pytest.mark.anyio
async def test_profile_service_load_profile_error(hass, profile_service):
    """Hit line 187 in load_profile (profile not found)."""
    call = MagicMock()
    call.data = {"profile_name": "NonExistent"}

    with patch.object(
        profile_service, "get_profile_data", return_value={"error": "Not found"}
    ):
        res = await profile_service.load_profile(call)
        assert "error" in res


@pytest.mark.anyio
async def test_profile_service_load_profile_exception(hass, profile_service):
    """Hit lines 199-201 in load_profile (exception)."""
    call = MagicMock()
    call.data = {"profile_name": "Error"}
    with patch.object(
        profile_service, "get_profile_data", side_effect=Exception("Fail")
    ):
        res = await profile_service.load_profile(call)
        assert "error" in res


@pytest.mark.anyio
async def test_get_profile_data_loop_branches(
    hass, profile_service, mock_storage_manager
):
    """Trigger lines 258, 260 in get_profile_data (searching profiles)."""
    # Empty profiles dict branch
    mock_storage_manager.get_cached_containers = AsyncMock(
        return_value=[
            ("f1.json", {"meta": {}, "profiles": {}})  # Empty profiles
        ]
    )
    await profile_service.get_profile_data("P1", "thermostat")


@pytest.mark.anyio
async def test_profile_service_validate_schedule_invalid_types(profile_service):
    """Hit line 546-548 in _validate_schedule."""
    # Invalid value type (non-numeric string)
    schedule = [{"time": "08:00", "value": "invalid"}]
    res = profile_service._validate_schedule(schedule)
    assert len(res) == 0


@pytest.mark.anyio
async def test_setup_services_list_all_error(hass, mock_storage_manager):
    """Hit line 124-126 in setup/services.py (exception in list_all)."""
    from custom_components.cronostar.setup.services import setup_services

    mock_hass = hass
    mock_hass.data[DOMAIN] = {"settings_manager": MagicMock()}
    await setup_services(mock_hass, mock_storage_manager)

    handler = next(
        c[0][2]
        for call in [mock_hass.services.async_register.call_args_list]
        for c in call
        if c[0][1] == "list_all_profiles"
    )

    # Force exception in storage.list_profiles
    mock_storage_manager.list_profiles.side_effect = Exception("Storage fail")

    call = MagicMock()
    res = await handler(call)
    assert "error" in res

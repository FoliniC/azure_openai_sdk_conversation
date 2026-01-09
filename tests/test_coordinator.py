"""Test the CronoStar Coordinator."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from custom_components.cronostar.coordinator import CronoStarCoordinator
from homeassistant.const import STATE_OFF


@pytest.mark.anyio
async def test_coordinator_init(hass, mock_storage_manager):
    """Test coordinator initialization."""
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.title = "Test Controller"
    entry.data = {
        "name": "Test Controller",
        "preset": "thermostat",
        "target_entity": "climate.test_thermostat",
        "global_prefix": "cronostar_thermostat_test_",
    }
    entry.options = {}

    from custom_components.cronostar.const import DOMAIN

    hass.data[DOMAIN] = {"storage_manager": mock_storage_manager}

    coordinator = CronoStarCoordinator(hass, entry)

    assert coordinator.name == "Test Controller"
    assert coordinator.preset_type == "thermostat"
    assert coordinator.target_entity == "climate.test_thermostat"
    assert coordinator.prefix == "cronostar_thermostat_test_"
    assert coordinator.selected_profile == "Default"

    await coordinator.async_initialize()

    assert coordinator.available_profiles == ["Default", "Comfort"]
    assert coordinator.selected_profile == "Default"


@pytest.mark.anyio
async def test_coordinator_apply_schedule(hass, mock_coordinator):
    """Test applying schedule."""

    # Mock target entity state
    def get_state(entity_id):
        if entity_id == "climate.test_thermostat":
            m = MagicMock()
            m.state = "20"
            return m
        return None

    hass.states.get.side_effect = get_state

    with patch("custom_components.cronostar.coordinator.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 1, 1, 12, 0, 0)

        await mock_coordinator.apply_schedule()

        assert abs(mock_coordinator.current_value - 19.33) < 0.1

        hass.services.async_call.assert_called_with(
            "climate",
            "set_temperature",
            {"entity_id": "climate.test_thermostat", "temperature": 19.33},
            blocking=False,
        )


@pytest.mark.anyio
async def test_coordinator_apply_schedule_other_domains(hass, mock_coordinator):
    """Test applying schedule for other domains (cover, input_number)."""
    # Cover
    mock_coordinator.target_entity = "cover.test"
    mock_coordinator.preset_type = "cover"

    def get_state(entity_id):
        m = MagicMock()
        m.state = "open"
        return m

    hass.states.get.side_effect = get_state

    with patch("custom_components.cronostar.coordinator.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 1, 1, 12, 0, 0)
        await mock_coordinator.apply_schedule()

        # Verify cover.set_cover_position called
        # interpolation value is 19.33, position should be int(19.33) = 19
        hass.services.async_call.assert_called_with(
            "cover",
            "set_cover_position",
            {"entity_id": "cover.test", "position": 19},
            blocking=False,
        )

    # input_number
    mock_coordinator.target_entity = "input_number.test"
    await mock_coordinator._update_target_entity(25.5)
    hass.services.async_call.assert_called_with(
        "input_number",
        "set_value",
        {"entity_id": "input_number.test", "value": 25.5},
        blocking=False,
    )


@pytest.mark.anyio
async def test_coordinator_apply_schedule_generic_switch(hass, mock_storage_manager):
    """Test applying schedule for generic switch (step interpolation)."""
    entry = MagicMock()
    entry.entry_id = "test_switch"
    entry.title = "Test Switch"
    entry.data = {
        "name": "Test Switch",
        "preset": "generic_switch",
        "target_entity": "switch.test_switch",
        "global_prefix": "cronostar_generic_switch_test_",
    }
    entry.options = {}

    from custom_components.cronostar.const import DOMAIN

    hass.data[DOMAIN] = {"storage_manager": mock_storage_manager}

    coordinator = CronoStarCoordinator(hass, entry)

    mock_storage_manager.load_profile_cached.return_value = {
        "profiles": {
            "Default": {
                "schedule": [
                    {"time": "08:00", "value": 1.0},
                    {"time": "20:00", "value": 0.0},
                ]
            }
        }
    }
    mock_storage_manager.list_profiles.return_value = ["test.json"]

    def get_state(entity_id):
        if entity_id == "switch.test_switch":
            m = MagicMock()
            m.state = STATE_OFF
            return m
        return None

    hass.states.get.side_effect = get_state

    with patch("custom_components.cronostar.coordinator.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 1, 1, 12, 0, 0)
        await coordinator.apply_schedule()
        assert coordinator.current_value == 1.0
        hass.services.async_call.assert_called_with(
            "switch", "turn_on", {"entity_id": "switch.test_switch"}, blocking=False
        )


@pytest.mark.anyio
async def test_coordinator_set_profile(hass, mock_coordinator):
    """Test setting profile."""
    mock_coordinator.available_profiles = ["Default", "Comfort"]
    await mock_coordinator.set_profile("Comfort")
    assert mock_coordinator.selected_profile == "Comfort"
    assert mock_coordinator.async_refresh.called

    await mock_coordinator.set_profile("Invalid")
    assert mock_coordinator.selected_profile == "Comfort"


@pytest.mark.anyio
async def test_coordinator_set_enabled(hass, mock_coordinator):
    """Test enabling/disabling."""
    await mock_coordinator.set_enabled(False)
    assert mock_coordinator.is_enabled is False
    assert mock_coordinator.async_refresh.called


@pytest.mark.anyio
async def test_coordinator_target_unavailable(hass, mock_coordinator):
    """Test behavior when target is unavailable."""
    hass.states.get.side_effect = None
    hass.states.get.return_value = None
    await mock_coordinator.apply_schedule()

    m = MagicMock()
    m.state = "unavailable"
    hass.states.get.return_value = m
    hass.services.async_call.reset_mock()
    await mock_coordinator.apply_schedule()
    hass.services.async_call.assert_not_called()


@pytest.mark.anyio
async def test_coordinator_async_refresh_profiles(
    hass, mock_coordinator, mock_storage_manager
):
    """Test refreshing profiles."""
    mock_storage_manager.load_profile_cached.return_value = {
        "profiles": {"NewProfile": {"schedule": []}}
    }
    await mock_coordinator.async_refresh_profiles()
    assert "NewProfile" in mock_coordinator.available_profiles
    assert mock_coordinator.selected_profile == "NewProfile"


@pytest.mark.anyio
async def test_coordinator_interpolation_wrap_around(hass, mock_coordinator):
    """Test interpolation crossing midnight."""
    schedule = [{"time": "22:00", "value": 18.0}, {"time": "02:00", "value": 22.0}]

    # 23:00 (midway between 22:00 and 02:00)
    with patch("custom_components.cronostar.coordinator.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2023, 1, 1, 23, 0, 0)
        val = mock_coordinator._interpolate_schedule(schedule)
        # (23-22)/(26-22) = 1/4
        # 18.0 + (22.0-18.0)*0.25 = 19.0
        assert val == 19.0

        # 01:00
        mock_dt.now.return_value = datetime(2023, 1, 1, 1, 0, 0)
        val = mock_coordinator._interpolate_schedule(schedule)
        # (25-22)/(26-22) = 3/4
        # 18.0 + 4*0.75 = 21.0
        assert val == 21.0


def test_minutes_to_time(mock_coordinator):
    """Test conversion."""
    assert mock_coordinator._minutes_to_time(60) == "01:00"
    assert mock_coordinator._minutes_to_time(1440) == "00:00"


def test_get_next_change(mock_coordinator):
    """Test get_next_change logic."""
    schedule = [{"time": "08:00", "value": 20.0}, {"time": "20:00", "value": 18.0}]

    with patch("custom_components.cronostar.coordinator.datetime") as mock_dt:
        # At 12:00, value is interpolated (approx 19.33). Next point is 20:00 with 18.0.
        mock_dt.now.return_value = datetime(2023, 1, 1, 12, 0, 0)
        change = mock_coordinator._get_next_change(schedule, 19.33)
        assert change[0] == "20:00"
        assert change[1] == 480  # 8 hours

        # At 21:00, next point is wrap-around 08:00
        mock_dt.now.return_value = datetime(2023, 1, 1, 21, 0, 0)
        change = mock_coordinator._get_next_change(schedule, 18.0)
        assert change[0] == "08:00"
        assert change[1] == 660  # 11 hours (3h to midnight + 8h)

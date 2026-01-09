"""Test CronoStar Select."""

from unittest.mock import AsyncMock

import pytest
from custom_components.cronostar.select import CronoStarProfileSelect


@pytest.mark.anyio
async def test_select_entity(hass, mock_coordinator):
    """Test select entity properties."""
    mock_coordinator.data = {
        "available_profiles": ["Default", "Comfort", "Night"],
        "selected_profile": "Comfort",
    }

    select = CronoStarProfileSelect(mock_coordinator)

    assert select.unique_id == "cronostar_thermostat_test_current_profile"
    assert select.options == ["Default", "Comfort", "Night"]
    assert select.current_option == "Comfort"

    # Test selection
    mock_coordinator.set_profile = AsyncMock()
    await select.async_select_option("Night")
    mock_coordinator.set_profile.assert_called_with("Night")

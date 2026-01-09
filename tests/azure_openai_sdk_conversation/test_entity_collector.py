"""Tests for the entity collector."""

from unittest.mock import MagicMock, patch

import pytest

from custom_components.azure_openai_sdk_conversation.context.entity_collector import (
    EntityCollector,
)
from custom_components.azure_openai_sdk_conversation.core.config import AgentConfig
from custom_components.azure_openai_sdk_conversation.core.logger import AgentLogger


@pytest.fixture
def mock_config(hass):
    return AgentConfig.from_dict(
        hass,
        {
            "api_key": "test",
            "api_base": "https://test",
            "chat_model": "gpt-4o",
            "exposed_entities_limit": 100,
        },
    )


@pytest.fixture
def logger(hass, mock_config):
    return AgentLogger(hass, mock_config)


@pytest.fixture
def collector(hass, mock_config, logger):
    return EntityCollector(hass, mock_config, logger)


@pytest.mark.anyio
async def test_collect_entities(hass, collector):
    """Test collecting exposed entities."""
    # Mock registries
    mock_ent_reg = MagicMock()
    mock_dev_reg = MagicMock()
    mock_area_reg = MagicMock()

    with (
        patch(
            "homeassistant.helpers.entity_registry.async_get", return_value=mock_ent_reg
        ),
        patch(
            "homeassistant.helpers.device_registry.async_get", return_value=mock_dev_reg
        ),
        patch(
            "homeassistant.helpers.area_registry.async_get", return_value=mock_area_reg
        ),
    ):
        # Mock entities in HA
        state1 = MagicMock()
        state1.entity_id = "light.living_room"
        state1.name = "Living Room Light"
        state1.state = "on"

        state2 = MagicMock()
        state2.entity_id = "switch.kitchen"
        state2.name = "Kitchen Switch"
        state2.state = "off"

        hass.states.async_all.return_value = [state1, state2]

        # Mock registry entries
        entry1 = MagicMock()
        entry1.options = {"conversation": {"should_expose": True}}
        entry1.area_id = "living_area"
        entry1.device_id = None

        entry2 = MagicMock()
        entry2.options = {"conversation": {"should_expose": False}}

        mock_ent_reg.async_get.side_effect = (
            lambda eid: entry1 if eid == "light.living_room" else entry2
        )

        # Mock area
        area1 = MagicMock()
        area1.name = "Living Room"
        mock_area_reg.async_get_area.return_value = area1

        entities = await collector.collect()

        assert len(entities) == 1
        assert entities[0]["entity_id"] == "light.living_room"
        assert entities[0]["area"] == "Living Room"
        assert entities[0]["name"] == "Living Room Light"

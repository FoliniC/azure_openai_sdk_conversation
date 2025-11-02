"""
Conversation platform setup for Azure OpenAI SDK integration.

This is the entry point called by Home Assistant to set up the conversation
platform. It instantiates the agent and registers it with the conversation system.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.components import conversation

from .core.agent import AzureOpenAIConversationAgent
from .core.config import AgentConfig
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Any,
) -> bool:
    """
    Set up the conversation platform from a config entry.

    Args:
        hass: Home Assistant instance
        config_entry: Configuration entry
        async_add_entities: Callback to add entities (unused for conversation)

    Returns:
        True if setup successful
    """
    # Merge config entry data and options
    config_dict = {
        **config_entry.data,
        **config_entry.options,
    }

    # Ensure system_message is present (backward compatibility)
    if "system_message" not in config_dict:
        config_dict["system_message"] = (
            config_dict.get("system_prompt")
            or config_dict.get("prompt")
            or llm.DEFAULT_INSTRUCTIONS_PROMPT
        )

    # Create type-safe configuration
    try:
        config = AgentConfig.from_dict(hass, config_dict)
    except Exception as err:
        _LOGGER.error("Failed to create agent configuration: %r", err)
        return False

    # Validate configuration
    errors = config.validate()
    if errors:
        _LOGGER.error("Invalid configuration: %s", "; ".join(errors))
        return False

    # Log sanitized configuration
    _LOGGER.info(
        "Setting up Azure OpenAI conversation agent: %s",
        config.to_dict(),
    )

    # Create agent
    try:
        agent = AzureOpenAIConversationAgent(hass, config)
    except Exception as err:
        _LOGGER.error("Failed to create conversation agent: %r", err)
        return False

    # Register agent with conversation system
    # Try new API first, fall back to legacy APIs
    try:
        # Home Assistant 2024.5+
        conversation.async_set_agent(hass, config_entry, agent)
        _LOGGER.debug("Registered agent using async_set_agent (with config_entry)")
    except TypeError:
        try:
            # Home Assistant 2024.1-2024.4
            conversation.async_set_agent(hass, agent)
            _LOGGER.debug(
                "Registered agent using async_set_agent (without config_entry)"
            )
        except (TypeError, AttributeError):
            # Home Assistant < 2024.1
            conversation.async_register_agent(
                hass,
                agent_id=f"{DOMAIN}.{config_entry.entry_id}",
                agent=agent,
            )
            _LOGGER.debug("Registered agent using async_register_agent")

    # Store agent reference for cleanup
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = agent

    _LOGGER.info(
        "Azure OpenAI conversation agent initialized successfully: %s",
        config.chat_model,
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> bool:
    """
    Unload conversation platform.

    Args:
        hass: Home Assistant instance
        config_entry: Configuration entry

    Returns:
        True if unload successful
    """
    # Get agent
    agent = hass.data.get(DOMAIN, {}).get(config_entry.entry_id)

    if agent:
        # Clean up agent resources
        try:
            await agent.async_close()
            _LOGGER.info("Closed conversation agent resources")
        except Exception as err:
            _LOGGER.error("Error closing agent: %r", err)

        # Remove from storage
        hass.data[DOMAIN].pop(config_entry.entry_id, None)

    return True

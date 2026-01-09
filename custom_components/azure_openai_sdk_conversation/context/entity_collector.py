"""
Entity collector for conversation context.

Collects exposed entities from Home Assistant with their state,
area, and alias information.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components import conversation
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
)
from homeassistant.helpers import (
    device_registry as dr,
)
from homeassistant.helpers import (
    entity_registry as er,
)

from ..core.config import AgentConfig
from ..core.logger import AgentLogger


class EntityCollector:
    """Collector for exposed entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: AgentConfig,
        logger: AgentLogger,
    ) -> None:
        """
        Initialize entity collector.

        Args:
            hass: Home Assistant instance
            config: Agent configuration
            logger: Logger instance
        """
        self._hass = hass
        self._config = config
        self._logger = logger

    async def collect(self) -> list[dict[str, Any]]:
        """
        Collect all exposed entities with their metadata.

        Returns:
            List of entity dicts with:
            - entity_id: Entity ID
            - name: Friendly name
            - state: Current state
            - area: Area name
            - aliases: List of aliases
        """
        area_reg = ar.async_get(self._hass)
        ent_reg = er.async_get(self._hass)
        dev_reg = dr.async_get(self._hass)

        entities = []
        count = 0
        limit = self._config.exposed_entities_limit

        for state in self._hass.states.async_all():
            # Check limit
            if limit > 0 and count >= limit:
                self._logger.warning(
                    "Entity limit reached (%d), some entities excluded", limit
                )
                break

            # Get registry entry
            entry = ent_reg.async_get(state.entity_id)

            # Filter: only exposed entities
            if not self._is_exposed(entry):
                continue

            # Get area
            area_name = self._get_area_name(entry, dev_reg, area_reg)

            # Get aliases
            aliases = self._get_aliases(entry)

            entities.append(
                {
                    "entity_id": state.entity_id,
                    "name": state.name or state.entity_id,
                    "state": state.state,
                    "area": area_name,
                    "aliases": aliases,
                }
            )

            count += 1

        self._logger.debug("Collected %d exposed entities", len(entities))

        return entities

    @staticmethod
    def _is_exposed(entry: er.RegistryEntry | None) -> bool:
        """Check if entity is exposed to conversation."""
        if entry is None:
            return False

        try:
            opts = entry.options or {}
            conv_opts = opts.get(conversation.DOMAIN) or opts.get("conversation") or {}
            val = conv_opts.get("should_expose", conv_opts.get("expose", None))
            return bool(val)
        except Exception:
            return False

    @staticmethod
    def _get_area_name(
        entry: er.RegistryEntry | None,
        dev_reg: dr.DeviceRegistry,
        area_reg: ar.AreaRegistry,
    ) -> str:
        """Get area name for entity."""
        if not entry:
            return ""

        # Try entity's area first
        area_id = entry.area_id

        # Fall back to device's area
        if not area_id and entry.device_id:
            dev = dev_reg.async_get(entry.device_id)
            if dev and dev.area_id:
                area_id = dev.area_id

        # Get area name
        if area_id:
            area = area_reg.async_get_area(area_id)
            if area and area.name:
                return area.name

        return ""

    @staticmethod
    def _get_aliases(entry: er.RegistryEntry | None) -> list[str]:
        """Get aliases for entity."""
        if not entry:
            return []

        try:
            opts = entry.options or {}
            conv_opts = opts.get(conversation.DOMAIN) or opts.get("conversation") or {}
            aliases = conv_opts.get("aliases", [])
            if isinstance(aliases, list):
                return [str(a) for a in aliases if a]
        except Exception:
            pass

        return []

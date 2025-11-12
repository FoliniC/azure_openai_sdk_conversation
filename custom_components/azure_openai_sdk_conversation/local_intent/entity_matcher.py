<<<<<<< HEAD
"""
Entity matcher for local intent handler.

Matches user tokens to Home Assistant entities using fuzzy matching.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.components import conversation

from ..core.logger import AgentLogger


class EntityMatcher:
    """Matcher for finding entities based on user tokens."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: AgentLogger,
    ) -> None:
        """
        Initialize entity matcher.

        Args:
            hass: Home Assistant instance
            logger: Logger instance
        """
        self._hass = hass
        self._logger = logger

    def match_entities(self, tokens: list[str]) -> list[dict[str, Any]]:
        """
        Match tokens to exposed entities.

        Args:
            tokens: List of normalized tokens from user input

        Returns:
            List of matched entity dicts with scoring
        """
        if not tokens:
            return []

        # Get exposed entities
        candidates = self._get_exposed_entities()

        # Score each candidate
        scored = []
        token_set = set(tokens)

        for entity in candidates:
            score = self._score_entity(entity, token_set)
            if score > 0:
                scored.append((score, entity))

        # Sort by score (descending)
        scored.sort(key=lambda x: x[0], reverse=True)

        # Return entities with top score (within 10% threshold)
        if not scored:
            return []

        top_score = scored[0][0]
        threshold = top_score * 0.9

        matched = [entity for score, entity in scored if score >= threshold]

        self._logger.debug(
            "Matched %d entities for tokens %s (top_score=%.1f)",
            len(matched),
            tokens,
            top_score,
        )

        return matched

    def _get_exposed_entities(self) -> list[dict[str, Any]]:
        """
        Get list of entities exposed to conversation/assist.

        Returns:
            List of entity dicts with {entity_id, name, state, area, domain}
        """
        area_reg = ar.async_get(self._hass)
        ent_reg = er.async_get(self._hass)
        dev_reg = dr.async_get(self._hass)

        entities = []

        for state in self._hass.states.async_all():
            entry = ent_reg.async_get(state.entity_id)

            # Filter: only exposed entities
            if not self._is_exposed(entry):
                continue

            # Only include light and switch domains for on/off
            domain = state.entity_id.split(".", 1)[0]
            if domain not in ("light", "switch"):
                continue

            # Get area
            area_name = ""
            area_id = None
            if entry:
                area_id = entry.area_id
                if not area_id and entry.device_id:
                    dev = dev_reg.async_get(entry.device_id)
                    if dev and dev.area_id:
                        area_id = dev.area_id

            if area_id:
                area = area_reg.async_get_area(area_id)
                if area and area.name:
                    area_name = area.name

            entities.append(
                {
                    "entity_id": state.entity_id,
                    "name": state.name or state.entity_id,
                    "state": state.state,
                    "area": area_name,
                    "domain": domain,
                }
            )

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

    def _score_entity(
        self,
        entity: dict[str, Any],
        token_set: set[str],
    ) -> float:
        """
        Score an entity against token set.

        Scoring:
        - Area exact match: +4.0
        - Token in name: +3.0
        - Token in entity_id: +1.5
        - Special patterns (e.g., "tavolo" ? "table"): +1.0

        Args:
            entity: Entity dict
            token_set: Set of user tokens

        Returns:
            Score (0.0 if no match)
        """
        score = 0.0

        entity_id = entity["entity_id"].lower()
        name = entity["name"].lower()
        area = entity.get("area", "").lower()

        for token in token_set:
            if not token:
                continue

            # Exact area match
            if token == area:
                score += 4.0

            # Token in name
            if token in name:
                score += 3.0

            # Token in entity_id
            if token in entity_id:
                score += 1.5

            # Special patterns
            if token == "tavolo" and any(x in name for x in ["table", "desk"]):
                score += 1.0

            if token == "tv" and any(x in name for x in ["televisore", "television"]):
                score += 1.0

        return score
=======
"""
Entity matcher for local intent handler.

Matches user tokens to Home Assistant entities using fuzzy matching.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.components import conversation

from ..core.logger import AgentLogger


class EntityMatcher:
    """Matcher for finding entities based on user tokens."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: AgentLogger,
    ) -> None:
        """
        Initialize entity matcher.

        Args:
            hass: Home Assistant instance
            logger: Logger instance
        """
        self._hass = hass
        self._logger = logger

    def match_entities(self, tokens: list[str]) -> list[dict[str, Any]]:
        """
        Match tokens to exposed entities.

        Args:
            tokens: List of normalized tokens from user input

        Returns:
            List of matched entity dicts with scoring
        """
        if not tokens:
            return []

        # Get exposed entities
        candidates = self._get_exposed_entities()

        # Score each candidate
        scored = []
        token_set = set(tokens)

        for entity in candidates:
            score = self._score_entity(entity, token_set)
            if score > 0:
                scored.append((score, entity))

        # Sort by score (descending)
        scored.sort(key=lambda x: x[0], reverse=True)

        # Return entities with top score (within 10% threshold)
        if not scored:
            return []

        top_score = scored[0][0]
        threshold = top_score * 0.9

        matched = [entity for score, entity in scored if score >= threshold]

        self._logger.debug(
            "Matched %d entities for tokens %s (top_score=%.1f)",
            len(matched),
            tokens,
            top_score,
        )

        return matched

    def _get_exposed_entities(self) -> list[dict[str, Any]]:
        """
        Get list of entities exposed to conversation/assist.

        Returns:
            List of entity dicts with {entity_id, name, state, area, domain}
        """
        area_reg = ar.async_get(self._hass)
        ent_reg = er.async_get(self._hass)
        dev_reg = dr.async_get(self._hass)

        entities = []

        for state in self._hass.states.async_all():
            entry = ent_reg.async_get(state.entity_id)

            # Filter: only exposed entities
            if not self._is_exposed(entry):
                continue

            # Only include light and switch domains for on/off
            domain = state.entity_id.split(".", 1)[0]
            if domain not in ("light", "switch"):
                continue

            # Get area
            area_name = ""
            area_id = None
            if entry:
                area_id = entry.area_id
                if not area_id and entry.device_id:
                    dev = dev_reg.async_get(entry.device_id)
                    if dev and dev.area_id:
                        area_id = dev.area_id

            if area_id:
                area = area_reg.async_get_area(area_id)
                if area and area.name:
                    area_name = area.name

            entities.append(
                {
                    "entity_id": state.entity_id,
                    "name": state.name or state.entity_id,
                    "state": state.state,
                    "area": area_name,
                    "domain": domain,
                }
            )

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

    def _score_entity(
        self,
        entity: dict[str, Any],
        token_set: set[str],
    ) -> float:
        """
        Score an entity against token set.

        Scoring:
        - Area exact match: +4.0
        - Token in name: +3.0
        - Token in entity_id: +1.5
        - Special patterns (e.g., "tavolo" ? "table"): +1.0

        Args:
            entity: Entity dict
            token_set: Set of user tokens

        Returns:
            Score (0.0 if no match)
        """
        score = 0.0

        entity_id = entity["entity_id"].lower()
        name = entity["name"].lower()
        area = entity.get("area", "").lower()

        for token in token_set:
            if not token:
                continue

            # Exact area match
            if token == area:
                score += 4.0

            # Token in name
            if token in name:
                score += 3.0

            # Token in entity_id
            if token in entity_id:
                score += 1.5

            # Special patterns
            if token == "tavolo" and any(x in name for x in ["table", "desk"]):
                score += 1.0

            if token == "tv" and any(x in name for x in ["televisore", "television"]):
                score += 1.0

        return score
>>>>>>> e8f918df5a0f1a917b9e8681179363a6574e13f1

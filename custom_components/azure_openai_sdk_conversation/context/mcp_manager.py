"""
MCP (Model Context Protocol) Server Manager.

Manages stateful context tracking across conversation turns,
sending only delta updates instead of full state every time.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from homeassistant.core import HomeAssistant

from ..core.logger import AgentLogger


@dataclass
class EntityState:
    """Representation of an entity's state."""

    entity_id: str
    name: str
    state: str
    area: str
    aliases: list[str]
    last_updated: str

    def __eq__(self, other: object) -> bool:
        """Two states are equal if state value is identical."""
        if not isinstance(other, EntityState):
            return False
        return self.entity_id == other.entity_id and self.state == other.state

    def __hash__(self) -> int:
        return hash((self.entity_id, self.state))


class MCPManager:
    """Manager for MCP state tracking."""

    def __init__(
        self,
        hass: HomeAssistant,
        ttl_seconds: int,
        logger: AgentLogger,
    ) -> None:
        """
        Initialize MCP manager.

        Args:
            hass: Home Assistant instance
            ttl_seconds: Time-to-live for conversation state
            logger: Logger instance
        """
        self._hass = hass
        self._ttl_seconds = ttl_seconds
        self._logger = logger

        # State storage: conversation_id -> {entity_id: EntityState}
        self._conversations: dict[str, dict[str, EntityState]] = {}

        # Last update times: conversation_id -> timestamp
        self._last_updated: dict[str, datetime] = {}

        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the MCP manager and cleanup task."""
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        self._logger.info("MCP Manager started (TTL=%ds)", self._ttl_seconds)

    async def stop(self) -> None:
        """Stop the MCP manager."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        self._logger.info("MCP Manager stopped")

    def is_new_conversation(self, conversation_id: str) -> bool:
        """Check if this is a new conversation (needs full context)."""
        return conversation_id not in self._conversations

    def build_initial_prompt(
        self,
        conversation_id: str,
        entities: list[dict[str, Any]],
        base_prompt: str,
    ) -> str:
        """
        Build initial system prompt with full entity state.

        Args:
            conversation_id: Conversation ID
            entities: List of current entities
            base_prompt: Base prompt template

        Returns:
            Full system prompt
        """
        # Convert to EntityState objects
        entity_states = {}
        for e in entities:
            state = EntityState(
                entity_id=e["entity_id"],
                name=e["name"],
                state=e["state"],
                area=e.get("area", ""),
                aliases=e.get("aliases", []),
                last_updated=datetime.now(timezone.utc).isoformat(),
            )
            entity_states[e["entity_id"]] = state

        # Store state
        self._conversations[conversation_id] = entity_states
        self._last_updated[conversation_id] = datetime.now(timezone.utc)

        # Build prompt with full context
        entity_csv = self._format_entities_csv(entity_states.values())

        prompt = f"""{base_prompt}

**Entity State Information** (Initial Full State):
Current time: {datetime.now(timezone.utc).isoformat()}

{entity_csv}

This is your initial state snapshot. In subsequent messages, you will only receive updates for entities that changed state.
"""

        self._logger.debug(
            "MCP: Created initial state for conversation %s (%d entities)",
            conversation_id,
            len(entity_states),
        )

        return prompt

    def build_delta_prompt(
        self,
        conversation_id: str,
        entities: list[dict[str, Any]],
    ) -> Optional[str]:
        """
        Build delta prompt with only changed entities.

        Args:
            conversation_id: Conversation ID
            entities: Current entity list

        Returns:
            Delta prompt if changes exist, None otherwise
        """
        if conversation_id not in self._conversations:
            self._logger.warning(
                "MCP: Conversation %s not found, should use initial prompt",
                conversation_id,
            )
            return None

        stored_states = self._conversations[conversation_id]

        # Build current states
        current_states = {}
        for e in entities:
            state = EntityState(
                entity_id=e["entity_id"],
                name=e["name"],
                state=e["state"],
                area=e.get("area", ""),
                aliases=e.get("aliases", []),
                last_updated=datetime.now(timezone.utc).isoformat(),
            )
            current_states[e["entity_id"]] = state

        # Find changes
        changed = []
        new = []
        removed_ids = set()

        # Check for changes and new entities
        for entity_id, current in current_states.items():
            if entity_id not in stored_states:
                new.append(current)
            elif stored_states[entity_id] != current:
                self._logger.debug(
                    "MCP Delta: State change for '%s': from '%s' to '%s'",
                    entity_id,
                    stored_states[entity_id].state,
                    current.state,
                )
                changed.append(current)

        # Check for removed entities
        current_ids = set(current_states.keys())
        removed_ids = set(stored_states.keys()) - current_ids

        # Update stored state
        self._conversations[conversation_id] = current_states
        self._last_updated[conversation_id] = datetime.now(timezone.utc)

        # Return None if no changes
        if not changed and not new and not removed_ids:
            return None

        # Build delta prompt
        parts = [
            f"**State Update** (Delta at {datetime.now(timezone.utc).isoformat()}):"
        ]

        if changed:
            parts.append(f"\nChanged entities ({len(changed)}):")
            parts.append(self._format_entities_csv(changed))

        if new:
            parts.append(f"\nNew entities ({len(new)}):")
            parts.append(self._format_entities_csv(new))

        if removed_ids:
            parts.append(f"\nRemoved entities: {', '.join(sorted(removed_ids))}")

        delta = "\n".join(parts)

        self._logger.debug(
            "MCP: Delta for conversation %s: %d changed, %d new, %d removed",
            conversation_id,
            len(changed),
            len(new),
            len(removed_ids),
        )

        return delta

    @staticmethod
    def _format_entities_csv(states: list[EntityState]) -> str:
        """Format entities as CSV grouped by area."""
        # Group by area
        by_area: dict[str, list[EntityState]] = {}
        for state in states:
            area = state.area or "_no_area"
            if area not in by_area:
                by_area[area] = []
            by_area[area].append(state)

        # Format
        lines = []
        for area in sorted(by_area.keys()):
            if area == "_no_area":
                lines.append("\nEntities without area:")
            else:
                lines.append(f"\nEntities in: {area}")

            lines.append("```csv")
            lines.append("entity_id;name;state;aliases")

            for state in sorted(by_area[area], key=lambda s: s.entity_id):
                aliases_str = "/".join(state.aliases) if state.aliases else ""
                lines.append(
                    f"{state.entity_id};{state.name};{state.state};{aliases_str}"
                )

            lines.append("```")

        return "\n".join(lines)

    async def _periodic_cleanup(self) -> None:
        """Periodically clean up old conversations."""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                await self._cleanup_old_conversations()
            except asyncio.CancelledError:
                break
            except Exception as err:
                self._logger.error("MCP cleanup error: %r", err)

    async def _cleanup_old_conversations(self) -> None:
        """Remove conversations older than TTL."""
        now = datetime.now(timezone.utc)
        to_remove = []

        for conv_id, last_update in self._last_updated.items():
            age_seconds = (now - last_update).total_seconds()
            if age_seconds > self._ttl_seconds:
                to_remove.append(conv_id)

        for conv_id in to_remove:
            del self._conversations[conv_id]
            del self._last_updated[conv_id]
            self._logger.debug("MCP: Cleaned up conversation %s (inactive)", conv_id)

        if to_remove:
            self._logger.info(
                "MCP: Cleaned up %d inactive conversations", len(to_remove)
            )

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about MCP state."""
        return {
            "active_conversations": len(self._conversations),
            "total_entities_tracked": sum(
                len(states) for states in self._conversations.values()
            ),
            "ttl_seconds": self._ttl_seconds,
        }

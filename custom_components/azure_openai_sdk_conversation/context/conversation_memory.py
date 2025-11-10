"""
Conversation memory manager with sliding window and token limits.

Uses tiktoken for accurate token counting and FIFO eviction strategy.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

from homeassistant.core import HomeAssistant

from ..core.config import AgentConfig
from ..core.logger import AgentLogger
from ..core.state import MessageEntry, ConversationWindow, AgentState
from ..core.interfaces import IMemoryManager

_LOGGER = logging.getLogger(__name__)


class ConversationMemoryManager(IMemoryManager):
    """
    Manages conversation history with sliding window and token limits.

    Features:
    - FIFO eviction when token limit exceeded
    - Accurate token counting with tiktoken
    - Custom tags for context grouping
    - In-memory only (no persistence)
    - Optional system message preservation
    """

    def __init__(
        self,
        hass: HomeAssistant,
        config: AgentConfig,
        logger: AgentLogger,
    ) -> None:
        """
        Initialize memory manager.

        Args:
            hass: Home Assistant instance
            config: Agent configuration
            logger: Logger instance
        """
        self._hass = hass
        self._config = config
        self._logger = logger

        self._tiktoken = None
        self._encoding = None
        self._base_tool_tokens = 0

        # Storage: conversation_id -> ConversationWindow
        self._windows: dict[str, ConversationWindow] = {}

        # Lock for thread safety
        self._lock = asyncio.Lock()

        # Configuration
        self._max_tokens = getattr(config, "sliding_window_max_tokens", 4000)
        self._preserve_system = getattr(config, "sliding_window_preserve_system", True)

        self._logger.info(
            "ConversationMemoryManager initialized: max_tokens=%d, preserve_system=%s",
            self._max_tokens,
            self._preserve_system,
        )

    async def async_setup(self) -> None:
        """Asynchronously initialize the tokenizer."""
        try:
            import tiktoken

            self._tiktoken = tiktoken
            self._encoding = await self._hass.async_add_executor_job(
                tiktoken.get_encoding, "cl100k_base"
            )
            self._logger.debug("Tiktoken encoding 'cl100k_base' loaded successfully.")
        except ImportError:
            self._logger.error(
                "tiktoken not installed. Install with: pip install tiktoken"
            )
            raise
        except Exception as err:
            self._logger.error("Failed to load tiktoken encoding: %r", err)
            raise

    async def async_set_base_tool_tokens(self, count: int) -> None:
        """Set the base token count for tool definitions and update existing windows."""
        async with self._lock:
            delta = count - self._base_tool_tokens
            self._base_tool_tokens = count

            # Update all existing windows with the new base token count
            for window in self._windows.values():
                window.current_tokens += delta
                # Ensure eviction is checked if tokens were added
                if delta > 0:
                    self._evict_if_needed(window)

            self._logger.info(
                "Base tool token count set to %d. Updated %d existing windows.",
                count,
                len(self._windows),
            )

    async def async_set_system_prompt(self, conversation_id: str, content: str) -> None:
        """Add or update the system prompt for a conversation, and manage token counts."""
        async with self._lock:
            # Ensure the window exists
            if conversation_id not in self._windows:
                self._windows[conversation_id] = ConversationWindow(
                    conversation_id=conversation_id,
                    messages=[],
                    max_tokens=self._max_tokens,
                    current_tokens=self._base_tool_tokens,
                    preserve_system=self._preserve_system,
                    created_at=datetime.now(timezone.utc),
                    last_updated=datetime.now(timezone.utc),
                )

            window = self._windows[conversation_id]

            new_token_count = self._count_tokens(content)

            # Find existing system prompt
            existing_prompt_idx = -1
            for i, msg in enumerate(window.messages):
                if msg.role == "system":
                    existing_prompt_idx = i
                    break

            if existing_prompt_idx != -1:
                # Update existing system prompt
                old_token_count = window.messages[existing_prompt_idx].token_count
                token_delta = new_token_count - old_token_count

                window.messages[existing_prompt_idx].content = content
                window.messages[existing_prompt_idx].token_count = new_token_count
                window.messages[existing_prompt_idx].timestamp = datetime.now(
                    timezone.utc
                )
                window.current_tokens += token_delta

                self._logger.debug(
                    "Updated system prompt for conv=%s. Token delta: %d, new total: %d",
                    conversation_id,
                    token_delta,
                    window.current_tokens,
                )
            else:
                # Insert new system prompt at the beginning
                system_message = MessageEntry(
                    role="system",
                    content=content,
                    timestamp=datetime.now(timezone.utc),
                    token_count=new_token_count,
                    conversation_id=conversation_id,
                )
                window.messages.insert(0, system_message)
                window.current_tokens += new_token_count
                self._logger.debug(
                    "Added new system prompt for conv=%s. Tokens: %d, new total: %d",
                    conversation_id,
                    new_token_count,
                    window.current_tokens,
                )

            # Check if the window is still over budget after adding the system prompt
            if window.current_tokens > window.max_tokens:
                self._logger.error(
                    "Sliding window max_tokens (%d) is too small to fit the initial prompt (Check 1) "
                    "(tools + system prompt). Current initial prompt size: %d tokens. "
                    "Please increase 'sliding_window_max_tokens' in the integration options.",
                    window.max_tokens,
                    window.current_tokens,
                )

            # Evict if necessary after any change
            self._evict_if_needed(window)

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tags: Optional[set[str]] = None,
    ) -> None:
        """
        Add message to conversation history.

        Applies FIFO eviction if token limit exceeded.

        Args:
            conversation_id: Conversation ID
            role: Message role (user/assistant/system/tool)
            content: Message content
            tags: Optional custom tags for grouping
        """
        async with self._lock:
            # Create window if not exists
            if conversation_id not in self._windows:
                self._windows[conversation_id] = ConversationWindow(
                    conversation_id=conversation_id,
                    messages=[],
                    max_tokens=self._max_tokens,
                    current_tokens=self._base_tool_tokens,  # Start with base tool tokens
                    preserve_system=self._preserve_system,
                    created_at=datetime.now(timezone.utc),
                    last_updated=datetime.now(timezone.utc),
                )

            window = self._windows[conversation_id]

            # Count tokens
            token_count = self._count_tokens(content)

            # Create message entry
            message = MessageEntry(
                role=role,
                content=content,
                timestamp=datetime.now(timezone.utc),
                token_count=token_count,
                conversation_id=conversation_id,
                tags=tags or set(),
            )

            # Add to window
            window.messages.append(message)
            window.current_tokens += token_count
            window.last_updated = datetime.now(timezone.utc)

            # Apply FIFO eviction if needed
            self._evict_if_needed(window)

            self._logger.debug(
                "Added message to conv=%s: role=%s, tokens=%d, total_tokens=%d/%d",
                conversation_id,
                role,
                token_count,
                window.current_tokens,
                window.max_tokens,
            )

    async def get_messages(
        self,
        conversation_id: str,
        tag_filter: Optional[set[str]] = None,
    ) -> list[dict[str, Any]]:
        """
        Get messages formatted for LLM API.

        Args:
            conversation_id: Conversation ID
            tag_filter: Optional tag filter (if set, only return messages with ANY of these tags)

        Returns:
            List of message dicts for LLM API
        """
        async with self._lock:
            if conversation_id not in self._windows:
                return []

            window = self._windows[conversation_id]
            messages = window.messages

            # Apply tag filter if specified
            if tag_filter:
                messages = [
                    msg
                    for msg in messages
                    if msg.tags & tag_filter  # Intersection
                ]

            return [msg.to_dict() for msg in messages]

    async def reset_conversation(self, conversation_id: str) -> None:
        """
        Reset conversation history (complete reset).

        Args:
            conversation_id: Conversation ID to reset
        """
        async with self._lock:
            if conversation_id in self._windows:
                del self._windows[conversation_id]
                self._logger.info("Reset conversation: %s", conversation_id)

    def get_stats(self, conversation_id: str) -> dict[str, Any]:
        """
        Get memory statistics for conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            Statistics dict
        """
        if conversation_id not in self._windows:
            return {
                "exists": False,
                "conversation_id": conversation_id,
            }

        window = self._windows[conversation_id]
        stats = window.get_stats()
        stats["exists"] = True

        # Add tag distribution
        tag_counts = defaultdict(int)
        for msg in window.messages:
            for tag in msg.tags:
                tag_counts[tag] += 1

        stats["tag_distribution"] = dict(tag_counts)

        return stats

    def get_all_conversations(self) -> list[str]:
        """Get list of all active conversation IDs."""
        return list(self._windows.keys())

    # -------------------------------------------------------------------------
    # Internal Methods
    # -------------------------------------------------------------------------

    def _count_tokens(self, text: str) -> int:
        """
        Count tokens using tiktoken.

        Args:
            text: Text to count

        Returns:
            Token count
        """
        if not self._encoding:
            self._logger.error(
                "Tiktoken encoding not initialized. Cannot count tokens."
            )
            return int(len(text) / 4)

        try:
            return len(self._encoding.encode(text))
        except Exception as err:
            # Fallback to character-based estimation
            self._logger.warning("tiktoken failed, using fallback: %r", err)
            return int(len(text) / 4)  # ~4 chars per token

    def _evict_if_needed(self, window: ConversationWindow) -> None:
        """
        Apply FIFO eviction if token limit exceeded.

        Preserves system messages if configured.

        Args:
            window: Conversation window to evict from
        """
        while window.current_tokens > window.max_tokens:
            if not window.messages:
                break

            # Find first evictable message (FIFO)
            evict_idx = None
            for idx, msg in enumerate(window.messages):
                # Skip system messages if preserve_system is True
                if window.preserve_system and msg.role == "system":
                    continue

                evict_idx = idx
                break

            if evict_idx is None:
                # No evictable messages (all system messages)
                self._logger.warning(
                    "Cannot evict: all messages are system messages (conv=%s)",
                    window.conversation_id,
                )
                break

            # Evict message
            evicted = window.messages.pop(evict_idx)
            window.current_tokens -= evicted.token_count

            self._logger.debug(
                "Evicted message (FIFO): conv=%s, role=%s, tokens=%d, remaining=%d",
                window.conversation_id,
                evicted.role,
                evicted.token_count,
                window.current_tokens,
            )

    async def get_state(self, conversation_id: str) -> Optional[AgentState]:
        """
        Get complete agent state for conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            AgentState or None if not found
        """
        async with self._lock:
            if conversation_id not in self._windows:
                return None

            window = self._windows[conversation_id]

            return AgentState(
                conversation_id=conversation_id,
                window=window,
            )

    async def update_state(self, conversation_id: str, state: AgentState) -> None:
        """
        Update conversation state.

        Args:
            conversation_id: Conversation ID
            state: New state
        """
        async with self._lock:
            self._windows[conversation_id] = state.window
            self._logger.debug("Updated state for conv=%s", conversation_id)

"""
Abstract interfaces for LangGraph migration preparation.

Minimal abstraction layer to decouple agent logic from HA-specific implementations.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Optional, Protocol

from .state import AgentState


class IStateManager(Protocol):
    """Interface for state management."""
    
    async def get_state(self, conversation_id: str) -> Optional[AgentState]:
        """Get current state for conversation."""
        ...
    
    async def update_state(self, conversation_id: str, state: AgentState) -> None:
        """Update conversation state."""
        ...
    
    async def reset_state(self, conversation_id: str) -> None:
        """Reset conversation state."""
        ...


class ILLMClient(Protocol):
    """Interface for LLM clients."""
    
    async def complete(
        self,
        messages: list[dict[str, Any]],
        conversation_id: Optional[str] = None,
        user_message: str = "",
        track_callback: Optional[callable] = None,
    ) -> tuple[str, dict[str, int]]:
        """Complete conversation with text response."""
        ...
    
    async def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        conversation_id: Optional[str] = None,
        user_message: str = "",
        track_callback: Optional[callable] = None,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        """Complete conversation with tool calling support."""
        ...
    
    async def close(self) -> None:
        """Clean up resources."""
        ...


class IMemoryManager(ABC):
    """Abstract interface for conversation memory management."""
    
    @abstractmethod
    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tags: Optional[set[str]] = None,
    ) -> None:
        """Add message to conversation history."""
        pass
    
    @abstractmethod
    async def get_messages(
        self,
        conversation_id: str,
        tag_filter: Optional[set[str]] = None,
    ) -> list[dict[str, Any]]:
        """Get messages for LLM context."""
        pass
    
    @abstractmethod
    async def reset_conversation(self, conversation_id: str) -> None:
        """Reset conversation history."""
        pass
    
    @abstractmethod
    def get_stats(self, conversation_id: str) -> dict[str, Any]:
        """Get memory statistics."""
        pass

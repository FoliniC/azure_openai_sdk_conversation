"""
Typed state objects for agent execution.

Designed for easy migration to LangGraph StateDict in the future.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class MessageEntry:
    """Single message in conversation history."""

    role: str  # "user" | "assistant" | "system" | "tool"
    content: str
    timestamp: datetime
    token_count: int
    conversation_id: str
    tags: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for LLM API."""
        return {
            "role": self.role,
            "content": self.content,
        }

    def to_langgraph_message(self) -> dict[str, Any]:
        """Convert to LangGraph-compatible message format."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "tags": list(self.tags),
            "metadata": self.metadata,
        }


@dataclass
class ConversationWindow:
    """Conversation memory window with token limits."""

    conversation_id: str
    messages: list[MessageEntry]
    max_tokens: int
    current_tokens: int
    preserve_system: bool
    created_at: datetime
    last_updated: datetime

    def get_llm_messages(self) -> list[dict[str, Any]]:
        """Get messages formatted for LLM API."""
        return [msg.to_dict() for msg in self.messages]

    def get_stats(self) -> dict[str, Any]:
        """Get window statistics."""
        return {
            "conversation_id": self.conversation_id,
            "message_count": len(self.messages),
            "current_tokens": self.current_tokens,
            "max_tokens": self.max_tokens,
            "utilization": (self.current_tokens / self.max_tokens * 100)
            if self.max_tokens > 0
            else 0.0,
            "age_seconds": (
                datetime.now(timezone.utc) - self.created_at
            ).total_seconds(),
        }


@dataclass
class AgentState:
    """
    Complete agent state for a conversation.

    Minimal structure for future LangGraph migration.
    """

    conversation_id: str
    window: ConversationWindow
    current_intent: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_langgraph_state(self) -> dict[str, Any]:
        """
        Convert to LangGraph StateDict format.

        Future implementation will map to actual LangGraph state schema.
        """
        return {
            "conversation_id": self.conversation_id,
            "messages": [msg.to_langgraph_message() for msg in self.window.messages],
            "current_intent": self.current_intent,
            "metadata": self.metadata,
        }

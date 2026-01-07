# ============================================================================
# core/__init__.py
# ============================================================================
"""Core modules for Azure OpenAI conversation agent."""

from .config import AgentConfig
from .logger import AgentLogger
from .state import AgentState, MessageEntry, ConversationWindow
from .interfaces import IStateManager, ILLMClient, IMemoryManager

__all__ = [
    "AgentConfig",
    "AgentLogger",
    "AgentState",
    "MessageEntry",
    "ConversationWindow",
    "IStateManager",
    "ILLMClient",
    "IMemoryManager",
]

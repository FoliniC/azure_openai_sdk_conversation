# ============================================================================
# core/__init__.py
# ============================================================================
"""Core modules for Azure OpenAI conversation agent."""

from .config import AgentConfig
from .interfaces import ILLMClient, IMemoryManager, IStateManager
from .logger import AgentLogger
from .state import AgentState, ConversationWindow, MessageEntry

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

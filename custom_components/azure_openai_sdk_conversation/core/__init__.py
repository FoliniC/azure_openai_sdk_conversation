# ============================================================================
# core/__init__.py
# ============================================================================
"""Core modules for Azure OpenAI conversation agent."""

from .agent import AzureOpenAIConversationAgent
from .config import AgentConfig
from .logger import AgentLogger
from .state import AgentState, MessageEntry, ConversationWindow
from .interfaces import IStateManager, ILLMClient, IMemoryManager

__all__ = [
    "AzureOpenAIConversationAgent",
    "AgentConfig",
    "AgentLogger",
    "AgentState",
    "MessageEntry",
    "ConversationWindow",
    "IStateManager",
    "ILLMClient",
    "IMemoryManager",
]

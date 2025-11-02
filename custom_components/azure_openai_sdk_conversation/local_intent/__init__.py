# ============================================================================
# intent/__init__.py
# ============================================================================
"""Local intent handling modules."""

from .local_handler import LocalIntentHandler
from .text_normalizer import TextNormalizer
from .entity_matcher import EntityMatcher

__all__ = [
    "LocalIntentHandler",
    "TextNormalizer",
    "EntityMatcher",
]

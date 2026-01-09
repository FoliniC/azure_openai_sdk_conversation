# ============================================================================
# intent/__init__.py
# ============================================================================
"""Local intent handling modules."""

from .entity_matcher import EntityMatcher
from .local_handler import LocalIntentHandler
from .text_normalizer import TextNormalizer

__all__ = [
    "LocalIntentHandler",
    "TextNormalizer",
    "EntityMatcher",
]

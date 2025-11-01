"""
Text normalization with vocabulary/synonym support.

Applies regex rules and token substitutions to normalize user input.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from homeassistant.core import HomeAssistant

from ..core.config import AgentConfig
from ..core.logger import AgentLogger


class TextNormalizer:
    """Text normalizer with configurable vocabulary."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        config: AgentConfig,
        logger: AgentLogger,
    ) -> None:
        """
        Initialize text normalizer.
        
        Args:
            hass: Home Assistant instance
            config: Agent configuration
            logger: Logger instance
        """
        self._hass = hass
        self._config = config
        self._logger = logger
        
        # Vocabulary data
        self._token_synonyms: dict[str, str] = {}
        self._regex_rules: list[tuple[re.Pattern, str]] = []
        self._loaded = False
    
    async def ensure_loaded(self) -> None:
        """Load vocabulary if not already loaded."""
        if self._loaded:
            return
        
        # Get default vocabulary
        vocab = self._get_default_vocabulary()
        
        # Load custom synonyms file if configured
        if self._config.synonyms_file and os.path.isfile(self._config.synonyms_file):
            try:
                custom_vocab = await self._load_synonyms_file(
                    self._config.synonyms_file
                )
                # Merge with default
                vocab = self._merge_vocabularies(vocab, custom_vocab)
                
                self._logger.info(
                    "Loaded custom synonyms from %s", self._config.synonyms_file
                )
            except Exception as err:
                self._logger.error(
                    "Failed to load synonyms file %s: %r",
                    self._config.synonyms_file,
                    err,
                )
        
        # Build token synonyms map
        self._token_synonyms = {}
        for source, target in vocab.get("token_synonyms", {}).items():
            if isinstance(source, str) and isinstance(target, str):
                self._token_synonyms[source.strip().lower()] = target.strip().lower()
        
        # Compile regex rules
        self._regex_rules = []
        for rule in vocab.get("regex_rules", []):
            pattern = rule.get("pattern", "")
            replacement = rule.get("replace", "")
            if pattern and isinstance(pattern, str):
                try:
                    compiled = re.compile(pattern, flags=re.IGNORECASE)
                    self._regex_rules.append((compiled, replacement))
                except re.error as rex:
                    self._logger.warning(
                        "Invalid regex pattern in vocabulary: %s (error: %s)",
                        pattern,
                        rex,
                    )
        
        self._loaded = True
        self._logger.debug(
            "Vocabulary loaded: %d synonyms, %d regex rules",
            len(self._token_synonyms),
            len(self._regex_rules),
        )
    
    def normalize(self, text: str) -> str:
        """
        Normalize text using vocabulary rules.
        
        Args:
            text: Raw user input
            
        Returns:
            Normalized text
        """
        if not text:
            return ""
        
        s = text.strip()
        
        # Apply regex rules first
        for pattern, replacement in self._regex_rules:
            s = pattern.sub(replacement, s)
        
        # Apply token synonyms (full-phrase substitutions)
        # Process longer phrases first to avoid partial matches
        for source in sorted(self._token_synonyms.keys(), key=len, reverse=True):
            target = self._token_synonyms[source]
            # Use word boundaries to avoid partial matches
            try:
                s = re.sub(
                    rf"\b{re.escape(source)}\b",
                    target,
                    s,
                    flags=re.IGNORECASE,
                )
            except re.error:
                # Fallback to simple replace if regex fails
                s = s.replace(source, target)
        
        # Clean up multiple spaces
        s = re.sub(r"\s{2,}", " ", s).strip()
        
        # Normalize to lowercase (preserving accents)
        s = s.lower()
        
        return s
    
    async def _load_synonyms_file(self, path: str) -> dict[str, Any]:
        """Load synonyms from JSON file."""
        def _read() -> dict[str, Any]:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        
        return await self._hass.async_add_executor_job(_read)
    
    @staticmethod
    def _get_default_vocabulary() -> dict[str, Any]:
        """Get default vocabulary specification."""
        return {
            "token_synonyms": {
                # Verbs (Italian)
                "disattiva": "spegni",
                "disattivare": "spegni",
                "spegnere": "spegni",
                "spengi": "spegni",  # Common typo
                "off": "spegni",
                
                "attiva": "accendi",
                "attivare": "accendi",
                "accendere": "accendi",
                "on": "accendi",
                
                # Objects/Rooms (Italian)
                "luci": "luce",
                "lampada": "luce",
                "lampadario": "luce",
                "faretti": "luce",
                "spot": "luce",
                
                "salotto": "soggiorno",
                "sala": "soggiorno",
                
                "bagni": "bagno",
                
                # Common collocations
                "luce tavolo": "tavolo",
                "luci tavolo": "tavolo",
                "tavolo cucina": "tavolo",
                "luce cucina": "cucina",
                "luci cucina": "cucina",
            },
            "regex_rules": [
                # Remove articles before verbs
                {
                    "pattern": r"\b(spegni|accendi)\s+(il|lo|la|i|gli|le|l')\s+",
                    "replace": r"\1 ",
                },
                # Simplify "luce del tavolo" ? "tavolo"
                {
                    "pattern": r"\b(luce|luci)\s+(del|della|dello|dei|degli|delle)\s+(tavolo)\b",
                    "replace": r"\3",
                },
                # Simplify "luce tavolo" ? "tavolo"
                {
                    "pattern": r"\b(luce|luci)\s+tavolo\b",
                    "replace": "tavolo",
                },
                # Simplify "tavolo cucina" ? "tavolo"
                {
                    "pattern": r"\btavolo\s+cucina\b",
                    "replace": "tavolo",
                },
                # Collapse multiple spaces
                {
                    "pattern": r"\s{2,}",
                    "replace": " ",
                },
            ],
        }
    
    @staticmethod
    def _merge_vocabularies(
        base: dict[str, Any],
        custom: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Merge two vocabulary specifications.
        
        Custom rules are added to base rules (not replaced).
        """
        merged = {
            "token_synonyms": dict(base.get("token_synonyms", {})),
            "regex_rules": list(base.get("regex_rules", [])),
        }
        
        # Merge token synonyms (custom overrides base)
        custom_synonyms = custom.get("token_synonyms", {})
        if isinstance(custom_synonyms, dict):
            merged["token_synonyms"].update(custom_synonyms)
        
        # Append regex rules
        custom_rules = custom.get("regex_rules", [])
        if isinstance(custom_rules, list):
            merged["regex_rules"].extend(custom_rules)
        
        return merged
    
    async def close(self) -> None:
        """Clean up resources."""
        pass
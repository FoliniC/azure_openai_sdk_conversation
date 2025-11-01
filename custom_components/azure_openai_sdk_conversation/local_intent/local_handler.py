"""
Local intent handler for simple commands (turn_on/turn_off).

Handles common home automation commands locally without LLM,
reducing latency and costs.
"""

from __future__ import annotations

from typing import Optional

from homeassistant.components import conversation
from homeassistant.components.conversation import ConversationInput, ConversationResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent as intent_helper

from .text_normalizer import TextNormalizer
from .entity_matcher import EntityMatcher
from ..core.config import AgentConfig
from ..core.logger import AgentLogger


class LocalIntentHandler:
    """Handler for local intent processing."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        config: AgentConfig,
        logger: AgentLogger,
    ) -> None:
        """
        Initialize local intent handler.
        
        Args:
            hass: Home Assistant instance
            config: Agent configuration
            logger: Logger instance
        """
        self._hass = hass
        self._config = config
        self._logger = logger
        
        # Initialize normalizer and matcher
        self._normalizer = TextNormalizer(
            hass=hass,
            config=config,
            logger=logger,
        )
        
        self._matcher = EntityMatcher(
            hass=hass,
            logger=logger,
        )
        
        self._logger.debug("LocalIntentHandler initialized")
    
    async def ensure_vocabulary_loaded(self) -> None:
        """Ensure vocabulary/synonyms are loaded."""
        await self._normalizer.ensure_loaded()
    
    def normalize_text(self, text: str) -> str:
        """
        Normalize text using vocabulary rules.
        
        Args:
            text: Raw user input text
            
        Returns:
            Normalized text
        """
        if not self._config.vocabulary_enable:
            return text.strip()
        
        return self._normalizer.normalize(text)
    
    async def try_handle(
        self,
        normalized_text: str,
        user_input: ConversationInput,
    ) -> Optional[ConversationResult]:
        """
        Try to handle request with local intent.
        
        Args:
            normalized_text: Normalized user text
            user_input: Original conversation input
            
        Returns:
            ConversationResult if handled locally, None otherwise
        """
        if not self._config.local_intent_enable:
            return None
        
        # Parse intent
        intent_data = self._parse_onoff_intent(normalized_text)
        if not intent_data:
            return None
        
        action, tokens = intent_data
        self._logger.debug(
            "Local intent parsed: action=%s, tokens=%s", action, tokens
        )
        
        # Match entities
        entities = self._matcher.match_entities(tokens)
        if not entities:
            self._logger.info(
                "Local intent recognized but no matching entities for tokens=%s",
                tokens,
            )
            return None
        
        # Execute action
        entity_ids = [e["entity_id"] for e in entities]
        results = await self._execute_service(action, entity_ids)
        
        # Generate response summary
        summary = self._summarize_execution(
            language=getattr(user_input, "language", None),
            action=action,
            results=results,
        )
        
        # Create result
        response = intent_helper.IntentResponse(
            language=getattr(user_input, "language", None)
        )
        response.async_set_speech(summary)
        
        return conversation.ConversationResult(
            response=response,
            conversation_id=user_input.conversation_id,
        )
    
    @staticmethod
    def _parse_onoff_intent(text: str) -> Optional[tuple[str, list[str]]]:
        """
        Parse turn_on/turn_off intent from text.
        
        Args:
            text: Normalized text
            
        Returns:
            Tuple of (action, tokens) if found, None otherwise
            action: "on" | "off"
            tokens: List of target tokens
        """
        import re
        
        if not text:
            return None
        
        # Match "spegni" or "accendi" at start
        match = re.match(r"^\s*(spegni|accendi)\b(.*)$", text, flags=re.IGNORECASE)
        if not match:
            return None
        
        action_word = match.group(1).lower()
        action = "off" if action_word == "spegni" else "on"
        
        rest = (match.group(2) or "").strip().lower()
        
        # Extract meaningful tokens (skip stopwords)
        stopwords = {
            "il", "lo", "la", "i", "gli", "le", "l'",
            "del", "dello", "della", "dei", "degli", "delle",
            "di", "in", "sul", "sulla", "sui", "nelle",
            "nel", "nella", "alla", "al", "allo", "alle",
            "ai", "agli", "per", "da", "con", "su", "a",
        }
        
        raw_tokens = re.findall(r"[a-zàèéìòóù]+", rest)
        
        # Filter tokens
        tokens = []
        for token in raw_tokens:
            if token in stopwords:
                continue
            # Skip "luce" if there are other tokens (it's implied)
            if token == "luce" and any(t for t in raw_tokens if t != "luce"):
                continue
            tokens.append(token)
        
        # Remove duplicates while preserving order
        unique_tokens = []
        for token in tokens:
            if token not in unique_tokens:
                unique_tokens.append(token)
        
        return (action, unique_tokens) if unique_tokens or action else None
    
    async def _execute_service(
        self,
        action: str,
        entity_ids: list[str],
    ) -> list[tuple[str, bool, str]]:
        """
        Execute homeassistant.turn_on or turn_off service.
        
        Args:
            action: "on" or "off"
            entity_ids: List of entity IDs to control
            
        Returns:
            List of (entity_id, success, error_message) tuples
        """
        results = []
        
        if not entity_ids:
            return results
        
        service = "turn_off" if action == "off" else "turn_on"
        data = {"entity_id": entity_ids}
        
        try:
            await self._hass.services.async_call(
                "homeassistant",
                service,
                data,
                blocking=True,
            )
            
            # All succeeded
            for entity_id in entity_ids:
                results.append((entity_id, True, ""))
            
            self._logger.info(
                "Local intent executed: service=%s, entities=%s",
                service,
                entity_ids,
            )
        
        except Exception as err:
            # All failed
            error_msg = f"{type(err).__name__}: {err}"
            for entity_id in entity_ids:
                results.append((entity_id, False, error_msg))
            
            self._logger.error(
                "Local intent execution failed: service=%s, entities=%s, error=%s",
                service,
                entity_ids,
                error_msg,
            )
        
        return results
    
    def _summarize_execution(
        self,
        language: Optional[str],
        action: str,
        results: list[tuple[str, bool, str]],
    ) -> str:
        """
        Create human-readable summary of execution.
        
        Args:
            language: User's language
            action: "on" or "off"
            results: Execution results
            
        Returns:
            Summary text
        """
        is_italian = (language or "").lower().startswith("it")
        
        if not results:
            if is_italian:
                return "Non ho trovato alcuna entità corrispondente da controllare."
            return "I couldn't find any matching entities to control."
        
        # Build lines for each entity
        lines = []
        for entity_id, success, error in results:
            # Get friendly name
            state = self._hass.states.get(entity_id)
            friendly_name = (state.name if state else None) or entity_id
            
            if success:
                status = "off" if action == "off" else "on"
                lines.append(f"- {friendly_name}: {status}")
            else:
                if is_italian:
                    lines.append(f"- {friendly_name}: errore ({error})")
                else:
                    lines.append(f"- {friendly_name}: error ({error})")
        
        # Build header
        any_success = any(ok for _, ok, _ in results)
        
        if is_italian:
            verb = "spento" if action == "off" else "acceso"
            prefix = "Ho" if any_success else "Non sono riuscito a"
            header = f"{prefix} {verb} i seguenti dispositivi:\n"
        else:
            verb = "turned off" if action == "off" else "turned on"
            prefix = "I have" if any_success else "I couldn't"
            header = f"{prefix} {verb} the following devices:\n"
        
        return header + "\n".join(lines)
    
    async def close(self) -> None:
        """Clean up resources."""
        await self._normalizer.close()

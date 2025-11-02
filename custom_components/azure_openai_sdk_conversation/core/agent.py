"""
Core conversation agent implementation.

Responsibilities:
- Implements HomeAssistant's AbstractConversationAgent
- Orchestrates between local intent handler and LLM clients
- Manages pending requests and early timeout
- Coordinates statistics tracking
"""

from __future__ import annotations

import asyncio
import time
from functools import partial
from datetime import datetime, timezone
from typing import Any, Optional

from homeassistant.components import conversation
from homeassistant.components.conversation import (
    AbstractConversationAgent,
    ConversationInput,
    ConversationResult,
)
from homeassistant.components.persistent_notification import async_create
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent as intent_helper

from ..llm.chat_client import ChatClient
from ..llm.responses_client import ResponsesClient
from ..local_intent.local_handler import LocalIntentHandler
from ..context.system_prompt import SystemPromptBuilder
from ..stats.manager import StatsManager
from ..stats.metrics import RequestMetrics
from .config import AgentConfig
from .logger import AgentLogger


class AzureOpenAIConversationAgent(AbstractConversationAgent):
    """Conversation agent that routes between local intents and Azure OpenAI LLM."""
    
    def __init__(self, hass: HomeAssistant, config: AgentConfig) -> None:
        """
        Initialize the conversation agent.
        
        Args:
            hass: Home Assistant instance
            config: Agent configuration
        """
        super().__init__()
        self._hass = hass
        self._config = config
        self._logger = AgentLogger(config)
        
        # Initialize LLM clients
        self._chat_client: Optional[ChatClient] = None
        self._responses_client: Optional[ResponsesClient] = None
        self._init_llm_clients()
        
        # Initialize local intent handler
        self._local_handler = LocalIntentHandler(
            hass=hass,
            config=config,
            logger=self._logger,
        )
        
        # Initialize system prompt builder
        self._prompt_builder = SystemPromptBuilder(
            hass=hass,
            config=config,
            logger=self._logger,
        )
        
        # Initialize statistics manager
        self._stats_manager: Optional[StatsManager] = None
        if config.stats_enable:
            self._stats_manager = StatsManager(
                hass=hass,
                stats_file=config.stats_aggregated_file,
                aggregation_interval_minutes=config.stats_aggregation_interval,
            )
            hass.async_create_task(self._stats_manager.start())
        
        # Pending requests tracking
        self._pending_requests: dict[str, dict[str, Any]] = {}
        
        self._logger.info(
            "Agent initialized: model=%s, local_intent=%s, stats=%s",
            config.chat_model,
            config.local_intent_enable,
            config.stats_enable,
        )
    
    def _init_llm_clients(self) -> None:
        """Initialize LLM clients based on configuration."""
        # Chat Completions client (always available)
        self._chat_client = ChatClient(
            hass=self._hass,
            config=self._config,
            logger=self._logger,
        )
        
        # Responses client (for reasoning models)
        if self._should_use_responses():
            self._responses_client = ResponsesClient(
                hass=self._hass,
                config=self._config,
                logger=self._logger,
            )
    
    def _should_use_responses(self) -> bool:
        """Determine if we should use Responses API based on model."""
        force_mode = self._config.force_responses_mode
        
        if force_mode == "responses":
            return True
        elif force_mode == "chat":
            return False
        else:  # auto
            # Use Responses for o-series models
            model = self._config.chat_model.lower()
            return model.startswith("o")
    
    @property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        return ["en", "it", "de", "es", "fr", "nl", "pl", "pt", "sk", "zh"]
    
    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        """
        Process a conversation input and return response.
        
        This is the main entry point called by Home Assistant's conversation system.
        
        Args:
            user_input: User's conversation input
            
        Returns:
            ConversationResult with response
        """
        # Start timing
        start_time = time.perf_counter()
        
        # Initialize metrics
        conv_id = user_input.conversation_id
        text_raw = (user_input.text or "").strip()
        language = getattr(user_input, "language", None)
        
        metrics = RequestMetrics(
            timestamp=datetime.now(timezone.utc).isoformat(),
            conversation_id=conv_id or "",
            execution_time_ms=0.0,
            handler="unknown",
            original_text=text_raw,
            normalized_text="",
            success=True,
        )
        
        try:
            self._logger.debug("Processing request: conv_id=%s, text=%s", conv_id, text_raw[:50])
            
            # Check for pending continuation
            if conv_id and conv_id in self._pending_requests:
                return await self._handle_pending_continuation(
                    user_input, metrics, start_time
                )
            
            # Load vocabulary if needed
            if self._config.vocabulary_enable:
                await self._local_handler.ensure_vocabulary_loaded()
            
            # Normalize text
            normalized_text = self._local_handler.normalize_text(text_raw)
            metrics.normalized_text = normalized_text
            
            # Try local intent handling first
            if self._config.local_intent_enable:
                local_result = await self._try_local_intent(
                    user_input, normalized_text, metrics, start_time
                )
                if local_result:
                    return local_result
            
            # Fall back to LLM
            return await self._process_with_llm(
                user_input,
                normalized_text,
                metrics,
                start_time,
            )
        
        except TimeoutError as err:
            self._logger.error("Request timed out: %s", err)
            response = intent_helper.IntentResponse(language=language)
            response.async_set_speech(str(err))
            return conversation.ConversationResult(
                response=response,
                conversation_id=conv_id,
            )
        except Exception as err:
            # Record failure
            metrics.success = False
            if not metrics.error_type:
                metrics.error_type = type(err).__name__
                metrics.error_message = str(err)
            metrics.execution_time_ms = (time.perf_counter() - start_time) * 1000
            
            if self._stats_manager:
                await self._stats_manager.record_request(metrics)
            
            self._logger.error("Request processing failed: %r", err)
            raise
    
    async def _try_local_intent(
        self,
        user_input: ConversationInput,
        normalized_text: str,
        metrics: RequestMetrics,
        start_time: float,
    ) -> Optional[ConversationResult]:
        """
        Try to handle request with local intent handler.
        
        Returns:
            ConversationResult if handled locally, None otherwise
        """
        intent_result = await self._local_handler.try_handle(
            normalized_text, user_input
        )
        
        if intent_result:
            # Successfully handled locally
            metrics.handler = "local_intent"
            #metrics.response_length = len(intent_result.speech)
            metrics.response_length = len(intent_result.response.speech)
            metrics.execution_time_ms = (time.perf_counter() - start_time) * 1000
            
            if self._stats_manager:
                await self._stats_manager.record_request(metrics)
            
            # Log utterance
            await self._log_utterance(
                user_input.conversation_id,
                "local_intent",
                user_input.text,
                normalized_text,
            )
            
            return intent_result
        
        return None
    
    async def _process_with_llm(
        self,
        user_input: ConversationInput,
        normalized_text: str,
        metrics: RequestMetrics,
        start_time: float,
    ) -> ConversationResult:
        """
        Process request using LLM (Chat or Responses API).
        
        Args:
            user_input: Original user input
            normalized_text: Normalized text for model
            metrics: Metrics being tracked
            start_time: Request start time
            
        Returns:
            ConversationResult with LLM response
        """
        conv_id = user_input.conversation_id
        language = getattr(user_input, "language", None)
        
        # Determine which API to use
        use_responses = self._should_use_responses()
        client = self._responses_client if use_responses else self._chat_client
        
        if not client:
            raise RuntimeError("No LLM client available")
        
        # Update metrics
        metrics.handler = "llm_responses" if use_responses else "llm_chat"
        metrics.model = self._config.chat_model
        metrics.api_version = client.effective_api_version
        metrics.temperature = self._config.temperature
        
        # Build system prompt
        system_prompt = await self._prompt_builder.build(
            conversation_id=conv_id,
        )
        
        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": normalized_text},
        ]
        
        # Log utterance
        await self._log_utterance(
            conv_id,
            metrics.handler,
            user_input.text,
            normalized_text,
        )
        
        # Track first chunk callback
        first_chunk_tracked = False
        
        def track_first_chunk():
            nonlocal first_chunk_tracked
            if not first_chunk_tracked:
                first_chunk_tracked = True
                metrics.first_chunk_time_ms = (time.perf_counter() - start_time) * 1000
        
        # Execute LLM call with early timeout if enabled
        if self._config.early_wait_enable and self._config.early_wait_seconds > 0:
            result = await self._execute_with_early_timeout(
                client=client,
                messages=messages,
                conv_id=conv_id,
                language=language,
                metrics=metrics,
                track_callback=track_first_chunk,
            )
        else:
            # Execute directly
            text_out, token_counts = await client.complete(
                messages=messages,
                conversation_id=conv_id,
                track_callback=track_first_chunk,
            )
            #result = self._create_result(user_input, text_out)
            result = self._create_result(conversation_id=conv_id, language=language, text=text_out)
            # Update metrics
            metrics.prompt_tokens = token_counts.get("prompt", 0)
            metrics.completion_tokens = token_counts.get("completion", 0)
            metrics.total_tokens = token_counts.get("total", 0)
        
        # Finalize metrics
        metrics.execution_time_ms = (time.perf_counter() - start_time) * 1000
        metrics.response_length = len(result.response.speech)
        
        if self._stats_manager:
            await self._stats_manager.record_request(metrics)
        
        return result
    
    async def _execute_with_early_timeout(
        self,
        client: Any,
        messages: list[dict[str, str]],
        conv_id: Optional[str],
        language: Optional[str],
        metrics: RequestMetrics,
        track_callback: callable,
    ) -> ConversationResult:
        """
        Execute LLM call with early timeout handling.
        
        If first chunk doesn't arrive within timeout, return a "still processing"
        message and continue in background.
        """
        first_chunk_event = asyncio.Event()
        
        # Start LLM call as task
        task = self._hass.async_create_task(
            client.complete(
                messages=messages,
                conversation_id=conv_id,
                first_chunk_event=first_chunk_event,
                track_callback=track_callback,
            )
        )
        
        try:
            # Wait for first chunk with timeout
            await asyncio.wait_for(
                first_chunk_event.wait(),
                timeout=self._config.early_wait_seconds,
            )
            
            # First chunk arrived, wait for completion
            text_out, token_counts = await task
            
            # Update metrics
            metrics.prompt_tokens = token_counts.get("prompt", 0)
            metrics.completion_tokens = token_counts.get("completion", 0)
            metrics.total_tokens = token_counts.get("total", 0)
            
            return self._create_result(
                conversation_id=conv_id,
                language=language,
                text=text_out,
            )
        
        except asyncio.TimeoutError:
            # First chunk didn't arrive in time
            self._logger.warning(
                "No first chunk within %ds, sending timeout message",
                self._config.early_wait_seconds,
            )
            
            # Store task for potential continuation
            if conv_id:
                self._pending_requests[conv_id] = {
                    "task": task,
                    "handler": metrics.handler,
                    "expire": time.monotonic() + self._config.api_timeout + 120,
                }
                
                # Notify user when task is done
                task.add_done_callback(
                    partial(self._background_task_done, conv_id=conv_id)
                )
            
            # Return timeout message
            timeout_msg = self._get_timeout_message(
                language, self._config.early_wait_seconds
            )
            
            return self._create_result(
                conversation_id=conv_id,
                language=language,
                text=timeout_msg,
            )

    def _background_task_done(self, task: asyncio.Task, conv_id: str) -> None:
        """
        Handle completion of a background LLM task.
        
        If the user hasn't already handled the request, this will cache the result
        and create a persistent notification to deliver the response.
        """
        pending_req = self._pending_requests.get(conv_id)
        if not pending_req or "result" in pending_req:
            # Already handled or result is already cached
            return

        try:
            text_out, _ = task.result()
            
            # Cache the result FIRST for the next user interaction
            pending_req["result"] = text_out
            
            # Try to create a notification to deliver the response proactively
            self._logger.info("Delivering background response for conv_id=%s via notification", conv_id)
            async_create(
                self._hass,
                message=text_out,
                title="Azure OpenAI Response",
                notification_id=f"azure_openai_{conv_id}",
            )

        except (asyncio.CancelledError, TimeoutError):
            # Task was cancelled or timed out, pop the request to clean up.
            self._logger.info("Background task for conv_id=%s was cancelled or timed out.", conv_id)
            self._pending_requests.pop(conv_id, None)
        except Exception as e:
            # Log other errors from the task, but leave the pending request
            # (with the cached result if available) for the user to retrieve manually.
            self._logger.error("Background LLM task for conv_id=%s failed: %r", conv_id, e)

    async def _handle_pending_continuation(
        self,
        user_input: ConversationInput,
        metrics: RequestMetrics,
        start_time: float,
    ) -> ConversationResult:
        """
        Handle continuation of a pending background request.
        """
        conv_id = user_input.conversation_id
        pending = self._pending_requests[conv_id]
        language = getattr(user_input, "language", None)

        # If result is already cached by the done_callback, return it
        if "result" in pending:
            self._logger.debug("Returning cached background result for conv_id=%s", conv_id)
            text_out = pending["result"]
            self._pending_requests.pop(conv_id, None)
            return self._create_result(
                conversation_id=conv_id,
                language=language,
                text=text_out,
            )

        task = pending["task"]
        text_input = (user_input.text or "").strip()
        
        # Check if user wants to continue waiting
        wait_seconds = self._parse_wait_seconds(text_input)
        
        if wait_seconds is not None:
            # User wants to wait for a specific number of seconds
            self._logger.info(
                "User requested to wait %ds more for background task", wait_seconds
            )
            
            try:
                # Wait with shield to prevent cancellation
                text_out, token_counts = await asyncio.wait_for(
                    asyncio.shield(task), timeout=wait_seconds
                )
                
                # Success - remove from pending
                self._pending_requests.pop(conv_id, None)
                
                # Update metrics
                metrics.handler = pending["handler"]
                metrics.prompt_tokens = token_counts.get("prompt", 0)
                metrics.completion_tokens = token_counts.get("completion", 0)
                metrics.total_tokens = token_counts.get("total", 0)
                metrics.execution_time_ms = (time.perf_counter() - start_time) * 1000
                
                if self._stats_manager:
                    await self._stats_manager.record_request(metrics)
                
                return self._create_result(
                    conversation_id=conv_id,
                    language=language,
                    text=text_out,
                )
            
            except asyncio.TimeoutError:
                # Still no response
                msg = self._get_still_waiting_message(language, wait_seconds)
                return self._create_result(
                    conversation_id=conv_id,
                    language=language,
                    text=msg,
                )
        
        else:
            # User wants to wait indefinitely
            self._logger.info("User chose to wait indefinitely for background task.")
            try:
                text_out, token_counts = await asyncio.shield(task)

                # Success - remove from pending
                self._pending_requests.pop(conv_id, None)

                # Update metrics
                metrics.handler = pending["handler"]
                metrics.prompt_tokens = token_counts.get("prompt", 0)
                metrics.completion_tokens = token_counts.get("completion", 0)
                metrics.total_tokens = token_counts.get("total", 0)
                metrics.execution_time_ms = (time.perf_counter() - start_time) * 1000

                if self._stats_manager:
                    await self._stats_manager.record_request(metrics)

                return self._create_result(
                    conversation_id=conv_id,
                    language=language,
                    text=text_out,
                )
            except (asyncio.CancelledError, TimeoutError) as err:
                self._logger.warning("Background task failed while waiting indefinitely: %r", err)
                self._pending_requests.pop(conv_id, None)
                msg = self._get_task_failed_message(language)
                return self._create_result(
                    conversation_id=conv_id, language=language, text=msg
                )

    def _create_result(
        self,
        conversation_id: Optional[str],
        language: Optional[str],
        text: str,
    ) -> ConversationResult:
        """Create ConversationResult from response text."""
        response = intent_helper.IntentResponse(language=language)
        
        # Ensure non-empty speech to avoid frontend crashes
        safe_text = text.strip() if text else self._get_empty_response_message(language)
        response.async_set_speech(safe_text)
        
        return conversation.ConversationResult(
            response=response,
            conversation_id=conversation_id,
        )
    
    async def _log_utterance(
        self,
        conversation_id: Optional[str],
        mode: str,
        original: str,
        normalized: str,
    ) -> None:
        """Log utterance if enabled."""
        if self._config.log_utterances and self._config.utterances_log_path:
            # Delegate to config utility
            await self._config.log_utterance(
                self._hass,
                conversation_id,
                mode,
                original,
                normalized,
            )
    
    @staticmethod
    def _parse_wait_seconds(text: str) -> Optional[int]:
        """Parse wait seconds from user input."""
        import re
        match = re.fullmatch(r"\s*(\d+)\s*", text or "")
        if not match:
            return None
        try:
            val = int(match.group(1))
            return max(1, min(val, 600))  # Clamp to [1, 600]
        except (ValueError, IndexError):
            return None
    
    @staticmethod
    def _get_timeout_message(language: Optional[str], seconds: int) -> str:
        """Get timeout message in user's language."""
        if (language or "").lower().startswith("it"):
            return (
                f"Nessuna risposta entro {seconds}s. "
                f"Rispondi con un numero per attendere altri secondi (es. 15), "
                f"o qualsiasi altro testo per attendere la risposta."
            )
        return (
            f"No response within {seconds}s. "
            f"Reply with seconds to wait (e.g., 15), "
            f"or any other text to wait for the response."
        )
    
    @staticmethod
    def _get_still_waiting_message(language: Optional[str], seconds: int) -> str:
        """Get still waiting message."""
        if (language or "").lower().startswith("it"):
            return (
                f"Ancora nessuna risposta dopo {seconds}s. "
                f"Rispondi con altri secondi per continuare, "
                f"o qualsiasi altro testo per attendere la risposta."
            )
        return (
            f"Still no response after {seconds}s. "
            f"Reply with more seconds to continue, "
            f"or any other text to wait for the response."
        )

    @staticmethod
    def _get_task_failed_message(language: Optional[str]) -> str:
        """Get message for when a background task fails."""
        if (language or "").lower().startswith("it"):
            return "La richiesta in background non è riuscita o è stata annullata."
        return "The background request failed or was cancelled."

    @staticmethod
    def _get_empty_response_message(language: Optional[str]) -> str:
        """Get fallback message for empty responses."""
        if (language or "").lower().startswith("it"):
            return "Non ho ricevuto alcuna risposta testuale dal modello."
        return "No textual response was received from the model."
    
    async def async_close(self) -> None:
        """Clean up resources."""
        if self._chat_client:
            await self._chat_client.close()
        if self._responses_client:
            await self._responses_client.close()
        if self._local_handler:
            await self._local_handler.close()
        if self._prompt_builder:
            await self._prompt_builder.close()
        if self._stats_manager:
            await self._stats_manager.stop()
        
        self._logger.info("Agent closed")

"""
Tool Manager - orchestrates tool calling workflow.

Coordinates schema building, validation, and execution of function calls.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from homeassistant.core import HomeAssistant

from ..core.config import AgentConfig
from ..core.logger import AgentLogger

_LOGGER = logging.getLogger(__name__)


class ToolManager:
    """
    Manages the complete tool calling lifecycle.

    Responsibilities:
    - Build and cache tool schemas
    - Coordinate execution via FunctionExecutor
    - Track tool call statistics
    - Manage tool iterations and loops
    """

    def __init__(
        self,
        hass: HomeAssistant,
        config: AgentConfig,
        logger: AgentLogger,
    ) -> None:
        """
        Initialize tool manager.

        Args:
            hass: Home Assistant instance
            config: Agent configuration
            logger: Logger instance
        """
        self._hass = hass
        self._config = config
        self._logger = logger

        # Import executor and schema builder
        from .function_executor import FunctionExecutor
        from .schema_builder import ToolSchemaBuilder

        # Initialize components
        self._executor = FunctionExecutor(
            hass=hass,
            allowed_domains=self._get_allowed_domains(),
            max_calls_per_minute=config.tools_max_calls_per_minute,
        )

        self._schema_builder = ToolSchemaBuilder(hass=hass)

        # Cached tool schemas
        self._tools_cache: Optional[list[dict[str, Any]]] = None
        self._cache_timestamp: Optional[float] = None
        self._cache_ttl = 300  # 5 minutes

        self._logger.info(
            "ToolManager initialized: enabled=%s, domains=%s",
            config.tools_enable,
            self._get_allowed_domains(),
        )

    def _get_allowed_domains(self) -> set[str]:
        """Get set of allowed service domains from config."""
        whitelist = getattr(self._config, "tools_whitelist", None)

        if whitelist:
            if isinstance(whitelist, str):
                return set(d.strip() for d in whitelist.split(",") if d.strip())
            elif isinstance(whitelist, list):
                return set(whitelist)

        # Default: common safe domains
        return {
            "light",
            "switch",
            "climate",
            "cover",
            "fan",
            "media_player",
            "lock",
            "vacuum",
            "water_heater",
            "humidifier",
            "number",
            "input_boolean",
            "input_number",
            "input_select",
            "input_text",
        }

    async def get_tools_schema(self) -> list[dict[str, Any]]:
        """
        Get OpenAI tools schema for current configuration.

        Returns cached schema if fresh, otherwise rebuilds.

        Returns:
            List of OpenAI tool schema dicts
        """
        import time

        now = time.time()

        # Check cache validity
        if (
            self._tools_cache is not None
            and self._cache_timestamp is not None
            and (now - self._cache_timestamp) < self._cache_ttl
        ):
            self._logger.debug(
                "Using cached tools schema (%d tools)", len(self._tools_cache)
            )
            return self._tools_cache

        # Rebuild schema
        self._logger.info("Building tools schema...")

        allowed_domains = self._get_allowed_domains()
        tools = await self._schema_builder.build_all_tools(
            allowed_domains=allowed_domains
        )

        # Cache result
        self._tools_cache = tools
        self._cache_timestamp = now

        self._logger.info(
            "Built %d tools from %d domains", len(tools), len(allowed_domains)
        )

        return tools

    async def execute_tool_calls(
        self,
        tool_calls: list[dict[str, Any]],
        parallel: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Execute list of tool calls.

        Args:
            tool_calls: List of OpenAI tool call objects
            parallel: Execute in parallel (default: sequential for safety)

        Returns:
            List of tool result dicts
        """
        if not tool_calls:
            return []

        self._logger.info(
            "Executing %d tool calls (parallel=%s)", len(tool_calls), parallel
        )

        results = await self._executor.execute_multiple(
            tool_calls=tool_calls,
            parallel=parallel,
        )

        # Log execution summary
        success_count = sum(1 for r in results if r.get("success"))
        self._logger.info(
            "Tool execution complete: %d/%d successful", success_count, len(results)
        )

        return results

    async def process_tool_loop(
        self,
        initial_messages: list[dict[str, Any]],
        llm_client: Any,  # ChatClient or ResponsesClient
        max_iterations: int,
        conversation_id: Optional[str] = None,
        user_message: str = "",
        track_callback: Optional[callable] = None,
    ) -> dict[str, Any]:
        """
        Execute complete tool calling loop with LLM.

        Flow:
        1. Call LLM with tools
        2. If tool_calls present:
           a. Execute all tool calls
           b. Add results to messages
           c. Go to step 1
        3. Return final text response

        Args:
            initial_messages: Initial message history
            llm_client: LLM client (ChatClient or ResponsesClient)
            max_iterations: Maximum tool call iterations
            track_callback: Optional callback to invoke on first chunk

        Returns:
            Tuple of (final_text_response, full_message_history)
        """
        messages = initial_messages.copy()
        iteration = 0

        # Get tools schema
        tools = await self.get_tools_schema()

        if not tools:
            self._logger.warning("No tools available, skipping tool loop")
            # Fall back to normal completion
            text, _tokens = await llm_client.complete(
                messages=messages,
                conversation_id=None,
                user_message=user_message,
                track_callback=track_callback,
            )
            return {"text": text, "messages": messages}

        # Track if callback was already called
        callback_called = False

        def call_callback_once():
            nonlocal callback_called
            if not callback_called and track_callback:
                track_callback()
                callback_called = True

        while iteration < max_iterations:
            iteration += 1
            self._logger.debug("Tool loop iteration %d/%d", iteration, max_iterations)

            # Call LLM with tools
            response_data, token_counts = await self._call_llm_with_tools(
                llm_client=llm_client,
                messages=messages,
                tools=tools,
                conversation_id=conversation_id,
                user_message=user_message,
                track_callback=track_callback,
            )

            # Check for tool calls
            text_response = response_data.get("text", "")
            tool_calls = response_data.get("tool_calls", [])

            if not tool_calls:
                # No more tool calls - we're done
                self._logger.info(
                    "Tool loop complete after %d iterations: final response", iteration
                )
                return {"text": text_response, "messages": messages}

            # Add assistant message with tool calls to history
            messages.append(
                {
                    "role": "assistant",
                    "content": response_data.get("text") or "",
                    "tool_calls": tool_calls,
                }
            )

            # Execute tool calls
            tool_results = await self.execute_tool_calls(tool_calls)

            # Add tool results to messages
            for result in tool_results:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": result["tool_call_id"],
                        "content": result["content"],
                    }
                )

        # Max iterations reached - force final response
        self._logger.warning(
            "Tool loop reached max iterations (%d), forcing final response",
            max_iterations,
        )

        # One final call without tools to get conclusion
        text, _tokens = await llm_client.complete(
            messages=messages,
            conversation_id=None,
            user_message=user_message,
            track_callback=call_callback_once,
        )

        return {"text": text, "messages": messages}

    async def _call_llm_with_tools(
        self,
        llm_client: Any,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        conversation_id: Optional[str] = None,
        user_message: str = "",
        track_callback: Optional[callable] = None,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        """Call the LLM with the current messages and tools."""
        self._logger.debug("Calling LLM with %d tools", len(tools))

        response_dict, token_counts = await llm_client.complete_with_tools(
            messages=messages,
            tools=tools,
            conversation_id=conversation_id,
            user_message=user_message,
            track_callback=track_callback,
        )
        return response_dict, token_counts

    def invalidate_cache(self) -> None:
        """Invalidate tools schema cache (e.g., after service reload)."""
        self._tools_cache = None
        self._cache_timestamp = None
        self._logger.info("Tools schema cache invalidated")

    def get_stats(self) -> dict[str, Any]:
        """Get tool manager statistics."""
        executor_stats = self._executor.get_stats()

        return {
            "tools_enabled": self._config.tools_enable,
            "tools_cached": len(self._tools_cache) if self._tools_cache else 0,
            "allowed_domains": list(self._get_allowed_domains()),
            **executor_stats,
        }

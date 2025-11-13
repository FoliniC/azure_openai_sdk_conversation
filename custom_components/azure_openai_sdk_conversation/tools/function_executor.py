"""
Function executor with safety checks for Azure OpenAI SDK Conversation.

Handles secure execution of Home Assistant service calls from LLM tool calls.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional
from collections import deque
from datetime import datetime, timezone

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


class FunctionExecutor:
    """
    Executes Home Assistant service calls with safety validation.

    Features:
    - Whitelist/blacklist validation
    - Parameter validation
    - Rate limiting
    - Error handling and logging
    - Execution history tracking
    """

    # Dangerous services that should never be called
    BLACKLISTED_SERVICES = {
        "homeassistant.restart",
        "homeassistant.stop",
        "homeassistant.reload_core_config",
        "homeassistant.reload_all",
        "homeassistant.save_persistent_states",
        "persistent_notification.dismiss_all",
        "system_log.clear",
        "recorder.purge",
        "recorder.disable",
    }

    # Domains that require special caution
    SENSITIVE_DOMAINS = {
        "script",
        "automation",
        "scene",
        "shell_command",
        "python_script",
    }

    def __init__(
        self,
        hass: HomeAssistant,
        allowed_domains: set[str] | None = None,
        max_calls_per_minute: int = 30,
    ) -> None:
        """
        Initialize function executor.

        Args:
            hass: Home Assistant instance
            allowed_domains: Set of allowed service domains
                           If None, all non-blacklisted services allowed
            max_calls_per_minute: Rate limit for service calls
        """
        self._hass = hass
        self._allowed_domains = allowed_domains or set()
        self._max_calls_per_minute = max_calls_per_minute

        # Execution history for rate limiting
        self._call_history: deque[datetime] = deque(maxlen=100)

        # Statistics
        self._total_calls = 0
        self._failed_calls = 0

    async def execute_tool_call(
        self,
        tool_call: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute a single tool call from LLM.

        Args:
            tool_call: OpenAI tool call object with:
                - id: Tool call ID
                - function: {name: str, arguments: str (JSON)}

        Returns:
            Tool result dict with:
                - tool_call_id: Original tool call ID
                - content: Result message (success or error)
                - success: Boolean success flag
        """
        tool_id = tool_call.get("id", "unknown")
        function = tool_call.get("function", {})
        function_name = function.get("name", "")

        _LOGGER.debug("Executing tool call: %s (id=%s)", function_name, tool_id)

        try:
            # Parse arguments
            import json

            args_str = function.get("arguments") or "{}"
            arguments = json.loads(args_str) if isinstance(args_str, str) else args_str

            # Validate tool call
            validation_error = self._validate_tool_call(function_name, arguments)
            if validation_error:
                return self._error_result(tool_id, validation_error)

            # Check rate limit
            if not self._check_rate_limit():
                return self._error_result(
                    tool_id,
                    f"Rate limit exceeded: max {self._max_calls_per_minute} calls/minute",
                )

            # Execute service call
            result = await self._execute_service(function_name, arguments)

            self._total_calls += 1
            self._call_history.append(datetime.now(timezone.utc))

            return {
                "tool_call_id": tool_id,
                "content": result,
                "success": True,
            }

        except Exception as err:
            self._failed_calls += 1
            _LOGGER.error(
                "Tool call execution failed: %s (id=%s): %r",
                function_name,
                tool_id,
                err,
            )
            return self._error_result(tool_id, str(err))

    async def execute_multiple(
        self,
        tool_calls: list[dict[str, Any]],
        parallel: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Execute multiple tool calls.

        Args:
            tool_calls: List of tool call objects
            parallel: If True, execute in parallel; else sequential

        Returns:
            List of tool results
        """
        if parallel:
            # Execute all concurrently
            tasks = [self.execute_tool_call(tool_call) for tool_call in tool_calls]
            return await asyncio.gather(*tasks)
        else:
            # Execute sequentially
            results = []
            for tool_call in tool_calls:
                result = await self.execute_tool_call(tool_call)
                results.append(result)
            return results

    def _validate_tool_call(
        self,
        function_name: str,
        arguments: dict[str, Any],
    ) -> Optional[str]:
        """
        Validate a tool call against security rules.

        Returns:
            Error message if invalid, None if valid
        """
        # Parse domain and service
        parts = function_name.split("_", 1)
        if len(parts) != 2:
            return f"Invalid function name format: {function_name}"

        domain, service = parts
        full_service = f"{domain}.{service}"

        # Check blacklist
        if full_service in self.BLACKLISTED_SERVICES:
            return f"Service {full_service} is blacklisted for security reasons"

        # Check domain whitelist (if configured)
        if self._allowed_domains and domain not in self._allowed_domains:
            return f"Domain {domain} is not in allowed domains: {self._allowed_domains}"

        # Warn about sensitive domains
        if domain in self.SENSITIVE_DOMAINS:
            _LOGGER.warning(
                "Executing potentially sensitive service: %s with args: %s",
                full_service,
                arguments,
            )

        # Validate entity_id if present
        entity_id = arguments.get("entity_id")
        if entity_id:
            if not self._validate_entity_id(entity_id):
                return f"Invalid or non-existent entity_id: {entity_id}"

        return None  # Valid

    def _validate_entity_id(self, entity_id: str | list[str]) -> bool:
        """
        Validate that entity_id exists and is exposed.

        Args:
            entity_id: Single entity ID or list of entity IDs

        Returns:
            True if all valid
        """
        # Handle list of entity_ids
        if isinstance(entity_id, list):
            return all(self._validate_entity_id(eid) for eid in entity_id)

        # Check if entity exists
        state = self._hass.states.get(entity_id)
        if not state:
            return False

        # TODO: Check if entity is exposed to conversation
        # For now, we allow all existing entities
        return True

    async def _execute_service(
        self,
        function_name: str,
        arguments: dict[str, Any],
    ) -> str:
        """
        Execute the actual Home Assistant service call.

        Args:
            function_name: Function name (domain_service)
            arguments: Service call arguments

        Returns:
            Success message describing what was done
        """
        # Parse domain and service
        domain, service = function_name.split("_", 1)

        _LOGGER.info("Calling service %s.%s with args: %s", domain, service, arguments)

        try:
            # Execute service call
            await self._hass.services.async_call(
                domain=domain,
                service=service,
                service_data=arguments,
                blocking=True,
            )

            # Generate success message
            return self._format_success_message(domain, service, arguments)

        except HomeAssistantError as err:
            raise RuntimeError(f"Service call failed: {err}") from err

    def _format_success_message(
        self,
        domain: str,
        service: str,
        arguments: dict[str, Any],
    ) -> str:
        """
        Format a structured success message as a JSON string.
        This is more robust for the model to understand than natural language.
        """
        import json

        result = {
            "service_called": f"{domain}.{service}",
            "status": "success",
            "arguments_used": arguments,
        }
        return json.dumps(result)

    def _error_result(self, tool_id: str, error_msg: str) -> dict[str, Any]:
        """Create an error result dict."""
        return {
            "tool_call_id": tool_id,
            "content": f"Error: {error_msg}",
            "success": False,
        }

    def _check_rate_limit(self) -> bool:
        """
        Check if rate limit allows another call.

        Returns:
            True if call is allowed
        """
        now = datetime.now(timezone.utc)
        cutoff = now.timestamp() - 60  # 1 minute ago

        # Count recent calls
        recent_calls = sum(1 for ts in self._call_history if ts.timestamp() >= cutoff)

        return recent_calls < self._max_calls_per_minute

    def get_stats(self) -> dict[str, Any]:
        """Get execution statistics."""
        return {
            "total_calls": self._total_calls,
            "failed_calls": self._failed_calls,
            "success_rate": (
                (self._total_calls - self._failed_calls) / self._total_calls * 100
                if self._total_calls > 0
                else 0.0
            ),
            "allowed_domains": list(self._allowed_domains)
            if self._allowed_domains
            else "all",
        }

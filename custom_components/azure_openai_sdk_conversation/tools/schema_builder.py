# tools/schema_builder.py
"""
Tool schema builder - converte HA services in OpenAI function schemas
"""

from typing import Any
import voluptuous as vol
from homeassistant.core import HomeAssistant
import logging

_LOGGER = logging.getLogger(__name__)


class ToolSchemaBuilder:
    """Costruisce OpenAI tool schemas da HA services"""

    def __init__(self, hass: HomeAssistant):
        self._hass = hass

    async def build_all_tools(
        self, allowed_domains: set[str] | None = None
    ) -> list[dict[str, Any]]:
        """
        Costruisce lista completa di tools disponibili

        Args:
            allowed_domains: Set di domini permessi (es: {"light", "switch"})
                            Se None, usa tutti i domini

        Returns:
            Lista di OpenAI tool schema dicts
        """
        tools = []

        # Get all services
        services = self._hass.services.async_services()

        # --- START: Log all available domains ---
        try:
            all_domains = sorted(list(services.keys()))
            _LOGGER.warning(
                "\n--- All Available Service Domains ---\n%s", ", ".join(all_domains)
            )
        except Exception as e:
            _LOGGER.error("Could not log available domains: %r", e)
        # --- END: Log all available domains ---

        service_map_for_log = {}

        for domain, domain_services in services.items():
            # Filter by allowed domains
            if allowed_domains and domain not in allowed_domains:
                continue

            for service_name, service_obj in domain_services.items():
                try:
                    tool_schema = self._build_tool_schema(
                        domain=domain, service=service_name, service_obj=service_obj
                    )

                    if tool_schema:
                        tools.append(tool_schema)
                        if domain not in service_map_for_log:
                            service_map_for_log[domain] = []
                        service_map_for_log[domain].append(service_name)

                except Exception as err:
                    _LOGGER.warning(
                        "Failed to build schema for %s.%s: %r",
                        domain,
                        service_name,
                        err,
                    )
                    continue

        # --- START: Log collected services as YAML ---
        if service_map_for_log:
            try:
                import yaml

                for domain in service_map_for_log:
                    service_map_for_log[domain].sort()
                sorted_service_map = dict(sorted(service_map_for_log.items()))

                yaml_output = yaml.dump(
                    sorted_service_map, indent=2, default_flow_style=False
                )

                _LOGGER.warning(
                    "\n--- Filtered Services for Tool Generation (YAML) ---\n%s\n--- End of Services ---",
                    yaml_output,
                )
            except Exception as e:
                _LOGGER.error("Could not log services as YAML: %r", e)
        # --- END: Log collected services as YAML ---

        _LOGGER.info(
            "Built %d tool schemas from %d domains",
            len(tools),
            len(allowed_domains or services),
        )
        return tools

    def _build_tool_schema(
        self, domain: str, service: str, service_obj: Any
    ) -> dict[str, Any] | None:
        """Costruisce schema per singolo servizio"""

        # Tool name: domain_service (es: light_turn_on)
        tool_name = f"{domain}_{service}"

        # Description
        description = (
            getattr(service_obj, "description", None) or f"Call {domain}.{service}"
        )

        # Truncate description se troppo lunga
        if len(description) > 1000:
            description = description[:997] + "..."

        # Estrai parametri dallo schema
        schema = getattr(service_obj, "schema", None)
        parameters = self._extract_parameters_from_schema(domain, service, schema)

        _LOGGER.debug(
            "Built schema for %s.%s: %d parameters: %s",
            domain,
            service,
            len(parameters.get("properties", {})),
            list(parameters.get("properties", {}).keys()),
        )

        return {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": description,
                "parameters": parameters,
            },
        }

    def _extract_parameters_from_schema(
        self, domain: str, service: str, schema: Any
    ) -> dict[str, Any]:
        """
        Estrae parametri da uno schema Voluptuous.

        Args:
            domain: Service domain
            service: Service name
            schema: Voluptuous schema object

        Returns:
            OpenAI-compatible parameters schema
        """
        if not schema:
            return self._build_default_parameters(domain, service)

        properties = {}
        required = []

        try:
            # Unwrap validators
            schema_dict = self._unwrap_schema(schema)

            if not schema_dict:
                _LOGGER.debug(
                    "No schema dict extracted for %s.%s, using defaults",
                    domain,
                    service,
                )
                return self._build_default_parameters(domain, service)

            _LOGGER.debug(
                "Schema dict for %s.%s has %d keys: %s",
                domain,
                service,
                len(schema_dict),
                list(schema_dict.keys()),
            )

            # Process each parameter
            for key, validator in schema_dict.items():
                param_name, is_required = self._extract_param_info(key)

                if not param_name:
                    continue

                # Convert validator to JSON schema
                param_schema = self._validator_to_json_schema(param_name, validator)

                if param_schema:
                    properties[param_name] = param_schema

                    if is_required:
                        required.append(param_name)

                    _LOGGER.debug(
                        "Extracted %s.%s parameter: %s (required=%s, type=%s)",
                        domain,
                        service,
                        param_name,
                        is_required,
                        param_schema.get("type", "unknown"),
                    )

        except Exception as err:
            _LOGGER.warning(
                "Failed to extract schema for %s.%s: %r, using defaults",
                domain,
                service,
                err,
            )
            return self._build_default_parameters(domain, service)

        # Fallback to defaults if no properties found
        if not properties:
            return self._build_default_parameters(domain, service)

        result = {
            "type": "object",
            "properties": properties,
        }

        if required:
            result["required"] = required

        return result

    def _unwrap_schema(self, schema: Any) -> dict | None:
        """
        Unwrap Voluptuous schema to get the underlying dict.

        Handles:
        - vol.Schema objects
        - vol.All validators
        - Direct dicts
        """
        # Try vol.Schema
        if hasattr(schema, "schema"):
            inner = schema.schema
            if isinstance(inner, dict):
                return inner
            # Recursively unwrap
            return self._unwrap_schema(inner)

        # Try vol.All (wrapper validator)
        if isinstance(schema, vol.All):
            # vol.All wraps multiple validators
            # Get the first one that's a dict or Schema
            for validator in schema.validators:
                result = self._unwrap_schema(validator)
                if result:
                    return result

        # Direct dict
        if isinstance(schema, dict):
            return schema

        # Try to access underlying schema attribute
        if hasattr(schema, "__dict__") and "schema" in schema.__dict__:
            return self._unwrap_schema(schema.__dict__["schema"])

        return None

    def _extract_param_info(self, key: Any) -> tuple[str | None, bool]:
        """
        Extract parameter name and required flag from schema key.

        Args:
            key: Schema key (can be vol.Required, vol.Optional, or string)

        Returns:
            Tuple of (param_name, is_required)
        """
        if isinstance(key, vol.Required):
            return str(key.schema), True
        elif isinstance(key, vol.Optional):
            return str(key.schema), False
        elif isinstance(key, str):
            return key, False
        else:
            # Try to convert to string
            try:
                return str(key), False
            except Exception:  # Catch all exceptions explicitly
                return None, False

    def _validator_to_json_schema(
        self, param_name: str, validator: Any
    ) -> dict[str, Any] | None:
        """
        Converte un validatore Voluptuous in JSON schema.

        Args:
            param_name: Nome del parametro
            validator: Validatore Voluptuous

        Returns:
            JSON schema dict
        """
        # entity_id è sempre string
        if param_name == "entity_id":
            return {
                "type": "string",
                "description": "Entity ID (e.g., light.living_room)",
            }

        # Unwrap validator if it's vol.All or similar
        actual_validator = validator
        if isinstance(validator, vol.All):
            # Get first meaningful validator
            for v in validator.validators:
                if v not in (vol.Any,) and not callable(v):
                    actual_validator = v
                    break

        # Check validator type
        validator_str = str(type(actual_validator).__name__)

        # Type inference from validator
        type_map = {
            "str": "string",
            "int": "integer",
            "float": "number",
            "bool": "boolean",
            "list": "array",
            "dict": "object",
        }

        for type_name, json_type in type_map.items():
            if type_name in validator_str.lower():
                schema = {
                    "type": json_type,
                    "description": param_name.replace("_", " ").title(),
                }
                if json_type == "array":
                    schema["items"] = {"type": "string"}
                return schema

        # Check if validator is a Python type
        if actual_validator in (str, int, float, bool, list, dict):
            json_type = type_map.get(actual_validator.__name__, "string")
            schema = {
                "type": json_type,
                "description": param_name.replace("_", " ").title(),
            }
            if json_type == "array":
                schema["items"] = {"type": "string"}
            return schema

        # Default: string
        return {"type": "string", "description": param_name.replace("_", " ").title()}

    def _build_default_parameters(self, domain: str, service: str) -> dict[str, Any]:
        """
        Costruisce parametri di default per servizi comuni.
        """
        # Domini che richiedono un target
        TARGET_DOMAINS = {
            "light",
            "switch",
            "climate",
            "cover",
            "fan",
            "lock",
            "media_player",
            "vacuum",
            "water_heater",
            "humidifier",
            "number",
            "input_boolean",
        }

        if domain not in TARGET_DOMAINS:
            return {"type": "object", "properties": {}}

        # Base schema with multiple targeting options.
        # None are "required" from the tool's perspective, as the user can provide any of them.
        # Home Assistant's service layer will validate that at least one is present.
        schema = {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "The entity_id of the entity to control (e.g., 'light.living_room'). Can be a single ID or a list.",
                },
                "device_id": {
                    "type": "string",
                    "description": "The device_id of the device to control. Can be a single ID or a list.",
                },
                "area_id": {
                    "type": "string",
                    "description": "The area_id of the area to control (e.g., 'kitchen'). Can be a single ID or a list.",
                },
            },
            # No 'required' field, as any of the above can be used.
        }

        # Parametri specifici per dominio/servizio
        if domain == "light":
            if "turn_on" in service:
                schema["properties"].update(
                    {
                        "brightness": {
                            "type": "integer",
                            "description": "Brightness (0-255)",
                            "minimum": 0,
                            "maximum": 255,
                        },
                        "rgb_color": {
                            "type": "array",
                            "description": "RGB color as [red, green, blue]",
                            "items": {"type": "integer", "minimum": 0, "maximum": 255},
                            "minItems": 3,
                            "maxItems": 3,
                        },
                        "color_temp": {
                            "type": "integer",
                            "description": "Color temperature in mireds",
                        },
                    }
                )

        elif domain == "climate":
            if "set_temperature" in service:
                schema["properties"].update(
                    {
                        "temperature": {
                            "type": "number",
                            "description": "Target temperature",
                        },
                        "target_temp_high": {
                            "type": "number",
                            "description": "High target temperature",
                        },
                        "target_temp_low": {
                            "type": "number",
                            "description": "Low target temperature",
                        },
                    }
                )
            elif "set_hvac_mode" in service:
                schema["properties"].update(
                    {
                        "hvac_mode": {
                            "type": "string",
                            "description": "HVAC mode",
                            "enum": [
                                "off",
                                "heat",
                                "cool",
                                "heat_cool",
                                "auto",
                                "dry",
                                "fan_only",
                            ],
                        }
                    }
                )

        elif domain == "cover":
            if "set_cover_position" in service:
                schema["properties"].update(
                    {
                        "position": {
                            "type": "integer",
                            "description": "Position (0-100, 0=closed, 100=open)",
                            "minimum": 0,
                            "maximum": 100,
                        }
                    }
                )

        elif domain == "media_player":
            if "volume_set" in service:
                schema["properties"].update(
                    {
                        "volume_level": {
                            "type": "number",
                            "description": "Volume level (0.0-1.0)",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        }
                    }
                )

        _LOGGER.debug(
            "Using default parameters for %s.%s: %s",
            domain,
            service,
            list(schema["properties"].keys()),
        )

        return schema

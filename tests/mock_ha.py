from unittest.mock import MagicMock, AsyncMock
import sys
import types
from enum import StrEnum
from typing import Any

# Helper to create a mock module
def mock_module(name):
    m = types.ModuleType(name)
    m.__path__ = []
    return m

# Mock Base Classes
class MockEntity:
    def __init__(self):
        self.hass = None
        self.platform = None
        self.entity_id = None
        self._attr_unique_id = None
        self._attr_name = None
        self._attr_has_entity_name = False
        self._attr_device_info = None
        self._attr_state_class = None
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None
        self._attr_translation_key = None
        self.registry_entry = None
        self._attr_device_class = None
        self._attr_native_unit_of_measurement = None

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def name(self):
        return self._attr_name
        
    @property
    def device_info(self):
        return self._attr_device_info
        
    @property
    def extra_state_attributes(self):
        return {}
        
    @property
    def device_class(self):
        return self._attr_device_class
        
    @property
    def native_unit_of_measurement(self):
        return self._attr_native_unit_of_measurement

class MockCoordinatorEntity(MockEntity):
    def __init__(self, coordinator):
        super().__init__()
        self.coordinator = coordinator

class MockDataUpdateCoordinator(MagicMock):
    def __init__(self, hass, logger, name, update_interval=None, **kwargs):
        super().__init__(**kwargs)
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.data = {}
    
    async def async_refresh(self):
        pass
        
    async def async_config_entry_first_refresh(self):
        pass

class MockConfigFlow:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()
    
    def __init__(self):
        self.hass = None
    
    async def async_set_unique_id(self, *args, **kwargs):
        return MagicMock()
    
    def _abort_if_unique_id_configured(self, *args, **kwargs):
        pass
        
    def async_abort(self, **kwargs):
        return {"type": "abort", **kwargs}
        
    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}
        
    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

class MockOptionsFlow:
    def __init__(self, config_entry=None):
        self._config_entry = config_entry
        self.hass = None

    @property
    def config_entry(self):
        return self._config_entry

    @config_entry.setter
    def config_entry(self, value):
        self._config_entry = value

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}
        
    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

# Mock Platform enum
class Platform(StrEnum):
    CONVERSATION = "conversation"
    SENSOR = "sensor"
    SWITCH = "switch"
    SELECT = "select"
    NUMBER = "number"
    CLIMATE = "climate"
    COVER = "cover"

class FlowResultType(StrEnum):
    FORM = "form"
    CREATE_ENTRY = "create_entry"
    ABORT = "abort"
    EXTERNAL_STEP = "external_step"
    SHOW_PROGRESS = "show_progress"

FlowResult = dict[str, Any]

# Create mock modules
ha = mock_module("homeassistant")
ha.const = mock_module("homeassistant.const")
ha.const.STATE_UNAVAILABLE = "unavailable"
ha.const.STATE_UNKNOWN = "unknown"
ha.const.STATE_ON = "on"
ha.const.STATE_OFF = "off"
ha.const.CONF_NAME = "name"
ha.const.CONF_API_KEY = "api_key"
ha.const.Platform = Platform
ha.const.EVENT_HOMEASSISTANT_START = "homeassistant_start"
ha.const.EVENT_HOMEASSISTANT_STOP = "homeassistant_stop"

ha.core = mock_module("homeassistant.core")
ha.core.HomeAssistant = MagicMock
ha.core.ServiceCall = MagicMock
ha.core.ServiceResponse = MagicMock
ha.core.CoreState = MagicMock()
ha.core.Event = MagicMock
ha.core.callback = lambda x: x

ha.config_entries = mock_module("homeassistant.config_entries")
ha.config_entries.ConfigEntry = MagicMock
ha.config_entries.ConfigFlow = MockConfigFlow
ha.config_entries.OptionsFlow = MockOptionsFlow
ha.config_entries.ConfigFlowResult = MagicMock 

ha.data_entry_flow = mock_module("homeassistant.data_entry_flow")
ha.data_entry_flow.FlowResultType = FlowResultType
ha.data_entry_flow.FlowResult = FlowResult

ha.helpers = mock_module("homeassistant.helpers")
ha.helpers.config_validation = mock_module("homeassistant.helpers.config_validation")
ha.helpers.config_validation.config_entry_only_config_schema = MagicMock(return_value=MagicMock())
ha.helpers.config_validation.boolean = MagicMock()
ha.helpers.config_validation.string = MagicMock()
ha.helpers.config_validation.template = MagicMock()
ha.helpers.config_validation.entity_id = MagicMock()
ha.helpers.config_validation.entity_ids = MagicMock()
ha.helpers.config_validation.entity_domain = MagicMock()
ha.helpers.config_validation.positive_int = MagicMock()
ha.helpers.config_validation.url = MagicMock()
ha.helpers.config_validation.enum = MagicMock()

ha.helpers.template = mock_module("homeassistant.helpers.template")
ha.helpers.template.Template = MagicMock
ha.helpers.intent = mock_module("homeassistant.helpers.intent")
ha.helpers.intent.IntentResponse = MagicMock
ha.helpers.httpx_client = mock_module("homeassistant.helpers.httpx_client")
ha.helpers.httpx_client.get_async_client = MagicMock()
ha.helpers.area_registry = mock_module("homeassistant.helpers.area_registry")
ha.helpers.device_registry = mock_module("homeassistant.helpers.device_registry")
ha.helpers.entity_registry = mock_module("homeassistant.helpers.entity_registry")

# Added for Azure
ha.helpers.llm = mock_module("homeassistant.helpers.llm")
ha.helpers.llm.DEFAULT_INSTRUCTIONS_PROMPT = "Default prompt"

# Added for Azure
ha.helpers.typing = mock_module("homeassistant.helpers.typing")
ha.helpers.typing.ConfigType = dict[str, Any]

# Added for Azure
ha.helpers.selector = mock_module("homeassistant.helpers.selector")
ha.helpers.selector.BooleanSelector = MagicMock
ha.helpers.selector.NumberSelector = MagicMock
ha.helpers.selector.NumberSelectorConfig = MagicMock
ha.helpers.selector.SelectSelector = MagicMock
ha.helpers.selector.SelectSelectorConfig = MagicMock
ha.helpers.selector.SelectSelectorMode = MagicMock
ha.helpers.selector.TemplateSelector = MagicMock

ha.helpers.update_coordinator = mock_module("homeassistant.helpers.update_coordinator")
ha.helpers.update_coordinator.DataUpdateCoordinator = MockDataUpdateCoordinator
ha.helpers.update_coordinator.CoordinatorEntity = MockCoordinatorEntity

ha.helpers.entity = mock_module("homeassistant.helpers.entity")
ha.helpers.entity.EntityCategory = MagicMock()

# Added for Cronostar (missing in my prev attempt? no I added it)
ha.helpers.frame = mock_module("homeassistant.helpers.frame")
ha.helpers.frame.ReportBehavior = MagicMock
ha.helpers.frame.report_usage = MagicMock()

ha.components = mock_module("homeassistant.components")
ha.components.sensor = mock_module("homeassistant.components.sensor")
ha.components.sensor.SensorEntity = MockEntity
ha.components.sensor.SensorDeviceClass = MagicMock()
ha.components.sensor.SensorStateClass = MagicMock()

ha.components.select = mock_module("homeassistant.components.select")
ha.components.select.SelectEntity = MockEntity

ha.components.switch = mock_module("homeassistant.components.switch")
ha.components.switch.SwitchEntity = MockEntity

ha.components.frontend = mock_module("homeassistant.components.frontend")
ha.components.frontend.add_extra_js_url = MagicMock()

ha.components.http = mock_module("homeassistant.components.http")
ha.components.http.StaticPathConfig = MagicMock
ha.components.http.start_http_server_and_save_config = MagicMock

# Added for Azure
ha.components.conversation = mock_module("homeassistant.components.conversation")
ha.components.conversation.AbstractConversationAgent = MagicMock
ha.components.conversation.ConversationInput = MagicMock
ha.components.conversation.ConversationResult = MagicMock
ha.components.conversation.DOMAIN = "conversation"
# Also need to ensure get_agent_manager etc. if used, but Azure agent mainly uses AbstractConversationAgent.
# In test_conversation.py, we verify agent processes. 
# agent.py imports: conversation.get_agent_manager(self._hass).
ha.components.conversation.get_agent_manager = MagicMock()
ha.components.conversation.ResponseType = MagicMock()

ha.components.persistent_notification = mock_module("homeassistant.components.persistent_notification")
ha.components.persistent_notification.async_create = MagicMock()

ha.loader = mock_module("homeassistant.loader")
ha.loader.async_get_integration = AsyncMock()

class MockHomeAssistantError(Exception):
    def __init__(self, *args, **kwargs):
        self.translation_domain = kwargs.get("translation_domain")
        self.translation_key = kwargs.get("translation_key")
        self.translation_placeholders = kwargs.get("translation_placeholders")
        super().__init__(*args)

ha.exceptions = mock_module("homeassistant.exceptions")
ha.exceptions.HomeAssistantError = MockHomeAssistantError
ha.exceptions.ConfigEntryNotReady = type("ConfigEntryNotReady", (Exception,), {})

ha.util = mock_module("homeassistant.util")
ha.util.dt = MagicMock()

# Mock voluptuous
vol = mock_module("voluptuous")
vol.Schema = MagicMock
vol.Optional = MagicMock
vol.Required = MagicMock
vol.All = MagicMock
vol.Coerce = MagicMock
vol.In = MagicMock
vol.ALLOW_EXTRA = "ALLOW_EXTRA"

# Inject into sys.modules
sys.modules["homeassistant"] = ha
sys.modules["homeassistant.const"] = ha.const
sys.modules["homeassistant.core"] = ha.core
sys.modules["homeassistant.config_entries"] = ha.config_entries
sys.modules["homeassistant.data_entry_flow"] = ha.data_entry_flow
sys.modules["homeassistant.helpers"] = ha.helpers
sys.modules["homeassistant.helpers.config_validation"] = ha.helpers.config_validation
sys.modules["homeassistant.helpers.template"] = ha.helpers.template
sys.modules["homeassistant.helpers.intent"] = ha.helpers.intent
sys.modules["homeassistant.helpers.httpx_client"] = ha.helpers.httpx_client
sys.modules["homeassistant.helpers.area_registry"] = ha.helpers.area_registry
sys.modules["homeassistant.helpers.device_registry"] = ha.helpers.device_registry
sys.modules["homeassistant.helpers.entity_registry"] = ha.helpers.entity_registry
sys.modules["homeassistant.helpers.llm"] = ha.helpers.llm
sys.modules["homeassistant.helpers.typing"] = ha.helpers.typing
sys.modules["homeassistant.helpers.selector"] = ha.helpers.selector
sys.modules["homeassistant.helpers.update_coordinator"] = ha.helpers.update_coordinator
sys.modules["homeassistant.helpers.frame"] = ha.helpers.frame
sys.modules["homeassistant.helpers.entity"] = ha.helpers.entity
sys.modules["homeassistant.components"] = ha.components
sys.modules["homeassistant.components.sensor"] = ha.components.sensor
sys.modules["homeassistant.components.select"] = ha.components.select
sys.modules["homeassistant.components.switch"] = ha.components.switch
sys.modules["homeassistant.components.frontend"] = ha.components.frontend
sys.modules["homeassistant.components.http"] = ha.components.http
sys.modules["homeassistant.components.conversation"] = ha.components.conversation
sys.modules["homeassistant.components.persistent_notification"] = ha.components.persistent_notification
sys.modules["homeassistant.loader"] = ha.loader
sys.modules["homeassistant.exceptions"] = ha.exceptions
sys.modules["homeassistant.util"] = ha.util
sys.modules["voluptuous"] = vol
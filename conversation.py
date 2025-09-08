"""Conversation entity backed by Azure OpenAI Chat Completions."""  
from __future__ import annotations  
  
import asyncio  
import importlib  
import inspect  
import logging  
import uuid  
from typing import Any, Literal, cast  
  
import openai  
from homeassistant.components import conversation  
from homeassistant.config_entries import ConfigEntry  
from homeassistant.const import CONF_API_KEY, MATCH_ALL  
from homeassistant.core import HomeAssistant  
from homeassistant.exceptions import HomeAssistantError  
from homeassistant.helpers import llm  
from homeassistant.helpers.entity_platform import AddEntitiesCallback  
from homeassistant.helpers.httpx_client import get_async_client  
from homeassistant.helpers.template import Template, TemplateError  
from homeassistant.util import ulid  
from homeassistant.helpers import entity_registry as er  
  
from . import normalize_azure_endpoint  
from .const import (  
    CONF_API_BASE,  
    CONF_CHAT_MODEL,  
    CONF_MAX_TOKENS,  
    CONF_PROMPT,  
    CONF_TEMPERATURE,  
    CONF_TOP_P,  
    CONF_API_TIMEOUT,  
    DOMAIN,  
    RECOMMENDED_CHAT_MODEL,  
    RECOMMENDED_MAX_TOKENS,  
    RECOMMENDED_TEMPERATURE,  
    RECOMMENDED_TOP_P,  
    RECOMMENDED_API_TIMEOUT,  
)  
  
# ---------------------------------------------------------------  
#  `CONF_LLM_HASS_API` può non esistere su release < 2024.10  
# ---------------------------------------------------------------  
try:  
    from homeassistant.const import CONF_LLM_HASS_API  # type: ignore  
except ImportError:  # pragma: no cover  
    CONF_LLM_HASS_API = "llm_hass_api"  # type: ignore  
  
_LOGGER = logging.getLogger(__name__)  
  
# ----------------------------------------------------------------------  
#  ConversationResult / AgentResponseText import-helper  
# ----------------------------------------------------------------------  
def _best_effort_imports() -> tuple[type, type, bool]:  
    """  
    Return (AgentResponseText, ConversationResult, expects_agent_response).  
    """  
    # ---- ConversationResult -----------------------------------------  
    try:  
        from homeassistant.components.conversation import (  # type: ignore  
            ConversationResult as CR,  
        )  
    except ImportError:  
        CR = None  # type: ignore[assignment]  
  
    if CR is None:  
        class _ConversationResultShim:  # noqa: D401  
            def __init__(  
                self,  
                response: Any,  
                conversation_id: str | None = None,  
                continue_conversation: bool | None = False,  
            ) -> None:  
                self.response = response  
                self.conversation_id = conversation_id  
                self.continue_conversation = continue_conversation  
  
        CR = cast(type, _ConversationResultShim)  # type: ignore[initial-value]  
  
    # ---- AgentResponseText ------------------------------------------  
    AgentCls: type | None = None  
    for mod_name in (  
        "homeassistant.components.conversation.response",  
        "homeassistant.components.conversation.agent",  
        "homeassistant.components.assist_pipeline.response",  
        "homeassistant.components.assist_pipeline.agent",  
    ):  
        try:  
            mod = importlib.import_module(mod_name)  
        except ModuleNotFoundError:  
            continue  
        for attr in (  
            "AgentResponseText",  
            "TextAgentResponse",  
            "PlainTextResponse",  
            "TextResponse",  
        ):  
            AgentCls = getattr(mod, attr, None)  
            if isinstance(AgentCls, type):  
                break  
        if AgentCls:  
            break  
  
    if AgentCls is None:  
        class _AgentResponseTextShim:  # type: ignore[too-few-public-methods]  
            def __init__(self, text: str | None = None, **kwargs: Any) -> None:  
                self.text = text or kwargs.get("text", "")  
                self.speech = {"plain": {"text": self.text}}  
  
        AgentCls = _AgentResponseTextShim  # type: ignore[assignment]  
  
    # ---- does ConversationResult expect an AgentResponse*? ----------  
    try:  
        sig = inspect.signature(CR)  # type: ignore[arg-type]  
        expects = "AgentResponse" in str(sig.parameters["response"].annotation)  
    except Exception:  
        expects = True  
  
    return AgentCls, CR, expects  
  
AgentResponseText, ConversationResult, _EXPECTS_AGENT_RSP = _best_effort_imports()  
  
# ----------------------------------------------------------------------  
#  Misc helpers  
# ----------------------------------------------------------------------  
def _token_param() -> str:  
    return (  
        "max_tokens"  
        if "max_tokens" in getattr(openai, "__all__", [])  # type: ignore[attr-defined]  
        else "max_completion_tokens"  
    )  
  
# ----------------------------------------------------------------------  
#  Platform setup  
# ----------------------------------------------------------------------  
async def async_setup_entry(  
    hass: HomeAssistant,  
    entry: ConfigEntry,  
    async_add_entities: AddEntitiesCallback,  
) -> None:  
    async_add_entities([AzureOpenAIConversationEntity(hass, entry)])  
  
class AzureOpenAIConversationEntity(  
    conversation.ConversationEntity, conversation.AbstractConversationAgent  
):  
    """Conversation agent – Azure OpenAI Chat Completions."""  
  
    _attr_should_poll = False  
    _attr_supports_streaming = False  
  
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:  
        self.hass = hass  
        self._entry = entry  
  
        data = entry.data  
        opts = entry.options or {}  
  
        self._api_base: str = opts.get(CONF_API_BASE) or data[CONF_API_BASE]  
        self._model: str = (  
            opts.get(CONF_CHAT_MODEL)  
            or data.get(CONF_CHAT_MODEL)  
            or RECOMMENDED_CHAT_MODEL  
        )  
        self._prompt: str = opts.get(CONF_PROMPT, llm.DEFAULT_INSTRUCTIONS_PROMPT)  
        self._temperature: float = float(  
            opts.get(CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE)  
        )  
        self._top_p: float = float(opts.get(CONF_TOP_P, RECOMMENDED_TOP_P))  
        self._max_tokens: int = int(opts.get(CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS))  
        self._api_timeout: int = int(opts.get(CONF_API_TIMEOUT, RECOMMENDED_API_TIMEOUT))  
  
        # ---------- visibilità / naming --------------------------------  
        self._attr_name = f"Azure OpenAI SDK Conversation – {self._model}"  
        self._attr_entity_id = (  
            f"conversation.azure_openai_sdk_conversation_{entry.entry_id[-6:]}"  
        )  
        self._attr_unique_id = entry.entry_id  
  
        # ---------- HASS-API abilitation -------------------------------  
        llm_api_opt = opts.get(CONF_LLM_HASS_API)  
        if isinstance(llm_api_opt, list):  
            llm_api_opt = (  
                llm.LLM_API_ASSIST if llm.LLM_API_ASSIST in llm_api_opt else None  
            )  
        self._attr_llm_hass_api = llm_api_opt or llm.LLM_API_ASSIST  
  
        self._client: openai.AsyncAzureOpenAI | None = None  
        self._history: dict[str, list[dict[str, Any]]] = {}  
        self._history_lock = asyncio.Lock()  
        self._max_history = 12  
  
    # ------------------------------------------------------------------  
    #  Client helper  
    # ------------------------------------------------------------------  
    async def _get_client(self) -> openai.AsyncAzureOpenAI:  
        if self._client is None:  
            _LOGGER.debug("Creating Azure OpenAI client for %s", self._api_base)  
            from openai import AsyncAzureOpenAI  
  
            root = (  
                normalize_azure_endpoint(self._api_base)  
                .rstrip("/")  
                .removesuffix("/openai")  
            )  
            self._client = AsyncAzureOpenAI(  
                api_key=self._entry.data[CONF_API_KEY],  
                api_version="2025-01-01-preview",  
                azure_endpoint=root,  
                http_client=get_async_client(self.hass),  
            )  
        return self._client  
  
    # ------------------------------------------------------------------  
    #  Prompt / history helpers  
    # ------------------------------------------------------------------  
    async def _get_exposed_entities(self) -> list[Any]:  
        """Return entities for conversation with area support."""  
        ent_reg = er.async_get(self.hass)  
        entities: list[dict[str, Any]] = []  
        for st in self.hass.states.async_all():  
            entry = ent_reg.async_get(st.entity_id)  
            entities.append(  
                {  
                    "entity_id": st.entity_id,  
                    "name": st.name or st.entity_id,  
                    "state": st.state,  
                    "aliases": [],  
                    "area": entry.area_id if entry else None,  
                }  
            )  
        return entities  
  
    async def _render_prompt(  
        self, user_input: str, conversation_id: str | None  
    ) -> str:  
        """Evaluate the Jinja2 template stored in self._prompt."""  
        if not self._prompt:  
            return ""  
        try:  
            tpl = Template(self._prompt, self.hass)  
            rendered = tpl.async_render(  
                {  
                    "user_input": user_input,  
                    "conversation_id": conversation_id,  
                    "hass": self.hass,  
                    "exposed_entities": await self._get_exposed_entities(),  
                },  
                parse_result=False,  
            )  
            if inspect.isawaitable(rendered):  
                rendered = await rendered  # type: ignore[assignment]  
            return str(rendered).strip()  
        except TemplateError as err:  
            _LOGGER.error("Prompt template render error: %s", err)  
            return self._prompt  
  
    async def _build_messages(  
        self, user_input: str, conv_id: str | None  
    ) -> list[dict[str, Any]]:  
        msgs: list[dict[str, Any]] = []  
        if self._prompt:  
            rendered_prompt = await self._render_prompt(user_input, conv_id)  
            if rendered_prompt:  
                msgs.append({"role": "system", "content": rendered_prompt})  
        if conv_id and (hist := self._history.get(conv_id)):  
            msgs.extend(hist)  
        msgs.append({"role": "user", "content": user_input})  
        return msgs  
  
    async def _update_history(  
        self,  
        conv_id: str | None,  
        user_msg: dict[str, Any],  
        assistant_msg: dict[str, Any],  
    ) -> None:  
        if not conv_id:  
            return  
        async with self._history_lock:  
            hist = self._history.setdefault(conv_id, [])  
            hist.extend([user_msg, assistant_msg])  
            if len(hist) > self._max_history:  
                self._history[conv_id] = hist[-self._max_history :]  
  
    # ------------------------------------------------------------------  
    #  Misc helpers  
    # ------------------------------------------------------------------  
    @staticmethod  
    def _extract_reply(message: Any) -> str:  
        if message is None:  
            return ""  
        if isinstance(message, dict):  
            content = message.get("content")  
            if isinstance(content, str):  
                return content.strip()  
        content = getattr(message, "content", None)  
        if isinstance(content, str):  
            return content.strip()  
        return ""  
  
    @staticmethod  
    def _generate_conversation_id() -> str:  
        try:  
            return ulid.ulid_now()  
        except Exception:  
            return str(uuid.uuid4())  
  
    # ------------------------------------------------------------------  
    #  ChatLog creation helper  
    # ------------------------------------------------------------------  
    def _create_chat_log(self, conversation_id: str | None):  
        ChatLogCls = conversation.ChatLog  
        sig = inspect.signature(ChatLogCls)  
        kwargs: dict[str, Any] = {}  
        if "hass" in sig.parameters:  
            kwargs["hass"] = self.hass  
        if "conversation_id" in sig.parameters and conversation_id:  
            kwargs["conversation_id"] = conversation_id  
        if "continue_conversation" in sig.parameters:  
            kwargs["continue_conversation"] = False  
        return ChatLogCls(**kwargs)  # type: ignore[arg-type]  
  
    # ------------------------------------------------------------------  
    #  ConversationEntity basics  
    # ------------------------------------------------------------------  
    @property  
    def supported_languages(self) -> list[str] | Literal["*"]:  
        return MATCH_ALL  
  
    async def async_added_to_hass(self) -> None:  
        await super().async_added_to_hass()  
        conversation.async_set_agent(self.hass, self._entry, self)  
  
    async def async_will_remove_from_hass(self) -> None:  
        conversation.async_unset_agent(self.hass, self._entry)  
        await super().async_will_remove_from_hass()  
        if self._client is not None:  
            if hasattr(self._client, "aclose"):  
                await self._client.aclose()  # type: ignore[attr-defined]  
            else:  
                await self.hass.async_add_executor_job(self._client.close)  
  
    # ------------------------------------------------------------------  
    #  NEW API  (_async_handle_message)  
    # ------------------------------------------------------------------  
    async def _async_handle_message(  
        self,  
        user_input: conversation.ConversationInput,  
        chat_log: conversation.ChatLog,  
    ) -> conversation.ConversationResult:  
        try:  
            await chat_log.async_update_llm_data(  
                DOMAIN, user_input, False, self._prompt  
            )  
        except conversation.ConverseError as err:  
            return err.as_conversation_result()  
  
        try:  
            client = await self._get_client()  
            extra_body = {_token_param(): self._max_tokens}  
            messages = await self._build_messages(  
                user_input.text, chat_log.conversation_id  
            )  
            resp = await client.chat.completions.create(  
                model=self._model,  
                messages=messages,  
                temperature=self._temperature,  
                top_p=self._top_p,  
                response_format={"type": "text"},  
                extra_body=extra_body,  
                timeout=self._api_timeout,  # Aggiunto timeout configurabile  
            )  
            reply = self._extract_reply(resp.choices[0].message)  # type: ignore[index]  
            await self._update_history(  
                chat_log.conversation_id,  
                {"role": "user", "content": user_input.text},  
                {"role": "assistant", "content": reply},  
            )  
        except openai.RateLimitError as err:  
            _LOGGER.error("Rate limited: %s", err)  
            raise HomeAssistantError("Rate limited or insufficient funds") from err  
        except openai.APIConnectionError as err:  
            _LOGGER.error("Connection error with Azure OpenAI: %s", err)  
            raise HomeAssistantError("Connection error with Azure OpenAI") from err  
        except openai.OpenAIError as err:  
            _LOGGER.error("Azure OpenAI error: %s", err)  
            raise HomeAssistantError("Error talking to Azure OpenAI") from err  
  
        # --- add assistant content to ChatLog --------------------------  
        async def _consume(obj):  
            if inspect.isasyncgen(obj):  
                async for _ in obj:  
                    pass  
            elif inspect.isawaitable(obj):  
                await obj  
  
        if hasattr(chat_log, "async_add_assistant_content"):  
            await _consume(  
                chat_log.async_add_assistant_content(  
                    self.entity_id, {"role": "assistant", "content": reply}  
                )  
            )  
        elif hasattr(chat_log, "async_add_delta_content_stream"):  
            async def _stream():  
                yield {"role": "assistant"}  
                yield {"content": reply}  
  
            await _consume(  
                chat_log.async_add_delta_content_stream(self.entity_id, _stream())  
            )  
        elif hasattr(chat_log, "async_add_content"):  
            from homeassistant.components.conversation import AssistantContent  
  
            await chat_log.async_add_content(  
                self.entity_id,  
                AssistantContent(role="assistant", content=reply),  
            )  
  
        # --- build response object -------------------------------------  
        if _EXPECTS_AGENT_RSP:  
            result_response = AgentResponseText(text=reply)  
        else:  
            from homeassistant.helpers import intent as intent_mod  # noqa: WPS433  
  
            intent_resp = intent_mod.IntentResponse(language=user_input.language)  
            if hasattr(intent_resp, "async_set_speech"):  
                intent_resp.async_set_speech(reply)  
            else:  
                intent_resp.set_speech(reply)  # type: ignore[attr-defined]  
            result_response = intent_resp  
  
        return ConversationResult(  
            response=result_response,  
            conversation_id=chat_log.conversation_id,  
            continue_conversation=False,  
        )  
  
    # ------------------------------------------------------------------  
    #  OLD API (async_process) – compatibility shim  
    # ------------------------------------------------------------------  
    async def async_process(  
        self,  
        user_input,  
        context=None,  
        conversation_id: str | None = None,  
        language: str | None = None,  
    ):  
        if not isinstance(user_input, conversation.ConversationInput):  
            text = getattr(user_input, "text", str(user_input))  
            conversation_id = getattr(user_input, "conversation_id", conversation_id)  
            language = getattr(user_input, "language", language) or "en"  
            user_input = conversation.ConversationInput(  
                text=text,  
                conversation_id=conversation_id,  
                language=language,  
                agent_id=self.entity_id,  
            )  
  
        if not conversation_id:  
            conversation_id = self._generate_conversation_id()  
  
        chat_log = self._create_chat_log(conversation_id)  
        return await self._async_handle_message(user_input, chat_log)  
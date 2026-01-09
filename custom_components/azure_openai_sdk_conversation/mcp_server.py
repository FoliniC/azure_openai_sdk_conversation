"""
MCP Server per Home Assistant con gestione stateful del contesto.
Invia il system prompt completo solo alla prima richiesta, poi mantiene
lo stato e invia solo le entità che hanno cambiato stato.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict

_LOGGER = logging.getLogger(__name__)


@dataclass
class EntityState:
    """Rappresentazione dello stato di un'entità."""

    entity_id: str
    name: str
    state: str
    area: str
    aliases: list[str]
    last_updated: str

    def __eq__(self, other: object) -> bool:
        """Due stati sono uguali se lo stato corrente è identico."""
        if not isinstance(other, EntityState):
            return False
        return self.entity_id == other.entity_id and self.state == other.state


class HAMCPStateManager:
    """Gestisce lo stato persistente delle entità HA per conversazioni MCP."""

    def __init__(self) -> None:
        """Inizializza il gestore di stato."""
        # Mappa conversation_id -> stato completo delle entità
        self._conversations: Dict[str, Dict[str, EntityState]] = {}
        # Mappa conversation_id -> timestamp ultimo aggiornamento
        self._last_updated: Dict[str, datetime] = {}
        # TTL per pulizia conversazioni inattive (default 1 ora)
        self._ttl_seconds: int = 3600

    def is_new_conversation(self, conversation_id: str) -> bool:
        """Verifica se è una nuova conversazione (richiede system prompt completo)."""
        return conversation_id not in self._conversations

    def get_initial_prompt(
        self,
        conversation_id: str,
        entities: list[dict[str, Any]],
        base_prompt: str,
    ) -> str:
        """
        Genera il system prompt iniziale completo e memorizza lo stato.

        Args:
            conversation_id: ID univoco della conversazione
            entities: Lista entità esposte da HA
            base_prompt: Template base del prompt

        Returns:
            System prompt formattato con tutte le entità
        """
        # Converti entità in EntityState e memorizza
        entity_states = {}
        for e in entities:
            state = EntityState(
                entity_id=e["entity_id"],
                name=e["name"],
                state=e["state"],
                area=e.get("area", ""),
                aliases=e.get("aliases", []),
                last_updated=datetime.now(timezone.utc).isoformat(),
            )
            entity_states[e["entity_id"]] = state

        self._conversations[conversation_id] = entity_states
        self._last_updated[conversation_id] = datetime.now(timezone.utc)

        # Formatta il prompt con CSV raggruppato per area
        entities_csv = self._format_entities_as_csv(entity_states.values())

        prompt = f"""{base_prompt}

**Entity State Information** (Initial Full State):
Current time: {datetime.now(timezone.utc).isoformat()}

{entities_csv}

This is your initial state snapshot. In subsequent messages, you will only receive updates for entities that changed state.
"""

        _LOGGER.info(
            "MCP: Created initial state for conversation %s with %d entities (%d tokens est.)",
            conversation_id,
            len(entity_states),
            len(prompt.split()) * 1.3,  # stima approssimativa
        )

        return prompt

    def get_delta_prompt(
        self,
        conversation_id: str,
        current_entities: list[dict[str, Any]],
    ) -> str | None:
        """
        Genera un prompt delta contenente solo le entità che hanno cambiato stato.

        Args:
            conversation_id: ID della conversazione
            current_entities: Stato attuale delle entità da HA

        Returns:
            Prompt con solo i cambiamenti, None se nessun cambiamento
        """
        if conversation_id not in self._conversations:
            _LOGGER.warning(
                "MCP: Conversation %s not found, should use initial prompt",
                conversation_id,
            )
            return None

        stored_states = self._conversations[conversation_id]
        changed_entities: list[EntityState] = []
        new_entities: list[EntityState] = []

        # Identifica cambiamenti e nuove entità
        for e in current_entities:
            entity_id = e["entity_id"]
            current_state = EntityState(
                entity_id=entity_id,
                name=e["name"],
                state=e["state"],
                area=e.get("area", ""),
                aliases=e.get("aliases", []),
                last_updated=datetime.now(timezone.utc).isoformat(),
            )

            if entity_id not in stored_states:
                # Nuova entità
                new_entities.append(current_state)
                stored_states[entity_id] = current_state
            elif stored_states[entity_id] != current_state:
                # Stato cambiato
                changed_entities.append(current_state)
                stored_states[entity_id] = current_state

        # Identifica entità rimosse
        current_ids = {e["entity_id"] for e in current_entities}
        removed_ids = set(stored_states.keys()) - current_ids
        for eid in removed_ids:
            del stored_states[eid]

        # Aggiorna timestamp
        self._last_updated[conversation_id] = datetime.now(timezone.utc)

        # Se non ci sono cambiamenti, non inviare nulla
        if not changed_entities and not new_entities and not removed_ids:
            return None

        # Formatta il delta
        delta_parts = [
            f"**State Update** (Delta at {datetime.now(timezone.utc).isoformat()}):"
        ]

        if changed_entities:
            delta_parts.append("\nChanged entities:")
            delta_parts.append(self._format_entities_as_csv(changed_entities))

        if new_entities:
            delta_parts.append("\nNew entities:")
            delta_parts.append(self._format_entities_as_csv(new_entities))

        if removed_ids:
            delta_parts.append(f"\nRemoved entities: {', '.join(removed_ids)}")

        delta_prompt = "\n".join(delta_parts)

        _LOGGER.info(
            "MCP: Delta for conversation %s: %d changed, %d new, %d removed (%d tokens est.)",
            conversation_id,
            len(changed_entities),
            len(new_entities),
            len(removed_ids),
            len(delta_prompt.split()) * 1.3,
        )

        return delta_prompt

    def _format_entities_as_csv(self, entities: list[EntityState]) -> str:
        """Formatta una lista di entità come CSV raggruppato per area."""
        # Raggruppa per area
        by_area: Dict[str, list[EntityState]] = {}
        for e in entities:
            area = e.area or "_no_area"
            if area not in by_area:
                by_area[area] = []
            by_area[area].append(e)

        # Formatta CSV
        lines = []
        for area in sorted(by_area.keys()):
            if area == "_no_area":
                lines.append("\nEntities without configured area:")
            else:
                lines.append(f"\nEntities in: {area}")

            lines.append("csv")
            lines.append("entity_id;name;state;aliases")

            for e in sorted(by_area[area], key=lambda x: x.entity_id):
                aliases_str = "/".join(e.aliases) if e.aliases else ""
                lines.append(f"{e.entity_id};{e.name};{e.state};{aliases_str}")

        return "\n".join(lines)

    async def cleanup_old_conversations(self) -> None:
        """Rimuove conversazioni inattive oltre il TTL."""
        now = datetime.now(timezone.utc)
        to_remove = []

        for conv_id, last_update in self._last_updated.items():
            age_seconds = (now - last_update).total_seconds()
            if age_seconds > self._ttl_seconds:
                to_remove.append(conv_id)

        for conv_id in to_remove:
            del self._conversations[conv_id]
            del self._last_updated[conv_id]
            _LOGGER.debug("MCP: Cleaned up conversation %s (inactive)", conv_id)

    def get_stats(self) -> dict[str, Any]:
        """Ritorna statistiche sullo stato corrente."""
        return {
            "active_conversations": len(self._conversations),
            "total_entities_tracked": sum(
                len(states) for states in self._conversations.values()
            ),
            "ttl_seconds": self._ttl_seconds,
        }


class HAMCPServer:
    """
    Server MCP per Home Assistant.
    Intercetta le richieste di conversazione e gestisce il contesto in modo stateful.
    """

    def __init__(self, hass: Any, original_agent: Any) -> None:
        """
        Args:
            hass: Istanza Home Assistant
            original_agent: Agent originale (AzureOpenAIConversationAgent)
        """
        self._hass = hass
        self._agent = original_agent
        self._state_mgr = HAMCPStateManager()
        self._cleanup_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Avvia il server MCP e il task di pulizia."""
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        _LOGGER.info("MCP Server started for Home Assistant")

    async def stop(self) -> None:
        """Ferma il server MCP."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        _LOGGER.info("MCP Server stopped")

    async def _periodic_cleanup(self) -> None:
        """Task periodico per pulizia conversazioni inattive."""
        while True:
            try:
                await asyncio.sleep(300)  # ogni 5 minuti
                await self._state_mgr.cleanup_old_conversations()
            except asyncio.CancelledError:
                break
            except Exception as err:
                _LOGGER.error("MCP: Cleanup error: %r", err)

    def prepare_system_message(
        self,
        conversation_id: str | None,
        entities: list[dict[str, Any]],
        base_prompt: str,
    ) -> str:
        """
        Prepara il system message appropriato (completo o delta).

        Returns:
            System message da inviare al modello
        """
        if not conversation_id:
            # Senza ID, invia sempre il prompt completo (fallback sicuro)
            return self._format_full_prompt(entities, base_prompt)

        if self._state_mgr.is_new_conversation(conversation_id):
            # Prima richiesta: invia prompt completo
            return self._state_mgr.get_initial_prompt(
                conversation_id, entities, base_prompt
            )
        else:
            # Richieste successive: invia solo delta
            delta = self._state_mgr.get_delta_prompt(conversation_id, entities)
            if delta:
                return delta
            else:
                # Nessun cambiamento: invia un messaggio minimale
                return f"**State Update**: No changes since last update at {datetime.now(timezone.utc).isoformat()}"

    def _format_full_prompt(
        self,
        entities: list[dict[str, Any]],
        base_prompt: str,
    ) -> str:
        """Fallback: formatta prompt completo senza memorizzazione."""
        # Simula il template Jinja2 originale
        by_area: Dict[str, list[dict]] = {}
        for e in entities:
            area = e.get("area") or "_no_area"
            if area not in by_area:
                by_area[area] = []
            by_area[area].append(e)

        lines = [base_prompt, "\n**Entity State Information**:"]
        lines.append(f"Current time: {datetime.now(timezone.utc).isoformat()}\n")

        for area in sorted(by_area.keys()):
            if area == "_no_area":
                lines.append("\nEntities without configured area:")
            else:
                lines.append(f"\nEntities in: {area}")

            lines.append("csv")
            lines.append("entity_id;name;state;aliases")

            for e in sorted(by_area[area], key=lambda x: x["entity_id"]):
                aliases_str = "/".join(e.get("aliases", []))
                lines.append(f"{e['entity_id']};{e['name']};{e['state']};{aliases_str}")

        return "\n".join(lines)

    def get_stats(self) -> dict[str, Any]:
        """Ritorna statistiche del server MCP."""
        return self._state_mgr.get_stats()


# ============================================================================
# INTEGRAZIONE NEL COMPONENTE ESISTENTE
# ============================================================================


def patch_conversation_agent(agent: Any, hass: Any) -> Any:
    """
    Modifica (monkey-patch) l'agent esistente per usare MCP.

    Args:
        agent: AzureOpenAIConversationAgent originale
        hass: Istanza Home Assistant

    Returns:
        Agent wrappato con MCP
    """
    mcp_server = HAMCPServer(hass, agent)

    # Avvia il server MCP
    asyncio.create_task(mcp_server.start())

    # Salva il metodo originale
    ############
    def _mcp_prepare_system_message(self, *args, **kwargs):
        """Normalize MCP prepare_system_message return types across versions.

        Always returns (sys_msg: str, is_initial: bool).
        Any additional values are stored in self._mcp_prepare_extras for potential later use.
        """
        prep_result = self._mcp_server.prepare_system_message(*args, **kwargs)

        sys_msg = ""
        is_initial = False

        # Expected older/newer signatures:
        # - (sys_msg, is_initial)
        # - (sys_msg, is_initial, <extras...>)
        # - {"system_message"|"message": str, "is_initial": bool, ...}
        # - str
        if isinstance(prep_result, tuple):
            if len(prep_result) >= 2:
                sys_msg = prep_result[0]
                is_initial = bool(prep_result[1])
                if len(prep_result) > 2:
                    # Save any extra payload for debugging or future features
                    self._mcp_prepare_extras = prep_result[2:]
                    try:
                        _LOGGER.debug(
                            "MCP prepare_system_message returned %d extra values; stored in self._mcp_prepare_extras",
                            len(prep_result) - 2,
                        )
                    except Exception:
                        # Keep robust even if logging fails
                        pass
            elif len(prep_result) == 1:
                sys_msg = prep_result[0]
            else:
                _LOGGER.warning(
                    "MCP prepare_system_message returned an empty tuple; using defaults"
                )
        elif isinstance(prep_result, dict):
            sys_msg = (
                prep_result.get("system_message") or prep_result.get("message") or ""
            )
            is_initial = bool(prep_result.get("is_initial", False))
            self._mcp_prepare_extras = prep_result
            _LOGGER.debug(
                "MCP prepare_system_message returned a dict; normalized to (sys_msg, is_initial)"
            )
        else:
            # Assume it's a string or something string-coercible
            sys_msg = str(prep_result)

        return sys_msg, is_initial
        ###########

    async def mcp_render_system_message(
        raw_sys_msg: str,
        azure_ctx: dict[str, Any],
        conversation_id: str | None = None,
    ) -> str:
        """Override del metodo _render_system_message per usare MCP."""
        # Raccogli entità esposte
        entities = agent._collect_exposed_entities()

        # Usa MCP per preparare il messaggio (completo o delta)
        return mcp_server.prepare_system_message(
            conversation_id=conversation_id,
            entities=entities,
            base_prompt=raw_sys_msg,
        )

    # Sostituisci il metodo
    agent._render_system_message = mcp_render_system_message
    agent._mcp_server = mcp_server  # Mantieni riferimento

    _LOGGER.info("MCP Server integrated into conversation agent")

    return agent

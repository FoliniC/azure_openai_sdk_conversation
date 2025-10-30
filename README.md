# Azure OpenAI SDK Conversation

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)

This custom integration adds a conversation agent powered by Azure OpenAI in Home Assistant, based on the original OpenAI Conversation integration.

## Features

*   **Azure OpenAI Integration**: Uses OpenAI models available through Azure.
*   **Stateful Conversations**: A stateful MCP (Master Control Program) server sits between Home Assistant and Azure to enable more complex interactions.
*   **State History**: Ability to retrieve state history of exposed entities.
*   **Configurable Logging**: Change log verbosity from the options UI.
*   **Custom Template Information**: Pass custom information using Home Assistant templates.
*   **Synonym Normalization**: Substitute similar prompts using a vocabulary.
*   **Prompt Execution Control**: Ability to stop long-running prompts.
*   **History**: Stores prompt history.
*   **Web Search**: Optional Bing search integration for real-time information.
*   **Flexible Configuration**: Configure and modify endpoint, model, and max tokens in the options UI.

## Architecture: The MCP Server

Starting with version 0.4, this integration uses an intermediary "MCP (Master Control Program) Server" to manage the conversation state. This allows for more complex and stateful interactions, as the MCP server sits between Home Assistant and the stateless Azure OpenAI service.

```
+-----------------+      +--------------+      +-----------------+
¦  Home Assistant ¦?----?¦  MCP Server  ¦?----?¦  Azure OpenAI   ¦
¦   (conversation)¦      ¦  (stateful)  ¦      ¦   (stateless)   ¦
+-----------------+      +--------------+      +-----------------+
                               ¦
                               ?
                         +----------+
                         ¦  State   ¦
                         ¦  Cache   ¦
                         +----------+
```

## Installation

Install from HACS by adding this GitHub repository (`https://github.com/FoliniC/azure_openai_sdk_conversation`) as a custom repository.

## Configuration

Configuration can be changed in the integration's options page after it has been added.

<img width="431" height="452" alt="image" src="https://github.com/user-attachments/assets/656a3d06-9e0d-4a8a-b78e-c56016fe00c0" />

For troubleshooting, it is useful to add the following to your `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.azure_openai_sdk_conversation: debug
    homeassistant.components.assist_pipeline: debug
    homeassistant.components.conversation: debug
```

### Example System Prompt

Here is an example of a system message to instruct the assistant:
```
You are an assistant controlling a Home Assistant instance. 
Current time: {{ now() }}

Your operating instructions are:

1. **Entity State Information**:
Use the following entity state tables to answer questions about the current state of devices or areas:
{% set ns = namespace(ents=[]) -%}
{%- for e in exposed_entities -%}
{%- set ns.ents = ns.ents + [{
"entity_id": e.entity_id,
"name": e.name,
"state": e.state,
"area": (area_name(e.entity_id) or ""),
"aliases": e.aliases,
}] -%}
{%- endfor -%}
{%- set sorted_list = (ns.ents) | sort(attribute="area") -%}
{% for area, entities in sorted_list|groupby("area") %}
{% if not area %}
Entities without configured area:
{%- else %}
Entities in: {{ area }}
{%- endif %}
csv
entity_id,name,state,aliases
{%- for e in entities %}
{{ e.entity_id }};{{ e.name }};{{ e.state }};{{ e.aliases | join('/') }}
{%- endfor %}
{%- endfor %}

2. **Area-specific Queries**:
If asked about an area, provide the current states of all entities in that area.

3. **Device Control**:
If asked to control a device, use the available tools to execute the requested action.

4. **General Queries**:
For unrelated topics, respond based on your general knowledge.

5. **Response Style**:
- Keep replies casual, short, and concise.
- Use "this: that" format for clarity.
- Avoid repeating parts of the user's question.
- Use short forms of entity names for brevity.
- Speak in italian.
```

## Tested Models
- gpt-5
- grok-3
- o1
- gpt-4o-mini
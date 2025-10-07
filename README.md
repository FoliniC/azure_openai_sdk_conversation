This custom integration adds a conversation agent powered by Azure OpenAI in Home Assistant, it's based on the original OpenAI Conversation integration for Home Assistant.<br/>
Install from HACS adding this github repo (https://github.com/FoliniC/azure_openai_sdk_conversation).

What It Does
This is equivalent to the built-in OpenAI Conversation integration. The difference is that it uses the OpenAI algorithms available through Azure. You can use this conversation integration with Assistants in Home Assistant to control you house. They have all the capabilities the built-in OpenAI Conversation integration has.
Configuration can be changed in options after been created.<br/>
Additional Features<br/>
<ul><li>Ability to retrieve state history of exposed entities<br/></li>
<li>Ability to change logs verbosity from options. Be sure to enable debug logs on component setting following line in configuration.yaml<br/>
```custom_components.azure_openai_sdk_conversation: debug```<br/>
Note: also those lines are usefull for troubleshooting:
```    homeassistant.components.assist_pipeline: debug
    homeassistant.components.conversation: debug```
</li>
<li>Ability to pass custom informations with HA template.<br/>
<li>Ability to substitute prompt of similar prompts (with vocabulary).<br/>
<li>Ability to stop prompt execution (ready wait).<br/>
<li>Ability to store prompt history.<br/>
<br/>
Sample system message:<br/>
  
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
</li>
<li>Ability to configure and modify endpoint, model, max tokens on options.<br/>
<img width="431" height="452" alt="image" src="https://github.com/user-attachments/assets/656a3d06-9e0d-4a8a-b78e-c56016fe00c0" />

</li>
</ul>

<br/><br/>
Tested models:<ul>
<li>gpt-5</li>
<li>grok-3</li>

<li>o1</li>

<li>gpt-4o-mini</li>
</ul>

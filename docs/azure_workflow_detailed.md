# Detailed Workflow: Azure OpenAI Request → Local Home Assistant Action

## Complete Request/Response Cycle Explained

---

## SCENARIO: User Says "Turn on the living room light"

### PHASE 1: USER INPUT

```
┌─────────────────────────────────────┐
│   USER INPUT (Voice or Text)        │
│   "Turn on the living room light"   │
└────────────┬────────────────────────┘
             │
             ▼
    ┌──────────────────────┐
    │  Speech-to-Text (STT)│  [Optional, if voice input]
    │  (if from voice)     │
    └──────────┬───────────┘
             │
             ▼
    ┌────────────────────────────────┐
    │  ConversationInput Object      │
    │  - text: "Turn on the..."      │
    │  - language: "en"              │
    │  - conversation_id: "abc123"   │
    │  - agent_id: "your_component"  │
    └──────────┬────────────────────┘
             │
     ✅ Ready for processing
```

---

## PHASE 2: PREPARE CONTEXT FOR AZURE

### Step 2.1: Get Exposed Entities from Home Assistant

**Your Home Assistant has these devices:**
```yaml
light.living_room:
  state: off
  friendly_name: "Living Room Light"
  brightness: 0

light.bedroom:
  state: on
  friendly_name: "Bedroom Light"
  brightness: 200

switch.kitchen:
  state: on
  friendly_name: "Kitchen Switch"

climate.thermostat:
  state: idle
  current_temperature: 72
  target_temperature: 72
```

**Your code filters to only exposed entities:**
```python
# From Voice Assistant settings > Exposed Entities
exposed = [
    "light.living_room",
    "light.bedroom",
    "switch.kitchen",
]

# Gets state for each
entity_context = {
    "light.living_room": {"state": "off", "friendly_name": "Living Room Light"},
    "light.bedroom": {"state": "on", "friendly_name": "Bedroom Light"},
    "switch.kitchen": {"state": "on", "friendly_name": "Kitchen Switch"},
}
```

### Step 2.2: Build System Prompt

```
SYSTEM PROMPT:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are a smart home AI assistant for Home Assistant.
Your job is to help users control their home devices using natural language.

AVAILABLE DEVICES (only these can be controlled):
┌─────────────────────────────────────────────────────────────┐
│ Lights:                                                     │
│  - light.living_room (currently: OFF)                       │
│  - light.bedroom (currently: ON)                            │
│                                                             │
│ Switches:                                                   │
│  - switch.kitchen (currently: ON)                           │
└─────────────────────────────────────────────────────────────┘

RULES:
1. Always identify which device the user wants to control
2. Only use the devices listed above
3. Be concise and friendly
4. Confirm actions before executing them
5. If unsure about which device, ask for clarification

AVAILABLE ACTIONS:
- Turn devices ON/OFF
- Set brightness for lights
- Set colors for lights
```

---

## PHASE 3: BUILD REQUEST TO AZURE

### Step 3.1: Construct Messages Array

```python
messages = [
    {
        "role": "system",
        "content": "[SYSTEM PROMPT from above]"
    },
    {
        "role": "user",
        "content": "Turn on the living room light"
    }
]
```

### Step 3.2: Define Available Tools (Function Calling)

```json
tools = [
  {
    "type": "function",
    "function": {
      "name": "call_service",
      "description": "Call a Home Assistant service to control devices",
      "parameters": {
        "type": "object",
        "properties": {
          "domain": {
            "type": "string",
            "enum": ["light", "switch", "climate", "lock", "cover"],
            "description": "The service domain (e.g., 'light', 'switch')"
          },
          "service": {
            "type": "string",
            "description": "The service to call (e.g., 'turn_on', 'turn_off')"
          },
          "entity_id": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of entity IDs to target"
          },
          "data": {
            "type": "object",
            "description": "Additional parameters (brightness, color, temp, etc)"
          }
        },
        "required": ["domain", "service"]
      }
    }
  }
]
```

### Step 3.3: Send Request to Azure OpenAI

```python
# Azure OpenAI API Call
response = client.chat.completions.create(
    model="gpt-4o-mini",  # Your deployed model name in Azure
    messages=messages,
    tools=tools,           # ← This enables function calling!
    tool_choice="auto",    # ← Model decides if/when to use tools
    temperature=0.7,
    max_tokens=500
)
```

**What you send to Azure (over HTTPS):**
```json
{
  "model": "gpt-4o-mini",
  "messages": [
    {
      "role": "system",
      "content": "You are a smart home AI...\nAVAILABLE DEVICES:\n- light.living_room (OFF)\n- light.bedroom (ON)\n- switch.kitchen (ON)"
    },
    {
      "role": "user",
      "content": "Turn on the living room light"
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "call_service",
        "description": "Call a Home Assistant service",
        "parameters": {...}
      }
    }
  ],
  "tool_choice": "auto",
  "temperature": 0.7,
  "max_tokens": 500
}
```

---

## PHASE 4: AZURE OPENAI PROCESSES REQUEST

### Inside Azure's Brain:

```
┌──────────────────────────────────────────────────────────┐
│  AZURE OPENAI (Cloud)                                   │
│                                                          │
│  1. Reads: "Turn on the living room light"              │
│                                                          │
│  2. Analyzes:                                           │
│     - User wants to control a device ✓                  │
│     - Device: "living room light" = light.living_room   │
│     - Action: "turn on" = service "turn_on"             │
│     - Domain: "light"                                   │
│                                                          │
│  3. Decides: "I should call the turn_on function"      │
│                                                          │
│  4. Generates function call with parameters             │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Azure's Response:

```json
{
  "id": "chatcmpl-8qK9Z8PQZ...",
  "object": "chat.completion",
  "created": 1699001234,
  "model": "gpt-4o-mini",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "I'll turn on the living room light for you.",
        "tool_calls": [
          {
            "id": "call_abc123",
            "type": "function",
            "function": {
              "name": "call_service",
              "arguments": "{\"domain\": \"light\", \"service\": \"turn_on\", \"entity_id\": [\"light.living_room\"]}"
            }
          }
        ]
      },
      "finish_reason": "tool_calls"
    }
  ],
  "usage": {
    "prompt_tokens": 250,
    "completion_tokens": 45,
    "total_tokens": 295
  }
}
```

**Key observation:** 
- `finish_reason: "tool_calls"` means the model wants to execute a function
- `tool_calls` array contains the function it wants to call

---

## PHASE 5: YOUR COMPONENT EXECUTES THE TOOL CALL

### Step 5.1: Parse the Tool Call

```python
# Extract from Azure response
tool_call = response.choices[0].message.tool_calls[0]

function_name = tool_call.function.name
# Result: "call_service"

arguments_json = tool_call.function.arguments
# Result: '{"domain": "light", "service": "turn_on", "entity_id": ["light.living_room"]}'

# Parse JSON string to dict
arguments = json.loads(arguments_json)
# Result: {
#   "domain": "light",
#   "service": "turn_on",
#   "entity_id": ["light.living_room"]
# }
```

### Step 5.2: Execute Local Action (Home Assistant Service Call)

```python
# Your code in Home Assistant
await self.hass.services.async_call(
    domain="light",           # ← From arguments["domain"]
    service="turn_on",        # ← From arguments["service"]
    service_data={
        "entity_id": ["light.living_room"]  # ← From arguments["entity_id"]
    },
    blocking=True  # ← Wait for completion
)
```

**What happens inside Home Assistant:**
```
┌───────────────────────────────────────────────────┐
│  HOME ASSISTANT (Local)                           │
│                                                   │
│  1. Receives: light.turn_on(entity_id=...)       │
│                                                   │
│  2. Finds: light.living_room integration         │
│                                                   │
│  3. Calls underlying driver/protocol:            │
│     - For WiFi light: Send HTTP/MQTT message    │
│     - For Zigbee: Send Zigbee command           │
│     - For Z-Wave: Send Z-Wave command           │
│     - etc.                                       │
│                                                   │
│  4. Device state updates:                        │
│     light.living_room.state = "on"              │
│     light.living_room.brightness = 255          │
│                                                   │
│  ✅ LIGHT TURNS ON                              │
└───────────────────────────────────────────────────┘
```

### Step 5.3: Collect Result

```python
# After service call completes
result = {
    "status": "success",
    "message": "Light turned on",
    "entity": "light.living_room",
    "new_state": "on"
}
```

---

## PHASE 6: SEND RESULT BACK TO AZURE

### Step 6.1: Add Tool Result to Messages

```python
# Append assistant response to conversation
messages.append({
    "role": "assistant",
    "content": "I'll turn on the living room light for you.",
    "tool_calls": [
        {
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "call_service",
                "arguments": '{"domain": "light", "service": "turn_on", "entity_id": ["light.living_room"]}'
            }
        }
    ]
})

# Append tool result
messages.append({
    "role": "user",  # Important: "user" role, not "tool"
    "content": json.dumps({
        "tool_call_id": "call_abc123",
        "status": "success",
        "result": "Light turned on"
    })
})
```

**Updated messages array:**
```python
messages = [
    {
        "role": "system",
        "content": "[System prompt with devices...]"
    },
    {
        "role": "user",
        "content": "Turn on the living room light"
    },
    {
        "role": "assistant",
        "content": "I'll turn on the living room light for you.",
        "tool_calls": [...]
    },
    {
        "role": "user",
        "content": '{"tool_call_id": "call_abc123", "status": "success", "result": "Light turned on"}'
    }
]
```

### Step 6.2: Send Updated Messages Back to Azure

```python
# Second call to Azure OpenAI with tool results
final_response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages,  # ← Now includes tool execution result
    tools=tools,
    tool_choice="auto",
    temperature=0.7,
    max_tokens=500
)
```

**What you send to Azure (2nd request):**
```json
{
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "Turn on the living room light"},
    {"role": "assistant", "content": "I'll turn on...", "tool_calls": [...]},
    {"role": "user", "content": "{\"status\": \"success\", \"result\": \"Light turned on\"}"}
  ],
  "tools": [...],
  "tool_choice": "auto"
}
```

---

## PHASE 7: AZURE GENERATES FINAL RESPONSE

### Azure's Processing:

```
Azure reads:
1. Original request: "Turn on the living room light"
2. Its decision: "I should call turn_on service"
3. Local execution result: "Light turned on"
4. Now decides: "I have all info needed to respond to user"
```

### Azure's Final Response:

```json
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "Done! I've turned on the living room light for you.",
        "tool_calls": null
      },
      "finish_reason": "stop"
    }
  ]
}
```

**Key observation:**
- `finish_reason: "stop"` means no more tool calls needed
- `tool_calls: null` means model is done
- `content:` has the final response to show user

---

## PHASE 8: RETURN RESULT TO USER

### Step 8.1: Extract Final Response

```python
response_text = final_response.choices[0].message.content
# Result: "Done! I've turned on the living room light for you."
```

### Step 8.2: Convert to ConversationResult

```python
from homeassistant.helpers import intent

response_obj = intent.IntentResponse(language="en")
response_obj.async_set_speech(response_text)

return ConversationResult(
    conversation_id=user_input.conversation_id,
    response=response_obj,
)
```

### Step 8.3: Display to User

```
┌──────────────────────────────────────────────────────────┐
│  USER RECEIVES RESPONSE                                  │
│                                                          │
│  Text: "Done! I've turned on the living room light."     │
│  (If enabled: Text-to-Speech reads this aloud)           │
│                                                          │
│  ✅ AND: Light.living_room is physically ON              │
└──────────────────────────────────────────────────────────┘
```

---

## COMPLETE WORKFLOW TIMELINE

```
Time    Action                              Location
────────────────────────────────────────────────────────────────
T0      User says: "Turn on the light"     Home (Voice)
        │
T1      Speech-to-Text conversion          HA Server
        │
T2      ConversationInput created          HA Server
        │
T3      Get exposed entities from HA       HA Server (Local)
        Build system prompt
        │
T4      Create messages array              HA Server
        │
T5      ──────► HTTPS Request #1 ────────► Azure Cloud
        (user message + tools)
        │
T6      Azure OpenAI processes             Azure Cloud
        Generates tool call decision
        │
T7      ◄────── Response #1 ──────────────  Azure Cloud
        (tool_calls: [{call_service}])
        │
T8      Parse tool call                    HA Server
        │
T9      ──────► Execute Home Assistant    HA Server (Local)
        Service: light.turn_on
        │
T10     Device receives command            Physical Device
        │
T11     ✅ Light turns ON physically       Physical
        │
T12     Collect execution result           HA Server (Local)
        │
T13     Add result to messages             HA Server
        │
T14     ──────► HTTPS Request #2 ────────► Azure Cloud
        (tool result + original message)
        │
T15     Azure OpenAI processes             Azure Cloud
        Generates final natural language
        │
T16     ◄────── Response #2 ──────────────  Azure Cloud
        (final response, no more tools)
        │
T17     Extract response text              HA Server
        │
T18     Convert to ConversationResult      HA Server
        │
T19     Return to user                     User Interface
        │
T20     ✅ User hears: "Light is on now"   User

Total time: ~500-800ms (most spent waiting for Azure)
```

---

## KEY DIFFERENCES: Local vs Cloud

| Operation | Location | Speed | Details |
|-----------|----------|-------|---------|
| **Parse request** | Local (HA) | ~1ms | Instant |
| **Get entity context** | Local (HA) | ~5ms | Read from memory |
| **Build prompt** | Local (HA) | ~10ms | String building |
| **Azure API call** | Cloud | ~300-400ms | Network + model |
| **Execute service** | Local (HA) | ~50-200ms | Depends on device |
| **Parse response** | Local (HA) | ~2ms | JSON parsing |
| **Return to user** | User device | ~50ms | UI display |

**Total: ~400-700ms** (dominated by Azure network latency)

---

## MULTIPLE TOOL CALLS

### What if user says: "Turn on the light and close the blinds"

```json
{
  "tool_calls": [
    {
      "id": "call_1",
      "function": {
        "name": "call_service",
        "arguments": "{\"domain\": \"light\", \"service\": \"turn_on\", \"entity_id\": [\"light.living_room\"]}"
      }
    },
    {
      "id": "call_2",
      "function": {
        "name": "call_service",
        "arguments": "{\"domain\": \"cover\", \"service\": \"close_cover\", \"entity_id\": [\"cover.blinds\"]}"
      }
    }
  ]
}
```

**Your code executes both:**
```python
# Execute in parallel
await asyncio.gather(
    self.hass.services.async_call("light", "turn_on", {"entity_id": ["light.living_room"]}),
    self.hass.services.async_call("cover", "close_cover", {"entity_id": ["cover.blinds"]})
)

# Collect both results
results = {
    "call_1": {"status": "success", "light": "on"},
    "call_2": {"status": "success", "blinds": "closed"}
}
```

---

## ERROR HANDLING

### What if device doesn't exist?

```python
try:
    await self.hass.services.async_call("light", "turn_on", {...})
except ServiceNotFound:
    result = {
        "status": "error",
        "error": "Light not found",
        "suggestion": "Check entity name"
    }
```

**Send error back to Azure:**
```python
messages.append({
    "role": "user",
    "content": '{"status": "error", "error": "Entity not found"}'
})
```

**Azure will understand and respond:**
```
Final response: "I couldn't find the light. Do you mean one of these..."
```

---

## SUMMARY

The workflow is:
1. **User Input** → Text/Voice
2. **Local Prep** → Build context with HA entities
3. **Request #1 → Azure** → "Turn on light" (with available tools)
4. **Azure Responds** → "I'll call this function" (tool_calls)
5. **Local Execute** → HA actually turns on the light
6. **Request #2 → Azure** → "Here's what happened" (tool result)
7. **Azure Responds** → "Done! Light is on"
8. **Return to User** → Text/Speech response

**Azure makes the DECISIONS, Home Assistant does the ACTIONS** ✅


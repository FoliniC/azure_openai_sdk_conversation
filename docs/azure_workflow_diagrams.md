# Visual Workflow Diagrams: Azure OpenAI → Home Assistant Actions

## DIAGRAM 1: High-Level Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                              USER                                       │
│                    "Turn on the living room light"                      │
│                        (Voice or Text Input)                            │
└─────────────────────────────┬──────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │   YOUR CUSTOM COMPONENT                 │
        │   (Home Assistant Local)                │
        │                                         │
        │   1. Receive user input                 │
        │   2. Get exposed entities from HA       │
        │   3. Build system prompt with context   │
        │   4. Define available tools (functions) │
        │   5. Package message + tools            │
        └────────────────┬────────────────────────┘
                         │
                    ║ HTTPS ║
                    ║ API   ║
                    ║ Call  ║
                         │
                         ▼
        ┌──────────────────────────────────────┐
        │      AZURE OPENAI (Cloud)            │
        │                                      │
        │  1. Analyze user intent              │
        │  2. Read available tools             │
        │  3. Decide which tool to call        │
        │  4. Generate function call JSON      │
        │  5. Return with tool_calls array     │
        └────────────────┬─────────────────────┘
                         │
                    ║ HTTPS ║
                    ║ API   ║
                    ║ Resp  ║
                         │
                         ▼
        ┌─────────────────────────────────────────────────┐
        │   YOUR CUSTOM COMPONENT (receives response)    │
        │                                                 │
        │   1. Parse tool_calls from response            │
        │   2. Extract function name & arguments         │
        │   3. ✅ EXECUTE LOCAL ACTION                   │
        │   4. Call Home Assistant service               │
        │   5. Collect result                            │
        │   6. Prepare tool result                       │
        └────────────────┬────────────────────────────────┘
                         │
        ┌────────────────▼──────────────────────┐
        │   HOME ASSISTANT (Local)              │
        │                                       │
        │   Receives: light.turn_on             │
        │   Executes: service.async_call()      │
        │   Result: ✅ LIGHT TURNS ON          │
        │                                       │
        │   Device state updates:               │
        │   light.living_room.state = "on"      │
        └────────────────┬──────────────────────┘
                         │
                    ║ Device Protocol ║
                    ║ (WiFi/MQTT/    ║
                    ║  Zigbee/Z-Wave) ║
                         │
                         ▼
        ┌──────────────────────────────────────┐
        │   PHYSICAL DEVICE                    │
        │   💡 LIGHT TURNS ON                 │
        └──────────────────────────────────────┘
```

---

## DIAGRAM 2: Message Flow with API Details

```
Step 1: USER INPUT
═════════════════════════════════════════════════════════════════
"Turn on the living room light"
                    │
                    ▼
Step 2: LOCAL PREPARATION (Your Custom Component)
═════════════════════════════════════════════════════════════════
[Get Exposed Entities from Home Assistant]
light.living_room (OFF)
light.bedroom (ON)
switch.kitchen (ON)
                    │
                    ▼
[Build Messages Array]
messages = [
    {"role": "system", "content": "You are a smart home AI...\n
      AVAILABLE DEVICES:\n
      - light.living_room (OFF)\n
      - light.bedroom (ON)\n
      - switch.kitchen (ON)"},
    {"role": "user", "content": "Turn on the living room light"}
]
                    │
                    ▼
[Define Tools]
tools = [{
    "type": "function",
    "function": {
        "name": "call_service",
        "description": "Call Home Assistant service",
        "parameters": {...}
    }
}]
                    │
                    ▼
Step 3: REQUEST TO AZURE
═════════════════════════════════════════════════════════════════
        POST https://your-resource.openai.azure.com/openai/deployments/gpt-4/chat/completions
        
        Body: {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "..."},
                {"role": "user", "content": "Turn on the living room light"}
            ],
            "tools": [{...}],
            "tool_choice": "auto",
            "temperature": 0.7,
            "max_tokens": 500
        }
                    │
                    ▼
Step 4: AZURE PROCESSING
═════════════════════════════════════════════════════════════════
Azure reads:
- "Turn on the living room light"
- Available tools: [call_service]
- Available devices: [light.living_room, light.bedroom, switch.kitchen]

Azure decides:
"The user wants to turn on light.living_room"
"I should call the call_service function"
                    │
                    ▼
Step 5: AZURE RESPONSE
═════════════════════════════════════════════════════════════════
        Response: {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "I'll turn on the living room light for you.",
                    "tool_calls": [{
                        "id": "call_abc123",
                        "function": {
                            "name": "call_service",
                            "arguments": "{\"domain\": \"light\", \"service\": \"turn_on\", \"entity_id\": [\"light.living_room\"]}"
                        }
                    }]
                },
                "finish_reason": "tool_calls"
            }]
        }
                    │
                    ▼
Step 6: PARSE & EXECUTE (Your Custom Component)
═════════════════════════════════════════════════════════════════
Parse from response:
- tool_call.function.name = "call_service"
- arguments = {
    "domain": "light",
    "service": "turn_on",
    "entity_id": ["light.living_room"]
  }

Execute:
await hass.services.async_call(
    domain="light",
    service="turn_on",
    service_data={"entity_id": ["light.living_room"]},
    blocking=True
)
                    │
                    ▼
Step 7: HOME ASSISTANT EXECUTES SERVICE
═════════════════════════════════════════════════════════════════
hass.services.async_call()
    │
    ├─→ Find light.living_room integration
    ├─→ Send command to device driver
    ├─→ Device receives ON command
    └─→ Device state updates: state = "on"

Collect result:
result = {
    "status": "success",
    "message": "Light turned on",
    "entity": "light.living_room"
}
                    │
                    ▼
Step 8: SEND RESULT BACK TO AZURE
═════════════════════════════════════════════════════════════════
messages.append({
    "role": "assistant",
    "content": "I'll turn on the living room light for you.",
    "tool_calls": [{"id": "call_abc123", ...}]
})

messages.append({
    "role": "user",
    "content": "{\"status\": \"success\", \"message\": \"Light turned on\"}"
})

POST https://your-resource.openai.azure.com/openai/deployments/gpt-4/chat/completions
Body: {
    "model": "gpt-4o-mini",
    "messages": [...],  # ← Now includes tool result
    "tools": [{...}]
}
                    │
                    ▼
Step 9: AZURE FINAL RESPONSE
═════════════════════════════════════════════════════════════════
Azure understands:
- Tool was executed
- Light was turned on
- Task is complete

Response: {
    "choices": [{
        "message": {
            "role": "assistant",
            "content": "Done! I've turned on the living room light for you.",
            "tool_calls": null
        },
        "finish_reason": "stop"
    }]
}
                    │
                    ▼
Step 10: RETURN TO USER
═════════════════════════════════════════════════════════════════
Final response text:
"Done! I've turned on the living room light for you."

[Text-to-Speech if enabled]
[User hears response]

✅ LIGHT IS ON
✅ USER GETS CONFIRMATION
```

---

## DIAGRAM 3: Decision Tree - What Azure Does

```
┌─────────────────────────────────────────────────────────────┐
│  Azure Receives: "Turn on the living room light"            │
│  + List of available tools                                  │
│  + List of available devices                                │
└─────────────────────────────────┬───────────────────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │ Does the model understand │
                    │ which device? (Using AI)  │
                    └────────┬──────────────┬───┘
                             │              │
                          YES│              │NO
                             │              │
        ┌────────────────────▼┐  ┌──────────▼──────────────┐
        │ Can I use the       │  │ Ask for clarification  │
        │ available tools?    │  │                        │
        └────────┬────────────┘  │ "Which living room?"   │
                 │               │ "Did you mean..."      │
          YES│   │NO             └────────────────────────┘
             │   │
     ┌───────▼───▼────────────┐
     │ Return tool_calls      │ Return just text
     │ with function call     │ response (no tools)
     │                        │
     │ finish_reason: "tool_calls"
     │ tool_calls: [{...}]    │
     └───────────────────────┘
```

---

## DIAGRAM 4: Tool Execution Sequence

```
Request from Azure:
└─→ tool_call = {
      "id": "call_abc123",
      "function": {
        "name": "call_service",
        "arguments": "{...}"
      }
    }

Your Component Processing:
│
├─→ 1. Extract function name
│      call_service ✓
│
├─→ 2. Parse arguments (JSON string → dict)
│      {
│        "domain": "light",
│        "service": "turn_on",
│        "entity_id": ["light.living_room"],
│        "data": {}
│      }
│
├─→ 3. Validate inputs
│      - domain "light" exists ✓
│      - service "turn_on" exists ✓
│      - entity_id "light.living_room" exists ✓
│
├─→ 4. Build service_data
│      {
│        "entity_id": ["light.living_room"],
│        "brightness": 255,
│        "color_name": "white"
│      }
│
├─→ 5. Call Home Assistant
│      await hass.services.async_call(
│        "light",
│        "turn_on",
│        service_data
│      )
│      │
│      ▼
│    Home Assistant routes call
│    │
│    ├─→ Find light.living_room integration
│    ├─→ Call integration's async_turn_on()
│    │
│    ▼
│    Device protocol (WiFi/MQTT/Zigbee/Z-Wave)
│    │
│    ▼
│    Physical light device
│    │
│    ▼
│    ✅ LIGHT TURNS ON
│
├─→ 6. Collect response
│      {
│        "tool_call_id": "call_abc123",
│        "status": "success",
│        "entity": "light.living_room",
│        "new_state": "on",
│        "timestamp": "2025-11-02T11:15:30Z"
│      }
│
└─→ 7. Prepare to send back to Azure
       (as part of next request)
```

---

## DIAGRAM 5: Multiple Tool Calls (Complex Scenario)

```
User: "Close the blinds, turn off the light, and set the temperature to 72"

Azure analyzes and returns:
┌─────────────────────────────────────────────────────────────┐
│ tool_calls: [                                               │
│   {                                                         │
│     "id": "call_1",                                         │
│     "function": {                                           │
│       "name": "call_service",                              │
│       "arguments": "{\"domain\": \"cover\", \"service\": \"close_cover\", \"entity_id\": [\"cover.blinds\"]}"
│     }                                                       │
│   },                                                        │
│   {                                                         │
│     "id": "call_2",                                         │
│     "function": {                                           │
│       "name": "call_service",                              │
│       "arguments": "{\"domain\": \"light\", \"service\": \"turn_off\", \"entity_id\": [\"light.living_room\"]}"
│     }                                                       │
│   },                                                        │
│   {                                                         │
│     "id": "call_3",                                         │
│     "function": {                                           │
│       "name": "call_service",                              │
│       "arguments": "{\"domain\": \"climate\", \"service\": \"set_temperature\", \"entity_id\": [\"climate.thermostat\"], \"data\": {\"temperature\": 72}}"
│     }                                                       │
│   }                                                         │
│ ]                                                           │
└─────────────────────────────────────────────────────────────┘

Your Component's Parallel Execution:
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│ Tool Call #1         │  │ Tool Call #2         │  │ Tool Call #3         │
│                      │  │                      │  │                      │
│ cover.close_cover    │  │ light.turn_off       │  │ climate.turn_heat    │
│ blinds               │  │ living_room_light    │  │ thermostat to 72     │
│                      │  │                      │  │                      │
│ await hass.services  │  │ await hass.services  │  │ await hass.services  │
│   .async_call()      │  │   .async_call()      │  │   .async_call()      │
│                      │  │                      │  │                      │
└─────────┬────────────┘  └──────────┬───────────┘  └──────────┬───────────┘
          │                          │                         │
          │   (All in parallel)      │                         │
          │   asyncio.gather()       │                         │
          │                          │                         │
          └──────────────┬───────────┴────────────┬────────────┘
                         │                        │
                    ✅ All Done                  │
                    │                            │
                    ▼                            ▼
         Collect all results         Send back to Azure:
         ┌──────────────────────┐    ┌──────────────────────┐
         │ call_1: success      │    │ {                    │
         │ call_2: success      │    │   "call_1": "ok",    │
         │ call_3: success      │    │   "call_2": "ok",    │
         └──────────────────────┘    │   "call_3": "ok"     │
                                     │ }                    │
                                     └──────────────────────┘
                                            │
                                            ▼
                                     Azure generates
                                     natural response:
                                     "Done! I've closed the blinds,
                                      turned off the light, and set
                                      the temperature to 72 degrees."
```

---

## DIAGRAM 6: Error Handling Flow

```
Tool Execution Error Path:
────────────────────────────────────────────────────────────

Try to execute:
└─→ hass.services.async_call("light", "turn_on", {...})

                         │
            ┌────────────▼────────────┐
            │ Did it work?            │
            └────────────┬────────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
        YES│             │NO            │
          │              │              │
    ┌─────▼──────┐  ┌────▼─────────────────┐
    │ Success    │  │ Exception raised     │
    │ Return:    │  └────┬────────────────┘
    │ {          │       │
    │  "status": │   ┌───▼──────────────────────────┐
    │  "success" │   │ Type of Error?               │
    │ }          │   └───┬──────────────────────┬──┘
    └────────────┘       │                      │
                  ┌──────▼──────┐      ┌────────▼─────────┐
                  │ Entity not  │      │ Service not      │
                  │ found?      │      │ callable/       │
                  │             │      │ permission?      │
                  │ Return:     │      │                  │
                  │ {"error":   │      │ Return:          │
                  │  "entity    │      │ {"error":        │
                  │  not found"}│      │  "permission"}   │
                  └─────────────┘      └──────────────────┘

Send error back to Azure:
└─→ messages.append({
    "role": "user",
    "content": "{\"status\": \"error\", \"error\": \"Entity not found\"}"
})

Azure's Response (understands failure):
└─→ "I couldn't find that entity. Available entities are..."
    OR
    "Sorry, I don't have permission to control that device."
```

---

## DIAGRAM 7: Complete Timeline (ms)

```
T+0ms    ┌─────────────────────────────┐
         │ User says: "Turn on light"  │
         └─────────────┬───────────────┘
                       │
T+5ms    ├─── Get entities (HA read)
                       │
T+10ms   ├─── Build system prompt
                       │
T+15ms   ├─── Create messages array
                       │
T+20ms   ├─── Define tools
                       │
T+25ms   ├─── Package request
                       │
T+30ms   ├──────────────────────┐
         │  🌐 HTTPS REQUEST #1 │
         │  (Upload to Azure)   │
         └──────────────────────┘
         │
T+150ms  ├─── Network transfer to Azure
         │
T+250ms  ├─── Azure processes request
         │
T+350ms  ├─── Azure generates response
         │
T+370ms  ├──────────────────────┐
         │  🌐 HTTPS RESPONSE #1 │
         │  (Download from Azure)│
         └──────────────────────┘
         │
T+400ms  ├─── Parse response
         │
T+405ms  ├─── Extract tool call
         │
T+410ms  ├─── Execute HA service
         │
T+450ms  ├─── Device receives command
         │     (WiFi/MQTT/Zigbee latency)
         │
T+550ms  ├─── Device updates state
         │
T+555ms  ├─── HA confirms execution
         │
T+560ms  ├─── Build 2nd request
         │
T+565ms  ├──────────────────────┐
         │  🌐 HTTPS REQUEST #2  │
         │  (Tool result)        │
         └──────────────────────┘
         │
T+685ms  ├─── Azure processes
         │
T+750ms  ├──────────────────────┐
         │  🌐 HTTPS RESPONSE #2 │
         │  (Final answer)       │
         └──────────────────────┘
         │
T+775ms  ├─── Parse final response
         │
T+780ms  ├─── Convert to ConversationResult
         │
T+790ms  ├─── Return to user
         │
T+800ms  └─── 🔊 User hears: "Light is on"
             ✅ LIGHT IS ON

Total: ~800ms
(Most time: Azure network latency + device protocol)
```


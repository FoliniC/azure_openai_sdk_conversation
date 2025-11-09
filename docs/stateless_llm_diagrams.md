# Visual Diagrams: Stateless LLM Context Handling

## DIAGRAM 1: Request #1 vs Request #2 - The Key Difference

```
REQUEST #1: "Turn on the light"
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│ YOUR LOCAL COMPONENT                                            │
│ (Stateful - remembers everything)                              │
└─────────────────────────────────────────────────────────────────┘
  │
  ├─→ Builds messages:
  │   [
  │     {"role": "system", "content": "You are..."},
  │     {"role": "user", "content": "Turn on the light"}
  │   ]
  │
  ├─→ Defines tools:
  │   [{
  │     "type": "function",
  │     "function": {"name": "call_service", ...}
  │   }]
  │
  ├─→ Sends HTTPS request to Azure
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│ AZURE CLOUD - GPT INSTANCE #1 (Stateless)                      │
│ This specific instance has NO memory!                          │
│ It only knows what's in the request                            │
└─────────────────────────────────────────────────────────────────┘
  │
  ├─→ Reads from request:
  │   ✓ System prompt
  │   ✓ User message: "Turn on the light"
  │   ✓ Available tools
  │
  ├─→ Analyzes (in GPT's internal weights):
  │   "User wants to turn on light"
  │   "I have a tool that can do this"
  │   "I should call the tool"
  │
  ├─→ Generates output:
  │   {
  │     "content": "I'll turn on the light",
  │     "tool_calls": [{
  │       "id": "call_abc123",
  │       "function": {
  │         "name": "call_service",
  │         "arguments": "{\"domain\": \"light\", ...}"
  │       }
  │     }]
  │   }
  │
  ├─→ Sends response back
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│ YOUR LOCAL COMPONENT                                            │
│ (Receives: "I'll turn on the light" + tool_calls)             │
└─────────────────────────────────────────────────────────────────┘
  │
  ├─→ Extracts tool call
  │   domain: "light"
  │   service: "turn_on"
  │   entity_id: ["light.living_room"]
  │
  ├─→ EXECUTES LOCALLY:
  │   await hass.services.async_call("light", "turn_on", ...)
  │
  ▼ (Light physically turns ON) ✅
  
  ├─→ Collects result:
  │   {
  │     "status": "success",
  │     "entity": "light.living_room",
  │     "new_state": "on"
  │   }


TIME PASSES (Light is now ON)
═══════════════════════════════════════════════════════════════════


REQUEST #2: "Here's what happened"
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│ YOUR LOCAL COMPONENT                                            │
│ (Stateful - still remembers everything)                        │
└─────────────────────────────────────────────────────────────────┘
  │
  ├─→ Builds messages with FULL CONTEXT:
  │   [
  │     {"role": "system", "content": "You are..."},
  │
  │     {"role": "user", "content": "Turn on the light"},
  │     ↑ Same as before
  │
  │     {
  │       "role": "assistant",
  │       "content": "I'll turn on the light",
  │       "tool_calls": [{...}]  ← GPT's response from Request #1
  │     },
  │     ↑ NEW - This is GPT's tool call decision
  │
  │     {
  │       "role": "user",
  │       "content": "{\"status\": \"success\", \"result\": \"Light on\"}"
  │     }
  │     ↑ NEW - This is the tool execution result
  │   ]
  │
  ├─→ Sends HTTPS request to Azure
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│ AZURE CLOUD - GPT INSTANCE #2 (Different Instance!)            │
│ Completely NEW instance - no connection to Instance #1         │
│ But receives FULL conversation history                         │
└─────────────────────────────────────────────────────────────────┘
  │
  ├─→ Reads from request:
  │   ✓ System prompt (again)
  │   ✓ User message (again): "Turn on the light"
  │   ✓ Assistant's previous decision (NEW): "I'll turn it on"
  │   ✓ Tool calls that were made (NEW): call_service(...)
  │   ✓ Tool execution result (NEW): "success"
  │   ✓ Available tools (again)
  │
  ├─→ Analyzes (in GPT Instance #2's internal weights):
  │   "User asked to turn on the light"
  │   "I (in my previous response) said I'd do it"
  │   "I called the call_service tool"
  │   "The tool succeeded"
  │   "Now I should confirm to the user and provide final response"
  │
  ├─→ Generates output:
  │   {
  │     "content": "Done! I've turned on the light for you.",
  │     "tool_calls": null  ← No more tool calls needed
  │   }
  │
  ├─→ Sends response back
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│ YOUR LOCAL COMPONENT                                            │
│ (Receives: "Done! Light is on" + NO tool_calls)               │
│                                                                 │
│ Knows: No more tool calls, task is complete                    │
└─────────────────────────────────────────────────────────────────┘
  │
  ▼ Return to user

KEY INSIGHT:
GPT Instance #1 has NO idea that Instance #2 will exist
GPT Instance #2 has NO connection to Instance #1
But Instance #2 understands full context because YOU sent it!
```

---

## DIAGRAM 2: Messages Array is THE STATE

```
CONVERSATION STATE FLOW:
═══════════════════════════════════════════════════════════════════

REQUEST #1
┌───────────────────────────────────────────────────────┐
│ messages = [                                          │
│   system_msg,                                         │
│   user_msg: "Turn on light"                           │
│ ]                                                     │
└────────────────────┬────────────────────────────────┘
                     │
                GPT Instance #1
                     │
                Response: tool_calls
                     │
    ┌────────────────▼──────────────────┐
    │ Your code executes the tool       │
    │ Light turns ON ✅                 │
    └────────────────┬──────────────────┘
                     │
REQUEST #2           │
┌────────────────────▼──────────────────────────────────┐
│ messages = [                                          │
│   system_msg,          ← Same as before               │
│   user_msg: "Turn on", ← Same as before               │
│   {                    ← NEW!                         │
│     role: "assistant", ← GPT's prev response          │
│     tool_calls: [...]  ← Tool decision                │
│   },                                                  │
│   {                    ← NEW!                         │
│     role: "user",      ← Tool result                  │
│     content: "{...}"   ← success!                     │
│   }                                                   │
│ ]                                                     │
└────────────────────┬──────────────────────────────────┘
                     │
             GPT Instance #2 (DIFFERENT)
                     │
    Response: "Done! Light is on" + NO tool_calls
                     │
    ┌───────────────▼────────────────┐
    │ Return to user                 │
    │ Conversation complete ✅        │
    └────────────────────────────────┘


THE MESSAGES ARRAY IS THE STATE MACHINE!
It captures:
1. What the user wanted
2. What GPT decided
3. What actually happened
4. What GPT should do next
```

---

## DIAGRAM 3: How GPT Understands "Tool Was Executed"

```
INSIDE GPT'S REASONING (REQUEST #2):
═══════════════════════════════════════════════════════════════════

INPUT (from your messages array):
┌─────────────────────────────────────────────────────────────┐
│ System: "You're a smart home assistant"                     │
│                                                              │
│ User: "Turn on the living room light"                       │
│                                                              │
│ Assistant (from prev response): [                           │
│   "I'll turn on the living room light.",                    │
│   tool_calls: [{                                            │
│     function: call_service,                                │
│     arguments: {domain: "light", service: "turn_on"}       │
│   }]                                                        │
│ ]                                                           │
│                                                              │
│ User (tool result): {                                       │
│   "tool_call_id": "call_abc123",                           │
│   "status": "success",                                      │
│   "result": "Light turned on successfully"                 │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
                         │
                    ▼ GPT READS ▼
                         │
GPT's thought process:

"Let me understand what's happening here:

1. System says I'm a smart home assistant ✓
2. User asked to turn on the light ✓
3. I responded that I would do it ✓
4. I called the 'call_service' tool ✓
5. The user is now telling me:
   - The tool_call_id matches my tool call
   - Status: success (not error!)
   - Result: Light was successfully turned on

So:
- The action was executed ✓
- The action succeeded ✓
- The light is now actually ON ✓
- My job is complete ✓

I should:
- Confirm to the user
- Not call any more tools (tool_calls: null)
- Provide a natural response"
                         │
                    ▼ GPT OUTPUTS ▼
                         │
{
  "content": "Done! I've successfully turned on the light for you.",
  "tool_calls": null
}
```

---

## DIAGRAM 4: Why Each Request Must Include Full History

```
SCENARIO: What if you DON'T send full history?
═══════════════════════════════════════════════════════════════════

REQUEST #2 (WRONG WAY):
┌─────────────────────────────────────────────────────────────┐
│ messages = [                                                │
│   system_msg,                                               │
│   {                                                         │
│     role: "user",                                           │
│     content: "{\"status\": \"success\", \"result\": \"...\"}"│
│   }                                                         │
│ ]                                                           │
│                                                              │
│ ❌ MISSING:                                                │
│ - The original user request                                │
│ - GPT's tool decision                                      │
│                                                              │
│ GPT reads this and thinks:                                 │
│ "Status success? Success of what?"                        │
│ "Tool result? What tool?"                                 │
│ "I have no context!"                                      │
└─────────────────────────────────────────────────────────────┘
           │
           ▼ GPT is confused ❌


REQUEST #2 (RIGHT WAY):
┌─────────────────────────────────────────────────────────────┐
│ messages = [                                                │
│   system_msg,                                               │
│   {"role": "user", "content": "Turn on light"},            │
│   {                                                         │
│     "role": "assistant",                                    │
│     "content": "I'll do it",                               │
│     "tool_calls": [...]                                    │
│   },                                                        │
│   {"role": "user", "content": "{\"status\": \"success\"}"} │
│ ]                                                           │
│                                                              │
│ ✅ INCLUDES:                                               │
│ - The original request                                     │
│ - My tool decision                                         │
│ - The result of that tool call                             │
│                                                              │
│ GPT reads this and understands:                           │
│ "User asked to turn on light"                            │
│ "I decided to use the tool"                              │
│ "The tool succeeded"                                      │
│ "Now I should confirm"                                    │
└─────────────────────────────────────────────────────────────┘
           │
           ▼ GPT understands clearly ✓

PRINCIPLE: Each API call must be self-contained!
```

---

## DIAGRAM 5: Multi-Turn Conversation

```
TURN 1: "Turn on the light"
═══════════════════════════════════════════════════════════════════
Request:
  [system_msg, user: "Turn on the light"]
Response:
  tool_calls: [turn_on light]
Action:
  ✓ Light turns on


TURN 2: "Got it, turn on"
═══════════════════════════════════════════════════════════════════
Request:
  [
    system_msg,
    user: "Turn on the light",
    assistant: tool_calls + response,
    user: "success result"
  ]
Response:
  "Done! Light is on"


TURN 3: "Now set brightness to 50%"
═══════════════════════════════════════════════════════════════════
Request:
  [
    system_msg,
    user: "Turn on the light",
    assistant: tool_calls + response,      ← Turn 1 history
    user: "success result",
    assistant: "Done! Light is on",        ← Turn 2 history
    user: "Now set brightness to 50%"      ← NEW user message
  ]
Response:
  tool_calls: [call_service set_brightness]
Action:
  ✓ Brightness changes


TURN 4: (continued)
═══════════════════════════════════════════════════════════════════
Request:
  [
    system_msg,
    user: "Turn on the light",
    assistant: tool_calls,
    user: "success",
    assistant: "Done!",
    user: "set brightness to 50%",
    assistant: tool_calls,               ← Turn 3 response
    user: "brightness set result"        ← Turn 3 execution
  ]
Response:
  "Brightness set to 50%. Anything else?"


The messages array grows with each turn!
Each new request includes ENTIRE conversation history.
GPT always has full context.
```

---

## DIAGRAM 6: Stateless vs Stateful Comparison

```
STATELESS MODEL (GPT):
═════════════════════════════════════════════════════════════════

Request #1 (Fresh Instance A)
  Input: User message + tools
  Output: Tool call
  Memory: None! ← Forgotten immediately

Request #2 (Fresh Instance B) 
  Input: User message + GPT's response + result + tools
  Output: Final response
  Memory: None! ← Forgotten immediately

Advantages:
  ✓ Infinitely scalable (no memory bloat)
  ✓ Every request independent
  ✓ No memory corruption possible
  ✓ Can be load-balanced across servers

How it works:
  YOU maintain the memory (messages array)
  GPT is stateless (only in request/response)
  YOU provide context each time


STATEFUL MODEL (Hypothetical):
═════════════════════════════════════════════════════════════════

Request #1 (Instance A - STATEFUL)
  Input: User message + tools
  Output: Tool call
  Memory: STORED internally
    {
      "conversation_id": "xyz123",
      "history": [...],
      "entities": {...}
    }

Request #2 (Same Instance A)
  Input: Tool result
  Output: Final response
  Memory: Uses internally stored history ✓

Disadvantages:
  ✗ Must keep same instance (connection)
  ✗ Memory grows forever
  ✗ Server crashes = memory loss
  ✗ Can't load-balance
  ✗ Hard to scale


WHAT AZURE/OPENAI CHOSE:
Stateless model (GPT) with client-managed state (messages array)
Best of both worlds!
```

---

## DIAGRAM 7: The Token Flow (Why Full History Matters)

```
REQUEST #2: Full History Needed
═════════════════════════════════════════════════════════════════

Token counting in messages array:

[
  {
    "role": "system",
    "content": "You are..."        ← ~10 tokens
  },
  {
    "role": "user",
    "content": "Turn on light"     ← ~5 tokens
  },
  {
    "role": "assistant",
    "content": "I'll turn it on",  ← ~5 tokens
    "tool_calls": [{...}]         ← ~20 tokens
  },
  {
    "role": "user",
    "content": "{success...}"      ← ~15 tokens
  }
]

Total: ~55 tokens

YOU PAY FOR EVERY TOKEN!
  Input tokens: charged per request
  Output tokens: charged per response
  Tool calls: counted as tokens

This is why Azure charges per token!
Each request to GPT includes full history = more tokens = more cost.

Optimization:
  - Keep messages concise
  - Remove old conversations
  - Summarize long histories
  - Use token counting API first
```

---

## DIAGRAM 8: Error Handling Flow (Stateless)

```
REQUEST #2 - Error Case:
═══════════════════════════════════════════════════════════════════

Tool executed but FAILED:

messages = [
  system_msg,
  user: "Turn on the light",
  assistant: tool_calls,
  user: {                          ← This time, status: "error"
    "tool_call_id": "...",
    "status": "error",             ← ❌ Not success!
    "error": "Light entity not found",
    "available_entities": [...]
  }
]

GPT reads this:
"The tool failed"
"Entity not found"
"But here are other available entities"

GPT responds:
"I couldn't find that light. Available lights are:
 - light.living_room
 - light.bedroom
 - light.hallway
 
 Which one did you mean?"

GPT's reasoning is stateless:
✓ Reads: "I tried to turn on the light, it failed, here's why"
✓ Understands: situation, what went wrong, what to ask
✓ Responds: naturally handles the error

All from messages array context!
No internal memory of previous failure needed.
```


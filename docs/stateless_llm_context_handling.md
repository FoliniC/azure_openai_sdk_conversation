# How Stateless LLMs Handle Tool Results: GPT Models Context Management

## THE CORE CONCEPT: Stateless ≠ No Memory

**Stateless means**: GPT has NO internal memory between API calls  
**BUT**: It can understand context through the messages array

```
REQUEST #1
┌─────────────────────────────────────┐
│ User: "Turn on the light"           │
│ Tools: [call_service]               │
└─────────────────────────────────────┘
         ↓
         ▼
┌─────────────────────────────────────┐
│ GPT (brand new instance)            │
│ No memory from before!              │
│ But receives: user message          │
│ And receives: available tools       │
└─────────────────────────────────────┘
         ↓
         ▼
    "I should call the tool"
    → Returns: tool_calls array


TIME PASSES (seconds)
Your code executes the tool
Light physically turns ON


REQUEST #2 (Separate API Call)
┌─────────────────────────────────────┐
│ New GPT instance (completely fresh!)│
│ Has NO memory of Request #1!        │
│ But you send:                       │
│ 1. Original user message            │
│ 2. Its own tool call decision       │
│ 3. The tool result                  │
└─────────────────────────────────────┘
         ↓
         ▼
    "Oh! The user asked to turn on light"
    "I decided to call the tool"
    "The tool was executed successfully"
    → Generates final response
```

---

## THE MAGIC: The Messages Array (Conversation History)

GPT doesn't have memory, but **YOU provide the memory** through the messages array.

### REQUEST #1

```python
messages = [
    {
        "role": "system",
        "content": "You are a smart home assistant."
    },
    {
        "role": "user",
        "content": "Turn on the living room light"
    }
]

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages,  # ← This IS the memory!
    tools=[...],
    tool_choice="auto"
)
```

**What GPT sees:**
```
"I'm a smart home assistant.
The user just said: 'Turn on the living room light'
I have a tool called 'call_service'.
What should I do?"
```

**GPT returns:**
```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "I'll turn on the living room light.",
      "tool_calls": [{
        "id": "call_abc123",
        "function": {
          "name": "call_service",
          "arguments": "{\"domain\": \"light\", \"service\": \"turn_on\", \"entity_id\": [\"light.living_room\"]}"
        }
      }]
    }
  }]
}
```

---

### REQUEST #2 (The Key Part!)

Now you construct a **NEW messages array** that includes:
1. The system prompt (again)
2. The original user message (again)
3. **GPT's own response** (the tool call decision)
4. **The tool result** (what you executed)

```python
# This is what you send to GPT in Request #2:
messages = [
    {
        "role": "system",
        "content": "You are a smart home assistant."
    },
    {
        "role": "user",
        "content": "Turn on the living room light"
    },
    {
        "role": "assistant",
        "content": "I'll turn on the living room light.",
        "tool_calls": [{
            "id": "call_abc123",
            "function": {
                "name": "call_service",
                "arguments": "{\"domain\": \"light\", \"service\": \"turn_on\", \"entity_id\": [\"light.living_room\"]}"
            }
        }]
    },
    {
        "role": "user",  # Important: "user" role, not "tool"
        "content": json.dumps({
            "tool_call_id": "call_abc123",
            "status": "success",
            "result": "Light successfully turned on"
        })
    }
]

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages,  # ← All context is here!
    tools=[...],
    tool_choice="auto"
)
```

**What GPT sees (in Request #2):**

```
"I'm a smart home assistant.

The user said: 'Turn on the living room light'

I responded: 'I'll turn on the living room light.'
And I called the tool 'call_service' with these parameters.

Then I got the result: 'Light successfully turned on'

What should I say now?"
```

**GPT understands the full context** even though it's a brand new instance!

---

## HOW THIS WORKS: The Messages Array is THE STATE

```
REQUEST #1 (Fresh GPT)
────────────────────────────────
Input:
  User message
  + Tools available
  ↓
GPT thinks: "What should I do?"
Output: "Call this tool"

REQUEST #2 (Different Fresh GPT)
────────────────────────────────
Input:
  User message (again)
  + GPT's previous response (tool call)
  + Tool result
  ↓
GPT thinks: "Ah, the tool was already called"
            "And it succeeded"
            "I should confirm to user"
Output: "Done! Light is on"

REQUEST #3 (Another Fresh GPT)
────────────────────────────────
Input:
  User message (again)
  + GPT's first response
  + Tool result
  + GPT's confirmation response (again)
  + New user follow-up (e.g., "Set it to 50%")
  ↓
GPT thinks: "Light is already on"
            "Now user wants to set brightness"
            "I should call the tool again with new parameters"
Output: "I'll set the brightness to 50%"
```

**Each GPT instance is FRESH, but the messages array provides FULL CONTEXT**

---

## VISUAL: The State Machine

```
┌──────────────────────────────────────────────────────┐
│                  REQUEST #1                          │
│                                                      │
│  GPT Instance #1 (FRESH/STATELESS)                 │
│  ┌──────────────────────────────────────┐           │
│  │ Receives:                            │           │
│  │ - System prompt                      │           │
│  │ - User: "Turn on light"              │           │
│  │ - Tools: [call_service]              │           │
│  │                                      │           │
│  │ Decides: "Use the call_service tool" │           │
│  │ Returns: tool_calls array            │           │
│  └──────────────────────────────────────┘           │
└──────────────────────────────────────────────────────┘
              ↓ (Your code executes)
         Light turns ON
              ↓
┌──────────────────────────────────────────────────────┐
│                  REQUEST #2                          │
│                                                      │
│  GPT Instance #2 (FRESH/STATELESS)                 │
│  ┌──────────────────────────────────────┐           │
│  │ Receives:                            │           │
│  │ - System prompt (AGAIN)              │           │
│  │ - User: "Turn on light" (AGAIN)      │           │
│  │ - Assistant's prev tool call (AGAIN) │ ← KEY!    │
│  │ - Tool result: success (NEW)         │ ← KEY!    │
│  │ - Tools: [call_service] (AGAIN)      │           │
│  │                                      │           │
│  │ Understands: "Tool was executed"     │           │
│  │ Responds: "Done! Light is on"        │           │
│  │ No more tool_calls needed            │           │
│  └──────────────────────────────────────┘           │
└──────────────────────────────────────────────────────┘
```

**Each GPT is stateless, but the full conversation history (messages array) IS the state!**

---

## ACTUAL PYTHON CODE FLOW

```python
# REQUEST #1
messages_r1 = [
    {"role": "system", "content": "You are a smart home AI"},
    {"role": "user", "content": "Turn on the light"}
]

response_r1 = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages_r1,
    tools=[...],
    tool_choice="auto"
)

# Extract tool call
tool_call = response_r1.choices[0].message.tool_calls[0]
print(f"GPT decided to call: {tool_call.function.name}")
# Output: "GPT decided to call: call_service"

# Your code executes the tool
result = await hass.services.async_call(
    domain="light",
    service="turn_on",
    service_data={"entity_id": ["light.living_room"]}
)

print(f"Tool execution result: success")
# Output: "Tool execution result: success"


# REQUEST #2 - CRITICAL PART
# Build messages array with FULL HISTORY
messages_r2 = [
    {"role": "system", "content": "You are a smart home AI"},
    {"role": "user", "content": "Turn on the light"},  # ← Original message again
    
    # ← This is what GPT said before (tool call)
    {
        "role": "assistant",
        "content": response_r1.choices[0].message.content,
        "tool_calls": response_r1.choices[0].message.tool_calls
    },
    
    # ← This is what the tool returned (tool result)
    {
        "role": "user",  # Sent as "user" message
        "content": json.dumps({
            "tool_call_id": tool_call.id,
            "status": "success",
            "result": "Light turned on successfully"
        })
    }
]

response_r2 = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages_r2,  # ← Full context!
    tools=[...],
    tool_choice="auto"
)

final_response = response_r2.choices[0].message.content
print(f"GPT's final response: {final_response}")
# Output: "Done! I've turned on the light for you."
```

---

## KEY INSIGHT: Why "user" role for tool result?

```
CORRECT (what you should do):
messages.append({
    "role": "user",  # ← User/System perspective
    "content": json.dumps({"status": "success", "result": "..."})
})

WRONG (don't do this):
messages.append({
    "role": "tool",  # ← This might confuse older models
    "content": json.dumps({"status": "success", "result": "..."})
})
```

Why? Because when GPT sees this message flow:
```
1. System: "You're a helper"
2. User: "Do X"
3. Assistant: "I'll call tool_service"
4. User: "Tool executed successfully"  ← GPT sees this as "user saying tool worked"
   (not as "tool said this")
```

**GPT interprets the message flow as a conversation**, not as a technical log.

---

## MULTI-TURN CONVERSATION EXAMPLE

```python
# REQUEST #1: "Turn on the light"
messages_r1 = [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "Turn on the light"}
]
response_r1 = call_gpt(messages_r1)
# GPT: "I'll turn on the light"
# tool_calls: [call_service(...)]

# Execute: Light turns on
execute_tool(...)

# REQUEST #2: Send tool result
messages_r2 = [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "Turn on the light"},
    {"role": "assistant", "content": "...", "tool_calls": [...]},
    {"role": "user", "content": '{"status": "success", "result": "..."}'}
]
response_r2 = call_gpt(messages_r2)
# GPT: "Done! Light is on"
# tool_calls: null

# REQUEST #3: User asks follow-up
messages_r3 = [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "Turn on the light"},
    {"role": "assistant", "content": "...", "tool_calls": [...]},
    {"role": "user", "content": '{"status": "success", "result": "..."}'},
    {"role": "assistant", "content": "Done! Light is on"},
    {"role": "user", "content": "Set brightness to 50%"}  ← New user message
]
response_r3 = call_gpt(messages_r3)
# GPT: "I'll set the brightness to 50%"
# tool_calls: [call_service(...)]

# Execute: Light brightness changes
execute_tool(...)

# And so on...
```

---

## THE BEAUTY OF THIS DESIGN

GPT doesn't need to remember anything because:

1. **YOU maintain the state** (messages array)
2. **Each request is self-contained** (full context included)
3. **GPT can always understand** what happened before (it reads the messages)
4. **Perfectly stateless** while appearing stateful to the user

```
User perspective:
"I have a conversation with an AI"

Technical reality:
"Each API call is independent, but we send the full context each time"

Result:
"Feels like stateful, actually stateless"
```

---

## REQUEST #2 BREAKDOWN: Word by Word

```
REQUEST #2 DATA:
{
  "messages": [
    {"role": "system", "content": "You are a smart home AI"},
    
    {"role": "user", "content": "Turn on the light"},
    
    {
      "role": "assistant",
      "content": "I'll turn on the light for you",
      "tool_calls": [{
        "id": "call_abc123",
        "function": {
          "name": "call_service",
          "arguments": "{...}"
        }
      }]
    },
    
    {
      "role": "user",
      "content": "{
        \"tool_call_id\": \"call_abc123\",
        \"status\": \"success\",
        \"result\": \"Light is now on\"
      }"
    }
  ]
}

GPT's INTERPRETATION:

Step 1: Read system prompt
  → "I'm a smart home assistant"

Step 2: Read user message
  → "The user wants to turn on the light"

Step 3: Read my previous response
  → "Oh! I already responded that I'll turn it on"
  → "And I called the call_service tool with light parameters"

Step 4: Read tool result
  → "Oh! The light execution was successful"
  → "The light is now actually ON"

Step 5: Decide next action
  → "The task is complete"
  → "I should confirm to the user"

Output:
  → "Done! I've successfully turned on the light for you."
  → No more tool calls needed
```

---

## STATELESS vs STATEFUL

| Aspect | Stateless (GPT) | Stateful (Human) |
|--------|---|---|
| **Memory Between Calls** | ❌ None | ✅ Full |
| **Context In Request** | ✅ Via messages array | ❌ Internal memory |
| **What GPT knows** | Only what's in messages | N/A |
| **Scalability** | ✅ Perfect (no memory bloat) | ❌ Limited (memory grows) |
| **Cost** | Per-request basis | Depends on memory size |
| **Reliability** | ✅ Every request independent | ⚠️ Memory can be lost |

---

## WHY THIS IS BRILLIANT

1. **Scalability**: No server needs to remember thousands of conversations
2. **Reliability**: Message corruption doesn't corrupt state
3. **Flexibility**: Can replay/resume conversations easily
4. **Cost**: Only pay for tokens actually used

```
Your code:
- Maintains conversation history (messages array)
- Sends full context to stateless GPT
- GPT always understands full picture
- Appears to user as continuous conversation

Reality:
- Each GPT instance is independent
- No memory between instances
- But context is preserved via messages
```

---

## SUMMARY

**How stateless GPT handles tool results:**

1. **First request**: User message → GPT reads it → Returns tool call
2. **Your code**: Executes the tool → Gets result
3. **Second request**: You send:
   - Original user message (again)
   - GPT's tool decision (again)
   - Tool execution result (NEW!)
4. **GPT (fresh instance)**: Reads full message history → Understands what happened → Generates final response

**The messages array IS the state machine!**

GPT doesn't remember, but IT DOESN'T NEED TO because you send the entire conversation history with every request.


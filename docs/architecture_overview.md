# Architecture Overview: Sliding Window + LangGraph Prep

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Home Assistant Core                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ ConversationInput
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              AzureOpenAIConversationAgent                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Orchestration Layer                                 │  │
│  │  - Request routing (local vs LLM)                    │  │
│  │  - Early timeout handling                            │  │
│  │  - Statistics tracking                               │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────┬────────────┬────────────┬─────────────────────┘
             │            │            │
             ▼            ▼            ▼
    ┌────────────┐  ┌─────────────┐  ┌──────────────────┐
    │   Local    │  │   Memory    │  │   LLM Clients   │
    │  Intent    │  │  Manager    │  │  Chat/Response  │
    │  Handler   │  │  (NEW)      │  │                 │
    └────────────┘  └─────────────┘  └──────────────────┘
                           │
                           │ ConversationWindow
                           ▼
                    ┌─────────────────┐
                    │   State Layer   │
                    │  - MessageEntry │
                    │  - AgentState   │
                    └─────────────────┘
                           │
                           │ (Future)
                           ▼
                    ┌─────────────────┐
                    │   LangGraph     │
                    │   StateDict     │
                    └─────────────────┘
```

## Component Responsibilities

### 1. Agent (Orchestrator)
**File**: `core/agent.py`

**Responsibilities**:
- Receive ConversationInput from HA
- Route to local intent handler or LLM
- Manage conversation memory
- Track statistics
- Handle early timeouts
- Coordinate tool calling

**Key Changes**:
```python
# Before
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_text}
]

# After (with sliding window)
await self._memory.add_message(conv_id, "user", user_text)
messages = await self._memory.get_messages(conv_id)
```

### 2. ConversationMemoryManager (NEW)
**File**: `context/conversation_memory.py`

**Responsibilities**:
- Maintain conversation history per conversation_id
- Enforce token limits with FIFO eviction
- Count tokens accurately (tiktoken)
- Preserve system messages (optional)
- Support custom tags for filtering
- Provide statistics

**Key Features**:
```python
# Token-limited storage
window = ConversationWindow(
    conversation_id="conv123",
    messages=[MessageEntry(...)],
    max_tokens=4000,
    current_tokens=1250,
)

# FIFO eviction
while window.current_tokens > window.max_tokens:
    evict_oldest_message()

# Tag filtering
messages = await memory.get_messages(
    "conv123",
    tag_filter={"important", "context:lights"}
)
```

### 3. State Objects (NEW)
**File**: `core/state.py`

**Responsibilities**:
- Type-safe state representation
- LangGraph compatibility preparation
- Serialization for future persistence

**Structure**:
```python
@dataclass
class MessageEntry:
    role: str
    content: str
    timestamp: datetime
    token_count: int
    tags: set[str]
    
    def to_langgraph_message(self) -> dict:
        # Future migration point
```

### 4. Interfaces (NEW)
**File**: `core/interfaces.py`

**Responsibilities**:
- Abstract contracts for components
- Decoupling for LangGraph migration
- Type hints for protocols

**Interfaces**:
- `IStateManager`: State persistence
- `ILLMClient`: LLM communication
- `IMemoryManager`: Memory operations

### 5. SystemPromptBuilder (Existing)
**File**: `context/system_prompt.py`

**Interaction with Memory**:
- Builds system prompt once per conversation
- Memory manager stores it with `role="system"`
- Optionally preserved during eviction

### 6. MCPManager (Existing, Separate)
**File**: `context/mcp_manager.py`

**Separation Rationale**:
- MCP tracks **entity state** (light.kitchen: on → off)
- Memory tracks **conversation history** (user: "turn off light", assistant: "done")
- Independent lifecycles
- MCP sends deltas, Memory manages window

## Data Flow

### 1. User Message → Memory → LLM

```
User: "Turn on the lights"
    ↓
Agent.async_process()
    ↓
Memory.add_message(conv_id, "user", "Turn on the lights", tags={"input"})
    ↓
Memory.get_messages(conv_id) → [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "Turn on the lights"}
]
    ↓
LLMClient.complete(messages)
    ↓
Response: "I've turned on the lights"
    ↓
Memory.add_message(conv_id, "assistant", "I've turned on...", tags={"output"})
```

### 2. Token Limit Exceeded → FIFO Eviction

```
Current: 3800 tokens (10 messages)
New message: 400 tokens
Total: 4200 tokens > 4000 max
    ↓
FIFO Eviction:
    While total > max:
        Remove oldest non-system message
        Update total tokens
    ↓
Result: 3900 tokens (9 messages) ✓
```

### 3. Tag-Based Context Filtering

```
All messages:
1. {role: "user", content: "lights on", tags: {"input", "context:lights"}}
2. {role: "assistant", content: "done", tags: {"output", "context:lights"}}
3. {role: "user", content: "weather?", tags: {"input", "context:weather"}}
4. {role: "assistant", content: "sunny", tags: {"output", "context:weather"}}

Filter: tag_filter={"context:lights"}
    ↓
Result: messages 1 and 2 only
```

## Configuration Hierarchy

```yaml
# 1. Defaults (const.py)
RECOMMENDED_SLIDING_WINDOW_MAX_TOKENS = 4000

# 2. Config Entry (initial setup)
data:
  api_key: "..."
  api_base: "..."
options:
  sliding_window_max_tokens: 4000

# 3. Runtime (options flow)
config_entry.options["sliding_window_max_tokens"] = 6000

# 4. Agent Config (typed)
config = AgentConfig.from_dict(hass, entry.data | entry.options)
config.sliding_window_max_tokens  # 6000
```

## Memory Management Strategy

### Token Budget Allocation

For `max_tokens = 4000`:

```
System Prompt:     ~500 tokens  (12.5%)
Recent Context:   ~2500 tokens  (62.5%)
Buffer Space:     ~1000 tokens  (25.0%)
──────────────────────────────────────
Total:             4000 tokens  (100%)
```

### Eviction Priority (FIFO)

```
Priority: Newest → Oldest

[System Message]  ← Never evicted (if preserve_system=True)
[User Message 10] ← Most recent
[Asst Response 9]
[User Message 8]
[Asst Response 7]
[User Message 6]
[Asst Response 5]
[User Message 4]
[Asst Response 3]
[User Message 2]  ← Evicted first
[Asst Response 1] ← Evicted second
```

### Tag Strategy

| Tag Pattern | Purpose | Example |
|-------------|---------|---------|
| `input` / `output` | Message direction | All user/assistant |
| `context:*` | Topic grouping | `context:lights`, `context:weather` |
| `important` | Preserve if possible | User constraints |
| `ephemeral` | OK to evict | Search results |
| `tool_call` | Tool invocations | Function calls |

## Performance Characteristics

### Time Complexity

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| Add message | O(1) | Append to list |
| FIFO eviction | O(n) worst | n = messages to evict |
| Token counting | O(m) | m = message length |
| Get messages | O(n) | n = total messages |
| Tag filtering | O(n) | Linear scan |

### Space Complexity

```
Per Message:
- Content: ~200-500 chars → ~50-125 tokens
- Metadata: ~100 bytes
- Total: ~400 bytes per message

Per Window (4000 tokens):
- ~1000 messages max
- ~400 KB memory
- Negligible overhead
```

### Benchmarks (Expected)

```
Operation              Time        Memory
─────────────────────────────────────────
Add message           < 1ms       +400 B
FIFO eviction         < 1ms       -400 B
Token count           < 0.5ms     0 B
Get messages (all)    < 1ms       0 B
Get messages (tagged) < 2ms       0 B
Reset conversation    < 0.1ms     -400KB
```

## LangGraph Migration Path

### Phase 1: Current (Minimal Prep)

```python
# State objects exist but simple
@dataclass
class AgentState:
    conversation_id: str
    window: ConversationWindow
    
    def to_langgraph_state(self) -> dict:
        # Stub for now
        return {...}
```

### Phase 2: Migration (3-6 months)

```python
# LangGraph StateDict
from langgraph.graph import StateGraph

# Convert to LangGraph state
state = {
    "messages": [msg.to_langgraph_message() for msg in window.messages],
    "conversation_id": conv_id,
}

# Define graph
graph = StateGraph(AgentState)
graph.add_node("intent_detection", detect_intent)
graph.add_node("llm_call", call_llm)
graph.add_edge("intent_detection", "llm_call")
```

### Phase 3: Full Migration

```python
# State manager becomes LangGraph checkpoint
from langgraph.checkpoint import MemorySaver

checkpointer = MemorySaver()

graph = graph.compile(checkpointer=checkpointer)

# Invoke with state
result = graph.invoke(
    {"messages": [...], "conversation_id": "..."},
    config={"configurable": {"thread_id": conv_id}}
)
```

## Testing Strategy

### Unit Tests (test_conversation_memory.py)

```python
✓ test_add_message_creates_window
✓ test_fifo_eviction
✓ test_preserve_system_messages
✓ test_tag_filtering
✓ test_reset_conversation
✓ test_token_counting
✓ test_multiple_conversations
✓ test_tag_distribution_stats
```

### Integration Tests

```python
✓ test_long_conversation_with_eviction
✓ test_context_preservation_across_turns
✓ test_reset_mid_conversation
✓ test_concurrent_conversations
✓ test_tool_calling_with_memory
✓ test_early_timeout_with_memory
```

### Performance Tests

```python
✓ benchmark_token_counting_speed
✓ benchmark_eviction_performance
✓ measure_memory_usage_growth
✓ stress_test_many_messages
✓ stress_test_many_conversations
```

## Monitoring & Debugging

### Logging

```python
# Agent logs window stats after each response
self._logger.debug(
    "Window: conv=%s, msgs=%d, tokens=%d/%d (%.1f%%)",
    conv_id, msg_count, current, max, utilization
)

# Memory manager logs evictions
self._logger.debug(
    "Evicted: conv=%s, role=%s, tokens=%d",
    conv_id, role, token_count
)
```

### Statistics API

```python
stats = memory.get_stats(conv_id)
# {
#   "message_count": 8,
#   "current_tokens": 1250,
#   "max_tokens": 4000,
#   "utilization": 31.25,
#   "tag_distribution": {
#       "input": 4,
#       "output": 4,
#       "context:lights": 2
#   }
# }
```

### Health Checks

```python
# Check for memory leaks
all_convs = memory.get_all_conversations()
if len(all_convs) > 100:
    logger.warning("Too many active conversations: %d", len(all_convs))

# Check for high utilization
for conv_id in all_convs:
    stats = memory.get_stats(conv_id)
    if stats["utilization"] > 95:
        logger.warning("Window nearly full: %s", conv_id)
```

## Security Considerations

### Memory Isolation

- Each `conversation_id` has separate window
- No cross-conversation access
- Conversation IDs from HA (trusted)

### Token Limits

- Prevents unbounded memory growth
- Protects against DoS via long conversations
- Configurable per deployment

### Data Persistence

- In-memory only (no disk writes)
- Conversations cleared on restart
- No sensitive data leakage risk

## Future Enhancements

### Short Term (v1.1)

- [ ] Importance-based eviction (preserve tagged messages)
- [ ] Conversation summarization (compress old context)
- [ ] Export/import conversations (for debugging)

### Medium Term (v1.2)

- [ ] Semantic similarity search (retrieve relevant past messages)
- [ ] Automatic context summarization
- [ ] Conversation branching (fork conversations)

### Long Term (v2.0)

- [ ] LangGraph migration complete
- [ ] Persistent checkpointing
- [ ] Multi-modal message support (images, audio)

---

## Summary

The sliding window implementation provides:

✅ **Efficient memory management** with token limits
✅ **FIFO eviction** for predictable behavior
✅ **Custom tags** for flexible context filtering
✅ **LangGraph preparation** with typed state objects
✅ **In-memory storage** for fast access
✅ **Comprehensive statistics** for monitoring

All while maintaining **backward compatibility** and preparing for future **LangGraph migration**.

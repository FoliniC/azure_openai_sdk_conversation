# Sliding Window Memory Management

## Overview

The **Sliding Window** feature manages conversation history with token limits, ensuring efficient memory usage while preserving context for meaningful conversations.

## Key Features

- **FIFO Eviction**: Oldest messages removed first when limit exceeded
- **Accurate Token Counting**: Uses tiktoken for precise token measurement
- **System Message Preservation**: Optionally preserves system prompts
- **Custom Tags**: Mark and filter messages by context
- **In-Memory Storage**: Fast access, no disk I/O

## Configuration

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `sliding_window_enable` | bool | `true` | Enable/disable sliding window |
| `sliding_window_max_tokens` | int | `4000` | Maximum tokens in window |
| `sliding_window_preserve_system` | bool | `true` | Preserve system messages |

### Via UI

1. Go to **Settings** → **Devices & Services**
2. Find **Azure OpenAI SDK Conversation**
3. Click **Configure**
4. Adjust sliding window settings

### Via YAML

```yaml
# configuration.yaml (not recommended, use UI)
azure_openai_sdk_conversation:
  sliding_window_enable: true
  sliding_window_max_tokens: 4000
  sliding_window_preserve_system: true
```

## How It Works

### Token Limits

The sliding window maintains a maximum token count. When adding a new message would exceed the limit:

1. Calculate token count for new message
2. Add message to window
3. If total > max_tokens:
   - Remove oldest message (FIFO)
   - Repeat until total ≤ max_tokens
   - Preserve system messages if configured

### Example

```
Max tokens: 100
Current: 85 tokens (5 messages)

New message: 20 tokens
Total: 105 tokens (exceeds limit)

Action: Remove oldest user message (15 tokens)
Result: 90 tokens (5 messages) ✓
```

## Custom Tags

Tags allow you to mark messages for specific contexts and retrieve them selectively.

### Built-in Tags

- `input`: User messages
- `output`: Assistant responses
- `system`: System prompts

### Custom Tags

```python
# Example: Mark messages by topic
await memory.add_message(
    conversation_id="conv123",
    role="user",
    content="Turn on the lights",
    tags={"input", "home_automation", "context:lights"}
)

# Retrieve only home automation messages
messages = await memory.get_messages(
    "conv123",
    tag_filter={"home_automation"}
)
```

### Common Tag Patterns

**Context Grouping**:
```python
tags={"context:weather"}
tags={"context:calendar"}
tags={"context:lights"}
```

**Importance Marking**:
```python
tags={"important"}  # Preserve if possible
tags={"ephemeral"}  # OK to evict early
```

**Feature Grouping**:
```python
tags={"tool_call"}
tags={"web_search"}
tags={"local_intent"}
```

## API Reference

### ConversationMemoryManager

#### Methods

**`add_message(conversation_id, role, content, tags=None)`**

Add message to conversation history.

```python
await memory.add_message(
    conversation_id="conv123",
    role="user",
    content="Hello",
    tags={"input", "greeting"}
)
```

**`get_messages(conversation_id, tag_filter=None)`**

Get messages for LLM context.

```python
# All messages
messages = await memory.get_messages("conv123")

# Filtered by tag
messages = await memory.get_messages(
    "conv123",
    tag_filter={"important"}
)
```

**`reset_conversation(conversation_id)`**

Reset conversation history.

```python
await memory.reset_conversation("conv123")
```

**`get_stats(conversation_id)`**

Get window statistics.

```python
stats = memory.get_stats("conv123")
# {
#   "exists": true,
#   "message_count": 5,
#   "current_tokens": 150,
#   "max_tokens": 4000,
#   "utilization": 3.75,
#   "tag_distribution": {"input": 3, "output": 2}
# }
```

## Performance

### Token Counting

Uses **tiktoken** for accurate token counting:
- ~0.1ms per message
- Exact match with OpenAI's tokenization
- Supports all GPT models

### Memory Usage

In-memory storage only:
- ~1KB per message (average)
- 4000 token window ≈ 1000 messages ≈ 1MB
- No disk I/O overhead

### Eviction Performance

FIFO eviction is O(1):
- Constant time regardless of window size
- No sorting or complex logic
- Fast message removal

## Best Practices

### 1. Choose Appropriate Window Size

**General conversation**: 4000 tokens (default)
- ~10-15 exchanges
- Good context retention

**Technical support**: 6000-8000 tokens
- More context for troubleshooting
- Preserves command history

**Simple commands**: 2000 tokens
- Minimal context needed
- Faster responses

### 2. Use Tags Strategically

**DO**:
- Mark important constraints: `{"important", "constraint"}`
- Group by topic: `{"context:lights"}`
- Identify message types: `{"tool_call"}`

**DON'T**:
- Over-tag every message
- Use tags for temporary state
- Create too many tag variations

### 3. Monitor Window Utilization

```python
stats = memory.get_stats(conv_id)
if stats["utilization"] > 90:
    # Window nearly full, consider:
    # - Increasing max_tokens
    # - Summarizing old context
    # - Resetting conversation
```

### 4. Reset When Needed

Reset conversation when:
- User starts new topic explicitly
- Window consistently full
- Context no longer relevant

```python
# User says "let's start over"
await memory.reset_conversation(conv_id)
```

## Troubleshooting

### Messages Disappearing Too Quickly

**Symptom**: Important context evicted prematurely

**Solutions**:
1. Increase `sliding_window_max_tokens`
2. Tag important messages
3. Enable `sliding_window_preserve_system`

### Token Count Inaccurate

**Symptom**: Window size doesn't match expectations

**Check**:
- tiktoken installed: `pip show tiktoken`
- Encoding used: `cl100k_base` (GPT-4/3.5)
- Token counts in stats: `memory.get_stats(conv_id)`

### High Memory Usage

**Symptom**: Memory usage growing over time

**Solutions**:
- Reduce `sliding_window_max_tokens`
- Reset inactive conversations
- Check for conversation ID leaks

## Migration from Legacy System

If upgrading from a version without sliding window:

1. **Enable gradually**: Start with high max_tokens
2. **Monitor logs**: Check eviction messages
3. **Adjust limits**: Based on usage patterns
4. **Update automations**: If they depend on full history

## Future: LangGraph Migration

The sliding window is designed for easy migration to LangGraph:

- **State objects**: Already typed and compatible
- **Interfaces**: Abstract layer ready
- **Checkpointing**: Structure supports it

When migrating:
1. ConversationWindow → LangGraph State
2. Tags → LangGraph metadata
3. FIFO eviction → Custom reducer

## FAQ

**Q: Does sliding window work with MCP?**
A: Yes, they're independent. MCP manages entity state, sliding window manages conversation history.

**Q: Are messages persisted across restarts?**
A: No, in-memory only. Conversations reset on restart.

**Q: Can I disable sliding window?**
A: Yes, set `sliding_window_enable: false`. All messages will be kept (may hit API limits).

**Q: Does it work with tool calling?**
A: Yes, tool messages are stored like any other role.

**Q: What happens if I exceed max_tokens?**
A: FIFO eviction automatically removes oldest messages.

## Support

For issues or questions:
- GitHub Issues: [repository]/issues
- Discussions: [repository]/discussions
- Logs: Check `home-assistant.log` for eviction details

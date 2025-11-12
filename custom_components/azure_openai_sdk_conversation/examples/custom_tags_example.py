"""
Example: Using custom tags in ConversationMemoryManager.

This example shows how to use tags to mark and filter messages
belonging to specific contexts.
"""

from custom_components.azure_openai_sdk_conversation.context.conversation_memory import (
    ConversationMemoryManager,
)


async def example_custom_tags(memory_manager: ConversationMemoryManager):
    """
    Example: Multi-context conversation with custom tags.
    
    Scenario: User switches between different topics/contexts
    within the same conversation.
    """
    
    conv_id = "multi_context_conv"
    
    # -------------------------------------------------------------------------
    # Context 1: Home automation
    # -------------------------------------------------------------------------
    
    await memory_manager.add_message(
        conversation_id=conv_id,
        role="user",
        content="Turn on the living room lights",
        tags={"input", "home_automation", "context:lights"},
    )
    
    await memory_manager.add_message(
        conversation_id=conv_id,
        role="assistant",
        content="I've turned on the living room lights.",
        tags={"output", "home_automation", "context:lights"},
    )
    
    # -------------------------------------------------------------------------
    # Context 2: Weather information
    # -------------------------------------------------------------------------
    
    await memory_manager.add_message(
        conversation_id=conv_id,
        role="user",
        content="What's the weather like today?",
        tags={"input", "information", "context:weather"},
    )
    
    await memory_manager.add_message(
        conversation_id=conv_id,
        role="assistant",
        content="It's sunny with a high of 75Â°F.",
        tags={"output", "information", "context:weather"},
    )
    
    # -------------------------------------------------------------------------
    # Context 3: Calendar/scheduling
    # -------------------------------------------------------------------------
    
    await memory_manager.add_message(
        conversation_id=conv_id,
        role="user",
        content="What's on my calendar tomorrow?",
        tags={"input", "productivity", "context:calendar"},
    )
    
    await memory_manager.add_message(
        conversation_id=conv_id,
        role="assistant",
        content="You have a meeting at 10 AM.",
        tags={"output", "productivity", "context:calendar"},
    )
    
    # -------------------------------------------------------------------------
    # Retrieve messages by context
    # -------------------------------------------------------------------------
    
    # Get all messages (no filter)
    all_messages = await memory_manager.get_messages(conv_id)
    print(f"Total messages: {len(all_messages)}")
    
    # Get only home automation messages
    home_messages = await memory_manager.get_messages(
        conv_id,
        tag_filter={"context:lights"},
    )
    print(f"Home automation messages: {len(home_messages)}")
    
    # Get only weather messages
    weather_messages = await memory_manager.get_messages(
        conv_id,
        tag_filter={"context:weather"},
    )
    print(f"Weather messages: {len(weather_messages)}")
    
    # Get only calendar messages
    calendar_messages = await memory_manager.get_messages(
        conv_id,
        tag_filter={"context:calendar"},
    )
    print(f"Calendar messages: {len(calendar_messages)}")
    
    # -------------------------------------------------------------------------
    # Get statistics with tag distribution
    # -------------------------------------------------------------------------
    
    stats = memory_manager.get_stats(conv_id)
    print("\nConversation statistics:")
    print(f"  Total messages: {stats['message_count']}")
    print(f"  Token usage: {stats['current_tokens']}/{stats['max_tokens']}")
    print(f"  Utilization: {stats['utilization']:.1f}%")
    print("\nTag distribution:")
    for tag, count in stats['tag_distribution'].items():
        print(f"  {tag}: {count}")


async def example_important_messages(memory_manager: ConversationMemoryManager):
    """
    Example: Marking important messages that should be preserved.
    
    Use case: User gives explicit instructions that should not be evicted.
    """
    
    conv_id = "important_context_conv"
    
    # Add important system constraint
    await memory_manager.add_message(
        conversation_id=conv_id,
        role="user",
        content="Please always respond in Italian.",
        tags={"input", "important", "constraint"},
    )
    
    # Regular conversation
    await memory_manager.add_message(
        conversation_id=conv_id,
        role="user",
        content="What's 2+2?",
        tags={"input", "question"},
    )
    
    await memory_manager.add_message(
        conversation_id=conv_id,
        role="assistant",
        content="La risposta Ã¨ 4.",
        tags={"output"},
    )
    
    # Add many more messages to trigger eviction
    for i in range(20):
        await memory_manager.add_message(
            conversation_id=conv_id,
            role="user",
            content=f"Question {i}",
            tags={"input", "question"},
        )
        
        await memory_manager.add_message(
            conversation_id=conv_id,
            role="assistant",
            content=f"Answer {i}",
            tags={"output"},
        )
    
    # Check if important message is still there
    messages = await memory_manager.get_messages(conv_id)
    
    has_important = any(
        "Please always respond in Italian" in msg["content"]
        for msg in messages
    )
    
    print(f"Important message preserved: {has_important}")
    
    # Get only important messages
    important_messages = await memory_manager.get_messages(
        conv_id,
        tag_filter={"important"},
    )
    
    print(f"Important messages: {len(important_messages)}")
    for msg in important_messages:
        print(f"  - {msg['role']}: {msg['content'][:50]}")


async def example_ephemeral_context(memory_manager: ConversationMemoryManager):
    """
    Example: Ephemeral context that can be safely evicted.
    
    Use case: Temporary information like search results or API responses
    that don't need to be preserved long-term.
    """
    
    conv_id = "ephemeral_conv"
    
    # Add ephemeral search results
    await memory_manager.add_message(
        conversation_id=conv_id,
        role="assistant",
        content="Here are the search results for 'best pizza nearby': ...(long list)...",
        tags={"output", "ephemeral", "search_results"},
    )
    
    # User makes a choice
    await memory_manager.add_message(
        conversation_id=conv_id,
        role="user",
        content="I'll go with the second one.",
        tags={"input", "decision"},
    )
    
    await memory_manager.add_message(
        conversation_id=conv_id,
        role="assistant",
        content="Great choice! I've saved it to your favorites.",
        tags={"output", "confirmation"},
    )
    
    # Later: ephemeral messages can be filtered out if needed
    # or will be evicted naturally by FIFO when limit is reached
    
    # non_ephemeral = await memory_manager.get_messages(conv_id)
    # Note: tag_filter uses set intersection, so this would need
    # a different implementation for "exclude" logic. For now,
    # ephemeral messages will just be evicted naturally by FIFO.


# Example usage in agent
"""
In core/agent.py:

async def async_process(self, user_input: ConversationInput):
    conv_id = user_input.conversation_id
    
    # Determine context from user input
    if "light" in user_input.text.lower():
        context_tags = {"context:lights", "home_automation"}
    elif "weather" in user_input.text.lower():
        context_tags = {"context:weather", "information"}
    elif "calendar" in user_input.text.lower():
        context_tags = {"context:calendar", "productivity"}
    else:
        context_tags = {"context:general"}
    
    # Add user message with context tags
    await self._memory.add_message(
        conversation_id=conv_id,
        role="user",
        content=user_input.text,
        tags={"input"} | context_tags,
    )
    
    # Process with LLM...
    response = await self._process_with_llm(...)
    
    # Add assistant response with same context tags
    await self._memory.add_message(
        conversation_id=conv_id,
        role="assistant",
        content=response,
        tags={"output"} | context_tags,
    )
"""

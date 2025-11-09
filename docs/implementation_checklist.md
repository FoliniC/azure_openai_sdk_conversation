# Implementation Checklist: Sliding Window + LangGraph Prep

## ✅ Phase 1: Core Implementation

### Dependencies
- [ ] Add `tiktoken>=0.5.0` to `requirements.txt`
- [ ] Install: `pip install tiktoken`
- [ ] Verify installation: `python -c "import tiktoken; print(tiktoken.__version__)"`

### Constants
- [ ] Add sliding window constants to `const.py`:
  - `CONF_SLIDING_WINDOW_ENABLE`
  - `CONF_SLIDING_WINDOW_MAX_TOKENS`
  - `CONF_SLIDING_WINDOW_PRESERVE_SYSTEM`
  - Recommended defaults

### Core State Objects
- [ ] Create `core/state.py`:
  - `MessageEntry` dataclass
  - `ConversationWindow` dataclass
  - `AgentState` dataclass
  - `to_langgraph_*` methods (stubs for now)

### Interfaces
- [ ] Create `core/interfaces.py`:
  - `IStateManager` protocol
  - `ILLMClient` protocol
  - `IMemoryManager` abstract class

### Memory Manager
- [ ] Create `context/conversation_memory.py`:
  - `ConversationMemoryManager` class
  - Import tiktoken
  - Implement FIFO eviction
  - Implement tag filtering
  - Implement statistics

### Module Exports
- [ ] Update `core/__init__.py`: export new classes
- [ ] Update `context/__init__.py`: export ConversationMemoryManager

## ✅ Phase 2: Agent Integration

### Config Updates
- [ ] Update `core/config.py`:
  - Add sliding window fields to `AgentConfig`
  - Update `from_dict` method

### Agent Modifications
- [ ] Update `core/agent.py`:
  - Import `ConversationMemoryManager`
  - Initialize in `__init__`
  - Add message on user input
  - Build messages from window in `_process_with_llm`
  - Add message on assistant response
  - Log window stats
  - Implement `async_reset_conversation` method
  - Implement `get_conversation_stats` method
  - Cleanup in `async_close`

### Early Timeout Integration
- [ ] Ensure `_execute_with_early_timeout` works with sliding window
- [ ] Test background task completion

### Tool Calling Integration
- [ ] Verify `ToolManager.process_tool_loop` works with sliding window
- [ ] Test tool messages are stored correctly

## ✅ Phase 3: Configuration UI

### Config Flow
- [ ] Update `config_flow.py`:
  - Import sliding window constants
  - Add fields to `async_step_params`
  - Add defaults to `_create_entry`
  - Test initial setup

### Options Flow
- [ ] Update `options_flow.py`:
  - Add sliding window section
  - Conditional display based on enable flag
  - Test configuration changes

### Translations
- [ ] Update `strings.json` (EN):
  - Add descriptions for sliding window options
- [ ] Update `translations/en.json`
- [ ] Update `translations/it.json`

## ✅ Phase 4: Testing

### Unit Tests
- [ ] Create `tests/test_conversation_memory.py`:
  - Test window creation
  - Test FIFO eviction
  - Test system message preservation
  - Test tag filtering
  - Test reset functionality
  - Test token counting
  - Test multiple conversations
  - Test statistics

### Integration Tests
- [ ] Test with real LLM:
  - Long conversation with eviction
  - Context preservation
  - Reset mid-conversation
  - Multiple concurrent conversations

### Performance Tests
- [ ] Benchmark token counting speed
- [ ] Benchmark eviction performance
- [ ] Monitor memory usage

## ✅ Phase 5: Documentation

- [ ] Create `docs/SLIDING_WINDOW.md`:
  - Overview
  - Configuration
  - How it works
  - API reference
  - Best practices
  - Troubleshooting
  - Migration guide

- [ ] Create `examples/custom_tags_usage.py`:
  - Multi-context example
  - Important messages example
  - Ephemeral context example

- [ ] Update main `README.md`:
  - Add sliding window section
  - Link to detailed docs

## ✅ Phase 6: Release Preparation

### Code Review
- [ ] Self-review all changes
- [ ] Check code style (Ruff)
- [ ] Type checking (mypy)
- [ ] Ensure no breaking changes

### Testing
- [ ] Test in development environment
- [ ] Test in production-like setup
- [ ] Test upgrade path from previous version

### Documentation
- [ ] Update CHANGELOG.md
- [ ] Update version number
- [ ] Write release notes

## 🔮 Future: LangGraph Migration (Not Now)

When migrating to LangGraph (3-6 months):

### State Migration
- [ ] Implement `AgentState.to_langgraph_state()` fully
- [ ] Create LangGraph nodes from agent methods
- [ ] Define edges for flow control

### Interface Implementation
- [ ] Implement concrete `IStateManager` for LangGraph
- [ ] Adapt `ILLMClient` to LangGraph nodes
- [ ] Create checkpointing mechanism

### Testing
- [ ] Compatibility tests
- [ ] Performance comparison
- [ ] Feature parity validation

---

## Estimated Timeline

| Phase | Duration | Notes |
|-------|----------|-------|
| 1. Core Implementation | 2-3 hours | Most critical |
| 2. Agent Integration | 1-2 hours | Careful testing needed |
| 3. Configuration UI | 1 hour | Straightforward |
| 4. Testing | 2-3 hours | Thorough testing |
| 5. Documentation | 1-2 hours | Clear examples |
| 6. Release Prep | 1 hour | Final checks |
| **Total** | **8-12 hours** | Single developer |

## Priority Order

**Must Have (MVP)**:
1. Core state objects (`state.py`)
2. Memory manager (`conversation_memory.py`)
3. Agent integration (modified `agent.py`)
4. Basic tests

**Should Have (v1.0)**:
5. Configuration UI
6. Full test suite
7. Documentation
8. Examples

**Nice to Have (v1.1+)**:
9. Advanced tag filtering
10. Conversation summarization
11. Importance-based eviction
12. Analytics dashboard

## Success Criteria

✅ **Functional**:
- Sliding window manages message history
- FIFO eviction works correctly
- Token limits enforced
- No breaking changes

✅ **Performance**:
- Token counting < 1ms per message
- Eviction < 1ms per operation
- Memory usage reasonable

✅ **Quality**:
- Test coverage > 80%
- No critical bugs
- Documentation complete
- Code reviewed

## Rollback Plan

If issues arise:
1. Disable sliding window by default
2. Keep legacy behavior as fallback
3. Log issues for investigation
4. Fix in patch release

## Notes

- **In-memory only**: No persistence, simple implementation
- **FIFO eviction**: Predictable, easy to reason about
- **LangGraph prep**: Minimal, just structure
- **Breaking changes**: None expected

## Contact

For questions during implementation:
- Review artifact comments
- Check examples in `/examples/`
- Reference tests in `/tests/`

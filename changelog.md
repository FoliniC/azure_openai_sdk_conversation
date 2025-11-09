# CHANGELOG – Azure OpenAI SDK Conversation

## 1.1.0 - 2025-11-10

### Bug Fixes
- **Event Loop Blocking**: Fixed multiple blocking calls (`tiktoken`, `httpx`) in the Home Assistant event loop, which were causing `RuntimeError` and `Detected blocking call` warnings.
- **Sliding Window Token Counting**: Fixed a major bug in the sliding window token counting. The new implementation now correctly accounts for the token count of both the tool definitions and the dynamic system prompt, ensuring the sliding window works as expected.
- **NameError Resolution**: Resolved several `NameError` exceptions in `llm/responses_client.py` and `context/conversation_memory.py` by adding or restoring missing imports and moving code to the correct scope.

### New Features & Improvements
- **Configuration Warning**: Added an `ERROR` log message that is displayed when the configured `sliding_window_max_tokens` is too small to fit the initial prompt, guiding the user to fix their configuration.
- **On-Demand Tool Calculation**: Refactored the tool token calculation to happen on the first real request instead of at startup. This eliminates "ghost" request logs during initialization and improves startup time.
- **Empty Request Guard**: Added a guard to `async_process` to ignore empty or whitespace-only requests from Home Assistant, preventing unnecessary processing and LLM calls.
- **Code Quality**: Linted the entire codebase with `ruff` and fixed all reported issues.

### Architectural Changes
- **Configurable Sliding Window**: Implemented a configurable sliding window for managing request/response history. This provides a balance between context preservation and resource constraints, ensuring recent messages are always available to the LLM while managing memory efficiently with token limits.
  - User-adjustable window size.
  - Ability for users to reset the conversation context.
  - Support for tagged context for different purposes.
- **Preparation for LangGraph Migration**: The agent logic has been kept in isolated modules, using typed state objects for context and implementing logging hooks for introspection, to facilitate a future migration to LangGraph.

---

## 1.0.2 - 2025-11-05

### Features
- **Local Intent Handling Toggle**: Added a new configuration option (`local_intent_enable`) to allow users to enable or disable direct handling of simple intents (e.g., turning lights on/off) without calling the LLM.
- **Configuration UI Clarity**: Added descriptive help text for numerous configuration options (`ssl_verify`, `log_payload_request`, `early_wait_enable`, etc.) to better explain their behavior.
- **Internationalization**: Updated and synchronized translation files for English (`en.json`), German (`de.json`), French (`fr.json`), and Chinese (`zh.json`) to ensure a consistent user experience.

### Bug Fixes
- **Missing UI Descriptions**: Fixed a bug where descriptions for boolean options (like `ssl_verify`) would not appear in the UI due to an incorrect schema definition.
- **IndentationError in Config Flow**: Corrected an `IndentationError` that prevented the configuration flow from loading.
- **Inconsistent English Translations**: Resolved an issue where the `en.json` file was out of sync with `strings.json`, causing missing text in the English UI.

### Improvements
- **Code Quality**: Performed general code cleanup and resolved all linting issues reported by `ruff`.

---

## 1.0.0 - November 2025

### 🎉 Major Release - Stability & Enhanced Logging

This release focuses on significantly improving the stability and reliability of the conversation agent, particularly around tool calling and API interactions. It also introduces advanced logging capabilities for better debugging and insight into model behavior.

### Features

-   **Advanced Payload Logging**: Introduced a new option (`payload_log_path`) to log detailed API request/response payloads and system messages to a custom file. This includes `conversation_id`, message length, and execution time, with concise `WARNING` messages in the main Home Assistant log.
-   **Improved Tool Schema Generation**: Enhanced tool schema generation to support flexible targeting by `area_id`, `device_id`, `floor_id`, and `label_id` for Home Assistant services, in addition to `entity_id`.

### Bug Fixes

-   **Tool Calling Argument Parsing**: Fixed a critical bug where tool call arguments from streaming API responses were not correctly parsed, leading to empty arguments and service call failures.
-   **Empty Tool Arguments**: Resolved `JSONDecodeError` when the LLM provided empty strings for tool arguments.
-   **Content Filter Violations**: Mitigated Azure OpenAI content filter violations by changing the tool execution success message to a structured JSON format, reducing false positives.
-   **`StreamClosed` Error**: Fixed `StreamClosed` errors by ensuring the full error response body is read before raising an exception.
-   **`AttributeError` Series**: Addressed a series of `AttributeError`s related to missing or incorrectly referenced configuration attributes (`base_url`, `ssl_verify`, `max_completion_tokens`, `_tools`).
-   **`NameError` Series**: Corrected `NameError`s in the options flow due to missing imports of configuration constants (`CONF_SSL_VERIFY`, `CONF_PAYLOAD_LOG_PATH`).
-   **Missing Conversation ID in Logs**: Fixed an issue where `conversation_id` was not correctly propagated and logged in custom payload files.
-   **Empty Response Issue**: Resolved a bug where the agent would report "No textual response was received from the model" despite a valid response, due to an issue in value propagation.

### Improvements

-   **Vocabulary Normalization Clarity**: Provided clarification and debugging for the vocabulary normalization feature, explaining its purpose and how to disable or customize it.
-   **General Stability & Refactoring**: Numerous minor code refactorings and stability improvements across the component.

### Breaking Changes

-   None. This release is focused on stability and new features.

### Upgrade Guide

1.  Update the component to version `1.0.0`.
2.  Review the new `payload_log_path` option in the integration's configuration if you wish to enable detailed payload logging.
3.  If you use vocabulary normalization, review the `assist_synonyms_it.json` file and the `vocabulary_enable` option to ensure it meets your needs.

---

## 0.6.0 - December 2025
### 🎉 Major Features

- **Tool Calling (Function Calling)**: LLM can now directly call Home Assistant services!
  - Automatic service discovery and schema generation
  - Support for all HA service domains (with configurable whitelist)
  - Safe execution with multiple validation layers
  - Rate limiting and iteration limits
  - Multi-turn tool calling loops
  - Parallel and sequential execution modes

### Features

- **Tool Schema Builder**: Automatically converts HA service schemas to OpenAI tool format
  - Supports all HA selector types (entity, number, boolean, select, etc.)
  - Dynamic parameter validation
  - Description and example extraction

- **Function Executor**: Safe service call execution
  - Domain whitelist (default: light, switch, climate, cover, fan, media_player, lock, vacuum)
  - Service blacklist (restart, stop, etc.)
  - Entity validation (only existing, exposed entities)
  - Rate limiting (30 calls/min default, configurable)
  - Comprehensive error handling

- **Tool Manager**: Orchestrates tool calling workflow
  - Tool schema caching (5-min TTL)
  - Multi-iteration loop support (max 5 by default)
  - First chunk tracking for performance metrics
  - Automatic fallback to regular completion

- **LLM Client Extensions**: Enhanced ChatClient and ResponsesClient
  - `complete_with_tools()` method for both APIs
  - Streaming tool call extraction from SSE
  - Tool call delta accumulation
  - Backward compatible with existing code

### Configuration

- **New Options**:
  - `tools_enable`: Enable/disable tool calling (default: true)
  - `tools_whitelist`: Comma-separated allowed domains
  - `tools_max_iterations`: Max tool call loops (default: 5)
  - `tools_max_calls_per_minute`: Rate limit (default: 30)
  - `tools_parallel_execution`: Execute tools in parallel (default: false)

### Statistics

- **Extended Metrics**: Tool calling statistics tracked
  - `tools_called`: List of tool names used
  - `tool_iterations`: Number of tool call loops
  - `tool_execution_time_ms`: Time spent in tool execution
  - `tool_errors`: List of tool call errors

- **Aggregated Stats**: Summary across time periods
  - `total_tool_calls`: Total number of tool calls
  - `unique_tools_called`: Set of unique tools used
  - `avg_tool_iterations`: Average loops per request
  - `tool_error_count`: Total tool call failures

### UI/UX

- **Options Flow**: New Tool Calling section with:
  - Enable/disable toggle
  - Domain selection
  - Iteration and rate limit sliders
  - Parallel execution checkbox

- **Translations**: English and Italian translations for all tool calling options

### Security

- **Multi-Layer Protection**:
  1. Domain whitelist validation
  2. Service blacklist (dangerous services blocked)
  3. Entity validation (must exist and be exposed)
  4. Rate limiting (prevents abuse)
  5. Iteration limits (prevents infinite loops)

### Testing

- **Comprehensive Test Suite**: `tests/test_tools.py`
  - Schema builder tests
  - Function executor validation tests
  - Rate limiting tests
  - Security tests (blacklist, whitelist)
  - Tool manager caching tests

### Documentation

- **README**: New Tool Calling section with:
  - How it works
  - Configuration guide
  - Security features
  - Examples (basic, multi-step, context-aware)
  - Monitoring and troubleshooting
  - Best practices
  - Comparison with Extended OpenAI Conversation

### Bug Fixes

- Fixed track_callback not being passed through tool loop
- Fixed tool_calls extraction from SSE delta events
- Fixed metrics not including tool call data

### Breaking Changes

- None - Tool calling is opt-in and backward compatible

### Upgrade Guide

1. Update to 0.6.0
2. Tool calling is **enabled by default** - to disable:
   - Go to Settings → Devices & Services → Azure OpenAI SDK Conversation
   - Click Configure
   - Disable "Enable Tool Calling"
3. Review allowed domains whitelist (default is safe)
4. Test with simple commands first: "Turn on the lights"
5. Monitor statistics for tool call usage

### Known Limitations

- **Responses API**: Limited tool calling support on reasoning models (o1, o3)
  - Falls back to regular completion if tools not supported
  - Full support expected in future API versions

- **Entity Exposure**: Entities must be exposed to conversation
  - Configure in Settings → Voice Assistants → Expose

- **Service Schemas**: Some complex services may not be fully supported
  - File a bug report if you encounter issues

### Performance Impact

- **Minimal Overhead**: Tool schema built once and cached
- **First Request**: +100-200ms (schema building)
- **Subsequent Requests**: +0-50ms (cache hit)
- **Tool Execution**: Depends on service (typically 50-200ms per call)

### Migration from Extended OpenAI Conversation

If migrating from Extended OpenAI Conversation:

1. Tool calling is automatically enabled
2. Default whitelist may differ - review and adjust
3. Some advanced features may differ - check documentation
4. Statistics format is different but more detailed

### Acknowledgments

This implementation is inspired by [Extended OpenAI Conversation](https://github.com/jekalmin/extended_openai_conversation) by @jekalmin. Thank you for pioneering this approach!

## 0.5.1 - November 2025

### Housekeeping
- **Linting**: Fixed various linting errors reported by `ruff`, including undefined names, unused variables, and incorrect import locations.

## 0.5.0 - November 2025

### Features
- **Global Statistics Configuration**: Added the ability to enable/disable statistics globally for the component via `configuration.yaml`.
- **Per-Instance Statistics Override**: Added a per-instance override setting in the UI to force-enable or force-disable statistics, overriding the global setting.
- **"Wait Indefinitely" for Early Wait**: Changed the "early wait" prompt to allow a user to wait indefinitely for a response by replying with any non-numeric text. The agent will now wait for the background task to complete and deliver the response in the chat.
- **Persistent Notifications for Responses**: Implemented persistent notifications to deliver responses from backgrounded "early wait" tasks, ensuring the user receives the response even if they don't interact with the chat.

### Bug Fixes
- **Timeout Configuration**: Fixed an `httpx.ReadTimeout` error by adding specific exception handling and making the API timeout configurable in the UI.
- **Early Wait Race Condition**: Fixed a race condition where the "early wait" continuation prompt would fail if the background task finished at the wrong time.
- **Early Wait Trigger**: Fixed a bug where the "early wait" feature would not trigger correctly due to initial whitespace from the language model.
- **Notification Crash**: Fixed an `AttributeError` that caused the component to crash when attempting to create a persistent notification.

## 0.4 - October 2025
### Higlights
- use MCP server
┌─────────────────┐      ┌──────────────┐      ┌─────────────────┐
│  Home Assistant │◄────►│  MCP Server  │◄────►│  Azure OpenAI   │
│   (conversation)│      │  (stateful)  │      │   (stateless)   │
└─────────────────┘      └──────────────┘      └─────────────────┘
                               │
                               ▼
                         ┌──────────┐
                         │  State   │
                         │  Cache   │
                         └──────────┘  
## 0.3.2 – September 2025  
Compatible with Home Assistant ≥ 2025.3  
  
### Highlights  
- only exposed entity are passed to the model
- if no response arrives in 5 seconds, ask user seconds to wait or stop
- add vocabulary to group similar prompts
- configuration in config flow and option flow of previous points
- Added Azure OpenAI conversation integration:
  - New AzureOpenAIConversationAgent with advanced Responses API and Chat Completions handling.
  - SSE streaming support for Responses and Chat with multi-format parsing and fallbacks.
  - Non-streaming Responses fallback implemented.
  - Dynamic token parameter selection (max_tokens / max_completion_tokens / max_output_tokens) based on api-version and model.
  - Enhanced logging options for request/response payloads, system message, and SSE debug sampling.
  - System message templating using Home Assistant Jinja templates with a regex fallback for azure.* variables.
  - Collection of Home Assistant exposed entities (name, state, area) to provide contextual information to the model.
  - Optional Web Search (Bing) integration to include search results as model context.
  - Backwards-compatible configuration mapping (api_base, chat_model, enable_web_search, legacy keys).
  - New SSE debug options and intelligent API-version/parameter retry logic.

- Minor fixes and hardening:
  - Robust JSON parsing for streaming and non-streaming responses.
  - Timeouts and type coercions for configuration parameters.
  - Automatic fallback from Responses to Chat Completions when no text is produced.

## 0.3.1 – September 2025  
Compatible with Home Assistant ≥ 2025.3  
  
### Highlights  
- Logging options are now applied immediately: the integration automatically reloads when saving Options (no manual reload or HA restart needed).  
- Smarter token-parameter selection for Chat Completions with newest models (gpt-5, gpt-4.1, gpt-4.2), avoiding the initial 400 error.  
  
### Added  
- Informative setup log line that summarizes current logging configuration: level, payload flags, truncation limits, and SSE debug.  
  
### Changed  
- Options flow and config flow compute and persist `token_param` based on model and API-version:  
  - gpt-5 / gpt-4.1 / gpt-4.2 → `max_completion_tokens`  
  - otherwise → version-based rule (>= 2025-03 → `max_completion_tokens`, older → `max_tokens`)  
- Payload logging controls (request/response/system) are respected without restart thanks to the automatic entry-reload on options save.  
- Minor: improved Azure endpoint normalization (canonical scheme://host[:port]).  
  
### Fixed / Improved  
- Chat Completions for gpt-5 no longer attempts `max_tokens` first; it uses `max_completion_tokens` immediately (still keeps a fallback if the server insists on the other one).  
- Clearer debug/trace logs when SSE is enabled and when retries switch API-version or token parameter.  
  
### Breaking Changes  
- None in this release.  
  
### Upgrade Guide  
1. Update to 0.3.1.  
2. Save your Options once; changes to logging and other flags apply immediately (the entry reloads automatically).  
3. If you use gpt-5/gpt-4.1/gpt-4.2, no extra steps are required; token handling is automatic.  
  
## 0.3.0 – March 2025  
Compatible with Home Assistant ≥ 2025.3  
  
### Highlights  
- First release that targets the new Azure “Responses” API and introduces a brand-new conversation agent.  
- Major clean-up of defaults and option names (→ see Breaking Changes).  
  
### Added  
- Responses API support  
  - SSE streaming with internal delta re-assembly.  
  - Automatic fall-back to non-stream Responses, then to Chat Completions.  
  - New option `force_responses_mode` (auto / responses / chat).  
- Web Search integration (optional)  
  - Built-in Bing client (`WebSearchClient`).  
  - New options: `enable_web_search`, `bing_api_key`, `bing_endpoint`, `bing_max_results` and location parameters.  
- Template-driven system message  
  - Full Jinja support with variables `azure` (endpoint, deployment, api-version, …) and `exposed_entities` (entities + area).  
  - Regex fall-back if Jinja is unavailable or fails.  
- Debugging & diagnostics  
  - `debug_sse`, `debug_sse_lines` – log first N SSE frames.  
  - `AzureOpenAILogger` now masks secrets automatically.  
- Configurable timeout (`api_timeout`) for every outbound call.  
- Dynamic API-version manager  
  - Default bumped to `2025-03-01-preview`.  
  - Picks the right token-parameter (`max_output_tokens`, `max_completion_tokens`, `max_tokens`) on the fly.  
- Service layer rewrite  
  - `generate_content` and `generate_image` now use plain HTTP/JSON (no `openai.types.*` dependency).  
  - Support for inline images & PDF via Data-URI.  
  
### Changed  
- New conversation class `AzureOpenAIConversationAgent` (old `AzureOpenAIConversationEntity` removed).  
- Recommended defaults updated:  
  - `RECOMMENDED_CHAT_MODEL`: `"o1"` (was `"gpt-4o-mini"`)  
  - `RECOMMENDED_MAX_TOKENS`: `300` (was `1500`)  
- Constants reorganised; immutable `UNSUPPORTED_MODELS`.  
- Capability cache doubled to 64 entries (TTL 4 h).  
- Config-flow default `api_version` set to `2025-03-01-preview`.  
  
### Fixed / Improved  
- Smarter retry logic: switches api-version or token-parameter automatically on HTTP 400.  
- Safer file handling in `generate_content`: explicit allow-list check, MIME detection.  
- More robust system-message rendering with identity block injection if placeholders remain.  
  
### Breaking Changes  
- Agent API – custom overrides must migrate to `AbstractConversationAgent`.  
- Web-search keys renamed / expanded    
  Old: `web_search`, `user_location`, `search_context_size`, …    
  New: `enable_web_search`, `web_search_user_location`, `web_search_context_size`, `web_search_city`, `web_search_region`, `web_search_country`, `web_search_timezone`.  
- Service output – `generate_content` always returns `{ "text": "<output>" }`.  
- Defaults – new recommended model (“o1”) and lower default token budget.  
- Removed reliance on `openai.types.*` – if you imported those classes downstream, update your code.  
  
### Upgrade Guide  
1. Update the component and reload the integration.  
2. Review your options: pick the desired model, timeout and new Web-search settings.  
3. Update automations or scripts that read the old service response schema.  
4. If you extended/overrode the previous entity-based agent, port your code to the new agent class.  
5. Enjoy the new release!
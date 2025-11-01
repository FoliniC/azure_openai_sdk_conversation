# CHANGELOG – Azure OpenAI SDK Conversation  
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
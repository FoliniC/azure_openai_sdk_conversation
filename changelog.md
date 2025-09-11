CHANGELOG – Azure OpenAI SDK Conversation
Release: 0.3.0 - March 2025
Compatible with Home Assistant ≥ 2025.3

Highlights
• First release that targets the new Azure “Responses” API and introduces a brand-new conversation agent.
• Major clean-up of defaults and option names (→ see Breaking Changes).

Added
Responses API support
• SSE streaming with internal delta re-assembly.
• Automatic fall-back to non-stream Responses, then to Chat Completions.
• New option force_responses_mode (auto / responses / chat).

Web Search integration (optional)
• Built-in Bing client (WebSearchClient).
• New options: enable_web_search, bing_api_key, bing_endpoint, bing_max_results and location parameters.

Template-driven system message
• Full Jinja support with variables azure (endpoint, deployment, api-version, …) and exposed_entities (entities + area).
• Regex fall-back if Jinja is unavailable or fails.

Debugging & diagnostics
• debug_sse, debug_sse_lines – log first N SSE frames.
• AzureOpenAILogger now masks secrets automatically.

Configurable timeout (api_timeout) for every outbound call.

Dynamic API-version manager
• Default bumped to 2025-03-01-preview.
• Picks the right token-parameter (max_output_tokens, max_completion_tokens, max_tokens) on the fly.

Service layer rewrite
• generate_content and generate_image now use plain HTTP/JSON (no openai.types.* dependency).
• Support for inline images & PDF via Data-URI.

Changed
• New conversation class AzureOpenAIConversationAgent (old AzureOpenAIConversationEntity removed).
• Recommended defaults updated:
– RECOMMENDED_CHAT_MODEL: "o1" (was "gpt-4o-mini")
– RECOMMENDED_MAX_TOKENS: 300 (was 1500)
• Constants reorganised; immutable UNSUPPORTED_MODELS.
• Capability cache doubled to 64 entries (TTL 4 h).
• Config-flow default api_version set to 2025-03-01-preview.

Fixed / Improved
• Smarter retry logic: switches api-version or token-parameter automatically on HTTP 400.
• Safer file handling in generate_content: explicit allow-list check, MIME detection.
• More robust system-message rendering with identity block injection if placeholders remain.

Breaking Changes
Agent API – custom overrides must migrate to AbstractConversationAgent.
Web-search keys renamed / expanded
Old: web_search, user_location, search_context_size, …
New: enable_web_search, web_search_user_location, web_search_context_size, web_search_city, web_search_region, web_search_country, web_search_timezone.
Service output – generate_content always returns { "text": "<output>" }.
Defaults – new recommended model (“o1”) and lower default token budget.
Removed reliance on openai.types.* – if you imported those classes downstream, update your code.
Upgrade Guide
Update the component and reload the integration.
Review your options: pick the desired model, timeout and new Web-search settings.
Update automations or scripts that read the old service response schema.
If you extended/overrode the previous entity-based agent, port your code to the new agent class.
Enjoy the new release!

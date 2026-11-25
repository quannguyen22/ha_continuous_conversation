# Continuous Conversation

A local custom Home Assistant conversation agent that delegates to the built-in agent and changes only the continuation flag. Targets Core **2026.9.3**, Glassworks **Aqara S1 Plus 0.9.0**. No LLM, cloud service, Core patch, or firmware change is included.

**Status: implementation with automated tests, pending physical validation. The full acceptance criteria cannot be met by a custom-agent-only integration on unmodified Core 2026.9.3.** Read the pipeline limitation below before installation.

## Installation

Copy `custom_components/continuous_conversation` into `/config/custom_components/continuous_conversation` on Home Assistant. Restart Home Assistant. In Settings → Devices & Services → Add Integration, select **Continuous Conversation**. Configure its options, then select its conversation entity as the agent in the existing **Vietnamese Local** voice assistant. Keep Wyoming Vietnamese Gipformer and NghiTTS unchanged.

Disable **Prefer handling commands locally** in that assistant's configuration so ordinary built-in intents reach this wrapper. This does **not** disable the separate sentence-trigger shortcut described below. Both panels must use the configured assistant.

### Install through HACS

In HACS, open the menu → Custom repositories. Add `https://github.com/quannguyen22/ha_continuous_conversation` with category **Integration**. Find **Continuous Conversation**, download it, and restart Home Assistant. Then add the integration and select its agent as described above.

HACS installs the files; it does not configure the voice assistant or remove the pipeline limitations below.

## Controls

- **Always** (default): successful delegated responses request another listening turn.
- **Off**: delegated responses never request another turn. Stop phrases still receive the configured polite response. Changing mode does not interrupt a microphone already listening; it affects subsequent processing.
- **Question**: preserve the delegate's explicit `continue_conversation` flag. The built-in agent currently returns false, so this mode normally stops. A question mark in speech is not treated as a request for follow-up.

Use the mode select entity or the integration's options dialog. Options persist through Home Assistant restarts. They include a list of termination phrases, a termination response, whether to continue after a recognition miss, and the maximum consecutive failures (1–10, default 2). With maximum 2, the second consecutive miss ends the session. Errors other than `no_intent_match` always stop. The default stops on the first miss.

Stop phrases are matched against the entire normalized utterance: NFC Unicode, case folding, punctuation replaced by spaces, and collapsed whitespace. Accents are retained. “CẢM ƠN NHÉ!” matches; “bật đèn rồi cảm ơn nhé” does not. An empty phrase list disables phrase interception. Empty/punctuation-only phrases and blank responses are rejected.

## Verified architecture and important pipeline limitation

The wrapper is a `ConversationEntity`, discovered through the conversation platform. It explicitly resolves `conversation.HOME_ASSISTANT_AGENT` and calls that agent's `async_process` once with the **original ConversationInput object**. This preserves text, context, language, device/satellite IDs, conversation ID, original agent attribution, and extra prompt. It returns the original result and response object after adjusting `continue_conversation`. It does not reimplement intent recognition or execute automation triggers itself. Built-in matching, custom sentences, intent handling, and automation `set_conversation_response` remain in the built-in code path when delegation is reached.

Core's Assist Pipeline has a shortcut **before** calling a custom agent: sentence-trigger automations are tried first, and local intents are also tried when `prefer_local_intents` is enabled. These shortcut results get a new `ConversationResult` with continuation false. Therefore:

- On a fresh wake-word turn matching a sentence-triggered automation, the automation runs normally, but this agent is never called and listening will not automatically reopen.
- A termination phrase overlapping a sentence trigger can also be consumed by that trigger first.
- Disable local preference to route ordinary intents through the wrapper. Once the wrapper requests continuation, Core sets `_intent_agent_only` for the next turn, bypassing those shortcuts. Existing sentence-trigger automations can then run through the delegated built-in agent and continue normally.
- A practical entry path is a normal built-in command that reaches the wrapper first, then automation commands on subsequent turns. This does not provide unconditional continuation after an automation as the first command.

There is no public custom-agent hook to alter shortcut results. Making all first-turn automations continue would require an upstream Core change to route those results through a supported continuation-policy hook, or a different satellite-side continuation policy. Neither is implemented here: silently patching Core or overriding firmware would violate the requested architecture constraints. No supported alternative satisfying every acceptance criterion was found in the inspected sources.

This wrapper does not provide semantic follow-up understanding. Core owns conversation IDs and history. No global conversation ID is created. Failure counters are keyed by device, satellite, and conversation ID, expire after 5 minutes, and are capped at 256 entries. Pruning happens on requests; unloading releases all state. Concurrent requests update counters synchronously in completion order without sharing a session across panels. Requests with no usable conversation ID never retry failures. Reload resets transient failure counts and keeps persistent options.

## Satellite, silence, and errors

The exact Glassworks release reads `continue_conversation` from `INTENT_END`. After successful TTS playback it sends the playback-finished event, goes idle, and calls `startRun(null)` when continuation is requested. It does not restart after failed playback. A run without TTS returns to idle, even if continuation was requested. Consequently a successful but silent automation response cannot be guaranteed to reopen the microphone; configure an audible response if continuation is needed.

Glassworks returns to idle for pipeline errors while starting, streaming, or awaiting results. Core rejects unsuccessful STT and empty recognized text before calling this integration. The wrapper also stops on empty input when called directly, never synthesizes another pipeline run, and never tries to detect silence.

Listening and silence handling belong to the satellite/audio stream, Assist Pipeline VAD, and STT provider. Pipeline `AudioSettings` contains silence controls, but the Conversation Agent API cannot change them. No listening-timeout option is exposed here. Glassworks' hardcoded 300-second conversation timeout controls conversation-ID reuse, **not** how long the microphone waits for speech. The actual no-speech timing and behavior with Wyoming Gipformer must be measured on your panels; this integration cannot guarantee a silence deadline or recover a stuck upstream stream.

Expected Home Assistant errors produce a short polite Vietnamese error and stop. Unexpected exceptions propagate to Core's pipeline error handling, which ends the run. The integration adds no logging of utterances or responses. Core and Glassworks may log their own conversation content.

## Source investigation

Inspected before implementation:

- [Core 2026.9.3 conversation entity](https://github.com/home-assistant/core/blob/2026.9.3/homeassistant/components/conversation/entity.py): registration via platform, supported languages, `async_process`.
- [Conversation models](https://github.com/home-assistant/core/blob/2026.9.3/homeassistant/components/conversation/models.py): all input fields and mutable continuation result.
- [Agent lookup](https://github.com/home-assistant/core/blob/2026.9.3/homeassistant/components/conversation/agent_manager.py): explicit built-in lookup, input construction, error handling.
- [Built-in agent](https://github.com/home-assistant/core/blob/2026.9.3/homeassistant/components/conversation/default_agent.py): `_async_handle_message`, trigger execution and response conversion, intents, history.
- [Assist Pipeline](https://github.com/home-assistant/core/blob/2026.9.3/homeassistant/components/assist_pipeline/pipeline.py): `prepare_recognize_intent`, `recognize_intent`, STT error handling, continuation propagation and shortcut bypass.
- [ESPHome bridge](https://github.com/home-assistant/core/blob/2026.9.3/homeassistant/components/esphome/assist_satellite.py): maps the flag to `INTENT_END` event data as `"1"`/`"0"`.
- [Glassworks exact Aqara 0.9.0 controller](https://github.com/GlassworksHQ/glassworks/blob/aqara-s1-plus-v0.9.0/libs/voice/src/main/java/dev/glassworks/voice/VoiceAssistantController.kt): event handling, playback completion, restart, errors, ID reuse.

The Glassworks tag is `aqara-s1-plus-v0.9.0`, not `v0.9.0`. Source compatibility is evidence of the intended behavior, not physical hardware verification.

## Tests

Use Python 3.14 (the target Core runtime):

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/python -m pytest -q
```

Tests use real pinned Home Assistant classes with a mocked delegate. They check exact input and response preservation, modes, stop matching, errors, failure limits/reset, session isolation, concurrent devices, expiry/bounds, configuration and platform lifecycle. They do not execute real STT/TTS, real sentence-trigger automations, or a physical panel. See `VALIDATION.md` for the recorded results and remaining acceptance checks.

## Troubleshooting

If the integration is missing, confirm the folder nesting, restart Core, and check startup logs. If the agent is missing, confirm the conversation platform loaded and the entity is enabled. If ordinary commands do not continue, disable local preference and verify the pipeline selects this agent. If only first-turn automation commands stop, this is the documented pipeline shortcut. If no response audio plays, check NghiTTS and the panel's reachability to the audio URL; Glassworks requires successful playback to restart. If listening hangs during silence, inspect the pipeline's STT/VAD diagnostics and Wyoming service; there is no agent-level timeout setting. Avoid sharing pipeline debug recordings containing private speech.

To uninstall, select the built-in Home Assistant agent in each assistant, remove the integration from Devices & Services, remove its custom component directory, and restart Core.

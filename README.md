# Continuous Conversation

A local custom Home Assistant conversation agent that delegates to the built-in agent and changes only the continuation flag. Tested on Core **2026.9.3 and 2026.11.2**, Glassworks **Aqara S1 Plus 0.9.0**. No LLM, cloud service, or firmware change is included. Version 0.1.2 includes a scoped, reversible runtime patch to Assist Pipeline; it does not modify Core files on disk.

**Status: 0.1.3 adds per-phrase replies and silent termination, retaining the first-turn automation routing fix and real Core pipeline/agent/script regression tests. Physical Glassworks validation is still pending.** The runtime compatibility patch uses private Core APIs; read the compatibility section before upgrading Core.

## Installation

Copy `custom_components/continuous_conversation` into `/config/custom_components/continuous_conversation` on Home Assistant. Restart Home Assistant. In Settings → Devices & Services → Add Integration, select **Continuous Conversation**. Configure its options, then select its conversation entity as the agent in the existing **Vietnamese Local** voice assistant. Keep Wyoming Vietnamese Gipformer and NghiTTS unchanged.

Select this agent for both panels. Disabling **Prefer handling commands locally** is recommended for a clear configuration, but the 0.1.1 runtime patch routes both local intents and sentence triggers through the wrapper regardless of that preference.

### Install through HACS

In HACS, open the menu → Custom repositories. Add `https://github.com/quannguyen22/ha_continuous_conversation` with category **Integration**. Find **Continuous Conversation**, download it, and restart Home Assistant. Then add the integration and select its agent as described above.

HACS installs the files; it does not configure the voice assistant or remove the pipeline limitations below.

## Controls

- **Always** (default): successful delegated responses request another listening turn.
- **Off**: delegated responses never request another turn. Stop phrases still receive the configured polite response. Changing mode does not interrupt a microphone already listening; it affects subsequent processing.
- **Question**: preserve the delegate's explicit `continue_conversation` flag. The built-in agent currently returns false, so this mode normally stops. A question mark in speech is not treated as a request for follow-up.

Use the mode select entity or the integration's options dialog. Options persist through Home Assistant restarts. They include a list of termination phrases, a termination response, whether to continue after a recognition miss, and the maximum consecutive failures (1–10, default 2). With maximum 2, the second consecutive miss ends the session. Errors other than `no_intent_match` always stop. The default stops on the first miss.

### Per-phrase replies and silent termination (0.1.3)

In Devices & Services → Continuous Conversation → Configure, open **Per-phrase termination responses** and add an item for each phrase. Each item has a **Termination phrase**, optional **Response**, and **End silently** toggle.

| Phrase | Response | End silently |
| --- | --- | --- |
| cảm ơn | Rất vui được giúp bạn. | Off |
| tạm biệt | Hẹn gặp lại bạn nhé. | Off |
| thôi | (empty) | On |

A rule phrase works even if it is absent from the shared termination list. A rule overrides that phrase's shared response. An empty or whitespace-only response is silent too; **End silently** takes precedence over any entered response. All these outcomes end the conversation and are never forwarded to the built-in agent. Two rules with the same normalized phrase are rejected.

The existing shared phrase list and response are preserved on upgrade and remain the fallback for phrases without a rule. No migration or reconfiguration is required. Removing a rule restores the shared behavior if its phrase is in the shared list; otherwise the phrase stops being a termination command.

Silent termination returns no speech payload and sets `continue_conversation` to false. The real Core pipeline skips TTS; Glassworks returns to idle when that run ends. It still waits for STT to recognize the phrase: this feature does not shorten VAD or transcription time for a short word such as “thôi”. Physical idle behavior remains to be verified on the panel.

Stop phrases are matched against the entire normalized utterance: NFC Unicode, case folding, punctuation replaced by spaces, and collapsed whitespace. Accents are retained. “CẢM ƠN NHÉ!” matches; “bật đèn rồi cảm ơn nhé” does not. An empty phrase list disables phrase interception. Empty/punctuation-only phrases and blank shared responses are rejected. Per-phrase responses may be empty for silent termination.

## Architecture and runtime compatibility

The wrapper is a `ConversationEntity`, discovered through the conversation platform. It explicitly resolves `conversation.HOME_ASSISTANT_AGENT` and calls that agent's `async_process` once with the **original ConversationInput object**. This preserves text, context, language, device/satellite IDs, conversation ID, original agent attribution, and extra prompt. It returns the original result and response object after adjusting `continue_conversation`. Built-in matching, custom sentences, intent handling, and automation `set_conversation_response` stay in the built-in code path.

Core 2026.9.3 tries sentence-trigger automations before calling custom agents. Version 0.1.0 therefore could not continue after first-turn automation commands, even with local preference disabled. This was confirmed in the user's live pipeline trace for “chất lượng không khí”: `processed_locally: true`, `continue_conversation: false`.

### Fix in 0.1.1 and 0.1.2

The integration wraps the actual intent processor in memory: `PipelineRun.recognize_intent` on 2026.9.3, or `_DefaultPipelineProcessor.recognize_intent` in `assist_pipeline.default_pipeline` on the refactored 2026.11.2. Version 0.1.1 assumed the old layout and failed to load on 2026.11.2; use 0.1.2 or later. Immediately before the original method runs, it sets that **individual run's** `_intent_agent_only` flag, only when the resolved agent is an active Continuous Conversation entity belonging to this integration entry and HA instance. This is the same flag Core uses for agent-only follow-up turns. The original pipeline then delegates to the wrapper instead of consuming the sentence trigger early. The built-in delegate still recognizes and executes the automation once, and its final result passes through the configured continuation policy. A stop phrase also reaches this policy before a matching automation can consume it.

The previous per-run flag is restored in `finally`, including cancellation/errors. Other agents and HA instances retain their original routing. Renaming the conversation entity does not break selection. Unloading the final entry restores the original method when the integration still owns the method slot; if another integration wrapped it later, that wrapper is left intact and this integration's retained wrapper becomes inert. Setup failure also releases the patch; failed unload retains it with the still-loaded entry.

**This is an explicit runtime monkey-patch, approved as an exception to the original no-monkey-patch requirement.** No Core file or automation is edited. The patch is installed automatically on startup/reload, so there is no manual Core patch to reapply after an upgrade. However, future Core compatibility is not guaranteed: this version is tested against **2026.9.3 and 2026.11.2**. Setup checks the method signature and the presence of the expected routing hooks; incompatible shapes and pre-existing wrappers are rejected with a configuration error. These structural checks cannot detect every semantic change in future Core releases. Update this integration if Core changes its pipeline internals.

Only the integration files need updating through HACS. After upgrading to 0.1.2, restart Home Assistant so Python loads the new compatibility module. To roll back, install 0.1.0 and restart, accepting its first-turn automation limitation; removing the integration also releases the runtime patch.

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
- [Core 2026.11.2 processor](https://github.com/home-assistant/core/blob/2026.11.2/homeassistant/components/assist_pipeline/default_pipeline.py) and [run controller](https://github.com/home-assistant/core/blob/2026.11.2/homeassistant/components/assist_pipeline/run.py): refactored intent processing used by 0.1.2.
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

For Core 2026.11.2, use `requirements_test_2026_11.txt` instead. The CI matrix tests both layouts, including actual integration setup/unload.

Tests use real pinned Home Assistant classes with a mocked delegate. They check exact input and response preservation, modes, stop matching, errors, failure limits/reset, session isolation, concurrent devices, expiry/bounds, configuration and platform lifecycle. Additional regression tests run the real Core pipeline, default agent sentence matching, registered trigger callback and a real script containing `set_conversation_response`. They verify one execution per request, mode policy, overlapping stop phrases, renamed agents, two concurrent panels, patch cleanup, cancellation and compatibility rejection. They do not execute real STT/TTS or a physical panel. See `VALIDATION.md` for the recorded results and remaining acceptance checks.

## Troubleshooting

If the integration is missing, confirm the folder nesting, restart Core, and check startup logs. If the agent is missing, confirm the conversation platform loaded and the entity is enabled. If ordinary commands do not continue, disable local preference and verify the pipeline selects this agent. If first-turn automation commands stop, verify version 0.1.2 is installed, restart HA, and inspect integration setup errors and the pipeline trace. With this agent selected, successful automation results should now have `continue_conversation: true` in Always mode. If no response audio plays, check NghiTTS and the panel's reachability to the audio URL; Glassworks requires successful playback to restart. If listening hangs during silence, inspect the pipeline's STT/VAD diagnostics and Wyoming service; there is no agent-level timeout setting. Avoid sharing pipeline debug recordings containing private speech.

To uninstall, select the built-in Home Assistant agent in each assistant, remove the integration from Devices & Services, remove its custom component directory, and restart Core.

## Release numbering

Published versions use matching manifest versions and Git tags (`0.1.3` / `v0.1.3`). The release workflow publishes a GitHub Release with that version and its changelog notes when a version tag is pushed. HACS can then display release versions instead of branch commit hashes. Installing from a development branch may still show a commit hash.

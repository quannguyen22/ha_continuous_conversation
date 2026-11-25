# Validation record

## Automated

Executed in isolated virtual environments using Python 3.14.4, the real Core 2026.9.3 and 2026.11.2 packages, and each conversation integration's pinned dependencies.

Commands: `/tmp/cc-test-env/bin/python -m pytest -q` and `/tmp/cc-test-2026-11/bin/python -m pytest -q`.

Version **0.1.2** result: **36 passed on Core 2026.9.3** and **36 passed on Core 2026.11.2**, in separate Python 3.14 virtual environments. Five upstream aiohttp/backoff deprecation warnings. Ruff, Python compilation and JSON validation also pass.

The original unit tests mock delegate calls and config-entry lifecycle operations. Regression tests execute the real Core 2026.9.3 and 2026.11.2 `PipelineRun.recognize_intent`, built-in `DefaultAgent`, Hassil sentence recognition, a registered trigger callback, and a real HA `Script` with `set_conversation_response` and sensor-template rendering. Entity-component lookup is supplied by a small test registry. Tests verify first-turn continuation with local preference both on and off, exact single execution, input/context/satellite/session preservation, all modes, stop-phrase precedence, cancellation restoration, concurrent panels, scope to the registered HA instance, ownership cleanup, setup/unload failures and incompatible API rejection. The baseline test also confirms the unpatched Core shortcut reproduces the failure.

These are integration-level software tests, not physical STT/TTS or microphone tests.

## Live failure diagnosed before 0.1.2

The actual user instance reports Core **2026.11.2**, newer than the initial request's 2026.9.3. Version 0.1.1 failed at entry setup with `AttributeError: type object 'PipelineRun' has no attribute 'recognize_intent'`; the entity was unavailable before any conversation could start. Core 2026.11.2 moved intent processing to `_DefaultPipelineProcessor` in `assist_pipeline.default_pipeline`.

Version 0.1.2 detects both source layouts. Tests now include real integration setup/unload on both versions and explicit rejection of a missing processor method without an unhandled `AttributeError`. CI runs the same matrix. The live instance needs to load the fixed version before runtime or physical validation can be claimed.

## Acceptance status

| Requirement | Evidence / remaining work |
| --- | --- |
| UI installation and configuration | Version 0.1.0 was installed successfully on the user instance. Updated flow/schema tests pass; live 0.1.2 loading pending. |
| Selectable agent | User instance confirmed Vietnamese Local selects this agent. Live 0.1.2 upgrade pending. |
| Existing sentence automations and response text | Real Core pipeline/default agent/trigger/script tests preserve response and execute once. First-turn bypass fixed by scoped runtime patch. Live panel automation retest pending. |
| Always mode microphone reopening | Exact Glassworks 0.9.0 source supports flag after successful TTS. Physical playback/listening pending. |
| Consecutive commands | Policy tested. Physical multiple-turn test pending. |
| Termination | Exact-match, normalization and false continuation tested. Stop phrase takes precedence over a matching automation in the patched pipeline test. Physical idle transition pending. |
| Silence/STT timeout | Upstream source reviewed. No agent timeout API. Actual Gipformer silence behavior pending measurement. |
| Off | Flag override and persistence write tested. Physical wake-word return pending. |
| Two panels | Concurrent pipeline runs through the patched real default agent and independent failure bookkeeping tested. Simultaneous hardware sessions pending. |
| Persistence | Config-entry options used and write tested. Actual restart persistence pending. |

## Physical test procedure

1. Install on Core 2026.9.3, select the new agent in Vietnamese Local, disable local preference, and leave STT/TTS unchanged.
2. On each panel, wake and issue an ordinary built-in command with an audible response. Verify the microphone opens only after playback. Issue at least three further commands.
3. During that continuation, invoke existing sentence-triggered automations and verify their exact `set_conversation_response` output and subsequent listening.
4. Start a fresh wake-word session with “chất lượng không khí”. Expect its original automation response followed by listening. Inspect pipeline debug: `continue_conversation` should be true in Always mode. This failed in 0.1.0 and is the primary automation regression check.
5. Try each configured termination phrase and a longer unrelated command containing one. Verify idle for exact matches and normal processing for embedded phrases.
6. Repeat with Off and Question modes. Do not infer explicit follow-up intent from a question mark.
7. Leave a reopened microphone silent. Measure the time until idle. Also test empty STT, STT failure, TTS failure, and network interruption. Confirm errors do not trigger an automatic retry loop. A hung upstream stream is outside the wrapper's control.
8. Enable recognition-miss continuation with maximum 2; verify the second consecutive miss ends listening. Verify a successful command resets the count.
9. Run both panels simultaneously with distinct commands, stop only one, and verify the other continues.
10. Restart Home Assistant; verify options and mode persist and both panels still use the correct pipeline.

Development inspected the user instance read-only. No physical Home Assistant configuration or panel firmware was changed; the 0.1.2 runtime patch is not active on that instance until the integration is updated and HA restarted.

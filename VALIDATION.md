# Validation record

## Automated

Executed in an isolated virtual environment using Python 3.14.4, the real `homeassistant==2026.9.3` package and its conversation integration's pinned dependencies.

Command: `/tmp/cc-test-env/bin/python -m pytest -q`

Result: **17 passed**. One upstream aiohttp application inheritance deprecation warning. Delegate calls and config-entry lifecycle operations are mocked; real input/result/response types, configuration-flow APIs, selectors and schemas are exercised. These are component tests, not a full Home Assistant installation or physical end-to-end test.

## Acceptance status

| Requirement | Evidence / remaining work |
| --- | --- |
| UI installation and configuration | Files, schemas and flow creation tested. Full Devices & Services installation pending. |
| Selectable agent | Conversation entity platform implemented against 2026.9.3; live pipeline selection pending. |
| Existing sentence automations and response text | Delegation preserves original input/result, source confirms built-in path. Real automation execution pending. First-turn shortcut cannot be modified by wrapper. |
| Always mode microphone reopening | Exact Glassworks 0.9.0 source supports flag after successful TTS. Physical playback/listening pending. |
| Consecutive commands | Policy tested. Physical multiple-turn test pending. |
| Termination | Exact-match, normalization and false continuation tested. Physical idle transition pending; shortcut overlap caveat applies. |
| Silence/STT timeout | Upstream source reviewed. No agent timeout API. Actual Gipformer silence behavior pending measurement. |
| Off | Flag override and persistence write tested. Physical wake-word return pending. |
| Two panels | Concurrent independent failure bookkeeping tested. Simultaneous hardware sessions pending. |
| Persistence | Config-entry options used and write tested. Actual restart persistence pending. |

## Physical test procedure

1. Install on Core 2026.9.3, select the new agent in Vietnamese Local, disable local preference, and leave STT/TTS unchanged.
2. On each panel, wake and issue an ordinary built-in command with an audible response. Verify the microphone opens only after playback. Issue at least three further commands.
3. During that continuation, invoke existing sentence-triggered automations and verify their exact `set_conversation_response` output and subsequent listening.
4. Start a fresh wake-word session with a sentence-trigger automation. Expect its normal response followed by idle because of the documented Core shortcut; record this as an unmet acceptance criterion.
5. Try each configured termination phrase and a longer unrelated command containing one. Verify idle for exact matches and normal processing for embedded phrases.
6. Repeat with Off and Question modes. Do not infer explicit follow-up intent from a question mark.
7. Leave a reopened microphone silent. Measure the time until idle. Also test empty STT, STT failure, TTS failure, and network interruption. Confirm errors do not trigger an automatic retry loop. A hung upstream stream is outside the wrapper's control.
8. Enable recognition-miss continuation with maximum 2; verify the second consecutive miss ends listening. Verify a successful command resets the count.
9. Run both panels simultaneously with distinct commands, stop only one, and verify the other continues.
10. Restart Home Assistant; verify options and mode persist and both panels still use the correct pipeline.

No physical Home Assistant configuration or panel firmware was changed during development.

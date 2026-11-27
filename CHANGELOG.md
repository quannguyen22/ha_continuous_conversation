# Changelog

## 0.1.4

- Add a local, configurable workaround for STT repeating the leading Vietnamese “chế độ” prefix, applying to all mode names without per-automation edits. Enabled by default; can be disabled in options.
- Collapse only adjacent leading copies with a following target. Preserve unrelated text and the original caller input/context.
- Repair pipeline text before its chat log opens, preserving one user message and one trigger execution. Raw STT diagnostics remain unchanged.
- Add regression tests for prefix scope, Unicode, disabled behavior, input preservation, legacy options and real pipeline automation matching. Extend CI to Core 2026.11.3.

## 0.1.3

- Add UI-editable per-phrase termination rules with individual responses and a silent toggle. Empty rule responses also end silently.
- Preserve existing shared phrases and personalized response as the fallback; per-phrase rules take precedence and can define new phrases.
- Reject ambiguous duplicate normalized rule phrases and malformed entries.
- Verify real pipeline stage advancement skips TTS entirely for silent termination on both supported Core versions.

## 0.1.2

- Fix integration setup failing on Core 2026.11.2: intent processing moved from `PipelineRun` into `_DefaultPipelineProcessor` in `assist_pipeline.default_pipeline`.
- Detect the actual processor layout and scope routing through its host HA instance. Preserve 2026.9.3 compatibility.
- Report a clear configuration error if the processor method is missing, instead of raising `AttributeError`.
- Test real entry setup/unload and the complete routing suite on both Core versions; add a CI matrix.

## 0.1.1

- Fix first-turn conversation-triggered automation responses ending continuous conversation by routing them through the wrapper before applying continuation policy.
- Add a scoped and reversible in-memory Assist Pipeline compatibility patch. No Core file edits are required; the patch installs on integration setup and releases on unload.
- Reject incompatible method signatures or unknown shortcut implementations at setup. Tested on Core 2026.9.3; future Core releases may require an integration update.
- Preserve original automation response and run each trigger once; ensure stop phrases reach the policy even if an automation uses the same sentence.
- Add real-Core pipeline, sentence matching and script-response regression tests, concurrent-device checks, cancellation, setup/unload cleanup and patch ownership coverage.

## 0.1.0

- Initial local conversation-agent wrapper, UI options, persistent mode select, Vietnamese termination phrases and bounded per-session failure policy.
- Known limitation: Core's first-turn sentence-trigger shortcut bypassed the agent and stopped continuation.

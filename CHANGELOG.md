# Changelog

## 0.1.1

- Fix first-turn conversation-triggered automation responses ending continuous conversation by routing them through the wrapper before applying continuation policy.
- Add a scoped and reversible in-memory Assist Pipeline compatibility patch. No Core file edits are required; the patch installs on integration setup and releases on unload.
- Reject incompatible method signatures or unknown shortcut implementations at setup. Tested on Core 2026.9.3; future Core releases may require an integration update.
- Preserve original automation response and run each trigger once; ensure stop phrases reach the policy even if an automation uses the same sentence.
- Add real-Core pipeline, sentence matching and script-response regression tests, concurrent-device checks, cancellation, setup/unload cleanup and patch ownership coverage.

## 0.1.0

- Initial local conversation-agent wrapper, UI options, persistent mode select, Vietnamese termination phrases and bounded per-session failure policy.
- Known limitation: Core's first-turn sentence-trigger shortcut bypassed the agent and stopped continuation.

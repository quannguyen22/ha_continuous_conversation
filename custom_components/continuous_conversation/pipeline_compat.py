"""Reversible, scoped compatibility patch for Core's sentence-trigger shortcut.

This uses private Assist Pipeline APIs. It does not modify Core files on disk.
Keep the real-Core routing tests when changing this module or supporting new APIs.
"""

import inspect
from collections.abc import Callable
from functools import wraps
from importlib import import_module
from typing import Any

from homeassistant.components import conversation
from homeassistant.components.assist_pipeline.pipeline import PipelineRun
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError

from .conversation import ContinuousConversation

# Each wrapper owns its registrations. A wrapper retained by another integration
# after unload remains inert rather than overwriting that integration's patch.
_active_patch: (
    tuple[type, Callable[..., Any], Callable[..., Any], dict[HomeAssistant, set[str]]]
    | None
) = None


def _get_pipeline_type() -> type:
    """Find the actual intent processor across the Core pipeline refactor."""
    if callable(getattr(PipelineRun, "recognize_intent", None)):
        return PipelineRun
    try:
        module = import_module(
            "homeassistant.components.assist_pipeline.default_pipeline"
        )
        processor = getattr(module, "_DefaultPipelineProcessor", None)
    except ModuleNotFoundError:
        processor = None
    if processor is None or not callable(getattr(processor, "recognize_intent", None)):
        raise ConfigEntryError(
            "Continuous Conversation cannot find a compatible Assist intent processor. "
            "Update the integration for this Core version. No Core files have been changed."
        )
    return processor


def _check_compatible(method: Callable[..., Any], target: type) -> None:
    """Reject unknown call shapes or shortcut implementations before patching."""
    expected = (
        "self",
        "intent_input",
        "conversation_id",
        "conversation_extra_system_prompt",
    )
    if (
        not inspect.iscoroutinefunction(method)
        or method.__module__ != target.__module__
        or method.__qualname__ != f"{target.__qualname__}.recognize_intent"
        or hasattr(method, "__wrapped__")
        or tuple(inspect.signature(method).parameters) != expected
        or not {
            "_intent_agent_only",
            "async_handle_sentence_triggers",
            "async_converse",
        }.issubset(method.__code__.co_names)
    ):
        raise ConfigEntryError(
            "Continuous Conversation cannot safely patch this Assist Pipeline API. "
            "Update the integration for this Core version or remove the conflicting "
            "pipeline patch. No Core files have been changed."
        )


@callback
def install_pipeline_compat(hass: HomeAssistant, entry_id: str) -> Callable[[], None]:
    """Install once, register this entry and return its idempotent release callback."""
    global _active_patch
    if _active_patch is None:
        target = _get_pipeline_type()
        original = target.recognize_intent
        _check_compatible(original, target)
        owners: dict[HomeAssistant, set[str]] = {}

        @wraps(original)
        async def recognize_intent(
            self: Any,
            intent_input: str,
            conversation_id: str,
            conversation_extra_system_prompt: str | None,
        ) -> tuple[str, bool]:
            # Resolve the actual entity, never its name or an assumed entity_id.
            # Other HA instances, agents and disabled/unloaded entries are untouched.
            host = self.host if target is not PipelineRun else self
            owned_entries = owners.get(host.hass)
            agent = (
                conversation.async_get_agent(host.hass, self.intent_agent.id)
                if owned_entries and self.intent_agent is not None
                else None
            )
            if not (
                owned_entries
                and isinstance(agent, ContinuousConversation)
                and agent.entry.entry_id in owned_entries
            ):
                return await original(
                    self,
                    intent_input,
                    conversation_id,
                    conversation_extra_system_prompt,
                )

            had_override = "_intent_agent_only" in vars(self)
            previous = self._intent_agent_only
            self._intent_agent_only = True
            try:
                # Repair before the pipeline opens its chat log, so it records one
                # user message. The raw STT event remains available for diagnostics.
                intent_input = agent.prepare_input_text(intent_input)
                # The delegate handles triggers exactly once. Its final result then
                # passes through the normal mode/termination/error policy.
                return await original(
                    self,
                    intent_input,
                    conversation_id,
                    conversation_extra_system_prompt,
                )
            finally:
                if had_override:
                    self._intent_agent_only = previous
                else:
                    del self._intent_agent_only

        target.recognize_intent = recognize_intent
        _active_patch = (target, original, recognize_intent, owners)

    target, original, wrapper, owners = _active_patch
    owners.setdefault(hass, set()).add(entry_id)
    released = False

    @callback
    def release() -> None:
        """Release ownership; restore only when nobody else replaced our wrapper."""
        nonlocal released
        global _active_patch
        if released:
            return
        released = True
        if entries := owners.get(hass):
            entries.discard(entry_id)
            if not entries:
                owners.pop(hass)
        if not owners:
            if target.recognize_intent is wrapper:
                target.recognize_intent = original
            _active_patch = None

    return release

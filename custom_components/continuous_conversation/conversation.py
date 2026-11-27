"""Delegate locally to Home Assistant and apply continuation policy."""

from dataclasses import replace
from typing import Literal

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULTS
from .policy import FailureTracker, normalize, repair_mode_prefix


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Expose a selectable conversation entity."""
    async_add_entities([ContinuousConversation(entry)])


class ContinuousConversation(conversation.ConversationEntity):
    """Wrap the built-in agent with configurable text repair and continuation policy."""

    _attr_has_entity_name = True
    _attr_name = "Continuous Conversation"
    _attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    def __init__(self, entry: ConfigEntry) -> None:
        self.entry = entry
        self._attr_unique_id = entry.entry_id
        self.failures = FailureTracker()

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Advertise only languages supported by the delegate."""
        agent = conversation.async_get_agent(
            self.hass, conversation.HOME_ASSISTANT_AGENT
        )
        return agent.supported_languages if agent is not None else []

    async def async_prepare(self, language: str | None = None) -> None:
        """Prepare the built-in recognizer."""
        agent = conversation.async_get_agent(
            self.hass, conversation.HOME_ASSISTANT_AGENT
        )
        if agent is not None:
            await agent.async_prepare(language)

    def prepare_input_text(self, text: str) -> str:
        """Apply the configured narrow repair, leaving other utterances untouched."""
        if self.entry.options.get(
            "repair_repeated_mode_prefix", DEFAULTS["repair_repeated_mode_prefix"]
        ):
            return repair_mode_prefix(text)
        return text

    def _reply(
        self, user_input: conversation.ConversationInput, text: str, error: bool = False
    ) -> conversation.ConversationResult:
        response = intent.IntentResponse(language=user_input.language)
        if error:
            response.async_set_error(intent.IntentResponseErrorCode.UNKNOWN, text)
        elif text.strip():
            # No speech payload means the pipeline skips TTS and ends the run.
            response.async_set_speech(text)
        return conversation.ConversationResult(
            response, user_input.conversation_id, False
        )

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Delegate once; copy only repaired input and preserve all other fields."""
        prepared_text = self.prepare_input_text(user_input.text)
        if prepared_text != user_input.text:
            user_input = replace(user_input, text=prepared_text)
        options = DEFAULTS | self.entry.options
        self.failures.prune()
        text = normalize(user_input.text)
        key = (
            user_input.device_id,
            user_input.satellite_id,
            user_input.conversation_id or "",
        )
        if not text:
            self.failures.clear(key)
            return self._reply(
                user_input, "Tôi chưa nghe rõ. Bạn có thể gọi lại khi cần nhé."
            )
        for rule in options["termination_rules"]:
            if text == normalize(rule["phrase"]):
                self.failures.clear(key)
                response = (
                    ""
                    if rule.get("silent", False)
                    else rule.get("response", "").strip()
                )
                return self._reply(user_input, response)
        if text in {normalize(phrase) for phrase in options["termination_phrases"]}:
            self.failures.clear(key)
            return self._reply(user_input, options["termination_response"])

        agent = conversation.async_get_agent(
            self.hass, conversation.HOME_ASSISTANT_AGENT
        )
        if agent is None or agent is self:
            return self._reply(user_input, "Xin lỗi, trợ lý hiện chưa sẵn sàng.", True)
        try:
            # Explicit lookup avoids pipeline selection recursion. Passing the original
            # object (or its repaired copy) preserves all request attribution.
            result = await agent.async_process(user_input)
        except HomeAssistantError:
            self.failures.clear(key)
            return self._reply(
                user_input,
                "Xin lỗi, tôi chưa thể xử lý yêu cầu. Bạn vui lòng thử lại sau nhé.",
                True,
            )

        key = (
            user_input.device_id,
            user_input.satellite_id,
            result.conversation_id or key[2],
        )
        failed = result.response.response_type == intent.IntentResponseType.ERROR
        if failed:
            count = self.failures.failed(key)
            # Only recognition misses may reopen; infrastructure/action errors stop.
            result.continue_conversation = bool(
                options["mode"] == "Always"
                and options["continue_unrecognized"]
                and key[2]
                and result.response.error_code
                == intent.IntentResponseErrorCode.NO_INTENT_MATCH
                and count < options["max_failures"]
            )
        else:
            self.failures.clear(key)
            if options["mode"] == "Off":
                result.continue_conversation = False
            elif options["mode"] == "Always":
                result.continue_conversation = True
            # Question preserves an explicit delegate flag; punctuation is not intent.
        return result

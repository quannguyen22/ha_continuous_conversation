"""UI configuration for Continuous Conversation."""

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DEFAULTS, DOMAIN, MODES
from .policy import normalize


def options_schema(options: dict[str, Any]) -> vol.Schema:
    """Build selectors with current values."""
    values = DEFAULTS | options
    return vol.Schema(
        {
            vol.Required("mode", default=values["mode"]): selector.SelectSelector(
                selector.SelectSelectorConfig(options=MODES)
            ),
            vol.Required(
                "termination_phrases", default=values["termination_phrases"]
            ): selector.TextSelector(selector.TextSelectorConfig(multiple=True)),
            vol.Required(
                "termination_response", default=values["termination_response"]
            ): str,
            vol.Required(
                "continue_unrecognized", default=values["continue_unrecognized"]
            ): bool,
            vol.Required("max_failures", default=values["max_failures"]): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=10)
            ),
        }
    )


def valid(options: dict[str, Any]) -> bool:
    """Reject blank termination phrases or a silent termination response."""
    return bool(options["termination_response"].strip()) and all(
        normalize(phrase) for phrase in options["termination_phrases"]
    )


class ContinuousConversationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create one global policy entry; sessions remain independent."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        self._async_abort_entries_match()
        errors = {}
        if user_input is not None:
            if valid(user_input):
                return self.async_create_entry(
                    title="Continuous Conversation", data={}, options=user_input
                )
            errors["base"] = "invalid_text"
        return self.async_show_form(
            step_id="user", data_schema=options_schema(user_input or {}), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return ContinuousConversationOptionsFlow()


class ContinuousConversationOptionsFlow(config_entries.OptionsFlow):
    """Persist policy updates in config-entry options."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input is not None:
            if valid(user_input):
                return self.async_create_entry(title="", data=user_input)
            errors["base"] = "invalid_text"
        return self.async_show_form(
            step_id="init",
            data_schema=options_schema(user_input or dict(self.config_entry.options)),
            errors=errors,
        )

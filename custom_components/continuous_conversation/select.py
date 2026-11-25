"""Persistent conversation mode selector."""

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULTS, MODES


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add the mode selector."""
    async_add_entities([ConversationMode(entry)])


class ConversationMode(SelectEntity):
    """Store the selected mode in the integration options."""

    _attr_has_entity_name = True
    _attr_translation_key = "mode"
    _attr_options = MODES
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_mode"

    @property
    def current_option(self) -> str:
        return self.entry.options.get("mode", DEFAULTS["mode"])

    async def async_select_option(self, option: str) -> None:
        """Persist mode; the update listener reloads entities."""
        if option not in MODES:
            raise ValueError("Unsupported conversation mode")
        self.hass.config_entries.async_update_entry(
            self.entry, options={**self.entry.options, "mode": option}
        )
        self.async_write_ha_state()

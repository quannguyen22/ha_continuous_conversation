"""Exercise configuration schema, persistence and lifecycle against HA APIs."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant

from custom_components.continuous_conversation import (
    async_setup_entry,
    async_unload_entry,
)
from custom_components.continuous_conversation.config_flow import (
    ContinuousConversationConfigFlow,
    ContinuousConversationOptionsFlow,
    options_schema,
    valid,
)
from custom_components.continuous_conversation.const import DEFAULTS
from custom_components.continuous_conversation.select import ConversationMode


def test_schema():
    assert options_schema({})(DEFAULTS) == DEFAULTS
    for value in [0, 11]:
        with pytest.raises(vol.Invalid):
            options_schema({})(DEFAULTS | {"max_failures": value})
    assert not valid(DEFAULTS | {"termination_phrases": ["!!!"]})
    assert not valid(DEFAULTS | {"termination_response": " "})
    assert valid(DEFAULTS | {"termination_phrases": []})


@pytest.mark.asyncio
async def test_flow_and_options():
    hass = HomeAssistant("/tmp/cc-config-test")
    hass.config_entries = SimpleNamespace(async_entries=Mock(return_value=[]))
    flow = ContinuousConversationConfigFlow()
    flow.hass = hass
    flow.context = {}
    response = await flow.async_step_user(dict(DEFAULTS))
    assert response["type"] == "create_entry"
    assert response["options"] == DEFAULTS
    options_flow = ContinuousConversationConfigFlow.async_get_options_flow(None)
    assert isinstance(options_flow, ContinuousConversationOptionsFlow)
    response = await options_flow.async_step_init(dict(DEFAULTS))
    assert response["data"] == DEFAULTS


@pytest.mark.asyncio
async def test_select_persists_and_lifecycle():
    entry = SimpleNamespace(
        entry_id="test",
        options=dict(DEFAULTS),
        async_on_unload=Mock(),
        add_update_listener=Mock(),
    )
    config_entries = SimpleNamespace(
        async_update_entry=Mock(),
        async_forward_entry_setups=AsyncMock(),
        async_unload_platforms=AsyncMock(return_value=True),
    )
    hass = SimpleNamespace(config_entries=config_entries)
    select = ConversationMode(entry)
    select.hass = hass
    select.async_write_ha_state = Mock()
    await select.async_select_option("Off")
    assert (
        config_entries.async_update_entry.call_args.kwargs["options"]["mode"] == "Off"
    )
    assert await async_setup_entry(hass, entry)
    assert await async_unload_entry(hass, entry)
    config_entries.async_forward_entry_setups.assert_awaited_once()
    config_entries.async_unload_platforms.assert_awaited_once()
    entry.async_on_unload.assert_called_once()

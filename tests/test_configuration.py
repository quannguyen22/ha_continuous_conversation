"""Exercise configuration schema, persistence and lifecycle against HA APIs."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

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
    remove_patch = Mock()
    with patch(
        "custom_components.continuous_conversation.install_pipeline_compat",
        return_value=remove_patch,
    ):
        assert await async_setup_entry(hass, entry)
        assert await async_unload_entry(hass, entry)
    remove_patch.assert_called_once_with()
    config_entries.async_forward_entry_setups.assert_awaited_once()
    config_entries.async_unload_platforms.assert_awaited_once()
    entry.async_on_unload.assert_called_once()


@pytest.mark.asyncio
async def test_setup_failure_releases_patch():
    """A failed platform setup must not leave a process-wide patch installed."""
    from custom_components.continuous_conversation import async_setup_entry

    entry = SimpleNamespace(entry_id="test")
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(
            async_forward_entry_setups=AsyncMock(
                side_effect=RuntimeError("setup failed")
            )
        )
    )
    release = Mock()
    with (
        patch(
            "custom_components.continuous_conversation.install_pipeline_compat",
            return_value=release,
        ),
        pytest.raises(RuntimeError, match="setup failed"),
    ):
        await async_setup_entry(hass, entry)
    release.assert_called_once_with()


@pytest.mark.asyncio
async def test_failed_unload_retains_patch():
    """Keep routing in place while an entry remains loaded."""
    release = Mock()
    entry = SimpleNamespace(runtime_data=release)
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(
            async_unload_platforms=AsyncMock(return_value=False)
        )
    )
    assert not await async_unload_entry(hass, entry)
    release.assert_not_called()


@pytest.mark.asyncio
async def test_entry_setup_installs_real_compatibility_patch():
    """Catch layout errors at real entry startup, before a conversation begins."""
    from custom_components.continuous_conversation.pipeline_compat import (
        _get_pipeline_type,
    )

    hass = HomeAssistant("/tmp/cc-real-entry-setup")
    hass.config_entries = SimpleNamespace(
        async_forward_entry_setups=AsyncMock(),
        async_unload_platforms=AsyncMock(return_value=True),
    )
    entry = SimpleNamespace(
        entry_id="startup", async_on_unload=Mock(), add_update_listener=Mock()
    )
    target = _get_pipeline_type()
    original = target.recognize_intent
    assert await async_setup_entry(hass, entry)
    try:
        assert target.recognize_intent is not original
    finally:
        assert await async_unload_entry(hass, entry)
    assert target.recognize_intent is original


@pytest.mark.parametrize(
    "rules",
    [
        [{"phrase": "!!!", "response": "Stop"}],
        [{"phrase": "thôi"}, {"phrase": "THÔI!"}],
        [{"response": "Missing phrase"}],
        [{"phrase": "thôi", "response": None}],
        [{"phrase": "thôi", "silent": "yes"}],
        [{"phrase": "thôi", "unexpected": True}],
        ["not a rule"],
        {"thôi": "not a list"},
    ],
)
def test_invalid_termination_rules(rules):
    assert not valid(DEFAULTS | {"termination_rules": rules})


def test_termination_rule_selector_and_legacy_options():
    values = DEFAULTS | {
        "termination_rules": [
            {"phrase": "thôi", "silent": True},
            {"phrase": "cảm ơn", "response": "Vâng ạ."},
        ]
    }
    assert options_schema({})(values) == values
    assert valid(values)
    legacy = {k: v for k, v in DEFAULTS.items() if k != "termination_rules"}
    assert valid(legacy)
    assert options_schema(legacy)(legacy)["termination_rules"] == []
    assert valid(DEFAULTS | {"termination_rules": [{"phrase": "im lặng"}]})


@pytest.mark.asyncio
async def test_rules_persist_through_options_flow():
    values = DEFAULTS | {"termination_rules": [{"phrase": "thôi", "silent": True}]}
    options_flow = ContinuousConversationOptionsFlow()
    response = await options_flow.async_step_init(values)
    assert response["data"]["termination_rules"] == values["termination_rules"]
    invalid = await options_flow.async_step_init(
        DEFAULTS | {"termination_rules": [{"phrase": ""}]}
    )
    assert invalid["type"] == "form"
    assert invalid["errors"] == {"base": "invalid_text"}

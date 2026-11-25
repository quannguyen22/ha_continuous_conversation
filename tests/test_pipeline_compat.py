"""Exercise patched real Core routing, default-agent matching and script responses."""

import asyncio
from functools import wraps
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.components import conversation
from homeassistant.components.assist_pipeline.pipeline import PipelineEventType
from homeassistant.components.conversation.agent_manager import get_agent_manager
from homeassistant.components.conversation.const import DATA_COMPONENT
from homeassistant.components.conversation.default_agent import DefaultAgent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.script import Script
from pipeline_helpers import make_run

from custom_components.continuous_conversation.const import DEFAULTS
from custom_components.continuous_conversation.conversation import (
    ContinuousConversation,
)
from custom_components.continuous_conversation.pipeline_compat import (
    _get_pipeline_type,
    install_pipeline_compat,
)


async def setup_agents(hass, mode="Always", command="chất lượng không khí"):
    builtin = DefaultAgent(hass)
    manager = get_agent_manager(hass)
    manager.default_agent = builtin
    await builtin.async_added_to_hass()
    agent = ContinuousConversation(
        SimpleNamespace(entry_id="test", options=DEFAULTS | {"mode": mode})
    )
    agent.hass = hass
    agent.entity_id = "conversation.renamed_agent"
    agent.async_write_ha_state = Mock()
    hass.data[DATA_COMPONENT] = SimpleNamespace(
        get_entity=lambda entity_id: agent if entity_id == agent.entity_id else None
    )
    hass.states.async_set("sensor.living_room_temperature", "24.6")
    script = Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {
                    "set_conversation_response": "Nhiệt độ phòng khách là {{ states('sensor.living_room_temperature') }} độ C."
                }
            ]
        ),
        "Air Quality",
        "automation",
    )
    seen = []

    async def callback(user_input, recognized):
        seen.append(user_input)
        result = await script.async_run(context=user_input.context)
        return result.conversation_response

    unsubscribe = manager.register_trigger([command], callback)
    return agent, builtin, seen, unsubscribe


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "expected"), [("Always", True), ("Off", False), ("Question", False)]
)
@pytest.mark.parametrize("prefer_local", [False, True])
async def test_first_turn_automation_reaches_policy_once(mode, expected, prefer_local):
    hass = HomeAssistant("/tmp/cc-compat-test")
    agent, builtin, seen, unsubscribe = await setup_agents(hass, mode)
    run, events = make_run(hass, agent.entity_id, prefer_local=prefer_local)
    original = _get_pipeline_type().recognize_intent
    release = install_pipeline_compat(hass, "test")
    try:
        speech, _ = await run.recognize_intent(
            "chất lượng không khí", "session", "keep prompt"
        )
        assert speech == "Nhiệt độ phòng khách là 24.6 độ C."
        assert len(seen) == 1
        assert seen[0].device_id == "panel1"
        assert seen[0].satellite_id == "assist_satellite.panel1"
        assert seen[0].conversation_id == "session"
        assert seen[0].extra_system_prompt == "keep prompt"
        assert seen[0].context is getattr(run, "host", run).context
        output = next(
            e.data["intent_output"]
            for e in events
            if e.type == PipelineEventType.INTENT_END
        )
        assert output["continue_conversation"] is expected
        assert run._conversation_data.continue_conversation_agent == (
            agent.entity_id if expected else None
        )
        assert "_intent_agent_only" not in vars(run)
    finally:
        release()
        unsubscribe()
        await builtin.async_will_remove_from_hass()
    assert _get_pipeline_type().recognize_intent is original


@pytest.mark.asyncio
async def test_stop_phrase_takes_precedence_over_automation():
    hass = HomeAssistant("/tmp/cc-compat-stop")
    agent, builtin, seen, unsubscribe = await setup_agents(hass, command="cảm ơn")
    run, events = make_run(hass, agent.entity_id)
    release = install_pipeline_compat(hass, "test")
    try:
        speech, _ = await run.recognize_intent("cảm ơn", "session", None)
        assert speech == DEFAULTS["termination_response"]
        assert not seen
        output = next(
            e.data["intent_output"]
            for e in events
            if e.type == PipelineEventType.INTENT_END
        )
        assert not output["continue_conversation"]
    finally:
        release()
        unsubscribe()
        await builtin.async_will_remove_from_hass()


@pytest.mark.asyncio
async def test_other_agent_keeps_core_shortcut():
    hass = HomeAssistant("/tmp/cc-compat-other")
    run, _events = make_run(hass, "conversation.other")
    release = install_pipeline_compat(hass, "test")
    sentence = AsyncMock(return_value="Original automation response")
    converse = AsyncMock()
    try:
        with (
            patch.object(conversation, "async_get_agent", return_value=None),
            patch.object(conversation, "async_handle_sentence_triggers", sentence),
            patch.object(conversation, "async_converse", converse),
        ):
            speech, _ = await run.recognize_intent("command", "session", None)
        assert speech == "Original automation response"
        sentence.assert_awaited_once()
        converse.assert_not_awaited()
    finally:
        release()


@pytest.mark.asyncio
async def test_two_panels_concurrently():
    hass = HomeAssistant("/tmp/cc-compat-concurrent")
    agent, builtin, seen, unsubscribe = await setup_agents(hass)
    runs = [make_run(hass, agent.entity_id, device=f"panel{i}")[0] for i in range(2)]
    release = install_pipeline_compat(hass, "test")
    try:
        await asyncio.gather(
            *(
                run.recognize_intent("chất lượng không khí", f"session{i}", None)
                for i, run in enumerate(runs)
            )
        )
        assert {v.device_id for v in seen} == {"panel0", "panel1"}
        assert {v.conversation_id for v in seen} == {"session0", "session1"}
        assert len(seen) == 2
        assert all(not run._intent_agent_only for run in runs)
    finally:
        release()
        unsubscribe()
        await builtin.async_will_remove_from_hass()


@pytest.mark.asyncio
async def test_cancelled_run_restores_override():
    hass = HomeAssistant("/tmp/cc-compat-cancel")
    agent, builtin, _, unsubscribe = await setup_agents(hass)
    run, _ = make_run(hass, agent.entity_id)
    run._intent_agent_only = False
    release = install_pipeline_compat(hass, "test")
    try:
        with (
            patch.object(
                conversation,
                "async_converse",
                AsyncMock(side_effect=asyncio.CancelledError),
            ),
            pytest.raises(asyncio.CancelledError),
        ):
            await run.recognize_intent("command", "session", None)
        assert run._intent_agent_only is False
    finally:
        release()
        unsubscribe()
        await builtin.async_will_remove_from_hass()


@pytest.mark.asyncio
async def test_reference_count_and_external_wrapper_are_preserved():
    original = _get_pipeline_type().recognize_intent
    hass1, hass2 = HomeAssistant("/tmp/cc-owner1"), HomeAssistant("/tmp/cc-owner2")
    release1 = install_pipeline_compat(hass1, "one")
    wrapper = _get_pipeline_type().recognize_intent
    release2 = install_pipeline_compat(hass2, "two")
    assert _get_pipeline_type().recognize_intent is wrapper
    release1()
    release1()
    assert _get_pipeline_type().recognize_intent is wrapper

    @wraps(wrapper)
    async def external(*args, **kwargs):
        return await wrapper(*args, **kwargs)

    with patch.object(_get_pipeline_type(), "recognize_intent", external):
        release2()
        assert _get_pipeline_type().recognize_intent is external
    # The third-party owner is responsible for removing its wrapper.
    _get_pipeline_type().recognize_intent = original


@pytest.mark.asyncio
async def test_incompatible_api_rejected_without_mutation():
    async def incompatible(self, new_parameter):
        pass

    hass = HomeAssistant("/tmp/cc-incompatible")
    with patch.object(_get_pipeline_type(), "recognize_intent", incompatible):
        with pytest.raises(ConfigEntryError, match="cannot safely patch"):
            install_pipeline_compat(hass, "test")
        assert _get_pipeline_type().recognize_intent is incompatible


@pytest.mark.asyncio
async def test_unregistered_instance_is_untouched():
    """Global wrapping must not affect a different HA instance using the same class."""
    owner = HomeAssistant("/tmp/cc-registered")
    other = HomeAssistant("/tmp/cc-unregistered")
    agent, builtin, seen, unsubscribe = await setup_agents(other)
    run, events = make_run(other, agent.entity_id)
    release = install_pipeline_compat(owner, "test")
    try:
        speech, _ = await run.recognize_intent("chất lượng không khí", "session", None)
        assert speech == "Nhiệt độ phòng khách là 24.6 độ C."
        assert len(seen) == 1
        output = next(
            e.data["intent_output"]
            for e in events
            if e.type == PipelineEventType.INTENT_END
        )
        assert not output["continue_conversation"]
    finally:
        release()
        unsubscribe()
        await builtin.async_will_remove_from_hass()


@pytest.mark.asyncio
async def test_missing_pipeline_api_reports_configuration_error():
    """Missing methods must never escape as a raw AttributeError during startup."""
    from homeassistant.components.assist_pipeline.pipeline import PipelineRun

    hass = HomeAssistant("/tmp/cc-missing-api")
    with (
        patch.object(PipelineRun, "recognize_intent", None, create=True),
        patch(
            "custom_components.continuous_conversation.pipeline_compat.import_module",
            return_value=SimpleNamespace(),
        ),
        pytest.raises(ConfigEntryError, match="cannot find a compatible"),
    ):
        install_pipeline_compat(hass, "test")

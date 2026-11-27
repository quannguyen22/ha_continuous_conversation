"""Cover the narrowly scoped workaround for repeated Vietnamese mode prefixes."""

import unicodedata
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.assist_pipeline.pipeline import PipelineEventType
from homeassistant.components.conversation.chat_log import DATA_CHAT_LOGS
from homeassistant.core import HomeAssistant
from pipeline_helpers import make_run
from test_conversation import result, user, wrapper
from test_pipeline_compat import setup_agents

from custom_components.continuous_conversation.pipeline_compat import (
    install_pipeline_compat,
)
from custom_components.continuous_conversation.policy import repair_mode_prefix


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("chế độ chế độ tiếp khách", "chế độ tiếp khách"),
        ("chế độ chế độ ăn tối", "chế độ ăn tối"),
        ("CHẾ ĐỘ chế độ Chế độ tiếp khách!", "chế độ tiếp khách!"),
        (" chế   độ\tchế độ  xem phim", "chế độ  xem phim"),
        (unicodedata.normalize("NFD", "chế độ chế độ ăn tối"), "chế độ ăn tối"),
    ],
)
def test_repeated_prefix_only(text, expected):
    assert repair_mode_prefix(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "chế độ tiếp khách",
        "bật đèn đèn phòng khách",
        "tắt tắt quạt",
        "hãy nói chế độ chế độ tiếp khách",
        "chế độ chế độ",
        "chế độ chế độ   ",
        "chế độ chế độăn tối",
        "đèn chế độ chế độ",
        "",
        "   ",
    ],
)
def test_unrelated_or_incomplete_text_is_untouched(text):
    assert repair_mode_prefix(text) == text


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [True, False])
async def test_delegate_copy_preserves_context_and_original_input(enabled):
    entity = wrapper(repair_repeated_mode_prefix=enabled)
    original = user("chế độ chế độ tiếp khách")
    before = asdict(original)
    delegate = SimpleNamespace(async_process=AsyncMock(return_value=result()))
    with patch(
        "custom_components.continuous_conversation.conversation.conversation.async_get_agent",
        return_value=delegate,
    ):
        await entity.async_process(original)
    forwarded = delegate.async_process.call_args.args[0]
    assert asdict(original) == before
    expected = before | {"text": "chế độ tiếp khách"} if enabled else before
    assert asdict(forwarded) == expected
    assert forwarded.context is original.context
    assert (forwarded is original) is not enabled


def test_existing_entry_defaults_to_repair():
    entity = wrapper()
    entity.entry.options.pop("repair_repeated_mode_prefix")
    assert entity.prepare_input_text("chế độ chế độ tiếp khách") == "chế độ tiếp khách"


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["tiếp khách", "ăn tối", "xem phim"])
@pytest.mark.parametrize("enabled", [True, False])
async def test_real_pipeline_matches_mode_automation_once(target, enabled):
    hass = HomeAssistant("/tmp/cc-repair-pipeline")
    expected_text = f"chế độ {target}" if enabled else f"chế độ chế độ {target}"
    agent, builtin, seen, unsubscribe = await setup_agents(hass, command=expected_text)
    agent.entry.options["repair_repeated_mode_prefix"] = enabled
    run, events = make_run(hass, agent.entity_id)
    release = install_pipeline_compat(hass, "test")
    try:
        await run.recognize_intent(f"chế độ chế độ {target}", "session", None)
        assert len(seen) == 1
        assert seen[0].text == expected_text
        assert seen[0].device_id == "panel1"
        assert seen[0].conversation_id == "session"
        event = next(e for e in events if e.type == PipelineEventType.INTENT_START)
        assert event.data["intent_input"] == expected_text
        users = [
            c for c in hass.data[DATA_CHAT_LOGS]["session"].content if c.role == "user"
        ]
        assert len(users) == 1
        assert users[0].content == expected_text
        output = next(
            e.data["intent_output"]
            for e in events
            if e.type == PipelineEventType.INTENT_END
        )
        assert output["continue_conversation"]
    finally:
        release()
        unsubscribe()
        await builtin.async_will_remove_from_hass()

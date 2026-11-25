"""Tests against real Home Assistant models; no satellite hardware is simulated."""

import asyncio
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.conversation import ConversationInput, ConversationResult
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import intent

from custom_components.continuous_conversation.const import DEFAULTS
from custom_components.continuous_conversation.conversation import (
    ContinuousConversation,
)
from custom_components.continuous_conversation.policy import FailureTracker, normalize


def user(text="bật đèn", device="panel1", session="session1"):
    return ConversationInput(
        text,
        Context(),
        session,
        device,
        f"assist_satellite.{device}",
        "vi",
        "conversation.continuous_conversation",
        "original prompt",
    )


def result(failed=False, question=False, session="session1", code=None):
    response = intent.IntentResponse(language="vi")
    if failed:
        response.async_set_error(
            code or intent.IntentResponseErrorCode.NO_INTENT_MATCH, "original error"
        )
    else:
        response.async_set_speech("Phản hồi từ tự động hóa")
    return ConversationResult(response, session, question)


def wrapper(**options):
    entity = ContinuousConversation(
        SimpleNamespace(entry_id="test", options=DEFAULTS | options)
    )
    entity.hass = SimpleNamespace()
    return entity


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "flag", "expected"),
    [
        ("Always", False, True),
        ("Off", True, False),
        ("Question", False, False),
        ("Question", True, True),
    ],
)
async def test_modes_preserve_input_and_response(mode, flag, expected):
    entity = wrapper(mode=mode)
    original = user()
    snapshot = asdict(original)
    output = result(question=flag)
    delegate = SimpleNamespace(async_process=AsyncMock(return_value=output))
    with patch(
        "custom_components.continuous_conversation.conversation.conversation.async_get_agent",
        return_value=delegate,
    ) as lookup:
        actual = await entity.async_process(original)
    assert actual is output
    assert actual.response is output.response
    assert actual.continue_conversation is expected
    assert asdict(original) == snapshot
    assert delegate.async_process.call_args.args[0] is original
    assert lookup.call_args.args[1] == "conversation.home_assistant"


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [" CẢM ƠN NHÉ!!! ", "thôi", "tạm biệt.", "", "   !!!"])
async def test_stop_and_empty_do_not_delegate(text):
    with patch(
        "custom_components.continuous_conversation.conversation.conversation.async_get_agent"
    ) as lookup:
        output = await wrapper().async_process(user(text))
    assert not output.continue_conversation
    lookup.assert_not_called()


@pytest.mark.asyncio
async def test_embedded_phrase_delegates():
    delegate = SimpleNamespace(async_process=AsyncMock(return_value=result()))
    with patch(
        "custom_components.continuous_conversation.conversation.conversation.async_get_agent",
        return_value=delegate,
    ):
        await wrapper().async_process(user("bật đèn rồi cảm ơn nhé"))
    delegate.async_process.assert_awaited_once()


@pytest.mark.asyncio
async def test_failure_limit_isolated_and_success_resets():
    entity = wrapper(continue_unrecognized=True, max_failures=2)
    delegate = SimpleNamespace(
        async_process=AsyncMock(
            side_effect=[
                result(True),
                result(True, session="other"),
                result(True),
                result(),
                result(True),
            ]
        )
    )
    with patch(
        "custom_components.continuous_conversation.conversation.conversation.async_get_agent",
        return_value=delegate,
    ):
        assert (await entity.async_process(user())).continue_conversation
        assert (
            await entity.async_process(user(device="panel2", session="other"))
        ).continue_conversation
        assert not (await entity.async_process(user())).continue_conversation
        assert (await entity.async_process(user())).continue_conversation
        assert (await entity.async_process(user())).continue_conversation


@pytest.mark.asyncio
async def test_action_error_and_exception_stop():
    for response in [
        result(True, code=intent.IntentResponseErrorCode.UNKNOWN),
        HomeAssistantError("private text"),
    ]:
        entity = wrapper(continue_unrecognized=True)
        mock = (
            AsyncMock(side_effect=response)
            if isinstance(response, Exception)
            else AsyncMock(return_value=response)
        )
        with patch(
            "custom_components.continuous_conversation.conversation.conversation.async_get_agent",
            return_value=SimpleNamespace(async_process=mock),
        ):
            output = await entity.async_process(user())
        assert not output.continue_conversation


@pytest.mark.asyncio
async def test_concurrent_devices():
    async def process(value):
        await asyncio.sleep(0)
        return result(True, session=value.conversation_id)

    delegate = SimpleNamespace(async_process=process)
    entity = wrapper(continue_unrecognized=True)
    with patch(
        "custom_components.continuous_conversation.conversation.conversation.async_get_agent",
        return_value=delegate,
    ):
        outputs = await asyncio.gather(
            *(
                entity.async_process(user(device=f"panel{i}", session=f"session{i}"))
                for i in range(10)
            )
        )
    assert all(value.continue_conversation for value in outputs)
    assert len(entity.failures._items) == 10


def test_normalization_and_bounded_expiry():
    assert normalize("  CẢM ƠN, NHÉ! ") == "cảm ơn nhé"
    tracker = FailureTracker(ttl=5, capacity=2)
    with patch(
        "custom_components.continuous_conversation.policy.monotonic", return_value=10
    ):
        for value in range(5):
            tracker.failed((str(value), None, "session"))
        assert len(tracker._items) == 2
    with patch(
        "custom_components.continuous_conversation.policy.monotonic", return_value=16
    ):
        tracker.prune()
    assert not tracker._items


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("CẢM ƠN!", "Rất vui được giúp bạn."),
        ("tạm biệt", "Hẹn gặp lại bạn."),
        ("thôi", ""),
        ("im lặng nhé", ""),
        ("kết thúc", ""),
    ],
)
async def test_per_phrase_response_and_silent_rules(text, expected):
    entity = wrapper(
        termination_rules=[
            {"phrase": "cảm ơn", "response": "Rất vui được giúp bạn."},
            {"phrase": "tạm biệt", "response": "Hẹn gặp lại bạn."},
            {"phrase": "thôi", "response": "Not spoken", "silent": True},
            {"phrase": "im lặng nhé", "response": "   "},
            {"phrase": "kết thúc"},
        ]
    )
    with patch(
        "custom_components.continuous_conversation.conversation.conversation.async_get_agent"
    ) as delegate:
        output = await entity.async_process(user(text))
    delegate.assert_not_called()
    assert not output.continue_conversation
    assert output.conversation_id == "session1"
    assert output.response.speech.get("plain", {}).get("speech", "") == expected
    if not expected:
        assert output.response.speech == {}


@pytest.mark.asyncio
async def test_legacy_response_and_custom_rule_substring_preserved():
    entity = wrapper(
        termination_response="Existing personalized response",
        termination_rules=[{"phrase": "cảm ơn", "response": "New response"}],
    )
    assert (await entity.async_process(user("thôi"))).response.speech["plain"][
        "speech"
    ] == "Existing personalized response"
    delegate = SimpleNamespace(async_process=AsyncMock(return_value=result()))
    with patch(
        "custom_components.continuous_conversation.conversation.conversation.async_get_agent",
        return_value=delegate,
    ):
        await entity.async_process(user("bật đèn rồi cảm ơn"))
    delegate.async_process.assert_awaited_once()

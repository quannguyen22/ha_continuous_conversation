"""Regression coverage for Core's automation shortcut before custom agents."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components import conversation
from homeassistant.components.assist_pipeline.pipeline import PipelineEventType
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from pipeline_helpers import make_run


@pytest.mark.asyncio
@pytest.mark.parametrize("agent_only", [False, True])
async def test_core_sentence_shortcut_bypasses_agent_on_fresh_turn(agent_only):
    """Prove why a correct agent alone cannot change first-turn automation results."""
    hass = HomeAssistant("/tmp/cc-pipeline-test")
    run, events = make_run(hass, "conversation.continuous_conversation")
    run._intent_agent_only = agent_only
    response = intent.IntentResponse(language="vi")
    response.async_set_speech("Nhiệt độ phòng khách là 24.6 độ C.")
    delegated = conversation.ConversationResult(response, "session", True)
    sentence = AsyncMock(return_value="Nhiệt độ phòng khách là 24.6 độ C.")
    converse = AsyncMock(return_value=delegated)
    with (
        patch.object(conversation, "async_handle_sentence_triggers", sentence),
        patch.object(conversation, "async_converse", converse),
    ):
        speech, _ = await run.recognize_intent("chất lượng không khí", "session", None)
    assert speech == "Nhiệt độ phòng khách là 24.6 độ C."
    output = next(
        event.data["intent_output"]
        for event in events
        if event.type == PipelineEventType.INTENT_END
    )
    assert output["continue_conversation"] is agent_only
    assert converse.await_count == int(agent_only)
    assert sentence.await_count == int(not agent_only)

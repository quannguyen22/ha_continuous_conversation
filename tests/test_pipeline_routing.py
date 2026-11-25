"""Regression coverage for Core's automation shortcut before custom agents."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.components import conversation
from homeassistant.components.assist_pipeline.pipeline import (
    KEY_ASSIST_PIPELINE,
    AudioSettings,
    Pipeline,
    PipelineConversationData,
    PipelineEventType,
    PipelineRun,
    PipelineStage,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent


@pytest.mark.asyncio
@pytest.mark.parametrize("agent_only", [False, True])
async def test_core_sentence_shortcut_bypasses_agent_on_fresh_turn(agent_only):
    """Prove why a correct agent alone cannot change first-turn automation results."""
    hass = HomeAssistant("/tmp/cc-pipeline-test")
    hass.data[KEY_ASSIST_PIPELINE] = SimpleNamespace(
        pipeline_debug={}, pipeline_runs=SimpleNamespace(add_run=Mock())
    )
    pipeline = Pipeline(
        conversation_engine="conversation.continuous_conversation",
        conversation_language="vi",
        language="vi",
        name="Vietnamese Local",
        stt_engine=None,
        stt_language=None,
        tts_engine=None,
        tts_language=None,
        tts_voice=None,
        wake_word_entity=None,
        wake_word_id=None,
        prefer_local_intents=False,
    )
    events = []
    run = PipelineRun(
        hass,
        Context(),
        pipeline,
        PipelineStage.INTENT,
        PipelineStage.INTENT,
        events.append,
        intent_agent=conversation.AgentInfo(
            pipeline.conversation_engine, "Continuous Conversation", False
        ),
        audio_settings=AudioSettings(is_vad_enabled=False),
        _conversation_data=PipelineConversationData(),
    )
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

"""Construct real pipeline controllers/processors for both supported Core layouts."""

from types import SimpleNamespace
from unittest.mock import Mock

from homeassistant.components import conversation
from homeassistant.components.assist_pipeline.pipeline import (
    KEY_ASSIST_PIPELINE,
    AudioSettings,
    Pipeline,
    PipelineRun,
    PipelineStage,
)
from homeassistant.core import Context

if hasattr(PipelineRun, "recognize_intent"):
    from homeassistant.components.assist_pipeline.pipeline import (
        PipelineConversationData,
    )
else:
    from homeassistant.components.assist_pipeline.default_pipeline import (
        PipelineConversationData,
    )


def make_run(hass, agent_id, device="panel1", prefer_local=False):
    """Return the real intent processor and its events on either Core layout."""
    hass.data.setdefault(
        KEY_ASSIST_PIPELINE,
        SimpleNamespace(
            pipeline_debug={}, pipeline_runs=SimpleNamespace(add_run=Mock())
        ),
    )
    pipeline = Pipeline(
        agent_id,
        "vi",
        "vi",
        "Vietnamese Local",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        prefer_local,
    )
    events = []
    host = PipelineRun(
        hass,
        Context(),
        pipeline,
        PipelineStage.INTENT,
        PipelineStage.INTENT,
        events.append,
        audio_settings=AudioSettings(is_vad_enabled=False),
        _device_id=device,
        _satellite_id=f"assist_satellite.{device}",
    )
    processor = host if hasattr(host, "recognize_intent") else host._processor
    processor.intent_agent = conversation.AgentInfo(agent_id, "Agent", False)
    processor._conversation_data = PipelineConversationData()
    return processor, events

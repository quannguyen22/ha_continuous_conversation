"""Constants for Continuous Conversation."""

DOMAIN = "continuous_conversation"
MODES = ["Off", "Always", "Question"]
DEFAULT_PHRASES = [
    "cảm ơn",
    "cảm ơn nhé",
    "thôi",
    "thôi nhé",
    "kết thúc",
    "dừng lại",
    "không cần nữa",
    "tạm biệt",
]
DEFAULTS = {
    "mode": "Always",
    "termination_phrases": DEFAULT_PHRASES,
    "termination_response": "Vâng, hẹn gặp lại bạn nhé.",
    "continue_unrecognized": False,
    "max_failures": 2,
}

"""Pure continuation policy and bounded failure accounting."""

import re
import unicodedata
from collections import OrderedDict
from time import monotonic

_REPEATED_MODE_PREFIX = re.compile(
    r"^\s*chế\s+độ(?:\s+chế\s+độ)+(?=\s|$)", re.IGNORECASE
)


def repair_mode_prefix(text: str) -> str:
    """Collapse only a repeated Vietnamese mode prefix with a following target."""
    composed = unicodedata.normalize("NFC", text)
    if (match := _REPEATED_MODE_PREFIX.match(composed)) and composed[
        match.end() :
    ].strip():
        return "chế độ" + composed[match.end() :]
    return text


def normalize(text: str) -> str:
    """Normalize Unicode, punctuation, case and whitespace without substring matching."""
    text = unicodedata.normalize("NFC", text).casefold()
    return " ".join(
        "".join(
            " " if unicodedata.category(char).startswith("P") else char for char in text
        ).split()
    )


class FailureTracker:
    """Track only recent failures, with a strict memory bound and no background task."""

    def __init__(self, ttl: float = 300, capacity: int = 256) -> None:
        self.ttl = ttl
        self.capacity = capacity
        self._items: OrderedDict[
            tuple[str | None, str | None, str], tuple[float, int]
        ] = OrderedDict()

    def prune(self) -> None:
        """Remove expired entries on requests; unload releases the whole tracker."""
        cutoff = monotonic() - self.ttl
        for key, (timestamp, _) in list(self._items.items()):
            if timestamp <= cutoff:
                del self._items[key]

    def clear(self, key: tuple[str | None, str | None, str]) -> None:
        """Reset the consecutive failure count."""
        self._items.pop(key, None)

    def failed(self, key: tuple[str | None, str | None, str]) -> int:
        """Count in completion order; this synchronous update cannot interleave."""
        self.prune()
        count = self._items.pop(key, (0, 0))[1] + 1
        self._items[key] = (monotonic(), count)
        while len(self._items) > self.capacity:
            self._items.popitem(last=False)
        return count

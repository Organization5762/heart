from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class Input:
    """Normalized structure for messages emitted by peripherals."""

    event_type: str
    data: Any
    producer_id: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BotHolder:
    bot: Any | None = None

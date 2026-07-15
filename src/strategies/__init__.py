"""Strategy registry. Add new strategies here and they appear everywhere."""
from __future__ import annotations

from .base import Strategy
from .confluence import ConfluenceStrategy
from .orb import ORBStrategy

_STRATEGIES: dict[str, Strategy] = {
    ConfluenceStrategy.key: ConfluenceStrategy(),
    ORBStrategy.key: ORBStrategy(),
}

DEFAULT = ConfluenceStrategy.key


def get_strategy(key: str | None) -> Strategy:
    return _STRATEGIES.get((key or DEFAULT).lower(), _STRATEGIES[DEFAULT])


def list_strategies() -> list[dict]:
    return [
        {"key": s.key, "name": s.name, "description": s.description}
        for s in _STRATEGIES.values()
    ]


__all__ = ["Strategy", "get_strategy", "list_strategies", "DEFAULT"]

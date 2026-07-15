"""Data provider factory.

Returns the configured data provider. Swap between mock and Angel One
purely via the DATA_PROVIDER env var — no code changes needed elsewhere.
"""
from __future__ import annotations

from config import settings
from .base import DataProvider
from .mock_provider import MockDataProvider


def get_provider() -> DataProvider:
    provider = settings.data_provider
    if provider == "angelone":
        # Imported lazily so the app runs on mock without SmartAPI installed.
        from .angelone_provider import AngelOneDataProvider

        return AngelOneDataProvider()
    return MockDataProvider()


__all__ = ["DataProvider", "get_provider"]

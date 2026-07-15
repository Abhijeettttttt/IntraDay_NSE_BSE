"""Central configuration. Reads from environment / .env file."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv optional at runtime
    pass


@dataclass
class Settings:
    # Which data provider to use: "mock" or "angelone"
    data_provider: str = os.getenv("DATA_PROVIDER", "mock").lower()

    # Angel One SmartAPI credentials (only needed when data_provider == "angelone")
    angelone_api_key: str = os.getenv("ANGELONE_API_KEY", "")
    angelone_client_code: str = os.getenv("ANGELONE_CLIENT_CODE", "")
    angelone_mpin: str = os.getenv("ANGELONE_MPIN", "")
    angelone_totp_secret: str = os.getenv("ANGELONE_TOTP_SECRET", "")

    # Default intraday candle interval
    interval: str = os.getenv("INTERVAL", "FIVE_MINUTE")

    # Default watchlist (NSE symbols). Edit freely.
    watchlist: list[str] = field(
        default_factory=lambda: [
            "RELIANCE",
            "TCS",
            "HDFCBANK",
            "INFY",
            "ICICIBANK",
            "SBIN",
            "TATAMOTORS",
            "AXISBANK",
            "ITC",
            "WIPRO",
        ]
    )

    @property
    def angelone_ready(self) -> bool:
        return all(
            [
                self.angelone_api_key,
                self.angelone_client_code,
                self.angelone_mpin,
                self.angelone_totp_secret,
            ]
        )


settings = Settings()

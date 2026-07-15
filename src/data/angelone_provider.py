"""Angel One SmartAPI data provider.

Implements the same DataProvider interface as the mock provider, so the
rest of the app is unchanged. Activated by setting DATA_PROVIDER=angelone
and providing credentials in .env.

Install first:
    pip install smartapi-python pyotp websocket-client

Docs: https://smartapi.angelbroking.com/docs
"""
from __future__ import annotations

import time as _time
from datetime import datetime, timedelta
from functools import lru_cache

import pandas as pd

from config import settings
from .base import DataProvider

# SmartAPI interval labels match the ones we use internally.
_VALID_INTERVALS = {
    "ONE_MINUTE",
    "THREE_MINUTE",
    "FIVE_MINUTE",
    "TEN_MINUTE",
    "FIFTEEN_MINUTE",
    "THIRTY_MINUTE",
    "ONE_HOUR",
    "ONE_DAY",
}

_INSTRUMENT_URL = (
    "https://margincalculator.angelbroking.com/OpenAPI_File/files/"
    "OpenAPIScripMaster.json"
)


class AngelOneDataProvider(DataProvider):
    name = "angelone"

    def __init__(self) -> None:
        if not settings.angelone_ready:
            raise RuntimeError(
                "Angel One credentials are missing. Fill ANGELONE_* values "
                "in your .env file, or set DATA_PROVIDER=mock."
            )
        try:
            from SmartApi import SmartConnect  # type: ignore
            import pyotp  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "SmartAPI packages not installed. Run:\n"
                "  pip install smartapi-python pyotp websocket-client"
            ) from exc

        self._pyotp = pyotp
        self._smart = SmartConnect(api_key=settings.angelone_api_key)
        self._login()

    # ------------------------------------------------------------------ auth
    def _login(self) -> None:
        totp = self._pyotp.TOTP(settings.angelone_totp_secret).now()
        session = self._smart.generateSession(
            settings.angelone_client_code,
            settings.angelone_mpin,
            totp,
        )
        if not session.get("status"):
            raise RuntimeError(f"Angel One login failed: {session}")
        self._feed_token = self._smart.getfeedToken()

    # ------------------------------------------------------ instrument lookup
    @lru_cache(maxsize=1)
    def _instruments(self) -> pd.DataFrame:
        # Full scrip master (~a few MB). Cached for the session.
        df = pd.read_json(_INSTRUMENT_URL)
        return df

    def _token_for(self, symbol: str, exchange: str = "NSE") -> str:
        df = self._instruments()
        # NSE equity symbols carry an "-EQ" suffix in the master.
        target = f"{symbol.upper()}-EQ"
        match = df[(df["exch_seg"] == exchange) & (df["symbol"] == target)]
        if match.empty:
            # Fall back to a name-based contains search.
            match = df[
                (df["exch_seg"] == exchange)
                & (df["name"].astype(str).str.upper() == symbol.upper())
            ]
        if match.empty:
            raise ValueError(f"Symbol not found in instrument master: {symbol}")
        return str(match.iloc[0]["token"])

    # ------------------------------------------------------------- historical
    def get_historical(
        self,
        symbol: str,
        interval: str = "FIVE_MINUTE",
        days: int = 5,
    ) -> pd.DataFrame:
        if interval not in _VALID_INTERVALS:
            interval = "FIVE_MINUTE"
        token = self._token_for(symbol)
        to_dt = datetime.now()
        from_dt = to_dt - timedelta(days=days + 4)  # pad for weekends/holidays
        params = {
            "exchange": "NSE",
            "symboltoken": token,
            "interval": interval,
            "fromdate": from_dt.strftime("%Y-%m-%d %H:%M"),
            "todate": to_dt.strftime("%Y-%m-%d %H:%M"),
        }
        resp = self._retry(lambda: self._smart.getCandleData(params))
        data = resp.get("data") or []
        if not data:
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "volume"]
            )
        df = pd.DataFrame(
            data, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")
        return df.astype(float).assign(volume=lambda d: d["volume"].astype(int))

    # -------------------------------------------------------------------- ltp
    def get_ltp(self, symbol: str) -> float:
        token = self._token_for(symbol)
        resp = self._retry(
            lambda: self._smart.ltpData("NSE", f"{symbol.upper()}-EQ", token)
        )
        return float(resp["data"]["ltp"])

    # ----------------------------------------------------------------- helper
    def _retry(self, fn, attempts: int = 3, delay: float = 0.4):
        """Simple retry to respect transient errors / rate limits."""
        last = None
        for i in range(attempts):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001
                last = exc
                _time.sleep(delay * (i + 1))
        raise RuntimeError(f"Angel One request failed after {attempts} tries: {last}")

# ============================================================
#  data_fetcher.py  —  завантаження даних з Binance (безкоштовно)
# ============================================================

import requests
import pandas as pd
from config import SYMBOL, CANDLES_LIMIT


BINANCE_URL = "https://api.binance.com/api/v3/klines"


def get_ohlcv(timeframe: str) -> pd.DataFrame:
    """
    Завантажує OHLCV свічки з Binance.
    Повертає DataFrame з колонками: open, high, low, close, volume
    """
    params = {
        "symbol": SYMBOL,
        "interval": timeframe,
        "limit": CANDLES_LIMIT,
    }
    try:
        resp = requests.get(BINANCE_URL, params=params, timeout=10)
        resp.raise_for_status()
        raw = resp.json()

        df = pd.DataFrame(raw, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades",
            "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        df = df[["timestamp", "open", "high", "low", "close", "volume"]].copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)

        return df

    except Exception as e:
        print(f"[DataFetcher] Помилка завантаження {timeframe}: {e}")
        return pd.DataFrame()

# ============================================================
#  data_fetcher.py  —  дані з Bybit (працює в Україні)
# ============================================================

import requests
import pandas as pd
from config import SYMBOL, CANDLES_LIMIT

BYBIT_URL = "https://api.bybit.com/v5/market/kline"

# Bybit використовує числові інтервали замість "15m"
INTERVAL_MAP = {
    "1m":  "1",
    "3m":  "3",
    "5m":  "5",
    "15m": "15",
    "30m": "30",
    "1h":  "60",
    "2h":  "120",
    "4h":  "240",
    "1d":  "D",
}


def get_ohlcv(timeframe: str) -> pd.DataFrame:
    interval = INTERVAL_MAP.get(timeframe)
    if not interval:
        print(f"[DataFetcher] Невідомий таймфрейм: {timeframe}")
        return pd.DataFrame()

    try:
        resp = requests.get(
            BYBIT_URL,
            params={
                "category": "spot",
                "symbol":   SYMBOL,
                "interval": interval,
                "limit":    CANDLES_LIMIT,
            },
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("retCode") != 0:
            print(f"[DataFetcher] Bybit помилка: {data.get('retMsg')}")
            return pd.DataFrame()

        raw = data["result"]["list"]
        # Bybit повертає від нового до старого — перевертаємо
        raw = list(reversed(raw))

        df = pd.DataFrame(raw, columns=[
            "timestamp", "open", "high", "low", "close", "volume", "turnover"
        ])
        df["timestamp"] = pd.to_datetime(df["timestamp"].astype(float), unit="ms")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)

        return df.reset_index(drop=True)

    except Exception as e:
        print(f"[DataFetcher] Помилка завантаження {timeframe}: {e}")
        return pd.DataFrame()

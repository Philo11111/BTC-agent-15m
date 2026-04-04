# ============================================================
#  data_fetcher.py  —  Binance → OKX → Kraken
#
#  Порядок пріоритетів:
#  1. Binance  — найкращі дані, працює на Railway (США)
#  2. OKX      — без гео-обмежень, fallback для локального запуску
#  3. Kraken   — останній резерв, працює скрізь
# ============================================================

import requests
import pandas as pd
from config import CANDLES_LIMIT

HEADERS = {"User-Agent": "Mozilla/5.0 BTC-Signal-Bot/1.0"}

TF_BINANCE = {"1m":"1m","5m":"5m","15m":"15m","30m":"30m","1h":"1h","4h":"4h","1d":"1d"}
TF_OKX     = {"1m":"1m","5m":"5m","15m":"15m","30m":"30m","1h":"1H","4h":"4H","1d":"1D"}
TF_KRAKEN  = {"1m":1,"5m":5,"15m":15,"30m":30,"1h":60,"4h":240,"1d":1440}


def _from_binance(timeframe: str) -> pd.DataFrame:
    interval = TF_BINANCE.get(timeframe)
    if not interval:
        return pd.DataFrame()
    r = requests.get(
        "https://api.binance.com/api/v3/klines",
        params={"symbol": "BTCUSDT", "interval": interval, "limit": CANDLES_LIMIT},
        headers=HEADERS, timeout=10
    )
    r.raise_for_status()
    raw = r.json()
    if not raw or isinstance(raw, dict):
        return pd.DataFrame()
    df = pd.DataFrame(raw, columns=[
        "timestamp","open","high","low","close","volume",
        "close_time","quote_volume","trades","taker_buy_base","taker_buy_quote","ignore"
    ])
    df = df[["timestamp","open","high","low","close","volume"]].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    for col in ["open","high","low","close","volume"]:
        df[col] = df[col].astype(float)
    return df.reset_index(drop=True)


def _from_okx(timeframe: str) -> pd.DataFrame:
    bar = TF_OKX.get(timeframe)
    if not bar:
        return pd.DataFrame()
    r = requests.get(
        "https://www.okx.com/api/v5/market/candles",
        params={"instId": "BTC-USDT", "bar": bar, "limit": CANDLES_LIMIT},
        headers=HEADERS, timeout=10
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != "0" or not data.get("data"):
        return pd.DataFrame()
    rows = list(reversed(data["data"]))
    df = pd.DataFrame(rows, columns=[
        "timestamp","open","high","low","close","vol","volCcy","volCcyQuote","confirm"
    ])
    df = df[["timestamp","open","high","low","close","vol"]].copy()
    df.columns = ["timestamp","open","high","low","close","volume"]
    df["timestamp"] = pd.to_datetime(df["timestamp"].astype(float), unit="ms")
    for col in ["open","high","low","close","volume"]:
        df[col] = df[col].astype(float)
    return df.reset_index(drop=True)


def _from_kraken(timeframe: str) -> pd.DataFrame:
    interval = TF_KRAKEN.get(timeframe)
    if not interval:
        return pd.DataFrame()
    r = requests.get(
        "https://api.kraken.com/0/public/OHLC",
        params={"pair": "XBTUSDT", "interval": interval},
        headers=HEADERS, timeout=10
    )
    r.raise_for_status()
    data = r.json()
    if data.get("error") or not data.get("result"):
        return pd.DataFrame()
    key = [k for k in data["result"] if k != "last"][0]
    rows = data["result"][key][-CANDLES_LIMIT:]
    df = pd.DataFrame(rows, columns=[
        "timestamp","open","high","low","close","vwap","volume","count"
    ])
    df = df[["timestamp","open","high","low","close","volume"]].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
    for col in ["open","high","low","close","volume"]:
        df[col] = df[col].astype(float)
    return df.reset_index(drop=True)


def get_ohlcv(timeframe: str) -> pd.DataFrame:
    """
    Завантажує OHLCV з автоматичним fallback.
    Порядок: Binance (Railway/США) → OKX (везде) → Kraken (резерв)
    """
    sources = [
        ("OKX",     _from_okx),
        ("Binance", _from_binance),
        ("Kraken",  _from_kraken),
    ]
    for name, fn in sources:
        try:
            df = fn(timeframe)
            if not df.empty and len(df) >= 50:
                return df
        except Exception as e:
            # 451 = Україна (очікувано локально), 403 = IP заблокований
            code = getattr(getattr(e, 'response', None), 'status_code', 0)
            if code in (451, 403):
                print(f"[DataFetcher] {name} недоступний з цього IP ({code}), пробую наступне...")
            else:
                print(f"[DataFetcher] {name} помилка ({timeframe}): {e}")
            continue

    print(f"[DataFetcher] ❌ Всі джерела недоступні для {timeframe}")
    return pd.DataFrame()

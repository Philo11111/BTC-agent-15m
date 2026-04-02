# ============================================================
#  indicators.py  —  розрахунок технічних індикаторів
# ============================================================

import pandas as pd
import numpy as np


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series, fast=12, slow=26, signal=9):
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger_bands(series: pd.Series, period=20, std_dev=2):
    middle = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower


def volume_sma(volume: pd.Series, period=20) -> pd.Series:
    return volume.rolling(period).mean()


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    """
    Додає всі індикатори до DataFrame.
    """
    close = df["close"]
    volume = df["volume"]

    # EMA тренд
    df["ema9"]  = ema(close, 9)
    df["ema21"] = ema(close, 21)
    df["ema50"] = ema(close, 50)
    df["ema200"] = ema(close, 200)

    # RSI
    df["rsi"] = rsi(close, 14)

    # MACD
    df["macd"], df["macd_signal"], df["macd_hist"] = macd(close)

    # Bollinger Bands
    df["bb_upper"], df["bb_mid"], df["bb_lower"] = bollinger_bands(close)

    # Volume
    df["vol_sma20"] = volume_sma(volume, 20)
    df["vol_ratio"] = volume / df["vol_sma20"]  # > 1.5 = підвищений обʼєм

    return df

# ============================================================
#  indicators.py  —  всі індикатори включно з Krajekis-стеком
# ============================================================

import pandas as pd
import numpy as np


# ── Базові функції ────────────────────────────────────────────

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def macd(series: pd.Series, fast=12, slow=26, signal=9):
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def bollinger_bands(series: pd.Series, period=20, std_dev=2):
    middle = series.rolling(period).mean()
    std = series.rolling(period).std()
    return middle + std_dev * std, middle, middle - std_dev * std

def volume_sma(volume: pd.Series, period=20) -> pd.Series:
    return volume.rolling(period).mean()


# ── Krajekis-стек ─────────────────────────────────────────────

def stoch_rsi(rsi_series: pd.Series, period=14) -> pd.Series:
    """StochRSI: де RSI знаходиться у своєму діапазоні (0-100)."""
    low = rsi_series.rolling(period).min()
    high = rsi_series.rolling(period).max()
    return (rsi_series - low) / (high - low + 1e-9) * 100

def atr(df: pd.DataFrame, period=14) -> pd.Series:
    """Average True Range — волатильність."""
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift()).abs(),
        (df['low'] - df['close'].shift()).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()

def adx(df: pd.DataFrame, period=14):
    """ADX + PDI + NDI — сила і напрямок тренду."""
    up = df['high'].diff()
    dn = -df['low'].diff()
    pdm = up.where((up > dn) & (up > 0), 0)
    ndm = dn.where((dn > up) & (dn > 0), 0)
    atr_ = atr(df, period)
    pdi = 100 * pdm.ewm(span=period, adjust=False).mean() / atr_
    ndi = 100 * ndm.ewm(span=period, adjust=False).mean() / atr_
    dx = 100 * (pdi - ndi).abs() / (pdi + ndi + 1e-9)
    adx_line = dx.ewm(span=period, adjust=False).mean()
    return adx_line, pdi, ndi

def obv(df: pd.DataFrame) -> pd.Series:
    """On-Balance Volume — тиск покупців/продавців."""
    sign = np.sign(df['close'].diff().fillna(0))
    return (sign * df['volume']).cumsum()

def cvd(df: pd.DataFrame) -> pd.Series:
    """Cumulative Volume Delta — апроксимація delta обсягу."""
    bull_vol = df['volume'] * (df['close'] - df['low']) / (df['high'] - df['low'] + 1e-9)
    bear_vol = df['volume'] * (df['high'] - df['close']) / (df['high'] - df['low'] + 1e-9)
    return (bull_vol - bear_vol).cumsum()

def vwap(df: pd.DataFrame) -> pd.Series:
    """VWAP — середня ціна зважена за обсягом (обнуляється щодня)."""
    typical = (df['high'] + df['low'] + df['close']) / 3
    # Групуємо по даті щоб VWAP обнулявся кожен день
    if 'timestamp' in df.columns:
        date_group = df['timestamp'].dt.date
        cum_tv = (typical * df['volume']).groupby(date_group).cumsum()
        cum_v = df['volume'].groupby(date_group).cumsum()
    else:
        cum_tv = (typical * df['volume']).cumsum()
        cum_v = df['volume'].cumsum()
    return cum_tv / cum_v

def heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """Heikin Ashi свічки — згладжують шум."""
    ha = pd.DataFrame(index=df.index)
    ha['close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    ha_open = np.zeros(len(df))
    ha_open[0] = (df['open'].iloc[0] + df['close'].iloc[0]) / 2
    for i in range(1, len(df)):
        ha_open[i] = (ha_open[i-1] + ha['close'].iloc[i-1]) / 2
    ha['open'] = ha_open
    ha['bull'] = ha['close'] > ha['open']
    return ha


# ── Головна функція ───────────────────────────────────────────

def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    """Розраховує всі індикатори і додає їх до DataFrame."""
    c = df['close']
    v = df['volume']

    # ── Класичний стек ────────────────────────
    df['ema9']   = ema(c, 9)
    df['ema21']  = ema(c, 21)
    df['ema50']  = ema(c, 50)
    df['ema200'] = ema(c, 200)
    df['rsi'] = rsi(c, 14)
    df['macd'], df['macd_signal'], df['macd_hist'] = macd(c)
    df['bb_upper'], df['bb_mid'], df['bb_lower'] = bollinger_bands(c)
    df['vol_sma20'] = volume_sma(v, 20)
    df['vol_ratio'] = v / df['vol_sma20']

    # ── Krajekis стек ─────────────────────────
    df['stoch_rsi'] = stoch_rsi(df['rsi'])
    df['atr'] = atr(df, 14)
    df['atr_pct'] = df['atr'] / c  # волатильність у %
    df['adx'], df['pdi'], df['ndi'] = adx(df, 14)
    df['obv'] = obv(df)
    df['obv_ema'] = ema(df['obv'], 21)
    df['cvd'] = cvd(df)
    df['cvd_ema'] = ema(df['cvd'], 21)
    df['vwap'] = vwap(df)
    df['vwap_dist'] = (c - df['vwap']) / df['vwap'] * 100  # % від VWAP

    # Heikin Ashi
    ha = heikin_ashi(df)
    df['ha_close'] = ha['close']
    df['ha_open']  = ha['open']
    df['ha_bull']  = ha['bull']

    # MACD histogram прискорення
    df['macd_accel'] = df['macd_hist'].diff()

    # Моментум
    df['mom4'] = c / c.shift(4) - 1   # за 1 год (4 свічки по 15м)
    df['mom8'] = c / c.shift(8) - 1   # за 2 год

    return df

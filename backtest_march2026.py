"""
Бектест BTC/USDT 15m — березень 2026
Запуск: python backtest_march2026.py
"""
import requests, time
import pandas as pd
import numpy as np

print("="*60)
print("  BTC BACKTEST — 15m — БЕРЕЗЕНЬ 2026")
print("="*60)

# ── 1. Завантаження даних ─────────────────────────────────────
print("\n[1/3] Завантажую свічки з Binance...")

START = 1740787200000   # 1 берез. 2026 00:00 UTC
END   = 1743465600000   # 1 квіт.  2026 00:00 UTC
INTERVAL = "15m"
URL = "https://api.binance.com/api/v3/klines"

all_candles = []
t = START
batch = 0
while t < END:
    batch += 1
    resp = requests.get(URL, params={"symbol":"BTCUSDT","interval":INTERVAL,
                                      "startTime":t,"limit":1000}, timeout=15)
    data = resp.json()
    if not isinstance(data, list) or not data:
        break
    all_candles.extend(data)
    t = data[-1][0] + 900_000   # +15 хв
    if len(data) < 1000:
        break
    print(f"   блок {batch} завантажено ({len(all_candles)} свічок)...")
    time.sleep(0.4)

df = pd.DataFrame(all_candles,
    columns=["ts","open","high","low","close","vol",
             "ct","qv","nt","tbbv","tbqv","ign"])
df = df[["ts","open","high","low","close","vol"]].copy()
df["ts"] = pd.to_datetime(df["ts"], unit="ms")
for c in ["open","high","low","close","vol"]:
    df[c] = df[c].astype(float)
df = df[(df["ts"] >= "2026-03-01") & (df["ts"] < "2026-04-01")].reset_index(drop=True)

print(f"   Завантажено {len(df)} свічок з {df['ts'].iloc[0].date()} по {df['ts'].iloc[-1].date()}")
price_start = df['close'].iloc[0]
price_end   = df['close'].iloc[-1]
pct = (price_end - price_start) / price_start * 100
print(f"   Старт:  ${price_start:,.0f}")
print(f"   Фінал:  ${price_end:,.0f}")
print(f"   Зміна:  {pct:+.1f}%")

# ── 2. Індикатори ─────────────────────────────────────────────
print("\n[2/3] Розраховую індикатори...")

close = df["close"]
vol   = df["vol"]

# EMA
df["ema9"]  = close.ewm(span=9,  adjust=False).mean()
df["ema21"] = close.ewm(span=21, adjust=False).mean()

# RSI-14
delta = close.diff()
gain  = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
loss  = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
df["rsi"] = 100 - 100/(1 + gain/loss.replace(0, np.nan))

# MACD
macd_line   = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
signal_line = macd_line.ewm(span=9, adjust=False).mean()
df["macd_bull"] = macd_line > signal_line

# Bollinger Bands 20
roll = close.rolling(20)
df["bb_upper"] = roll.mean() + 2 * roll.std()
df["bb_lower"] = roll.mean() - 2 * roll.std()

# Volume SMA20
df["vol_sma20"] = vol.rolling(20).mean()
df["high_vol"]  = vol > 1.5 * df["vol_sma20"]

# Сигнальні стовпці
df["sig_rsi_bull"]  = df["rsi"] <= 45
df["sig_rsi_bear"]  = df["rsi"] >= 55
df["sig_macd_bull"] = df["macd_bull"]
df["sig_macd_bear"] = ~df["macd_bull"]
df["sig_ema_bull"]  = df["ema9"] > df["ema21"]
df["sig_ema_bear"]  = df["ema9"] < df["ema21"]
df["sig_bb_bull"]   = df["low"]  <= df["bb_lower"]
df["sig_bb_bear"]   = df["high"] >= df["bb_upper"]

print("   Готово.")

# ── 3. Бектест ────────────────────────────────────────────────
print("\n[3/3] Бектест (горизонт: 1 год = 4 свічки)...")

HORIZONS = {
    "30хв (2 свічки)": 2,
    "1год  (4 свічки)": 4,
    "2год  (8 свічок)": 8,
    "4год (16 свічок)": 16,
}

COMBOS = [
    ("RSI зона",               "sig_rsi_bull",  "sig_rsi_bear",  False),
    ("MACD напрямок",          "sig_macd_bull", "sig_macd_bear", False),
    ("EMA 9/21",               "sig_ema_bull",  "sig_ema_bear",  False),
    ("Bollinger відбій",       "sig_bb_bull",   "sig_bb_bear",   False),
    ("RSI + MACD",             "sig_rsi_bull",  "sig_rsi_bear",  False,  "sig_macd_bull","sig_macd_bear"),
    ("RSI + EMA",              "sig_rsi_bull",  "sig_rsi_bear",  False,  "sig_ema_bull","sig_ema_bear"),
    ("MACD + EMA",             "sig_macd_bull", "sig_macd_bear", False,  "sig_ema_bull","sig_ema_bear"),
    ("RSI + MACD + EMA",       "sig_rsi_bull",  "sig_rsi_bear",  False,  "sig_macd_bull","sig_macd_bear","sig_ema_bull","sig_ema_bear"),
    ("RSI + Обʼєм↑",          "sig_rsi_bull",  "sig_rsi_bear",  True),
    ("MACD + Обʼєм↑",         "sig_macd_bull", "sig_macd_bear", True),
    ("EMA + Обʼєм↑",          "sig_ema_bull",  "sig_ema_bear",  True),
    ("RSI + MACD + Обʼєм↑",   "sig_rsi_bull",  "sig_rsi_bear",  True,   "sig_macd_bull","sig_macd_bear"),
    ("RSI + EMA + Обʼєм↑",    "sig_rsi_bull",  "sig_rsi_bear",  True,   "sig_ema_bull","sig_ema_bear"),
    ("MACD + EMA + Обʼєм↑",   "sig_macd_bull", "sig_macd_bear", True,   "sig_ema_bull","sig_ema_bear"),
    ("RSI+MACD+EMA+Обʼєм↑",   "sig_rsi_bull",  "sig_rsi_bear",  True,   "sig_macd_bull","sig_macd_bear","sig_ema_bull","sig_ema_bear"),
]

def run_backtest(df, h):
    results = []
    close_arr = df["close"].values
    N = len(df)
    for combo in COMBOS:
        name   = combo[0]
        b_col  = combo[1]
        be_col = combo[2]
        use_vol= combo[3]
        extra  = combo[4:] if len(combo) > 4 else []

        total, correct, longs, long_c, shorts, short_c = 0, 0, 0, 0, 0, 0
        for i in range(50, N - h):
            if pd.isna(df["rsi"].iloc[i]):
                continue
            is_bull = bool(df[b_col].iloc[i])
            is_bear = bool(df[be_col].iloc[i])
            # extra умови
            for j in range(0, len(extra), 2):
                if j+1 < len(extra):
                    is_bull = is_bull and bool(df[extra[j]].iloc[i])
                    is_bear = is_bear and bool(df[extra[j+1]].iloc[i])
            if not is_bull and not is_bear:
                continue
            direction = "U" if is_bull else "D"
            if use_vol and not df["high_vol"].iloc[i]:
                continue
            future = close_arr[i + h]
            current = close_arr[i]
            win = (future > current) if direction == "U" else (future < current)
            total += 1; correct += int(win)
            if direction == "U": longs += 1; long_c += int(win)
            else: shorts += 1; short_c += int(win)
        wr  = round(correct / total * 100, 1) if total else 0
        lwr = round(long_c / longs * 100, 1) if longs else None
        swr = round(short_c / shorts * 100, 1) if shorts else None
        results.append({"name": name, "total": total, "correct": correct,
                         "wr": wr, "longs": longs, "lwr": lwr,
                         "shorts": shorts, "swr": swr})
    return sorted(results, key=lambda x: x["wr"], reverse=True)

# ── Вивід ─────────────────────────────────────────────────────
def bar(pct):
    n = int((pct - 40) / 1.5) if pct > 40 else 0
    n = max(0, min(n, 20))
    color = "\033[92m" if pct >= 62 else "\033[93m" if pct >= 55 else "\033[91m"
    return color + "█" * n + "\033[0m"

medals = ["🥇","🥈","🥉"]

for label, h in HORIZONS.items():
    print(f"\n{'='*60}")
    print(f"  ГОРИЗОНТ: {label}")
    print(f"{'='*60}")
    print(f"  {'КОМБІНАЦІЯ':<30} {'СИГН':>5} {'WR%':>6}   {'ЛОНГ%':>6}  {'ШОРТ%':>6}  ГРАФІК")
    print(f"  {'-'*30} {'-'*5} {'-'*6}   {'-'*6}  {'-'*6}  {'-'*22}")
    res = run_backtest(df, h)
    for idx, r in enumerate(res):
        m = medals[idx] if idx < 3 else "  "
        lw = f"{r['lwr']:>5.1f}%" if r['lwr'] else "   —  "
        sw = f"{r['swr']:>5.1f}%" if r['swr'] else "   —  "
        b  = bar(r["wr"])
        print(f"  {m} {r['name']:<28} {r['total']:>5}  {r['wr']:>5.1f}%   {lw}  {sw}  {b} {r['wr']:.0f}%")

print("\n" + "="*60)
print("  ЛЕГЕНДА")
print("="*60)
print("  WR% >= 62%  = \033[92m██\033[0m відмінний сигнал")
print("  WR% 55-62%  = \033[93m██\033[0m хороший сигнал")
print("  WR% < 55%   = \033[91m██\033[0m слабкий сигнал (близько до рандому 50%)")
print("\n  Визначення:")
print("  RSI бичачий = RSI <= 45 | RSI ведмежий = RSI >= 55")
print("  MACD — лінія MACD vs сигнальна лінія")
print("  EMA — EMA9 vs EMA21")
print("  Обʼєм↑ — поточний обʼєм > 1.5x SMA20")
print("="*60)
print("\n  Готово! Результати вище показують які комбінації")
print("  індикаторів давали найкращі сигнали у березні 2026.")

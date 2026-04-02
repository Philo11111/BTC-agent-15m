# ============================================================
#  signal_engine.py  —  логіка генерації якісних сигналів
# ============================================================
#
#  Система балів (максимум 6 балів):
#
#  1. EMA Cross       (+1) — EMA9 перетинає EMA21
#  2. EMA Trend       (+1) — ціна вище/нижче EMA50 і EMA200
#  3. RSI Zone        (+1) — RSI виходить з перепроданості/перекупленості
#  4. MACD Cross      (+1) — MACD перетинає сигнальну лінію
#  5. Bollinger       (+1) — відбиття від смуги Боллінджера
#  6. Volume Confirm  (+1) — обʼєм вище середнього (x1.5)
#
#  Сигнал спрацьовує тільки якщо балів >= MIN_SCORE (за замовч. 4)
# ============================================================

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from config import MIN_SCORE, SIGNAL_COOLDOWN

# Зберігаємо час останнього сигналу по кожному TF
_last_signal_time: dict[str, datetime] = {}


def analyze(df: pd.DataFrame, timeframe: str) -> Optional[dict]:
    """
    Аналізує останню закриту свічку і повертає сигнал або None.
    """
    if df is None or len(df) < 60:
        return None

    # Беремо останні 3 свічки ([-1] — поточна, [-2] — попередня)
    cur = df.iloc[-1]
    prev = df.iloc[-2]
    prev2 = df.iloc[-3]

    score = 0
    reasons = []
    direction = None  # "UP" або "DOWN"

    bull_score = 0
    bear_score = 0
    bull_reasons = []
    bear_reasons = []

    # ── 1. EMA Cross ────────────────────────────────────────
    ema_cross_bull = prev["ema9"] <= prev["ema21"] and cur["ema9"] > cur["ema21"]
    ema_cross_bear = prev["ema9"] >= prev["ema21"] and cur["ema9"] < cur["ema21"]

    if ema_cross_bull:
        bull_score += 1
        bull_reasons.append("📈 EMA9 перетнула EMA21 вгору")
    if ema_cross_bear:
        bear_score += 1
        bear_reasons.append("📉 EMA9 перетнула EMA21 вниз")

    # ── 2. EMA Trend (ціна відносно EMA50/EMA200) ───────────
    price = cur["close"]
    if price > cur["ema50"] and cur["ema50"] > cur["ema200"]:
        bull_score += 1
        bull_reasons.append("✅ Ціна вище EMA50 і EMA200 (бичачий тренд)")
    elif price < cur["ema50"] and cur["ema50"] < cur["ema200"]:
        bear_score += 1
        bear_reasons.append("🔻 Ціна нижче EMA50 і EMA200 (ведмежий тренд)")

    # ── 3. RSI Zone ─────────────────────────────────────────
    rsi_cur  = cur["rsi"]
    rsi_prev = prev["rsi"]

    if rsi_prev < 35 and rsi_cur >= 35:  # вихід з перепроданості
        bull_score += 1
        bull_reasons.append(f"💚 RSI виходить з перепроданості ({rsi_cur:.1f})")
    elif rsi_prev > 65 and rsi_cur <= 65:  # вихід з перекупленості
        bear_score += 1
        bear_reasons.append(f"🔴 RSI виходить з перекупленості ({rsi_cur:.1f})")
    elif 40 <= rsi_cur <= 60:
        pass  # нейтральна зона — нічого не додаємо
    elif rsi_cur < 40:
        bull_score += 0.5  # слабкий бичачий сигнал
    elif rsi_cur > 60:
        bear_score += 0.5

    # ── 4. MACD Cross ────────────────────────────────────────
    macd_cross_bull = prev["macd"] <= prev["macd_signal"] and cur["macd"] > cur["macd_signal"]
    macd_cross_bear = prev["macd"] >= prev["macd_signal"] and cur["macd"] < cur["macd_signal"]

    if macd_cross_bull:
        bull_score += 1
        bull_reasons.append("📊 MACD перетнув сигнальну лінію вгору")
    if macd_cross_bear:
        bear_score += 1
        bear_reasons.append("📊 MACD перетнув сигнальну лінію вниз")

    # ── 5. Bollinger Bands ───────────────────────────────────
    # Відбиття від нижньої смуги (бичаче)
    if prev["low"] <= prev["bb_lower"] and cur["close"] > cur["bb_lower"]:
        bull_score += 1
        bull_reasons.append(f"🎯 Відбиття від нижньої смуги Боллінджера")
    # Відбиття від верхньої смуги (ведмеже)
    elif prev["high"] >= prev["bb_upper"] and cur["close"] < cur["bb_upper"]:
        bear_score += 1
        bear_reasons.append(f"🎯 Відбиття від верхньої смуги Боллінджера")

    # ── 6. Volume Confirmation ───────────────────────────────
    vol_ratio = cur["vol_ratio"]
    if vol_ratio >= 1.5:
        label = f"🔊 Підвищений обʼєм ({vol_ratio:.1f}x від норми)"
        bull_score += 1
        bear_score += 1
        bull_reasons.append(label)
        bear_reasons.append(label)

    # ── Визначаємо напрямок ──────────────────────────────────
    if bull_score >= MIN_SCORE and bull_score > bear_score:
        direction = "UP"
        score = bull_score
        reasons = bull_reasons
    elif bear_score >= MIN_SCORE and bear_score > bull_score:
        direction = "DOWN"
        score = bear_score
        reasons = bear_reasons
    else:
        return None  # Немає якісного сигналу

    # ── Кулдаун ──────────────────────────────────────────────
    cooldown_min = SIGNAL_COOLDOWN.get(timeframe, 60)
    last = _last_signal_time.get(timeframe)
    if last and datetime.utcnow() - last < timedelta(minutes=cooldown_min):
        return None  # Ще діє кулдаун

    _last_signal_time[timeframe] = datetime.utcnow()

    return {
        "timeframe": timeframe,
        "direction": direction,
        "score": score,
        "max_score": 6,
        "reasons": reasons,
        "price": price,
        "rsi": round(rsi_cur, 2),
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }

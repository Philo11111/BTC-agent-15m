# ============================================================
#  signal_engine.py  —  дві стратегії: Класична + Krajekis
# ============================================================
#
#  СТРАТЕГІЯ 1 — КЛАСИЧНА (перевірка кожну хвилину, всі TF)
#  ┌─────────────────────────────────────────────────────┐
#  │  EMA Cross (+1) │ EMA Trend (+1) │ RSI Zone (+1)   │
#  │  MACD Cross (+1)│ Bollinger (+1) │ Volume (+1)     │
#  │  Сигнал при скорі >= MIN_SCORE (за замовч. 4/6)    │
#  └─────────────────────────────────────────────────────┘
#
#  СТРАТЕГІЯ 2 — KRAJEKIS (перевірка кожні 15 хв, тільки 15м TF)
#  ┌─────────────────────────────────────────────────────┐
#  │  VWAP reclaim/reject  — ціна повертається до VWAP  │
#  │  Heikin Ashi trend    — 2+ HA свічки в напрямку    │
#  │  MACD hist accel      — прискорення гістограми      │
#  │  CVD confirmation     — обсяг підтверджує рух       │
#  │  StochRSI filter      — не в нейтральній зоні       │
#  │  ADX > 15             — є тренд (не боковик)        │
#  │  Session filter       — London або NY open          │
#  │  Weekday only         — без вихідних                │
#  └─────────────────────────────────────────────────────┘
# ============================================================

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from config import MIN_SCORE, SIGNAL_COOLDOWN

_last_signal_time: dict[str, datetime] = {}


# ══════════════════════════════════════════════════════════════
#  СТРАТЕГІЯ 1 — КЛАСИЧНА
# ══════════════════════════════════════════════════════════════

def analyze_classic(df: pd.DataFrame, timeframe: str) -> Optional[dict]:
    """Класична стратегія: EMA + RSI + MACD + Bollinger + Volume."""
    if df is None or len(df) < 60:
        return None

    cur  = df.iloc[-1]
    prev = df.iloc[-2]

    bull_score = 0
    bear_score = 0
    bull_reasons = []
    bear_reasons = []

    # 1. EMA Cross
    if prev['ema9'] <= prev['ema21'] and cur['ema9'] > cur['ema21']:
        bull_score += 1
        bull_reasons.append("📈 EMA9 перетнула EMA21 вгору")
    if prev['ema9'] >= prev['ema21'] and cur['ema9'] < cur['ema21']:
        bear_score += 1
        bear_reasons.append("📉 EMA9 перетнула EMA21 вниз")

    # 2. EMA Trend
    if cur['close'] > cur['ema50'] and cur['ema50'] > cur['ema200']:
        bull_score += 1
        bull_reasons.append("✅ Ціна вище EMA50/200 (бичачий тренд)")
    elif cur['close'] < cur['ema50'] and cur['ema50'] < cur['ema200']:
        bear_score += 1
        bear_reasons.append("🔻 Ціна нижче EMA50/200 (ведмежий тренд)")

    # 3. RSI Zone
    rsi_cur = cur['rsi']
    rsi_prev = prev['rsi']
    if rsi_prev < 35 and rsi_cur >= 35:
        bull_score += 1
        bull_reasons.append(f"💚 RSI виходить з перепроданості ({rsi_cur:.1f})")
    elif rsi_prev > 65 and rsi_cur <= 65:
        bear_score += 1
        bear_reasons.append(f"🔴 RSI виходить з перекупленості ({rsi_cur:.1f})")

    # 4. MACD Cross
    if prev['macd'] <= prev['macd_signal'] and cur['macd'] > cur['macd_signal']:
        bull_score += 1
        bull_reasons.append("📊 MACD перетнув сигнальну лінію вгору")
    if prev['macd'] >= prev['macd_signal'] and cur['macd'] < cur['macd_signal']:
        bear_score += 1
        bear_reasons.append("📊 MACD перетнув сигнальну лінію вниз")

    # 5. Bollinger відбиття
    if prev['low'] <= prev['bb_lower'] and cur['close'] > cur['bb_lower']:
        bull_score += 1
        bull_reasons.append("🎯 Відбиття від нижньої смуги Боллінджера")
    elif prev['high'] >= prev['bb_upper'] and cur['close'] < cur['bb_upper']:
        bear_score += 1
        bear_reasons.append("🎯 Відбиття від верхньої смуги Боллінджера")

    # 6. Volume
    vol_ratio = cur['vol_ratio']
    if vol_ratio >= 1.5:
        label = f"🔊 Підвищений обʼєм ({vol_ratio:.1f}x)"
        bull_score += 1
        bear_score += 1
        bull_reasons.append(label)
        bear_reasons.append(label)

    # Визначаємо напрямок
    if bull_score >= MIN_SCORE and bull_score > bear_score:
        direction, score, reasons = 'UP', bull_score, bull_reasons
    elif bear_score >= MIN_SCORE and bear_score > bull_score:
        direction, score, reasons = 'DOWN', bear_score, bear_reasons
    else:
        return None

    # Кулдаун
    key = f"classic_{timeframe}"
    cooldown = SIGNAL_COOLDOWN.get(timeframe, 60)
    last = _last_signal_time.get(key)
    if last and datetime.utcnow() - last < timedelta(minutes=cooldown):
        return None
    _last_signal_time[key] = datetime.utcnow()

    return {
        'strategy': 'classic',
        'strategy_label': '🔵 Класична',
        'timeframe': timeframe,
        'direction': direction,
        'score': score,
        'max_score': 6,
        'reasons': reasons,
        'price': cur['close'],
        'rsi': round(rsi_cur, 2),
        'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
    }


# ══════════════════════════════════════════════════════════════
#  СТРАТЕГІЯ 2 — KRAJEKIS
# ══════════════════════════════════════════════════════════════

def _get_session(hour_utc: int) -> str:
    if 8 <= hour_utc <= 13:
        return 'london'
    elif 14 <= hour_utc <= 20:
        return 'ny'
    else:
        return 'asia'

def _is_active_session(hour_utc: int) -> bool:
    """London open (8-11) і NY open (14-17) UTC — найкращі сесії."""
    return (8 <= hour_utc <= 11) or (14 <= hour_utc <= 17)

def analyze_krajekis(df: pd.DataFrame) -> Optional[dict]:
    """
    Krajekis-стратегія для 15м таймфрейму.
    Перевіряє: VWAP + HA + MACD accel + CVD + StochRSI + ADX + сесія.
    """
    if df is None or len(df) < 60:
        return None

    cur   = df.iloc[-1]
    prev  = df.iloc[-2]
    prev2 = df.iloc[-3]

    now_utc = datetime.utcnow()

    # ── Фільтр: вихідні ──────────────────────────────────────
    if now_utc.weekday() >= 5:  # субота=5, неділя=6
        return None

    # ── Фільтр: активна сесія ────────────────────────────────
    hour = now_utc.hour
    session = _get_session(hour)
    if not _is_active_session(hour):
        return None

    # ── Фільтр: мінімальна волатильність ─────────────────────
    if cur['atr_pct'] < 0.001:  # менше 0.1% на свічку = сплячий ринок
        return None

    # ── Фільтр: ADX > 15 (є тренд) ───────────────────────────
    if cur['adx'] < 15:
        return None

    price = cur['close']
    bull_score = 0
    bear_score = 0
    bull_reasons = []
    bear_reasons = []

    # 1. VWAP reclaim/reject (ключовий сигнал)
    vwap_prev = prev['vwap_dist']
    vwap_cur  = cur['vwap_dist']

    vwap_reclaim = vwap_prev < -0.15 and vwap_cur >= -0.05   # повернення знизу
    vwap_reject  = vwap_prev > 0.15  and vwap_cur <= 0.05    # відкидання зверху

    if vwap_reclaim:
        bull_score += 2  # ключовий сигнал — вага 2
        bull_reasons.append(f"💎 VWAP reclaim (ціна повернулась до VWAP)")
    if vwap_reject:
        bear_score += 2
        bear_reasons.append(f"💎 VWAP reject (ціна відкинута від VWAP)")

    # Додаткові бали якщо просто нижче/вище VWAP
    if not vwap_reclaim and vwap_cur < -0.2:
        bull_score += 1
        bull_reasons.append(f"📍 Ціна нижче VWAP ({vwap_cur:.2f}%)")
    if not vwap_reject and vwap_cur > 0.2:
        bear_score += 1
        bear_reasons.append(f"📍 Ціна вище VWAP (+{vwap_cur:.2f}%)")

    # 2. Heikin Ashi тренд
    ha_bull_now  = bool(cur['ha_bull'])
    ha_bull_prev = bool(prev['ha_bull'])
    ha_bull_prev2 = bool(prev2['ha_bull'])

    ha_reversal_up   = ha_bull_now and not ha_bull_prev
    ha_reversal_down = not ha_bull_now and ha_bull_prev
    ha_trend_up   = ha_bull_now and ha_bull_prev
    ha_trend_down = not ha_bull_now and not ha_bull_prev

    if ha_reversal_up:
        bull_score += 2
        bull_reasons.append("🕯 HA розворот вгору (перша бичача свічка)")
    elif ha_trend_up:
        bull_score += 1
        bull_reasons.append("🕯 HA тренд вгору (2+ бичачих свічки)")

    if ha_reversal_down:
        bear_score += 2
        bear_reasons.append("🕯 HA розворот вниз (перша ведмежа свічка)")
    elif ha_trend_down:
        bear_score += 1
        bear_reasons.append("🕯 HA тренд вниз (2+ ведмежих свічки)")

    # 3. MACD histogram прискорення
    macd_accel = cur['macd_accel']
    if macd_accel > 0 and cur['macd_hist'] < 0:
        bull_score += 1
        bull_reasons.append("📊 MACD hist прискорюється вгору (з від'ємної зони)")
    elif macd_accel > 0 and cur['macd_hist'] > 0:
        bull_score += 1
        bull_reasons.append("📊 MACD hist зростає у позитивній зоні")
    if macd_accel < 0 and cur['macd_hist'] > 0:
        bear_score += 1
        bear_reasons.append("📊 MACD hist сповільнюється (з позитивної зони)")
    elif macd_accel < 0 and cur['macd_hist'] < 0:
        bear_score += 1
        bear_reasons.append("📊 MACD hist падає у від'ємній зоні")

    # 4. CVD підтвердження
    if cur['cvd'] > cur['cvd_ema']:
        bull_score += 1
        bull_reasons.append("🔵 CVD бичачий (більше покупців ніж продавців)")
    else:
        bear_score += 1
        bear_reasons.append("🔴 CVD ведмежий (більше продавців ніж покупців)")

    # 5. StochRSI фільтр
    stoch = cur['stoch_rsi']
    stoch_prev = prev['stoch_rsi']
    if stoch_prev < 20 and stoch > 20:
        bull_score += 1
        bull_reasons.append(f"💚 StochRSI виходить з перепроданості ({stoch:.0f})")
    elif stoch_prev > 80 and stoch < 80:
        bear_score += 1
        bear_reasons.append(f"🔴 StochRSI виходить з перекупленості ({stoch:.0f})")

    # 6. OBV підтвердження
    if cur['obv'] > cur['obv_ema']:
        bull_score += 1
        bull_reasons.append("📈 OBV зростає (обʼєм підтверджує ріст)")
    else:
        bear_score += 1
        bear_reasons.append("📉 OBV падає (обʼєм підтверджує падіння)")

    # ── Визначаємо напрямок ───────────────────────────────────
    SESSION_LABELS = {'london': 'London open 🇬🇧', 'ny': 'NY open 🇺🇸', 'asia': 'Asia'}
    session_label = SESSION_LABELS.get(session, session)

    MIN_KRAJEKIS_SCORE = 5  # вищий поріг для якості

    if bull_score >= MIN_KRAJEKIS_SCORE and bull_score > bear_score:
        direction, score, reasons = 'UP', bull_score, bull_reasons
    elif bear_score >= MIN_KRAJEKIS_SCORE and bear_score > bull_score:
        direction, score, reasons = 'DOWN', bear_score, bear_reasons
    else:
        return None

    # ── Кулдаун 45 хвилин для Krajekis ───────────────────────
    key = 'krajekis_15m'
    last = _last_signal_time.get(key)
    if last and datetime.utcnow() - last < timedelta(minutes=45):
        return None
    _last_signal_time[key] = datetime.utcnow()

    return {
        'strategy': 'krajekis',
        'strategy_label': '🟣 Krajekis',
        'timeframe': '15m',
        'direction': direction,
        'score': score,
        'max_score': 9,
        'reasons': reasons,
        'price': price,
        'rsi': round(cur['rsi'], 2),
        'session': session_label,
        'vwap_dist': round(vwap_cur, 2),
        'adx': round(cur['adx'], 1),
        'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
    }


# ══════════════════════════════════════════════════════════════
#  Єдина точка входу (зворотна сумісність з main.py)
# ══════════════════════════════════════════════════════════════

def analyze(df: pd.DataFrame, timeframe: str) -> Optional[dict]:
    """Запускає класичну стратегію. Використовується в main.py."""
    return analyze_classic(df, timeframe)

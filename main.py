# ============================================================
#  main.py  —  дві стратегії в паралельних потоках
# ============================================================

import requests
import time
import threading
from datetime import datetime

from config import (
    TIMEFRAMES, TELEGRAM_TOKEN,
    CHECK_INTERVAL_CLASSIC, CHECK_INTERVAL_KRAJEKIS,
    KRAJEKIS_TIMEFRAME
)
from data_fetcher import get_ohlcv
from indicators import compute_all
from signal_engine import analyze_classic, analyze_krajekis
from telegram_bot import send_signal, send_startup_message
from web_app import run_web, update_state, add_signal


def format_signal_message(signal: dict) -> str:
    direction = signal['direction']
    emoji = '🟢' if direction == 'UP' else '🔴'
    dir_text = 'ВГОРУ (LONG)' if direction == 'UP' else 'ВНИЗ (SHORT)'
    polymarket = (
        '👉 Polymarket: ставь на *вище* поточної ціни'
        if direction == 'UP' else
        '👉 Polymarket: ставь на *нижче* поточної ціни'
    )
    score = signal['score']
    max_score = signal['max_score']
    stars = '⭐' * min(int(score), 6)
    quality = 'ВІДМІННИЙ' if score >= max_score * 0.8 else 'ХОРОШИЙ' if score >= max_score * 0.6 else 'СЕРЕДНІЙ'
    reasons_text = '\n'.join(f'  • {r}' for r in signal['reasons'])
    extra = ''
    if signal.get('strategy') == 'krajekis':
        extra = (
            f"🕐 Сесія: `{signal.get('session', '—')}`\n"
            f"📏 VWAP dist: `{signal.get('vwap_dist', 0):+.2f}%`\n"
            f"💪 ADX: `{signal.get('adx', 0):.1f}`\n"
        )
    return (
        f"{emoji} *BTC СИГНАЛ — {dir_text}*\n"
        f"{signal.get('strategy_label', '')} | `{signal['timeframe']}`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Ціна: `${signal['price']:,.2f}`\n"
        f"📊 RSI: `{signal['rsi']}`\n"
        f"{extra}"
        f"🏆 Якість: {stars} ({quality})\n"
        f"🎯 Скор: `{score}/{max_score}`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"*Причини:*\n{reasons_text}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{polymarket}\n"
        f"⏰ {signal['timestamp']}"
    )


def send_formatted_signal(signal: dict):
    from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
    text = format_signal_message(signal)
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=10
        )
    except Exception as e:
        print(f"[Signal] Помилка: {e}")


def get_tf_indicators(df):
    if df is None or df.empty:
        return []
    cur = df.iloc[-1]
    rsi_val = cur['rsi']
    return [
        {"name": "RSI (14)",     "value": f"{rsi_val:.1f}", "cls": "bull" if rsi_val < 40 else "bear" if rsi_val > 60 else "neu"},
        {"name": "EMA9/21",      "value": "Бик" if cur['ema9'] > cur['ema21'] else "Ведмідь", "cls": "bull" if cur['ema9'] > cur['ema21'] else "bear"},
        {"name": "MACD",         "value": "Бик" if cur['macd'] > cur['macd_signal'] else "Ведмідь", "cls": "bull" if cur['macd'] > cur['macd_signal'] else "bear"},
        {"name": "Тренд EMA200", "value": "Вище" if cur['close'] > cur['ema200'] else "Нижче", "cls": "bull" if cur['close'] > cur['ema200'] else "bear"},
        {"name": "Обʼєм",       "value": f"{cur['vol_ratio']:.2f}x", "cls": "bull" if cur['vol_ratio'] >= 1.5 else "neu"},
        {"name": "VWAP dist",    "value": f"{cur['vwap_dist']:+.2f}%", "cls": "bull" if cur['vwap_dist'] < -0.2 else "bear" if cur['vwap_dist'] > 0.2 else "neu"},
        {"name": "ADX",          "value": f"{cur['adx']:.1f}", "cls": "bull" if cur['adx'] > 25 else "neu" if cur['adx'] > 15 else "bear"},
        {"name": "StochRSI",     "value": f"{cur['stoch_rsi']:.0f}", "cls": "bull" if cur['stoch_rsi'] < 20 else "bear" if cur['stoch_rsi'] > 80 else "neu"},
    ]


def classic_loop():
    print("[Classic] Запускаю класичну стратегію...")
    send_startup_message()
    while True:
        try:
            tf_indicators = {}
            current_price = None
            for tf in TIMEFRAMES:
                print(f"[Classic] Перевіряю {tf}...")
                df = get_ohlcv(tf)
                if df.empty:
                    continue
                df = compute_all(df)
                current_price = df.iloc[-1]['close']
                tf_indicators[tf] = get_tf_indicators(df)
                signal = analyze_classic(df, tf)
                if signal:
                    print(f"[Classic] 🔔 {signal['direction']} на {tf} (скор {signal['score']})")
                    send_formatted_signal(signal)
                    add_signal(signal)
                else:
                    print(f"[Classic] {tf} — немає сигналу")
            if current_price:
                update_state(current_price, tf_indicators)
        except Exception as e:
            print(f"[Classic] Помилка: {e}")
        print(f"[Classic] Чекаю {CHECK_INTERVAL_CLASSIC}с...\n")
        time.sleep(CHECK_INTERVAL_CLASSIC)


def krajekis_loop():
    print("[Krajekis] Запускаю Krajekis-стратегію (15м, London+NY)...")
    time.sleep(10)
    while True:
        try:
            print(f"[Krajekis] Перевіряю 15м...")
            df = get_ohlcv(KRAJEKIS_TIMEFRAME)
            if not df.empty:
                df = compute_all(df)
                signal = analyze_krajekis(df)
                if signal:
                    print(f"[Krajekis] 🔔 {signal['direction']} (скор {signal['score']}/{signal['max_score']})")
                    send_formatted_signal(signal)
                    add_signal(signal)
                else:
                    print(f"[Krajekis] 15м — немає сигналу")
        except Exception as e:
            print(f"[Krajekis] Помилка: {e}")
        print(f"[Krajekis] Чекаю {CHECK_INTERVAL_KRAJEKIS//60} хв...\n")
        time.sleep(CHECK_INTERVAL_KRAJEKIS)


def telegram_polling():
    from chat import handle_chat_update
    offset = 0
    print("[Chat] Polling запущено...")
    while True:
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                params={"offset": offset, "timeout": 10},
                timeout=15
            )
            data = resp.json()
            if not data.get("ok"):
                print(f"[Chat] Помилка: {data}")
                time.sleep(5)
                continue
            updates = data.get("result", [])
            if updates:
                print(f"[Chat] 📨 Нових: {len(updates)}")
            for upd in updates:
                offset = upd["update_id"] + 1
                handle_chat_update(upd)
        except Exception as e:
            print(f"[Polling] {e}")
            time.sleep(3)
        time.sleep(0.5)


if __name__ == "__main__":
    print("=" * 52)
    print("  BTC Signal Bot — Classic + Krajekis")
    print("=" * 52)

    threading.Thread(target=run_web, daemon=True).start()
    print("[Web] Дашборд: http://localhost:5000")

    threading.Thread(target=telegram_polling, daemon=True).start()
    threading.Thread(target=krajekis_loop, daemon=True).start()

    classic_loop()

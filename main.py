# ============================================================
#  main.py  —  головний файл, запускає всі компоненти
# ============================================================

import time
import threading
from datetime import datetime

from config import TIMEFRAMES, CHECK_INTERVAL
from data_fetcher import get_ohlcv
from indicators import compute_all
from signal_engine import analyze
from telegram_bot import send_signal, send_startup_message
from web_app import run_web, update_state, add_signal


def classify_indicator(value, low_bad, low_good, high_good, high_bad):
    """Повертає клас і текст для відображення на дашборді."""
    if value <= low_bad or value >= high_bad:
        return "bear", f"{value:.1f}"
    elif low_good <= value <= high_good:
        return "bull", f"{value:.1f}"
    else:
        return "neu", f"{value:.1f}"


def get_tf_indicators(df):
    """Готує дані індикаторів для веб-дашборду."""
    if df is None or df.empty:
        return []
    cur = df.iloc[-1]
    prev = df.iloc[-2]

    rsi_val = cur["rsi"]
    rsi_cls = "bull" if rsi_val < 40 else "bear" if rsi_val > 60 else "neu"

    macd_cls = "bull" if cur["macd"] > cur["macd_signal"] else "bear"

    ema_cls = "bull" if cur["ema9"] > cur["ema21"] else "bear"

    vol_cls = "bull" if cur["vol_ratio"] >= 1.5 else "neu"

    trend_cls = "bull" if cur["close"] > cur["ema200"] else "bear"

    return [
        {"name": "RSI (14)",     "value": f"{rsi_val:.1f}", "cls": rsi_cls},
        {"name": "EMA9/21",      "value": "Бик" if ema_cls == "bull" else "Ведмідь", "cls": ema_cls},
        {"name": "MACD",         "value": "Бик" if macd_cls == "bull" else "Ведмідь", "cls": macd_cls},
        {"name": "Тренд EMA200", "value": "Вище" if trend_cls == "bull" else "Нижче", "cls": trend_cls},
        {"name": "Обʼєм",       "value": f"{cur['vol_ratio']:.2f}x", "cls": vol_cls},
    ]


def main_loop():
    """Основний цикл перевірки сигналів."""
    print("[Bot] Запускаю головний цикл...")
    send_startup_message()

    while True:
        try:
            tf_indicators = {}
            current_price = None

            for tf in TIMEFRAMES:
                print(f"[Bot] Перевіряю {tf}...")
                df = get_ohlcv(tf)

                if df.empty:
                    continue

                df = compute_all(df)
                current_price = df.iloc[-1]["close"]

                # Зберігаємо індикатори для дашборду
                tf_indicators[tf] = get_tf_indicators(df)

                # Аналізуємо сигнал
                signal = analyze(df, tf)
                if signal:
                    print(f"[Bot] 🔔 СИГНАЛ на {tf}: {signal['direction']} (скор {signal['score']})")
                    send_signal(signal)
                    add_signal(signal)
                else:
                    print(f"[Bot] {tf} — немає якісного сигналу")

            # Оновлюємо дашборд
            if current_price:
                update_state(current_price, tf_indicators)

        except Exception as e:
            print(f"[Bot] Помилка в головному циклі: {e}")

        print(f"[Bot] Чекаю {CHECK_INTERVAL}с до наступної перевірки...\n")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    print("=" * 50)
    print("  BTC Signal Bot for Polymarket")
    print("=" * 50)

    # Запускаємо веб-дашборд у окремому потоці
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    print(f"[Web] Дашборд доступний на http://localhost:5000")

    # Запускаємо основний цикл
    main_loop()

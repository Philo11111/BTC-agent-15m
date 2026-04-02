# ============================================================
#  telegram_bot.py  —  відправка сигналів у Telegram
# ============================================================

import requests
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID


def send_signal(signal: dict):
    """
    Відправляє красиве повідомлення з сигналом у Telegram.
    """
    tf = signal["timeframe"]
    direction = signal["direction"]
    score = signal["score"]
    max_score = signal["max_score"]
    price = signal["price"]
    rsi = signal["rsi"]
    reasons = signal["reasons"]
    ts = signal["timestamp"]

    # Вибираємо емодзі та текст
    if direction == "UP":
        emoji = "🟢"
        dir_text = "ВГОРУ (LONG)"
        polymarket_hint = "👉 Polymarket: ставь на **вище** поточної ціни"
    else:
        emoji = "🔴"
        dir_text = "ВНИЗ (SHORT)"
        polymarket_hint = "👉 Polymarket: ставь на **нижче** поточної ціни"

    # Рейтинг якості сигналу
    stars = "⭐" * int(score)
    quality = "ВІДМІННИЙ" if score >= 5 else "ХОРОШИЙ" if score >= 4 else "СЕРЕДНІЙ"

    reasons_text = "\n".join(f"  • {r}" for r in reasons)

    message = (
        f"{emoji} *BTC СИГНАЛ — {dir_text}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📐 Таймфрейм: `{tf}`\n"
        f"💰 Ціна: `${price:,.2f}`\n"
        f"📊 RSI: `{rsi}`\n"
        f"🏆 Якість: {stars} ({quality})\n"
        f"🎯 Скор: `{score}/{max_score}`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"*Причини сигналу:*\n{reasons_text}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{polymarket_hint}\n"
        f"⏰ {ts}"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print(f"[Telegram] Сигнал відправлено: {direction} на {tf}")
        else:
            print(f"[Telegram] Помилка: {resp.text}")
    except Exception as e:
        print(f"[Telegram] Помилка зʼєднання: {e}")


def send_startup_message():
    """Повідомлення при запуску бота."""
    msg = (
        "🤖 *BTC Signal Bot запущено!*\n\n"
        "Слідкую за BTC на таймфреймах: 5m, 15m, 30m, 1h\n"
        "Мінімальний скор для сигналу: 4/6\n\n"
        "Сигнали приходитимуть автоматично 🔔"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"[Telegram] Помилка старту: {e}")

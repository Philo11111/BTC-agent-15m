# chat.py — чат з AI через OpenRouter прямо в Telegram

import os
import requests
from config import TELEGRAM_TOKEN

OPENROUTER_KEY = os.getenv("OPENROUTER_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

chat_history = []


def send_telegram(chat_id, text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10
        )
    except Exception as e:
        print(f"[Chat] Помилка надсилання: {e}")


def ask_ai(user_message: str) -> str:
    chat_history.append({"role": "user", "content": user_message})
    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://btc-signal-bot",
                "X-Title": "BTC Signal Bot",
            },
            json={
                "model": "anthropic/claude-haiku-4-5",
                "messages": chat_history,
                "max_tokens": 1000,
            },
            timeout=30
        )
        print(f"[Chat] OpenRouter статус: {response.status_code}")
        data = response.json()
        print(f"[Chat] OpenRouter відповідь: {data}")

        if "error" in data:
            return f"❌ Помилка API: {data['error'].get('message', str(data['error']))}"

        reply = data["choices"][0]["message"]["content"]
        chat_history.append({"role": "assistant", "content": reply})
        return reply

    except Exception as e:
        return f"❌ Помилка: {e}"


def handle_chat_update(update: dict):
    try:
        if "message" not in update:
            return

        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")
        photo = update["message"].get("photo")

        # Якщо надіслано фото без тексту
        if photo and not text:
            send_telegram(chat_id, "🖼 Бачу що ти надіслав зображення, але я поки працюю лише з текстом. Опиши словами що тебе цікавить!")
            return

        print(f"[Chat] ✉ від {chat_id}: '{text}'")

        if not text or text.startswith("/signal"):
            return

        if text == "/start":
            send_telegram(chat_id, "👋 Привіт! Я BTC Signal Bot + AI асистент.\nПиши будь-які питання — відповім!\nСигнали по BTC приходять автоматично 🔔")
            return

        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendChatAction",
            json={"chat_id": chat_id, "action": "typing"},
            timeout=5
        )

        print("[Chat] Відправляю до OpenRouter...")
        reply = ask_ai(text)
        print(f"[Chat] Відповідь отримано: {reply[:80]}...")

        send_telegram(chat_id, reply)
        print("[Chat] ✅ Надіслано!")

    except Exception as e:
        print(f"[Chat] ПОМИЛКА: {e}")

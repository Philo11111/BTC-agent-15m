# config.py — всі налаштування беруться зі змінних середовища
import os

# Telegram — задаються на Railway у Variables, або локально в .env
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Торговий символ
SYMBOL = "BTCUSDT"

# Таймфрейми
TIMEFRAMES = ["5m", "15m", "30m", "1h"]

# Кількість свічок
CANDLES_LIMIT = 200

# Мінімальний скор сигналу (4 = якісні, 3 = більше але гірші)
MIN_SCORE = 4

# Кулдаун між сигналами (хвилини)
SIGNAL_COOLDOWN = {
    "5m":  20,
    "15m": 45,
    "30m": 90,
    "1h":  180,
}

# Порт веб-дашборду
WEB_PORT = int(os.getenv("PORT", 5000))

# Інтервал перевірки (секунди)
CHECK_INTERVAL = 60

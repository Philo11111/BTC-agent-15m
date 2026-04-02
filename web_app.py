# ============================================================
#  web_app.py  —  веб-дашборд на Flask
# ============================================================

from flask import Flask, render_template
from datetime import datetime
from config import WEB_PORT

app = Flask(__name__)

# Глобальне сховище (заповнюється з main.py)
dashboard_state = {
    "price": "—",
    "signals_today": 0,
    "last_check": "—",
    "signals": [],       # список останніх сигналів (останні 20)
    "tf_data": {},       # стан індикаторів по кожному TF
}


def update_state(price, tf_indicators: dict):
    """Оновлює стан дашборду. Викликається з main.py."""
    dashboard_state["price"] = f"${price:,.2f}"
    dashboard_state["last_check"] = datetime.utcnow().strftime("%H:%M:%S UTC")
    dashboard_state["tf_data"] = tf_indicators


def add_signal(signal: dict):
    """Додає сигнал до лога. Викликається з main.py."""
    dashboard_state["signals"].insert(0, signal)
    dashboard_state["signals"] = dashboard_state["signals"][:20]  # зберігаємо останні 20
    dashboard_state["signals_today"] += 1


@app.route("/")
def index():
    return render_template(
        "dashboard.html",
        price=dashboard_state["price"],
        signals_today=dashboard_state["signals_today"],
        last_check=dashboard_state["last_check"],
        signals=dashboard_state["signals"],
        tf_data=dashboard_state["tf_data"],
    )


def run_web():
    """Запускає Flask в окремому потоці."""
    app.run(host="0.0.0.0", port=WEB_PORT, debug=False, use_reloader=False)

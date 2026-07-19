from flask import Flask, jsonify
from threading import Thread
import os
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from bot import main as bot_main

    logger.info("✅ Бот импортирован")
except Exception as e:
    logger.error(f"Ошибка импорта: {e}")
    exit(1)

app = Flask(__name__)

bot_status = {"status": "starting", "start_time": time.time()}


@app.route('/')
@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "bot": bot_status["status"],
        "uptime": int(time.time() - bot_status["start_time"])
    })


def run_bot():
    try:
        bot_status["status"] = "running"
        bot_main()
    except Exception as e:
        bot_status["status"] = "error"
        logger.error(f"Бот упал: {e}")
        time.sleep(30)
        run_bot()


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))

    thread = Thread(target=run_bot, daemon=True)
    thread.start()

    app.run(host='0.0.0.0', port=port)
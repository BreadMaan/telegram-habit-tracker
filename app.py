import os
import threading
import asyncio
from flask import Flask
from bot import main  # твоя функция из bot.py

app = Flask(__name__)

@app.route("/")
def health():
    return "OK", 200

def run_web():
    # поднимаем flask в отдельном потоке
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # 1) стартим Flask в потоке
    t = threading.Thread(target=run_web, daemon=True)
    t.start()
    # 2) в главном потоке запускаем бота — тут сигнал‑хендлеры встают корректно
    asyncio.run(main())

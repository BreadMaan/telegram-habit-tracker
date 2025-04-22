import os
import threading
import asyncio
from flask import Flask
from bot import main  # импортируем нашу функцию из bot.py

app = Flask(__name__)

@app.route("/")
def health():
    return "OK", 200

def run_bot():
    # main — это корутина, поэтому нам нужен asyncio loop
    asyncio.run(main())

if __name__ == "__main__":
    # бот стартует в отдельном потоке
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    # подхватываем порт из ENV (Render задаёт PORT)
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

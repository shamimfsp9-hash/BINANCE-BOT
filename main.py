import os
import asyncio
from flask import Flask, request, jsonify
from binance.client import Client
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)

# Credentials
API_KEY = os.environ.get("BINANCE_API_KEY", "")
API_SECRET = os.environ.get("BINANCE_API_SECRET", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Binance Client Init
try:
    client = Client(API_KEY, API_SECRET)
except Exception as e:
    client = None
    print(f"Binance Init Error: {e}")

bot = Bot(token=TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None

@app.route('/', methods=['GET'])
def health_check():
    return "Bot is Active!", 200

@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    if not TELEGRAM_TOKEN:
        return "No Token", 400

    data = request.get_json(force=True)
    if "message" in data and "text" in data["message"]:
        chat_id = str(data["message"]["chat"]["id"])
        text = data["message"]["text"].strip()

        # Security Check
        if chat_id != str(ALLOWED_CHAT_ID):
            return "Unauthorized", 403

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        if text == "/start":
            loop.run_until_complete(bot.send_message(chat_id=chat_id, text="Binance Trading Bot active! Use /buy or /sell commands."))
        elif text == "/buy":
            try:
                order = client.futures_create_order(
                    symbol='BTCUSDT', side='BUY', type='MARKET', quantity=0.001
                )
                msg = f"BUY Order Placed Successfully!\nID: {order.get('orderId')}"
            except Exception as e:
                msg = f"Error placing BUY order: {str(e)}"
            loop.run_until_complete(bot.send_message(chat_id=chat_id, text=msg))
        elif text == "/sell":
            try:
                order = client.futures_create_order(
                    symbol='BTCUSDT', side='SELL', type='MARKET', quantity=0.001
                )
                msg = f"SELL Order Placed Successfully!\nID: {order.get('orderId')}"
            except Exception as e:
                msg = f"Error placing SELL order: {str(e)}"
            loop.run_until_complete(bot.send_message(chat_id=chat_id, text=msg))

    return "OK", 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

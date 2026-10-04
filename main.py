import os
import asyncio
from flask import Flask, jsonify
from binance.client import Client
from telegram import Update
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

# Telegram Functions
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Binance Trading Bot active! Use /buy or /sell commands.")

async def buy_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != str(ALLOWED_CHAT_ID):
        return
    try:
        order = client.futures_create_order(
            symbol='BTCUSDT', side='BUY', type='MARKET', quantity=0.001
        )
        await update.message.reply_text(f"BUY Order Placed Successfully!\nID: {order.get('orderId')}")
    except Exception as e:
        await update.message.reply_text(f"Error placing BUY order: {str(e)}")

async def sell_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != str(ALLOWED_CHAT_ID):
        return
    try:
        order = client.futures_create_order(
            symbol='BTCUSDT', side='SELL', type='MARKET', quantity=0.001
        )
        await update.message.reply_text(f"SELL Order Placed Successfully!\nID: {order.get('orderId')}")
    except Exception as e:
        await update.message.reply_text(f"Error placing SELL order: {str(e)}")

# Initialize Telegram App
tg_app = None
if TELEGRAM_TOKEN:
    tg_app = Application.builder().token(TELEGRAM_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("buy", buy_order))
    tg_app.add_handler(CommandHandler("sell", sell_order))

@app.route('/', methods=['GET'])
def health_check():
    return "Bot is Active!", 200

if __name__ == '__main__':
    if tg_app:
        loop = asyncio.get_event_loop()
        loop.create_task(tg_app.run_polling())
        
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

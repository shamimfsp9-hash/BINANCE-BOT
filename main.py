import os
import time
import threading
from flask import Flask, request, jsonify
import requests
from binance.client import Client

app = Flask(__name__)

# Environment Variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')

# Binance Client Initialize
client = None
if BINANCE_API_KEY and BINANCE_API_SECRET:
    try:
        client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)
    except Exception as e:
        print(f"Binance Client Init Error: {e}")

SYMBOL = "BTCUSDT"  # আপনি যেকোনো পেয়ার দিতে পারেন
POSITION = None     # ট্রেডের ট্র্যাকিং এর জন্য

def send_telegram(message):
    if TELEGRAM_BOT_TOKEN:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": os.getenv('TELEGRAM_CHAT_ID'), "text": message})

# --- AUTO TRADING BOT ENGINE ---
def auto_trade_loop():
    global POSITION
    while True:
        try:
            if client is None:
                time.sleep(10)
                continue

            # 1. Daily Candle Data (High and Low)
            daily_klines = client.futures_klines(symbol=SYMBOL, interval=Client.KLINE_INTERVAL_1DAY, limit=2)
            prev_day_high = float(daily_klines[0][2])
            prev_day_low = float(daily_klines[0][3])
            
            # 2. 1-Minute Candles Data
            m1_klines = client.futures_klines(symbol=SYMBOL, interval=Client.KLINE_INTERVAL_1MINUTE, limit=5)
            c1 = m1_klines[-2] # আগের ক্যান্ডেল
            c2 = m1_klines[-1] # বর্তমান বন্ধ হওয়া ক্যান্ডেল

            current_price = float(c2[4])

            # Green Candle Condition (Close > Open)
            c1_is_green = float(c1[4]) > float(c1[1])
            c2_is_green = float(c2[4]) > float(c2[1])

            # Red Candle Condition (Close < Open)
            c1_is_red = float(c1[4]) < float(c1[1])
            c2_is_red = float(c2[4]) < float(c2[1])

            # BUY SETUP: Daily Low Sweep + 2 Green Candles
            if POSITION is None and float(c2[3]) < prev_day_low and c1_is_green and c2_is_green:
                sl_price = min(float(c1[3]), float(c2[3])) # ২টি ক্যান্ডেলের সর্বনিম্ন Low
                
                # Execute Buy Order on Binance
                order = client.futures_create_order(
                    symbol=SYMBOL, side="BUY", type="MARKET", quantity=0.002
                )
                POSITION = {"side": "BUY", "sl": sl_price, "entry": current_price}
                send_telegram(f"🚀 **BUY Trade Opened!**\nSymbol: {SYMBOL}\nEntry: {current_price}\nSL: {sl_price}")

            # SELL SETUP: Daily High Sweep + 2 Red Candles
            elif POSITION is None and float(c2[2]) > prev_day_high and c1_is_red and c2_is_red:
                sl_price = max(float(c1[2]), float(c2[2])) # ২টি ক্যান্ডেলের সর্বোচ্চ High
                
                # Execute Sell Order on Binance
                order = client.futures_create_order(
                    symbol=SYMBOL, side="SELL", type="MARKET", quantity=0.002
                )
                POSITION = {"side": "SELL", "sl": sl_price, "entry": current_price}
                send_telegram(f"🔻 **SELL Trade Opened!**\nSymbol: {SYMBOL}\nEntry: {current_price}\nSL: {sl_price}")

            # MANAGE OPEN POSITIONS (Exit Logic)
            if POSITION:
                # Stop Loss Hit Check
                if POSITION['side'] == 'BUY' and current_price <= POSITION['sl']:
                    client.futures_create_order(symbol=SYMBOL, side="SELL", type="MARKET", quantity=0.002)
                    send_telegram(f"❌ BUY Stop Loss Hit at {current_price}")
                    POSITION = None

                elif POSITION['side'] == 'SELL' and current_price >= POSITION['sl']:
                    client.futures_create_order(symbol=SYMBOL, side="BUY", type="MARKET", quantity=0.002)
                    send_telegram(f"❌ SELL Stop Loss Hit at {current_price}")
                    POSITION = None

                # Market Structure Break / Reversal Exit (2 Red candles for BUY or 2 Green for SELL)
                elif POSITION['side'] == 'BUY' and c1_is_red and c2_is_red:
                    client.futures_create_order(symbol=SYMBOL, side="SELL", type="MARKET", quantity=0.002)
                    send_telegram(f"💰 **BUY Position Closed! (Structure Break)**\nExit Price: {current_price}")
                    POSITION = None

                elif POSITION['side'] == 'SELL' and c1_is_green and c2_is_green:
                    client.futures_create_order(symbol=SYMBOL, side="BUY", type="MARKET", quantity=0.002)
                    send_telegram(f"💰 **SELL Position Closed! (Structure Break)**\nExit Price: {current_price}")
                    POSITION = None

        except Exception as e:
            print(f"Auto Loop Error: {e}")

        time.sleep(5)  # প্রতি ৫ সেকেন্ড পর পর অ্যানালাইসিস করবে

# Background Thread
threading.Thread(target=auto_trade_loop, daemon=True).start()

# --- WEBHOOK FOR TELEGRAM COMMANDS ---
@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if "message" in data and "text" in data["message"]:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"]["text"]

        if text == "/start":
            send_telegram("🤖 Auto Sweep Trading Bot Active!")
        elif text == "/balance":
            if client:
                bal = client.futures_account_balance()
                usdt_bal = next((item['balance'] for item in bal if item['asset'] == 'USDT'), '0')
                send_telegram(f"💰 USDT Balance: {usdt_bal}")
            else:
                send_telegram("Binance connection error.")

    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

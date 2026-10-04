import os
import time
import threading
import requests
from flask import Flask
from binance.client import Client

app = Flask(__name__)

API_KEY = os.environ.get('BINANCE_API_KEY')
API_SECRET = os.environ.get('BINANCE_API_SECRET')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def send_telegram_message(message):
    """টেলিগ্রামে মেসেজ পাঠানোর ফাংশন"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials missing!")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        }
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        print(f"Telegram Error: {e}")

def background_trading_bot():
    """ব্যাকগ্রাউন্ডে নিয়মিত রান হওয়া BTCUSDT মার্কেট সুইপ ও রিভার্সাল লজিক"""
    print("BTCUSDT Smart Money Reversal Bot Started...")
    send_telegram_message("🟢 BTCUSDT Market Sweep & Reversal Bot is Active!")
    
    while True:
        try:
            # আইপি রেট লিমিট এড়াতে সেফভাবে ক্লায়েন্ট ইনিশিয়ালাইজ করা
            client = Client(API_KEY, API_SECRET)
            
            # BTCUSDT এর ৫ মিনিটের ক্যান্ডেল ডাটা ফেচ করা (শেষ ১০টি ক্যান্ডেল)
            klines = client.get_klines(symbol='BTCUSDT', interval=Client.KLINE_INTERVAL_5MINUTE, limit=10)
            
            if klines:
                latest_candle = klines[-1]
                close_price = float(latest_candle[4])
                high_price = float(latest_candle[2])
                low_price = float(latest_candle[3])
                
                print(f"BTCUSDT Checked: Close={close_price}, High={high_price}, Low={low_price}")
                # ভবিষ্যতের সুইপ বা FVG কন্ডিশন এখানে যোগ করা যাবে
                
            time.sleep(600) # ১০ মিনিট পর পর রিকোয়েস্ট পাঠাবে যাতে আইপি ব্যান না হয়
            
        except Exception as e:
            error_msg = f"⚠️ Binance error / Rate limit: {str(e)}"
            print(error_msg)
            send_telegram_message(error_msg)
            time.sleep(900) # এরর খেলে ১৫ মিনিট অপেক্ষা করবে

@app.route('/')
def home():
    return "Secure Full Auto Futures Trading Bot is Active and Running!"

@app.route('/test-telegram')
def test_telegram():
    """টেলিগ্রাম ঠিকমতো কাজ করছে কি না তা টেস্ট করার রুট"""
    try:
        res = send_telegram_message("🟢 Test Message: Your Telegram bridge is working successfully!")
        if res and res.get("ok"):
            return "Telegram test message sent successfully! Check your Telegram chat."
        else:
            return f"Failed to send: {res}"
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == '__main__':
    t = threading.Thread(target=background_trading_bot)
    t.daemon = True
    t.start()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

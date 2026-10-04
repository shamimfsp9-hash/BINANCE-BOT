import os
import time
import threading
import requests
from flask import Flask, request
from binance.client import Client

app = Flask(__name__)

API_KEY = os.environ.get('BINANCE_API_KEY')
API_SECRET = os.environ.get('BINANCE_API_SECRET')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def send_telegram_message(message, chat_id=None):
    """টেলিগ্রামে মেসেজ পাঠানোর ফাংশন"""
    target_chat = chat_id if chat_id else TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not target_chat:
        print("Telegram credentials missing!")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": target_chat,
            "text": message
        }
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        print(f"Telegram Error: {e}")

def set_telegram_webhook():
    """বট চালু হওয়ার সাথে সাথে অটোমেটিক ওয়েবুক সেট করার ফাংশন"""
    render_url = os.environ.get('RENDER_EXTERNAL_URL') # রেন্ডার অটোমেটিক তার নিজের লিংক ধরে নেয়
    if render_url and TELEGRAM_BOT_TOKEN:
        webhook_url = f"{render_url}/telegram-webhook"
        api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook?url={webhook_url}"
        try:
            res = requests.get(api_url)
            print("Webhook Auto-Setup Response:", res.json())
        except Exception as e:
            print(f"Webhook Setup Error: {e}")

def get_binance_futures_balance():
    """বাইন্যান্স ফিউচার্স অ্যাকাউন্ট থেকে ইউএসডিটি ব্যালেন্স চেক করার ফাংশন"""
    try:
        client = Client(API_KEY, API_SECRET)
        account_info = client.futures_account()
        for asset in account_info.get('assets', []):
            if asset['asset'] == 'USDT':
                wallet_balance = float(asset['walletBalance'])
                available_balance = float(asset['availableBalance'])
                return f"💰 Binance Futures Balance:\n- Wallet Balance: {wallet_balance} USDT\n- Available Balance: {available_balance} USDT"
        return "⚠️ USDT balance not found in Futures account."
    except Exception as e:
        return f"⚠ Error fetching balance: {str(e)}"

def background_trading_bot():
    """ব্যাকগ্রাউন্ডে নিয়মিত রান হওয়া BTCUSDT মার্কেট সুইপ লজিক"""
    print("BTCUSDT Smart Money Reversal Bot Started...")
    
    # বট চালু হওয়ার সাথে সাথে অটো ওয়েবুক সেট করে নেবে
    set_telegram_webhook()
    
    send_telegram_message("🟢 BTCUSDT Market Sweep & Reversal Bot is Active!")
    
    while True:
        try:
            client = Client(API_KEY, API_SECRET)
            klines = client.get_klines(symbol='BTCUSDT', interval=Client.KLINE_INTERVAL_5MINUTE, limit=10)
            
            if klines:
                latest_candle = klines[-1]
                close_price = float(latest_candle[4])
                print(f"BTCUSDT Checked: Close={close_price}")
                
            time.sleep(600) # ১০ মিনিট পর পর রিকোয়েস্ট পাঠাবে
            
        except Exception as e:
            error_msg = f"⚠️ Binance error / Rate limit: {str(e)}"
            print(error_msg)
            send_telegram_message(error_msg)
            time.sleep(900)

@app.route('/')
def home():
    return "Secure Full Auto Futures Trading Bot is Active and Running!"

@app.route('/telegram-webhook', methods=['POST'])
def telegram_webhook():
    """টেলিগ্রাম থেকে কমান্ড রিসিভ করার ওয়েবুক রুট"""
    try:
        data = request.get_json()
        if data and 'message' in data:
            message = data['message']
            chat_id = message['chat']['id']
            text = message.get('text', '').strip()
            
            if text == '/balance':
                balance_msg = get_binance_futures_balance()
                send_telegram_message(balance_msg, chat_id=chat_id)
                
        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook Error: {e}")
        return {"status": "error"}

if __name__ == '__main__':
    t = threading.Thread(target=background_trading_bot)
    t.daemon = True
    t.start()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

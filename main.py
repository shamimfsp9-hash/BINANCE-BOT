from flask import Flask
import time
import requests
import threading
import pandas as pd
from binance.client import Client

app = Flask(__name__)

# আপনার বাইন্যান্স এবং টেলিগ্রাম তথ্য নিচে বসিয়ে দিন
API_KEY = "YOUR_BINANCE_API_KEY"
API_SECRET = "YOUR_BINANCE_API_SECRET"
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"

ACTIVE_POSITION = None
SYMBOL = "BTCUSDT"


def send_telegram_message(message):
  try:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload, timeout=5)
  except Exception as e:
    print(f"Telegram Error: {e}")


@app.route("/")
def home():
  return "Live Trading Bot is Active and Running!"


def get_market_data():
  try:
    client = Client(API_KEY, API_SECRET)
    klines = client.get_klines(symbol=SYMBOL, interval=Client.KLINE_INTERVAL_1MINUTE, limit=10)
    df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'])
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)

    daily_klines = client.get_klines(symbol=SYMBOL, interval=Client.KLINE_INTERVAL_1DAY, limit=2)
    daily_high = float(daily_klines[-2][2])
    daily_low = float(daily_klines[-2][3])

    return df, daily_high, daily_low
  except Exception as e:
    print(f"Binance API Error: {e}")
    return None, None, None


def check_entry_signal(df_1m, daily_high, daily_low):
  if df_1m is None or len(df_1m) < 5:
    return None, None, None

  c1 = df_1m.iloc[-3]
  c2 = df_1m.iloc[-2]
  c3 = df_1m.iloc[-1]

  # সেল সেটআপ: ডেইলি হাই সুইপ এবং বিয়ারিশ ক্যান্ডেল কনফার্মেশন
  high_swept = (c1['high'] > daily_high) or (c2['high'] > daily_high) or (c3['high'] > daily_high)
  if high_swept:
    if (c2['close'] < c2['open']) and (c3['close'] < c3['open']):
      stop_loss = max(c1['high'], c2['high'], c3['high'])
      return "SELL", c3['close'], stop_loss

  # বাই সেটআপ: ডেইলি লো সুইপ এবং বুলিশ ক্যান্ডেল কনফার্মেশন
  low_swept = (c1['low'] < daily_low) or (c2['low'] < daily_low) or (c3['low'] < daily_low)
  if low_swept:
    if (c2['close'] > c2['open']) and (c3['close'] > c3['open']):
      stop_loss = min(c1['low'], c2['low'], c3['low'])
      return "BUY", c3['close'], stop_loss

  return None, None, None


def manage_active_trade(df_1m):
  global ACTIVE_POSITION
  if not ACTIVE_POSITION:
    return

  current_price = df_1m.iloc[-1]['close']
  side = ACTIVE_POSITION['side']
  entry = ACTIVE_POSITION['entry']
  sl = ACTIVE_POSITION['sl']
  risk = ACTIVE_POSITION['risk']

  c1 = df_1m.iloc[-2]
  c2 = df_1m.iloc[-1]

  if side == "BUY":
    target_1_3 = entry + (risk * 3)
    if current_price >= target_1_3 and sl < entry:
      ACTIVE_POSITION['sl'] = entry
      send_telegram_message("📈 *BUY Trade Update*\nTarget 1:3 reached! Stop Loss moved to Break-even.")

    if c1['close'] < c1['open'] and c2['close'] < c2['open']:
      send_telegram_message("📉 *Structure Shift Confirmed!*\nClosing BUY Trade.")
      ACTIVE_POSITION = None

  elif side == "SELL":
    target_1_3 = entry - (risk * 3)
    if current_price <= target_1_3 and sl > entry:
      ACTIVE_POSITION['sl'] = entry
      send_telegram_message("📉 *SELL Trade Update*\nTarget 1:3 reached! Stop Loss moved to Break-even.")

    if c1['close'] > c1['open'] and c2['close'] > c2['open']:
      send_telegram_message("📈 *Structure Shift Confirmed!*\nClosing SELL Trade.")
      ACTIVE_POSITION = None


def background_trading_bot():
  global ACTIVE_POSITION
  print("Background Trading Bot Started...")
  
  while True:
    try:
      df_1m, daily_high, daily_low = get_market_data()
      if df_1m is not None:
        if ACTIVE_POSITION is None:
          side, entry, sl = check_entry_signal(df_1m, daily_high, daily_low)
          if side:
            risk = abs(entry - sl)
            ACTIVE_POSITION = {"side": side, "entry": entry, "sl": sl, "risk": risk}
            send_telegram_message(f"🚀 *New {side} Trade Opened!*\n- Entry: {entry}\n- Stop Loss: {sl}\n- Risk: {risk}")
        else:
          manage_active_trade(df_1m)
    except Exception as e:
      print(f"Loop Error: {e}")
    
    # বাইন্যান্স এপিআই রেট লিমিট (আইপি ব্যান -1003) এড়াতে ১০ সেকেন্ড বিরতি
    time.sleep(10)


bot_thread = threading.Thread(target=background_trading_bot, daemon=True)
bot_thread.start()

if __name__ == "__main__":
  app.run(host="0.0.0.0", port=10000)

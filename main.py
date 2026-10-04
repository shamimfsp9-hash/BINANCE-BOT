from flask import Flask
import time
import requests
import threading
import pandas as pd
from binance.client import Client

app = Flask(__name__)

# আপনার বাইন্যান্স এবং টেলিগ্রাম তথ্য এখানে বসিয়ে দিন
API_KEY = "YOUR_BINANCE_API_KEY"
API_SECRET = "YOUR_BINANCE_API_SECRET"
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"

ACTIVE_POSITION = None
SYMBOL = "BTCUSDT"
QUANTITY = 0.002  # আপনার ফিউচার্স ট্রেডের লট সাইজ (প্রয়োজনমতো কমাতে বা বাড়াতে পারেন)


def send_telegram_message(message):
  try:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload, timeout=5)
  except Exception as e:
    print(f"Telegram Error: {e}")


@app.route("/")
def home():
  return "Full Auto Futures Trading Bot is Active and Running!"


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


def place_futures_order(side, entry, sl, tp):
  try:
    client = Client(API_KEY, API_SECRET)
    
    # ফিউচার্সে মার্কেট অর্ডার ওপেন করা
    order_side = Client.SIDE_BUY if side == "BUY" else Client.SIDE_SELL
    order = client.futures_create_order(
      symbol=SYMBOL,
      side=order_side,
      type=Client.ORDER_TYPE_MARKET,
      quantity=QUANTITY
    )
    
    # স্টপ লস এবং টেক প্রফিট অর্ডার সেট করা
    opp_side = Client.SIDE_SELL if side == "BUY" else Client.SIDE_BUY
    
    # Stop Loss Order
    client.futures_create_order(
      symbol=SYMBOL,
      side=opp_side,
      type=Client.FUTURE_ORDER_TYPE_STOP_MARKET,
      stopPrice=str(round(sl, 2)),
      closePosition=True
    )
    
    # Take Profit Order (1:3 Target)
    client.futures_create_order(
      symbol=SYMBOL,
      side=opp_side,
      type=Client.FUTURE_ORDER_TYPE_LIMIT,
      price=str(round(tp, 2)),
      quantity=QUANTITY,
      timeInForce='GTC'
    )
    
    return True
  except Exception as e:
    print(f"Binance Order Error: {e}")
    send_telegram_message(f"⚠️ *Order Execution Error:* {e}")
    return False


def close_futures_position():
  try:
    client = Client(API_KEY, API_SECRET)
    # পজিশন ক্লোজ করার জন্য বিপরীত অর্ডারের মার্কেট ট্রিক বা পজিশন স্কয়ার অফ করা যেতে পারে
    # সহজভাবে অল ওপেন অর্ডার ক্যান্সেল এবং মার্কেট ক্লোজ করা যায়
    positions = client.futures_position_information(symbol=SYMBOL)
    for pos in positions:
      amt = float(pos['positionAmt'])
      if amt != 0:
        close_side = Client.SIDE_SELL if amt > 0 else Client.SIDE_BUY
        client.futures_create_order(
          symbol=SYMBOL,
          side=close_side,
          type=Client.ORDER_TYPE_MARKET,
          quantity=abs(amt)
        )
    client.futures_cancel_all_open_orders(symbol=SYMBOL)
  except Exception as e:
    print(f"Close Position Error: {e}")


def check_entry_signal(df_1m, daily_high, daily_low):
  if df_1m is None or len(df_1m) < 5:
    return None, None, None, None

  c1 = df_1m.iloc[-3]
  c2 = df_1m.iloc[-2]
  c3 = df_1m.iloc[-1]

  # সেল সেটআপ: ডেইলি হাই সুইপ এবং বিয়ারিশ ক্যান্ডেল কনফার্মেশন
  high_swept = (c1['high'] > daily_high) or (c2['high'] > daily_high) or (c3['high'] > daily_high)
  if high_swept:
    if (c2['close'] < c2['open']) and (c3['close'] < c3['open']):
      stop_loss = max(c1['high'], c2['high'], c3['high'])
      entry = c3['close']
      risk = abs(entry - stop_loss)
      tp = entry - (risk * 3)
      return "SELL", entry, stop_loss, tp

  # বাই সেটআপ: ডেইলি লো সুইপ এবং বুলিশ ক্যান্ডেল কনফার্মেশন
  low_swept = (c1['low'] < daily_low) or (c2['low'] < daily_low) or (c3['low'] < daily_low)
  if low_swept:
    if (c2['close'] > c2['open']) and (c3['close'] > c3['open']):
      stop_loss = min(c1['low'], c2['low'], c3['low'])
      entry = c3['close']
      risk = abs(entry - stop_loss)
      tp = entry + (risk * 3)
      return "BUY", entry, stop_loss, tp

  return None, None, None, None


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
      send_telegram_message("📈 *BUY Trade Update*\nTarget 1:3 reached! Stop Loss should be managed.")

    # স্ট্রাকচার শিফট (ChoCH) হলে পজিশন ক্লোজ করা
    if c1['close'] < c1['open'] and c2['close'] < c2['open']:
      send_telegram_message("📉 *Structure Shift Confirmed (ChoCH)*\nClosing BUY Trade Automatically.")
      close_futures_position()
      ACTIVE_POSITION = None

  elif side == "SELL":
    target_1_3 = entry - (risk * 3)
    if current_price <= target_1_3 and sl > entry:
      ACTIVE_POSITION['sl'] = entry
      send_telegram_message("📉 *SELL Trade Update*\nTarget 1:3 reached! Stop Loss should be managed.")

    # স্ট্রাকচার শিফট (ChoCH) হলে পজিশন ক্লোজ করা
    if c1['close'] > c1['open'] and c2['close'] > c2['open']:
      send_telegram_message("📈 *Structure Shift Confirmed (ChoCH)*\nClosing SELL Trade Automatically.")
      close_futures_position()
      ACTIVE_POSITION = None


def background_trading_bot():
  global ACTIVE_POSITION
  print("Full Auto Futures Trading Bot Started...")
  
  while True:
    try:
      df_1m, daily_high, daily_low = get_market_data()
      if df_1m is not None:
        if ACTIVE_POSITION is None:
          side, entry, sl, tp = check_entry_signal(df_1m, daily_high, daily_low)
          if side:
            risk = abs(entry - sl)
            # বাইন্যান্স ফিউচার্সে অটো অর্ডার প্লেস করা
            success = place_futures_order(side, entry, sl, tp)
            if success:
              ACTIVE_POSITION = {"side": side, "entry": entry, "sl": sl, "risk": risk}
              send_telegram_message(f"🚀 *Full Auto: New {side} Trade Executed!*\n- Entry: {entry}\n- Stop Loss: {sl}\n- Take Profit (1:3): {tp}\n- Risk: {risk}")
        else:
          manage_active_trade(df_1m)
    except Exception as e:
      print(f"Loop Error: {e}")
    
    # রেট লিমিট এড়াতে ৫ মিনিট (৩০০ সেকেন্ড) পর পর চেক করবে
    time.sleep(300)


bot_thread = threading.Thread(target=background_trading_bot, daemon=True)
bot_thread.start()

if __name__ == "__main__":
  app.run(host="0.0.0.0", port=10000)

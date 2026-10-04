from flask import Flask
import time
import requests
import threading
import os
import pandas as pd
from binance.client import Client

app = Flask(__name__)

# রেন্ডারের Environment Variables থেকে সিক্রেট তথ্যগুলো রিড করা হচ্ছে
API_KEY = os.environ.get("BINANCE_API_KEY")
API_SECRET = os.environ.get("BINANCE_API_SECRET")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

ACTIVE_POSITION = None
SYMBOL = "BTCUSDT"
QUANTITY = 0.002  # আপনার ফিউচার্স ট্রেডের লট সাইজ


def send_telegram_message(message):
  try:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
      return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload, timeout=5)
  except Exception as e:
    print(f"Telegram Error: {e}")


@app.route("/")
def home():
  return "Secure Full Auto Futures Trading Bot is Active and Running!"


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
    
    order_side = Client.SIDE_BUY if side == "BUY" else Client.SIDE_SELL
    client.futures_create_order(
      symbol=SYMBOL,
      side=order_side,
      type=Client.ORDER_TYPE_MARKET,
      quantity=QUANTITY
    )
    
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

  high_swept = (c1['high'] > daily_high) or (c2['high'] > daily_high) or (c3['high'] > daily_high)
  if high_swept:
    if (c2['close'] < c2['open']) and (c3['close'] < c3['open']):
      stop_loss = max(c1['high'], c2['high'], c3['high'])
      entry = c3['close']
      risk = abs(entry - stop_loss)
      tp = entry - (risk * 3)
      return "SELL", entry, stop_loss, tp

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
      send_telegram_message("📈 *BUY Trade Update*\nTarget 1:3 reached! Stop Loss managed.")

    if c1['close'] < c1['open'] and c2['close'] < c2['open']:
      send_telegram_message("📉 *Structure Shift Confirmed (ChoCH)*\nClosing BUY Trade.")
      close_futures_position()
      ACTIVE_POSITION = None

  elif side == "SELL":
    target_1_3 = entry - (risk * 3)
    if current_price <= target_1_3 and sl > entry:
      ACTIVE_POSITION['sl'] = entry
      send_telegram_message("📉 *SELL Trade Update*\nTarget 1:3 reached! Stop Loss managed.")

    if c1['close'] > c1['open'] and c2['close'] > c2['open']:
      send_telegram_message("📈 *Structure Shift Confirmed (ChoCH)*\nClosing SELL Trade.")
      close_futures_position()
      ACTIVE_POSITION = None


def background_trading_bot():
  global ACTIVE_POSITION
  print("Secure Full Auto Futures Trading Bot Started...")
  
  while True:
    try:
      df_1m, daily_high, daily_low = get_market_data()
      if df_1m is not None:
        if ACTIVE_POSITION is None:
          side, entry, sl, tp = check_entry_signal(df_1m, daily_high, daily_low)
          if side:
            risk = abs(entry - sl)
            success = place_futures_order(side, entry, sl, tp)
            if success:
              ACTIVE_POSITION = {"side": side, "entry": entry, "sl": sl, "risk": risk}
              send_telegram_message(f"🚀 *Full Auto: New {side} Trade Executed!*\n- Entry: {entry}\n- Stop Loss: {sl}\n- Take Profit (1:3): {tp}\n- Risk: {risk}")
        else:
          manage_active_trade(df_1m)
    except Exception as e:
      print(f"Loop Error: {e}")
    
    time.sleep(300)


bot_thread = threading.Thread(target=background_trading_bot, daemon=True)
bot_thread.start()

if __name__ == "__main__":
  app.run(host="0.0.0.0", port=10000)
  @app.route('/test-telegram')
def test_telegram():
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": "🟢 Test Message: Your Telegram bridge is working successfully!"
        }
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return "Telegram test message sent successfully! Check your chat."
        else:
            return f"Failed to send: {response.text}"
    except Exception as e:
        return f"Error: {str(e)}"


from flask import Flask
import time
import requests

app = Flask(__name__)

# টেলিগ্রাম কনফিগারেশন (আপনার বট টোকেন ও চ্যাট আইডি এখানে বসিয়ে দেবেন)
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"


def send_telegram_message(message):
  """টেলিগ্রামে নোটিফিকেশন পাঠানোর ফাংশন"""
  try:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload, timeout=5)
  except Exception as e:
    print(f"Telegram Error: {e}")


@app.route("/")
def home():
  return "Trading Bot is Active and Running!"


# গ্লোবাল ভ্যারিয়েবল পজিশন ট্র্যাক করার জন্য
ACTIVE_POSITION = None  # ফরম্যাট: {"side": "BUY" / "SELL", "entry": price, "sl": price, "risk": val}


def check_entry_signal(df_1m, daily_high, daily_low):
  """১-মিনিট চার্ট থেকে ডেইলি হাই/লো সুইপ এবং ডাবল ক্যান্ডেল রিভার্সাল চেক করে"""
  if len(df_1m) < 5:
    return None, None, None

  c1 = df_1m.iloc[-3]
  c2 = df_1m.iloc[-2]
  c3 = df_1m.iloc[-1]

  # ১. সেল সেটআপ (SELL Setup): ডেইলি হাই সুইপ এবং বিয়ারিশ ক্যান্ডেল কনফার্মেশন
  high_swept = (
      (c1["high"] > daily_high)
      or (c2["high"] > daily_high)
      or (c3["high"] > daily_high)
  )
  if high_swept:
    is_c2_red = c2["close"] < c2["open"]
    is_c3_red = c3["close"] < c3["open"]
    if is_c2_red and is_c3_red:
      stop_loss = max(c1["high"], c2["high"], c3["high"])
      entry_price = c3["close"]
      return "SELL", entry_price, stop_loss

  # ২. বাই সেটআপ (BUY Setup): ডেইলি লো সুইপ এবং বুলিশ ক্যান্ডেল কনফার্মেশন
  low_swept = (
      (c1["low"] < daily_low) or (c2["low"] < daily_low) or (c3["low"] < daily_low)
  )
  if low_swept:
    is_c2_green = c2["close"] > c2["open"]
    is_c3_green = c3["close"] > c3["open"]
    if is_c2_green and is_c3_green:
      stop_loss = min(c1["low"], c2["low"], c3["low"])
      entry_price = c3["close"]
      return "BUY", entry_price, stop_loss

  return None, None, None


def manage_active_trade(df_1m):
  """রানিং ট্রেড ম্যানেজ করবে: ১:৩ টার্গেটে ট্রেইলিং এসএল এবং স্ট্রাকচার শিফটে ক্লোজ"""
  global ACTIVE_POSITION
  if not ACTIVE_POSITION:
    return

  current_price = df_1m.iloc[-1]["close"]
  side = ACTIVE_POSITION["side"]
  entry = ACTIVE_POSITION["entry"]
  sl = ACTIVE_POSITION["sl"]
  risk = ACTIVE_POSITION["risk"]

  c1 = df_1m.iloc[-2]
  c2 = df_1m.iloc[-1]

  if side == "BUY":
    target_1_3 = entry + (risk * 3)

    # ১:৩ টার্গেট হিট করলে বা তার বেশি গেলে ট্রেইলিং স্টপ লস ব্রেক-ইভেন এ নিয়ে আসা
    if current_price >= target_1_3 and sl < entry:
      ACTIVE_POSITION["sl"] = entry
      send_telegram_message(
          "📈 *BUY Trade Update*\nTarget 1:3 reached! Stop Loss moved to"
          " Break-even."
      )

    # স্ট্রাকচার শিফট চেক (টানা দুটি লাল ক্যান্ডেল ক্লোজ হলে ট্রেড ক্লোজ)
    if c1["close"] < c1["open"] and c2["close"] < c2["open"]:
      send_telegram_message(
          "📉 *Structure Shift Confirmed!*\nClosing BUY Trade."
      )
      # TODO: এখানে অর্ডার ক্লোজ করার কোড বসবে
      ACTIVE_POSITION = None

  elif side == "SELL":
    target_1_3 = entry - (risk * 3)

    # ১:৩ টার্গেট হিট করলে বা তার বেশি গেলে ট্রেইলিং স্টপ লস ব্রেক-ইভেন এ নিয়ে আসা
    if current_price <= target_1_3 and sl > entry:
      ACTIVE_POSITION["sl"] = entry
      send_telegram_message(
          "📉 *SELL Trade Update*\nTarget 1:3 reached! Stop Loss moved to"
          " Break-even."
      )

    # স্ট্রাকচার শিফট চেক (টানা দুটি সবুজ ক্যান্ডেল ক্লোজ হলে ট্রেড ক্লোজ)
    if c1["close"] > c1["open"] and c2["close"] > c2["open"]:
      send_telegram_message(
          "📈 *Structure Shift Confirmed!*\nClosing SELL Trade."
      )
      # TODO: এখানে অর্ডার ক্লোজ করার কোড বসবে
      ACTIVE_POSITION = None


def auto_trade_loop(df_1m, daily_high, daily_low):
  global ACTIVE_POSITION

  if ACTIVE_POSITION is None:
    side, entry, sl = check_entry_signal(df_1m, daily_high, daily_low)
    if side:
      risk = abs(entry - sl)
      ACTIVE_POSITION = {"side": side, "entry": entry, "sl": sl, "risk": risk}
      msg = (
          f"🚀 *New {side} Trade Opened!*\n- Entry: {entry}\n- Stop Loss:"
          f" {sl}\n- Risk: {risk}"
      )
      send_telegram_message(msg)
  else:
    manage_active_trade(df_1m)


if __name__ == "__main__":
  # এটি রেন্ডারে ফ্লাস্ক সার্ভার চালু করার জন্য (গুনিকর্ন এটি হ্যান্ডেল করবে)
  app.run(host="0.0.0.0", port=10000)

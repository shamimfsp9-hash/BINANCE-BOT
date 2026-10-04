import time

# গ্লোবাল ভ্যারিয়েবল: এটি মনে রাখবে বর্তমানে কোনো ট্রেড রানিং আছে কি না এবং তার তথ্য কি
ACTIVE_POSITION = None  # ফরম্যাট: {"side": "BUY" / "SELL", "entry": দাম, "sl": স্টপলস, "risk": ঝুঁকি}


def check_entry_signal(df_1m, daily_high, daily_low):
  """১-মিনিট চার্ট থেকে ডেইলি হাই/লো সুইপ এবং ডাবল ক্যান্ডেল রিভার্সাল চেক করে সিগন্যাল দেয়"""
  if len(df_1m) < 5:
    return None, None, None

  # শেষ ৩টি ১-মিনিটের ক্যান্ডেল নির্ধারণ করা হচ্ছে
  c1 = df_1m.iloc[-3]
  c2 = df_1m.iloc[-2]
  c3 = df_1m.iloc[-1]

  # ১. সেল সেটআপ (SELL Setup): ডেইলি হাই সুইপ এবং পরপর দুটি লাল ক্যান্ডেল ক্লোজ হলে
  high_swept = (
      (c1["high"] > daily_high)
      or (c2["high"] > daily_high)
      or (c3["high"] > daily_high)
  )
  if high_swept:
    is_c2_red = c2["close"] < c2["open"]
    is_c3_red = c3["close"] < c3["open"]
    if is_c2_red and is_c3_red:
      # সুইপ মুভমেন্টের সর্বোচ্চ পিক পয়েন্ট স্টপ লস হিসেবে সেট হবে
      stop_loss = max(c1["high"], c2["high"], c3["high"])
      entry_price = c3["close"]
      return "SELL", entry_price, stop_loss

  # ২. বাই সেটআপ (BUY Setup): ডেইলি লো সুইপ এবং পরপর দুটি সবুজ ক্যান্ডেল ক্লোজ হলে
  low_swept = (
      (c1["low"] < daily_low) or (c2["low"] < daily_low) or (c3["low"] < daily_low)
  )
  if low_swept:
    is_c2_green = c2["close"] > c2["open"]
    is_c3_green = c3["close"] > c3["open"]
    if is_c2_green and is_c3_green:
      # সুইপ মুভমেন্টের সর্বনিম্ন লো পয়েন্ট স্টপ লস হিসেবে সেট হবে
      stop_loss = min(c1["low"], c2["low"], c3["low"])
      entry_price = c3["close"]
      return "BUY", entry_price, stop_loss

  return None, None, None


def manage_active_trade(df_1m):
  """রানিং ট্রেড ম্যানেজ করে: ১:৩ টার্গেটে ট্রেইলিং এসএল এবং স্ট্রাকচার শিফটে ট্রেড ক্লোজ করে"""
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
    # ১:৩ রিস্ক-টু-রিওয়ার্ড টার্গেট হিসাব
    target_1_3 = entry + (risk * 3)

    # প্রাইস ১:৩ টার্গেটে পৌঁছালে স্টপ লসকে এন্ট্রি প্রাইসে (Break-even) নিয়ে আসা
    if current_price >= target_1_3 and sl < entry:
      ACTIVE_POSITION["sl"] = entry
      print(
          "ট্রেড ১:৩ টার্গেটে পৌঁছেছে! স্টপ লস ব্রেক-ইভেন (Entry Price) এ শিফট"
          " করা হলো (BUY)"
      )

    # স্ট্রাকচার শিফট চেক: বাই ট্রেডে হঠাৎ দুটি লাল ক্যান্ডেল আসলে ট্রেন্ড পরিবর্তন ধরে ট্রেড ক্লোজ
    if c1["close"] < c1["open"] and c2["close"] < c2["open"]:
      print(
          "মার্কেট স্ট্রাকচার শিফট কনফার্ম হয়েছে! BUY ট্রেড ক্লোজ করা হচ্ছে।"
      )
      # TODO: এখানে আপনার এক্সচেঞ্জের অর্ডার ক্লোজ করার কোড বসবে
      ACTIVE_POSITION = None

  elif side == "SELL":
    # ১:৩ রিস্ক-টু-রিওয়ার্ড টার্গেট হিসাব
    target_1_3 = entry - (risk * 3)

    # প্রাইস ১:৩ টার্গেটে পৌঁছালে স্টপ লসকে এন্ট্রি প্রাইসে (Break-even) নিয়ে আসা
    if current_price <= target_1_3 and sl > entry:
      ACTIVE_POSITION["sl"] = entry
      print(
          "ট্রেড ১:৩ টার্গেটে পৌঁছেছে! স্টপ লস ব্রেক-ইভেন (Entry Price) এ শিফট"
          " করা হলো (SELL)"
      )

    # স্ট্রাকচার শিফট চেক: সেল ট্রেডে হঠাৎ দুটি সবুজ ক্যান্ডেল আসলে ট্রেন্ড পরিবর্তন ধরে ট্রেড ক্লোজ
    if c1["close"] > c1["open"] and c2["close"] > c2["open"]:
      print(
          "মার্কেট স্ট্রাকচার শিফট কনফার্ম হয়েছে! SELL ট্রেড ক্লোজ করা হচ্ছে।"
      )
      # TODO: এখানে আপনার এক্সচেঞ্জের অর্ডার ক্লোজ করার কোড বসবে
      ACTIVE_POSITION = None


def auto_trade_loop(df_1m, daily_high, daily_low):
  global ACTIVE_POSITION

  # যদি কোনো ট্রেড খোলা না থাকে, তবে নতুন এন্ট্রি সিগন্যাল খুঁজবে
  if ACTIVE_POSITION is None:
    side, entry, sl = check_entry_signal(df_1m, daily_high, daily_low)
    if side:
      risk = abs(entry - sl)
      ACTIVE_POSITION = {"side": side, "entry": entry, "sl": sl, "risk": risk}
      print(
          f"নতুন {side} ট্রেড ওপেন হয়েছে! এন্ট্রি: {entry}, স্টপ লস: {sl},"
          f" ঝুঁকি: {risk}"
      )
      # TODO: এখানে টেলিগ্রামে নোটিফিকেশন পাঠানোর কোড যুক্ত করতে পারেন
  else:
    # যদি ইতিমধ্যে ট্রেড রানিং থাকে, তবে তা ট্রেইল এবং ম্যানেজ করতে থাকবে
    manage_active_trade(df_1m)
    from flask import Flask

app = Flask(__name__)


@app.route("/")
def home():
  return "Trading Bot is Running!"


import os
import json
from flask import Flask, request, jsonify
from binance.client import Client

app = Flask(__name__)

API_KEY = os.environ.get("BINANCE_API_KEY")
API_SECRET = os.environ.get("BINANCE_API_SECRET")

client = Client(API_KEY, API_SECRET)

@app.route('/', methods=['GET'])
def health_check():
    return "Bot is Active!", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = json.loads(request.data)
        symbol = data.get('symbol', 'BTCUSDT')
        action = data.get('action')
        quantity = float(data.get('quantity', 0.001))
        
        if action == 'sell':
            order = client.futures_create_order(
                symbol=symbol,
                side='SELL',
                type='MARKET',
                quantity=quantity
            )
            return jsonify({"status": "success", "order": order}), 200

        elif action == 'buy':
            order = client.futures_create_order(
                symbol=symbol,
                side='BUY',
                type='MARKET',
                quantity=quantity
            )
            return jsonify({"status": "success", "order": order}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

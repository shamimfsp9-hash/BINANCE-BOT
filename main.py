import os
import json
from flask import Flask, request, jsonify
from binance.client import Client

app = Flask(__name__)

# Environment variables
API_KEY = os.environ.get("BINANCE_API_KEY", "")
API_SECRET = os.environ.get("BINANCE_API_SECRET", "")

# Client initialization wrapped in try-except to prevent runtime crashes on startup
try:
    client = Client(API_KEY, API_SECRET)
except Exception as e:
    client = None
    print(f"Binance Client Init Error: {e}")

@app.route('/', methods=['GET'])
def health_check():
    return "Bot is Active!", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    if not client:
        return jsonify({"status": "error", "message": "Binance Client not initialized properly"}), 500
        
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"status": "error", "message": "No JSON payload received"}), 400

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

        return jsonify({"status": "ignored", "message": "Invalid action specified"}), 400

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

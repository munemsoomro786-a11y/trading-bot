import os
import json
import pandas as pd
from flask import Flask, jsonify, request, send_from_directory
from config import load_config, save_config
from bot_runner import bot_runner_instance
from backtester import Backtester
from indicators import add_all_indicators

app = Flask(__name__, static_folder="static", static_url_path="/static")

# Start background trading bot on server launch
bot_runner_instance.start()

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/api/status", methods=["GET"])
def get_status():
    stats = bot_runner_instance.account.get_stats()
    config = load_config()
    return jsonify({
        "is_running": bot_runner_instance.is_running,
        "config": config,
        "stats": stats,
        "market_prices": bot_runner_instance.market_prices
    })

@app.route("/api/positions", methods=["GET"])
def get_positions():
    return jsonify({
        "positions": bot_runner_instance.account.positions
    })

@app.route("/api/trades", methods=["GET"])
def get_trades():
    return jsonify({
        "trades": bot_runner_instance.account.trades
    })

@app.route("/api/logs", methods=["GET"])
def get_logs():
    return jsonify({
        "logs": bot_runner_instance.logs
    })

@app.route("/api/chart", methods=["GET"])
def get_chart_data():
    symbol = request.args.get("symbol", "BTC/USDT")
    timeframe = request.args.get("timeframe", "15m")
    limit = int(request.args.get("limit", 150))

    df = bot_runner_instance.fetcher.fetch_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit)
    if df is None or df.empty:
        return jsonify({"error": "Failed to fetch chart data"}), 400
    
    df = add_all_indicators(df)

    candles = []
    for _, row in df.iterrows():
        c_ts = int(row['timestamp'].timestamp()) if hasattr(row['timestamp'], 'timestamp') else int(row['timestamp'] / 1000)
        candles.append({
            "time": c_ts,
            "open": float(row['open']),
            "high": float(row['high']),
            "low": float(row['low']),
            "close": float(row['close']),
            "volume": float(row['volume']),
            "ema_fast": float(row['ema_fast']) if 'ema_fast' in row and not pd.isna(row['ema_fast']) else None,
            "ema_slow": float(row['ema_slow']) if 'ema_slow' in row and not pd.isna(row['ema_slow']) else None,
            "rsi": float(row['rsi']) if 'rsi' in row and not pd.isna(row['rsi']) else None
        })

    analysis = bot_runner_instance.strategy.analyze(df)

    return jsonify({
        "symbol": symbol,
        "timeframe": timeframe,
        "candles": candles,
        "analysis": analysis
    })

@app.route("/api/bot/start", methods=["POST"])
def start_bot():
    bot_runner_instance.start()
    return jsonify({"success": True, "message": "Bot started"})

@app.route("/api/bot/pause", methods=["POST"])
def pause_bot():
    bot_runner_instance.pause()
    return jsonify({"success": True, "message": "Bot paused"})

@app.route("/api/bot/reset", methods=["POST"])
def reset_bot():
    data = request.get_json(silent=True) or {}
    config = load_config()
    default_bal = config.get("initial_balance", 50.0)
    balance = float(data.get("balance", default_bal))
    bot_runner_instance.account.reset_account(balance)
    bot_runner_instance.log(f"Account reset to ${balance:.2f}", "WARNING")
    return jsonify({"success": True, "message": f"Account reset to ${balance:.2f}"})

@app.route("/api/position/close", methods=["POST"])
def close_position():
    data = request.get_json(silent=True) or {}
    position_id = data.get("position_id")
    symbol = None
    for p in bot_runner_instance.account.positions:
        if p["id"] == position_id:
            symbol = p["symbol"]
            break
    current_price = bot_runner_instance.market_prices.get(symbol, 0.0) if symbol else 0.0
    if current_price == 0.0 and symbol:
        current_price = bot_runner_instance.fetcher.fetch_current_price(symbol)

    res = bot_runner_instance.account.close_position_manually(position_id, current_price)
    if res.get("success"):
        bot_runner_instance.log(f"Manual Close executed for position {position_id}", "INFO")
    return jsonify(res)

@app.route("/api/backtest", methods=["POST"])
def run_backtest():
    data = request.get_json(silent=True) or {}
    symbol = data.get("symbol", "BTC/USDT")
    timeframe = data.get("timeframe", "15m")
    limit = int(data.get("limit", 500))

    backtester = Backtester(
        initial_balance=bot_runner_instance.account.initial_balance,
        risk_pct=bot_runner_instance.config.get("risk_per_trade_pct", 2.0)
    )
    result = backtester.run(symbol=symbol, timeframe=timeframe, limit=limit)
    return jsonify(result)

if __name__ == "__main__":
    print("Launching AI Paper Trading Bot Dashboard on http://127.0.0.1:5000 ...")
    app.run(host="127.0.0.1", port=5000, debug=False)

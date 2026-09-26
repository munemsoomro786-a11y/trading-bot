import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from config import load_config, save_config
from bot_runner import bot_runner_instance
from backtester import Backtester

app = FastAPI(title="AI Paper Trading Bot Dashboard", version="1.0.0")

# Serve Static files for UI
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.on_event("startup")
def startup_event():
    print("Starting AI Paper Trading Bot Engine...")
    bot_runner_instance.start()

@app.get("/")
def read_root():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/api/status")
def get_status():
    stats = bot_runner_instance.account.get_stats()
    config = load_config()
    return {
        "is_running": bot_runner_instance.is_running,
        "config": config,
        "stats": stats,
        "market_prices": bot_runner_instance.market_prices
    }

@app.get("/api/positions")
def get_positions():
    return {
        "positions": bot_runner_instance.account.positions
    }

@app.get("/api/trades")
def get_trades():
    return {
        "trades": bot_runner_instance.account.trades
    }

@app.get("/api/logs")
def get_logs():
    return {
        "logs": bot_runner_instance.logs
    }

@app.get("/api/chart")
def get_chart_data(symbol: str = "BTC/USDT", timeframe: str = "15m", limit: int = 150):
    df = bot_runner_instance.fetcher.fetch_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit)
    if df is None or df.empty:
        return {"error": "Failed to fetch chart data"}
    
    # Enrich with indicators
    from indicators import add_all_indicators
    df = add_all_indicators(df)

    candles = []
    for _, row in df.iterrows():
        candles.append({
            "time": int(row['timestamp'].timestamp()),
            "open": float(row['open']),
            "high": float(row['high']),
            "low": float(row['low']),
            "close": float(row['close']),
            "volume": float(row['volume']),
            "ema_fast": float(row['ema_fast']) if 'ema_fast' in row and not pd.isna(row['ema_fast']) else None,
            "ema_slow": float(row['ema_slow']) if 'ema_slow' in row and not pd.isna(row['ema_slow']) else None,
            "rsi": float(row['rsi']) if 'rsi' in row and not pd.isna(row['rsi']) else None
        })
    
    # Get current strategy analysis for this symbol
    analysis = bot_runner_instance.strategy.analyze(df)

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "candles": candles,
        "analysis": analysis
    }

class ConfigUpdateRequest(BaseModel):
    risk_per_trade_pct: float = None
    risk_reward_ratio: float = None
    timeframe: str = None
    symbol: str = None

@app.post("/api/config")
def update_config(req: ConfigUpdateRequest):
    cfg = load_config()
    if req.risk_per_trade_pct is not None:
        cfg["risk_per_trade_pct"] = req.risk_per_trade_pct
    if req.risk_reward_ratio is not None:
        cfg["risk_reward_ratio"] = req.risk_reward_ratio
    if req.timeframe is not None:
        cfg["timeframe"] = req.timeframe
    if req.symbol is not None:
        cfg["symbol"] = req.symbol
    save_config(cfg)
    bot_runner_instance.config = cfg
    return {"success": True, "config": cfg}

@app.post("/api/bot/start")
def start_bot():
    bot_runner_instance.start()
    return {"success": True, "message": "Bot started"}

@app.post("/api/bot/pause")
def pause_bot():
    bot_runner_instance.pause()
    return {"success": True, "message": "Bot paused"}

@app.post("/api/bot/reset")
def reset_bot(balance: float = 10000.0):
    bot_runner_instance.account.reset_account(balance)
    bot_runner_instance.log(f"Account reset to ${balance:.2f}", "WARNING")
    return {"success": True, "message": f"Account reset to ${balance}"}

class ClosePositionRequest(BaseModel):
    position_id: str

@app.post("/api/position/close")
def close_position(req: ClosePositionRequest):
    symbol = None
    for p in bot_runner_instance.account.positions:
        if p["id"] == req.position_id:
            symbol = p["symbol"]
            break
    current_price = bot_runner_instance.market_prices.get(symbol, 0.0) if symbol else 0.0
    if current_price == 0.0 and symbol:
        current_price = bot_runner_instance.fetcher.fetch_current_price(symbol)

    res = bot_runner_instance.account.close_position_manually(req.position_id, current_price)
    if res.get("success"):
        bot_runner_instance.log(f"Manual Close executed for {req.position_id}", "INFO")
    return res

class BacktestRequest(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "15m"
    limit: int = 500

@app.post("/api/backtest")
def run_backtest(req: BacktestRequest):
    backtester = Backtester(
        initial_balance=bot_runner_instance.account.initial_balance,
        risk_pct=bot_runner_instance.config.get("risk_per_trade_pct", 2.0)
    )
    result = backtester.run(symbol=req.symbol, timeframe=req.timeframe, limit=req.limit)
    return result

import pandas as pd

import os
import json

CONFIG_FILE = "trading_config.json"

DEFAULT_CONFIG = {
    "symbol": "BTC/USDT",
    "timeframe": "15m",
    "initial_balance": 100.0,     # $100 Starting Balance
    "risk_per_trade_pct": 2.0,    # Risk 2% of total equity per trade
    "risk_reward_ratio": 1.5,     # 1:1.5 Risk to Reward Ratio
    "atr_sl_multiplier": 2.0,     # Stop Loss distance = 2.0 * ATR
    "adx_threshold": 22.0,        # Trend filter threshold (Noise Protection)
    "max_open_positions": 2,      # Max 2 concurrent positions
    "pairs_to_monitor": [
        "BTC/USDT", 
        "ETH/USDT", 
        "SOL/USDT"
    ],
    "bot_active": True,
    "poll_interval_seconds": 5,
    "strategy_parameters": {
        "ema_fast": 9,
        "ema_slow": 21,
        "ema_trend": 200,
        "rsi_period": 14,
        "rsi_oversold": 40,
        "rsi_overbought": 60,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "atr_period": 14
    }
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                merged = DEFAULT_CONFIG.copy()
                merged.update(config)
                return merged
        except Exception as e:
            print(f"Error loading config, using defaults: {e}")
    return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

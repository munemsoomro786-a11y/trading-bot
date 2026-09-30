import pandas as pd
import numpy as np
from data_fetcher import DataFetcher
from strategy import TradingStrategy
from indicators import add_all_indicators

class Backtester:
    def __init__(self, initial_balance: float = 10000.0, risk_pct: float = 2.0):
        self.initial_balance = initial_balance
        self.risk_pct = risk_pct
        self.fetcher = DataFetcher()

    def run(self, symbol: str = "BTC/USDT", timeframe: str = "15m", limit: int = 500) -> dict:
        """Run historical backtest on given symbol."""
        df = self.fetcher.fetch_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit)
        if df is None or df.empty or len(df) < 50:
            return {"error": "Failed to fetch sufficient historical data for backtest"}

        # Calculate indicators for whole dataframe
        df = add_all_indicators(df)
        strategy = TradingStrategy()

        balance = self.initial_balance
        open_position = None
        trades = []
        equity_curve = []

        # Iterate through candles (starting from index 30 to allow indicator warmup)
        for i in range(30, len(df)):
            sub_df = df.iloc[:i+1].copy()
            current_candle = sub_df.iloc[-1]
            close_price = float(current_candle['close'])
            high_price = float(current_candle['high'])
            low_price = float(current_candle['low'])
            timestamp_str = str(current_candle['timestamp'])

            # 1. Check if we have an open position to evaluate SL / TP
            if open_position:
                side = open_position['side']
                sl = open_position['stop_loss']
                tp = open_position['take_profit']
                units = open_position['units']
                entry = open_position['entry_price']

                closed = False
                exit_price = 0.0
                reason = ""

                if side == "BUY":
                    # Move SL to Break-Even if price reaches >= 1.0% profit
                    max_pnl_pct = ((high_price - entry) / entry) * 100.0
                    if max_pnl_pct >= 1.00 and sl < entry:
                        sl = round(entry * 1.0005, 4)

                    if low_price <= sl:
                        closed = True
                        exit_price = sl
                        reason = "BREAK_EVEN" if sl >= entry else "STOP_LOSS"
                    elif high_price >= tp:
                        closed = True
                        exit_price = tp
                        reason = "TAKE_PROFIT"
                else:  # SELL (Short)
                    # Move SL to Break-Even if price reaches >= 1.0% profit
                    max_pnl_pct = ((entry - low_price) / entry) * 100.0
                    if max_pnl_pct >= 1.00 and sl > entry:
                        sl = round(entry * 0.9995, 4)

                    if high_price >= sl:
                        closed = True
                        exit_price = sl
                        reason = "BREAK_EVEN" if sl <= entry else "STOP_LOSS"
                    elif low_price <= tp:
                        closed = True
                        exit_price = tp
                        reason = "TAKE_PROFIT"

                if closed:
                    pnl = (exit_price - entry) * units if side == "BUY" else (entry - exit_price) * units
                    pnl_pct = ((exit_price - entry) / entry) * 100.0 if side == "BUY" else ((entry - exit_price) / entry) * 100.0
                    balance += pnl

                    trades.append({
                        "symbol": symbol,
                        "side": side,
                        "entry_price": entry,
                        "exit_price": exit_price,
                        "stop_loss": sl,
                        "take_profit": tp,
                        "pnl": round(pnl, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "opened_at": open_position['opened_at'],
                        "closed_at": timestamp_str,
                        "close_reason": reason,
                        "is_win": pnl > 0
                    })
                    open_position = None

            # 2. If no position open, check strategy signal
            if not open_position:
                analysis = strategy.analyze(sub_df)
                sig = analysis['signal']

                if sig in ["BUY", "SELL"]:
                    entry_price = close_price
                    sl = analysis['stop_loss']
                    tp = analysis['take_profit']
                    sl_dist = abs(entry_price - sl)

                    if sl_dist > 0:
                        risk_amount = balance * (self.risk_pct / 100.0)
                        units = risk_amount / sl_dist
                        
                        # Max 30% balance per position
                        max_val = balance * 0.30
                        if units * entry_price > max_val:
                            units = max_val / entry_price

                        open_position = {
                            "symbol": symbol,
                            "side": sig,
                            "entry_price": entry_price,
                            "stop_loss": sl,
                            "take_profit": tp,
                            "units": units,
                            "opened_at": timestamp_str
                        }

            # Track equity curve
            current_unrealized = 0.0
            if open_position:
                units = open_position['units']
                entry = open_position['entry_price']
                side = open_position['side']
                current_unrealized = (close_price - entry) * units if side == "BUY" else (entry - close_price) * units

            equity_curve.append({
                "timestamp": timestamp_str,
                "equity": round(balance + current_unrealized, 2),
                "close": close_price
            })

        # Summary Stats
        total_trades = len(trades)
        wins = [t for t in trades if t['is_win']]
        losses = [t for t in trades if not t['is_win']]
        win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0

        total_profit = sum(t['pnl'] for t in wins)
        total_loss = abs(sum(t['pnl'] for t in losses))
        profit_factor = (total_profit / total_loss) if total_loss > 0 else (total_profit if total_profit > 0 else 1.0)
        net_profit = balance - self.initial_balance
        net_profit_pct = (net_profit / self.initial_balance) * 100.0

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "total_candles": len(df),
            "initial_balance": self.initial_balance,
            "final_balance": round(balance, 2),
            "net_profit": round(net_profit, 2),
            "net_profit_pct": round(net_profit_pct, 2),
            "total_trades": total_trades,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(win_rate, 1),
            "profit_factor": round(profit_factor, 2),
            "trades": trades[-20:],  # Return last 20 trades
            "equity_curve": equity_curve[::5]  # Downsample for quick charting
        }

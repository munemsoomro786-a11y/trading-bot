import os
import json
import time
from datetime import datetime

DATA_FILE = "paper_account_data.json"

class PaperAccount:
    def __init__(self, initial_balance: float = 50.0):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.positions = []  # Open active positions
        self.trades = []     # Closed trade history
        self.load_data()

    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    data = json.load(f)
                    self.initial_balance = data.get("initial_balance", self.initial_balance)
                    self.balance = data.get("balance", self.balance)
                    self.positions = data.get("positions", [])
                    self.trades = data.get("trades", [])
                    print(f"Loaded paper account: Balance=${self.balance:.2f}, Active Positions={len(self.positions)}")
            except Exception as e:
                print(f"Error loading paper account data: {e}")

    def save_data(self):
        try:
            with open(DATA_FILE, "w") as f:
                json.dump({
                    "initial_balance": self.initial_balance,
                    "balance": self.balance,
                    "positions": self.positions,
                    "trades": self.trades,
                    "updated_at": datetime.now().isoformat()
                }, f, indent=4)
        except Exception as e:
            print(f"Error saving paper account data: {e}")

    def open_position(self, symbol: str, side: str, price: float, stop_loss: float, take_profit: float, risk_pct: float = 2.0) -> dict:
        """Execute a new paper trade with SL and TP."""
        # Check if position already open for this symbol
        for pos in self.positions:
            if pos["symbol"] == symbol:
                return {"success": False, "message": f"Position already open for {symbol}"}

        # Calculate position size based on risk percentage
        sl_distance = abs(price - stop_loss)
        if sl_distance <= 0:
            sl_distance = price * 0.015

        risk_amount = self.balance * (risk_pct / 100.0)
        # Position size in asset units
        units = risk_amount / sl_distance
        position_value = units * price

        # Limit maximum position value to 30% of total balance (leverage prevention)
        max_position_value = self.balance * 0.30
        if position_value > max_position_value:
            position_value = max_position_value
            units = position_value / price

        position = {
            "id": f"pos_{int(time.time() * 1000)}",
            "symbol": symbol,
            "side": side,  # "BUY" (Long) or "SELL" (Short)
            "entry_price": round(price, 4),
            "units": round(units, 6),
            "position_value": round(position_value, 2),
            "stop_loss": round(stop_loss, 4),
            "take_profit": round(take_profit, 4),
            "opened_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "current_price": round(price, 4),
            "unrealized_pnl": 0.0,
            "unrealized_pnl_pct": 0.0
        }

        self.positions.append(position)
        self.save_data()
        return {"success": True, "position": position}

    def update_positions(self, market_prices: dict) -> list:
        """Update active open positions with current prices and check SL/TP hits."""
        closed_in_tick = []
        remaining_positions = []

        for pos in self.positions:
            symbol = pos["symbol"]
            current_price = market_prices.get(symbol, pos["current_price"])
            pos["current_price"] = round(current_price, 4)

            entry = pos["entry_price"]
            side = pos["side"]
            sl = pos["stop_loss"]
            tp = pos["take_profit"]
            units = pos["units"]

            # Calculate unrealized PnL
            if side == "BUY":
                pnl = (current_price - entry) * units
                pnl_pct = ((current_price - entry) / entry) * 100.0
            else:  # SELL (Short)
                pnl = (entry - current_price) * units
                pnl_pct = ((entry - current_price) / entry) * 100.0

            pos["unrealized_pnl"] = round(pnl, 2)
            pos["unrealized_pnl_pct"] = round(pnl_pct, 2)

            # Break-Even Stop Loss Logic (Move SL to Entry after 0.55% Profit)
            if side == "BUY":
                # Move to Break-Even when profit >= 0.55%
                if pnl_pct >= 0.55 and sl < entry:
                    pos["stop_loss"] = round(entry * 1.0005, 4)  # Break-Even + tiny buffer
            else:  # SELL (Short)
                # Move to Break-Even when profit >= 0.55%
                if pnl_pct >= 0.55 and sl > entry:
                    pos["stop_loss"] = round(entry * 0.9995, 4)  # Break-Even

            # Re-read SL and TP
            sl = pos["stop_loss"]
            tp = pos["take_profit"]

            if side == "BUY":
                hit_sl = current_price <= sl
                hit_tp = current_price >= tp
            else:  # SELL (Short)
                hit_sl = current_price >= sl
                hit_tp = current_price <= tp

            # Check for SL or TP hit
            if hit_tp:
                close_res = self._close_position_internal(pos, tp, "TAKE_PROFIT")
                closed_in_tick.append(close_res)
            elif hit_sl:
                reason = "BREAK_EVEN" if (side == "BUY" and sl >= entry) or (side == "SELL" and sl <= entry) else "STOP_LOSS"
                close_res = self._close_position_internal(pos, sl, reason)
                closed_in_tick.append(close_res)
            else:
                remaining_positions.append(pos)

        self.positions = remaining_positions
        if closed_in_tick:
            self.save_data()

        return closed_in_tick

    def close_position_manually(self, position_id: str, current_price: float) -> dict:
        """Close an open position manually."""
        for pos in self.positions:
            if pos["id"] == position_id:
                close_res = self._close_position_internal(pos, current_price, "MANUAL_CLOSE")
                self.positions = [p for p in self.positions if p["id"] != position_id]
                self.save_data()
                return {"success": True, "trade": close_res}
        return {"success": False, "message": "Position ID not found"}

    def _close_position_internal(self, pos: dict, exit_price: float, reason: str) -> dict:
        entry = pos["entry_price"]
        units = pos["units"]
        side = pos["side"]

        if side == "BUY":
            pnl = (exit_price - entry) * units
            pnl_pct = ((exit_price - entry) / entry) * 100.0
        else:
            pnl = (entry - exit_price) * units
            pnl_pct = ((entry - exit_price) / entry) * 100.0

        self.balance += pnl

        trade = {
            "id": pos["id"],
            "symbol": pos["symbol"],
            "side": side,
            "entry_price": entry,
            "exit_price": round(exit_price, 4),
            "units": units,
            "stop_loss": pos["stop_loss"],
            "take_profit": pos["take_profit"],
            "opened_at": pos["opened_at"],
            "closed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "close_reason": reason,
            "is_win": pnl > 0
        }

        self.trades.insert(0, trade)  # Insert newest trade at beginning
        return trade

    def get_stats(self) -> dict:
        """Get summary stats for dashboard."""
        unrealized_pnl = sum(p["unrealized_pnl"] for p in self.positions)
        equity = self.balance + unrealized_pnl

        total_trades = len(self.trades)
        wins = [t for t in self.trades if t["is_win"]]
        losses = [t for t in self.trades if not t["is_win"]]

        win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0

        total_profit = sum(t["pnl"] for t in wins)
        total_loss = abs(sum(t["pnl"] for t in losses))

        profit_factor = (total_profit / total_loss) if total_loss > 0 else (total_profit if total_profit > 0 else 1.0)
        net_pnl = self.balance - self.initial_balance
        pnl_pct = (net_pnl / self.initial_balance) * 100.0

        return {
            "initial_balance": round(self.initial_balance, 2),
            "balance": round(self.balance, 2),
            "equity": round(equity, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "net_pnl": round(net_pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "total_trades": total_trades,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(win_rate, 1),
            "profit_factor": round(profit_factor, 2),
            "open_positions_count": len(self.positions)
        }

    def reset_account(self, new_balance: float = 10000.0):
        """Reset paper account balance and clear trade history."""
        self.initial_balance = new_balance
        self.balance = new_balance
        self.positions = []
        self.trades = []
        self.save_data()

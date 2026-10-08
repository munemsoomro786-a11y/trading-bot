import time
import threading
from datetime import datetime
from config import load_config
from data_fetcher import DataFetcher
from strategy import TradingStrategy
from paper_account import PaperAccount

class TradingBotRunner:
    def __init__(self):
        self.config = load_config()
        self.fetcher = DataFetcher()
        self.strategy = TradingStrategy(self.config)
        self.account = PaperAccount(self.config.get("initial_balance", 10000.0))
        
        self.is_running = False
        self.thread = None
        self.logs = []
        self.market_prices = {}
        self.symbol_cooldowns = {}

    def log(self, message: str, level: str = "INFO"):
        """Add timestamped log entry."""
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "message": message
        }
        self.logs.insert(0, entry)
        if len(self.logs) > 100:
            self.logs.pop()
        try:
            print(f"[{entry['timestamp']}] [{level}] {message}")
        except Exception:
            # Fallback for Windows cp1252 terminal encoding
            print(f"[{entry['timestamp']}] [{level}] {message.encode('ascii', 'ignore').decode('ascii')}")

    def start(self):
        """Start the background trading loop."""
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        self.log("🚀 Automated Paper Trading Bot Started!", "SUCCESS")

    def pause(self):
        """Pause the background trading loop."""
        self.is_running = False
        self.log("⏸️ Paper Trading Bot Paused.", "WARNING")

    def _run_loop(self):
        """Main real-time background execution loop."""
        while self.is_running:
            try:
                self.config = load_config()
                pairs = self.config.get("pairs_to_monitor", ["BTC/USDT", "ETH/USDT", "SOL/USDT"])
                timeframe = self.config.get("timeframe", "15m")
                max_positions = self.config.get("max_open_positions", 3)
                risk_pct = self.config.get("risk_per_trade_pct", 2.0)

                for symbol in pairs:
                    if not self.is_running:
                        break

                    # Fetch market data
                    df = self.fetcher.fetch_ohlcv(symbol, timeframe=timeframe, limit=100)
                    if df is None or df.empty:
                        continue

                    htf_df = self.fetcher.fetch_ohlcv(symbol, timeframe="1h", limit=50)

                    current_price = float(df['close'].iloc[-1])
                    self.market_prices[symbol] = current_price

                    # 1. Check for Early Signal Invalidation on active positions
                    for pos in list(self.account.positions):
                        if pos["symbol"] == symbol:
                            analysis = self.strategy.analyze(df, htf_df=htf_df)
                            sig = analysis["signal"]
                            side = pos["side"]

                            # If active LONG and signal turns SELL, or active SHORT and signal turns BUY
                            if (side == "BUY" and sig == "SELL") or (side == "SELL" and sig == "BUY"):
                                res = self.account.close_position_manually(pos["id"], current_price)
                                if res.get("success"):
                                    self.log(f"⚡ EARLY EXIT executed for {symbol} due to opposite market signal ({sig})", "WARNING")

                    # 2. Update active positions with live market price & check SL/TP
                    closed_trades = self.account.update_positions(self.market_prices)
                    for trade in closed_trades:
                        if trade["close_reason"] == "TAKE_PROFIT":
                            status = "🎯 TAKE PROFIT HIT"
                        elif trade["close_reason"] in ["BREAK_EVEN", "TRAILING_STOP_LOSS"]:
                            status = "🛡️ BREAK-EVEN HIT (NO LOSS)"
                        else:
                            status = "🛑 STOP LOSS HIT"
                            # Cooldown: Block re-entering this symbol for 45 minutes (2700s) after SL hit
                            self.symbol_cooldowns[trade["symbol"]] = time.time() + 2700
                            self.log(f"⏳ Cooldown activated for {trade['symbol']} (45 min pause after SL hit).", "WARNING")
                        
                        pnl_str = f"+${trade['pnl']:.2f}" if trade['pnl'] > 0 else f"-${abs(trade['pnl']):.2f}"
                        self.log(f"{status} on {trade['symbol']} ({trade['side']}) at ${trade['exit_price']:.2f}. PnL: {pnl_str}", "SUCCESS" if trade['pnl'] > 0 else "ERROR")

                    # 3. If bot active and positions under limit, evaluate strategy signal
                    if len(self.account.positions) < max_positions:
                        # Check if symbol is under loss cooldown
                        cooldown_until = self.symbol_cooldowns.get(symbol, 0)
                        if time.time() < cooldown_until:
                            continue

                        analysis = self.strategy.analyze(df, htf_df=htf_df)
                        sig = analysis["signal"]
                        reason = analysis["reason"]

                        if sig in ["BUY", "SELL"]:
                            sl = analysis["stop_loss"]
                            tp = analysis["take_profit"]

                            res = self.account.open_position(
                                symbol=symbol,
                                side=sig,
                                price=current_price,
                                stop_loss=sl,
                                take_profit=tp,
                                risk_pct=risk_pct
                            )

                            if res.get("success"):
                                pos = res["position"]
                                self.log(f"⚡ ORDER EXECUTED ({sig}) on {symbol} @ ${current_price:.2f} | SL: ${sl:.2f} | TP: ${tp:.2f} | Risk: {risk_pct}%", "ORDER")
                            else:
                                pass # Position already open

            except Exception as e:
                self.log(f"Error in bot trading loop: {e}", "ERROR")

            # Sleep between iterations
            poll_seconds = self.config.get("poll_interval_seconds", 10)
            time.sleep(poll_seconds)

bot_runner_instance = TradingBotRunner()

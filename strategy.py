import pandas as pd
import numpy as np
from indicators import add_all_indicators

class TradingStrategy:
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.rr_ratio = self.config.get("risk_reward_ratio", 2.0)
        self.atr_sl_mult = self.config.get("atr_sl_multiplier", 1.5)
        self.adx_threshold = self.config.get("adx_threshold", 15.0)

    def analyze(self, df: pd.DataFrame, htf_df: pd.DataFrame = None) -> dict:
        """
        HIGH-ACCURACY BALANCED MULTI-CONFLUENCE STRATEGY ENGINE:
        1. Multi-Timeframe (MTF) 1-Hour Macro Trend Alignment.
        2. ADX Market Regime Filter (> 15.0 Trend Strength).
        3. Support & Resistance / Pivot Level Filter.
        4. Candlestick Price Action & Early Breakdown/Breakout Confirmation.
        5. ATR Volatility-Based Stop Loss & Take Profit.
        """
        if df is None or len(df) < 30:
            return {"signal": "HOLD", "reason": "Insufficient candle data", "current_price": 0.0}

        df = add_all_indicators(df, self.config.get("strategy_parameters", {}))
        
        # Use OFFICIALLY CLOSED candle (df.iloc[-2]) to prevent mid-candle signal flipping!
        closed_candle = df.iloc[-2]
        prev_candle = df.iloc[-3]
        live_candle = df.iloc[-1]
        
        current_live_price = float(live_candle['close'])
        
        close = float(closed_candle['close'])
        open_p = float(closed_candle['open'])
        
        ema_fast = float(closed_candle['ema_fast'])
        ema_slow = float(closed_candle['ema_slow'])
        ema_trend = float(closed_candle['ema_trend'])
        
        prev_ema_fast = float(prev_candle['ema_fast'])
        prev_ema_slow = float(prev_candle['ema_slow'])
        
        prev_close = float(prev_candle['close'])
        prev_low = float(prev_candle['low'])
        prev_high = float(prev_candle['high'])
        
        rsi = float(closed_candle['rsi'])
        prev_rsi = float(prev_candle['rsi'])
        
        macd_hist = float(closed_candle['macd_hist'])
        prev_macd_hist = float(prev_candle['macd_hist'])
        
        adx = float(closed_candle['adx']) if 'adx' in closed_candle and not np.isnan(closed_candle['adx']) else 25.0
        atr = float(closed_candle['atr']) if 'atr' in closed_candle and not np.isnan(closed_candle['atr']) else current_live_price * 0.015
        
        support = float(closed_candle['support']) if 'support' in closed_candle else current_live_price * 0.98
        resistance = float(closed_candle['resistance']) if 'resistance' in closed_candle else current_live_price * 1.02
        pivot = float(closed_candle['pivot']) if 'pivot' in closed_candle else current_live_price
        
        pattern_bullish = bool(closed_candle.get('pattern_bullish', False))
        pattern_bearish = bool(closed_candle.get('pattern_bearish', False))
        pattern_name = str(closed_candle.get('pattern_name', 'None'))

        # Volume Confirmation (> 0.95x Volume SMA for Balanced Active Trading)
        vol_sma = df['volume'].rolling(window=20).mean().iloc[-2] if 'volume' in df.columns else 0
        closed_vol = float(closed_candle['volume']) if 'volume' in closed_candle else 0
        volume_surge = (closed_vol >= vol_sma * 0.95) if vol_sma > 0 else True

        # =========================================================================
        # 1. MULTI-TIMEFRAME (MTF) HIGHER TIMEFRAME TREND FILTER (1-HOUR CHART)
        # =========================================================================
        htf_macro_uptrend = True
        htf_macro_downtrend = True
        
        if htf_df is not None and len(htf_df) >= 30:
            htf_df = add_all_indicators(htf_df, self.config.get("strategy_parameters", {}))
            htf_closed = htf_df.iloc[-2]
            htf_close = float(htf_closed['close'])
            htf_ema_trend = float(htf_closed['ema_trend'])
            htf_macro_uptrend = htf_close > htf_ema_trend
            htf_macro_downtrend = htf_close < htf_ema_trend

        signal = "HOLD"
        reason = "Monitoring Multi-Confluence Aligned Signals..."
        stop_loss = 0.0
        take_profit = 0.0

        # MACRO TREND ON LOCAL TIMEFRAME
        is_macro_uptrend = (close > ema_trend) and htf_macro_uptrend
        is_macro_downtrend = (close < ema_trend) and htf_macro_downtrend

        # Volatility Spike / News Event Filter (Candle range > 2.5x ATR)
        candle_high = float(closed_candle['high'])
        candle_low = float(closed_candle['low'])
        candle_range = candle_high - candle_low
        volatility_spike = (candle_range >= 2.5 * atr)

        if volatility_spike:
            return {
                "signal": "HOLD",
                "reason": f"⚠️ Extreme Volatility / News Event Spike Detected ({candle_range:.1f} > 2.5x ATR). Trade paused.",
                "current_price": current_live_price,
                "stop_loss": 0.0,
                "take_profit": 0.0,
                "atr": round(atr, 4),
                "adx": round(adx, 2),
                "rsi": round(rsi, 2),
                "ema_fast": round(ema_fast, 2),
                "ema_slow": round(ema_slow, 2),
                "macd_hist": round(macd_hist, 4),
                "pattern_name": pattern_name
            }

        # =========================================================================
        # 2. ADX MARKET REGIME CHECK (Block Trades in Weak Sideways Market < 15.0)
        # =========================================================================
        is_trending_market = adx >= self.adx_threshold

        if not is_trending_market:
            reason = f"⚠️ Low Trend Strength (ADX: {adx:.1f} < {self.adx_threshold}). Sideways market trade blocked."
            return {
                "signal": "HOLD",
                "reason": reason,
                "current_price": current_live_price,
                "stop_loss": 0.0,
                "take_profit": 0.0,
                "atr": round(atr, 4),
                "adx": round(adx, 2),
                "rsi": round(rsi, 2),
                "ema_fast": round(ema_fast, 2),
                "ema_slow": round(ema_slow, 2),
                "macd_hist": round(macd_hist, 4),
                "pattern_name": pattern_name
            }

        # =========================================================================
        # 3. BULLISH LONG CONFLUENCE (Allowed ONLY in MTF & Local Uptrend)
        # =========================================================================
        if is_macro_uptrend:
            # FIX B: Early Trigger via High Breakout + EMA alignment
            ema_aligned = (prev_ema_fast <= prev_ema_slow and ema_fast > ema_slow) or \
                          (ema_fast > ema_slow and (ema_fast - ema_slow) > (prev_ema_fast - prev_ema_slow)) or \
                          (close > prev_high and close > ema_fast and macd_hist > prev_macd_hist)
                          
            rsi_bullish = 38 <= rsi <= 72 and rsi > prev_rsi
            macd_bullish = macd_hist > prev_macd_hist or macd_hist > 0
            bullish_candle = close > open_p
            
            # S/R Filter: Avoid buying directly into major Resistance level
            not_at_resistance = close < (resistance * 0.998)

            # FIX A: Avoid buying when already overbought/extended far above EMA
            not_overextended_long = ((close - ema_slow) / ema_slow <= 0.018) and (rsi <= 68)

            if ema_aligned and rsi_bullish and macd_bullish and volume_surge and bullish_candle and not_at_resistance and not_overextended_long:
                signal = "BUY"
                pattern_str = f" + Pattern ({pattern_name})" if pattern_bullish else ""
                reason = f"🚀 [MTF UPTREND] Bullish Confluence: Early Trigger/EMA + ADX ({adx:.1f}) + RSI ({rsi:.1f}){pattern_str}"
                sl_dist = max(atr * self.atr_sl_mult, current_live_price * 0.012)
                stop_loss = current_live_price - sl_dist
                take_profit = current_live_price + (sl_dist * self.rr_ratio)

        # =========================================================================
        # 4. BEARISH SHORT CONFLUENCE (Allowed ONLY in MTF & Local Downtrend)
        # =========================================================================
        elif is_macro_downtrend:
            # FIX B: Early Trigger via Low Breakdown + EMA alignment
            ema_bearish_aligned = (prev_ema_fast >= prev_ema_slow and ema_fast < ema_slow) or \
                                  (ema_fast < ema_slow and (ema_slow - ema_fast) > (prev_ema_slow - prev_ema_slow)) or \
                                  (close < prev_low and close < ema_fast and macd_hist < prev_macd_hist)

            rsi_bearish = 28 <= rsi <= 62 and rsi < prev_rsi
            macd_bearish = macd_hist < prev_macd_hist or macd_hist < 0
            bearish_candle = close < open_p
            
            # S/R Filter: Avoid shorting directly into major Support level
            not_at_support = close > (support * 1.002)

            # FIX A: Avoid shorting when already oversold/extended far below EMA (Prevents Bottom Shorting)
            not_overextended_short = ((ema_slow - close) / ema_slow <= 0.018) and (rsi >= 32)

            if ema_bearish_aligned and rsi_bearish and macd_bearish and volume_surge and bearish_candle and not_at_support and not_overextended_short:
                signal = "SELL"
                pattern_str = f" + Pattern ({pattern_name})" if pattern_bearish else ""
                reason = f"📉 [MTF DOWNTREND] Bearish Confluence: Early Breakdown/EMA + ADX ({adx:.1f}) + RSI ({rsi:.1f}){pattern_str}"
                sl_dist = max(atr * self.atr_sl_mult, current_live_price * 0.012)
                stop_loss = current_live_price + sl_dist
                take_profit = current_live_price - (sl_dist * self.rr_ratio)

        return {
            "signal": signal,
            "reason": reason,
            "current_price": current_live_price,
            "stop_loss": round(stop_loss, 4),
            "take_profit": round(take_profit, 4),
            "atr": round(atr, 4),
            "adx": round(adx, 2),
            "rsi": round(rsi, 2),
            "ema_fast": round(ema_fast, 2),
            "ema_slow": round(ema_slow, 2),
            "macd_hist": round(macd_hist, 4),
            "support": round(support, 2),
            "resistance": round(resistance, 2),
            "pattern_name": pattern_name
        }


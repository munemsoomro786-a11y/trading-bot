import pandas as pd
import numpy as np

def calculate_ema(df: pd.DataFrame, period: int, column: str = 'close') -> pd.Series:
    """Calculate Exponential Moving Average."""
    return df[column].ewm(span=period, adjust=False).mean()

def calculate_rsi(df: pd.DataFrame, period: int = 14, column: str = 'close') -> pd.Series:
    """Calculate Relative Strength Index (RSI)."""
    delta = df[column].diff()
    gain = (delta.where(delta > 0, 0)).copy()
    loss = (-delta.where(delta < 0, 0)).copy()
    
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    
    rs = avg_gain / (avg_loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9, column: str = 'close'):
    """Calculate MACD Line, Signal Line, and Histogram."""
    ema_fast = df[column].ewm(span=fast, adjust=False).mean()
    ema_slow = df[column].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    macd_histogram = macd_line - signal_line
    return macd_line, signal_line, macd_histogram

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range (ATR)."""
    high = df['high']
    low = df['low']
    close = df['close']
    
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    return atr

def calculate_adx(df: pd.DataFrame, period: int = 14):
    """Calculate Average Directional Index (ADX) and +DI / -DI to filter market regime and trend direction."""
    high = df['high']
    low = df['low']
    close = df['close']

    up_move = high.diff()
    down_move = -low.diff()

    pos_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    neg_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = calculate_atr(df, period=1)  # 1-period TR
    tr_smoothed = tr.ewm(alpha=1/period, adjust=False).mean()

    pos_di = 100 * (pd.Series(pos_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / (tr_smoothed + 1e-10))
    neg_di = 100 * (pd.Series(neg_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / (tr_smoothed + 1e-10))

    dx = 100 * (pos_di - neg_di).abs() / (pos_di + neg_di + 1e-10)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    return adx, pos_di, neg_di

def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0, column: str = 'close'):
    """Calculate Bollinger Bands (Middle, Upper, Lower)."""
    sma = df[column].rolling(window=period).mean()
    rolling_std = df[column].rolling(window=period).std()
    upper = sma + (rolling_std * std_dev)
    lower = sma - (rolling_std * std_dev)
    return sma, upper, lower

def calculate_support_resistance(df: pd.DataFrame, window: int = 20):
    """Calculate Swing High / Swing Low Support and Resistance levels."""
    swing_high = df['high'].rolling(window=window).max()
    swing_low = df['low'].rolling(window=window).min()
    pivot = (df['high'] + df['low'] + df['close']) / 3.0
    return swing_low, swing_high, pivot

def detect_candlestick_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """Detect Bullish/Bearish Price Action Candlestick Patterns (Engulfing, Hammer, Shooting Star)."""
    df = df.copy()
    
    open_p = df['open']
    high = df['high']
    low = df['low']
    close = df['close']
    
    prev_open = open_p.shift(1)
    prev_close = close.shift(1)
    
    body = (close - open_p).abs()
    prev_body = (prev_close - prev_open).abs()
    candle_range = high - low
    
    # 1. Bullish Engulfing
    bullish_engulfing = (prev_close < prev_open) & (close > open_p) & (close >= prev_open) & (open_p <= prev_close)
    
    # 2. Bullish Hammer / Pin Bar (Long lower wick, small body at top)
    lower_wick = np.minimum(open_p, close) - low
    upper_wick = high - np.maximum(open_p, close)
    bullish_hammer = (lower_wick >= 2.0 * body) & (upper_wick <= 0.5 * body) & (candle_range > 0)
    
    # 3. Bearish Engulfing
    bearish_engulfing = (prev_close > prev_open) & (close < open_p) & (close <= prev_open) & (open_p >= prev_close)
    
    # 4. Bearish Shooting Star / Pin Bar (Long upper wick, small body at bottom)
    bearish_shooting_star = (upper_wick >= 2.0 * body) & (lower_wick <= 0.5 * body) & (candle_range > 0)
    
    df['pattern_bullish'] = bullish_engulfing | bullish_hammer
    df['pattern_bearish'] = bearish_engulfing | bearish_shooting_star
    
    # String representation for logs
    pattern_names = []
    for i in range(len(df)):
        if bullish_engulfing.iloc[i]:
            pattern_names.append("Bullish Engulfing")
        elif bullish_hammer.iloc[i]:
            pattern_names.append("Bullish Hammer")
        elif bearish_engulfing.iloc[i]:
            pattern_names.append("Bearish Engulfing")
        elif bearish_shooting_star.iloc[i]:
            pattern_names.append("Bearish Shooting Star")
        else:
            pattern_names.append("None")
            
    df['pattern_name'] = pattern_names
    return df

def add_all_indicators(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    """Enrich dataframe with all necessary technical analysis indicators."""
    if df is None or df.empty or len(df) < 30:
        return df
    
    p = params or {
        "ema_fast": 9,
        "ema_slow": 21,
        "ema_trend": 200,
        "rsi_period": 14,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "atr_period": 14,
        "adx_period": 14
    }
    
    df = df.copy()
    
    # Ensure float types
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col in df.columns:
            df[col] = df[col].astype(float)
            
    df['ema_fast'] = calculate_ema(df, p.get('ema_fast', 9))
    df['ema_slow'] = calculate_ema(df, p.get('ema_slow', 21))
    
    if len(df) >= p.get('ema_trend', 200):
        df['ema_trend'] = calculate_ema(df, p.get('ema_trend', 200))
    else:
        df['ema_trend'] = calculate_ema(df, min(len(df), 50))
        
    df['rsi'] = calculate_rsi(df, p.get('rsi_period', 14))
    
    macd, macd_sig, macd_hist = calculate_macd(
        df, 
        fast=p.get('macd_fast', 12), 
        slow=p.get('macd_slow', 26), 
        signal=p.get('macd_signal', 9)
    )
    df['macd'] = macd
    df['macd_signal'] = macd_sig
    df['macd_hist'] = macd_hist
    
    df['atr'] = calculate_atr(df, p.get('atr_period', 14))
    adx, pos_di, neg_di = calculate_adx(df, p.get('adx_period', 14))
    df['adx'] = adx
    df['pos_di'] = pos_di
    df['neg_di'] = neg_di
    
    bb_mid, bb_upper, bb_lower = calculate_bollinger_bands(df)
    df['bb_upper'] = bb_upper
    df['bb_lower'] = bb_lower
    
    support, resistance, pivot = calculate_support_resistance(df)
    df['support'] = support
    df['resistance'] = resistance
    df['pivot'] = pivot
    
    df = detect_candlestick_patterns(df)
    
    return df


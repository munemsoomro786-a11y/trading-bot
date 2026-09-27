import time
import requests
import pandas as pd
import numpy as np
try:
    import ccxt
except ImportError:
    ccxt = None

try:
    import yfinance as yf
except ImportError:
    yf = None

class DataFetcher:
    def __init__(self):
        self.exchange = None
        if ccxt:
            try:
                self.exchange = ccxt.binance({'enableRateLimit': True, 'timeout': 10000})
            except Exception as e:
                print(f"Warning initializing CCXT Binance: {e}")

    def fetch_crypto_binance_direct(self, symbol="BTC/USDT", timeframe="15m", limit=100) -> pd.DataFrame:
        """Fetch OHLCV directly from Binance public API endpoint without needing API key."""
        try:
            binance_symbol = symbol.replace("/", "")
            url = f"https://api.binance.com/api/v3/klines?symbol={binance_symbol}&interval={timeframe}&limit={limit}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                df = pd.DataFrame(data, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_asset_volume', 'number_of_trades',
                    'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
                ])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = df[col].astype(float)
                return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        except Exception as e:
            print(f"Direct Binance fetch error for {symbol}: {e}")
        return None

    def fetch_fear_and_greed_index() -> dict:
        """Fetch live Crypto Fear & Greed Index score and classification."""
        try:
            url = "https://api.alternative.me/fng/"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json().get('data', [])[0]
                return {
                    "score": int(data.get('value', 50)),
                    "classification": data.get('value_classification', 'Neutral')
                }
        except Exception as e:
            pass
        return {"score": 50, "classification": "Neutral"}

    def fetch_crypto_coingecko(self, symbol="BTC/USDT") -> float:
        """Fetch current price fallback from CoinGecko."""
        coin_map = {"BTC/USDT": "bitcoin", "ETH/USDT": "ethereum", "SOL/USDT": "solana"}
        coin_id = coin_map.get(symbol, "bitcoin")
        try:
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                return float(resp.json()[coin_id]['usd'])
        except Exception as e:
            pass
        return None

    def fetch_ohlcv(self, symbol="BTC/USDT", timeframe="15m", limit=100) -> pd.DataFrame:
        """Fetch OHLCV data for given symbol and timeframe."""
        # 1. Try CCXT first
        if self.exchange:
            try:
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
                if ohlcv and len(ohlcv) > 0:
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    return df
            except Exception as e:
                pass

        # 2. Try Direct Binance API
        df = self.fetch_crypto_binance_direct(symbol, timeframe, limit)
        if df is not None and not df.empty:
            return df

        # 3. Try Yahoo Finance
        if yf:
            try:
                yf_symbol = symbol.replace("/USDT", "-USD").replace("/", "-")
                interval = timeframe if timeframe in ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d'] else '15m'
                ticker = yf.Ticker(yf_symbol)
                df_yf = ticker.history(period="7d", interval=interval)
                if not df_yf.empty:
                    df_yf = df_yf.reset_index()
                    date_col = 'Datetime' if 'Datetime' in df_yf.columns else 'Date'
                    df_yf = df_yf.rename(columns={
                        date_col: 'timestamp',
                        'Open': 'open',
                        'High': 'high',
                        'Low': 'low',
                        'Close': 'close',
                        'Volume': 'volume'
                    })
                    return df_yf[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            except Exception as e:
                print(f"yfinance fetch error: {e}")

        # 4. Realistic Fallback Synthetic Generator (if internet completely down or blocked)
        print(f"Generating realistic fallback synthetic candles for {symbol}")
        return self._generate_synthetic_ohlcv(symbol, limit)

    def fetch_current_price(self, symbol="BTC/USDT") -> float:
        """Fetch latest current market price."""
        df = self.fetch_ohlcv(symbol, timeframe="1m", limit=2)
        if df is not None and not df.empty:
            return float(df['close'].iloc[-1])
        return 65000.0  # Default fallback price if unreachable

    def _generate_synthetic_ohlcv(self, symbol="BTC/USDT", limit=100) -> pd.DataFrame:
        """Generate synthetic OHLCV data for testing when offline."""
        base_price = 65000.0 if "BTC" in symbol else (3500.0 if "ETH" in symbol else 150.0)
        now = time.time() * 1000
        timestamps = [pd.to_datetime(now - (limit - i) * 15 * 60 * 1000, unit='ms') for i in range(limit)]
        
        np.random.seed(42)
        returns = np.random.normal(0.0002, 0.005, limit)
        price = base_price * np.exp(np.cumsum(returns))
        
        highs = price * (1 + np.abs(np.random.normal(0, 0.003, limit)))
        lows = price * (1 - np.abs(np.random.normal(0, 0.003, limit)))
        opens = price * (1 + np.random.normal(0, 0.002, limit))
        volumes = np.random.uniform(10, 500, limit)
        
        df = pd.DataFrame({
            'timestamp': timestamps,
            'open': opens,
            'high': highs,
            'low': lows,
            'close': price,
            'volume': volumes
        })
        return df

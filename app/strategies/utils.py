import pandas as pd
import ta

# def calculate_rsi(data, window=14) -> pd.DataFrame:
#     data = data.copy()
#     df = pd.DataFrame(data, columns=[
#         "timestamp", "open", "high", "low", "close", "volume",
#         'close_time', 'quote_asset_volume', 'trades', 'taker_base_vol',
#         'taker_quote_vol', 'ignore'
#     ])

#     df['close'] = df['close'].astype(float)

#     df["rsi"] = ta.momentum.RSIIndicator(close=df['close'], window=window).rsi()

#     return df

# def calculate_ema(data, window=20) -> pd.DataFrame:
#     data = data.copy()

#     df = pd.DataFrame(data, columns=[
#         "timestamp", "open", "high", "low", "close", "volume",
#         'close_time', 'quote_asset_volume', 'trades', 'taker_base_vol',
#         'taker_quote_vol', 'ignore'
#     ])

#     df['close'] = df['close'].astype(float)

#     df[f"ema{window}"] = ta.trend.EMAIndicator(close=df['close'], window=window).ema_indicator()

#     return df

# def calculate_adx(data, window=14) -> pd.DataFrame:
#     data = data.copy()

#     df = pd.DataFrame(data, columns=[
#         "timestamp", "open", "high", "low", "close", "volume",
#         'close_time', 'quote_asset_volume', 'trades', 'taker_base_vol',
#         'taker_quote_vol', 'ignore'
#     ])

#     df['close'] = df['close'].astype(float)
#     df['high'] = df['high'].astype(float)
#     df['low'] = df['low'].astype(float)

#     df['adx'] = ta.trend.ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=window).adx()
    
#     return df

# def calculate_sma(data, window=14) -> pd.DataFrame:
#     data = data.copy()

#     df = pd.DataFrame(data, columns=[
#         "timestamp", "open", "high", "low", "close", "volume",
#         'close_time', 'quote_asset_volume', 'trades', 'taker_base_vol',
#         'taker_quote_vol', 'ignore'
#     ])

#     df['close'] = df['close'].astype(float)

#     df['sma'] = ta.trend.SMAIndicator(close=df['close'], window=window).sma_indicator()

#     return df

# def calculate_macd(data) -> pd.DataFrame:
#     data = data.copy()

#     df = pd.DataFrame(data, columns=[
#         "timestamp", "open", "high", "low", "close", "volume",
#         'close_time', 'quote_asset_volume', 'trades', 'taker_base_vol',
#         'taker_quote_vol', 'ignore'
#     ])

#     df['close'] = df['close'].astype(float)

#     macd = ta.trend.MACD(close=df['close'])
    
#     df['macd'] = macd.macd()
#     df['macd_signal'] = macd.macd_signal()
#     df['macd_diff'] = macd.macd_diff()

#     return df




class WilliamsFractals:
    def __init__(self, high: pd.Series, low: pd.Series, window=2):
        self.high = high
        self.low = low
        self.window = window

    def bullish_williams_fractals(self) -> pd.Series:
        """
        Identifies bullish fractals where the low of the middle candle is lower than
        the lows of the surrounding candles within the specified window.
        Returns a Series with True at bullish fractal points, False otherwise.
        """
        bullish_fractals = pd.Series(False, index=self.low.index)
        
        # Ensure we have enough data points
        if len(self.low) < 2 * self.window + 1:
            return bullish_fractals
            
        for i in range(self.window, len(self.low) - self.window):
            middle_low = self.low.iloc[i]
            is_bullish = True
            
            # Check if middle candle's low is the lowest in the window
            for j in range(1, self.window + 1):
                if (self.low.iloc[i - j] <= middle_low or 
                    self.low.iloc[i + j] <= middle_low):
                    is_bullish = False
                    break
            
            bullish_fractals.iloc[i] = is_bullish
            
        return bullish_fractals

    def bearish_williams_fractals(self) -> pd.Series:
        """
        Identifies bearish fractals where the high of the middle candle is higher than
        the highs of the surrounding candles within the specified window.
        Returns a Series with True at bearish fractal points, False otherwise.
        """
        bearish_fractals = pd.Series(False, index=self.high.index)
        
        # Ensure we have enough data points
        if len(self.high) < 2 * self.window + 1:
            return bearish_fractals
            
        for i in range(self.window, len(self.high) - self.window):
            middle_high = self.high.iloc[i]
            is_bearish = True
            
            # Check if middle candle's high is the highest in the window
            for j in range(1, self.window + 1):
                if (self.high.iloc[i - j] >= middle_high or 
                    self.high.iloc[i + j] >= middle_high):
                    is_bearish = False
                    break
            
            bearish_fractals.iloc[i] = is_bearish
            
        return bearish_fractals
    

if __name__ == "__main__":
    import numpy as np

    # Sun’iy ma’lumot
    data = {
        'date': pd.date_range('2024-01-01', periods=20, freq='D'),
        'high': [
            100.0,  # 0
            101.0,  # 1
            105.0,  # 2 <- UP FRACTAL (105 > 100,101,103,102)
            103.0,  # 3
            102.0,  # 4
            104.0,  # 5
            106.0,  # 6
            110.0,  # 7 <- UP FRACTAL (110 > 104,106,108,107)
            108.0,  # 8
            107.0,  # 9
            109.0,  # 10
            111.0,  # 11
            115.0,  # 12 <- UP FRACTAL (115 > 109,111,112,113)
            112.0,  # 13
            113.0,  # 14
            114.0,  # 15
            116.0,  # 16
            118.0,  # 17 <- UP FRACTAL (118 > 114,116,117,115)
            117.0,  # 18
            115.0,  # 19
        ],
        'low': [
            98.0,   # 0
            99.0,   # 1
            103.0,  # 2
            101.0,  # 3
            95.0,   # 4 <- DOWN FRACTAL (95 < 99,103,96,97)
            96.0,   # 5
            97.0,   # 6
            105.0,  # 7
            106.0,  # 8
            92.0,   # 9 <- DOWN FRACTAL (92 < 105,106,94,95)
            94.0,   # 10
            95.0,   # 11
            110.0,  # 12
            108.0,  # 13
            88.0,   # 14 <- DOWN FRACTAL (88 < 95,108,90,91)
            90.0,   # 15
            91.0,   # 16
            115.0,  # 17
            114.0,  # 18
            113.0,  # 19
        ]
    }
    data = pd.DataFrame(data)

    wf = WilliamsFractals(data["high"], data["low"], window=2)

    data["fractal_up"] = wf.bullish_williams_fractals()
    data["fractal_down"] = wf.bearish_williams_fractals()

    print(data)

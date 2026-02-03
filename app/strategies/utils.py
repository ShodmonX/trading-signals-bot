import pandas as pd


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
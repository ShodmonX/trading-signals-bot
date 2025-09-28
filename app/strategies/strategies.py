from ta.trend import EMAIndicator, ADXIndicator, MACD, SMAIndicator
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange
import pandas as pd

from .utils import WilliamsFractals


class BaseStrategy:
    def __init__(self, data, symbol):
        self.df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            'close_time', 'quote_asset_volume', 'trades', 'taker_base_vol',
            'taker_quote_vol', 'ignore'
        ])
        self.df[['open', 'high', 'low', 'close']] = self.df[['open', 'high', 'low', 'close']].astype(float)
        self.signal = "NEUTRAL"
        self.symbol = symbol
        self.unsupported_keys = ["timestamp", "open", "high", "low", "volume", 'close_time', 'quote_asset_volume', 'trades', 'taker_base_vol', 'taker_quote_vol', 'ignore', 'long_signal', 'short_signal']
        self.stop_mul = 1.5
        self.profit_muls = [1.5, 3, 4.5]

    
    def calculate_indicators(self):
        """Child classlar o‘zlari keraklisini override qiladi"""
        raise NotImplementedError
    
    def generate_signals(self):
        """Child classlar o‘zlari override qiladi"""
        raise NotImplementedError
    
    def decide(self):
        if self.df['long_signal'].iloc[-1]:
            self.signal = "LONG"
        elif self.df['short_signal'].iloc[-1]:
            self.signal = "SHORT"

    def run(self):
        self.calculate_indicators()
        self.generate_signals()
        self.decide()
        self.calculate_stop_loss_and_take_profit()
        return self.get_context()

    def get_context(self):
        last_row = self.df.iloc[-1].to_dict()
        other_data = {k: v for k, v in last_row.items() if k not in self.unsupported_keys}
        return {
            "signal": self.signal,
            "stop_loss": last_row.get("stop_loss"),
            "take_profit_1": last_row.get("take_profit_1"),
            "take_profit_2": last_row.get("take_profit_2"),
            "take_profit_3": last_row.get("take_profit_3"),
            "close": last_row.get("close"),
            "other_data": other_data
        }
    
    def generate_text(self) -> str:
        result = self.get_context()
        text = f"{self.symbol} - {self.get_name()}\n\n"
        if result['signal'] != 'NEUTRAL':
            text += f"SIGNAL {result['signal']}{'🔴' if result['signal'] == 'SHORT' else '🔵'}\n\n"
            for key in result['other_data']:
                if key not in self.unsupported_keys:
                    text += f"{key.upper()}: {result['other_data'][key]}\n"
        else:
            text += f"SIGNAL {result['signal']}📊\n\n"
            for key in result['other_data'].keys():
                if key not in self.unsupported_keys:
                    text += f"{key.upper()}: {result['other_data'][key]}\n"
        return text, result['signal']
    
    def get_name(self):
        return self.__class__.__name__

    def calculate_stop_loss_and_take_profit(self):
        self.df['atr'] = AverageTrueRange(
            high=self.df['high'],
            low=self.df['low'],
            close=self.df['close'],
            fillna=True
        ).average_true_range()
        
        long_idx = self.df['long_signal']
        short_idx = self.df['short_signal']

        # Long pozitsiyalar uchun
        self.df.loc[long_idx, 'stop_loss'] = self.df.loc[long_idx, 'close'] - self.stop_mul * self.df.loc[long_idx, 'atr']
        for i, mul in enumerate(self.profit_muls, start=1):
            self.df.loc[long_idx, f'take_profit_{i}'] = self.df.loc[long_idx, 'close'] + mul * self.df.loc[long_idx, 'atr']

        # Short pozitsiyalar uchun
        self.df.loc[short_idx, 'stop_loss'] = self.df.loc[short_idx, 'close'] + self.stop_mul * self.df.loc[short_idx, 'atr']
        for i, mul in enumerate(self.profit_muls, start=1):
            self.df.loc[short_idx, f'take_profit_{i}'] = self.df.loc[short_idx, 'close'] - mul * self.df.loc[short_idx, 'atr']

        self.unsupported_keys.append('atr')


class TrendFollowStrategy(BaseStrategy):
    def calculate_indicators(self):
        self.df['ema21'] = EMAIndicator(self.df['close'], window=21).ema_indicator()
        self.df['ema100'] = EMAIndicator(self.df['close'], window=100).ema_indicator()
        self.df['rsi'] = RSIIndicator(self.df['close'], window=14).rsi()
        self.df['adx'] = ADXIndicator(high=self.df['high'], low=self.df['low'], close=self.df['close'], window=14).adx()

    def generate_signals(self):
        self.df['ema21_prev'] = self.df['ema21'].shift(1)
        self.df['ema100_prev'] = self.df['ema100'].shift(1)

        self.df['bullish_crossover'] = (self.df['ema21_prev'] <= self.df['ema100_prev']) & (self.df['ema21'] > self.df['ema100'])
        self.df['bearish_crossover'] = (self.df['ema21_prev'] >= self.df['ema100_prev']) & (self.df['ema21'] < self.df['ema100'])

        self.df['below_ema21'] = self.df['close'].shift(1) < self.df['ema21'].shift(1)
        self.df['above_ema21'] = self.df['close'] > self.df['ema21']
        self.df['pullback'] = self.df['below_ema21'] & self.df['above_ema21']

        self.df['above_ema21_prev'] = self.df['close'].shift(1) > self.df['ema21'].shift(1)
        self.df['below_ema21_now'] = self.df['close'] < self.df['ema21']
        self.df['rally'] = self.df['above_ema21_prev'] & self.df['below_ema21_now']

        self.df['long_signal'] = (
            (self.df['ema21'] > self.df['ema100']) &
            (self.df['close'] > self.df['ema21']) &
            (self.df['bullish_crossover'] | self.df['pullback']) &
            (self.df['adx'] > 25) &
            (self.df['rsi'].between(50, 70))
        )

        self.df['short_signal'] = (
            (self.df['ema21'] < self.df['ema100']) &
            (self.df['close'] < self.df['ema21']) &
            (self.df['bearish_crossover'] | self.df['rally']) &
            (self.df['adx'] > 25) &
            (self.df['rsi'].between(30, 50))
        )

        self.unsupported_keys += ['bullish_crossover', 'bearish_crossover', 'ema21_prev', 'ema100_prev', 'below_ema21', 'above_ema21', 'above_ema21_prev', 'below_ema21_now', 'rally', 'pullback']

        return self.df
    

class MACDCrossoverStrategy(BaseStrategy):
    def __init__(self, data, symbol):
        super().__init__(data, symbol)
        self.stop_mul = 2
        self.profit_muls = [2, 4, 6]
    def calculate_indicators(self):
        macd = MACD(self.df['close'])
        self.df['macd'] = macd.macd()
        self.df['macd_signal'] = macd.macd_signal()
        self.df['ema20'] = EMAIndicator(self.df['close'], window=20).ema_indicator()
        self.df['ema200'] = EMAIndicator(self.df['close'], window=200).ema_indicator()
        self.df['adx'] = ADXIndicator(high=self.df['high'], low=self.df['low'], close=self.df['close'], window=14).adx()
    
    def generate_signals(self):
        short_trend = (
            (self.df['close'] < self.df['ema20']) &
            (self.df['ema20'] < self.df['ema200']) &
            (self.df['adx'] > 25)
        )
        long_trend = (
            (self.df['close'] > self.df['ema20']) &
            (self.df['ema20'] > self.df['ema200']) &
            (self.df['adx'] > 25)
        )

        long_macd_cross = (
            (self.df['macd'] > self.df['macd_signal']) &
            (self.df['macd'].shift(1) <= self.df['macd_signal'].shift(1))
        )
        short_macd_cross = (
            (self.df['macd'] < self.df['macd_signal']) &
            (self.df['macd'].shift(1) >= self.df['macd_signal'].shift(1))
        )

        self.df['long_signal'] = long_macd_cross & long_trend
        self.df['short_signal'] = short_macd_cross & short_trend

        return self.df
 

class BollingerBandSqueezeStrategy(BaseStrategy):
    def __init__(self, data, symbol):
        super().__init__(data, symbol)
        self.stop_mul = 2
        self.profit_muls = [2, 3, 4.5]
    def calculate_indicators(self):
        bollinger_band = BollingerBands(close=self.df['close'])
        self.df['bollinger_upper'] = bollinger_band.bollinger_hband()
        self.df['bollinger_lower'] = bollinger_band.bollinger_lband()

    def generate_signals(self):
        self.df['long_signal'] = (self.df['bollinger_upper'] < self.df['close']) & (self.df['bollinger_upper'].shift() >= self.df['close'])
        self.df['short_signal'] = (self.df['bollinger_upper'] > self.df['close']) & (self.df['bollinger_upper'].shift() <= self.df['close'])
        
        return self.df


class StochasticOscillatorStrategy(BaseStrategy):
    def __init__(self, data, symbol):
        super().__init__(data, symbol)
        self.stop_mul = 1
        self.profit_muls = [1, 2, 4]
    def calculate_indicators(self):
        stoch = StochasticOscillator(high=self.df['high'], low=self.df['low'], close=self.df['close'])
        self.df['stoch_k'] = stoch.stoch()
        self.df['stoch_d'] = stoch.stoch_signal()

    def generate_signals(self):
        self.df['long_signal'] = (self.df['stoch_k'] < 20) & (self.df['stoch_k'] > self.df['stoch_d']) & (self.df['stoch_k'].shift(1) <= self.df['stoch_d'].shift(1))
        self.df['short_signal'] = (self.df['stoch_k'] > 80) & (self.df['stoch_k'] < self.df['stoch_d']) & (self.df['stoch_k'].shift(1) >= self.df['stoch_d'].shift(1))

        return self.df
    

class SMACrossoverStrategy(BaseStrategy):
    def calculate_indicators(self):
        self.df['sma50'] = SMAIndicator(close=self.df['close'], window=50).sma_indicator()
        self.df['sma200'] = SMAIndicator(close=self.df['close'], window=200).sma_indicator()

    def generate_signals(self):
        self.df['long_signal'] = (self.df['sma50'] > self.df['sma200']) & (self.df['sma50'].shift(1) <= self.df['sma200'].shift(1))
        self.df['short_signal'] = (self.df['sma50'] < self.df['sma200']) & (self.df['sma50'].shift(1) >= self.df['sma200'].shift(1))

        return self.df
    

class WilliamsFractalsStrategy(BaseStrategy):
    def calculate_indicators(self):
        wf = WilliamsFractals(high=self.df['high'], low=self.df['low'], window=2)
        self.df['fractal_down'] = wf.bearish_williams_fractals()
        self.df['fractal_up'] = wf.bullish_williams_fractals()
        self.df['ema20'] = EMAIndicator(self.df['close'], window=20).ema_indicator()
        self.df['ema50'] = EMAIndicator(self.df['close'], window=50).ema_indicator()
        self.df['ema100'] = EMAIndicator(self.df['close'], window=100).ema_indicator()

        self.unsupported_keys.append('fractal_down')
        self.unsupported_keys.append('fractal_up')

    def generate_signals(self):
        
        self.df['long_signal'] = (
            (self.df["low"] > self.df["ema100"]) &
            (self.df["ema20"] > self.df["ema50"]) &
            (self.df["ema50"] > self.df["ema100"]) &
            (self.df["fractal_up"].shift(2))  # 2 ta oldingi shamda fractal up  
        )

        self.df['short_signal'] = (
            (self.df["high"] < self.df["ema100"]) &
            (self.df["ema20"] < self.df["ema50"]) &
            (self.df["ema50"] < self.df["ema100"]) &
            (self.df["fractal_down"].shift(2))  # 2 ta oldingi shamda fractal down
        )

        return self.df
    
    def calculate_stop_loss_and_take_profit(self):
        long_idx = self.df['long_signal']
        short_idx = self.df['short_signal']

        # Long uchun
        con_1 = long_idx & (self.df['low'] < self.df['ema20']) & (self.df['low'] > self.df['ema50'])
        self.df.loc[con_1, 'stop_loss'] = self.df.loc[con_1, 'ema50'] * 0.98
        risk = self.df.loc[con_1, 'close'] - self.df.loc[con_1, 'stop_loss']
        self.df.loc[con_1, 'take_profit_1'] = self.df.loc[con_1, 'close'] + 1.5 * risk
        self.df.loc[con_1, 'take_profit_2'] = self.df.loc[con_1, 'close'] + 2 * risk
        self.df.loc[con_1, 'take_profit_3'] = self.df.loc[con_1, 'close'] + 3 * risk

        con_2 = long_idx & (self.df['low'] < self.df['ema50']) & (self.df['low'] > self.df['ema100'])
        self.df.loc[con_2, 'stop_loss'] = self.df.loc[con_2, 'ema100'] * 0.98
        risk = self.df.loc[con_2, 'close'] - self.df.loc[con_2, 'stop_loss']
        self.df.loc[con_2, 'take_profit_1'] = self.df.loc[con_2, 'close'] + 1.5 * risk
        self.df.loc[con_2, 'take_profit_2'] = self.df.loc[con_2, 'close'] + 2 * risk
        self.df.loc[con_2, 'take_profit_3'] = self.df.loc[con_2, 'close'] + 3 * risk

        # Short  uchun
        con_3 = short_idx & (self.df['high'] > self.df['ema20']) & (self.df['high'] < self.df['ema50'])
        self.df.loc[con_3, 'stop_loss'] = self.df.loc[con_3, 'ema50'] * 1.02
        risk = self.df.loc[con_3, 'stop_loss'] - self.df.loc[con_3, 'close']
        self.df.loc[con_3, 'take_profit_1'] = self.df.loc[con_3, 'close'] - 1.5 * risk
        self.df.loc[con_3, 'take_profit_2'] = self.df.loc[con_3, 'close'] - 2 * risk
        self.df.loc[con_3, 'take_profit_3'] = self.df.loc[con_3, 'close'] - 3 * risk

        con_4 = short_idx & (self.df['high'] > self.df['ema50']) & (self.df['high'] < self.df['ema100'])
        self.df.loc[con_4, 'stop_loss'] = self.df.loc[con_4, 'ema100'] * 1.02
        risk = self.df.loc[con_4, 'stop_loss'] - self.df.loc[con_4, 'close']
        self.df.loc[con_4, 'take_profit_1'] = self.df.loc[con_4, 'close'] - 1.5 * risk
        self.df.loc[con_4, 'take_profit_2'] = self.df.loc[con_4, 'close'] - 2 * risk
        self.df.loc[con_4, 'take_profit_3'] = self.df.loc[con_4, 'close'] - 3 * risk
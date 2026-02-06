from typing import Any, Literal
from dataclasses import dataclass, field
from ta.trend import EMAIndicator, ADXIndicator, MACD, SMAIndicator
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange
import pandas as pd
import numpy as np

from .utils import WilliamsFractals


@dataclass
class StrategyResult:
    """Har bir strategiya natijasi"""
    direction: Literal["LONG", "SHORT", "NEUTRAL"]
    confidence: float  # 0-100 oralig'ida
    weight: float = 1.0  # strategiya og'irligi
    name: str = ""
    indicators: dict = field(default_factory=dict)


class BaseStrategy:
    """Yangilangan BaseStrategy - confidence asosida ishlaydi"""
    
    weight: float = 1.0  # Har bir strategiya uchun og'irlik
    
    def __init__(self, data: list, symbol: str):
        self.df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "trades", "taker_base_vol",
            "taker_quote_vol", "ignore"
        ])
        self.df[['open', 'high', 'low', 'close', 'volume']] = self.df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        self.symbol = symbol
        self.unsupported_keys = [
            "timestamp", "open", "high", "low", "volume", 'close_time', 
            'quote_asset_volume', 'trades', 'taker_base_vol', 'taker_quote_vol', 
            'ignore', 'long_signal', 'short_signal'
        ]

    def calculate_indicators(self) -> None:
        """Child klasslar override qiladi"""
        raise NotImplementedError
    
    def get_confidence(self) -> StrategyResult:
        """
        Strategiyaning ishonch darajasini qaytaradi.
        Child klasslar override qiladi.
        
        Returns:
            StrategyResult: direction, confidence (0-100), weight
        """
        raise NotImplementedError
    
    def run(self) -> StrategyResult:
        """Strategiyani ishga tushiradi va natijani qaytaradi"""
        self.calculate_indicators()
        result = self.get_confidence()
        result.name = self.get_name()
        result.indicators = self._get_indicators()
        # Confidence ni 5-95% oralig'ida cheklash
        result.confidence = max(5.0, min(95.0, result.confidence))
        return result
    
    def _get_indicators(self) -> dict[str, Any]:
        """Oxirgi qator indikatorlarini qaytaradi"""
        last_row = self.df.iloc[-1].to_dict()
        return {k: v for k, v in last_row.items() if k not in self.unsupported_keys}
    
    def get_name(self) -> str:
        return self.__class__.__name__
    
    def _normalize_confidence(self, value: float, min_val: float, max_val: float) -> float:
        """Qiymatni 0-100 oralig'iga normalizatsiya qiladi"""
        if max_val == min_val:
            return 50.0
        normalized = ((value - min_val) / (max_val - min_val)) * 100
        return max(0.0, min(100.0, normalized))


class TrendFollowStrategy(BaseStrategy):
    """EMA + RSI + ADX asosida trend following"""
    
    weight = 1.2  # Trend strategiyasi uchun yuqoriroq og'irlik
    
    def calculate_indicators(self) -> None:
        self.df['ema21'] = EMAIndicator(self.df['close'], window=21).ema_indicator()
        self.df['ema100'] = EMAIndicator(self.df['close'], window=100).ema_indicator()
        self.df['rsi'] = RSIIndicator(self.df['close'], window=14).rsi()
        self.df['adx'] = ADXIndicator(
            high=self.df['high'], 
            low=self.df['low'], 
            close=self.df['close'], 
            window=14
        ).adx()

    def get_confidence(self) -> StrategyResult:
        last = self.df.iloc[-1]
        
        ema21 = last['ema21']
        ema100 = last['ema100']
        rsi = last['rsi']
        adx = last['adx']
        close = last['close']
        
        # Trend yo'nalishi va kuchi
        ema_diff_pct = ((ema21 - ema100) / ema100) * 100
        
        # ADX kuchi (25+ kuchli trend)
        adx_score = min(100, (adx / 50) * 100) if adx > 20 else 0
        
        # RSI score
        if rsi > 50:
            rsi_score = min(100, ((rsi - 50) / 30) * 100)  # 50-80 oralig'i long uchun
            if rsi > 70:
                rsi_score *= 0.7  # Overbought
        else:
            rsi_score = min(100, ((50 - rsi) / 30) * 100)  # 20-50 oralig'i short uchun
            if rsi < 30:
                rsi_score *= 0.7  # Oversold
        
        # Price position relative to EMAs
        above_ema21 = close > ema21
        above_ema100 = close > ema100
        
        # Trend score
        trend_score = min(100, abs(ema_diff_pct) * 20)
        
        if ema21 > ema100 and above_ema21 and above_ema100 and adx > 25:
            # Kuchli LONG signal - kuchli trend
            confidence = (trend_score * 0.4 + adx_score * 0.3 + rsi_score * 0.3)
            direction = "LONG"
        elif ema21 < ema100 and not above_ema21 and not above_ema100 and adx > 25:
            # Kuchli SHORT signal - kuchli trend
            confidence = (trend_score * 0.4 + adx_score * 0.3 + rsi_score * 0.3)
            direction = "SHORT"
        elif ema21 > ema100 and above_ema21 and above_ema100:
            # O'rta LONG (trend bor, ADX past)
            confidence = (trend_score * 0.3 + adx_score * 0.2 + rsi_score * 0.2)
            direction = "LONG"
        elif ema21 < ema100 and not above_ema21 and not above_ema100:
            # O'rta SHORT
            confidence = (trend_score * 0.3 + adx_score * 0.2 + rsi_score * 0.2)
            direction = "SHORT"
        elif adx < 20:
            # Trend yo'q - NEUTRAL
            direction = "NEUTRAL"
            confidence = 0.0
        elif ema21 > ema100:
            # Zaif LONG (EMA uptrend, lekin price alignment yo'q)
            confidence = (trend_score * 0.15 + adx_score * 0.1)
            direction = "LONG"
        elif ema21 < ema100:
            # Zaif SHORT
            confidence = (trend_score * 0.15 + adx_score * 0.1)
            direction = "SHORT"
        else:
            # Flat market - NEUTRAL
            direction = "NEUTRAL"
            confidence = 0.0
        
        return StrategyResult(
            direction=direction,
            confidence=confidence,
            weight=self.weight
        )


class MACDCrossoverStrategy(BaseStrategy):
    """MACD crossover + trend filter"""
    
    weight = 1.0
    
    def calculate_indicators(self) -> None:
        macd = MACD(self.df['close'])
        self.df['macd'] = macd.macd()
        self.df['macd_signal'] = macd.macd_signal()
        self.df['macd_hist'] = macd.macd_diff()
        self.df['ema20'] = EMAIndicator(self.df['close'], window=20).ema_indicator()
        self.df['ema200'] = EMAIndicator(self.df['close'], window=200).ema_indicator()
        self.df['adx'] = ADXIndicator(
            high=self.df['high'], 
            low=self.df['low'], 
            close=self.df['close'], 
            window=14
        ).adx()
    
    def get_confidence(self) -> StrategyResult:
        last = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        
        macd = last['macd']
        macd_signal = last['macd_signal']
        macd_hist = last['macd_hist']
        prev_macd = prev['macd']
        prev_macd_signal = prev['macd_signal']
        
        ema20 = last['ema20']
        ema200 = last['ema200']
        close = last['close']
        adx = last['adx']
        
        # MACD histogram kuchi
        hist_std = self.df['macd_hist'].rolling(50).std().iloc[-1]
        if hist_std > 0:
            hist_strength = min(100, (abs(macd_hist) / (hist_std * 2)) * 100)
        else:
            hist_strength = 50
        
        # Crossover tekshirish
        bullish_cross = prev_macd <= prev_macd_signal and macd > macd_signal
        bearish_cross = prev_macd >= prev_macd_signal and macd < macd_signal
        
        # Trend alignment
        long_trend = close > ema20 > ema200
        short_trend = close < ema20 < ema200
        
        # ADX filter
        adx_multiplier = min(1.0, adx / 25) if adx > 20 else 0.5
        
        # MACD histogram kuchsiz bo'lsa - NEUTRAL
        if hist_strength < 20 and not bullish_cross and not bearish_cross:
            return StrategyResult(
                direction="NEUTRAL",
                confidence=0.0,
                weight=self.weight
            )
        
        if bullish_cross and long_trend:
            confidence = hist_strength * adx_multiplier
            direction = "LONG"
        elif bearish_cross and short_trend:
            confidence = hist_strength * adx_multiplier
            direction = "SHORT"
        elif macd > macd_signal and long_trend:
            # Mavjud LONG momentum
            confidence = hist_strength * 0.6 * adx_multiplier
            direction = "LONG"
        elif macd < macd_signal and short_trend:
            # Mavjud SHORT momentum
            confidence = hist_strength * 0.6 * adx_multiplier
            direction = "SHORT"
        elif adx < 20:
            # Trend yo'q - NEUTRAL
            direction = "NEUTRAL"
            confidence = 0.0
        elif macd > macd_signal:
            # MACD bullish, lekin trend alignment yo'q
            confidence = hist_strength * 0.25 * adx_multiplier
            direction = "LONG"
        elif macd < macd_signal:
            # MACD bearish, lekin trend alignment yo'q
            confidence = hist_strength * 0.25 * adx_multiplier
            direction = "SHORT"
        else:
            # MACD = signal - NEUTRAL
            direction = "NEUTRAL"
            confidence = 0.0
        
        return StrategyResult(
            direction=direction,
            confidence=confidence,
            weight=self.weight
        )


class BollingerBandSqueezeStrategy(BaseStrategy):
    """Bollinger Bands breakout"""
    
    weight = 0.8
    
    def calculate_indicators(self) -> None:
        bb = BollingerBands(close=self.df['close'])
        self.df['bb_upper'] = bb.bollinger_hband()
        self.df['bb_lower'] = bb.bollinger_lband()
        self.df['bb_mid'] = bb.bollinger_mavg()
        self.df['bb_width'] = bb.bollinger_wband()
        self.df['bb_pband'] = bb.bollinger_pband()  # 0-1 oralig'ida pozitsiya

    def get_confidence(self) -> StrategyResult:
        last = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        
        close = last['close']
        bb_upper = last['bb_upper']
        bb_lower = last['bb_lower']
        bb_pband = last['bb_pband']
        bb_width = last['bb_width']
        
        prev_close = prev['close']
        prev_bb_upper = prev['bb_upper']
        prev_bb_lower = prev['bb_lower']
        
        # Squeeze detection (rolling percentile)
        width_series = self.df['bb_width']
        squeeze_window = 100
        squeeze_quantile = 0.20
        squeeze_threshold = width_series.rolling(squeeze_window).quantile(squeeze_quantile).iloc[-1]
        has_squeeze_info = not np.isnan(squeeze_threshold)
        
        if has_squeeze_info:
            lookback = min(5, len(width_series) - 1)
            recent_window = width_series.iloc[-(lookback + 1):-1] if lookback > 0 else width_series.iloc[0:0]
            recent_squeeze = (recent_window <= squeeze_threshold).any() if len(recent_window) else False
        else:
            # Agar tarix yetarli bo'lmasa, squeeze filtrini qo'llamaymiz
            recent_squeeze = True
        
        # Breakout kuchini hisoblash (inverse width ratio)
        avg_width = width_series.rolling(20).mean().iloc[-1]
        width_ratio = (avg_width / bb_width) if bb_width > 0 and avg_width > 0 else 1.0
        
        # Yuqoriga breakout
        if close > bb_upper and prev_close <= prev_bb_upper:
            if recent_squeeze:
                # Breakout kuchi (faqat squeeze'dan keyin)
                breakout_strength = ((close - bb_upper) / bb_upper) * 1000
                confidence = min(100, breakout_strength * 50) * min(1.5, width_ratio)
                direction = "LONG"
            else:
                direction = "NEUTRAL"
                confidence = 0.0
        # Pastga breakout
        elif close < bb_lower and prev_close >= prev_bb_lower:
            if recent_squeeze:
                breakout_strength = ((bb_lower - close) / bb_lower) * 1000
                confidence = min(100, breakout_strength * 50) * min(1.5, width_ratio)
                direction = "SHORT"
            else:
                direction = "NEUTRAL"
                confidence = 0.0
        # Aniq zonalarda - past confidence bilan
        elif bb_pband > 0.85:
            confidence = (bb_pband - 0.85) * 150  # 0-22 oralig'ida
            direction = "LONG"
        elif bb_pband < 0.15:
            confidence = (0.15 - bb_pband) * 150
            direction = "SHORT"
        # O'rta zonada - NEUTRAL
        else:
            # Band ichida, aniq pozitsiya yo'q
            direction = "NEUTRAL"
            confidence = 0.0
        
        return StrategyResult(
            direction=direction,
            confidence=confidence,
            weight=self.weight
        )


class StochasticOscillatorStrategy(BaseStrategy):
    """Stochastic oversold/overbought + crossover"""
    
    weight = 0.9
    
    def calculate_indicators(self) -> None:
        stoch = StochasticOscillator(
            high=self.df['high'], 
            low=self.df['low'], 
            close=self.df['close']
        )
        self.df['stoch_k'] = stoch.stoch()
        self.df['stoch_d'] = stoch.stoch_signal()

    def get_confidence(self) -> StrategyResult:
        last = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        
        k = last['stoch_k']
        d = last['stoch_d']
        prev_k = prev['stoch_k']
        prev_d = prev['stoch_d']
        
        # Crossover tekshirish
        bullish_cross = prev_k <= prev_d and k > d
        bearish_cross = prev_k >= prev_d and k < d
        
        # Oversold zone (k < 20) + bullish crossover
        if k < 20 and bullish_cross:
            # Kuchli long signal
            confidence = 75 + (20 - k)  # 75-95 oralig'ida
            direction = "LONG"
        # Overbought zone (k > 80) + bearish crossover
        elif k > 80 and bearish_cross:
            confidence = 75 + (k - 80)  # 75-95 oralig'ida
            direction = "SHORT"
        # Oversold zone bilan momentum
        elif k < 25 and k > d:
            confidence = 45 + (25 - k) * 2  # 45-95 oralig'ida
            direction = "LONG"
        # Overbought zone bilan momentum
        elif k > 75 and k < d:
            confidence = 45 + (k - 75) * 2  # 45-95 oralig'ida
            direction = "SHORT"
        # O'rta zona (25-75) - NEUTRAL
        else:
            # Na overbought, na oversold - signal yo'q
            direction = "NEUTRAL"
            confidence = 0.0
        
        return StrategyResult(
            direction=direction,
            confidence=min(100, confidence),
            weight=self.weight
        )


class SMACrossoverStrategy(BaseStrategy):
    """Golden/Death cross - SMA50 vs SMA200"""
    
    weight = 1.1
    
    def calculate_indicators(self) -> None:
        self.df['sma50'] = SMAIndicator(close=self.df['close'], window=50).sma_indicator()
        self.df['sma200'] = SMAIndicator(close=self.df['close'], window=200).sma_indicator()

    def get_confidence(self) -> StrategyResult:
        last = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        
        sma50 = last['sma50']
        sma200 = last['sma200']
        prev_sma50 = prev['sma50']
        prev_sma200 = prev['sma200']
        close = last['close']
        
        # SMA farqi foizda
        sma_diff_pct = ((sma50 - sma200) / sma200) * 100
        
        # Golden cross (SMA50 SMA200 ni yuqoriga kesib o'tdi)
        golden_cross = prev_sma50 <= prev_sma200 and sma50 > sma200
        # Death cross (SMA50 SMA200 ni pastga kesib o'tdi)
        death_cross = prev_sma50 >= prev_sma200 and sma50 < sma200
        
        if golden_cross:
            confidence = 80  # Cross bo'lganda yuqori ishonch
            direction = "LONG"
        elif death_cross:
            confidence = 80
            direction = "SHORT"
        elif sma50 > sma200 and close > sma50 and abs(sma_diff_pct) > 1:
            # Aniq uptrend davom etmoqda (kamida 1% spread)
            confidence = min(65, 35 + abs(sma_diff_pct) * 8)
            direction = "LONG"
        elif sma50 < sma200 and close < sma50 and abs(sma_diff_pct) > 1:
            # Aniq downtrend davom etmoqda
            confidence = min(65, 35 + abs(sma_diff_pct) * 8)
            direction = "SHORT"
        elif abs(sma_diff_pct) < 0.5:
            # SMAlar juda yaqin - trend yo'q, NEUTRAL
            direction = "NEUTRAL"
            confidence = 0.0
        elif sma50 > sma200:
            # Uptrend, lekin kuchsiz yoki price alignment yo'q
            confidence = min(30, 10 + abs(sma_diff_pct) * 4)
            direction = "LONG"
        elif sma50 < sma200:
            # Downtrend, lekin kuchsiz
            confidence = min(30, 10 + abs(sma_diff_pct) * 4)
            direction = "SHORT"
        else:
            # SMA50 = SMA200 - NEUTRAL
            direction = "NEUTRAL"
            confidence = 0.0
        
        return StrategyResult(
            direction=direction,
            confidence=confidence,
            weight=self.weight
        )


class WilliamsFractalsStrategy(BaseStrategy):
    """Williams Fractals + EMA trend filter"""
    
    weight = 0.9
    
    def calculate_indicators(self) -> None:
        wf = WilliamsFractals(high=self.df['high'], low=self.df['low'], window=2)
        self.df['fractal_up'] = wf.bullish_williams_fractals()
        self.df['fractal_down'] = wf.bearish_williams_fractals()
        self.df['ema20'] = EMAIndicator(self.df['close'], window=20).ema_indicator()
        self.df['ema50'] = EMAIndicator(self.df['close'], window=50).ema_indicator()
        self.df['ema100'] = EMAIndicator(self.df['close'], window=100).ema_indicator()

    def get_confidence(self) -> StrategyResult:
        last = self.df.iloc[-1]
        # Fractal 2 ta oldingi shamda ko'rinadi
        fractal_row = self.df.iloc[-3] if len(self.df) > 3 else last
        
        close = last['close']
        low = last['low']
        high = last['high']
        ema20 = last['ema20']
        ema50 = last['ema50']
        ema100 = last['ema100']
        
        fractal_up = fractal_row['fractal_up']
        fractal_down = fractal_row['fractal_down']
        
        # EMA alignment
        bullish_ema = ema20 > ema50 > ema100
        bearish_ema = ema20 < ema50 < ema100
        
        # EMA alignment kuchi
        ema_spread = abs((ema20 - ema100) / ema100) * 100
        ema_strength = min(100, ema_spread * 20)
        
        if fractal_up and bullish_ema and low > ema100:
            confidence = 60 + ema_strength * 0.35
            direction = "LONG"
        elif fractal_down and bearish_ema and high < ema100:
            confidence = 60 + ema_strength * 0.35
            direction = "SHORT"
        elif bullish_ema and close > ema20 and ema_spread > 0.5:
            # Kuchli bullish alignment
            confidence = 35 + ema_strength * 0.25
            direction = "LONG"
        elif bearish_ema and close < ema20 and ema_spread > 0.5:
            # Kuchli bearish alignment
            confidence = 35 + ema_strength * 0.25
            direction = "SHORT"
        elif ema_spread < 0.3:
            # EMAlar juda yaqin - trend yo'q, NEUTRAL
            direction = "NEUTRAL"
            confidence = 0.0
        elif bullish_ema:
            # Bullish EMA, lekin zaif signal
            confidence = 15 + ema_strength * 0.1
            direction = "LONG"
        elif bearish_ema:
            # Bearish EMA, lekin zaif signal
            confidence = 15 + ema_strength * 0.1
            direction = "SHORT"
        else:
            # EMA alignment yo'q - NEUTRAL
            direction = "NEUTRAL"
            confidence = 0.0
        
        return StrategyResult(
            direction=direction,
            confidence=min(100, confidence),
            weight=self.weight
        )

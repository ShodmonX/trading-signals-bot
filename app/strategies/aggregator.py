"""Signal Aggregator - Ensemble/Consensus Strategy System

Bu modul barcha strategiyalardan kelgan signallarni birlashtiradi
va yakuniy signal hamda SL/TP ni hisoblaydi.
"""

from typing import Literal
from dataclasses import dataclass, field
from math import ceil
import pandas as pd
from ta.volatility import AverageTrueRange
from ta.trend import ADXIndicator

from .strategies import StrategyResult, BaseStrategy


# Aggregator defaults (false signalni kamaytirish uchun)
MIN_VOTE_CONFIDENCE_DEFAULT = 30.0  # Vote hisoblanishi uchun minimal confidence
MIN_VOTE_RATIO_DEFAULT = 0.66  # Total strategiyalardan talab qilinadigan ulush

# Regime filter sozlamalari (ADX asosida)
ADX_TREND_THRESHOLD = 25.0
ADX_RANGE_THRESHOLD = 20.0
TREND_STRATEGY_NAMES = {
    "TrendFollowStrategy",
    "MACDCrossoverStrategy",
    "SMACrossoverStrategy",
    "WilliamsFractalsStrategy",
}
RANGE_STRATEGY_NAMES = {
    "BollingerBandSqueezeStrategy",
    "StochasticOscillatorStrategy",
}
TREND_BOOST = 1.15
TREND_DAMPEN = 0.6
RANGE_BOOST = 1.1
RANGE_DAMPEN = 0.5

# Actual weight clamp
MIN_ACTUAL_WEIGHT = 0.1
MAX_ACTUAL_WEIGHT = 3.0


@dataclass
class AggregatedSignal:
    """Yakuniy birlashtrilgan signal"""
    direction: Literal["LONG", "SHORT", "NEUTRAL"]
    confidence: float  # Umumiy ishonch darajasi (0-100)
    entry_price: float
    stop_loss: float | None = None
    take_profit_1: float | None = None
    take_profit_2: float | None = None
    take_profit_3: float | None = None
    
    # Qo'shimcha ma'lumotlar
    strategy_results: list[StrategyResult] = field(default_factory=list)
    long_votes: int = 0
    short_votes: int = 0
    neutral_votes: int = 0
    filtered_votes: int = 0
    long_weight_sum: float = 0.0
    short_weight_sum: float = 0.0
    weighted_long_confidence: float = 0.0
    weighted_short_confidence: float = 0.0
    
    def to_dict(self) -> dict:
        """Signal ma'lumotlarini dict formatida qaytaradi"""
        return {
            "signal": self.direction,
            "confidence": round(self.confidence, 2),
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            "take_profit_3": self.take_profit_3,
            "long_votes": self.long_votes,
            "short_votes": self.short_votes,
            "neutral_votes": self.neutral_votes,
            "filtered_votes": self.filtered_votes,
            "long_weight_sum": round(self.long_weight_sum, 4),
            "short_weight_sum": round(self.short_weight_sum, 4),
            "weighted_long_confidence": round(self.weighted_long_confidence, 2),
            "weighted_short_confidence": round(self.weighted_short_confidence, 2),
        }


class SignalAggregator:
    """
    Ensemble strategiya tizimi - barcha strategiyalarni birlashtiradi
    
    Parameters:
        data: Binance API dan kelgan kline data
        symbol: Trading juftligi (masalan BTCUSDT)
        strategies: Strategiya klasslari ro'yxati
        threshold: Minimal ishonch darajasi (default: 60)
        stop_multiplier: ATR asosida SL multiplier (default: 1.5)
        tp_multipliers: ATR asosida TP multiplierlar (default: [1.5, 3, 4.5])
        min_vote_confidence: Vote hisoblanishi uchun minimal confidence (default: 30)
        min_vote_ratio: Total strategiyalardan min vote ulushi (default: 0.66)
    """
    
    def __init__(
        self,
        data: list,
        symbol: str,
        strategies: list[type[BaseStrategy]],
        threshold: float = 60.0,
        stop_multiplier: float = 1.5,
        tp_multipliers: list[float] | None = None,
        min_vote_confidence: float = MIN_VOTE_CONFIDENCE_DEFAULT,
        min_vote_ratio: float = MIN_VOTE_RATIO_DEFAULT,
        strategy_weights: dict[str, float] | None = None,
        stability_weights: dict[str, float] | None = None,
        correlation_penalties: dict[str, float] | None = None,
    ):
        self.data = data
        self.symbol = symbol
        self.strategies = strategies
        self.threshold = threshold
        self.stop_multiplier = stop_multiplier
        self.tp_multipliers = tp_multipliers or [1.5, 3.0, 4.5]
        self.min_vote_confidence = max(0.0, min(100.0, min_vote_confidence))
        self.min_vote_ratio = max(0.0, min(1.0, min_vote_ratio))
        self.strategy_weights = strategy_weights or {}
        self.stability_weights = stability_weights or {}
        self.correlation_penalties = correlation_penalties or {}
        
        # DataFrame yaratish (ATR uchun)
        self.df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            'close_time', 'quote_asset_volume', 'trades', 'taker_base_vol',
            'taker_quote_vol', 'ignore'
        ])
        self.df[['open', 'high', 'low', 'close', 'volume']] = \
            self.df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        self._adx: float | None = None

    def _get_adx(self) -> float:
        """Regime filter uchun ADX ni hisoblab cache qiladi"""
        if self._adx is None:
            if len(self.df) < 14:
                self._adx = 0.0
            else:
                adx_indicator = ADXIndicator(
                    high=self.df['high'],
                    low=self.df['low'],
                    close=self.df['close'],
                    window=14
                )
                adx_value = float(adx_indicator.adx().iloc[-1])
                self._adx = 0.0 if pd.isna(adx_value) else adx_value
        return self._adx

    def _get_regime_multiplier(self, strategy_name: str) -> float:
        """ADX asosida trend/range strategiyalariga multiplier qaytaradi"""
        adx = self._get_adx()
        multiplier = 1.0

        if adx >= ADX_TREND_THRESHOLD:
            if strategy_name in TREND_STRATEGY_NAMES:
                multiplier = TREND_BOOST
            elif strategy_name in RANGE_STRATEGY_NAMES:
                multiplier = TREND_DAMPEN
        elif adx <= ADX_RANGE_THRESHOLD:
            if strategy_name in RANGE_STRATEGY_NAMES:
                multiplier = RANGE_BOOST
            elif strategy_name in TREND_STRATEGY_NAMES:
                multiplier = RANGE_DAMPEN

        return multiplier

    def _get_stability_multiplier(self, strategy_name: str) -> float:
        """Stability weight (default 1.0)"""
        return self.stability_weights.get(strategy_name, 1.0)

    def _get_correlation_penalty(self, strategy_name: str) -> float:
        """Correlation penalty (default 1.0)"""
        return self.correlation_penalties.get(strategy_name, 1.0)
    
    def run_all_strategies(self) -> list[StrategyResult]:
        """Barcha strategiyalarni ishga tushiradi"""
        results = []
        for strategy_cls in self.strategies:
            try:
                strategy = strategy_cls(self.data, self.symbol)
                result = strategy.run()
                results.append(result)
            except Exception as e:
                # Xatolik bo'lsa neutral natija
                results.append(StrategyResult(
                    direction="NEUTRAL",
                    confidence=0.0,
                    weight=0.0,
                    name=strategy_cls.__name__,
                    indicators={"error": str(e)}
                ))
        return results
    
    def aggregate(self, results: list[StrategyResult]) -> AggregatedSignal:
        """
        Strategiya natijalarini birlashtiradi.
        
        Consensus logic:
        1. Minimum 3 ta strategiya (50%+1) bir xil yo'nalishda bo'lishi kerak
        2. Consensus confidence = avg_confidence + votes_bonus
        3. Ko'pchilik ovoz ustunlik qiladi
        
        Votes bonus formula:
        - Har bir qo'shimcha vote (min_votes dan ortiq) uchun +10%
        - Masalan: 4/6 LONG, avg 40% -> bonus = (4-3)*10 = 10% -> final = 50%
        - 5/6 LONG, avg 40% -> bonus = (5-3)*10 = 20% -> final = 60%
        """
        
        long_votes = 0
        short_votes = 0
        neutral_votes = 0
        filtered_votes = 0
        
        long_confidence_sum = 0.0
        short_confidence_sum = 0.0
        long_weight_sum = 0.0
        short_weight_sum = 0.0
        
        for result in results:
            name = result.name or ""
            perf_weight = self.strategy_weights.get(name, 1.0)
            regime_mult = self._get_regime_multiplier(name)
            stability_mult = self._get_stability_multiplier(name)
            corr_penalty = self._get_correlation_penalty(name)
            actual_weight = (
                result.weight
                * perf_weight
                * regime_mult
                * stability_mult
                * corr_penalty
            )
            actual_weight = max(MIN_ACTUAL_WEIGHT, min(MAX_ACTUAL_WEIGHT, actual_weight))
            if result.direction == "LONG":
                if result.confidence >= self.min_vote_confidence:
                    long_votes += 1
                    long_confidence_sum += result.confidence * actual_weight
                    long_weight_sum += actual_weight
                else:
                    filtered_votes += 1
            elif result.direction == "SHORT":
                if result.confidence >= self.min_vote_confidence:
                    short_votes += 1
                    short_confidence_sum += result.confidence * actual_weight
                    short_weight_sum += actual_weight
                else:
                    filtered_votes += 1
            else:
                neutral_votes += 1
        
        # O'rtacha confidence hisoblash
        avg_long_confidence = (long_confidence_sum / long_weight_sum) if long_weight_sum > 0 else 0.0
        avg_short_confidence = (short_confidence_sum / short_weight_sum) if short_weight_sum > 0 else 0.0
        
        # Total votes
        total_strategies = len(results)
        
        # Yakuniy yo'nalishni aniqlash
        entry_price = float(self.df['close'].iloc[-1])
        
        # Minimum ovoz soni - total strategiyalardan kelib chiqadi
        # 6 strategiya uchun min 4 ta (66%)
        min_votes = max(1, ceil(total_strategies * self.min_vote_ratio))
        
        # MINIMUM AVG CONFIDENCE - bu qiymatdan past bo'lsa signal chiqmaydi
        MIN_AVG_CONFIDENCE = 35.0
        
        # Votes bonus - har bir qo'shimcha vote uchun +5%
        # Weight bilan yaqinlashtirilgan bonus
        VOTE_BONUS = 5.0  # Har bir qo'shimcha vote uchun

        long_bonus = max(0, (long_votes - min_votes)) * VOTE_BONUS
        short_bonus = max(0, (short_votes - min_votes)) * VOTE_BONUS
        
        # Final consensus confidence = avg + bonus (max 95%)
        # Avg confidence MIN_AVG_CONFIDENCE dan yuqori bo'lishi kerak
        if long_votes >= min_votes and avg_long_confidence >= MIN_AVG_CONFIDENCE:
            consensus_long = min(95.0, avg_long_confidence + long_bonus)
        else:
            consensus_long = avg_long_confidence
            
        if short_votes >= min_votes and avg_short_confidence >= MIN_AVG_CONFIDENCE:
            consensus_short = min(95.0, avg_short_confidence + short_bonus)
        else:
            consensus_short = avg_short_confidence
        
        # Signal shartlari:
        # 1. Kamida min_votes ta strategiya bir xil yo'nalishda
        # 2. Consensus confidence >= threshold
        # 3. Bu yo'nalish boshqasidan ko'p
        
        direction = "NEUTRAL"
        confidence = 0.0
        
        if long_votes >= min_votes and consensus_long >= self.threshold and long_votes > short_votes:
            direction = "LONG"
            confidence = consensus_long
        elif short_votes >= min_votes and consensus_short >= self.threshold and short_votes > long_votes:
            direction = "SHORT"
            confidence = consensus_short
        else:
            # NEUTRAL - eng yuqori consensus confidence ni ko'rsatamiz
            confidence = max(consensus_long, consensus_short)
        
        # Signal obyektini yaratish
        signal = AggregatedSignal(
            direction=direction,
            confidence=confidence,
            entry_price=entry_price,
            strategy_results=results,
            long_votes=long_votes,
            short_votes=short_votes,
            neutral_votes=neutral_votes,
            filtered_votes=filtered_votes,
            long_weight_sum=long_weight_sum,
            short_weight_sum=short_weight_sum,
            weighted_long_confidence=avg_long_confidence,
            weighted_short_confidence=avg_short_confidence
        )
        
        # SL/TP hisoblash (faqat signal bo'lganda)
        if direction != "NEUTRAL":
            self._calculate_sl_tp(signal)
        
        return signal
    
    def _calculate_sl_tp(self, signal: AggregatedSignal) -> None:
        """ATR asosida Stop Loss va Take Profit hisoblash"""
        
        # ATR hisoblash
        atr_indicator = AverageTrueRange(
            high=self.df['high'],
            low=self.df['low'],
            close=self.df['close'],
            window=14,
            fillna=True
        )
        atr = float(atr_indicator.average_true_range().iloc[-1])
        
        if signal.direction == "LONG":
            signal.stop_loss = signal.entry_price - (self.stop_multiplier * atr)
            for i, mul in enumerate(self.tp_multipliers, start=1):
                setattr(signal, f'take_profit_{i}', signal.entry_price + (mul * atr))
        
        elif signal.direction == "SHORT":
            signal.stop_loss = signal.entry_price + (self.stop_multiplier * atr)
            for i, mul in enumerate(self.tp_multipliers, start=1):
                setattr(signal, f'take_profit_{i}', signal.entry_price - (mul * atr))
    
    def run(self) -> AggregatedSignal:
        """To'liq pipeline - strategiyalarni ishlatib, natijani birlashtiradi"""
        results = self.run_all_strategies()
        return self.aggregate(results)
    
    def generate_text(self) -> tuple[str, AggregatedSignal]:
        """Signal uchun Telegram xabar matni generatsiya qiladi"""
        signal = self.run()
        
        emoji = {
            "LONG": "🟢",
            "SHORT": "🔴", 
            "NEUTRAL": "⚪"
        }
        
        total_strategies = len(signal.strategy_results)
        
        text = f"📊 **{self.symbol}**\n\n"
        text += f"**Signal:** {signal.direction} {emoji[signal.direction]}\n"
        text += f"**Consensus Score:** {signal.confidence:.1f}%\n"
        text += f"**Threshold:** {self.threshold}%\n\n"
        
        if signal.direction != "NEUTRAL":
            text += f"**Entry:** {signal.entry_price:.8g}\n"
            text += f"**Stop Loss:** {signal.stop_loss:.8g}\n"
            text += f"**TP1:** {signal.take_profit_1:.8g}\n"
            text += f"**TP2:** {signal.take_profit_2:.8g}\n"
            text += f"**TP3:** {signal.take_profit_3:.8g}\n\n"
        
        text += f"📈 Long: {signal.long_votes}/{total_strategies} (score: {signal.weighted_long_confidence:.1f}%)\n"
        text += f"📉 Short: {signal.short_votes}/{total_strategies} (score: {signal.weighted_short_confidence:.1f}%)\n"
        text += f"➖ Neutral: {signal.neutral_votes}\n"
        text += f"⚠️ Filtered (low conf): {signal.filtered_votes}\n\n"
        
        # Strategiya natijalarini ko'rsatish
        text += "**Strategy Details:**\n"
        for result in signal.strategy_results:
            dir_emoji = emoji.get(result.direction, "⚪")
            text += f"• {result.name}: {result.direction} {dir_emoji} ({result.confidence:.1f}%)\n"
        
        return text, signal

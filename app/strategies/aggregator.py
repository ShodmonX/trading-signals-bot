"""Signal Aggregator - Ensemble/Consensus Strategy System

Bu modul barcha strategiyalardan kelgan signallarni birlashtiradi
va yakuniy signal hamda SL/TP ni hisoblaydi.
"""

from typing import Literal
from dataclasses import dataclass, field
import pandas as pd
from ta.volatility import AverageTrueRange

from .strategies import StrategyResult, BaseStrategy


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
    """
    
    def __init__(
        self,
        data: list,
        symbol: str,
        strategies: list[type[BaseStrategy]],
        threshold: float = 60.0,
        stop_multiplier: float = 1.5,
        tp_multipliers: list[float] | None = None
    ):
        self.data = data
        self.symbol = symbol
        self.strategies = strategies
        self.threshold = threshold
        self.stop_multiplier = stop_multiplier
        self.tp_multipliers = tp_multipliers or [1.5, 3.0, 4.5]
        
        # DataFrame yaratish (ATR uchun)
        self.df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            'close_time', 'quote_asset_volume', 'trades', 'taker_base_vol',
            'taker_quote_vol', 'ignore'
        ])
        self.df[['open', 'high', 'low', 'close', 'volume']] = \
            self.df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    
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
        1. Minimum 2 ta strategiya bir xil yo'nalishda bo'lishi kerak
        2. Ko'pchilik ovoz ustunlik qiladi
        3. Agar ovozlar teng bo'lsa, weighted confidence qaraladi
        4. Final confidence = (votes_ratio * avg_confidence)
        """
        
        long_votes = 0
        short_votes = 0
        neutral_votes = 0
        
        weighted_long_sum = 0.0
        weighted_short_sum = 0.0
        total_long_weight = 0.0
        total_short_weight = 0.0
        
        for result in results:
            if result.direction == "LONG":
                long_votes += 1
                weighted_long_sum += result.confidence * result.weight
                total_long_weight += result.weight
            elif result.direction == "SHORT":
                short_votes += 1
                weighted_short_sum += result.confidence * result.weight
                total_short_weight += result.weight
            else:
                neutral_votes += 1
        
        # Weighted average confidence (faqat o'sha yo'nalishdagi strategiyalar orasida)
        avg_long_confidence = weighted_long_sum / total_long_weight if total_long_weight > 0 else 0.0
        avg_short_confidence = weighted_short_sum / total_short_weight if total_short_weight > 0 else 0.0
        
        # Total active votes (NEUTRAL dan tashqari)
        total_active_votes = long_votes + short_votes
        
        # Consensus score hisoblash
        # votes_ratio * average_confidence = final_score
        if total_active_votes > 0:
            long_ratio = long_votes / total_active_votes
            short_ratio = short_votes / total_active_votes
            
            # Final consensus score
            long_score = long_ratio * avg_long_confidence
            short_score = short_ratio * avg_short_confidence
        else:
            long_score = 0.0
            short_score = 0.0
            long_ratio = 0.0
            short_ratio = 0.0
        
        # Yakuniy yo'nalishni aniqlash
        entry_price = float(self.df['close'].iloc[-1])
        
        # Minimum 2 ta strategiya bir xil yo'nalishda bo'lishi kerak
        min_votes = 2
        
        if long_score >= self.threshold and long_votes >= min_votes and long_score > short_score:
            direction = "LONG"
            confidence = long_score
        elif short_score >= self.threshold and short_votes >= min_votes and short_score > long_score:
            direction = "SHORT"
            confidence = short_score
        else:
            direction = "NEUTRAL"
            confidence = max(long_score, short_score)
        
        # Signal obyektini yaratish
        signal = AggregatedSignal(
            direction=direction,
            confidence=confidence,
            entry_price=entry_price,
            strategy_results=results,
            long_votes=long_votes,
            short_votes=short_votes,
            neutral_votes=neutral_votes,
            weighted_long_confidence=long_score,  # Endi bu consensus score
            weighted_short_confidence=short_score  # Endi bu consensus score
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
        text += f"➖ Neutral: {signal.neutral_votes}\n\n"
        
        # Strategiya natijalarini ko'rsatish
        text += "**Strategy Details:**\n"
        for result in signal.strategy_results:
            dir_emoji = emoji.get(result.direction, "⚪")
            text += f"• {result.name}: {result.direction} {dir_emoji} ({result.confidence:.1f}%)\n"
        
        return text, signal

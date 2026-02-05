"""Backtesting Service

Strategiyalarni tarixiy ma'lumotlar asosida sinash uchun xizmat.
Partial close strategiyasi: 40% TP1, 30% TP2, 30% TP3
"""

import asyncio
import random
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import uuid4

import pandas as pd

from app.services.api import get_klines, BinanceAPI
from app.strategies.aggregator import SignalAggregator, AggregatedSignal
from app.services.strategy_registry import get_all_strategy_classes
from app.config import SIGNAL_THRESHOLD, STOP_LOSS_MULTIPLIER, TAKE_PROFIT_MULTIPLIERS


# Partial close foizlari
TP1_PERCENT = 0.40  # 40%
TP2_PERCENT = 0.30  # 30%
TP3_PERCENT = 0.30  # 30%


@dataclass
class TradeResult:
    """Bitta trade natijasi"""
    signal_time: datetime
    direction: Literal["LONG", "SHORT"]
    confidence: float
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    
    # Natijalar
    result: Literal["SL", "TP1", "TP2", "TP3", "PARTIAL", "TIMEOUT"] = "TIMEOUT"
    exit_time: datetime | None = None
    exit_price: float | None = None
    
    # Partial close tracking
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    sl_hit: bool = False
    
    # Trailing SL tracking - SL qaysi darajada hit bo'lganini saqlash
    sl_hit_at: Literal["ORIGINAL", "BREAKEVEN", "TP1"] | None = None
    
    # Profit/Loss (partial close bilan)
    total_profit_percent: float = 0.0
    
    def calculate_profit(self) -> float:
        """
        Partial close asosida profit hisoblash.
        
        Strategiya:
        - TP1 hit: 40% yopiladi, SL -> entry (breakeven)
        - TP2 hit: 30% yopiladi, SL -> TP1
        - TP3 hit: 30% yopiladi
        
        SL hit bo'lganda:
        - Original SL: loss = (SL - entry) * qolgan%
        - Breakeven (entry da): loss = 0
        - TP1 da: profit = (TP1 - entry) * qolgan%
        
        Muhim: Barcha profit/loss har doim entry price dan hisoblanadi!
        """
        profit = 0.0
        
        if self.direction == "LONG":
            # TP profits - har doim entry dan hisoblanadi
            if self.tp1_hit:
                profit += ((self.take_profit_1 - self.entry_price) / self.entry_price) * 100 * TP1_PERCENT
            if self.tp2_hit:
                profit += ((self.take_profit_2 - self.entry_price) / self.entry_price) * 100 * TP2_PERCENT
            if self.tp3_hit:
                profit += ((self.take_profit_3 - self.entry_price) / self.entry_price) * 100 * TP3_PERCENT
            
            # SL hit - qolgan pozitsiya uchun
            if self.sl_hit:
                remaining = 1.0
                if self.tp1_hit:
                    remaining -= TP1_PERCENT
                if self.tp2_hit:
                    remaining -= TP2_PERCENT
                if self.tp3_hit:
                    remaining -= TP3_PERCENT
                
                if remaining > 0:
                    if self.sl_hit_at == "ORIGINAL":
                        # Asl SL da yopildi - loss
                        profit += ((self.stop_loss - self.entry_price) / self.entry_price) * 100 * remaining
                    elif self.sl_hit_at == "BREAKEVEN":
                        # Entry da yopildi - 0% (breakeven)
                        profit += 0.0
                    elif self.sl_hit_at == "TP1":
                        # TP1 da yopildi - profit
                        profit += ((self.take_profit_1 - self.entry_price) / self.entry_price) * 100 * remaining
                        
        else:  # SHORT
            # TP profits - har doim entry dan hisoblanadi
            if self.tp1_hit:
                profit += ((self.entry_price - self.take_profit_1) / self.entry_price) * 100 * TP1_PERCENT
            if self.tp2_hit:
                profit += ((self.entry_price - self.take_profit_2) / self.entry_price) * 100 * TP2_PERCENT
            if self.tp3_hit:
                profit += ((self.entry_price - self.take_profit_3) / self.entry_price) * 100 * TP3_PERCENT
            
            # SL hit - qolgan pozitsiya uchun
            if self.sl_hit:
                remaining = 1.0
                if self.tp1_hit:
                    remaining -= TP1_PERCENT
                if self.tp2_hit:
                    remaining -= TP2_PERCENT
                if self.tp3_hit:
                    remaining -= TP3_PERCENT
                
                if remaining > 0:
                    if self.sl_hit_at == "ORIGINAL":
                        # Asl SL da yopildi - loss
                        profit += ((self.entry_price - self.stop_loss) / self.entry_price) * 100 * remaining
                    elif self.sl_hit_at == "BREAKEVEN":
                        # Entry da yopildi - 0% (breakeven)
                        profit += 0.0
                    elif self.sl_hit_at == "TP1":
                        # TP1 da yopildi - profit
                        profit += ((self.entry_price - self.take_profit_1) / self.entry_price) * 100 * remaining
        
        self.total_profit_percent = profit
        return profit


@dataclass
class BacktestSummary:
    """Backtest natijasi - umumiy statistika"""
    session_id: str
    symbol: str
    signal_timeframe: str
    execution_timeframe: str
    period_start: datetime
    period_end: datetime
    
    # Signal statistikasi
    total_signals: int = 0
    long_signals: int = 0
    short_signals: int = 0
    
    # Natija statistikasi
    wins: int = 0  # Kamida TP1 hit bo'lgan
    losses: int = 0  # Faqat SL hit bo'lgan
    partial_wins: int = 0  # TP1+SL yoki TP1+TP2+SL
    timeouts: int = 0  # Vaqt tugagan
    
    # TP taqsimoti
    tp1_hits: int = 0
    tp2_hits: int = 0
    tp3_hits: int = 0
    
    # Profit statistikasi
    total_profit_percent: float = 0.0
    average_profit: float = 0.0
    average_loss: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0
    profit_factor: float = 0.0
    
    # Win rate
    win_rate: float = 0.0
    
    # Trade natijalar ro'yxati
    trades: list[TradeResult] = field(default_factory=list)
    
    created_at: datetime = field(default_factory=datetime.now)


# Timeframe to minutes mapping
TIMEFRAME_MINUTES = {
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "2h": 120,
    "4h": 240,
    "6h": 360,
    "8h": 480,
    "12h": 720,
    "1d": 1440,
}


def get_smallest_execution_tf(signal_tf: str) -> str:
    """Har doim 1m execution timeframe qaytaradi - eng aniq backtest uchun"""
    return "1m"


class Backtester:
    """Backtesting xizmati"""
    
    def __init__(
        self,
        symbol: str,
        signal_timeframe: str,
        start_date: datetime,
        end_date: datetime,
        threshold: float = SIGNAL_THRESHOLD,
    ):
        self.symbol = symbol
        self.signal_timeframe = signal_timeframe
        self.execution_timeframe = get_smallest_execution_tf(signal_timeframe)
        self.start_date = start_date
        self.end_date = end_date
        self.threshold = threshold
        
        self.session_id = str(uuid4())[:8]
        
        # Ma'lumotlar
        self.execution_candles: list = []
        self.signal_candles: list = []
        
    async def fetch_historical_data(
        self,
        interval: str,
        start_time: int,
        end_time: int,
    ) -> list:
        """
        Tarixiy ma'lumotlarni olish (chunked).
        Binance API limit: 1000 candles per request
        """
        all_candles = []
        current_start = start_time
        
        while current_start < end_time:
            # Random sleep (0-1 sekund)
            await asyncio.sleep(random.uniform(0.1, 1.0))
            
            klines, error = await get_klines(
                symbol=self.symbol,
                interval=interval,
                limit=1000
            )
            
            if error or not klines:
                logging.error(f"Backtest data fetch error: {error}")
                break
            
            # Vaqt bo'yicha filter
            filtered = [
                k for k in klines
                if start_time <= k[0] <= end_time
            ]
            
            if not filtered:
                break
                
            all_candles.extend(filtered)
            
            # Keyingi chunk uchun start vaqtini yangilash
            last_time = klines[-1][0]
            if last_time <= current_start:
                break
            current_start = last_time + 1
            
            logging.info(f"Fetched {len(all_candles)} candles for {self.symbol} {interval}")
            
            # Agar oxirgi candle end_time dan o'tgan bo'lsa to'xtatish
            if last_time >= end_time:
                break
        
        # Unique va sorted
        unique_candles = {c[0]: c for c in all_candles}
        sorted_candles = sorted(unique_candles.values(), key=lambda x: x[0])
        
        return sorted_candles
    
    async def fetch_data_by_chunks(
        self,
        interval: str,
        start_time: int,
        end_time: int,
        progress_callback=None,
    ) -> list:
        """
        Ko'p chunklarda ma'lumot olish.
        Bunda startTime va endTime parametrlaridan foydalanamiz.
        """
        all_candles = []
        current_end = end_time
        total_duration = end_time - start_time
        
        # 1 oyda taxminan qancha 1m candle borligini hisoblash
        # 1 oy = ~43200 daqiqa = ~43200 candle
        interval_minutes = TIMEFRAME_MINUTES.get(interval, 1)
        expected_candles = total_duration // (interval_minutes * 60 * 1000)
        
        session = await BinanceAPI.get_session()
        
        request_count = 0
        max_requests = 100  # 1m uchun ko'proq kerak
        
        while current_end > start_time and request_count < max_requests:
            # Random sleep (0.1-0.5 sekund)
            await asyncio.sleep(random.uniform(0.1, 0.5))
            
            url = (
                f"https://api.binance.com/api/v3/klines"
                f"?symbol={self.symbol}"
                f"&interval={interval}"
                f"&limit=1000"
                f"&endTime={current_end}"
            )
            
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        klines = await response.json()
                        
                        if not klines:
                            break
                        
                        # Vaqt bo'yicha filter
                        filtered = [
                            k for k in klines
                            if start_time <= k[0] <= end_time
                        ]
                        
                        all_candles = filtered + all_candles
                        
                        # Keyingi chunk uchun end vaqtini yangilash
                        earliest_time = klines[0][0]
                        current_end = earliest_time - 1
                        
                        # Progress callback - yuklangan candle / kutilgan candle
                        if progress_callback:
                            # Yuklash foizi (0-100 o'z ichida)
                            load_percent = int((len(all_candles) / max(expected_candles, 1)) * 100)
                            # Umumiy progress: data yuklash 0-20% oralig'ida
                            overall_progress = min(20, load_percent // 5)
                            await progress_callback(
                                overall_progress, 100, 
                                f"📥 Ma'lumot: {len(all_candles):,} / ~{expected_candles:,} ({load_percent}%)"
                            )
                        
                        logging.debug(
                            f"Fetched chunk: {len(klines)} candles, "
                            f"total: {len(all_candles)}"
                        )
                        
                        # Agar birinchi candle start_time dan oldin bo'lsa to'xtatish
                        if earliest_time <= start_time:
                            break
                    
                    elif response.status == 429:
                        logging.warning("Rate limit hit, waiting 10s...")
                        await asyncio.sleep(10)
                        continue
                    else:
                        error_text = await response.text()
                        logging.error(f"API error {response.status}: {error_text}")
                        break
                        
            except Exception as e:
                logging.error(f"Request error: {e}")
                break
            
            request_count += 1
        
        # Unique va sorted
        unique_candles = {c[0]: c for c in all_candles}
        sorted_candles = sorted(unique_candles.values(), key=lambda x: x[0])
        
        return sorted_candles
    
    def aggregate_candles(self, candles_small: list, target_tf: str) -> list:
        """
        Kichik timeframe candle'larni katta timeframe ga birlashtirish.
        Masalan: 5m -> 1h (12 candle = 1 candle)
        """
        if not candles_small:
            return []
        
        source_minutes = TIMEFRAME_MINUTES[self.execution_timeframe]
        target_minutes = TIMEFRAME_MINUTES[target_tf]
        
        ratio = target_minutes // source_minutes
        
        if ratio <= 1:
            return candles_small
        
        aggregated = []
        
        for i in range(0, len(candles_small), ratio):
            chunk = candles_small[i:i + ratio]
            
            if len(chunk) < ratio:
                continue  # Incomplete candle
            
            aggregated.append([
                chunk[0][0],  # open_time
                chunk[0][1],  # open
                max(float(c[2]) for c in chunk),  # high
                min(float(c[3]) for c in chunk),  # low
                chunk[-1][4],  # close
                sum(float(c[5]) for c in chunk),  # volume
                chunk[-1][6],  # close_time
                sum(float(c[7]) for c in chunk),  # quote_volume
                sum(int(c[8]) for c in chunk),  # trades
                sum(float(c[9]) for c in chunk),  # taker_buy_base
                sum(float(c[10]) for c in chunk),  # taker_buy_quote
                chunk[-1][11],  # ignore
            ])
        
        return aggregated
    
    async def generate_signal(self, historical_data: list) -> AggregatedSignal | None:
        """Berilgan ma'lumotlar asosida signal generatsiya qilish"""
        if len(historical_data) < 100:
            return None
        
        try:
            # DB ga bog'liq bo'lmagan - barcha strategiyalarni olish
            strategy_classes = get_all_strategy_classes()
            
            aggregator = SignalAggregator(
                data=historical_data,
                symbol=self.symbol,
                strategies=strategy_classes,
                threshold=self.threshold,
                stop_multiplier=STOP_LOSS_MULTIPLIER,
                tp_multipliers=TAKE_PROFIT_MULTIPLIERS
            )
            
            signal = aggregator.run()
            return signal
            
        except Exception as e:
            logging.error(f"Signal generation error: {e}")
            return None
    
    def simulate_trade(
        self,
        signal: AggregatedSignal,
        signal_time: int,
        execution_candles: list,
        max_candles: int = 24
    ) -> TradeResult:
        """
        Trade ni simulyatsiya qilish.
        
        Partial close strategiyasi:
        - TP1 hit = 40% close
        - TP2 hit = 30% close (qolgan 60% dan)
        - TP3 hit = 30% close (qolgan 30%)
        
        SL hit bo'lganda qolgan pozitsiya yopiladi.
        """
        
        trade = TradeResult(
            signal_time=datetime.fromtimestamp(signal_time / 1000),
            direction=signal.direction,  # type: ignore
            confidence=signal.confidence,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss or 0,
            take_profit_1=signal.take_profit_1 or 0,
            take_profit_2=signal.take_profit_2 or 0,
            take_profit_3=signal.take_profit_3 or 0,
        )
        
        # Signal vaqtidan keyingi candle'larni olish
        future_candles = [
            c for c in execution_candles
            if c[0] > signal_time
        ][:max_candles]
        
        if not future_candles:
            trade.result = "TIMEOUT"
            return trade
        
        # TP1 dan keyin SL ni entry ga ko'chirish (breakeven)
        current_sl = trade.stop_loss
        current_sl_type: Literal["ORIGINAL", "BREAKEVEN", "TP1"] = "ORIGINAL"
        
        for candle in future_candles:
            high = float(candle[2])
            low = float(candle[3])
            candle_time = datetime.fromtimestamp(candle[6] / 1000)
            
            if signal.direction == "LONG":
                # SL check (birinchi, chunki bir candle da ikkalasi ham bo'lishi mumkin)
                if low <= current_sl:
                    trade.sl_hit = True
                    trade.sl_hit_at = current_sl_type
                    trade.exit_time = candle_time
                    trade.exit_price = current_sl
                    trade.result = "SL" if not trade.tp1_hit else "PARTIAL"
                    break
                
                # TP checks (ketma-ket)
                if not trade.tp1_hit and high >= trade.take_profit_1:
                    trade.tp1_hit = True
                    current_sl = trade.entry_price  # Breakeven
                    current_sl_type = "BREAKEVEN"
                    
                if trade.tp1_hit and not trade.tp2_hit and high >= trade.take_profit_2:
                    trade.tp2_hit = True
                    current_sl = trade.take_profit_1  # SL ni TP1 ga ko'chirish
                    current_sl_type = "TP1"
                    
                if trade.tp2_hit and not trade.tp3_hit and high >= trade.take_profit_3:
                    trade.tp3_hit = True
                    trade.exit_time = candle_time
                    trade.exit_price = trade.take_profit_3
                    trade.result = "TP3"
                    break
                    
            else:  # SHORT
                # SL check
                if high >= current_sl:
                    trade.sl_hit = True
                    trade.sl_hit_at = current_sl_type
                    trade.exit_time = candle_time
                    trade.exit_price = current_sl
                    trade.result = "SL" if not trade.tp1_hit else "PARTIAL"
                    break
                
                # TP checks
                if not trade.tp1_hit and low <= trade.take_profit_1:
                    trade.tp1_hit = True
                    current_sl = trade.entry_price  # Breakeven
                    current_sl_type = "BREAKEVEN"
                    
                if trade.tp1_hit and not trade.tp2_hit and low <= trade.take_profit_2:
                    trade.tp2_hit = True
                    current_sl = trade.take_profit_1
                    current_sl_type = "TP1"
                    
                if trade.tp2_hit and not trade.tp3_hit and low <= trade.take_profit_3:
                    trade.tp3_hit = True
                    trade.exit_time = candle_time
                    trade.exit_price = trade.take_profit_3
                    trade.result = "TP3"
                    break
        
        # Agar hech narsa hit bo'lmagan bo'lsa
        if trade.result == "TIMEOUT":
            if trade.tp1_hit:
                # PARTIAL - TP1 (va ehtimol TP2) hit bo'ldi, lekin trade hali yopilmadi
                # Oxirgi candle close da yopildi deb hisoblaymiz
                trade.result = "PARTIAL"
                if future_candles:
                    last_candle = future_candles[-1] if len(future_candles) <= max_candles else future_candles[max_candles - 1]
                    trade.exit_time = datetime.fromtimestamp(last_candle[6] / 1000)
                    # PARTIAL da exit_price - oxirgi close yoki eng yaxshi TP
                    if trade.tp2_hit:
                        # TP2 gacha yetdi, qolgan 30% oxirgi close da
                        trade.exit_price = float(last_candle[4])
                    else:
                        # Faqat TP1, qolgan 60% oxirgi close da
                        trade.exit_price = float(last_candle[4])
            elif not trade.sl_hit and not trade.tp1_hit:
                trade.result = "TIMEOUT"
                # TIMEOUT da oxirgi candle close price da yopilgan deb hisoblaymiz
                if future_candles:
                    last_candle = future_candles[-1] if len(future_candles) <= max_candles else future_candles[max_candles - 1]
                    last_close = float(last_candle[4])
                    trade.exit_time = datetime.fromtimestamp(last_candle[6] / 1000)
                    trade.exit_price = last_close
                    
                    # TIMEOUT profit hisoblash
                    if signal.direction == "LONG":
                        trade.total_profit_percent = ((last_close - trade.entry_price) / trade.entry_price) * 100
                    else:  # SHORT
                        trade.total_profit_percent = ((trade.entry_price - last_close) / trade.entry_price) * 100
                    return trade  # calculate_profit() ni chaqirmaslik
        
        # Profit hisoblash
        trade.calculate_profit()
        
        return trade
    
    async def run(self, progress_callback=None) -> BacktestSummary:
        """
        To'liq backtest ishga tushirish.
        
        progress_callback: async func(current, total, message) - progress uchun
        """
        
        summary = BacktestSummary(
            session_id=self.session_id,
            symbol=self.symbol,
            signal_timeframe=self.signal_timeframe,
            execution_timeframe=self.execution_timeframe,
            period_start=self.start_date,
            period_end=self.end_date,
        )
        
        start_ts = int(self.start_date.timestamp() * 1000)
        end_ts = int(self.end_date.timestamp() * 1000)
        
        # 1. Execution timeframe (1m) uchun ma'lumotlarni olish
        if progress_callback:
            await progress_callback(0, 100, "📥 1m ma'lumotlar yuklanmoqda...")
        
        logging.info(f"Fetching 1m data for {self.symbol}...")
        
        self.execution_candles = await self.fetch_data_by_chunks(
            interval=self.execution_timeframe,
            start_time=start_ts,
            end_time=end_ts,
            progress_callback=progress_callback,
        )
        
        if not self.execution_candles:
            logging.error("No execution candles fetched")
            return summary
        
        if progress_callback:
            await progress_callback(
                20, 100, 
                f"✅ {len(self.execution_candles):,} ta 1m candle yuklandi"
            )
        
        logging.info(f"Fetched {len(self.execution_candles)} execution candles")
        
        # 2. Signal timeframe ga aggregate qilish
        if progress_callback:
            await progress_callback(22, 100, f"📊 {self.signal_timeframe} ga aggregatsiya...")
        
        self.signal_candles = self.aggregate_candles(
            self.execution_candles, 
            self.signal_timeframe
        )
        
        if len(self.signal_candles) < 100:
            logging.error(f"Not enough signal candles: {len(self.signal_candles)}")
            return summary
        
        logging.info(f"Aggregated to {len(self.signal_candles)} signal candles")
        
        # 3. Signal tahlili
        if progress_callback:
            await progress_callback(25, 100, "🔍 Signallar aniqlanmoqda...")
        
        total_candles = len(self.signal_candles)
        start_index = 100
        signals_found = 0
        
        position_open = False
        position_close_candle = start_index
        
        for i in range(start_index, total_candles):
            # Progress
            if progress_callback and i % 20 == 0:
                progress = 25 + int((i - start_index) / (total_candles - start_index) * 70)
                await progress_callback(
                    progress, 100, 
                    f"🔍 Tahlil: {i}/{total_candles} | Signallar: {signals_found}"
                )
            
            if position_open:
                if i < position_close_candle:
                    continue
                else:
                    position_open = False
            
            historical_data = self.signal_candles[:i + 1]
            signal = await self.generate_signal(historical_data)
            
            if signal and signal.direction != "NEUTRAL":
                signals_found += 1
                signal_time = self.signal_candles[i][6]
                
                signal_minutes = TIMEFRAME_MINUTES[self.signal_timeframe]
                exec_minutes = TIMEFRAME_MINUTES[self.execution_timeframe]
                max_exec_candles = 24 * (signal_minutes // exec_minutes)
                
                trade = self.simulate_trade(
                    signal=signal,
                    signal_time=signal_time,
                    execution_candles=self.execution_candles,
                    max_candles=max_exec_candles
                )
                
                summary.trades.append(trade)
                
                position_open = True
                
                if trade.exit_time:
                    exit_ts = int(trade.exit_time.timestamp() * 1000)
                    found = False
                    for j in range(i + 1, min(i + 30, total_candles)):
                        if self.signal_candles[j][0] >= exit_ts:
                            position_close_candle = j
                            found = True
                            break
                    if not found:
                        position_close_candle = min(i + 25, total_candles)
                else:
                    position_close_candle = min(i + 25, total_candles)
        
        # 4. Statistika hisoblash
        if progress_callback:
            await progress_callback(95, 100, "📈 Statistika hisoblanmoqda...")
        
        self._calculate_statistics(summary)
        
        if progress_callback:
            await progress_callback(100, 100, "✅ Backtest tugadi!")
        
        return summary
    
    def _calculate_statistics(self, summary: BacktestSummary) -> None:
        """Yakuniy statistikani hisoblash"""
        
        trades = summary.trades
        
        if not trades:
            return
        
        summary.total_signals = len(trades)
        summary.long_signals = sum(1 for t in trades if t.direction == "LONG")
        summary.short_signals = sum(1 for t in trades if t.direction == "SHORT")
        
        # TP hits
        summary.tp1_hits = sum(1 for t in trades if t.tp1_hit)
        summary.tp2_hits = sum(1 for t in trades if t.tp2_hit)
        summary.tp3_hits = sum(1 for t in trades if t.tp3_hit)
        
        # Results
        summary.wins = sum(1 for t in trades if t.tp1_hit and not t.sl_hit)
        summary.losses = sum(1 for t in trades if t.sl_hit and not t.tp1_hit)
        summary.partial_wins = sum(1 for t in trades if t.tp1_hit and t.sl_hit)
        summary.timeouts = sum(1 for t in trades if t.result == "TIMEOUT")
        
        # Profit
        profits = [t.total_profit_percent for t in trades if t.total_profit_percent > 0]
        losses = [t.total_profit_percent for t in trades if t.total_profit_percent < 0]
        
        summary.total_profit_percent = sum(t.total_profit_percent for t in trades)
        summary.average_profit = sum(profits) / len(profits) if profits else 0
        summary.average_loss = abs(sum(losses) / len(losses)) if losses else 0
        summary.max_profit = max(profits) if profits else 0
        summary.max_loss = abs(min(losses)) if losses else 0
        
        # Profit factor
        gross_profit = sum(profits)
        gross_loss = abs(sum(losses))
        summary.profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Win rate (kamida TP1 hit bo'lgan + partial)
        total_closed = summary.wins + summary.losses + summary.partial_wins
        if total_closed > 0:
            summary.win_rate = (summary.wins + summary.partial_wins) / total_closed * 100

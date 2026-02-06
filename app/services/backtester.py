"""Backtesting Service

Strategiyalarni tarixiy ma'lumotlar asosida sinash uchun xizmat.
Partial close strategiyasi: 40% TP1, 30% TP2, 30% TP3
"""

import asyncio
import random
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4
from pathlib import Path

import pandas as pd
import numpy as np
from ta.volatility import AverageTrueRange
from ta.trend import ADXIndicator

from app.services.api import get_klines, BinanceAPI
from app.strategies.aggregator import (
    SignalAggregator,
    AggregatedSignal,
    ADX_TREND_THRESHOLD,
    ADX_RANGE_THRESHOLD,
    TREND_STRATEGY_NAMES,
    RANGE_STRATEGY_NAMES,
    TREND_BOOST,
    TREND_DAMPEN,
    RANGE_BOOST,
    RANGE_DAMPEN,
)
from app.services.strategy_registry import (
    StrategyConfig,
    get_active_strategy_configs,
    get_fallback_strategy_configs,
)
from app.config import SIGNAL_THRESHOLD, STOP_LOSS_MULTIPLIER, TAKE_PROFIT_MULTIPLIERS, DATA_CACHE_DIR


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
class StrategyPerformance:
    """Har bir strategiya uchun backtest natijalari"""
    code: str
    name: str
    total_signals: int = 0
    wins: int = 0
    losses: int = 0
    partial_wins: int = 0
    timeouts: int = 0
    total_profit_percent: float = 0.0
    average_profit: float = 0.0
    average_loss: float = 0.0
    profit_factor: float = 0.0
    win_rate: float = 0.0
    current_weight: float = 1.0
    suggested_weight: float = 1.0
    base_weight: float = 1.0
    perf_weight: float = 1.0
    regime_mult: float = 1.0
    stability_weight: float = 1.0
    corr_penalty: float = 1.0
    actual_weight: float = 1.0

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "total_signals": self.total_signals,
            "wins": self.wins,
            "losses": self.losses,
            "partial_wins": self.partial_wins,
            "timeouts": self.timeouts,
            "total_profit_percent": self.total_profit_percent,
            "average_profit": self.average_profit,
            "average_loss": self.average_loss,
            "profit_factor": self.profit_factor,
            "win_rate": self.win_rate,
            "current_weight": self.current_weight,
            "suggested_weight": self.suggested_weight,
            "base_weight": self.base_weight,
            "perf_weight": self.perf_weight,
            "regime_mult": self.regime_mult,
            "stability_weight": self.stability_weight,
            "corr_penalty": self.corr_penalty,
            "actual_weight": self.actual_weight,
        }


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

    # Strategiyalar performance natijalari
    strategy_performance: list[StrategyPerformance] = field(default_factory=list)
    
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

# Kline CSV columns (Binance API order)
KLINE_COLUMNS = [
    "timestamp", "open", "high", "low", "close", "volume",
    "close_time", "quote_asset_volume", "trades", "taker_base_vol",
    "taker_quote_vol", "ignore"
]


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
        self.cache_dir = Path(DATA_CACHE_DIR)
        
        # Ma'lumotlar
        self.execution_candles: list = []
        self.signal_candles: list = []

        # Strategiyalar (active) va weight mapping
        self.strategy_configs: list[StrategyConfig] = []
        self.strategy_weights: dict[str, float] = {}
        self.strategy_code_map: dict[str, str] = {}
        self.strategy_name_map: dict[str, str] = {}
        
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
    
    def _month_key(self, dt: datetime) -> str:
        return f"{dt.year:04d}_{dt.month:02d}"

    def _month_bounds(self, dt: datetime) -> tuple[int, int]:
        """Oyning boshi va oxiri (UTC, ms)"""
        start = datetime(dt.year, dt.month, 1, 0, 0, 0, tzinfo=timezone.utc)
        if dt.month == 12:
            next_month = datetime(dt.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        else:
            next_month = datetime(dt.year, dt.month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        start_ms = int(start.timestamp() * 1000)
        end_ms = int(next_month.timestamp() * 1000) - 1
        return start_ms, end_ms

    def _iter_months(self, start_time: int, end_time: int) -> list[datetime]:
        """start/end oralig'ida oylik datetime list (UTC)"""
        start_dt = datetime.fromtimestamp(start_time / 1000, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(end_time / 1000, tz=timezone.utc)
        current = datetime(start_dt.year, start_dt.month, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_month = datetime(end_dt.year, end_dt.month, 1, 0, 0, 0, tzinfo=timezone.utc)
        months = []
        while current <= end_month:
            months.append(current)
            if current.month == 12:
                current = datetime(current.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
            else:
                current = datetime(current.year, current.month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        return months

    def _month_cache_path(self, symbol: str, month_key: str) -> Path:
        return self.cache_dir / symbol / f"{month_key}.csv"

    def _load_month_from_cache(self, path: Path) -> list:
        df = pd.read_csv(path)
        return df[KLINE_COLUMNS].values.tolist()

    def _save_month_to_cache(self, path: Path, candles: list) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(candles, columns=KLINE_COLUMNS)
        df.to_csv(path, index=False)

    async def _fetch_range_by_chunks(
        self,
        interval: str,
        start_time: int,
        end_time: int,
        progress_callback=None,
        progress_prefix: str | None = None,
    ) -> list:
        """
        Ko'p chunklarda ma'lumot olish (API).
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
                            prefix = f"{progress_prefix} " if progress_prefix else ""
                            await progress_callback(
                                overall_progress, 100, 
                                f"{prefix}📥 Ma'lumot: {len(all_candles):,} / ~{expected_candles:,} ({load_percent}%)"
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

    async def fetch_data_by_chunks(
        self,
        interval: str,
        start_time: int,
        end_time: int,
        progress_callback=None,
    ) -> list:
        """
        Oylik cache bilan ma'lumot olish.
        Har oy alohida CSV faylga saqlanadi va qayta ishlatiladi.
        """
        all_candles: list = []
        months = self._iter_months(start_time, end_time)

        for month_dt in months:
            month_key = self._month_key(month_dt)
            month_start, month_end = self._month_bounds(month_dt)
            cache_path = self._month_cache_path(self.symbol, month_key)

            now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
            should_refresh = month_end > now_ms

            if cache_path.exists() and not should_refresh:
                try:
                    candles = self._load_month_from_cache(cache_path)
                except Exception as e:
                    logging.warning(f"Cache read error {cache_path}: {e}")
                    candles = []
            else:
                candles = []

            if not candles:
                candles = await self._fetch_range_by_chunks(
                    interval=interval,
                    start_time=month_start,
                    end_time=month_end,
                    progress_callback=progress_callback,
                    progress_prefix=f"🗓 {month_key}"
                )
                if candles:
                    self._save_month_to_cache(cache_path, candles)

            # Faqat kerakli vaqt oralig'ini qoldiramiz
            filtered = [c for c in candles if start_time <= c[0] <= end_time]
            all_candles.extend(filtered)

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

    async def _load_strategy_configs(self) -> None:
        """DB dan faol strategiyalar konfiguratsiyasini yuklash"""
        configs = await get_active_strategy_configs()
        if not configs:
            configs = get_fallback_strategy_configs()
        self.strategy_configs = configs
        self.strategy_weights = {
            cfg.cls.__name__: cfg.performance_weight for cfg in configs
        }
        self.strategy_code_map = {cfg.cls.__name__: cfg.code for cfg in configs}
        self.strategy_name_map = {cfg.cls.__name__: cfg.name for cfg in configs}

    def _compute_atr(self, historical_data: list) -> float:
        """ATR ni hisoblash (signal timeframe)"""
        if len(historical_data) < 14:
            return 0.0
        df = pd.DataFrame(historical_data, columns=KLINE_COLUMNS)
        df[['open', 'high', 'low', 'close', 'volume']] = \
            df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        atr_indicator = AverageTrueRange(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            window=14,
            fillna=True
        )
        atr = float(atr_indicator.average_true_range().iloc[-1])
        return 0.0 if pd.isna(atr) else atr

    def _compute_adx(self, historical_data: list) -> float:
        """ADX ni hisoblash (signal timeframe)"""
        if len(historical_data) < 14:
            return 0.0
        df = pd.DataFrame(historical_data, columns=KLINE_COLUMNS)
        df[['open', 'high', 'low', 'close', 'volume']] = \
            df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        adx_indicator = ADXIndicator(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            window=14
        )
        adx = float(adx_indicator.adx().iloc[-1])
        return 0.0 if pd.isna(adx) else adx

    def _get_regime_multiplier(self, adx_value: float, strategy_name: str) -> float:
        """ADX ga ko'ra strategiya uchun regime multiplier"""
        if adx_value >= ADX_TREND_THRESHOLD:
            if strategy_name in TREND_STRATEGY_NAMES:
                return TREND_BOOST
            if strategy_name in RANGE_STRATEGY_NAMES:
                return TREND_DAMPEN
        if adx_value <= ADX_RANGE_THRESHOLD:
            if strategy_name in RANGE_STRATEGY_NAMES:
                return RANGE_BOOST
            if strategy_name in TREND_STRATEGY_NAMES:
                return RANGE_DAMPEN
        return 1.0

    def _compute_stability_weight(self, returns: list[float]) -> float:
        """Stability weight (volatility penalti)"""
        if len(returns) < 2:
            return 1.0
        std = float(np.std(returns))
        scale = 5.0
        raw = 1.0 / (1.0 + (std / scale)) if std >= 0 else 1.0
        return max(0.5, min(1.5, raw))

    def _compute_correlation_penalties(self, returns_by_time: dict[str, dict[int, float]]) -> dict[str, float]:
        """Strategiyalar orasidagi korrelyatsiya penalti"""
        penalties: dict[str, float] = {}
        codes = list(returns_by_time.keys())
        for code in codes:
            corr_vals: list[float] = []
            series = returns_by_time.get(code, {})
            for other in codes:
                if other == code:
                    continue
                other_series = returns_by_time.get(other, {})
                common_times = set(series.keys()) & set(other_series.keys())
                if len(common_times) < 5:
                    continue
                x = np.array([series[t] for t in common_times], dtype=float)
                y = np.array([other_series[t] for t in common_times], dtype=float)
                if np.std(x) == 0 or np.std(y) == 0:
                    continue
                corr = float(np.corrcoef(x, y)[0, 1])
                if not np.isnan(corr):
                    corr_vals.append(abs(corr))
            if not corr_vals:
                penalties[code] = 1.0
            else:
                avg_corr = float(np.mean(corr_vals))
                raw = 1.0 - (0.5 * avg_corr)
                penalties[code] = max(0.5, min(1.0, raw))
        return penalties

    def _apply_sl_tp(self, signal: AggregatedSignal, atr: float) -> None:
        """ATR asosida Stop Loss va Take Profit hisoblash"""
        if atr <= 0:
            return
        if signal.direction == "LONG":
            signal.stop_loss = signal.entry_price - (STOP_LOSS_MULTIPLIER * atr)
            for i, mul in enumerate(TAKE_PROFIT_MULTIPLIERS, start=1):
                setattr(signal, f'take_profit_{i}', signal.entry_price + (mul * atr))
        elif signal.direction == "SHORT":
            signal.stop_loss = signal.entry_price + (STOP_LOSS_MULTIPLIER * atr)
            for i, mul in enumerate(TAKE_PROFIT_MULTIPLIERS, start=1):
                setattr(signal, f'take_profit_{i}', signal.entry_price - (mul * atr))

    def _calculate_performance_weight(self, stats: dict) -> float:
        """Performance weight hisoblash (hozircha bir xil)"""
        pf = stats.get("profit_factor", 0.0)
        win_rate = stats.get("win_rate", 0.0)
        total_signals = stats.get("total_signals", 0)

        # PF + WinRate asosida weight
        raw = (pf / 1.1) * ((win_rate / 55.0) ** 0.5) if pf > 0 and win_rate > 0 else 0.3
        weight = max(0.3, min(2.5, raw))

        # Kichik sample uchun 1.0 ga shrink
        alpha = min(1.0, total_signals / 30) if total_signals > 0 else 0.0
        final_weight = 1.0 + alpha * (weight - 1.0)
        return round(final_weight, 4)

    def _calculate_strategy_stats(self, trades: list[TradeResult]) -> dict:
        """Strategiya bo'yicha statistikani hisoblash"""
        stats = {
            "total_signals": 0,
            "wins": 0,
            "losses": 0,
            "partial_wins": 0,
            "timeouts": 0,
            "total_profit_percent": 0.0,
            "average_profit": 0.0,
            "average_loss": 0.0,
            "max_profit": 0.0,
            "max_loss": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
        }
        if not trades:
            return stats
        stats["total_signals"] = len(trades)
        stats["wins"] = sum(1 for t in trades if t.tp1_hit and not t.sl_hit)
        stats["losses"] = sum(1 for t in trades if t.sl_hit and not t.tp1_hit)
        stats["partial_wins"] = sum(1 for t in trades if t.tp1_hit and t.sl_hit)
        stats["timeouts"] = sum(1 for t in trades if t.result == "TIMEOUT")

        profits = [t.total_profit_percent for t in trades if t.total_profit_percent > 0]
        losses = [t.total_profit_percent for t in trades if t.total_profit_percent < 0]

        stats["total_profit_percent"] = sum(t.total_profit_percent for t in trades)
        stats["average_profit"] = sum(profits) / len(profits) if profits else 0.0
        stats["average_loss"] = abs(sum(losses) / len(losses)) if losses else 0.0
        stats["max_profit"] = max(profits) if profits else 0.0
        stats["max_loss"] = abs(min(losses)) if losses else 0.0

        gross_profit = sum(profits)
        gross_loss = abs(sum(losses))
        stats["profit_factor"] = gross_profit / gross_loss if gross_loss > 0 else 0.0

        total_closed = stats["wins"] + stats["losses"] + stats["partial_wins"]
        if total_closed > 0:
            stats["win_rate"] = (stats["wins"] + stats["partial_wins"]) / total_closed * 100
        return stats
    
    async def generate_signal(self, historical_data: list) -> AggregatedSignal | None:
        """Berilgan ma'lumotlar asosida signal generatsiya qilish"""
        if len(historical_data) < 100:
            return None

        try:
            if not self.strategy_configs:
                await self._load_strategy_configs()

            strategy_classes = [cfg.cls for cfg in self.strategy_configs]

            aggregator = SignalAggregator(
                data=historical_data,
                symbol=self.symbol,
                strategies=strategy_classes,
                threshold=self.threshold,
                stop_multiplier=STOP_LOSS_MULTIPLIER,
                tp_multipliers=TAKE_PROFIT_MULTIPLIERS,
                strategy_weights=self.strategy_weights,
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

        # Strategiyalarni yuklash (faqat bir marta)
        await self._load_strategy_configs()
        
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

        # Strategiya bo'yicha tracking
        strategy_trades: dict[str, list[TradeResult]] = {
            cfg.code: [] for cfg in self.strategy_configs
        }
        strategy_position_open: dict[str, bool] = {
            cfg.code: False for cfg in self.strategy_configs
        }
        strategy_close_candle: dict[str, int] = {
            cfg.code: start_index for cfg in self.strategy_configs
        }
        strategy_regime_mults: dict[str, list[float]] = {
            cfg.code: [] for cfg in self.strategy_configs
        }
        
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

            # Strategiyalar bo'yicha position holatini yangilash
            for code in list(strategy_position_open.keys()):
                if strategy_position_open[code] and i >= strategy_close_candle[code]:
                    strategy_position_open[code] = False
            
            historical_data = self.signal_candles[:i + 1]
            signal = await self.generate_signal(historical_data)
            if not signal:
                continue

            signal_time = self.signal_candles[i][6]

            signal_minutes = TIMEFRAME_MINUTES[self.signal_timeframe]
            exec_minutes = TIMEFRAME_MINUTES[self.execution_timeframe]
            max_exec_candles = 24 * (signal_minutes // exec_minutes)

            # Ensemble trade
            if signal.direction != "NEUTRAL":
                signals_found += 1

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

            # Strategiyalar bo'yicha trade simulyatsiya
            atr_value: float | None = None
            adx_value: float | None = None
            for result in signal.strategy_results:
                code = self.strategy_code_map.get(result.name)
                if not code:
                    continue

                if strategy_position_open.get(code):
                    if i < strategy_close_candle.get(code, start_index):
                        continue
                    strategy_position_open[code] = False

                if result.direction == "NEUTRAL" or result.confidence < self.threshold:
                    continue

                if atr_value is None:
                    atr_value = self._compute_atr(historical_data)
                if atr_value <= 0:
                    continue
                if adx_value is None:
                    adx_value = self._compute_adx(historical_data)

                strategy_signal = AggregatedSignal(
                    direction=result.direction,
                    confidence=result.confidence,
                    entry_price=signal.entry_price,
                )
                self._apply_sl_tp(strategy_signal, atr_value)

                trade = self.simulate_trade(
                    signal=strategy_signal,
                    signal_time=signal_time,
                    execution_candles=self.execution_candles,
                    max_candles=max_exec_candles
                )
                strategy_trades.setdefault(code, []).append(trade)
                regime_mult = self._get_regime_multiplier(adx_value, result.name)
                strategy_regime_mults.setdefault(code, []).append(regime_mult)

                strategy_position_open[code] = True

                if trade.exit_time:
                    exit_ts = int(trade.exit_time.timestamp() * 1000)
                    found = False
                    for j in range(i + 1, min(i + 30, total_candles)):
                        if self.signal_candles[j][0] >= exit_ts:
                            strategy_close_candle[code] = j
                            found = True
                            break
                    if not found:
                        strategy_close_candle[code] = min(i + 25, total_candles)
                else:
                    strategy_close_candle[code] = min(i + 25, total_candles)
        
        # 4. Statistika hisoblash
        if progress_callback:
            await progress_callback(95, 100, "📈 Statistika hisoblanmoqda...")
        
        self._calculate_statistics(summary)

        # Strategiyalar performance hisoblash
        summary.strategy_performance = []
        returns_by_time: dict[str, dict[int, float]] = {}
        for cfg in self.strategy_configs:
            trades = strategy_trades.get(cfg.code, [])
            returns_by_time[cfg.code] = {
                int(t.signal_time.timestamp()): t.total_profit_percent for t in trades
            }
        corr_penalties = self._compute_correlation_penalties(returns_by_time)
        for cfg in self.strategy_configs:
            trades = strategy_trades.get(cfg.code, [])
            stats = self._calculate_strategy_stats(trades)
            returns = [t.total_profit_percent for t in trades]
            stability_weight = self._compute_stability_weight(returns)
            corr_penalty = corr_penalties.get(cfg.code, 1.0)
            regime_list = strategy_regime_mults.get(cfg.code, [])
            regime_mult = float(np.mean(regime_list)) if regime_list else 1.0

            base_weight = getattr(cfg.cls, "weight", 1.0)
            perf_weight = cfg.performance_weight
            actual_weight = base_weight * perf_weight * regime_mult * stability_weight * corr_penalty
            actual_weight = max(0.1, min(3.0, actual_weight))

            perf = StrategyPerformance(
                code=cfg.code,
                name=cfg.name,
                total_signals=stats["total_signals"],
                wins=stats["wins"],
                losses=stats["losses"],
                partial_wins=stats["partial_wins"],
                timeouts=stats["timeouts"],
                total_profit_percent=stats["total_profit_percent"],
                average_profit=stats["average_profit"],
                average_loss=stats["average_loss"],
                profit_factor=stats["profit_factor"],
                win_rate=stats["win_rate"],
                current_weight=cfg.performance_weight,
                suggested_weight=self._calculate_performance_weight(stats),
                base_weight=base_weight,
                perf_weight=perf_weight,
                regime_mult=regime_mult,
                stability_weight=stability_weight,
                corr_penalty=corr_penalty,
                actual_weight=actual_weight,
            )
            summary.strategy_performance.append(perf)
        
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

"""
Strategy Registry - Strategiyalarni DB dan yuklash va mapping qilish

Bu modul strategiya kodlarini Python klasslariga mapping qiladi
va DB dan dinamik ravishda strategiyalarni yuklaydi.
"""

from typing import Type
from dataclasses import dataclass
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.strategies import (
    BaseStrategy,
    TrendFollowStrategy, 
    MACDCrossoverStrategy, 
    BollingerBandSqueezeStrategy, 
    StochasticOscillatorStrategy, 
    SMACrossoverStrategy, 
    WilliamsFractalsStrategy
)
from app.db import LocalAsyncSession, StrategyCRUD
from app.db.models import Strategy


# Strategiya konfiguratsiyasi
@dataclass
class StrategyConfig:
    code: str
    name: str
    cls: Type[BaseStrategy]
    performance_weight: float = 1.0
    is_active: bool = True

# Strategiya kodi -> Python class mapping
# Bu yerda yangi strategiya qo'shilganda faqat shu dict ni yangilash kerak
STRATEGY_CLASS_MAP: dict[str, Type[BaseStrategy] | None] = {
    "trendfollowstrategy": TrendFollowStrategy, 
    "macdcrossoverstrategy": MACDCrossoverStrategy,
    "bollingerbandsqueezestrategy": BollingerBandSqueezeStrategy,
    "stochasticoscillatorstrategy": StochasticOscillatorStrategy,
    "smacrossoverstrategy": SMACrossoverStrategy, 
    "williamsfractalsstrategy": WilliamsFractalsStrategy,
    "ensemble": None,  # Ensemble - bu aggregator, alohida class emas
}


def get_strategy_class(code: str) -> Type[BaseStrategy] | None:
    """Strategiya kodiga mos Python klassini qaytaradi"""
    return STRATEGY_CLASS_MAP.get(code.lower())


def get_all_strategy_classes() -> list[Type[BaseStrategy]]:
    """Barcha strategiya klasslarini qaytaradi (ensemble dan tashqari)"""
    return [cls for cls in STRATEGY_CLASS_MAP.values() if cls is not None]


def get_fallback_strategy_configs() -> list[StrategyConfig]:
    """DB bo'lmaganda fallback strategiya konfiguratsiyalari"""
    configs: list[StrategyConfig] = []
    for code, cls in STRATEGY_CLASS_MAP.items():
        if cls is None:
            continue
        configs.append(
            StrategyConfig(
                code=code,
                name=cls.__name__,
                cls=cls,
                performance_weight=1.0,
                is_active=True,
            )
        )
    return configs


async def get_active_strategies() -> list[Strategy]:
    """DB dan faol strategiyalarni olish"""
    async with LocalAsyncSession() as session:
        crud = StrategyCRUD(session)
        return await crud.get_all(only_active=True)


async def get_all_strategies() -> list[Strategy]:
    """DB dan barcha strategiyalarni olish (faol/nochal)"""
    async with LocalAsyncSession() as session:
        crud = StrategyCRUD(session)
        return await crud.get_all(only_active=False)


async def get_active_strategy_classes() -> list[Type[BaseStrategy]]:
    """DB dan faol strategiyalarning Python klasslarini olish"""
    strategies = await get_active_strategies()
    classes = []
    for strategy in strategies:
        cls = get_strategy_class(strategy.code)
        if cls is not None:
            classes.append(cls)
    return classes


async def get_active_strategy_configs() -> list[StrategyConfig]:
    """DB dan faol strategiyalar konfiguratsiyasini olish"""
    strategies = await get_active_strategies()
    configs: list[StrategyConfig] = []
    for strategy in strategies:
        cls = get_strategy_class(strategy.code)
        if cls is not None:
            configs.append(
                StrategyConfig(
                    code=strategy.code,
                    name=strategy.name,
                    cls=cls,
                    performance_weight=strategy.performance_weight or 1.0,
                    is_active=strategy.is_active,
                )
            )
    return configs


async def get_all_strategy_configs() -> list[StrategyConfig]:
    """DB dan barcha strategiyalar konfiguratsiyasini olish"""
    strategies = await get_all_strategies()
    configs: list[StrategyConfig] = []
    for strategy in strategies:
        cls = get_strategy_class(strategy.code)
        if cls is not None:
            configs.append(
                StrategyConfig(
                    code=strategy.code,
                    name=strategy.name,
                    cls=cls,
                    performance_weight=strategy.performance_weight or 1.0,
                    is_active=strategy.is_active,
                )
            )
    return configs


async def build_strategies_keyboard() -> InlineKeyboardMarkup:
    """DB dan faol strategiyalar asosida dinamik keyboard yaratish"""
    strategies = await get_active_strategies()
    
    buttons = []
    for strategy in strategies:
        # Ensemble ni keyboard da ko'rsatmaymiz
        if strategy.code == "ensemble":
            continue
        buttons.append([
            InlineKeyboardButton(
                text=strategy.name, 
                callback_data=f'strategy:{strategy.code}'
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def get_strategy_by_code(code: str) -> Strategy | None:
    """DB dan strategiyani kod bo'yicha olish"""
    async with LocalAsyncSession() as session:
        crud = StrategyCRUD(session)
        return await crud.get_by_code(code)

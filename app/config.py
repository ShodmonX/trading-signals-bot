from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PrivateAttr
from typing import Type

from functools import lru_cache

from .strategies import (
    BaseStrategy,
    TrendFollowStrategy, 
    MACDCrossoverStrategy, 
    BollingerBandSqueezeStrategy, 
    StochasticOscillatorStrategy, 
    SMACrossoverStrategy, 
    WilliamsFractalsStrategy
)


STRATEGIES = {
    "trendfollowstrategy": TrendFollowStrategy, 
    "macdcrossoverstrategy": MACDCrossoverStrategy,
    "bollingerbandsqueezestrategy": BollingerBandSqueezeStrategy,
    "stochasticoscillatorstrategy": StochasticOscillatorStrategy,
    "smacrossoverstrategy": SMACrossoverStrategy, 
    "williamsfractalsstrategy": WilliamsFractalsStrategy
}

DEFAULT_CHECK_TYPES = {
    'check_5m': True,
    'check_15m': True,
    'check_30m': True,
    'check_1h': True,
    'check_4h': True,
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", from_attributes=True)

    BOT_TOKEN: str
    ADMIN_ID: int
    SYMBOLS: str
    DATABASE_URL: str
    
    _check_types: dict[str, bool] = PrivateAttr(default_factory=lambda: DEFAULT_CHECK_TYPES.copy())

    @property
    def symbols(self):
        if not self.SYMBOLS:
            return []
        return list(self.SYMBOLS.split(","))
    
    @property
    def strategies(self) -> dict[str, Type[BaseStrategy]]:
        return STRATEGIES.copy()
    
    @property
    def check_types(self) -> dict[str, bool]:
        return self._check_types
    
    def set_check_type(self, key: str, value: bool) -> None:
        """Bitta check_type ni o'zgartirish"""
        if key in self._check_types:
            self._check_types[key] = value
    
    def update_check_types(self, data: dict[str, bool]) -> None:
        """Bir nechta check_type ni o'zgartirish"""
        for key, value in data.items():
            if key in self._check_types:
                self._check_types[key] = value
    
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings() # type: ignore
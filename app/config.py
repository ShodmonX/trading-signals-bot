from pydantic_settings import BaseSettings, SettingsConfigDict
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

check_types = {
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

    @property
    def symbols(self):
        if not self.SYMBOLS:
            return []
        return list(self.SYMBOLS.split(","))
    
    @property
    def strategies(self) -> dict[str, Type[BaseStrategy]]:
        return STRATEGIES.copy()
    
    @property
    def check_types(self):
        return check_types.copy()
    
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings() # type: ignore
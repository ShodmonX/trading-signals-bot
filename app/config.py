from dotenv import load_dotenv
import os

from .strategies import (
    # TrendFollowStrategy, MACDCrossoverStrategy, 
    # BollingerBandSqueezeStrategy, StochasticOscillatorStrategy, 
    # SMACrossoverStrategy, 
    WilliamsFractalsStrategy
)


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
SYMBOLS = list(os.getenv("SYMBOLS").split(","))
DATABASE_URL = os.getenv("DATABASE_URL")

STRATEGIES = {
    # "trendfollowstrategy": TrendFollowStrategy, 
    # "macdcrossoverstrategy": MACDCrossoverStrategy,
    # "bollingerbandsqueezestrategy": BollingerBandSqueezeStrategy,
    # "stochasticoscillatorstrategy": StochasticOscillatorStrategy,
    # "smacrossoverstrategy": SMACrossoverStrategy, 
    "williamsfractalsstrategy": WilliamsFractalsStrategy
}

check_types = {
    'check_5m': True,
    'check_15m': True,
    'check_30m': True,
    'check_1h': True,
    'check_4h': True,
}

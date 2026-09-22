import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables from .env file if available
load_dotenv()

def _get_api_key() -> str:
    return (
        os.getenv("BINANCE_API_KEY") or
        os.getenv("API Key") or
        os.getenv("API_KEY") or
        ""
    )

def _get_api_secret() -> str:
    return (
        os.getenv("BINANCE_API_SECRET") or
        os.getenv("Secret Key") or
        os.getenv("SECRET_KEY") or
        ""
    )

class AppConfig(BaseModel):
    binance_api_key: str = Field(default_factory=_get_api_key)
    binance_api_secret: str = Field(default_factory=_get_api_secret)
    binance_rest_url: str = Field(default_factory=lambda: os.getenv("BINANCE_REST_URL", "https://api.binance.com"))
    binance_ws_url: str = Field(default_factory=lambda: os.getenv("BINANCE_WS_URL", "wss://stream.binance.com:9443"))
    
    market_type: str = Field(default_factory=lambda: os.getenv("MARKET_TYPE", "spot"))
    quote_asset: str = Field(default_factory=lambda: os.getenv("QUOTE_ASSET", "USDT"))
    max_markets_to_watch: int = Field(default_factory=lambda: int(os.getenv("MAX_MARKETS_TO_WATCH", "15")))
    
    dry_run: bool = Field(default_factory=lambda: os.getenv("DRY_RUN", "true").lower() == "true")
    live_trading: bool = Field(default_factory=lambda: os.getenv("LIVE_TRADING", "false").lower() == "true")
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

config = AppConfig()

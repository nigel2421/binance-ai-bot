import os
import sys
import logging
from typing import Dict, List, Any
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

logger = logging.getLogger("Config")

def _get_api_token() -> str:
    return (
        os.getenv("DERIV_API_TOKEN") or
        os.getenv("DERIV_TOKEN") or
        ""
    ).strip()

def _get_api_secret() -> str:
    return (
        os.getenv("BINANCE_API_SECRET") or
        os.getenv("Secret Key") or
        os.getenv("SECRET_KEY") or
        ""
    )

class AppConfig(BaseModel):
    # Deriv API Configuration
    deriv_app_id: str = Field(default_factory=lambda: os.getenv("DERIV_APP_ID", "33R2Z6MTElnIWrId8aH3m"))
    deriv_api_token: str = Field(default_factory=_get_api_token)
    deriv_ws_url: str = Field(default_factory=lambda: os.getenv("DERIV_WS_URL", "wss://ws.derivws.com/websockets/v3"))
    deriv_api_base: str = Field(default_factory=lambda: os.getenv("DERIV_API_BASE", "https://api.derivws.com"))

    # Legacy/Optional Binance Fields
    binance_api_key: str = Field(default_factory=lambda: os.getenv("BINANCE_API_KEY", ""))
    binance_api_secret: str = Field(default_factory=_get_api_secret)
    binance_rest_url: str = Field(default_factory=lambda: os.getenv("BINANCE_REST_URL", "https://api.binance.com"))
    binance_ws_url: str = Field(default_factory=lambda: os.getenv("BINANCE_WS_URL", "wss://stream.binance.com:9443"))

    # Global Settings
    quote_asset: str = Field(default_factory=lambda: os.getenv("QUOTE_ASSET", "USD"))
    max_markets_to_watch: int = Field(default_factory=lambda: int(os.getenv("MAX_MARKETS_TO_WATCH", "15")))
    history_lookback_candles: int = Field(default_factory=lambda: int(os.getenv("HISTORY_LOOKBACK_CANDLES", "200")))

    # Safety Locks
    dry_run: bool = Field(default_factory=lambda: os.getenv("DRY_RUN", "true").lower() == "true")
    live_trading: bool = Field(default_factory=lambda: os.getenv("LIVE_TRADING", "false").lower() == "true")
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # Telegram Notification Credentials
    telegram_bot_token: str = Field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", "").strip())
    telegram_chat_id: str = Field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", "").strip())

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    # Stage 3 Feature & Indicator Configuration
    ema_fast: int = 9
    ema_medium: int = 21
    ema_slow: int = 50
    sma_fast: int = 20
    sma_slow: int = 200
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    atr_period: int = 14
    adx_period: int = 14
    bb_period: int = 20
    bb_std: float = 2.0
    roc_period: int = 12
    volatility_period: int = 20
    min_candles_required: int = 30

    # Multi-Timeframe Alignment Weights
    timeframe_weights: Dict[str, float] = {
        "1m": 0.10,
        "5m": 0.15,
        "15m": 0.35,
        "30m": 0.15,
        "1h": 0.15,
        "4h": 0.10
    }

    # Quarantined symbols (NO_DATA / invalid historical response on API)
    quarantined_symbols: List[str] = ["cryDOTUSD", "cryUNIUSD"]

    def verify_safety_lock(self):
        """Enforces safety lock assertion for Stage 3 development."""
        if self.live_trading or not self.dry_run:
            error_msg = (
                "\n==================================================\n"
                "CRYPTO BOT SAFETY LOCK\n"
                "Stage: Feature Engine & Market Regime Intelligence\n"
                "LIVE TRADING IS DISABLED\n"
                "\n"
                "Configuration requires DRY_RUN=true and LIVE_TRADING=false.\n"
                "==================================================\n"
            )
            logger.critical(error_msg)
            raise SystemExit(error_msg)

    def get_config_fingerprint(self) -> Dict[str, Any]:
        """Calculates deterministic SHA-256 fingerprint hash of non-sensitive config parameters."""
        import hashlib
        import json

        params = {
            "config_version": "stage6_paper_v1",
            "strategy_version": "v1.0",
            "dry_run": self.dry_run,
            "live_trading": self.live_trading,
            "max_markets_to_watch": self.max_markets_to_watch,
            "ema_fast": self.ema_fast,
            "ema_medium": self.ema_medium,
            "ema_slow": self.ema_slow,
            "sma_fast": self.sma_fast,
            "sma_slow": self.sma_slow,
            "rsi_period": self.rsi_period,
            "timeframe_weights": self.timeframe_weights,
            "quarantined_symbols": sorted(self.quarantined_symbols),
        }
        json_str = json.dumps(params, sort_keys=True)
        config_hash = hashlib.sha256(json_str.encode("utf-8")).hexdigest()[:12]
        return {
            "config_version": "stage6_paper_v1",
            "strategy_version": "v1.0",
            "config_hash": config_hash,
            "parameters": params,
        }

config = AppConfig()

import logging
from typing import Dict, Any, List, Optional
from src.api.binance_client import BinanceClient
from src.config import config

logger = logging.getLogger("BinanceMarketRegistry")

class BinanceSymbolInfo:
    def __init__(self, raw_info: Dict[str, Any]):
        self.symbol: str = raw_info["symbol"]
        self.base_asset: str = raw_info["baseAsset"]
        self.quote_asset: str = raw_info["quoteAsset"]
        self.status: str = raw_info["status"]
        self.is_spot_allowed: bool = raw_info.get("isSpotTradingAllowed", True)
        self.price_precision: int = raw_info.get("pricePrecision", 8)
        self.quantity_precision: int = raw_info.get("quantityPrecision", 8)

        # Extract filters
        self.min_qty: float = 0.0
        self.max_qty: float = 0.0
        self.step_size: float = 0.0
        self.min_price: float = 0.0
        self.max_price: float = 0.0
        self.tick_size: float = 0.0
        self.min_notional: float = 0.0

        for f in raw_info.get("filters", []):
            filter_type = f.get("filterType")
            if filter_type == "LOT_SIZE":
                self.min_qty = float(f.get("minQty", 0))
                self.max_qty = float(f.get("maxQty", 0))
                self.step_size = float(f.get("stepSize", 0))
            elif filter_type == "PRICE_FILTER":
                self.min_price = float(f.get("minPrice", 0))
                self.max_price = float(f.get("maxPrice", 0))
                self.tick_size = float(f.get("tickSize", 0))
            elif filter_type in ("MIN_NOTIONAL", "NOTIONAL"):
                self.min_notional = float(f.get("minNotional", f.get("notional", 0)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "base_asset": self.base_asset,
            "quote_asset": self.quote_asset,
            "status": self.status,
            "price_precision": self.price_precision,
            "quantity_precision": self.quantity_precision,
            "min_qty": self.min_qty,
            "step_size": self.step_size,
            "min_notional": self.min_notional,
        }

class BinanceMarketRegistry:
    """
    Dynamic discovery registry for active Binance cryptocurrency trading pairs.
    """

    def __init__(self, client: Optional[BinanceClient] = None):
        self.client = client or BinanceClient()
        self.symbols_info: Dict[str, BinanceSymbolInfo] = {}
        self.available_crypto_symbols: List[str] = []
        self.active_crypto_symbols: List[str] = []
        self.disabled_crypto_symbols: List[str] = []

    async def discover_markets(self, quote_asset: Optional[str] = None) -> List[str]:
        """Query Binance REST API for exchangeInfo and update dynamic registry."""
        target_quote = (quote_asset or config.quote_asset).upper()
        logger.info(f"Discovering active Binance crypto markets with quote asset: {target_quote}...")

        exchange_info = await self.client.get_exchange_info()
        raw_symbols = exchange_info.get("symbols", [])

        self.symbols_info.clear()
        self.available_crypto_symbols.clear()
        self.active_crypto_symbols.clear()
        self.disabled_crypto_symbols.clear()

        for s in raw_symbols:
            symbol_name = s.get("symbol", "")
            q_asset = s.get("quoteAsset", "")

            if q_asset == target_quote:
                info = BinanceSymbolInfo(s)
                self.symbols_info[symbol_name] = info
                self.available_crypto_symbols.append(symbol_name)

                if info.status == "TRADING" and info.is_spot_allowed:
                    self.active_crypto_symbols.append(symbol_name)
                else:
                    self.disabled_crypto_symbols.append(symbol_name)

        logger.info(
            f"CRYPTO MARKET DISCOVERY COMPLETED: "
            f"{len(self.available_crypto_symbols)} Discovered | "
            f"{len(self.active_crypto_symbols)} Active TRADING | "
            f"{len(self.disabled_crypto_symbols)} Disabled/Inactive"
        )
        return self.active_crypto_symbols

    def get_symbol_info(self, symbol: str) -> Optional[BinanceSymbolInfo]:
        return self.symbols_info.get(symbol.upper())

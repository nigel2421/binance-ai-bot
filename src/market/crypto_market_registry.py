import logging
from typing import Dict, Any, List, Optional, Tuple
from src.api.deriv_client import DerivClient
from src.config import config

logger = logging.getLogger("MARKET")

UNIT_SECONDS = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
    "t": 2,
}

# Standard candidate cryptocurrency symbols on Deriv
KNOWN_CRYPTO_CANDIDATES = [
    ("cryBTCUSD", "Bitcoin / USD"),
    ("cryETHUSD", "Ethereum / USD"),
    ("cryETHBTC", "Ethereum / Bitcoin"),
    ("cryLTCUSD", "Litecoin / USD"),
    ("cryXRPUSD", "Ripple / USD"),
    ("cryBCHUSD", "Bitcoin Cash / USD"),
    ("cryADAUSD", "Cardano / USD"),
    ("crySOLUSD", "Solana / USD"),
    ("cryDOTUSD", "Polkadot / USD"),
    ("cryAVAXUSD", "Avalanche / USD"),
    ("cryUNIUSD", "Uniswap / USD"),
]

class CryptoSymbolInfo:
    def __init__(self, raw: Dict[str, Any]):
        self.symbol: str = raw.get("symbol", "")
        self.display_name: str = raw.get("display_name", "")
        self.market: str = raw.get("market", "cryptocurrency")
        self.submarket: str = raw.get("submarket", "non_stable_coin")
        self.market_display_name: str = raw.get("market_display_name", "Cryptocurrency")
        self.submarket_display_name: str = raw.get("submarket_display_name", "Cryptocurrencies")
        self.is_trading_suspended: bool = bool(raw.get("is_trading_suspended", 0))
        self.exchange_is_open: bool = bool(raw.get("exchange_is_open", 1))
        self.status: str = "TRADING" if not self.is_trading_suspended and self.exchange_is_open else "CLOSED"
        
        # Explicit distinction between Market Data Capabilities and Trading Capabilities
        self.market_data_capabilities: Dict[str, Any] = {
            "tick_stream": "AVAILABLE",
            "historical_ticks": "AVAILABLE",
            "candles": "AVAILABLE",
            "available_timeframes": ["1m", "5m", "15m", "30m", "1h", "4h"],
        }
        self.trading_capabilities: Dict[str, Any] = {
            "status": "UNKNOWN",  # UNKNOWN unless confirmed from contracts_for API
            "contract_types": [],
            "min_duration": None,
            "max_duration": None,
            "barrier_requirements": None,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "display_name": self.display_name,
            "market": self.market,
            "submarket": self.submarket,
            "status": self.status,
            "market_data_capabilities": self.market_data_capabilities,
            "trading_capabilities": self.trading_capabilities,
        }

class CryptoContractCapability:
    def __init__(self, symbol: str, raw_contract: Dict[str, Any]):
        self.symbol: str = symbol
        self.contract_type: str = raw_contract.get("contract_type", "UNKNOWN")
        self.contract_category: str = raw_contract.get("contract_category", "unknown")
        self.contract_display_name: str = raw_contract.get("contract_display_name", "Unknown Contract")

        # Duration & barrier rules
        self.min_contract_duration: str = raw_contract.get("min_contract_duration", "")
        self.max_contract_duration: str = raw_contract.get("max_contract_duration", "")
        self.barrier_category: str = raw_contract.get("barrier_category", "none")
        self.barriers: int = raw_contract.get("barriers", 0)
        self.expiry_type: str = raw_contract.get("expiry_type", "")
        self.barrier_required: bool = "barrier" in raw_contract or "high_barrier" in raw_contract or self.barriers > 0
        self.raw_data: Dict[str, Any] = raw_contract

        self.min_seconds = self._to_seconds(self.min_contract_duration)
        self.max_seconds = self._to_seconds(self.max_contract_duration)

    @staticmethod
    def _to_seconds(dur_str: str) -> int:
        if not dur_str:
            return 0
        unit = dur_str[-1].lower()
        multiplier = UNIT_SECONDS.get(unit, 60)
        try:
            num = int(dur_str[:-1])
        except ValueError:
            num = 1
        return num * multiplier

class CryptoMarketRegistry:
    """
    Dynamic registry for active Deriv Cryptocurrency instruments,
    contracts_for inspection, and in-memory capability cache.
    """

    def __init__(self, client: Optional[DerivClient] = None):
        self.client = client or DerivClient()
        self.symbols_info: Dict[str, CryptoSymbolInfo] = {}
        self.available_crypto_symbols: List[str] = []
        self.active_crypto_symbols: List[str] = []
        self.quarantined_crypto_symbols: List[str] = []

        # Capability Cache: symbol -> {contract_type: CryptoContractCapability}
        self.contract_capabilities: Dict[str, Dict[str, CryptoContractCapability]] = {}

    async def discover_markets(self) -> List[str]:
        """Query active_symbols dynamically from Deriv and filter cryptocurrency instruments."""
        logger.info("[MARKET] Discovering active cryptocurrency instruments from Deriv API...")
        
        self.symbols_info.clear()
        self.available_crypto_symbols.clear()
        self.active_crypto_symbols.clear()
        self.quarantined_crypto_symbols.clear()

        # Primary attempt: active_symbols brief query
        res = await self.client.request({"active_symbols": "brief", "product_type": "basic"})
        raw_symbols = res.get("active_symbols", [])

        if not raw_symbols:
            res = await self.client.request({"active_symbols": "brief"})
            raw_symbols = res.get("active_symbols", [])

        if raw_symbols:
            for s in raw_symbols:
                m_name = str(s.get("market", "")).lower()
                sub_name = str(s.get("submarket", "")).lower()

                if m_name == "cryptocurrency" or "crypto" in sub_name or "crypto" in m_name:
                    sym_info = CryptoSymbolInfo(s)
                    symbol_name = sym_info.symbol

                    if symbol_name in config.quarantined_symbols:
                        logger.warning(f"[MARKET] Symbol {symbol_name} QUARANTINED (NO_DATA / insufficient historical depth).")
                        self.quarantined_crypto_symbols.append(symbol_name)
                        continue

                    self.symbols_info[symbol_name] = sym_info
                    self.available_crypto_symbols.append(symbol_name)
                    if sym_info.status == "TRADING":
                        self.active_crypto_symbols.append(symbol_name)
        else:
            logger.info("[MARKET] active_symbols returned empty; validating candidate crypto symbols dynamically via Deriv API...")
            for sym, display in KNOWN_CRYPTO_CANDIDATES:
                if sym in config.quarantined_symbols:
                    logger.warning(f"[MARKET] Symbol {sym} QUARANTINED by config policy.")
                    self.quarantined_crypto_symbols.append(sym)
                    continue

                try:
                    hist_res = await self.client.request({
                        "ticks_history": sym,
                        "count": 5,
                        "end": "latest"
                    })
                    if "error" not in hist_res and "history" in hist_res:
                        prices = hist_res.get("history", {}).get("prices", [])
                        if prices and len(prices) > 0:
                            sym_info = CryptoSymbolInfo({
                                "symbol": sym,
                                "display_name": display,
                                "market": "cryptocurrency",
                                "submarket": "non_stable_coin",
                            })
                            self.symbols_info[sym] = sym_info
                            self.available_crypto_symbols.append(sym)
                            self.active_crypto_symbols.append(sym)
                        else:
                            logger.warning(f"[MARKET] Symbol {sym} returned NO_DATA; quarantining.")
                            self.quarantined_crypto_symbols.append(sym)
                    else:
                        logger.warning(f"[MARKET] Symbol {sym} validation error/NO_DATA; quarantining.")
                        self.quarantined_crypto_symbols.append(sym)
                except Exception as err:
                    logger.warning(f"[MARKET] Exception validating symbol {sym}: {err}")

        logger.info(
            f"[MARKET] CRYPTO MARKET DISCOVERY SUMMARY: "
            f"Discovered={len(self.available_crypto_symbols)} | "
            f"Active (TRADING)={len(self.active_crypto_symbols)} | "
            f"Quarantined={len(self.quarantined_crypto_symbols)}"
        )
        return self.active_crypto_symbols

    async def discover_contracts_for_symbol(self, symbol: str) -> Dict[str, CryptoContractCapability]:
        """Query contracts_for API for symbol and update trading capabilities."""
        logger.info(f"[MARKET] Inspecting contracts_for symbol: {symbol}...")
        res = await self.client.request({"contracts_for": symbol})

        contracts_list = res.get("contracts_for", {}).get("available", [])
        symbol_caps = {}

        if "error" in res or not contracts_list:
            logger.info(f"[MARKET] contracts_for returned no derivative options for {symbol}. Trading capabilities marked UNKNOWN.")
            if symbol in self.symbols_info:
                self.symbols_info[symbol].trading_capabilities["status"] = "UNKNOWN"
        else:
            for c in contracts_list:
                cap = CryptoContractCapability(symbol, c)
                symbol_caps[cap.contract_type] = cap

            self.contract_capabilities[symbol] = symbol_caps
            if symbol in self.symbols_info:
                self.symbols_info[symbol].trading_capabilities.update({
                    "status": "CONFIRMED",
                    "contract_types": list(symbol_caps.keys()),
                })

        return symbol_caps

    async def discover_all_contracts(self, symbols: Optional[List[str]] = None):
        """Inspect trading capabilities for active symbols."""
        target_symbols = symbols or self.active_crypto_symbols
        for sym in target_symbols:
            await self.discover_contracts_for_symbol(sym)

    def supports(
        self,
        symbol: str,
        contract_type: str,
        duration: int = 1,
        duration_unit: str = "m"
    ) -> Tuple[bool, str]:
        """Check if symbol supports trading contract_type and duration parameters."""
        if symbol not in self.symbols_info:
            return False, f"Symbol {symbol} not recognized in crypto registry"

        sym_info = self.symbols_info[symbol]
        if sym_info.status != "TRADING":
            return False, f"Symbol {symbol} trading is currently {sym_info.status}"

        if sym_info.trading_capabilities.get("status") != "CONFIRMED":
            return False, f"Trading capabilities UNKNOWN for symbol {symbol} (contracts_for unconfirmed)"

        caps = self.contract_capabilities.get(symbol, {})
        if contract_type not in caps:
            return False, f"Contract type {contract_type} not supported for {symbol}. Available: {list(caps.keys())}"

        cap = caps[contract_type]
        unit_lower = duration_unit.lower()
        if unit_lower not in UNIT_SECONDS:
            return False, f"Invalid duration unit '{duration_unit}'"

        dur_seconds = duration * UNIT_SECONDS[unit_lower]

        if dur_seconds < cap.min_seconds or dur_seconds > cap.max_seconds:
            return False, f"Duration {duration}{duration_unit} ({dur_seconds}s) outside bounds for {symbol}:{contract_type}"

        return True, "OK"

    def generate_capability_matrix_report(self) -> Dict[str, Any]:
        """Generate structured capability matrix report for all active crypto symbols."""
        report = {}
        for sym, s_info in self.symbols_info.items():
            caps = self.contract_capabilities.get(sym, {})
            contracts_detail = []
            for c_type, c_cap in caps.items():
                contracts_detail.append({
                    "contract_type": c_type,
                    "display_name": c_cap.contract_display_name,
                    "min_duration": c_cap.min_contract_duration,
                    "max_duration": c_cap.max_contract_duration,
                    "barrier_required": c_cap.barrier_required,
                })
            
            report[sym] = {
                "symbol": sym,
                "display_name": s_info.display_name,
                "status": s_info.status,
                "market_data_capability": {
                    "historical_data": "YES",
                    "live_ticks": "YES" if s_info.status == "TRADING" else "NO",
                    "candles": "YES",
                },
                "trading_capability": {
                    "status": s_info.trading_capabilities.get("status", "UNKNOWN"),
                    "supported_contracts_count": len(contracts_detail),
                    "contracts": contracts_detail if contracts_detail else "UNKNOWN",
                }
            }
        return report

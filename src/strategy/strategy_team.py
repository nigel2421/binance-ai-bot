"""
Crypto Strategy Team Orchestrator for Deriv Crypto AI Bot Stage 4.

Coordinates 5 independent crypto strategy agents:
  1. CryptoTrendAgent
  2. CryptoMomentumAgent
  3. CryptoBreakoutAgent
  4. CryptoMeanReversionAgent
  5. CryptoStructureAgent

Responsibilities:
  - Enforces global data safety gates via watcher health checks.
  - Consults StrategyRegimeRouter for strategy eligibility.
  - Calls eligible strategies with isolated exception handling.
  - Collects generated StrategySignal objects.
  - Publishes signals to SignalBus.

CRITICAL ARCHITECTURAL BOUNDARY:
  - DOES NOT vote.
  - DOES NOT select winning signals.
  - DOES NOT trade or place contracts.
"""

import logging
import time
from typing import Dict, List, Optional, Any

from src.agents.base_strategy_agent import BaseStrategyAgent
from src.agents.crypto_trend_agent import CryptoTrendAgent
from src.agents.crypto_momentum_agent import CryptoMomentumAgent
from src.agents.crypto_breakout_agent import CryptoBreakoutAgent
from src.agents.crypto_mean_reversion_agent import CryptoMeanReversionAgent
from src.agents.crypto_structure_agent import CryptoStructureAgent

from src.strategy.signal import StrategySignal, RejectionReason
from src.strategy.regime_router import StrategyRegimeRouter
from src.strategy.signal_bus import SignalBus

logger = logging.getLogger("STRATEGY_TEAM")


class CryptoStrategyTeam:
    """
    Orchestrator for Multi-Agent Crypto Strategy Team.
    """

    def __init__(
        self,
        router: Optional[StrategyRegimeRouter] = None,
        signal_bus: Optional[SignalBus] = None,
    ):
        self.router = router or StrategyRegimeRouter()
        self.signal_bus = signal_bus or SignalBus()

        # Instantiate 5 independent strategy specialists
        self.agents: Dict[str, BaseStrategyAgent] = {
            "CryptoTrendAgent": CryptoTrendAgent(),
            "CryptoMomentumAgent": CryptoMomentumAgent(),
            "CryptoBreakoutAgent": CryptoBreakoutAgent(),
            "CryptoMeanReversionAgent": CryptoMeanReversionAgent(),
            "CryptoStructureAgent": CryptoStructureAgent(),
        }

    def evaluate_market(
        self,
        symbol: str,
        feature_snapshots: Dict[str, Dict[str, Any]],
        regime_snapshot: Dict[str, Any],
        structure_snapshot: Dict[str, Any],
        watcher_health: Dict[str, Any],
        allow_offline: bool = False,
    ) -> List[StrategySignal]:
        """
        Evaluates a single crypto market across all strategy specialists.
        Isolates exceptions so one agent failure does not crash others.
        """
        results: List[StrategySignal] = []
        overall_regime = regime_snapshot.get("overall_regime", "UNCERTAIN")
        volatility_state = regime_snapshot.get("volatility_state", "NORMAL")
        regime_conf = regime_snapshot.get("confidence", 0.0)
        mkt_quality = regime_snapshot.get("market_quality", 0.0)
        mtf_align = regime_snapshot.get("alignment", 0.0)

        # 1. Determine eligible strategies via Regime Router
        eligible_strategy_names = set(
            self.router.get_eligible_strategies(overall_regime, volatility_state)
        )

        # 2. Iterate through strategy specialists
        for agent_name, agent in self.agents.items():
            try:
                if agent_name in eligible_strategy_names:
                    # Strategy is eligible to evaluate market
                    signal = agent.evaluate(
                        symbol=symbol,
                        feature_snapshots=feature_snapshots,
                        regime_snapshot=regime_snapshot,
                        structure_snapshot=structure_snapshot,
                        watcher_health=watcher_health,
                        allow_offline=allow_offline,
                    )
                else:
                    # Strategy is routed out for this regime -> abstain with REGIME_MISMATCH
                    signal = agent.abstain(
                        symbol=symbol,
                        timeframe=agent.primary_timeframe,
                        regime=overall_regime,
                        regime_confidence=regime_conf,
                        market_quality=mkt_quality,
                        timeframe_alignment=mtf_align,
                        reason=RejectionReason.REGIME_MISMATCH,
                    )

                # Publish to SignalBus
                self.signal_bus.publish(signal)
                results.append(signal)

            except Exception as err:
                logger.error(f"[STRATEGY_TEAM][{symbol}][{agent_name}] Exception during evaluation: {err}", exc_info=True)
                # Fallback error signal
                err_signal = agent.reject(
                    symbol=symbol,
                    timeframe=agent.primary_timeframe,
                    reason=RejectionReason.STRATEGY_EXCEPTION,
                    regime=overall_regime,
                    regime_confidence=regime_conf,
                    market_quality=mkt_quality,
                    timeframe_alignment=mtf_align,
                )
                self.signal_bus.publish(err_signal)
                results.append(err_signal)

        return results

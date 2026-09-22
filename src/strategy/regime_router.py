"""
Strategy Regime Router for Deriv Crypto AI Bot Stage 4.

Determines which strategy agents are eligible to evaluate a given market regime.
Prevents strategies from evaluating unsuitable regimes (e.g. MeanReversion during STRONG_UPTREND).
Routing rules are fully configurable.
"""

import logging
from typing import Dict, List, Optional, Set

logger = logging.getLogger("REGIME_ROUTER")

# Strategy identifiers
TREND_AGENT = "CryptoTrendAgent"
MOMENTUM_AGENT = "CryptoMomentumAgent"
BREAKOUT_AGENT = "CryptoBreakoutAgent"
MEAN_REVERSION_AGENT = "CryptoMeanReversionAgent"
STRUCTURE_AGENT = "CryptoStructureAgent"

DEFAULT_ROUTING_RULES: Dict[str, List[str]] = {
    "STRONG_UPTREND": [TREND_AGENT, MOMENTUM_AGENT, STRUCTURE_AGENT],
    "UPTREND": [TREND_AGENT, MOMENTUM_AGENT, STRUCTURE_AGENT],
    "STRONG_DOWNTREND": [TREND_AGENT, MOMENTUM_AGENT, STRUCTURE_AGENT],
    "DOWNTREND": [TREND_AGENT, MOMENTUM_AGENT, STRUCTURE_AGENT],
    "RANGING": [MEAN_REVERSION_AGENT, STRUCTURE_AGENT],
    "BREAKOUT_BULLISH": [BREAKOUT_AGENT, MOMENTUM_AGENT, STRUCTURE_AGENT],
    "BREAKOUT_BEARISH": [BREAKOUT_AGENT, MOMENTUM_AGENT, STRUCTURE_AGENT],
    "LOW_VOLATILITY": [BREAKOUT_AGENT, MEAN_REVERSION_AGENT, STRUCTURE_AGENT],
    "HIGH_VOLATILITY": [MOMENTUM_AGENT, STRUCTURE_AGENT, TREND_AGENT],
    "CHOPPY": [],       # Abstain default
    "UNCERTAIN": [],    # Abstain default
    "INSUFFICIENT_DATA": [],
}


class StrategyRegimeRouter:
    """
    Regime Router managing strategy eligibility according to Stage 3 regime classification.
    """

    def __init__(self, routing_rules: Optional[Dict[str, List[str]]] = None):
        self.rules: Dict[str, List[str]] = dict(DEFAULT_ROUTING_RULES)
        if routing_rules:
            self.rules.update(routing_rules)

    def get_eligible_strategies(self, overall_regime: str, volatility_state: str = "NORMAL") -> List[str]:
        """
        Returns list of strategy names eligible to evaluate the given regime.
        """
        regime_key = str(overall_regime).upper()
        
        # Override for high volatility if regime doesn't explicitly specify
        if volatility_state.upper() == "HIGH" and regime_key not in ("STRONG_UPTREND", "STRONG_DOWNTREND"):
            eligible = set(self.rules.get("HIGH_VOLATILITY", []))
        elif volatility_state.upper() == "LOW" and regime_key not in ("STRONG_UPTREND", "STRONG_DOWNTREND", "RANGING"):
            eligible = set(self.rules.get("LOW_VOLATILITY", []))
        else:
            eligible = set(self.rules.get(regime_key, []))

        return sorted(list(eligible))

    def is_strategy_eligible(self, strategy_name: str, overall_regime: str, volatility_state: str = "NORMAL") -> bool:
        """Checks if a specific strategy is allowed for the given regime."""
        eligible = self.get_eligible_strategies(overall_regime, volatility_state)
        return strategy_name in eligible

    def update_rule(self, regime: str, strategies: List[str]):
        """Dynamically update routing rule for a regime."""
        self.rules[regime.upper()] = list(strategies)
        logger.info(f"[REGIME_ROUTER] Updated rule for {regime.upper()}: {strategies}")

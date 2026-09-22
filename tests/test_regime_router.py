"""
Unit tests for StrategyRegimeRouter.
"""

import pytest
from src.strategy.regime_router import StrategyRegimeRouter, TREND_AGENT, MEAN_REVERSION_AGENT, BREAKOUT_AGENT


def test_regime_router_eligibility():
    router = StrategyRegimeRouter()

    # 1. Uptrend eligible strategies
    uptrend_strats = router.get_eligible_strategies("UPTREND")
    assert TREND_AGENT in uptrend_strats
    assert MEAN_REVERSION_AGENT not in uptrend_strats

    # 2. Ranging eligible strategies
    ranging_strats = router.get_eligible_strategies("RANGING")
    assert MEAN_REVERSION_AGENT in ranging_strats
    assert TREND_AGENT not in ranging_strats

    # 3. Choppy regime -> empty
    choppy_strats = router.get_eligible_strategies("CHOPPY")
    assert len(choppy_strats) == 0

    # 4. Custom rule update
    router.update_rule("CHOPPY", [BREAKOUT_AGENT])
    assert router.is_strategy_eligible(BREAKOUT_AGENT, "CHOPPY")

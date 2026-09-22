"""
Offline Strategy Replay Engine for Deriv Crypto AI Bot Stage 5.

Feeds historical candle sequences through the exact same pipeline used in runtime:
Historical Candles -> FeatureEngine -> RegimeEngine -> StrategyTeam -> SignalBus -> ConsensusEngine -> OpportunityScorer -> Forward Observation.

Records forward price observation (1, 3, 5, 10, 20 bars) post-signal generation for analytical evaluation.
DOES NOT use future candles during signal/consensus generation (prevents look-ahead bias).
DOES NOT calculate trade profit or PnL.
"""

import logging
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np

from src.features.crypto_feature_engine import CryptoFeatureEngine
from src.features.market_structure import MarketStructureEngine
from src.agents.crypto_regime_agent import CryptoRegimeAgent, MultiTimeframeRegimeEngine, CryptoMarketQualityEngine
from src.strategy.strategy_team import CryptoStrategyTeam
from src.strategy.signal import StrategySignal, SignalDirection, SignalStatus
from src.consensus.crypto_consensus_engine import CryptoConsensusEngine, ConsensusDirection
from src.opportunity.crypto_opportunity_scorer import CryptoOpportunityScorer, OpportunityStatus

logger = logging.getLogger("REPLAY_ENGINE")


class StrategyReplayEngine:
    """
    Offline Strategy Replay Engine evaluating historical candle DataFrames through Stage 4 & Stage 5.
    """

    def __init__(self, strategy_team: Optional[CryptoStrategyTeam] = None):
        self.team = strategy_team or CryptoStrategyTeam()
        self.regime_agent = CryptoRegimeAgent()
        self.quality_engine = CryptoMarketQualityEngine()
        self.consensus_engine = CryptoConsensusEngine()
        self.opportunity_scorer = CryptoOpportunityScorer()

    def replay_market(
        self,
        symbol: str,
        df_15m: pd.DataFrame,
        timeframe: str = "15m",
        min_history_candles: int = 50,
        observation_bars: List[int] = [1, 3, 5, 10, 20],
    ) -> List[Dict[str, Any]]:
        """
        Replays historical 15m candle DataFrame step-by-step.
        
        At index i:
          - Only candles 0..i are passed to feature engine (strict anti-look-ahead).
          - Signals, consensus, and opportunities generated at candle i are evaluated against future candles i+1..i+K.
        """
        if df_15m.empty or len(df_15m) < min_history_candles:
            logger.warning(f"[REPLAY] Insufficient candles for {symbol}: {len(df_15m)}")
            return []

        results: List[Dict[str, Any]] = []
        total_bars = len(df_15m)

        mock_watcher_health = {
            "state": "HEALTHY",
            "seconds_since_last_tick": 0.0,
            "candles_ready": True,
        }

        for i in range(min_history_candles, total_bars):
            history_slice = df_15m.iloc[: i + 1].copy()
            current_bar = history_slice.iloc[-1]
            current_close = float(current_bar["close"])
            current_ts = float(current_bar["timestamp"])

            # 1. Features
            feature_snapshot = CryptoFeatureEngine.calculate_snapshot(history_slice, symbol, timeframe)
            feature_dict = feature_snapshot.to_dict()

            # 2. Structure
            structure_snapshot = MarketStructureEngine.analyze_structure(history_slice, symbol, timeframe)
            structure_dict = structure_snapshot.to_dict()

            # 3. Regime
            single_tf_res = self.regime_agent.classify_regime(feature_snapshot, structure_snapshot)
            mtf_res = MultiTimeframeRegimeEngine.evaluate_multitimeframe_regime(symbol, {timeframe: single_tf_res})

            feature_snapshots_map = {timeframe: feature_dict}

            # 4. Strategy Team Signals
            signals = self.team.evaluate_market(
                symbol=symbol,
                feature_snapshots=feature_snapshots_map,
                regime_snapshot=mtf_res,
                structure_snapshot=structure_dict,
                watcher_health=mock_watcher_health,
                allow_offline=True,
            )

            # 5. Consensus Engine
            consensus_res = self.consensus_engine.evaluate_consensus(
                symbol=symbol,
                signals=signals,
                regime_snapshot=mtf_res,
                timestamp=current_ts,
            )

            # 6. Opportunity Scorer
            opportunity_res = self.opportunity_scorer.evaluate_opportunity(
                consensus=consensus_res,
                watcher_health=mock_watcher_health,
                timestamp=current_ts,
            )

            # 7. Annotate forward outcomes for qualified consensus/opportunity setups
            record = {
                "bar_index": i,
                "timestamp": current_ts,
                "price": current_close,
                "signals": [s.to_dict() for s in signals],
                "consensus": consensus_res.to_dict(),
                "opportunity": opportunity_res.to_dict(),
                "forward_excursion": {},
            }

            dir_enum = SignalDirection.NEUTRAL
            if consensus_res.direction == ConsensusDirection.BULLISH:
                dir_enum = SignalDirection.BULLISH
            elif consensus_res.direction == ConsensusDirection.BEARISH:
                dir_enum = SignalDirection.BEARISH

            if opportunity_res.status in (OpportunityStatus.QUALIFIED_LIVE, OpportunityStatus.QUALIFIED_RESEARCH) and dir_enum in (SignalDirection.BULLISH, SignalDirection.BEARISH):
                forward_outcomes = self._calculate_forward_excursion(
                    df_15m=df_15m,
                    signal_index=i,
                    direction=dir_enum,
                    entry_price=current_close,
                    observation_bars=observation_bars,
                )
                record["forward_excursion"] = forward_outcomes

            results.append(record)

        return results

    def _calculate_forward_excursion(
        self,
        df_15m: pd.DataFrame,
        signal_index: int,
        direction: SignalDirection,
        entry_price: float,
        observation_bars: List[int],
    ) -> Dict[str, Any]:
        outcomes: Dict[str, Any] = {}
        total_bars = len(df_15m)

        for horizon in observation_bars:
            target_idx = signal_index + horizon
            if target_idx < total_bars:
                future_bar = df_15m.iloc[target_idx]
                future_close = float(future_bar["close"])
                pct_change = ((future_close - entry_price) / entry_price * 100.0) if entry_price > 0 else 0.0

                if direction == SignalDirection.BULLISH:
                    is_correct = pct_change > 0
                elif direction == SignalDirection.BEARISH:
                    is_correct = pct_change < 0
                else:
                    is_correct = False

                outcomes[f"return_{horizon}b_pct"] = round(pct_change, 4)
                outcomes[f"correct_{horizon}b"] = is_correct
            else:
                outcomes[f"return_{horizon}b_pct"] = None
                outcomes[f"correct_{horizon}b"] = None

        max_horizon = max(observation_bars)
        end_idx = min(total_bars, signal_index + max_horizon + 1)
        future_slice = df_15m.iloc[signal_index + 1 : end_idx]

        if not future_slice.empty:
            future_highs = future_slice["high"].values
            future_lows = future_slice["low"].values

            if direction == SignalDirection.BULLISH:
                mfe = ((np.max(future_highs) - entry_price) / entry_price * 100.0) if entry_price > 0 else 0.0
                mae = ((np.min(future_lows) - entry_price) / entry_price * 100.0) if entry_price > 0 else 0.0
            elif direction == SignalDirection.BEARISH:
                mfe = ((entry_price - np.min(future_lows)) / entry_price * 100.0) if entry_price > 0 else 0.0
                mae = ((entry_price - np.max(future_highs)) / entry_price * 100.0) if entry_price > 0 else 0.0
            else:
                mfe, mae = 0.0, 0.0

            outcomes["mfe_pct"] = round(float(mfe), 4)
            outcomes["mae_pct"] = round(float(mae), 4)

        return outcomes

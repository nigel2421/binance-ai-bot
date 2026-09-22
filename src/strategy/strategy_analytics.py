"""
Strategy Analytics for Deriv Crypto AI Bot Stage 4.

Computes evaluation statistics, candidate rates, rejection breakdowns, tier distributions,
and forward directional performance across strategies, symbols, and regimes.
"""

from collections import Counter, defaultdict
import logging
from typing import Dict, List, Any, Optional

from src.strategy.signal import StrategySignal, SignalStatus, SignalTier, RejectionReason

logger = logging.getLogger("STRATEGY_ANALYTICS")


class StrategyAnalytics:
    """
    Analytics engine summarizing strategy team activity and candidate behavior.
    """

    @staticmethod
    def compute_summary(signals: List[StrategySignal]) -> Dict[str, Any]:
        """Computes global evaluation summary across all signals."""
        if not signals:
            return {
                "total_evaluations": 0,
                "candidates": 0,
                "neutral": 0,
                "abstains": 0,
                "rejections": 0,
                "candidate_rate_pct": 0.0,
                "average_confidence": 0.0,
                "tiers": {"A": 0, "B": 0, "C": 0, "REJECT": 0},
                "top_rejection_reasons": {},
            }

        total = len(signals)
        candidates = [s for s in signals if s.status == SignalStatus.CANDIDATE]
        rejections = [s for s in signals if s.status == SignalStatus.REJECTED]
        abstains = [s for s in signals if s.status == SignalStatus.ABSTAINED]
        neutral = [s for s in signals if s.direction == "NEUTRAL"]

        confidences = [s.confidence for s in candidates] if candidates else [0.0]
        avg_conf = sum(confidences) / len(confidences)

        tier_counts = Counter(s.tier.value if hasattr(s.tier, "value") else str(s.tier) for s in signals)
        rejection_reasons = Counter(
            s.rejection_reason.value if hasattr(s.rejection_reason, "value") else str(s.rejection_reason)
            for s in signals
            if s.rejection_reason is not None
        )

        return {
            "total_evaluations": total,
            "candidates": len(candidates),
            "neutral": len(neutral),
            "abstains": len(abstains),
            "rejections": len(rejections),
            "candidate_rate_pct": round(len(candidates) / total * 100.0, 2) if total > 0 else 0.0,
            "average_confidence": round(avg_conf, 4),
            "tiers": dict(tier_counts),
            "top_rejection_reasons": dict(rejection_reasons.most_common(5)),
        }

    @staticmethod
    def compute_per_strategy_summary(signals: List[StrategySignal]) -> Dict[str, Dict[str, Any]]:
        """Computes summary metrics grouped by strategy agent name."""
        grouped: Dict[str, List[StrategySignal]] = defaultdict(list)
        for sig in signals:
            grouped[sig.strategy].append(sig)

        strategy_summaries = {}
        for strat_name, strat_signals in grouped.items():
            summary = StrategyAnalytics.compute_summary(strat_signals)
            
            # Directional distribution
            bull_cnt = sum(1 for s in strat_signals if s.direction == "BULLISH" and s.is_candidate())
            bear_cnt = sum(1 for s in strat_signals if s.direction == "BEARISH" and s.is_candidate())
            
            summary["bullish_candidates"] = bull_cnt
            summary["bearish_candidates"] = bear_cnt
            strategy_summaries[strat_name] = summary

        return strategy_summaries

    @staticmethod
    def compute_per_symbol_summary(signals: List[StrategySignal]) -> Dict[str, Dict[str, Any]]:
        """Computes summary metrics grouped by market symbol."""
        grouped: Dict[str, List[StrategySignal]] = defaultdict(list)
        for sig in signals:
            grouped[sig.symbol].append(sig)

        symbol_summaries = {}
        for symbol, sym_signals in grouped.items():
            symbol_summaries[symbol] = StrategyAnalytics.compute_summary(sym_signals)

        return symbol_summaries

    @staticmethod
    def compute_per_regime_summary(signals: List[StrategySignal]) -> Dict[str, Dict[str, Any]]:
        """Computes summary metrics grouped by market regime."""
        grouped: Dict[str, List[StrategySignal]] = defaultdict(list)
        for sig in signals:
            grouped[sig.regime].append(sig)

        regime_summaries = {}
        for regime, reg_signals in grouped.items():
            regime_summaries[regime] = StrategyAnalytics.compute_summary(reg_signals)

        return regime_summaries

    @staticmethod
    def compute_replay_outcomes_summary(replay_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Computes forward directional agreement and excursion metrics from historical replay.
        """
        candidate_results = [r for r in replay_results if r.get("signal", {}).get("status") == "CANDIDATE"]
        if not candidate_results:
            return {"candidate_count": 0, "outcomes": {}}

        total_candidates = len(candidate_results)
        bar_horizons = [1, 3, 5, 10]
        accuracy_map = {}

        for b in bar_horizons:
            key = f"correct_{b}b"
            ret_key = f"return_{b}b_pct"
            valid_b = [r for r in candidate_results if r.get("forward_excursion", {}).get(key) is not None]
            
            if valid_b:
                correct_count = sum(1 for r in valid_b if r["forward_excursion"][key] is True)
                returns = [r["forward_excursion"][ret_key] for r in valid_b if r["forward_excursion"][ret_key] is not None]
                avg_ret = sum(returns) / len(returns) if returns else 0.0
                
                accuracy_map[f"accuracy_{b}b_pct"] = round(correct_count / len(valid_b) * 100.0, 2)
                accuracy_map[f"avg_return_{b}b_pct"] = round(avg_ret, 4)

        # Average MFE / MAE
        mfes = [r["forward_excursion"]["mfe_pct"] for r in candidate_results if r.get("forward_excursion", {}).get("mfe_pct") is not None]
        maes = [r["forward_excursion"]["mae_pct"] for r in candidate_results if r.get("forward_excursion", {}).get("mae_pct") is not None]

        accuracy_map["avg_mfe_pct"] = round(sum(mfes) / len(mfes), 4) if mfes else 0.0
        accuracy_map["avg_mae_pct"] = round(sum(maes) / len(maes), 4) if maes else 0.0

        return {
            "candidate_count": total_candidates,
            "outcomes": accuracy_map,
        }

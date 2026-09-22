"""
Baseline Historical Replay Engine (baseline_v1) for Deriv Crypto AI Bot Stage 5.5.

Executes offline historical replay across 500+ evaluation windows, collecting score dynamic range
percentiles, strategy contribution statistics, forward bar outcomes (+1, +3, +5, +10, +20 bars),
and MFE/MAE measurements without tuning parameters.
"""

import asyncio
import json
import logging
import math
import numpy as np
import os
import sys
import time
from typing import Dict, List, Any, Optional

from src.config import config
from src.api.deriv_client import DerivClient
from src.market.market_data_engine import CryptoMarketDataEngine
from src.features.crypto_feature_engine import CryptoFeatureEngine
from src.features.market_structure import MarketStructureEngine
from src.agents.crypto_regime_agent import CryptoRegimeAgent, MultiTimeframeRegimeEngine, CryptoMarketQualityEngine
from src.strategy.strategy_team import CryptoStrategyTeam
from src.strategy.signal import SignalStatus, SignalDirection
from src.consensus.crypto_consensus_engine import CryptoConsensusEngine, ConsensusDirection
from src.opportunity.crypto_opportunity_scorer import CryptoOpportunityScorer

logger = logging.getLogger("BASELINE_REPLAY")


def calculate_percentiles(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"min": 0.0, "P10": 0.0, "P25": 0.0, "median": 0.0, "P75": 0.0, "P90": 0.0, "P95": 0.0, "max": 0.0}
    arr = np.array(values)
    return {
        "min": float(np.min(arr)),
        "P10": float(np.percentile(arr, 10)),
        "P25": float(np.percentile(arr, 25)),
        "median": float(np.median(arr)),
        "P75": float(np.percentile(arr, 75)),
        "P90": float(np.percentile(arr, 90)),
        "P95": float(np.percentile(arr, 95)),
        "max": float(np.max(arr)),
    }


class BaselineReplayEngine:

    def __init__(self, symbols: Optional[List[str]] = None):
        self.symbols = symbols or ["cryBTCUSD", "cryETHUSD", "cryLTCUSD", "cryXRPUSD", "cryBCHUSD", "cryADAUSD", "crySOLUSD", "cryAVAXUSD"]
        self.regime_agent = CryptoRegimeAgent()
        self.strategy_team = CryptoStrategyTeam()
        self.consensus_engine = CryptoConsensusEngine()
        self.opportunity_scorer = CryptoOpportunityScorer()

        self.recorded_observations: List[Dict[str, Any]] = []
        self.strategy_stats: Dict[str, Dict[str, int]] = {
            s: {"participated": 0, "abstained": 0, "opposed": 0, "strongest_supporter": 0}
            for s in ["CryptoTrendAgent", "CryptoMomentumAgent", "CryptoBreakoutAgent", "CryptoMeanReversionAgent", "CryptoStructureAgent"]
        }

    async def run_replay(self, target_sample_size: int = 500) -> Dict[str, Any]:
        logger.info(f"[BASELINE_REPLAY] Initializing historical replay targeting {target_sample_size}+ observations...")
        
        client = DerivClient()
        data_engine = CryptoMarketDataEngine(client=client)

        await client.connect()

        # Preload 300 candles across all timeframes per symbol
        logger.info(f"[BASELINE_REPLAY] Preloading historical candles for {len(self.symbols)} symbols...")
        await data_engine.preload_historical_candles(
            self.symbols,
            timeframes=["1m", "5m", "15m", "30m", "1h", "4h"],
            count=300
        )
        await client.disconnect()

        total_obs = 0
        score_list: List[float] = []
        consensus_conf_list: List[float] = []
        market_quality_list: List[float] = []
        alignment_list: List[float] = []
        evidence_diversity_list: List[float] = []

        # Forward outcomes tracking by score band
        score_bands = {"<50": [], "50-60": [], "60-70": [], "70+": []}

        for sym in self.symbols:
            df_15m = data_engine.get_dataframe(sym, "15m")
            if df_15m.empty or len(df_15m) < 100:
                continue

            # Sliding window over historical 15m candles
            max_idx = len(df_15m) - 25  # leave 25 bars for forward evaluation
            start_idx = 50

            for idx in range(start_idx, max_idx):
                sub_df_15m = df_15m.iloc[:idx+1].copy()
                curr_price = float(sub_df_15m.iloc[-1]["close"])
                curr_time = float(sub_df_15m.iloc[-1]["timestamp"])

                # Sub-dataframes for higher timeframes
                df_1h = data_engine.get_dataframe(sym, "1h")
                sub_df_1h = df_1h[df_1h["timestamp"] <= curr_time].copy() if not df_1h.empty else sub_df_15m
                df_4h = data_engine.get_dataframe(sym, "4h")
                sub_df_4h = df_4h[df_4h["timestamp"] <= curr_time].copy() if not df_4h.empty else sub_df_15m

                tf_snapshots = {
                    "15m": CryptoFeatureEngine.calculate_snapshot(sub_df_15m, sym, "15m").to_dict(),
                    "1h": CryptoFeatureEngine.calculate_snapshot(sub_df_1h if not sub_df_1h.empty else sub_df_15m, sym, "1h").to_dict(),
                    "4h": CryptoFeatureEngine.calculate_snapshot(sub_df_4h if not sub_df_4h.empty else sub_df_15m, sym, "4h").to_dict(),
                }

                struct_dict = MarketStructureEngine.analyze_structure(sub_df_15m, sym, "15m").to_dict()

                feat_15m = CryptoFeatureEngine.calculate_snapshot(sub_df_15m, sym, "15m")
                r15m = self.regime_agent.classify_regime(
                    feat_15m,
                    MarketStructureEngine.analyze_structure(sub_df_15m, sym, "15m")
                )
                r1h = self.regime_agent.classify_regime(
                    CryptoFeatureEngine.calculate_snapshot(sub_df_1h, sym, "1h") if not sub_df_1h.empty else feat_15m,
                    MarketStructureEngine.analyze_structure(sub_df_1h if not sub_df_1h.empty else sub_df_15m, sym, "1h")
                )
                r4h = self.regime_agent.classify_regime(
                    CryptoFeatureEngine.calculate_snapshot(sub_df_4h, sym, "4h") if not sub_df_4h.empty else feat_15m,
                    MarketStructureEngine.analyze_structure(sub_df_4h if not sub_df_4h.empty else sub_df_15m, sym, "4h")
                )

                mtf_res = MultiTimeframeRegimeEngine.evaluate_multitimeframe_regime(sym, {"15m": r15m, "1h": r1h, "4h": r4h})
                quality_score = CryptoMarketQualityEngine.calculate_quality_score(
                    feat_15m.data_quality_score, mtf_res.get("regime_confidence", 0.0), mtf_res.get("timeframe_alignment", 0.0), r15m.trend.strength
                )
                mtf_res["market_quality"] = quality_score

                # Strategy signals
                watcher_health = {
                    "state": "HISTORY_ONLY",
                    "seconds_since_last_tick": 0.0,
                    "data_recency_sec": 0.0,
                    "live_stream_freshness_sec": 99999.0,
                    "ticks_received": 0,
                    "candles_ready": True,
                    "historical_ready": True,
                    "live_stream_ready": False,
                    "features_ready": True,
                    "regime_ready": True,
                    "strategy_ready": True,
                    "consensus_ready": True,
                    "research_ready": True,
                    "live_ready": False,
                }

                signals = self.strategy_team.evaluate_market(
                    symbol=sym,
                    feature_snapshots=tf_snapshots,
                    regime_snapshot=mtf_res,
                    structure_snapshot=struct_dict,
                    watcher_health=watcher_health,
                    allow_offline=True,
                )

                consensus = self.consensus_engine.evaluate_consensus(sym, signals, mtf_res, timestamp=curr_time)
                opportunity = self.opportunity_scorer.evaluate_opportunity(consensus, watcher_health, timestamp=curr_time)

                # Record statistics
                total_obs += 1
                score_list.append(opportunity.opportunity_score)
                consensus_conf_list.append(consensus.consensus_confidence)
                market_quality_list.append(consensus.market_quality)
                alignment_list.append(consensus.timeframe_alignment)
                evidence_diversity_list.append(consensus.evidence_diversity_score)

                # Strategy contribution stats
                for sig in signals:
                    s_name = sig.strategy
                    if s_name in self.strategy_stats:
                        if sig.status == SignalStatus.CANDIDATE:
                            self.strategy_stats[s_name]["participated"] += 1
                            if consensus.strongest_supporter == s_name:
                                self.strategy_stats[s_name]["strongest_supporter"] += 1
                            if consensus.strongest_opponent == s_name:
                                self.strategy_stats[s_name]["opposed"] += 1
                        else:
                            self.strategy_stats[s_name]["abstained"] += 1

                # Forward price movement analysis (+1, +3, +5, +10, +20 bars)
                future_prices = df_15m.iloc[idx+1:idx+21]["close"].values if (idx+21) <= len(df_15m) else []
                if len(future_prices) >= 20:
                    ret_1 = (future_prices[0] - curr_price) / curr_price
                    ret_3 = (future_prices[2] - curr_price) / curr_price
                    ret_5 = (future_prices[4] - curr_price) / curr_price
                    ret_10 = (future_prices[9] - curr_price) / curr_price
                    ret_20 = (future_prices[19] - curr_price) / curr_price

                    if consensus.direction == ConsensusDirection.BEARISH:
                        ret_1, ret_3, ret_5, ret_10, ret_20 = -ret_1, -ret_3, -ret_5, -ret_10, -ret_20

                    highs = df_15m.iloc[idx+1:idx+21]["high"].values
                    lows = df_15m.iloc[idx+1:idx+21]["low"].values
                    
                    if consensus.direction == ConsensusDirection.BULLISH:
                        mfe = (np.max(highs) - curr_price) / curr_price
                        mae = (curr_price - np.min(lows)) / curr_price
                    elif consensus.direction == ConsensusDirection.BEARISH:
                        mfe = (curr_price - np.min(lows)) / curr_price
                        mae = (np.max(highs) - curr_price) / curr_price
                    else:
                        mfe = (np.max(highs) - curr_price) / curr_price
                        mae = (curr_price - np.min(lows)) / curr_price

                    fwd_rec = {
                        "ret_1": float(ret_1),
                        "ret_3": float(ret_3),
                        "ret_5": float(ret_5),
                        "ret_10": float(ret_10),
                        "ret_20": float(ret_20),
                        "mfe": float(mfe),
                        "mae": float(mae),
                    }

                    if opportunity.opportunity_score >= 70.0:
                        score_bands["70+"].append(fwd_rec)
                    elif opportunity.opportunity_score >= 60.0:
                        score_bands["60-70"].append(fwd_rec)
                    elif opportunity.opportunity_score >= 50.0:
                        score_bands["50-60"].append(fwd_rec)
                    else:
                        score_bands["<50"].append(fwd_rec)

        # Summarize score distributions
        percentiles = {
            "opportunity_score": calculate_percentiles(score_list),
            "consensus_confidence": calculate_percentiles(consensus_conf_list),
            "market_quality": calculate_percentiles(market_quality_list),
            "timeframe_alignment": calculate_percentiles(alignment_list),
            "evidence_diversity": calculate_percentiles(evidence_diversity_list),
        }

        # Summarize forward outcomes
        forward_summary = {}
        for band_name, items in score_bands.items():
            if items:
                forward_summary[band_name] = {
                    "count": len(items),
                    "avg_ret_1_pct": float(np.mean([x["ret_1"] for x in items]) * 100.0),
                    "avg_ret_5_pct": float(np.mean([x["ret_5"] for x in items]) * 100.0),
                    "avg_ret_20_pct": float(np.mean([x["ret_20"] for x in items]) * 100.0),
                    "avg_mfe_pct": float(np.mean([x["mfe"] for x in items]) * 100.0),
                    "avg_mae_pct": float(np.mean([x["mae"] for x in items]) * 100.0),
                }
            else:
                forward_summary[band_name] = {"count": 0, "avg_ret_1_pct": 0.0, "avg_ret_5_pct": 0.0, "avg_ret_20_pct": 0.0, "avg_mfe_pct": 0.0, "avg_mae_pct": 0.0}

        summary_report = {
            "replay_version": "baseline_v1",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
            "total_observations": total_obs,
            "monitored_symbols": len(self.symbols),
            "percentiles": percentiles,
            "strategy_contributions": self.strategy_stats,
            "forward_outcomes": forward_summary,
        }

        logger.info(f"[BASELINE_REPLAY] Replay completed across {total_obs} observations.")
        return summary_report


async def main_async():
    engine = BaselineReplayEngine()
    res = await engine.run_replay(target_sample_size=500)
    print("\n==========================================================")
    print("STAGE 5.5 HISTORICAL BASELINE REPLAY REPORT (baseline_v1)")
    print("==========================================================")
    print(f"Total Observations:    {res['total_observations']}")
    print("Opportunity Score Percentiles:")
    for k, v in res["percentiles"]["opportunity_score"].items():
        print(f"  {k:<8}: {v:.1f}")
    print("----------------------------------------------------------")
    print("Forward Bar Outcomes by Score Band:")
    for band, stats in res["forward_outcomes"].items():
        print(f"  Band {band:<6} | Count: {stats['count']:<4} | +5b Ret: {stats['avg_ret_5_pct']:+.2f}% | MFE: {stats['avg_mfe_pct']:.2f}% | MAE: {stats['avg_mae_pct']:.2f}%")
    print("==========================================================\n")

    # Save snapshot json
    os.makedirs("artifacts", exist_ok=True)
    with open("config/baseline_v1_results.json", "w") as f:
        json.dump(res, f, indent=2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main_async())

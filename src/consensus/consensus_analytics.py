"""
Consensus & Opportunity Analytics for Deriv Crypto AI Bot Stage 5.

Performs empirical calibration analytics:
  - Score Band Calibration (50-59, 60-69, 70-79, 80-89, 90-100)
  - Consensus Strength Calibration (VERY_STRONG, STRONG, MODERATE, WEAK, SINGLE_SPECIALIST)
  - Strategy Combination Analytics
"""

from collections import defaultdict, Counter
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("CONSENSUS_ANALYTICS")


class ConsensusAnalytics:
    """
    Analytics engine evaluating consensus calibration and empirical opportunity score performance.
    """

    @staticmethod
    def compute_score_band_calibration(replay_opportunities: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Groups forward observation outcomes by opportunity score bands:
        50-59, 60-69, 70-79, 80-89, 90-100.
        """
        bands = {
            "50-59": [],
            "60-69": [],
            "70-79": [],
            "80-89": [],
            "90-100": [],
        }

        for item in replay_opportunities:
            op = item.get("opportunity", {})
            score = op.get("opportunity_score", 0.0)
            fwd = item.get("forward_excursion", {})

            if score >= 90:
                bands["90-100"].append(fwd)
            elif score >= 80:
                bands["80-89"].append(fwd)
            elif score >= 70:
                bands["70-79"].append(fwd)
            elif score >= 60:
                bands["60-69"].append(fwd)
            elif score >= 50:
                bands["50-59"].append(fwd)

        results = {}
        for band_name, fwd_list in bands.items():
            results[band_name] = ConsensusAnalytics._summarize_fwd_list(fwd_list)

        return results

    @staticmethod
    def compute_strength_calibration(replay_opportunities: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Groups forward observation outcomes by consensus strength:
        VERY_STRONG, STRONG, MODERATE, WEAK, SINGLE_SPECIALIST.
        """
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for item in replay_opportunities:
            strength = item.get("consensus", {}).get("consensus_strength", "NONE")
            fwd = item.get("forward_excursion", {})
            grouped[strength].append(fwd)

        results = {}
        for strength_name, fwd_list in grouped.items():
            results[strength_name] = ConsensusAnalytics._summarize_fwd_list(fwd_list)

        return results

    @staticmethod
    def _summarize_fwd_list(fwd_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not fwd_list:
            return {"sample_count": 0, "accuracy_1b_pct": 0.0, "accuracy_5b_pct": 0.0, "avg_mfe_pct": 0.0, "avg_mae_pct": 0.0}

        count = len(fwd_list)
        horizons = [1, 3, 5, 10, 20]
        acc_map = {"sample_count": count}

        for h in horizons:
            key = f"correct_{h}b"
            ret_key = f"return_{h}b_pct"
            valid = [f for f in fwd_list if f.get(key) is not None]
            if valid:
                correct = sum(1 for f in valid if f[key] is True)
                rets = [f[ret_key] for f in valid if f.get(ret_key) is not None]
                acc_map[f"accuracy_{h}b_pct"] = round(correct / len(valid) * 100.0, 2)
                acc_map[f"avg_return_{h}b_pct"] = round(sum(rets) / len(rets), 4) if rets else 0.0

        mfes = [f["mfe_pct"] for f in fwd_list if f.get("mfe_pct") is not None]
        maes = [f["mae_pct"] for f in fwd_list if f.get("mae_pct") is not None]
        acc_map["avg_mfe_pct"] = round(sum(mfes) / len(mfes), 4) if mfes else 0.0
        acc_map["avg_mae_pct"] = round(sum(maes) / len(maes), 4) if maes else 0.0

        return acc_map

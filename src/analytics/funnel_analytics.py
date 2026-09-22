"""
Trade Funnel & Rejection Analytics Engine for Deriv Crypto AI Bot Stage 7.

Instruments the 9-stage paper trade funnel and provides rejection gate frequency analysis
to identify over-filtering or systemic trade drop-offs globally and per symbol.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import logging

from src.execution.trade_journal import JournalRecord

logger = logging.getLogger("FUNNEL_ANALYTICS")


@dataclass
class FunnelStageMetrics:
    stage_name: str
    count: int = 0
    conversion_from_previous_pct: float = 0.0
    conversion_from_total_pct: float = 0.0


@dataclass
class RejectionGateSummary:
    gate_name: str
    rejection_count: int = 0
    share_of_rejections_pct: float = 0.0


@dataclass
class TradeFunnelReport:
    total_evaluations: int = 0
    total_rejections: int = 0
    stage_metrics: Dict[str, FunnelStageMetrics] = field(default_factory=dict)
    rejection_gates: List[RejectionGateSummary] = field(default_factory=list)


class TradeFunnelAnalytics:
    """
    Analyzes trade funnel conversion efficiency and ranks rejection gate bottlenecks.
    """

    REJECTION_GATE_MAP = {
        "NOT_LIVE_READY": "NOT_LIVE_READY",
        "LOW_OPPORTUNITY_SCORE": "LOW_OPPORTUNITY_SCORE",
        "CONFLICTED_DIRECTION": "CONFLICTED_DIRECTION",
        "CONTRACT_UNAVAILABLE": "CONTRACT_UNSUPPORTED",
        "PROPOSAL_FAILED": "PROPOSAL_FAILED",
        "UNCALIBRATED": "CALIBRATION_INSUFFICIENT",
        "NEGATIVE_EV": "NEGATIVE_EV",
        "RISK_REJECTED": "RISK_REJECT",
    }

    FUNNEL_STAGES = [
        "1_detected",
        "2_qualified",
        "3_contract_supported",
        "4_proposal_received",
        "5_calibrated",
        "6_positive_ev",
        "7_risk_approved",
        "8_paper_opened",
        "9_settled",
    ]

    @classmethod
    def analyze_funnel(
        cls,
        records: List[JournalRecord],
        symbol_filter: Optional[str] = None,
    ) -> TradeFunnelReport:
        if symbol_filter:
            records = [r for r in records if r.symbol == symbol_filter]

        if not records:
            return TradeFunnelReport()

        total_evaluations = len(records)
        rejection_records = [r for r in records if r.record_type == "REJECTION" or r.status == "REJECTED"]
        paper_records = [r for r in records if r.record_type == "PAPER_TRADE"]
        settled_records = [r for r in paper_records if r.status in ("WON", "LOST", "PUSH")]

        # Count funnel stages based on rejection stage audit
        rej_stage_counts: Dict[str, int] = {}
        for r in rejection_records:
            stg = r.rejection_stage or "UNKNOWN"
            gate = cls.REJECTION_GATE_MAP.get(stg, stg)
            rej_stage_counts[gate] = rej_stage_counts.get(gate, 0) + 1

        # Calculate cumulative funnel counts
        # Stage 1: Detected = Total evaluations
        c1 = total_evaluations
        # Stage 2: Qualified (passed NOT_LIVE_READY & LOW_OPPORTUNITY_SCORE)
        drop_s1 = rej_stage_counts.get("NOT_LIVE_READY", 0) + rej_stage_counts.get("LOW_OPPORTUNITY_SCORE", 0) + rej_stage_counts.get("CONFLICTED_DIRECTION", 0)
        c2 = max(0, c1 - drop_s1)
        # Stage 3: Contract Supported
        drop_s2 = rej_stage_counts.get("CONTRACT_UNSUPPORTED", 0)
        c3 = max(0, c2 - drop_s2)
        # Stage 4: Proposal Received
        drop_s3 = rej_stage_counts.get("PROPOSAL_FAILED", 0)
        c4 = max(0, c3 - drop_s3)
        # Stage 5: Calibrated
        drop_s4 = rej_stage_counts.get("CALIBRATION_INSUFFICIENT", 0)
        c5 = max(0, c4 - drop_s4)
        # Stage 6: Positive EV
        drop_s5 = rej_stage_counts.get("NEGATIVE_EV", 0)
        c6 = max(0, c5 - drop_s5)
        # Stage 7: Risk Approved
        drop_s6 = rej_stage_counts.get("RISK_REJECT", 0)
        c7 = max(0, c6 - drop_s6)
        # Stage 8: Paper Opened
        c8 = len(paper_records)
        # Stage 9: Settled
        c9 = len(settled_records)

        counts = [c1, c2, c3, c4, c5, c6, c7, c8, c9]
        stage_metrics = {}

        for idx, stage_name in enumerate(cls.FUNNEL_STAGES):
            cnt = counts[idx]
            prev_cnt = counts[idx - 1] if idx > 0 else cnt
            conv_prev = (cnt / prev_cnt * 100.0) if prev_cnt > 0 else 0.0
            conv_total = (cnt / total_evaluations * 100.0) if total_evaluations > 0 else 0.0

            stage_metrics[stage_name] = FunnelStageMetrics(
                stage_name=stage_name,
                count=cnt,
                conversion_from_previous_pct=round(conv_prev, 2),
                conversion_from_total_pct=round(conv_total, 2),
            )

        # Ranked Rejection Gates
        total_rejections = len(rejection_records)
        rejection_gates = []
        for gate_name, cnt in sorted(rej_stage_counts.items(), key=lambda x: x[1], reverse=True):
            share = (cnt / total_rejections * 100.0) if total_rejections > 0 else 0.0
            rejection_gates.append(RejectionGateSummary(
                gate_name=gate_name,
                rejection_count=cnt,
                share_of_rejections_pct=round(share, 2),
            ))

        return TradeFunnelReport(
            total_evaluations=total_evaluations,
            total_rejections=total_rejections,
            stage_metrics=stage_metrics,
            rejection_gates=rejection_gates,
        )

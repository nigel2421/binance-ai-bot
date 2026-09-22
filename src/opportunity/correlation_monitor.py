"""
Crypto Correlation Monitor for Deriv Crypto AI Bot Stage 5.

Calculates rolling return correlation matrix across monitored crypto symbols to track market clustering.
RESEARCH ONLY — does not block opportunities.
"""

import logging
from typing import Dict, List, Tuple, Any
import numpy as np
import pandas as pd

logger = logging.getLogger("CORRELATION_MONITOR")


class CryptoCorrelationMonitor:
    """
    Monitors rolling return correlations across crypto markets.
    """

    @staticmethod
    def calculate_correlation_matrix(price_series_map: Dict[str, pd.Series]) -> pd.DataFrame:
        """
        Calculates Pearson correlation matrix of percentage returns across symbols.
        price_series_map: Dict[symbol, pd.Series of close prices]
        """
        if not price_series_map or len(price_series_map) < 2:
            return pd.DataFrame()

        returns_df = pd.DataFrame()
        for sym, series in price_series_map.items():
            if not series.empty and len(series) > 5:
                returns_df[sym] = series.pct_change()

        if returns_df.empty:
            return pd.DataFrame()

        return returns_df.corr().fillna(0.0)

    @staticmethod
    def find_high_correlation_pairs(corr_matrix: pd.DataFrame, threshold: float = 0.80) -> List[Tuple[str, str, float]]:
        """Identifies pairs of symbols with correlation >= threshold."""
        if corr_matrix.empty:
            return []

        high_corr_pairs = []
        symbols = corr_matrix.columns
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                sym1 = symbols[i]
                sym2 = symbols[j]
                val = float(corr_matrix.iloc[i, j])
                if abs(val) >= threshold:
                    high_corr_pairs.append((sym1, sym2, round(val, 4)))

        high_corr_pairs.sort(key=lambda x: abs(x[2]), reverse=True)
        return high_corr_pairs

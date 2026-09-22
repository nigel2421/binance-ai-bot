"""
Unit tests for CryptoCorrelationMonitor.
"""

import pytest
import pandas as pd
import numpy as np

from src.opportunity.correlation_monitor import CryptoCorrelationMonitor


def test_correlation_matrix_calculation():
    s1 = pd.Series([100 + i * 2.0 for i in range(50)])
    s2 = pd.Series([200 + i * 4.0 for i in range(50)])  # perfect positive correlation
    s3 = pd.Series([300 - i * 3.0 for i in range(50)])  # negative correlation

    price_map = {"BTC": s1, "ETH": s2, "DOGE": s3}
    corr_df = CryptoCorrelationMonitor.calculate_correlation_matrix(price_map)

    assert not corr_df.empty
    assert corr_df.loc["BTC", "ETH"] > 0.95

    high_pairs = CryptoCorrelationMonitor.find_high_correlation_pairs(corr_df, threshold=0.80)
    assert len(high_pairs) >= 1
    assert high_pairs[0][0] in ("BTC", "ETH")

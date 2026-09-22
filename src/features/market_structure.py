import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger("STRUCTURE")

class MarketStructureSnapshot:
    """
    Normalized snapshot representing market structural state, support/resistance levels,
    and swing point characteristics for a single symbol and timeframe.
    """

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        structure_state: str = "UNCLEAR_STRUCTURE",
        support_level: float = 0.0,
        resistance_level: float = 0.0,
        local_swing_high: float = 0.0,
        local_swing_low: float = 0.0,
        higher_highs_count: int = 0,
        higher_lows_count: int = 0,
        lower_highs_count: int = 0,
        lower_lows_count: int = 0
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.structure_state = structure_state
        self.support_level = float(support_level)
        self.resistance_level = float(resistance_level)
        self.local_swing_high = float(local_swing_high)
        self.local_swing_low = float(local_swing_low)
        self.higher_highs_count = int(higher_highs_count)
        self.higher_lows_count = int(higher_lows_count)
        self.lower_highs_count = int(lower_highs_count)
        self.lower_lows_count = int(lower_lows_count)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "structure_state": self.structure_state,
            "support_level": round(self.support_level, 4),
            "resistance_level": round(self.resistance_level, 4),
            "local_swing_high": round(self.local_swing_high, 4),
            "local_swing_low": round(self.local_swing_low, 4),
            "higher_highs_count": self.higher_highs_count,
            "higher_lows_count": self.higher_lows_count,
            "lower_highs_count": self.lower_highs_count,
            "lower_lows_count": self.lower_lows_count,
        }

class MarketStructureEngine:
    """
    Market Structure Engine detecting swing highs/lows, support/resistance approximations,
    and structural trend states (BULLISH_STRUCTURE, BEARISH_STRUCTURE, RANGING_STRUCTURE, UNCLEAR_STRUCTURE).
    """

    @staticmethod
    def analyze_structure(df: pd.DataFrame, symbol: str, timeframe: str) -> MarketStructureSnapshot:
        if df.empty or len(df) < 10:
            return MarketStructureSnapshot(symbol=symbol, timeframe=timeframe)

        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        curr_price = float(closes[-1])

        # 1. Swing points detection using local window extrema
        window = min(15, len(df))
        recent_highs = highs[-window:]
        recent_lows = lows[-window:]

        local_swing_high = float(np.max(recent_highs))
        local_swing_low = float(np.min(recent_lows))

        # 2. Support and Resistance Approximations
        resistance_level = local_swing_high
        support_level = local_swing_low

        # 3. Higher Highs / Higher Lows / Lower Highs / Lower Lows sequence analysis
        hh_count = 0
        hl_count = 0
        lh_count = 0
        ll_count = 0

        lookback = min(10, len(df) - 1)
        for i in range(len(df) - lookback, len(df)):
            if highs[i] > highs[i - 1]:
                hh_count += 1
            elif highs[i] < highs[i - 1]:
                lh_count += 1

            if lows[i] > lows[i - 1]:
                hl_count += 1
            elif lows[i] < lows[i - 1]:
                ll_count += 1

        # 4. Classify Structural State
        if (hh_count + hl_count) >= 6 and (hh_count > lh_count) and (hl_count > ll_count):
            state = "BULLISH_STRUCTURE"
        elif (lh_count + ll_count) >= 6 and (lh_count > hh_count) and (ll_count > hl_count):
            state = "BEARISH_STRUCTURE"
        elif abs(hh_count - lh_count) <= 2 and abs(hl_count - ll_count) <= 2:
            # Check price range compression
            price_range_pct = ((local_swing_high - local_swing_low) / curr_price * 100.0) if curr_price > 0 else 0.0
            if price_range_pct < 3.0:
                state = "RANGING_STRUCTURE"
            else:
                state = "UNCLEAR_STRUCTURE"
        else:
            state = "UNCLEAR_STRUCTURE"

        return MarketStructureSnapshot(
            symbol=symbol,
            timeframe=timeframe,
            structure_state=state,
            support_level=support_level,
            resistance_level=resistance_level,
            local_swing_high=local_swing_high,
            local_swing_low=local_swing_low,
            higher_highs_count=hh_count,
            higher_lows_count=hl_count,
            lower_highs_count=lh_count,
            lower_lows_count=ll_count
        )

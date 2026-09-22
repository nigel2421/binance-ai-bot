import logging
import math
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.config import config

logger = logging.getLogger("FEATURES")

class MarketFeatureSnapshot:
    """
    Normalized feature snapshot for a single symbol and timeframe.
    """

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        timestamp: int,
        price: float,
        ema_fast: float = 0.0,
        ema_medium: float = 0.0,
        ema_slow: float = 0.0,
        sma_fast: float = 0.0,
        sma_slow: float = 0.0,
        rsi: float = 50.0,
        macd: float = 0.0,
        macd_signal: float = 0.0,
        macd_histogram: float = 0.0,
        atr: float = 0.0,
        atr_percent: float = 0.0,
        bollinger_upper: float = 0.0,
        bollinger_middle: float = 0.0,
        bollinger_lower: float = 0.0,
        bollinger_width: float = 0.0,
        bollinger_position: float = 0.5,
        adx: float = 0.0,
        plus_di: float = 0.0,
        minus_di: float = 0.0,
        roc: float = 0.0,
        trend_slope: float = 0.0,
        distance_from_fast_ema: float = 0.0,
        distance_from_slow_ema: float = 0.0,
        higher_highs: int = 0,
        higher_lows: int = 0,
        lower_highs: int = 0,
        lower_lows: int = 0,
        rolling_volatility: float = 0.0,
        data_quality_score: float = 0.0,
        candles_used: int = 0,
        is_ready: bool = False
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.timestamp = int(timestamp)
        self.price = float(price)

        self.ema_fast = float(ema_fast)
        self.ema_medium = float(ema_medium)
        self.ema_slow = float(ema_slow)
        self.sma_fast = float(sma_fast)
        self.sma_slow = float(sma_slow)

        self.rsi = float(rsi)
        self.macd = float(macd)
        self.macd_signal = float(macd_signal)
        self.macd_histogram = float(macd_histogram)

        self.atr = float(atr)
        self.atr_percent = float(atr_percent)

        self.bollinger_upper = float(bollinger_upper)
        self.bollinger_middle = float(bollinger_middle)
        self.bollinger_lower = float(bollinger_lower)
        self.bollinger_width = float(bollinger_width)
        self.bollinger_position = float(bollinger_position)

        self.adx = float(adx)
        self.plus_di = float(plus_di)
        self.minus_di = float(minus_di)

        self.roc = float(roc)
        self.trend_slope = float(trend_slope)
        self.distance_from_fast_ema = float(distance_from_fast_ema)
        self.distance_from_slow_ema = float(distance_from_slow_ema)

        self.higher_highs = int(higher_highs)
        self.higher_lows = int(higher_lows)
        self.lower_highs = int(lower_highs)
        self.lower_lows = int(lower_lows)

        self.rolling_volatility = float(rolling_volatility)
        self.data_quality_score = float(data_quality_score)
        self.candles_used = int(candles_used)
        self.is_ready = bool(is_ready)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp,
            "price": self.price,
            "ema_fast": round(self.ema_fast, 4),
            "ema_medium": round(self.ema_medium, 4),
            "ema_slow": round(self.ema_slow, 4),
            "sma_fast": round(self.sma_fast, 4),
            "sma_slow": round(self.sma_slow, 4),
            "rsi": round(self.rsi, 2),
            "macd": round(self.macd, 4),
            "macd_signal": round(self.macd_signal, 4),
            "macd_histogram": round(self.macd_histogram, 4),
            "atr": round(self.atr, 4),
            "atr_percent": round(self.atr_percent, 2),
            "bollinger_upper": round(self.bollinger_upper, 4),
            "bollinger_middle": round(self.bollinger_middle, 4),
            "bollinger_lower": round(self.bollinger_lower, 4),
            "bollinger_width": round(self.bollinger_width, 4),
            "bollinger_position": round(self.bollinger_position, 2),
            "adx": round(self.adx, 2),
            "plus_di": round(self.plus_di, 2),
            "minus_di": round(self.minus_di, 2),
            "roc": round(self.roc, 2),
            "trend_slope": round(self.trend_slope, 4),
            "distance_from_fast_ema": round(self.distance_from_fast_ema, 2),
            "distance_from_slow_ema": round(self.distance_from_slow_ema, 2),
            "higher_highs": self.higher_highs,
            "higher_lows": self.higher_lows,
            "lower_highs": self.lower_highs,
            "lower_lows": self.lower_lows,
            "rolling_volatility": round(self.rolling_volatility, 4),
            "data_quality_score": round(self.data_quality_score, 1),
            "candles_used": self.candles_used,
            "is_ready": self.is_ready,
        }

class CryptoFeatureEngine:
    """
    Engine calculating technical indicators, feature snapshots, and data quality scores
    using pure Python / NumPy / Pandas without external binary dependencies.
    """

    @staticmethod
    def verify_data_quality(df: pd.DataFrame) -> Tuple[float, List[str]]:
        """
        Verify OHLC candle integrity, timestamp ordering, and NaN presence.
        Returns (score_0_to_100, list_of_issues).
        """
        if df.empty:
            return 0.0, ["DataFrame is empty"]

        issues = []
        score = 100.0

        # 1. Minimum candle depth check
        if len(df) < config.min_candles_required:
            issues.append(f"Insufficient candles: {len(df)} < {config.min_candles_required}")
            score -= 30.0

        # 2. Strict timestamp ordering check
        if "timestamp" in df.columns:
            ts_diffs = np.diff(df["timestamp"].values)
            if np.any(ts_diffs <= 0):
                issues.append("Non-increasing or duplicate timestamps detected")
                score -= 25.0

        # 3. OHLC boundary consistency checks
        # high >= open, high >= close, low <= open, low <= close, high >= low
        invalid_high_open = (df["high"] < df["open"]).sum()
        invalid_high_close = (df["high"] < df["close"]).sum()
        invalid_low_open = (df["low"] > df["open"]).sum()
        invalid_low_close = (df["low"] > df["close"]).sum()
        invalid_high_low = (df["high"] < df["low"]).sum()

        total_invalid = invalid_high_open + invalid_high_close + invalid_low_open + invalid_low_close + invalid_high_low
        if total_invalid > 0:
            issues.append(f"OHLC price boundary violations: {total_invalid} instances")
            score -= min(40.0, total_invalid * 10.0)

        # 4. Null / NaN checks
        nan_count = df[["open", "high", "low", "close"]].isna().sum().sum()
        if nan_count > 0:
            issues.append(f"NaN values in OHLC data: {nan_count}")
            score -= min(30.0, nan_count * 15.0)

        return max(0.0, min(100.0, score)), issues

    @classmethod
    def calculate_snapshot(cls, df: pd.DataFrame, symbol: str, timeframe: str) -> MarketFeatureSnapshot:
        """
        Calculate complete feature snapshot for symbol and timeframe from candle DataFrame.
        """
        score, issues = cls.verify_data_quality(df)

        if len(df) < 5 or score < 20.0:
            last_price = float(df.iloc[-1]["close"]) if not df.empty else 0.0
            last_time = int(df.iloc[-1]["timestamp"]) if not df.empty else 0
            return MarketFeatureSnapshot(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=last_time,
                price=last_price,
                data_quality_score=score,
                candles_used=len(df),
                is_ready=False
            )

        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)

        last_idx = len(df) - 1
        current_price = float(close.iloc[last_idx])
        current_ts = int(df.iloc[last_idx]["timestamp"])

        # 1. Moving Averages
        ema_fast = float(close.ewm(span=min(config.ema_fast, len(df)), adjust=False).mean().iloc[last_idx])
        ema_medium = float(close.ewm(span=min(config.ema_medium, len(df)), adjust=False).mean().iloc[last_idx])
        ema_slow = float(close.ewm(span=min(config.ema_slow, len(df)), adjust=False).mean().iloc[last_idx])

        sma_fast_series = close.rolling(window=min(config.sma_fast, len(df)), min_periods=1).mean()
        sma_slow_series = close.rolling(window=min(config.sma_slow, len(df)), min_periods=1).mean()

        sma_fast = float(sma_fast_series.iloc[last_idx])
        sma_slow = float(sma_slow_series.iloc[last_idx])

        # 2. RSI (14)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0.0)).rolling(window=config.rsi_period, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(window=config.rsi_period, min_periods=1).mean()

        last_loss = loss.iloc[last_idx]
        last_gain = gain.iloc[last_idx]
        if last_loss == 0:
            rsi = 100.0 if last_gain > 0 else 50.0
        else:
            rs = last_gain / last_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))

        # 3. MACD (12, 26, 9)
        macd_series = close.ewm(span=config.macd_fast, adjust=False).mean() - close.ewm(span=config.macd_slow, adjust=False).mean()
        macd_signal_series = macd_series.ewm(span=config.macd_signal, adjust=False).mean()
        macd_hist_series = macd_series - macd_signal_series

        macd = float(macd_series.iloc[last_idx])
        macd_signal = float(macd_signal_series.iloc[last_idx])
        macd_histogram = float(macd_hist_series.iloc[last_idx])

        # 4. ATR & ATR %
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_series = tr.rolling(window=config.atr_period, min_periods=1).mean()

        atr = float(atr_series.iloc[last_idx])
        atr_percent = (atr / current_price * 100.0) if current_price > 0 else 0.0

        # 5. Bollinger Bands (20, 2 std)
        bb_mid = close.rolling(window=config.bb_period, min_periods=1).mean()
        bb_std = close.rolling(window=config.bb_period, min_periods=1).std().fillna(0.0)

        b_middle = float(bb_mid.iloc[last_idx])
        b_std_val = float(bb_std.iloc[last_idx])
        b_upper = b_middle + (config.bb_std * b_std_val)
        b_lower = b_middle - (config.bb_std * b_std_val)

        b_width = ((b_upper - b_lower) / b_middle) if b_middle > 0 else 0.0
        b_pos = ((current_price - b_lower) / (b_upper - b_lower)) if (b_upper - b_lower) > 0 else 0.5

        # 6. ADX (14)
        up_move = high.diff()
        down_move = -low.diff()

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        tr_smooth = tr.rolling(window=config.adx_period, min_periods=1).sum()
        p_dm_smooth = pd.Series(plus_dm).rolling(window=config.adx_period, min_periods=1).sum()
        m_dm_smooth = pd.Series(minus_dm).rolling(window=config.adx_period, min_periods=1).sum()

        p_di = (p_dm_smooth / tr_smooth * 100.0).fillna(0.0)
        m_di = (m_dm_smooth / tr_smooth * 100.0).fillna(0.0)

        di_diff = (p_di - m_di).abs()
        di_sum = (p_di + m_di).replace(0, 1.0)
        dx = (di_diff / di_sum) * 100.0
        adx_series = dx.rolling(window=config.adx_period, min_periods=1).mean()

        adx = float(adx_series.iloc[last_idx]) if not adx_series.empty else 0.0
        plus_di = float(p_di.iloc[last_idx]) if not p_di.empty else 0.0
        minus_di = float(m_di.iloc[last_idx]) if not m_di.empty else 0.0

        # 7. Rate of Change (ROC 12)
        roc_period = min(config.roc_period, len(df) - 1)
        prev_p = float(close.iloc[last_idx - roc_period]) if last_idx >= roc_period else float(close.iloc[0])
        roc = ((current_price - prev_p) / prev_p * 100.0) if prev_p > 0 else 0.0

        # 8. Trend slope & Distance from EMAs
        slope_window = min(10, len(df))
        y = close.iloc[-slope_window:].values
        x = np.arange(len(y))
        if len(y) > 1:
            slope, _ = np.polyfit(x, y, 1)
            trend_slope = float(slope / current_price * 100.0) if current_price > 0 else 0.0
        else:
            trend_slope = 0.0

        dist_fast = ((current_price - ema_fast) / ema_fast * 100.0) if ema_fast > 0 else 0.0
        dist_slow = ((current_price - ema_slow) / ema_slow * 100.0) if ema_slow > 0 else 0.0

        # 9. Structure Counts (higher highs/lows, lower highs/lows)
        window = min(10, len(df) - 1)
        sub_highs = high.iloc[-window:].values
        sub_lows = low.iloc[-window:].values

        hh = int(np.sum(np.diff(sub_highs) > 0))
        lh = int(np.sum(np.diff(sub_highs) < 0))
        hl = int(np.sum(np.diff(sub_lows) > 0))
        ll = int(np.sum(np.diff(sub_lows) < 0))

        # 10. Rolling Volatility
        pct_returns = close.pct_change().dropna()
        roll_vol = float(pct_returns.tail(config.volatility_period).std() * 100.0) if len(pct_returns) > 0 else 0.0

        is_ready = (len(df) >= config.min_candles_required) and (score >= 50.0)

        return MarketFeatureSnapshot(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=current_ts,
            price=current_price,
            ema_fast=ema_fast,
            ema_medium=ema_medium,
            ema_slow=ema_slow,
            sma_fast=sma_fast,
            sma_slow=sma_slow,
            rsi=rsi,
            macd=macd,
            macd_signal=macd_signal,
            macd_histogram=macd_histogram,
            atr=atr,
            atr_percent=atr_percent,
            bollinger_upper=b_upper,
            bollinger_middle=b_middle,
            bollinger_lower=b_lower,
            bollinger_width=b_width,
            bollinger_position=b_pos,
            adx=adx,
            plus_di=plus_di,
            minus_di=minus_di,
            roc=roc,
            trend_slope=trend_slope,
            distance_from_fast_ema=dist_fast,
            distance_from_slow_ema=dist_slow,
            higher_highs=hh,
            higher_lows=hl,
            lower_highs=lh,
            lower_lows=ll,
            rolling_volatility=roll_vol,
            data_quality_score=score,
            candles_used=len(df),
            is_ready=is_ready
        )

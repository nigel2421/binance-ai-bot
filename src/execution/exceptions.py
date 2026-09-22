"""
Custom Execution Exceptions for Deriv Crypto AI Bot Stage 6.
"""

class LiveTradingSafetyViolation(Exception):
    """
    Raised when live contract purchase or sell execution is attempted while safety lock is active
    (DRY_RUN=true or LIVE_TRADING=false).
    """
    pass

class ProposalError(Exception):
    """Raised when proposal pricing request fails or returns an error."""
    pass

class CalibrationError(Exception):
    """Raised when probability calibration fails or sample size is insufficient."""
    pass

class RiskViolationError(Exception):
    """Raised when risk manager rejects a trade candidate."""
    pass

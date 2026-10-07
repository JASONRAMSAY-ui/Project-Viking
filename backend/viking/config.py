"""All tunable thresholds from the specification live here, in one place."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScreenConfig:
    min_adv_usd: float = 20_000_000.0
    adv_window: int = 30
    max_option_spread: float = 0.05  # near-the-money bid/ask width: dollars/share, or fraction of mid if spread_relative
    spread_relative: bool = False
    hv_short: int = 20
    hv_long: int = 90
    hv_explosion_ratio: float = 1.5
    adx_period: int = 14
    adx_max: float = 22.0
    adx_slope_sessions: int = 3
    squeeze_std_window: int = 10
    squeeze_atr_period: int = 14
    squeeze_atr_sma: int = 50
    min_bis: int = 4
    bis_std_haircut: float = 0.5


@dataclass(frozen=True)
class OptimizerConfig:
    base_delta: float = 0.20
    max_short_delta: float = 0.25
    min_pop: float = 0.68
    penalty: float = 0.2
    min_vertical_yield: float = 0.25
    min_condor_yield: float = 0.33
    min_theta_ratio: float = 0.015
    min_ivr: float = 45.0
    max_skew_shift: float = 0.08  # cap on per-side delta shift from skew
    weights: dict = field(
        default_factory=lambda: {"pop": 0.30, "yield": 0.25, "ev": 0.15, "theta": 0.15, "vega": 0.15}
    )


@dataclass(frozen=True)
class RiskConfig:
    hvn_atr_multiple: float = 1.0
    pivot_breach_minutes: float = 15.0
    delta_stop: float = 0.35
    hvn_lookback: int = 180


@dataclass(frozen=True)
class ChaserConfig:
    max_chases: int = 5
    wait_seconds: float = 3.0
    max_slippage: float = 0.10  # dollars per share past the starting mid
    # Multi-leg option orders are generally not accepted as market orders and a
    # market fill in a fast tape is exactly the slippage this engine avoids.
    # Off by default; the final step instead rests at the natural price.
    allow_market_fallback: bool = False


@dataclass(frozen=True)
class BrokerConfig:
    """Live trading is opt-in. Default is the tastytrade certification sandbox + dry-run."""

    base_url: str = field(
        default_factory=lambda: os.getenv("TT_BASE_URL", "https://api.cert.tastyworks.com")
    )
    live_orders: bool = field(default_factory=lambda: os.getenv("VIKING_LIVE") == "1")
    client_secret: str = field(default_factory=lambda: os.getenv("TT_CLIENT_SECRET", ""))
    refresh_token: str = field(default_factory=lambda: os.getenv("TT_REFRESH_TOKEN", ""))
    account_number: str = field(default_factory=lambda: os.getenv("TT_ACCOUNT", ""))

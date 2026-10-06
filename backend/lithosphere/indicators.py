"""Technical indicators. All functions take pandas Series/DataFrames of daily bars
with columns: open, high, low, close, volume."""
from __future__ import annotations

import numpy as np
import pandas as pd


def historical_volatility(close: pd.Series, window: int) -> pd.Series:
    """Annualised close-to-close HV."""
    return np.log(close / close.shift(1)).rolling(window).std() * np.sqrt(252)


def true_range(df: pd.DataFrame) -> pd.Series:
    prev = df["close"].shift(1)
    return pd.concat(
        [df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1
    ).max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder ATR."""
    return true_range(df).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder ADX."""
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    a = 1 / period
    tr_s = true_range(df).ewm(alpha=a, adjust=False, min_periods=period).mean()
    plus_di = 100 * plus_dm.ewm(alpha=a, adjust=False, min_periods=period).mean() / tr_s
    minus_di = 100 * minus_dm.ewm(alpha=a, adjust=False, min_periods=period).mean() / tr_s
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=a, adjust=False, min_periods=period).mean()


def average_dollar_volume(df: pd.DataFrame, window: int = 30) -> pd.Series:
    return (df["close"] * df["volume"]).rolling(window).mean()


def squeeze_box(df: pd.DataFrame, std_window=10, atr_period=14, atr_sma=50) -> pd.Series:
    """True where StdDev(Close, 10) < SMA(ATR(14), 50)."""
    return df["close"].rolling(std_window).std() < atr(df, atr_period).rolling(atr_sma).mean()


def run_lengths(flags: pd.Series) -> tuple[int, list[int]]:
    """Return (current trailing run of True, lengths of all *completed* True runs)."""
    vals = flags.fillna(False).to_numpy(dtype=bool)
    runs, n = [], 0
    for v in vals:
        if v:
            n += 1
        elif n:
            runs.append(n)
            n = 0
    return n, runs


def volume_profile_hvn(df: pd.DataFrame, lookback: int = 180, bins: int = 48,
                       node_threshold: float = 0.70) -> dict:
    """Volume-at-price over `lookback` bars. Each bar's volume is spread evenly over the
    bins its high-low range touches. The HVN is the peak-volume bin extended outward over
    contiguous bins holding >= node_threshold of peak volume. Returns the node's borders."""
    d = df.tail(lookback)
    lo, hi = float(d["low"].min()), float(d["high"].max())
    edges = np.linspace(lo, hi, bins + 1)
    vol = np.zeros(bins)
    for h, l, v in zip(d["high"].to_numpy(), d["low"].to_numpy(), d["volume"].to_numpy()):
        a = min(max(np.searchsorted(edges, l, side="right") - 1, 0), bins - 1)
        b = min(max(np.searchsorted(edges, h, side="right") - 1, 0), bins - 1)
        vol[a : b + 1] += v / (b - a + 1)
    peak = int(vol.argmax())
    left = right = peak
    floor = vol[peak] * node_threshold
    while left > 0 and vol[left - 1] >= floor:
        left -= 1
    while right < bins - 1 and vol[right + 1] >= floor:
        right += 1
    return {"poc": float((edges[peak] + edges[peak + 1]) / 2),
            "low": float(edges[left]), "high": float(edges[right + 1])}


def anchored_vwap(df: pd.DataFrame, anchor_pos: int) -> float:
    d = df.iloc[anchor_pos:]
    tp = (d["high"] + d["low"] + d["close"]) / 3
    return float((tp * d["volume"]).sum() / d["volume"].sum())

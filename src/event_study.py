"""Core analytical logic for the Tariff Impact Explorer.

Event-study methodology in plain language:
    Given a tariff announcement date, we look at how each asset price moved
    in a window of trading days around the announcement. Because markets are
    closed on weekends and holidays, an announcement made on, say, Saturday
    is not observable until the next trading day. We therefore align the
    event to the nearest trading day ON OR AFTER the announcement date.

    Each asset price in the window is normalised so that the event-day value
    equals 100. This makes different assets comparable on a single chart
    (the S&P 500 is ~7000, steel futures are ~1000; raw prices would hide
    relative movements).
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

ASSET_COLUMNS = [
    "sp500",
    "shanghai_composite",
    "dxy",
    "usd_cny",
    "crude_oil_wti",
    "steel_futures",
    "aluminum_futures",
    "soybeans",
]


def _find_event_index(market_df: pd.DataFrame, event_date: pd.Timestamp) -> int:
    """Return the index of the nearest trading day on or after `event_date`.

    Uses `searchsorted` with `side='left'` so that if the event date itself
    is a trading day, that exact day is selected (offset 0).
    """
    dates = market_df["date"].values
    if pd.Timestamp(event_date) < pd.Timestamp(dates[0]):
        # searchsorted would silently return 0, mis-anchoring the event window
        # on the first available trading day. Fail loud instead.
        raise ValueError(
            f"Event date {event_date.date()} is before the start of the market data "
            f"({pd.Timestamp(dates[0]).date()}); cannot build a valid event window."
        )
    idx = int(np.searchsorted(dates, np.datetime64(event_date), side="left"))
    if idx >= len(market_df):
        raise ValueError(
            f"Event date {event_date.date()} is after the end of the market data."
        )
    return idx


def compute_event_window(
    market_df: pd.DataFrame,
    tariffs_df: pd.DataFrame,
    event_headline: str,
    window: tuple[int, int] = (-5, 10),
    assets: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Normalised price window around a tariff event.

    Parameters
    ----------
    market_df : daily market data (already cleaned).
    tariffs_df : tariff event rows.
    event_headline : exact string from `tariffs_df.headline` to select the event.
    window : (pre, post) trading-day offsets around the event day.
             (-5, 10) means 5 days before through 10 days after.
    assets : optional subset of asset columns to return.

    Returns
    -------
    DataFrame with columns:
        date, trading_day_offset, <asset columns normalised to event-day=100>.
    Row at offset 0 is the event day; every asset is 100.0 there.
    """
    matches = tariffs_df.loc[tariffs_df["headline"] == event_headline]
    if matches.empty:
        raise KeyError(f"No event with headline: {event_headline!r}")
    event_date = pd.Timestamp(matches["date"].iloc[0])

    event_idx = _find_event_index(market_df, event_date)

    # Clip the window to the available bounds so that events near either end
    # of the market data do not raise but instead return a truncated window.
    start = max(0, event_idx + window[0])
    end = min(len(market_df), event_idx + window[1] + 1)
    sliced = market_df.iloc[start:end].copy().reset_index(drop=True)

    # Compute trading-day offset relative to the actual event index we landed on.
    sliced["trading_day_offset"] = np.arange(start, end) - event_idx

    cols = list(assets) if assets is not None else ASSET_COLUMNS
    cols = [c for c in cols if c in sliced.columns]

    # Normalise each asset to 100 at offset 0. `base` lookup is via the
    # unique offset==0 row to stay robust if window is clipped asymmetrically.
    base_row = sliced.loc[sliced["trading_day_offset"] == 0]
    if base_row.empty:
        raise ValueError(
            "Event day fell outside the clipped window; cannot normalise."
        )
    base = base_row[cols].iloc[0]
    normalised = sliced[cols].divide(base).multiply(100.0)

    out = pd.concat(
        [sliced[["date", "trading_day_offset"]], normalised],
        axis=1,
    )
    return out


def summarize_event(window_df: pd.DataFrame, assets: Iterable[str] | None = None) -> pd.DataFrame:
    """Per-asset summary: pre-event return, post-event return, volatility, max drawdown.

    All metrics are computed on the normalised (event-day=100) series.
    """
    cols = list(assets) if assets is not None else [
        c for c in window_df.columns
        if c not in {"date", "trading_day_offset"}
    ]

    # Offset 0 is deliberately included in both subsets: it is the end anchor
    # of `pre` (value 100 by construction) and the start anchor of `post`
    # (also 100). This is a shared boundary, not a double-counted observation.
    pre = window_df.loc[window_df["trading_day_offset"] <= 0]
    post = window_df.loc[window_df["trading_day_offset"] >= 0]

    rows = []
    for asset in cols:
        if asset not in window_df.columns:
            continue
        pre_series = pre[asset].dropna()
        post_series = post[asset].dropna()
        # Return over the pre-event sub-window: (event-day value) / (first value) - 1.
        pre_ret = (pre_series.iloc[-1] / pre_series.iloc[0] - 1.0) if len(pre_series) >= 2 else np.nan
        # Return over the post-event sub-window: (last value) / (event-day value) - 1.
        post_ret = (post_series.iloc[-1] / post_series.iloc[0] - 1.0) if len(post_series) >= 2 else np.nan
        # Daily returns on the post window for volatility.
        daily_rets = post_series.pct_change().dropna()
        vol = daily_rets.std() if len(daily_rets) >= 2 else np.nan
        # Max drawdown on the post window (trough relative to running peak).
        running_peak = post_series.cummax()
        drawdown = (post_series / running_peak) - 1.0
        max_dd = drawdown.min() if len(drawdown) > 0 else np.nan
        rows.append(
            {
                "asset": asset,
                "pre_event_return": pre_ret,
                "post_event_return": post_ret,
                "post_event_volatility": vol,
                "max_drawdown": max_dd,
            }
        )
    return pd.DataFrame(rows)


def build_sensitivity_matrix(
    market_df: pd.DataFrame,
    tariffs_df: pd.DataFrame,
    window_length: int,
    assets: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Events x assets matrix of cumulative post-event returns.

    Each cell is the cumulative return from event day (offset 0) to
    offset +window_length, expressed as a decimal (e.g. 0.035 = +3.5%).
    Used to draw the Asset Sensitivity Heatmap.
    """
    cols = list(assets) if assets is not None else ASSET_COLUMNS
    index_labels = []
    rows = []
    for _, event in tariffs_df.iterrows():
        headline = event["headline"]
        try:
            win = compute_event_window(
                market_df, tariffs_df, headline,
                window=(0, window_length), assets=cols,
            )
        except (KeyError, ValueError):
            continue
        # Post-event cumulative return = (normalised value at end of window / 100) - 1.
        last_row = win.iloc[-1]
        returns = {c: (last_row[c] / 100.0 - 1.0) if c in win.columns else np.nan for c in cols}
        label = f"{pd.Timestamp(event['date']).date()} — {headline[:50]}"
        index_labels.append(label)
        rows.append(returns)

    matrix = pd.DataFrame(rows, index=index_labels)
    return matrix


def largest_absolute_moves(matrix: pd.DataFrame, top_n: int = 3) -> pd.DataFrame:
    """Identify the cells with the largest absolute returns in the matrix.

    Used to auto-generate the sentence under the heatmap.
    """
    # Use future_stack=True to opt into the pandas 2.x behaviour (no
    # FutureWarning). Behaviour is equivalent here because the matrix has
    # no NaN entries in practice.
    stacked = matrix.stack(future_stack=True).reset_index()
    stacked.columns = ["event", "asset", "return"]
    stacked = stacked.assign(abs_return=stacked["return"].abs())
    return stacked.sort_values("abs_return", ascending=False).head(top_n).reset_index(drop=True)

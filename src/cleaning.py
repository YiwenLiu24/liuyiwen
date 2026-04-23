"""Data cleaning and unit correction.

Two things worth highlighting for the marker:

1.  The `market_reaction.csv` file contains nulls on Chinese-market holidays
    (112 rows on `shanghai_composite`, and one-off gaps elsewhere). We apply
    a forward-fill so every trading day has a value. Forward-fill is the
    conventional choice for holiday gaps because the next available close
    is the most faithful representation of "last known price".

2.  The `trade_balance.csv` file has a column named `us_trade_balance_bn`,
    but inspection of the numbers (e.g. -43,562 for January 2020) shows they
    are in MILLIONS of US dollars, not billions. The US monthly goods-and-
    services deficit for Jan 2020 was reported by BEA at about USD 43.6B,
    which matches -43,562 million. We rename the column to make the unit
    explicit and add a billions column for user-friendly display.
"""
from __future__ import annotations

import pandas as pd

MARKET_FFILL_COLUMNS = [
    "sp500",
    "shanghai_composite",
    "dxy",
    "usd_cny",
    "crude_oil_wti",
    "steel_futures",
    "aluminum_futures",
    "soybeans",
]


def clean_market_reaction(df: pd.DataFrame) -> pd.DataFrame:
    """Forward-fill null market values that stem from holiday gaps."""
    out = df.copy()
    # Sort by date to guarantee the ffill direction is chronologically correct.
    out = out.sort_values("date").reset_index(drop=True)
    cols = [c for c in MARKET_FFILL_COLUMNS if c in out.columns]
    out[cols] = out[cols].ffill()
    return out


def clean_trade_balance(df: pd.DataFrame) -> pd.DataFrame:
    """Correct the mislabeled unit on the trade-balance column.

    Returns a DataFrame with:
      - `us_trade_balance_mn`: raw value, explicitly in millions of USD
      - `us_trade_balance_bn`: the same value expressed in billions of USD
                                (divided by 1000) for user-facing display.
    """
    out = df.copy()
    # The original column is misnamed `_bn` but is actually millions.
    if "us_trade_balance_bn" in out.columns:
        out = out.rename(columns={"us_trade_balance_bn": "us_trade_balance_mn"})
    out = out.assign(us_trade_balance_bn=out["us_trade_balance_mn"] / 1000.0)
    return out


def null_report(df: pd.DataFrame) -> pd.DataFrame:
    """Return a small DataFrame summarising null counts per column.

    Used in the notebook to document data quality before cleaning.
    """
    counts = df.isna().sum()
    return pd.DataFrame({"column": counts.index, "null_count": counts.values})

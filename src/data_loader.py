"""Load raw CSV files from the data/ directory.

Separating loading from cleaning makes it easy to re-run the notebook
and the Streamlit app on the same source files without duplicating I/O.
"""
from pathlib import Path

import pandas as pd
import streamlit as st

# Resolve data/ relative to this file so the code works regardless of
# the current working directory when `streamlit run app.py` is launched.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@st.cache_data
def load_market_reaction() -> pd.DataFrame:
    """Daily market data: S&P 500, Shanghai, DXY, USD/CNY, commodities."""
    path = DATA_DIR / "market_reaction.csv"
    df = pd.read_csv(path, parse_dates=["date"])
    return df.sort_values("date").reset_index(drop=True)


@st.cache_data
def load_tariff_rates() -> pd.DataFrame:
    """Tariff event announcements (15 rows, 2018-2025)."""
    path = DATA_DIR / "tariff_rates.csv"
    df = pd.read_csv(path, parse_dates=["date"])
    # The `url` column is entirely null in this dataset; drop it so downstream
    # code does not confuse a dead column for useful metadata.
    if "url" in df.columns:
        df = df.drop(columns=["url"])
    return df.sort_values("date").reset_index(drop=True)


@st.cache_data
def load_trade_balance() -> pd.DataFrame:
    """Monthly US trade balance (FRED / Census)."""
    path = DATA_DIR / "trade_balance.csv"
    df = pd.read_csv(path)
    # Date arrives as 'YYYY-MM'; parse to a month-start timestamp.
    df = df.assign(date=pd.to_datetime(df["date"], format="%Y-%m"))
    return df.sort_values("date").reset_index(drop=True)

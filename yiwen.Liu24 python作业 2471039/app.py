#ACC102 Track 4 Assignment
#Name:Yiwen Liu
#Student ID :2471039
"""Tariff Impact Explorer — Streamlit entry point.

Run locally with:
    streamlit run app.py

Four pages selectable from the sidebar:
  1. Overview — high-level orientation (KPIs + tariff-event timeline).
  2. Event Study Explorer — interactive normalised-price chart + summary table.
  3. Asset Sensitivity Heatmap — cross-event cross-asset post-event returns.
  4. Methodology & Limitations — what we did, what we excluded, and why.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.cleaning import clean_market_reaction, clean_trade_balance
from src.data_loader import (
    load_market_reaction,
    load_tariff_rates,
    load_trade_balance,
)
from src.event_study import (
    ASSET_COLUMNS,
    build_sensitivity_matrix,
    compute_event_window,
    largest_absolute_moves,
    summarize_event,
)
from src.plots import (
    event_window_line_chart,
    sensitivity_heatmap,
    tariff_timeline,
)

DATA_SOURCE_URL = (
    "https://www.kaggle.com/datasets/belbino/"
    "us-tariff-and-trade-war-impact-dataset-2018-present"
)
DATA_ACCESS_DATE = "2026-04-18"


st.set_page_config(
    page_title="Tariff Impact Explorer",
    page_icon=None,
    layout="wide",
)


# ---------- Data loading (cached via st.cache_data inside loaders) -----------

@st.cache_data
def load_all():
    market_raw = load_market_reaction()
    tariffs = load_tariff_rates()
    trade_raw = load_trade_balance()
    market = clean_market_reaction(market_raw)
    trade = clean_trade_balance(trade_raw)
    # The market data begins on 2020-01-02. A handful of 2018-2019 tariff
    # announcements predate the data and would silently anchor the event
    # window on the first trading day, which is meaningless. Drop them here
    # so the UI only surfaces events the data can actually analyse.
    market_start = market["date"].min()
    tariffs_in_range = tariffs.loc[tariffs["date"] >= market_start].reset_index(drop=True)
    return market, tariffs_in_range, trade


market_df, tariffs_df, trade_df = load_all()


# ---------- Sidebar navigation ----------------------------------------------

st.sidebar.title("Tariff Impact Explorer")
page = st.sidebar.radio(
    "Page",
    [
        "Overview",
        "Event Study Explorer",
        "Asset Sensitivity Heatmap",
        "Methodology & Limitations",
    ],
)
st.sidebar.markdown("---")
st.sidebar.markdown(f"**Data source:** [Kaggle]({DATA_SOURCE_URL})")
st.sidebar.markdown(f"**Access date:** {DATA_ACCESS_DATE}")


# ---------- Page 1: Overview -------------------------------------------------

def render_overview() -> None:
    st.title("Tariff Impact Explorer")
    st.markdown(
        "A small interactive tool that answers the question: "
        "*How did markets actually react to this specific US tariff announcement?* "
        "Intended for finance journalists, junior trade analysts, and business "
        "students who need quick exploratory evidence before writing a brief or "
        "preparing a case study."
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "Tariff events analysed",
        f"{len(tariffs_df):,}",
        help=(
            "The raw dataset lists 15 events; 4 pre-date the 2020-01-02 "
            "start of the market series and were dropped. See Methodology."
        ),
    )
    k2.metric(
        "Highest rate among analysed events",
        f"{tariffs_df['tariff_rate_pct'].max():.0f}%",
        help=(
            "Computed over the 11 in-range events. The 4 dropped pre-2020 "
            "events (max 25%) are lower than this value anyway."
        ),
    )
    span_start = market_df["date"].min().date()
    span_end = market_df["date"].max().date()
    k3.metric("Market data span", f"{span_start} → {span_end}")
    latest_trade = trade_df.iloc[-1]
    k4.metric(
        "Latest monthly trade balance",
        f"${latest_trade['us_trade_balance_bn']:.1f}B",
        help=(
            f"Month: {latest_trade['date'].strftime('%Y-%m')}. "
            "Negative values indicate a trade deficit."
        ),
    )

    st.subheader("Timeline of tariff events")
    st.plotly_chart(tariff_timeline(tariffs_df), use_container_width=True)

    st.caption(
        "Bubble size encodes the headline tariff rate. Hover over a point to "
        "see the underlying announcement."
    )


# ---------- Page 2: Event Study Explorer -------------------------------------

def _format_event_label(row: pd.Series) -> str:
    return f"{row['date'].date()} — {row['headline']}"


def render_event_study() -> None:
    st.title("Event Study Explorer")
    st.markdown(
        "Pick any tariff event and any subset of assets to see how prices moved "
        "in the trading days around the announcement. Prices are normalised so "
        "the event day equals 100."
    )

    tariffs_df_sorted = tariffs_df.sort_values("date").reset_index(drop=True)
    event_labels = [_format_event_label(r) for _, r in tariffs_df_sorted.iterrows()]
    label_to_headline = dict(zip(event_labels, tariffs_df_sorted["headline"]))

    c1, c2 = st.columns([2, 3])
    with c1:
        # Default to the 2018-03-08 Section 232 steel tariff — a classic event
        # whose effect on steel futures is visible and easy to narrate.
        default_idx = 0
        selected_label = st.selectbox(
            "Tariff event",
            options=event_labels,
            index=default_idx,
        )
        selected_assets = st.multiselect(
            "Assets to compare",
            options=ASSET_COLUMNS,
            default=["sp500", "steel_futures", "soybeans"],
        )
        # Two separate sliders so the window is guaranteed to include the
        # event day (offset 0). A single range-slider with bounds (-10, +20)
        # would let the user drag both handles to the same side of zero,
        # which raises ValueError inside compute_event_window.
        pre = st.slider(
            "Trading days before event",
            min_value=-10, max_value=0, value=-5,
        )
        post = st.slider(
            "Trading days after event",
            min_value=1, max_value=20, value=10,
        )

    if not selected_assets:
        st.warning("Select at least one asset to continue.")
        return

    headline = label_to_headline[selected_label]
    window_df = compute_event_window(
        market_df, tariffs_df,
        event_headline=headline,
        window=(pre, post),
        assets=selected_assets,
    )

    with c2:
        st.plotly_chart(
            event_window_line_chart(window_df, selected_assets, title=headline),
            use_container_width=True,
        )

    summary = summarize_event(window_df, assets=selected_assets)

    # Auto-insight: pick the asset with the largest absolute post-event move.
    if not summary.empty and summary["post_event_return"].notna().any():
        ordered = summary.reindex(
            summary["post_event_return"].abs().sort_values(ascending=False).index
        )
        top = ordered.iloc[0]
        pct = top["post_event_return"] * 100
        st.markdown(
            f"**Auto-insight.** In the {post} trading days after this event, "
            f"**{top['asset']}** moved **{pct:+.1f}%**, the largest reaction "
            f"among the selected assets."
        )

    st.subheader("Per-asset summary")
    def _fmt_pct(x):
        return "" if pd.isna(x) else f"{x:+.2%}"

    pct_cols = ["pre_event_return", "post_event_return", "post_event_volatility", "max_drawdown"]
    pretty = summary.assign(**{c: summary[c].map(_fmt_pct) for c in pct_cols})
    st.dataframe(pretty, hide_index=True, use_container_width=True)


# ---------- Page 3: Asset Sensitivity Heatmap --------------------------------

def render_heatmap() -> None:
    st.title("Asset Sensitivity Heatmap")
    st.markdown(
        "Cumulative return per asset over a fixed window after each tariff event. "
        "A diverging red-blue scale is centred at zero, so blue cells are gains "
        "and red cells are losses relative to the event day."
    )

    window_length = st.select_slider(
        "Post-event window (trading days)",
        options=[3, 5, 10],
        value=5,
    )
    matrix = build_sensitivity_matrix(market_df, tariffs_df, window_length)
    st.plotly_chart(sensitivity_heatmap(matrix), use_container_width=True)

    st.subheader("Largest absolute moves")
    top = largest_absolute_moves(matrix, top_n=3)
    for _, row in top.iterrows():
        pct = row["return"] * 100
        st.markdown(
            f"- **{row['asset']}** moved **{pct:+.1f}%** in the "
            f"{window_length} trading days after: *{row['event']}*."
        )


# ---------- Page 4: Methodology & Limitations --------------------------------

def render_methodology() -> None:
    st.title("Methodology & Limitations")

    st.subheader("Event-study construction")
    st.markdown(
        """
- **Event alignment.** A tariff announcement date is mapped to the nearest
  trading day on or after the announcement using `numpy.searchsorted`. This
  handles announcements that fall on weekends or holidays.
- **Normalisation.** Every asset in the window is rescaled so its event-day
  value equals 100. This makes assets with very different price levels (the
  S&P 500 in the thousands vs. the USD/CNY exchange rate near 0.14)
  comparable on a single chart.
- **Summary metrics.** Pre-event return, post-event return, post-event
  daily-return volatility, and maximum drawdown are computed on the
  normalised series.
- **Near-boundary clipping.** If an event is too close to the start or
  end of the market data, the requested window is silently truncated on
  the short side. For example, the 2020-01-15 Phase 1 event has only 9
  trading days before it in the data, so a (-10, +10) request returns
  a (-9, +10) window. The summary metrics still use whatever data is
  available; sub-windows with fewer than two observations return blank.
        """
    )

    st.subheader("Data cleaning decisions")
    st.markdown(
        """
- **Unit correction on trade balance.** The `trade_balance.csv` column was
  named `us_trade_balance_bn` but the values are in **millions** of USD,
  not billions. We rename the column to make the unit explicit and add
  a billions column for display.
- **Forward-fill on market holidays.** The Shanghai Composite has 112 null
  rows from Chinese-market holidays. We forward-fill so every trading day
  has a value; forward-fill is the conventional choice because the next
  available close is the most faithful representation of "last known price".
- **News file excluded.** `tariff_news_headlines.csv` covers only
  2026-04-06 to 2026-04-15 (10 days) and includes low-credibility sources
  such as Activistpost.com and Globalresearch.ca. The 10-day span is too
  short to support event-study analysis across our 2018–2025 event window,
  and the source mix is inconsistent with the educational-reliability
  requirement in the assignment brief. We therefore excluded it.
- **Pre-2020 tariff events dropped.** `market_reaction.csv` begins on
  2020-01-02, but four tariff events in `tariff_rates.csv` predate that
  start (2018-03-08 steel, 2018-03-08 aluminium, 2018-07-06 China tech,
  2019-09-01 consumer goods). Analysing them would silently anchor the
  event window on the first available trading day — a meaningless result.
  We drop these four rows up front so the app only surfaces the 11 events
  the market data can actually support.
        """
    )

    st.subheader("Limitations")
    st.markdown(
        """
- **Daily granularity only.** Intraday reactions to news are often
  concentrated in the first minutes or hours after release; this dataset
  cannot capture them.
- **Event-date approximation.** `tariff_rates.csv` encodes announcement or
  effective dates; the market may have priced in the event days earlier
  via rumours or leaks.
- **Small event sample.** 15 events is enough for exploratory comparison
  but too few for formal statistical inference.
- **US-centric perspective.** Asset coverage (S&P 500, steel/aluminium
  futures, soybeans, USD/CNY) reflects the US-China dimension of the trade
  war and does not capture broader spillovers.
- **Secondary data.** The Kaggle feed aggregates Yahoo Finance, FRED, and
  US Census series. We treat it as educational data, not as a trading or
  policy-grade source.
        """
    )

    st.caption(
        "See `reflection.md` in the repository for the full written reflection "
        "and the AI-use disclosure."
    )


# ---------- Router -----------------------------------------------------------

PAGES = {
    "Overview": render_overview,
    "Event Study Explorer": render_event_study,
    "Asset Sensitivity Heatmap": render_heatmap,
    "Methodology & Limitations": render_methodology,
}

PAGES[page]()

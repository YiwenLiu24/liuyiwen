"""Plotly chart builders.

Keeping chart construction in a dedicated module makes it easy to reuse
the same figures in the notebook and in the Streamlit app.
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def event_window_line_chart(
    window_df: pd.DataFrame,
    assets: Iterable[str],
    title: str = "",
) -> go.Figure:
    """Normalised-price line chart across the event window."""
    assets = [a for a in assets if a in window_df.columns]
    long = window_df.melt(
        id_vars=["date", "trading_day_offset"],
        value_vars=assets,
        var_name="asset",
        value_name="price_index",
    )
    fig = px.line(
        long,
        x="trading_day_offset",
        y="price_index",
        color="asset",
        title=title,
    )
    # A dashed horizontal line at 100 = event-day reference level,
    # plus a vertical marker at offset 0 = event day.
    fig.add_hline(y=100, line_dash="dash", line_color="gray", opacity=0.4)
    fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.4)
    fig.update_layout(
        xaxis_title="Trading days from event",
        yaxis_title="Normalised price (event day = 100)",
        legend_title="Asset",
        hovermode="x unified",
    )
    return fig


def sensitivity_heatmap(matrix: pd.DataFrame) -> go.Figure:
    """Events x assets heatmap of post-event cumulative returns."""
    # Multiply by 100 so the colour scale reads as percentages.
    pct = matrix * 100.0
    fig = px.imshow(
        pct.values,
        x=pct.columns,
        y=pct.index,
        color_continuous_scale="RdBu_r",
        color_continuous_midpoint=0.0,
        aspect="auto",
        labels={"color": "Return (%)"},
    )
    fig.update_layout(
        xaxis_title="Asset",
        yaxis_title="Event",
        coloraxis_colorbar_title="Return (%)",
    )
    return fig


def tariff_timeline(tariffs_df: pd.DataFrame) -> go.Figure:
    """Scatter of tariff events coloured by headline tariff rate."""
    fig = px.scatter(
        tariffs_df,
        x="date",
        y="tariff_rate_pct",
        color="country",
        size="tariff_rate_pct",
        hover_data=["headline", "product_category", "announcement_source"],
        title="Major US Tariff Events, 2018-2025",
    )
    fig.update_layout(
        xaxis_title="Announcement date",
        yaxis_title="Headline tariff rate (%)",
        legend_title="Country / region",
    )
    return fig

# Tariff Impact Explorer

A small interactive Streamlit tool that lets the user pick any of 15 major US tariff events (2018–2025) and see how major market indices and commodities moved in the trading days around the announcement.

Submitted for **ACC102 Mini Assignment (Python Data Product, 15%)** at Xi'an Jiaotong-Liverpool University, Track 4 — Interactive Data Analysis Tool.

## 1. Problem & User

When a new US tariff is announced, how did financial and commodity markets react? Static news reports cannot support follow-up questions such as *"which asset moved most in the ten days after Liberation Day?"*. This tool is built for finance journalists, junior trade analysts, and undergraduate business students who need quick exploratory evidence before writing a brief, article, or case study.

## 2. Live Demo

The demo video (see submission on LMO) walks through the notebook, the `src/event_study.py` core function, and the Streamlit app running locally.

## 3. Data

- **Source.** *US Tariff & Trade War Impact Dataset (2018–Present)* by BELBIN BENO — Kaggle: https://www.kaggle.com/datasets/belbino/us-tariff-and-trade-war-impact-dataset-2018-present
- **Access date.** 2026-04-18
- **Files used (all under `data/`).**
  - `market_reaction.csv` — 1,581 daily rows, 2020-01-02 to 2026-04-17, 8 asset series.
  - `tariff_rates.csv` — 15 tariff events, 2018-03-08 to 2025-04-09; 11 analysed in the app (4 pre-2020 dropped, see below).
  - `trade_balance.csv` — 74 monthly rows, 2020-01 to 2026-02.
- **File excluded.** `tariff_news_headlines.csv` covers only 10 days and mixes low-credibility sources; see `reflection.md` and the Methodology page of the app for the exclusion reasoning.
- **Four tariff events excluded.** The market data begins on 2020-01-02; four 2018–2019 tariff events (2018-03-08 Section 232 steel/aluminium, 2018-07-06 China tech, 2019-09-01 consumer goods) predate it. We drop them rather than silently anchor their event windows on the first available trading day. The app therefore analyses the 11 in-range events from 2020-01-15 onward.
- **Known data issue, fixed in `src/cleaning.py`.** The `trade_balance.csv` column `us_trade_balance_bn` is mis-labelled: the values are in **millions** of USD, not billions. We rename the raw column to `us_trade_balance_mn` and derive a true billions column.

## 4. Methods

- **Cleaning.** Forward-fill of holiday gaps in `shanghai_composite` and a few one-off gaps in `usd_cny` / `steel_futures`; unit correction on the trade-balance file.
- **Event-study design.** For each tariff event, snap to the nearest trading day on or after the announcement (`numpy.searchsorted`), slice a configurable window, normalise each asset so the event-day value equals 100, and compute pre/post returns, post-event volatility, and maximum drawdown.
- **Visualisation.** Plotly line charts for event windows, a diverging red-blue heatmap centred at zero for cross-event sensitivity, and a bubble timeline for tariff events.

## 5. Key Findings

Observations from the notebook and the interactive app:

- **Liberation Day (2025-04-02) is the notebook's worked example.** A broad 10% tariff on all imports produces a visible, multi-asset reaction (S&P 500, USD/CNY, Shanghai Composite) in the 10 trading days that follow — direction and size are readable from the summary table in `notebook.ipynb` §5.
- **Sensitivity is asset-specific.** The same tariff event does not move every asset by the same sign or magnitude — the heatmap makes the pattern visible across all 11 in-range events.
- **Event-day alignment matters mechanically.** Several tariff dates fall on weekends; without the `searchsorted` alignment to the next trading day, the event-day row is missing and every downstream return is shifted by one.
- **Data-range alignment matters too.** Four tariff events predate the market data start. Without an explicit in-range filter, `searchsorted` would silently anchor their event windows on 2020-01-02 and the heatmap would carry four meaningless rows.
- **Daily-only granularity understates announcement reactions.** Large intraday moves in the first hours after an overnight announcement collapse into a single close-to-close return.
- **The dataset is secondary.** We treat it as suitable for educational exploration; a trading-grade or policy-grade use case would demand direct pulls from Yahoo Finance / FRED / USTR.

## 6. How to Run

```bash
# 1. Clone the repository
git clone <repo-url>
cd tariff-impact-explorer

# 2. (Recommended) create a clean virtual environment
python3 -m venv .venv
source .venv/bin/activate     # macOS / Linux
# .venv\Scripts\activate      # Windows

# 3. Install pinned dependencies
pip install -r requirements.txt

# 4. Launch the app
streamlit run app.py
```

The app opens at `http://localhost:8501`. Use the sidebar to switch between the four pages: Overview, Event Study Explorer, Asset Sensitivity Heatmap, Methodology & Limitations.

To run the notebook instead:

```bash
jupyter notebook notebook.ipynb
```

## 7. Repository Structure

```
tariff-impact-explorer/
├── README.md
├── requirements.txt
├── app.py                  # Streamlit entry point (4 pages)
├── notebook.ipynb          # Analytical notebook (6 sections)
├── reflection.md           # 500-800 word reflection + AI disclosure
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── data_loader.py      # CSV loaders with @st.cache_data
│   ├── cleaning.py         # Forward-fill + unit correction
│   ├── event_study.py      # compute_event_window, summarize_event, build_sensitivity_matrix
│   └── plots.py            # Plotly chart builders
├── data/
│   ├── market_reaction.csv
│   ├── tariff_rates.csv
│   └── trade_balance.csv
└── figures/
    └── (screenshots)
```

## 8. Limitations & Next Steps

See the **Methodology & Limitations** page of the app and `reflection.md` for a full discussion. In short: daily-only granularity, 15-event sample, US-centric asset set, and secondary-data provenance. Natural next steps would include intraday data for the largest events and replacing Kaggle with direct pulls from FRED / Yahoo Finance / USTR.

## 9. Acknowledgements

Data aggregation by BELBIN BENO R M on Kaggle. Underlying sources: Yahoo Finance, FRED (Federal Reserve Economic Data), US Census Bureau trade API.

# Archive Selection System

A quantitative analysis system for identifying and evaluating high-potential archive fashion items on the resale market. It scrapes Grailed marketplace data, scores items on scarcity/velocity/hype/momentum, predicts price trends with ML models, and presents everything in an interactive dashboard.

## System Architecture

```
Discovery              Scraping             Scoring             Prediction           Decision
──────────           ──────────           ──────────           ──────────           ──────────
                     grailed_scraper.py   scorecard.py         historical_          dashboard.py
discovery.py   ───>  (listings/sold/      (weighted scoring    scraper.py    ───>   (interactive
(trend scan,          totals from          across 4             (180-day              Streamlit
 brand hype           Algolia API)         dimensions)          sold history)         dashboard)
 detection)               │                    │                    │                    │
                          ▼                    ▼                    ▼                    ▼
                    grailed_listings.csv  scorecard.csv       historical_sold.csv   Selection +
                    grailed_sold.csv                                                Price
                    grailed_totals.csv                        price_model.py        Prediction
                                                              (LR + XGBoost)        pages
```

## Modules

| Module | Description |
|--------|-------------|
| **`discovery.py`** | Scans Grailed for trending archive items without preset brand lists. Ranks by follower count to surface emerging demand signals. |
| **`grailed_scraper.py`** | Scrapes current listings, recent sold items, and total counts from Grailed's Algolia API for each tracked keyword. |
| **`scorecard.py`** | Computes a weighted composite score (0-10) per item: Supply/Demand (35%), Velocity (30%), Hype (25%), Momentum (10%). |
| **`historical_scraper.py`** | Pulls 180-day historical sold records for top-scoring items. Supports incremental updates with deduplication. |
| **`price_model.py`** | Trains Linear Regression + XGBoost models per item using time-series features and rolling price averages. Outputs predicted price and trend direction. |
| **`dashboard.py`** | Streamlit web app with two pages: **Selection Dashboard** (ranking, radar chart, scatter plot) and **Price Prediction** (forecasts, trend charts, model comparison). |
| **`run_weekly.py`** | Orchestrates the weekly pipeline: scrape → score → output. |

## Tech Stack

- **Python 3.10+**
- **Streamlit** — Interactive dashboard
- **Plotly** — Charts and visualizations
- **XGBoost + scikit-learn** — Price prediction models
- **pandas / NumPy** — Data processing
- **Grailed Algolia API** — Marketplace data source

## Getting Started

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the data pipeline

```bash
# Step 1: Discover trending items
python discovery.py

# Step 2: Scrape current market data + generate scorecard
python run_weekly.py

# Step 3: Scrape historical sold data (180 days) for price prediction
python historical_scraper.py
```

### 3. Launch the dashboard

```bash
streamlit run dashboard.py
```

The dashboard has two pages (switch via sidebar):
- **Selection Dashboard** — Item rankings, radar comparison, supply/demand scatter
- **Price Prediction** — ML price forecasts, trend signals, model performance

### 4. (Optional) Run analysis notebooks

```bash
jupyter notebook analysis_report.ipynb      # EDA & selection analysis
jupyter notebook price_prediction.ipynb     # Price model deep dive
```

## Live Dashboard

[**archive-selection-system on Streamlit Cloud**](https://archive-selection-system.streamlit.app/)

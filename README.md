# Archive Selection System

A quantitative analysis system for identifying and evaluating high-potential archive fashion items on the resale market. It scrapes Grailed marketplace data, scores items on scarcity/velocity/hype/momentum, predicts price trends with ML models, and presents everything in an interactive dashboard.

## LangGraph Agent Pipeline

```
User input (any keyword — English or Chinese)
↓
[preprocess]        Chinese detection → auto-translation via DeepSeek
↓
[fetch_data]        Real-time supply/demand data from Grailed Algolia API
↓
[validator]         Supply < 10? → auto-relax keyword and retry (max 2×)
↓                 ↑_____________________________|
[celebrity_signal]  Reddit + Google Trends + News RSS celebrity catalyst detection
↓
[score]             4-dimension quantitative scoring
                    (Supply/Demand 35% + Velocity 30% + Hype 25% + Momentum 10%)
↓
[analyze]           DeepSeek generates analysis report
                    buzz_level=high triggers "Celebrity Effect Window" recommendation
```

**Key capabilities:**
- Real-time analysis for any keyword — not limited to a preset list
- Chinese input auto-translation (e.g. 巴黎世家 → Balenciaga)
- Conditional edges enable autonomous retries with automatic keyword fallback
- `app.stream(stream_mode="updates")` streams live node progress to the dashboard
- Three-source celebrity catalyst aggregation; `buzz_level=high` triggers a timed buy-window recommendation

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

## AI Analysis

- **LangGraph multi-agent workflow**: preprocess → fetch_data → validator → celebrity_signal → score → analyze
- **Arbitrary keyword analysis**: not limited to a fixed brand list — any keyword works in real time
- **Chinese input auto-translation**: e.g. 巴黎世家 → Balenciaga
- **Automatic keyword relaxation**: falls back to a broader query when data is insufficient
- **Streaming progress**: each agent node reports status in real time

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

[**archive-selection-system on Streamlit Cloud**](https://archive-selection-system-2qhfvjhxgpcsauqfsqkzbm.streamlit.app/)

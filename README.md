# Archive Selection System

A quantitative analysis system for identifying and evaluating high-potential archive fashion items on the resale market. It scrapes Grailed marketplace data, scores items on scarcity / velocity / hype / momentum, predicts price trends with ML models, and presents everything in an interactive multi-page Streamlit dashboard with a live LangGraph AI agent.

## Project Structure

```
.
├── dashboard.py              # Entry point — landing page (streamlit run dashboard.py)
├── pages/
│   ├── 1_Selection.py        # Page 1: item ranking, radar chart, scatter plot
│   ├── 2_Price_Prediction.py # Page 2: LR + XGBoost forecasts, trend charts
│   └── 3_AI_Analysis.py      # Page 3: LangGraph AI agent, real-time analysis
├── lib/
│   ├── theme.py              # Shared CSS theme + set_page() / apply_theme()
│   └── data.py               # Cached data loaders (load_scorecard, load_prediction_data)
├── agent.py                  # LangGraph ReAct tool-calling agent
├── social_signals.py         # Wikipedia Pageviews + Reddit + News RSS signals
├── scorecard.py              # Weighted composite scoring (4 dimensions)
├── price_model.py            # LR + XGBoost price prediction pipeline
├── grailed_scraper.py        # Grailed Algolia API: listings / sold / totals
├── historical_scraper.py     # 180-day historical sold records
├── discovery.py              # Trending item discovery (no preset brand list)
├── run_weekly.py             # Orchestrates weekly scrape → score pipeline
├── scorecard.csv             # Latest scorecard output
├── historical_sold.csv       # 180-day sold history
└── requirements.txt
```

## System Architecture

```
Discovery           Scraping              Scoring            Prediction          Dashboard
─────────          ──────────            ──────────          ──────────          ──────────
                   grailed_scraper.py    scorecard.py        historical_         dashboard.py
discovery.py  ───> (listings/sold/       (weighted scoring   scraper.py   ───>  (Streamlit
(trend scan,        totals from           across 4            (180-day            multi-page)
 brand hype         Algolia API)          dimensions)         sold history)           │
 detection)              │                    │                   │               ┌───┴────────────────┐
                         ▼                    ▼                   ▼               │  pages/            │
                   grailed_listings.csv  scorecard.csv       historical_          │  1_Selection.py    │
                   grailed_sold.csv                          sold.csv             │  2_Price_Pred.py   │
                   grailed_totals.csv                             │               │  3_AI_Analysis.py  │
                                                            price_model.py        └────────────────────┘
                                                            (LR + XGBoost)
```

## LangGraph ReAct Agent (`feature/react-agent`)

Architecture: **ReAct (Reasoning + Acting)** via `langgraph.prebuilt.create_react_agent`.
Instead of a hard-coded DAG, the LLM autonomously decides which tools to call and in what order.

### Tool Registry

| Tool | What it does |
|------|-------------|
| `validate_brand` | DeepSeek classifier — is this archive/designer fashion? Stops pipeline if not. |
| `fetch_market_data` | Grailed Algolia API — supply count, 30-day sold, avg price, avg followers. |
| `calculate_scarcity_score` | 4-dimension log-normalised score: S/D 35% · Velocity 30% · Hype 25% · Momentum 10%. |
| `fetch_celebrity_signal` | Wikipedia Pageviews + Reddit (old.reddit.com) + News RSS — returns `buzz_level`. |
| `get_price_prediction` | Historical CSV → LR+XGBoost (if matched keyword) or simple IQR stats fallback. |

### Typical LLM Reasoning Flow

```
User: "Analyze this for archive resale: Number Nine AW03"
  │
  ├─ tool_call: validate_brand("Number Nine AW03")
  │    → is_archive=true ✓
  │
  ├─ tool_call: fetch_market_data("Number Nine AW03")
  │    → supply=689, demand_30d=17, avg_followers=84.1
  │
  ├─ tool_call: calculate_scarcity_score(689, 17, 84.1)
  │    → total_score=5.27/10, ratio=40.5
  │
  ├─ tool_call: fetch_celebrity_signal("Number Nine AW03")
  │    → buzz_level=low
  │
  ├─ tool_call: get_price_prediction("Number Nine AW03")
  │    → predicted=$218, trend=Declining (-24.5%), model=LR+XGBoost
  │
  └─ Final report: ### Recommendation / ### Market Status / ...
```

### Output Format (5 fixed sections)

```
### Recommendation
**Buy / Hold / Sell** — one sentence rationale with a specific number.

### Market Status
Supply/demand balance vs typical archive items (cite numbers).

### Suggested Price Range
Concrete USD range (e.g. $135 – $275) tied to prediction output.

### Key Risks
Single biggest downside, one sentence.

### Celebrity Hype Window          ← only when buzz_level = "high"
Celebrity name + recommended 24–48 h entry window.
```

**Key capabilities:**
- LLM controls call order — no brittle DAG edges to maintain
- Adding a new capability = add one `@tool` function, nothing else
- `analyze_item_react(keyword)` → blocking call, returns report string
- `stream_analyze_react(keyword)` → generator of LangGraph update events for live UI
- `analyze_item_full` / `analyze_item` kept as backward-compatible shims
- Wikipedia Pageviews as primary hype signal (no rate limits, no auth required)

## Modules

| Module | Description |
|--------|-------------|
| **`dashboard.py`** | Landing page — 4 overview KPI cards, navigation guide, methodology footer. |
| **`pages/1_Selection.py`** | Ranking table, radar comparison chart, bar chart, supply/demand scatter. |
| **`pages/2_Price_Prediction.py`** | Per-item ML price forecasts, MAE comparison bar chart, price trend scatter. |
| **`pages/3_AI_Analysis.py`** | Live LangGraph AI analysis: brand background, confidence badge, pageviews trend chart, analysis history. |
| **`lib/theme.py`** | `set_page()` + `apply_theme()`: injects all shared CSS across every page. |
| **`lib/data.py`** | `@st.cache_data` loaders for scorecard and prediction pipeline. |
| **`agent.py`** | **ReAct agent** (`create_react_agent`): 5 `@tool` functions, LLM decides call order. Public API: `analyze_item_react`, `stream_analyze_react`, `analyze_item_full`, `analyze_item`. |
| **`social_signals.py`** | Wikipedia Pageviews REST API, Reddit (old.reddit.com), News RSS. `_brand_root()` normalises long keywords to brand name for accurate signal fetching. |
| **`scorecard.py`** | Weighted composite score (0–10) per item. NaN-safe: missing sub-scores default to 5.0. |
| **`price_model.py`** | Trains LR + XGBoost per item using 180-day history with time-series split and 3-fold CV. |
| **`grailed_scraper.py`** | Grailed Algolia API: listings, sold, and total counts for each tracked keyword. |
| **`historical_scraper.py`** | 180-day historical sold records, incremental updates with deduplication. |
| **`discovery.py`** | Scans Grailed for trending archive items ranked by follower count, no preset brand list required. |
| **`run_weekly.py`** | Weekly orchestration: scrape → score. Run on a cron or manually each week. |

## Tech Stack

| Category | Tools |
|----------|-------|
| **Dashboard** | Streamlit (multi-page), Plotly |
| **ML / Stats** | XGBoost, scikit-learn, pandas, NumPy |
| **AI Agent** | LangGraph (`create_react_agent`), LangChain Core, LangChain OpenAI, DeepSeek API (OpenAI-compatible) |
| **Data Sources** | Grailed Algolia API, Wikipedia Pageviews REST API, old.reddit.com JSON API, News RSS |
| **HTTP** | requests |
| **Markdown rendering** | `markdown` library (LLM output → HTML) |

## Getting Started

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure the DeepSeek API key

The AI Analysis page calls the DeepSeek API. Set your key before running:

```bash
export DEEPSEEK_API_KEY="sk-..."
```

Or add it to a `.env` file and load it however you prefer (e.g. `python-dotenv`).

### 3. Run the data pipeline

```bash
# Step 1: Discover trending items (optional — edits discovery.csv)
python discovery.py

# Step 2: Scrape current market data and generate scorecard
python run_weekly.py

# Step 3: Scrape 180-day historical sold data (for Price Prediction page)
python historical_scraper.py
```

### 4. Launch the dashboard

```bash
streamlit run dashboard.py
```

Streamlit automatically detects `pages/` and generates sidebar navigation:

| Page | URL path | What it shows |
|------|----------|---------------|
| Landing | `/` | Overview KPIs, navigation guide |
| Selection Dashboard | `/Selection` | Item rankings, radar, scatter |
| Price Prediction | `/Price_Prediction` | LR + XGBoost forecasts, trend charts |
| AI Analysis | `/AI_Analysis` | Live ReAct agent — any keyword, streaming tool calls |

## Data Sources & Cloud Deployment Notes

### Why Wikipedia Pageviews instead of Google Trends

Google Trends (pytrends) rate-limits requests from shared cloud IPs (Streamlit Cloud, Heroku, etc.). Wikipedia Pageviews uses a public REST API with no authentication and no rate limits, making it reliable in all deployment environments:

```
https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/
  en.wikipedia/all-access/all-agents/{article}/daily/{start}/{end}
```

The `fetch_wikipedia_pageviews()` function in `social_signals.py` automatically tries three article name variants (`keyword`, `keyword_(brand)`, `keyword_(fashion_designer)`) and returns a 90-day daily pageview time series.

### Reddit endpoint

Uses `old.reddit.com` as the primary JSON endpoint (more permissive with automated requests) and falls back to `www.reddit.com`. Posts are filtered to fashion-related subreddits defined in `FASHION_SUB_ALLOWLIST`.

### Streamlit Cloud secrets

If deploying to Streamlit Cloud, add your DeepSeek key in **App settings → Secrets**:

```toml
DEEPSEEK_API_KEY = "sk-..."
```

Then read it in code via `st.secrets["DEEPSEEK_API_KEY"]` (already handled in `agent.py`).

## Scoring Weights

| Metric | Weight | Description |
|--------|--------|-------------|
| Supply / Demand Ratio | 35% | Listed count ÷ 30-day sold count. Lower = scarcer. |
| Velocity | 30% | Sales count in the last 30 days. Higher = more liquid. |
| Hype Score | 25% | Average followers per listing. Proxy for buyer demand. |
| Price Momentum | 10% | Recent avg price vs historical avg. Positive = rising trend. |

## Live Dashboard

[**archive-selection-system on Streamlit Cloud**](https://archive-selection-system-2qhfvjhxgpcsauqfsqkzbm.streamlit.app/)

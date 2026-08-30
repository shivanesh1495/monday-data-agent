# Skylark Drones Monday.com BI Agent

This project is a conversational business intelligence agent for Skylark Drones. It reads live data from monday.com boards, normalizes messy operational and pipeline records, and answers founder-level questions about deals, work orders, sector performance, collections, billing, and cross-board comparisons.

## What It Does

- Connects to monday.com dynamically through the GraphQL API
- Reads two boards:
  - `Work Orders`
  - `Deals`
- Normalizes inconsistent text and date fields
- Handles missing values without crashing
- Answers conversational BI questions with data-quality caveats
- Supports multi-turn clarification and memory for:
  - sector
  - metric
  - time window
  - comparison intent
- Generates a leadership-style summary view in the UI

## Architecture

The app is organized into five main modules:

- [app.py](D:/monday-data-agent/app.py:1)
  - Streamlit UI
  - Loads monday.com data
  - Builds the conversational agent
  - Renders KPI cards, chat history, and leadership summary output

- [monday_client.py](D:/monday-data-agent/monday_client.py:1)
  - monday.com GraphQL client
  - Handles auth, retries, HTTP failures, and pagination
  - Converts board items into pandas DataFrames

- [normalize.py](D:/monday-data-agent/normalize.py:1)
  - Cleans object fields
  - Normalizes fuzzy date formats
  - Fixes known messy values from imported board data

- [tools.py](D:/monday-data-agent/tools.py:1)
  - Deterministic BI calculations
  - Sector filtering
  - Historical time-window filtering
  - Pipeline, work-order, and cross-board summaries

- [agent.py](D:/monday-data-agent/agent.py:1)
  - Conversational routing layer
  - Detects intent, sector, metric, and time window
  - Accumulates multi-turn context
  - Chooses deterministic tool-backed answers before falling back to the LLM

## Data Flow

1. The app reads live board data from monday.com.
2. The raw board items are converted into pandas DataFrames.
3. Dates and text fields are normalized.
4. Quality summaries are generated for missing and incomplete fields.
5. The agent interprets the user's question.
6. Deterministic BI tools compute the answer.
7. The UI renders results along with caveats and context.

## Monday.com Setup

Create two monday.com boards from the provided assignment datasets:

1. Work Order board
2. Deal Funnel board

Use column names equivalent to the following.

### Deal Board Columns

- `Owner code`
- `Client Code`
- `Deal Status`
- `Close Date (A)`
- `Closure Probability`
- `Masked Deal value`
- `Tentative Close Date`
- `Deal Stage`
- `Product deal`
- `Sector/service`
- `Created Date`

### Work Order Board Columns

- `Customer Name Code`
- `Serial #`
- `Nature of Work`
- `Execution Status`
- `Data Delivery Date`
- `Date of PO/LOI`
- `Probable Start Date`
- `Probable End Date`
- `Sector`
- `Last invoice date`
- `Amount in Rupees (Excl of GST) (Masked)`
- `Billed Value in Rupees (Excl of GST.) (Masked)`
- `Collected Amount in Rupees (Incl of GST.) (Masked)`
- `Amount to be billed in Rs. (Exl. of GST) (Masked)`
- `Amount Receivable (Masked)`
- `Expected Billing Month`
- `Actual Collection Month`
- `Collection Date`
- `Billing Status`
- `Collection status`

The code is resilient to a few alternate column titles, but keeping the imported boards close to these names is recommended.

## Environment Variables

Use the included [`.env.example`](D:/monday-data-agent/.env.example:1) as your template.

```env
MONDAY_API_TOKEN=your_monday_api_token
WORK_ORDER_BOARD_ID=your_work_order_board_id
DEAL_FUNNEL_BOARD_ID=your_deal_funnel_board_id
GROQ_API_KEY=your_groq_api_key
```

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Running Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q -vv
```

## Hosting

### Recommended: Streamlit Community Cloud

This is the fastest path for the assignment because the app is already built with Streamlit and your Git remote already points to:

- `https://github.com/shivanesh1495/monday-data-agent.git`

Deployment steps:

1. Commit and push your latest changes to the `main` branch.
2. Open [share.streamlit.io](https://share.streamlit.io/).
3. Click `Create app`.
4. Select:
   - Repository: `shivanesh1495/monday-data-agent`
   - Branch: `main`
   - Main file path: `app.py`
5. Open `Advanced settings`.
6. Set Python to `3.11`.
7. Paste these secrets:

```toml
MONDAY_API_TOKEN="your_monday_api_token"
WORK_ORDER_BOARD_ID="your_work_order_board_id"
DEAL_FUNNEL_BOARD_ID="your_deal_funnel_board_id"
GROQ_API_KEY="your_groq_api_key"
```

8. Click `Deploy`.

Streamlit Community Cloud documentation says you create the app from your workspace, choose the repository, branch, and file path, and can set both Python version and secrets in `Advanced settings` before deployment. Sources: [Streamlit deploy overview](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app), [Streamlit deploy steps](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).

### Fallback: Render

This repo includes [render.yaml](D:/monday-data-agent/render.yaml:1) for a Render deployment.

Deployment steps:

1. Push the repo to GitHub.
2. In Render, create a new `Web Service`.
3. Connect the GitHub repository.
4. Use the included config or set:
   - Build command: `pip install -r requirements.txt`
   - Start command: `streamlit run app.py --server.address 0.0.0.0 --server.port $PORT`
5. Add these environment variables in Render:
   - `MONDAY_API_TOKEN`
   - `WORK_ORDER_BOARD_ID`
   - `DEAL_FUNNEL_BOARD_ID`
   - `GROQ_API_KEY`
6. Deploy.

Render's current docs say free web services are available, but they can spin down after 15 minutes of idle time, so this is better as a fallback demo option than the primary assignment submission path. Sources: [Render free web services](https://render.com/docs/free), [Render Streamlit guidance](https://render.com/articles/deploy-streamlit-gradio-localhost-to-live).

## Supported Question Types

- Pipeline summary by sector
- Work-order execution summary by sector
- Sector-vs-sector metric comparisons
- Deal pipeline vs work-order execution cross-reference
- Collections, billing, receivables, order-book, and win-rate questions
- Sector overview questions such as:
  - `How are we doing in Railways this quarter?`
  - `Compare win rate between Mining and Renewables`
  - `Compare collections between Railways and Powerline`

## Historical Time Windows

The agent supports:

- `last month`
- `this month`
- `last quarter`
- `this quarter`
- `last year`
- `this year`

Applied time windows are included in the answer together with:

- the date range used
- the date fields used as the filtering basis
- the number of rows excluded because no usable date was available

## Error Handling

The app handles:

- missing environment variables
- monday.com HTTP and timeout failures
- monday.com pagination
- GraphQL errors returned by monday.com
- incomplete or messy board data
- unsupported or ambiguous business questions through clarification

## Limitations

- Historical filtering depends on the available board date fields and uses best-effort date selection by metric type.
- This is a read-only monday.com integration.
- The agent is strongest on structured BI questions and less strong on completely open-ended strategic analysis.
- Hosted deployment is not included in this repository until you deploy it to Streamlit Cloud or Render.

## Submission Notes

This repository contains:

- source code
- tests
- README
- decision log
- `.env.example`
- `render.yaml`

For final submission, package the repository as a ZIP and include the hosted prototype link separately.

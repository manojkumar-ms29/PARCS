# PARCS

Predictive Analytics & Real-Time Intelligence System (PARCS) for Windows Modern Standby.

## Project Structure

```
PARCS/
│
├── src/
│   ├── collectors/   # Telemetry collectors (SleepStudy, Drivers, Updates, EventLog)
│   ├── etl/          # Validation, normalization, and Parquet persistence
│   ├── analytics/    # Baselines, anomaly detection, regressions, change correlation
│   ├── api/          # FastAPI backend services and endpoints
│   ├── dashboard/    # Streamlit visual dashboard and API client
│   ├── storage/      # Raw storage, Parquet persistence, DuckDB manager
│   └── utils/        # Serialization and synthetic demonstration fixtures
│
├── data/
│   ├── raw/          # Preserved raw JSON/HTML reports
│   ├── processed/    # Validated Parquet datasets (sleepstudy.parquet, changes.parquet)
│   └── analytics/    # Analytics artifacts
│
├── tests/            # Test suite (Collectors, ETL, Analytics, API, Dashboard, E2E)
├── requirements.txt  # Python package dependencies
└── main.py           # CLI entry point
```

## Getting Started

1. Set up a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # On Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Seed demonstration data (optional):
   ```bash
   python main.py seed-demo
   ```

4. Start FastAPI backend:
   ```bash
   python main.py api
   # Or directly:
   uvicorn src.api.app:app --host 127.0.0.1 --port 8000
   ```
   Interactive API docs are available at `http://127.0.0.1:8000/docs`.

5. Start Streamlit dashboard:
   ```bash
   python main.py dashboard
   # Or directly:
   streamlit run src/dashboard/app.py
   ```

6. Run the test suite:
   ```bash
   pytest
   ```

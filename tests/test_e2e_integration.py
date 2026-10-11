"""End-to-End Integration Test for PARCS.

Traces the complete pipeline:
Raw Ingestion -> Schema Validation -> Parquet Persistence -> DuckDB Query ->
Feature Engineering -> Baseline Readiness -> Anomaly Detection ->
Sustained Regression Detection -> Change Correlation -> API Responses.
"""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.analytics.anomaly import detect_anomalies
from src.analytics.baseline import build_baseline
from src.analytics.correlation import correlate_changes
from src.analytics.features import build_sleepstudy_features
from src.analytics.regression import detect_regressions
from src.api.app import app
from src.collectors.base import CollectorResult
from src.etl.pipeline import run_etl_pipeline
from src.storage.db import get_db_connection
from src.storage.parquet import read_parquet
from src.utils.demo_data import seed_demo_datasets

client = TestClient(app)


class TestEndToEndPipeline:
    def test_full_pipeline_trace(self, tmp_path) -> None:
        # 1. Collector Output & Ingestion
        collector_result = CollectorResult(
            collector="sleepstudy",
            collected_at="2026-09-01T14:00:00Z",
            source="mock_collector",
            data=[
                {
                    "start_time": f"2026-08-{10 + i:02d}T10:00:00Z",
                    "end_time": f"2026-08-{10 + i:02d}T10:30:00Z",
                    "duration_seconds": 1800.0,
                    "drips_percent": 95.0,
                    "battery_drain_percent": 2.0,
                    "battery_drain_rate_mw": 2500.0,
                }
                for i in range(12)
            ] + [
                {
                    "start_time": f"2026-09-01T{10 + i:02d}:00:00Z",
                    "end_time": f"2026-09-01T{10 + i:02d}:30:00Z",
                    "duration_seconds": 1800.0,
                    "drips_percent": 55.0,
                    "battery_drain_percent": 4.5,
                    "battery_drain_rate_mw": 5000.0,
                }
                for i in range(4)
            ],
        )

        # 2. ETL and Schema Validation into Parquet
        summary = run_etl_pipeline(
            collector_results=collector_result,
            machine_id="E2E-TEST-MACHINE",
            dataset_name="e2e_sessions",
            processed_dir=tmp_path,
        )
        assert summary.success is True
        assert summary.accepted_records == 16
        assert summary.rejected_records == 0

        # 3. DuckDB Querying from Parquet
        parquet_file = tmp_path / "e2e_sessions.parquet"
        assert parquet_file.exists()

        db = get_db_connection()
        try:
            db.conn.execute(f"CREATE OR REPLACE VIEW e2e_view AS SELECT * FROM '{parquet_file.as_posix()}'")
            db_df = db.query_to_df("SELECT COUNT(*) as cnt FROM e2e_view")
            assert db_df.iloc[0]["cnt"] == 16
        finally:
            db.close()

        # 4. Feature Engineering
        sessions_df = pd.read_parquet(parquet_file)
        features_df = build_sleepstudy_features(sessions_df)
        assert "duration_hours" in features_df.columns
        assert len(features_df) == 16

        # 5. Statistical Baseline (first 12 baseline observations)
        train_features = features_df.iloc[:12]
        baseline_df = build_baseline(train_features, min_observations=10)
        assert not baseline_df.empty
        ready_metrics = baseline_df[baseline_df["readiness"] == "ready"]
        assert len(ready_metrics) > 0

        # 6. Anomaly Detection on all sessions
        anomalies_df = detect_anomalies(features_df, baseline_df, threshold=3.5)
        assert not anomalies_df.empty
        # Severe drops at session index >= 12 should be flagged
        flagged_anomalies = anomalies_df[anomalies_df["is_anomaly"]]
        assert len(flagged_anomalies) > 0

        # 7. Sustained Regression Detection
        reg_df = detect_regressions(
            features=features_df,
            baseline=baseline_df,
            threshold=2.0,
            min_consecutive=3,
        )
        flagged_regs = reg_df[reg_df["is_regression"]]
        assert len(flagged_regs) >= 2  # sessions 3 and 4 in the 4-session streak

        # 8. Change Correlation
        changes_df = pd.DataFrame([
            {
                "machine_id": "E2E-TEST-MACHINE",
                "timestamp": "2026-09-01T08:30:00Z",  # Antecedent change
                "change_type": "driver",
                "change_id": "E2E-DRV-01",
                "description": "Updated Test Driver",
            }
        ])

        corr_df = correlate_changes(
            regressions=reg_df,
            changes=changes_df,
            only_regressions=True,
        )
        assert not corr_df.empty
        assert all(corr_df["is_correlated"])
        assert all(corr_df["change_id"] == "E2E-DRV-01")
        assert all(corr_df["temporal_relation"] == "before")
        assert all("causation is not asserted" in r for r in corr_df["reason"])

    def test_api_end_to_end_with_demo_seeder(self) -> None:
        # Seed demo data via API
        seed_res = client.post("/api/demo/seed")
        assert seed_res.status_code == 200

        # Query summary
        sum_res = client.get("/api/telemetry/summary")
        assert sum_res.status_code == 200
        sum_data = sum_res.json()
        assert sum_data["total_sessions"] > 0
        assert sum_data["is_synthetic"] is True

        # Query baselines for ready machine
        base_res = client.get("/api/analytics/baselines?machine_id=DEMO-MACHINE-READY")
        assert base_res.status_code == 200
        assert all(b["readiness"] == "ready" for b in base_res.json())

        # Query baselines for sparse machine
        sparse_res = client.get("/api/analytics/baselines?machine_id=DEMO-MACHINE-SPARSE")
        assert sparse_res.status_code == 200
        assert all(b["readiness"] == "insufficient_history" for b in sparse_res.json())

        # Query regressions
        reg_res = client.get("/api/analytics/regressions?machine_id=DEMO-MACHINE-READY&only_regressions=true")
        assert reg_res.status_code == 200
        regs = reg_res.json()
        assert len(regs) > 0

        # Query correlations
        corr_res = client.get("/api/analytics/correlations?machine_id=DEMO-MACHINE-READY")
        assert corr_res.status_code == 200
        corrs = corr_res.json()
        assert len(corrs) > 0
        assert any(c["is_correlated"] for c in corrs)

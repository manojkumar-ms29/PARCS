"""Tests for PARCS FastAPI backend integration."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.utils.demo_data import seed_demo_datasets

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_demo_data():
    """Ensure deterministic demo data is present for integration tests."""
    seed_demo_datasets()


class TestAPIEndpoints:
    def test_health_endpoint(self) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "PARCS API"
        assert data["version"] == "1.0.0"
        assert "timestamp" in data

    def test_telemetry_summary_with_seeded_data(self) -> None:
        response = client.get("/api/telemetry/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["total_sessions"] > 0
        assert "DEMO-MACHINE-READY" in data["machines"]
        assert "DEMO-MACHINE-SPARSE" in data["machines"]
        assert data["is_synthetic"] is True
        assert data["datasets_available"]["sleepstudy"] is True
        assert data["datasets_available"]["changes"] is True

    def test_baselines_endpoint_and_readiness_filtering(self) -> None:
        # All machines
        res_all = client.get("/api/analytics/baselines")
        assert res_all.status_code == 200
        items = res_all.json()
        assert len(items) > 0

        # Filter by DEMO-MACHINE-READY: should be 'ready'
        res_ready = client.get("/api/analytics/baselines?machine_id=DEMO-MACHINE-READY")
        assert res_ready.status_code == 200
        ready_items = res_ready.json()
        assert len(ready_items) > 0
        assert all(it["machine_id"] == "DEMO-MACHINE-READY" for it in ready_items)
        assert all(it["readiness"] == "ready" for it in ready_items)

        # Filter by DEMO-MACHINE-SPARSE: should be 'insufficient_history'
        res_sparse = client.get("/api/analytics/baselines?machine_id=DEMO-MACHINE-SPARSE")
        assert res_sparse.status_code == 200
        sparse_items = res_sparse.json()
        assert len(sparse_items) > 0
        assert all(it["machine_id"] == "DEMO-MACHINE-SPARSE" for it in sparse_items)
        assert all(it["readiness"] == "insufficient_history" for it in sparse_items)

    def test_baselines_invalid_parameters(self) -> None:
        res = client.get("/api/analytics/baselines?min_observations=0")
        assert res.status_code == 422

    def test_anomalies_endpoint(self) -> None:
        response = client.get("/api/analytics/anomalies?machine_id=DEMO-MACHINE-READY")
        assert response.status_code == 200
        items = response.json()
        assert len(items) > 0
        for item in items:
            assert "metric" in item
            assert "is_anomaly" in item
            assert "reason" in item

    def test_anomalies_invalid_threshold(self) -> None:
        res = client.get("/api/analytics/anomalies?threshold=-1.0")
        assert res.status_code == 422

    def test_regressions_endpoint(self) -> None:
        response = client.get("/api/analytics/regressions?machine_id=DEMO-MACHINE-READY")
        assert response.status_code == 200
        items = response.json()
        assert len(items) > 0

        # Should identify sustained regressions on DEMO-MACHINE-READY
        regression_flags = [it["is_regression"] for it in items]
        assert any(regression_flags)

    def test_regressions_sparse_machine_has_no_regressions(self) -> None:
        response = client.get("/api/analytics/regressions?machine_id=DEMO-MACHINE-SPARSE")
        assert response.status_code == 200
        items = response.json()
        assert len(items) > 0
        # Sparse machine has insufficient history, so is_regression must be False
        assert all(it["is_regression"] is False for it in items)
        assert all(it["status"] == "insufficient_history" for it in items)

    def test_regressions_invalid_parameters(self) -> None:
        res1 = client.get("/api/analytics/regressions?threshold=0")
        assert res1.status_code == 422
        res2 = client.get("/api/analytics/regressions?min_consecutive=0")
        assert res2.status_code == 422

    def test_correlations_endpoint(self) -> None:
        response = client.get("/api/analytics/correlations?machine_id=DEMO-MACHINE-READY")
        assert response.status_code == 200
        items = response.json()
        assert len(items) > 0

        # Verify matched change attributes
        correlated = [it for it in items if it["is_correlated"]]
        assert len(correlated) > 0
        first_corr = correlated[0]
        assert first_corr["change_id"] is not None
        assert first_corr["temporal_relation"] in ("before", "after", "concurrent")
        assert "causation is not asserted" in first_corr["reason"]

    def test_correlations_invalid_window(self) -> None:
        res = client.get("/api/analytics/correlations?window_before_hours=-5.0")
        assert res.status_code == 422

    def test_changes_endpoint(self) -> None:
        response = client.get("/api/changes?machine_id=DEMO-MACHINE-READY")
        assert response.status_code == 200
        items = response.json()
        assert len(items) > 0
        assert all(it["machine_id"] == "DEMO-MACHINE-READY" for it in items)

    def test_demo_seed_endpoint(self) -> None:
        response = client.post("/api/demo/seed")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_synthetic"] is True
        assert data["session_records"] > 0
        assert data["change_records"] > 0

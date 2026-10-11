"""Tests for the Streamlit dashboard API client and local fallback."""

from __future__ import annotations

import pytest

from src.dashboard.client import PARCSApiClient
from src.utils.demo_data import seed_demo_datasets


@pytest.fixture(autouse=True)
def setup_data():
    seed_demo_datasets()


class TestDashboardClient:
    def test_local_fallback_client_queries(self) -> None:
        # Use an invalid port to test guaranteed local fallback
        client = PARCSApiClient(base_url="http://127.0.0.1:59999", timeout=0.1)

        health = client.get_health()
        assert health["connection"] == "offline"

        summary = client.get_telemetry_summary()
        assert summary["status"] == "ok"
        assert "DEMO-MACHINE-READY" in summary["machines"]
        assert summary["is_synthetic"] is True

        baselines = client.get_baselines(machine_id="DEMO-MACHINE-READY")
        assert len(baselines) > 0
        assert all(b["readiness"] == "ready" for b in baselines)

        anomalies = client.get_anomalies(machine_id="DEMO-MACHINE-READY")
        assert len(anomalies) > 0

        regressions = client.get_regressions(machine_id="DEMO-MACHINE-READY")
        assert len(regressions) > 0

        correlations = client.get_correlations(machine_id="DEMO-MACHINE-READY")
        assert len(correlations) > 0

        changes = client.get_changes(machine_id="DEMO-MACHINE-READY")
        assert len(changes) > 0

    def test_sparse_machine_fallback(self) -> None:
        client = PARCSApiClient(base_url="http://127.0.0.1:59999", timeout=0.1)

        baselines = client.get_baselines(machine_id="DEMO-MACHINE-SPARSE")
        assert len(baselines) > 0
        assert all(b["readiness"] == "insufficient_history" for b in baselines)

        regressions = client.get_regressions(machine_id="DEMO-MACHINE-SPARSE")
        assert len(regressions) > 0
        assert all(r["status"] == "insufficient_history" for r in regressions)
        assert all(r["is_regression"] is False for r in regressions)

    def test_streamlit_app_renders_without_exceptions(self) -> None:
        from pathlib import Path
        from streamlit.testing.v1 import AppTest

        app_path = Path(__file__).resolve().parent.parent / "src" / "dashboard" / "app.py"
        at = AppTest.from_file(str(app_path), default_timeout=10.0)
        at.run()
        assert not at.exception
        assert len(at.selectbox) > 0
        assert "DEMO-MACHINE-READY" in at.selectbox[0].options
        assert len(at.tabs) == 5


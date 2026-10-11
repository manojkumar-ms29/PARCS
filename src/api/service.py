"""PARCS Analytics Service layer for FastAPI backend.

Orchestrates data loading from Parquet / DuckDB storage and executes
the existing analytics pipeline modules (features, baselines, anomalies,
regressions, change correlation) without duplicating analytics logic.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import pandas as pd

from src.analytics.anomaly import detect_anomalies
from src.analytics.baseline import build_baseline
from src.analytics.correlation import correlate_changes, normalize_changes
from src.analytics.features import build_sleepstudy_features
from src.analytics.regression import detect_regressions
from src.storage.db import get_db_connection
from src.storage.parquet import read_parquet
from src.storage.paths import PROCESSED_DIR
from src.utils.serialization import serialize_df_records

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service providing data retrieval and analytics orchestration."""

    @staticmethod
    def load_sessions_df() -> pd.DataFrame:
        """Safely load sleepstudy sessions from Parquet storage.

        Returns empty DataFrame if dataset does not exist or is unreadable.
        """
        path = PROCESSED_DIR / "sleepstudy.parquet"
        if not path.exists():
            return pd.DataFrame()
        try:
            return read_parquet("sleepstudy")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load sleepstudy dataset: %s", exc)
            return pd.DataFrame()

    @staticmethod
    def load_changes_df() -> pd.DataFrame:
        """Safely load system changes from Parquet storage.

        Returns empty DataFrame if dataset does not exist or is unreadable.
        """
        path = PROCESSED_DIR / "changes.parquet"
        if not path.exists():
            return pd.DataFrame()
        try:
            return read_parquet("changes")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load changes dataset: %s", exc)
            return pd.DataFrame()

    def get_telemetry_summary(self) -> dict[str, Any]:
        """Summarize available telemetry datasets and machines."""
        sessions_df = self.load_sessions_df()
        changes_df = self.load_changes_df()

        if sessions_df.empty:
            return {
                "total_sessions": 0,
                "total_changes": len(changes_df),
                "machines": [],
                "date_range": None,
                "datasets_available": {
                    "sleepstudy": False,
                    "changes": not changes_df.empty,
                },
                "is_synthetic": False,
                "status": "no_data",
                "message": "No sleepstudy telemetry dataset found. Please run collection or seed demo data.",
            }

        machines = sorted(sessions_df["machine_id"].dropna().unique().tolist())
        start_min = sessions_df["start_time"].min()
        end_max = sessions_df["end_time"].max()

        date_range = {
            "start": str(start_min) if pd.notna(start_min) else None,
            "end": str(end_max) if pd.notna(end_max) else None,
        }

        # Check if dataset is synthetic
        is_synthetic = bool(
            ("is_synthetic" in sessions_df.columns and sessions_df["is_synthetic"].any())
            or any(m.startswith("DEMO-") or m.startswith("SYNTHETIC-") for m in machines)
        )

        return {
            "total_sessions": len(sessions_df),
            "total_changes": len(changes_df),
            "machines": machines,
            "date_range": date_range,
            "datasets_available": {
                "sleepstudy": True,
                "changes": not changes_df.empty,
            },
            "is_synthetic": is_synthetic,
            "status": "ok",
            "message": "Telemetry dataset available.",
        }

    def get_baselines(
        self,
        machine_id: str | None = None,
        min_observations: int = 10,
    ) -> list[dict[str, Any]]:
        """Calculate and return machine statistical baselines."""
        sessions_df = self.load_sessions_df()
        if sessions_df.empty:
            return []

        if machine_id:
            sessions_df = sessions_df[sessions_df["machine_id"] == machine_id]
            if sessions_df.empty:
                return []

        features_df = build_sleepstudy_features(sessions_df)
        baseline_df = build_baseline(features_df, min_observations=min_observations)
        return serialize_df_records(baseline_df)

    def get_anomalies(
        self,
        machine_id: str | None = None,
        threshold: float = 3.5,
    ) -> list[dict[str, Any]]:
        """Detect and return statistical anomalies."""
        sessions_df = self.load_sessions_df()
        if sessions_df.empty:
            return []

        if machine_id:
            sessions_df = sessions_df[sessions_df["machine_id"] == machine_id]
            if sessions_df.empty:
                return []

        features_df = build_sleepstudy_features(sessions_df)
        baseline_df = build_baseline(features_df)
        anomalies_df = detect_anomalies(features_df, baseline_df, threshold=threshold)
        return serialize_df_records(anomalies_df)

    def get_regressions(
        self,
        machine_id: str | None = None,
        threshold: float = 2.0,
        min_consecutive: int = 3,
        only_regressions: bool = False,
    ) -> list[dict[str, Any]]:
        """Detect and return sustained performance regressions."""
        sessions_df = self.load_sessions_df()
        if sessions_df.empty:
            return []

        if machine_id:
            sessions_df = sessions_df[sessions_df["machine_id"] == machine_id]
            if sessions_df.empty:
                return []

        features_df = build_sleepstudy_features(sessions_df)
        baseline_df = build_baseline(features_df)
        reg_df = detect_regressions(
            features=features_df,
            baseline=baseline_df,
            threshold=threshold,
            min_consecutive=min_consecutive,
        )

        if only_regressions and not reg_df.empty:
            reg_df = reg_df[reg_df["is_regression"]].copy()

        return serialize_df_records(reg_df)

    def get_correlations(
        self,
        machine_id: str | None = None,
        window_before_hours: float = 24.0,
        window_after_hours: float = 2.0,
        only_regressions: bool = True,
    ) -> list[dict[str, Any]]:
        """Correlate detected regressions with system changes."""
        sessions_df = self.load_sessions_df()
        if sessions_df.empty:
            return []

        if machine_id:
            sessions_df = sessions_df[sessions_df["machine_id"] == machine_id]
            if sessions_df.empty:
                return []

        features_df = build_sleepstudy_features(sessions_df)
        baseline_df = build_baseline(features_df)
        reg_df = detect_regressions(features=features_df, baseline=baseline_df)

        changes_df = self.load_changes_df()
        if not changes_df.empty and machine_id:
            changes_df = changes_df[changes_df["machine_id"] == machine_id].copy()

        corr_df = correlate_changes(
            regressions=reg_df,
            changes=changes_df,
            window_before=timedelta(hours=window_before_hours),
            window_after=timedelta(hours=window_after_hours),
            only_regressions=only_regressions,
        )

        return serialize_df_records(corr_df)

    def get_changes(self, machine_id: str | None = None) -> list[dict[str, Any]]:
        """Retrieve system changes dataset."""
        changes_df = self.load_changes_df()
        if changes_df.empty:
            return []

        if machine_id:
            changes_df = changes_df[changes_df["machine_id"] == machine_id]

        return serialize_df_records(changes_df)

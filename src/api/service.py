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


VALID_EVALUATION_SCOPES: frozenset[str] = frozenset({"subsequent", "all"})


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
                "machine_provenance": {},
                "has_mixed_provenance": False,
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

        # Check machine-specific provenance
        machine_provenance: dict[str, bool] = {}
        for m in machines:
            m_rows = sessions_df[sessions_df["machine_id"] == m]
            if "is_synthetic" in m_rows.columns and m_rows["is_synthetic"].notna().any():
                is_m_synth = bool(m_rows["is_synthetic"].fillna(False).any())
            else:
                is_m_synth = bool(m.startswith("DEMO-") or m.startswith("SYNTHETIC-"))
            machine_provenance[m] = is_m_synth

        has_mixed_provenance = len(set(machine_provenance.values())) > 1 if machine_provenance else False
        is_synthetic = any(machine_provenance.values()) if machine_provenance else False

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
            "machine_provenance": machine_provenance,
            "has_mixed_provenance": has_mixed_provenance,
            "status": "ok",
            "message": "Telemetry dataset available.",
        }

    @staticmethod
    def partition_machine_features(
        features_df: pd.DataFrame,
        min_observations: int = 10,
        reference_count: int | None = None,
        reference_cutoff: str | pd.Timestamp | None = None,
        reference_ratio: float | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Partition feature observations for a single machine into reference and evaluation sets.

        Separates observations used to construct the reference baseline from observations
        evaluated against it, preserving temporal causality and machine isolation.

        Deterministic chronological ordering policy:
          1. start_time ascending (NaT placed last)
          2. end_time ascending
          3. _source_row_index ascending

        Partitioning policy:
          - If reference_cutoff is provided:
              reference: start_time < cutoff
              evaluation: start_time >= cutoff
          - If reference_count is provided:
              reference: first reference_count observations
              evaluation: remaining observations
          - If reference_ratio is provided:
              reference: first round(N * ratio) observations
              evaluation: remaining observations
          - Default policy (when none provided):
              - If N <= min_observations:
                  Entire dataset is reference (sparse history, unready baseline).
                  Evaluation set equals the observations, ensuring explicit
                  'insufficient_history' evaluation records are generated.
              - If N > min_observations:
                  Check for a temporal gap >= 24h occurring at or after index min_observations.
                  If a gap exists, split at the gap.
                  Otherwise, use a deterministic chronological split: first
                  max(min_observations, int(N * 0.75)) observations form the reference baseline,
                  and subsequent observations form the evaluation set.

        Returns:
            (reference_df, evaluation_df)
        """
        if features_df.empty:
            return features_df.copy(), features_df.copy()

        df = features_df.copy()
        if "_source_row_index" not in df.columns:
            df["_source_row_index"] = df.index

        # Deterministic chronological sort
        df["_sort_start"] = pd.to_datetime(df["start_time"], utc=True, errors="coerce")
        df["_sort_end"] = pd.to_datetime(df["end_time"], utc=True, errors="coerce")
        df.sort_values(
            by=["_sort_start", "_sort_end", "_source_row_index"],
            na_position="last",
            inplace=True,
        )
        sort_starts = df["_sort_start"].copy()
        sort_ends = df["_sort_end"].copy()
        df.drop(columns=["_sort_start", "_sort_end"], inplace=True, errors="ignore")

        n_rows = len(df)

        if reference_cutoff is not None:
            cutoff_ts = pd.to_datetime(reference_cutoff, utc=True)
            ref_mask = sort_starts < cutoff_ts
            ref_df = df[ref_mask].copy()
            eval_df = df[~ref_mask].copy()
            return ref_df, eval_df

        if reference_count is not None:
            k = max(0, min(reference_count, n_rows))
            ref_df = df.iloc[:k].copy()
            eval_df = df.iloc[k:].copy()
            return ref_df, eval_df

        if reference_ratio is not None:
            k = max(0, min(int(round(n_rows * reference_ratio)), n_rows))
            ref_df = df.iloc[:k].copy()
            eval_df = df.iloc[k:].copy()
            return ref_df, eval_df

        # Default policy:
        if n_rows <= min_observations:
            # Sparse machine: reference contains all available observations (yielding unready baseline)
            # evaluation contains all available observations (yielding explicit 'insufficient_history' statuses)
            return df.copy(), df.copy()

        # Check for temporal gap >= 24 hours occurring after min_observations
        split_idx: int | None = None
        for i in range(min_observations, n_rows):
            prev_end = sort_ends.iloc[i - 1]
            curr_start = sort_starts.iloc[i]
            if pd.notna(prev_end) and pd.notna(curr_start):
                if curr_start - prev_end >= pd.Timedelta(hours=24):
                    split_idx = i
                    break

        if split_idx is not None:
            ref_df = df.iloc[:split_idx].copy()
            eval_df = df.iloc[split_idx:].copy()
        else:
            k = max(min_observations, int(n_rows * 0.75))
            ref_df = df.iloc[:k].copy()
            eval_df = df.iloc[k:].copy()

        return ref_df, eval_df

    def get_baselines(
        self,
        machine_id: str | None = None,
        min_observations: int = 10,
        reference_count: int | None = None,
        reference_cutoff: str | pd.Timestamp | None = None,
    ) -> list[dict[str, Any]]:
        """Calculate and return machine statistical baselines built strictly from historical reference observations.

        Observations are partitioned deterministically per machine so that subsequent evaluation
        sessions never contaminate the reference baseline.
        """
        sessions_df = self.load_sessions_df()
        if sessions_df.empty:
            return []

        if machine_id:
            sessions_df = sessions_df[sessions_df["machine_id"] == machine_id]
            if sessions_df.empty:
                return []

        features_df = build_sleepstudy_features(sessions_df)

        baseline_dfs: list[pd.DataFrame] = []
        machines = sorted(features_df["machine_id"].dropna().unique())

        for m in machines:
            m_feat = features_df[features_df["machine_id"] == m]
            ref_df, _ = self.partition_machine_features(
                m_feat,
                min_observations=min_observations,
                reference_count=reference_count,
                reference_cutoff=reference_cutoff,
            )
            base_df = build_baseline(ref_df, min_observations=min_observations)
            baseline_dfs.append(base_df)

        if not baseline_dfs:
            return []

        combined_baseline = pd.concat(baseline_dfs, ignore_index=True)
        return serialize_df_records(combined_baseline)

    def get_anomalies(
        self,
        machine_id: str | None = None,
        threshold: float = 3.5,
        min_observations: int = 10,
        reference_count: int | None = None,
        reference_cutoff: str | pd.Timestamp | None = None,
        evaluation_scope: str = "subsequent",
    ) -> list[dict[str, Any]]:
        """Detect and return statistical anomalies evaluated against historical reference baselines."""
        if evaluation_scope not in VALID_EVALUATION_SCOPES:
            raise ValueError(
                f"Invalid evaluation_scope '{evaluation_scope}'. "
                f"Supported values: {sorted(VALID_EVALUATION_SCOPES)}"
            )

        sessions_df = self.load_sessions_df()
        if sessions_df.empty:
            return []

        if machine_id:
            sessions_df = sessions_df[sessions_df["machine_id"] == machine_id]
            if sessions_df.empty:
                return []

        features_df = build_sleepstudy_features(sessions_df)

        anomaly_dfs: list[pd.DataFrame] = []
        machines = sorted(features_df["machine_id"].dropna().unique())

        for m in machines:
            m_feat = features_df[features_df["machine_id"] == m]
            ref_df, eval_df = self.partition_machine_features(
                m_feat,
                min_observations=min_observations,
                reference_count=reference_count,
                reference_cutoff=reference_cutoff,
            )
            base_df = build_baseline(ref_df, min_observations=min_observations)

            if evaluation_scope == "subsequent":
                if eval_df.empty:
                    continue
                target_eval = eval_df
            elif evaluation_scope == "all":
                target_eval = m_feat
            else:
                raise ValueError(
                    f"Invalid evaluation_scope '{evaluation_scope}'. "
                    f"Supported values: {sorted(VALID_EVALUATION_SCOPES)}"
                )

            anom_df = detect_anomalies(target_eval, base_df, threshold=threshold)
            anomaly_dfs.append(anom_df)

        if not anomaly_dfs:
            return []

        combined_anomalies = pd.concat(anomaly_dfs, ignore_index=True)
        return serialize_df_records(combined_anomalies)

    def get_regressions(
        self,
        machine_id: str | None = None,
        threshold: float = 2.0,
        min_consecutive: int = 3,
        only_regressions: bool = False,
        min_observations: int = 10,
        reference_count: int | None = None,
        reference_cutoff: str | pd.Timestamp | None = None,
        evaluation_scope: str = "subsequent",
    ) -> list[dict[str, Any]]:
        """Detect and return sustained performance regressions evaluated against historical reference baselines."""
        if evaluation_scope not in VALID_EVALUATION_SCOPES:
            raise ValueError(
                f"Invalid evaluation_scope '{evaluation_scope}'. "
                f"Supported values: {sorted(VALID_EVALUATION_SCOPES)}"
            )

        sessions_df = self.load_sessions_df()
        if sessions_df.empty:
            return []

        if machine_id:
            sessions_df = sessions_df[sessions_df["machine_id"] == machine_id]
            if sessions_df.empty:
                return []

        features_df = build_sleepstudy_features(sessions_df)

        reg_dfs: list[pd.DataFrame] = []
        machines = sorted(features_df["machine_id"].dropna().unique())

        for m in machines:
            m_feat = features_df[features_df["machine_id"] == m]
            ref_df, eval_df = self.partition_machine_features(
                m_feat,
                min_observations=min_observations,
                reference_count=reference_count,
                reference_cutoff=reference_cutoff,
            )
            base_df = build_baseline(ref_df, min_observations=min_observations)

            if evaluation_scope == "subsequent":
                if eval_df.empty:
                    continue
                target_eval = eval_df
            elif evaluation_scope == "all":
                target_eval = m_feat
            else:
                raise ValueError(
                    f"Invalid evaluation_scope '{evaluation_scope}'. "
                    f"Supported values: {sorted(VALID_EVALUATION_SCOPES)}"
                )

            reg_df = detect_regressions(
                features=target_eval,
                baseline=base_df,
                threshold=threshold,
                min_consecutive=min_consecutive,
            )
            reg_dfs.append(reg_df)

        if not reg_dfs:
            return []

        combined_regs = pd.concat(reg_dfs, ignore_index=True)
        if only_regressions and not combined_regs.empty:
            combined_regs = combined_regs[combined_regs["is_regression"]].copy()

        return serialize_df_records(combined_regs)

    def get_correlations(
        self,
        machine_id: str | None = None,
        window_before_hours: float = 24.0,
        window_after_hours: float = 2.0,
        only_regressions: bool = True,
        threshold: float = 2.0,
        min_consecutive: int = 3,
        min_observations: int = 10,
        reference_count: int | None = None,
        reference_cutoff: str | pd.Timestamp | None = None,
        evaluation_scope: str = "subsequent",
    ) -> list[dict[str, Any]]:
        """Correlate detected regressions with system changes."""
        if evaluation_scope not in VALID_EVALUATION_SCOPES:
            raise ValueError(
                f"Invalid evaluation_scope '{evaluation_scope}'. "
                f"Supported values: {sorted(VALID_EVALUATION_SCOPES)}"
            )

        reg_records = self.get_regressions(
            machine_id=machine_id,
            threshold=threshold,
            min_consecutive=min_consecutive,
            only_regressions=False,
            min_observations=min_observations,
            reference_count=reference_count,
            reference_cutoff=reference_cutoff,
            evaluation_scope=evaluation_scope,
        )
        if not reg_records:
            return []

        reg_df = pd.DataFrame(reg_records)

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

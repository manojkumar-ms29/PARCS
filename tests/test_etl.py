"""Unit and integration tests for PARCS ETL pipeline.

Tests consumption of CollectorResult, schema normalization, measurement validation,
raw report preservation, Parquet persistence, DuckDB queryability, deduplication,
and structured error handling.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest

from src.collectors.base import CollectorResult
from src.collectors.sleepstudy import SleepStudyCollector
from src.etl.pipeline import (
    ETLCollectorError,
    ETLError,
    ETLExecutionSummary,
    ETLInputError,
    ETLPersistenceError,
    ETLPipeline,
    ETLValidationError,
    run_etl_pipeline,
)
from src.etl.transform import (
    DEFAULT_DATASET_NAME,
    SLEEPSTUDY_COLUMNS,
    RecordValidationError,
    generate_record_fingerprint,
    get_machine_id,
    parse_and_validate_timestamp,
    transform_and_validate_sleepstudy,
)
from src.storage.db import get_db_connection


# ======================================================================
# Synthetic Fixtures (not actual laptop observations)
# ======================================================================

def _make_synthetic_session(
    start_time: str = "2026-09-01T10:00:00Z",
    end_time: str = "2026-09-01T10:30:00Z",
    duration_seconds: float | None = 1800.0,
    drips_percent: float | None = 92.0,
    battery_drain_percent: float | None = 3.5,
    battery_drain_rate_mw: float | None = 4200.0,
) -> dict[str, Any]:
    """Generate a synthetic standby session dictionary."""
    return {
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": duration_seconds,
        "drips_percent": drips_percent,
        "battery_drain_percent": battery_drain_percent,
        "battery_drain_rate_mw": battery_drain_rate_mw,
    }


def _make_mock_sleepstudy_html(*sessions: dict[str, Any]) -> str:
    """Generate a mock HTML report embedding ScenarioInstances for SleepStudyCollector."""
    payload = json.dumps(list(sessions))
    return f"<!DOCTYPE html><html><body><script>{{\"ScenarioInstances\":{payload}}}</script></body></html>"


# ======================================================================
# 1. Valid SleepStudy Collector Result
# ======================================================================

class TestValidCollectorResult:
    def test_valid_sleepstudy_result_success(self, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        raw_report = tmp_path / "raw" / "report.html"
        raw_report.parent.mkdir(parents=True, exist_ok=True)
        raw_report.write_text("<html>synthetic</html>", encoding="utf-8")

        session = _make_synthetic_session()
        result = CollectorResult(
            collector="sleepstudy",
            collected_at="2026-09-01T11:00:00Z",
            source="powercfg /sleepstudy",
            data=[session],
            raw_report_path=str(raw_report),
            success=True,
        )

        pipeline = ETLPipeline(
            machine_id="TEST-MACHINE-01",
            processed_dir=processed_dir,
        )
        summary = pipeline.run(result)

        assert summary.success is True
        assert summary.error is None
        assert summary.collectors_processed == ["sleepstudy"]
        assert summary.successful_collectors == ["sleepstudy"]
        assert summary.failed_collectors == []
        assert summary.input_records == 1
        assert summary.accepted_records == 1
        assert summary.rejected_records == 0
        assert summary.records_persisted == 1
        assert len(summary.output_files) == 1

        # Check persisted parquet
        parquet_file = processed_dir / f"{DEFAULT_DATASET_NAME}.parquet"
        assert parquet_file.exists()
        df = pd.read_parquet(parquet_file)
        assert len(df) == 1
        assert df.iloc[0]["machine_id"] == "TEST-MACHINE-01"
        assert df.iloc[0]["duration_seconds"] == 1800.0


# ======================================================================
# 2. Multiple Standby Sessions
# ======================================================================

class TestMultipleSessions:
    def test_multiple_standby_sessions_persisted(self, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        s1 = _make_synthetic_session("2026-09-01T08:00:00Z", "2026-09-01T09:00:00Z", 3600.0, 95.0, 2.0, 3000.0)
        s2 = _make_synthetic_session("2026-09-01T12:00:00Z", "2026-09-01T12:30:00Z", 1800.0, 88.0, 1.5, 3500.0)
        s3 = _make_synthetic_session("2026-09-01T15:00:00Z", "2026-09-01T16:00:00Z", 3600.0, 90.0, 2.5, 3200.0)

        result = CollectorResult(
            collector="sleepstudy",
            collected_at="2026-09-01T17:00:00Z",
            source="powercfg /sleepstudy",
            data=[s1, s2, s3],
            success=True,
        )

        pipeline = ETLPipeline(machine_id="TEST-MACHINE-01", processed_dir=processed_dir)
        summary = pipeline.run(result)

        assert summary.success is True
        assert summary.input_records == 3
        assert summary.accepted_records == 3
        assert summary.records_persisted == 3

        df = pd.read_parquet(processed_dir / f"{DEFAULT_DATASET_NAME}.parquet")
        assert len(df) == 3


# ======================================================================
# 3. Missing Optional Measurements
# ======================================================================

class TestMissingOptionalMeasurements:
    def test_missing_optional_measurements_remain_null(self, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        # Session with missing DRIPS and battery measurements (e.g. on AC or active)
        session = _make_synthetic_session(
            duration_seconds=1200.0,
            drips_percent=None,
            battery_drain_percent=None,
            battery_drain_rate_mw=None,
        )

        result = CollectorResult(
            collector="sleepstudy",
            collected_at="2026-09-01T11:00:00Z",
            source="powercfg /sleepstudy",
            data=[session],
            success=True,
        )

        pipeline = ETLPipeline(machine_id="TEST-MACHINE-01", processed_dir=processed_dir)
        summary = pipeline.run(result)

        assert summary.success is True
        assert summary.accepted_records == 1

        df = pd.read_parquet(processed_dir / f"{DEFAULT_DATASET_NAME}.parquet")
        row = df.iloc[0]
        # Crucial requirement: missing measurements must remain null, NOT zero!
        assert pd.isna(row["drips_percent"])
        assert pd.isna(row["battery_drain_percent"])
        assert pd.isna(row["battery_drain_rate_mw"])
        assert row["drips_percent"] != 0
        assert row["battery_drain_percent"] != 0
        assert row["battery_drain_rate_mw"] != 0


# ======================================================================
# 4. Invalid Numerical Values
# ======================================================================

class TestInvalidNumericalValues:
    def test_invalid_numerical_values_rejected(self, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        invalid_sessions = [
            _make_synthetic_session(drips_percent=125.0),  # DRIPS > 100
            _make_synthetic_session(drips_percent=-5.0),   # DRIPS < 0
            _make_synthetic_session(battery_drain_percent=105.0),  # drain % > 100
            _make_synthetic_session(battery_drain_percent=-1.0),   # drain % < 0
            _make_synthetic_session(battery_drain_rate_mw=-500.0), # rate < 0
            _make_synthetic_session(duration_seconds=-60.0),       # duration < 0
            _make_synthetic_session(),  # 1 valid session
        ]

        result = CollectorResult(
            collector="sleepstudy",
            collected_at="2026-09-01T11:00:00Z",
            source="powercfg /sleepstudy",
            data=invalid_sessions,
            success=True,
        )

        pipeline = ETLPipeline(machine_id="TEST-MACHINE-01", processed_dir=processed_dir)
        summary = pipeline.run(result)

        assert summary.input_records == 7
        assert summary.accepted_records == 1
        assert summary.rejected_records == 6
        assert len(summary.validation_errors) == 6

        # Only the valid record is persisted
        assert summary.records_persisted == 1
        df = pd.read_parquet(processed_dir / f"{DEFAULT_DATASET_NAME}.parquet")
        assert len(df) == 1

        # Check validation errors mention the fields
        error_fields = {err.field for err in summary.validation_errors}
        assert "drips_percent" in error_fields
        assert "battery_drain_percent" in error_fields
        assert "battery_drain_rate_mw" in error_fields
        assert "duration_seconds" in error_fields


# ======================================================================
# 5. Failed Collector Result
# ======================================================================

class TestFailedCollectorResult:
    def test_failed_collector_does_not_produce_successful_empty_dataset(self, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        failed_result = CollectorResult(
            collector="sleepstudy",
            collected_at="2026-09-01T11:00:00Z",
            source="powercfg /sleepstudy",
            data=None,
            success=False,
            error="powercfg failed: Administrator privileges required",
        )

        pipeline = ETLPipeline(machine_id="TEST-MACHINE-01", processed_dir=processed_dir)
        summary = pipeline.run(failed_result)

        assert summary.success is False
        assert "Administrator privileges" in summary.error
        assert "sleepstudy" in summary.failed_collectors
        assert summary.accepted_records == 0
        assert summary.records_persisted == 0

        # Parquet dataset should NOT be created
        parquet_file = processed_dir / f"{DEFAULT_DATASET_NAME}.parquet"
        assert not parquet_file.exists()

    def test_failed_collector_raises_when_requested(self, tmp_path: Path) -> None:
        failed_result = CollectorResult(
            collector="sleepstudy",
            collected_at="2026-09-01T11:00:00Z",
            source="powercfg",
            data=None,
            success=False,
            error="Access denied",
        )
        pipeline = ETLPipeline(machine_id="TEST-MACHINE-01", processed_dir=tmp_path)
        with pytest.raises(ETLCollectorError, match="Access denied"):
            pipeline.run(failed_result, raise_on_error=True)


# ======================================================================
# 6. Empty Successful Result
# ======================================================================

class TestEmptySuccessfulResult:
    def test_empty_successful_result_handles_cleanly(self, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        empty_result = CollectorResult(
            collector="sleepstudy",
            collected_at="2026-09-01T11:00:00Z",
            source="powercfg /sleepstudy",
            data=[],
            success=True,
            error=None,
        )

        pipeline = ETLPipeline(machine_id="TEST-MACHINE-01", processed_dir=processed_dir)
        summary = pipeline.run(empty_result)

        assert summary.success is True
        assert summary.input_records == 0
        assert summary.accepted_records == 0
        assert summary.rejected_records == 0
        assert summary.records_persisted == 0
        assert summary.error is None


# ======================================================================
# 7. Malformed Input Records
# ======================================================================

class TestMalformedInputRecords:
    def test_malformed_input_records_rejected(self, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        malformed_data = [
            "not a dictionary",
            12345,
            None,
            {"some_key": "missing required start and end times"},
        ]

        result = CollectorResult(
            collector="sleepstudy",
            collected_at="2026-09-01T11:00:00Z",
            source="powercfg /sleepstudy",
            data=malformed_data,
            success=True,
        )

        pipeline = ETLPipeline(machine_id="TEST-MACHINE-01", processed_dir=processed_dir)
        summary = pipeline.run(result)

        assert summary.input_records == 4
        assert summary.accepted_records == 0
        assert summary.rejected_records == 4
        assert summary.success is False  # All input records failed validation
        assert len(summary.validation_errors) >= 4

    def test_invalid_data_container_type_reports_error(self, tmp_path: Path) -> None:
        result = CollectorResult(
            collector="sleepstudy",
            collected_at="2026-09-01T11:00:00Z",
            source="powercfg",
            data="plain string instead of list",  # Invalid container
            success=True,
        )
        pipeline = ETLPipeline(machine_id="TEST-MACHINE-01", processed_dir=tmp_path)
        summary = pipeline.run(result)
        assert summary.success is False
        assert "invalid data type" in summary.error


# ======================================================================
# 8. Raw Report Preservation
# ======================================================================

class TestRawReportPreservation:
    def test_raw_report_preserved_without_modification(self, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        raw_report = tmp_path / "raw" / "source_sleepstudy.html"
        raw_report.parent.mkdir(parents=True, exist_ok=True)
        original_content = "<html><head><title>Original Report</title></head><body>Data</body></html>"
        raw_report.write_text(original_content, encoding="utf-8")

        result = CollectorResult(
            collector="sleepstudy",
            collected_at="2026-09-01T11:00:00Z",
            source="powercfg /sleepstudy",
            data=[_make_synthetic_session()],
            raw_report_path=str(raw_report),
            success=True,
        )

        pipeline = ETLPipeline(machine_id="TEST-MACHINE-01", processed_dir=processed_dir)
        pipeline.run(result)

        # Raw report must still exist and be completely unaltered
        assert raw_report.exists()
        assert raw_report.read_text(encoding="utf-8") == original_content

    def test_in_memory_data_preserved_to_raw_storage(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        result = CollectorResult(
            collector="sleepstudy",
            collected_at="2026-09-01T11:00:00Z",
            source="powercfg /sleepstudy",
            data=[_make_synthetic_session()],
            raw_report_path=None,  # No existing report path
            success=True,
        )

        pipeline = ETLPipeline(
            machine_id="TEST-MACHINE-01",
            processed_dir=tmp_path / "processed",
            raw_dir=raw_dir,
        )
        pipeline.run(result)

        # Should preserve raw JSON and update raw_report_path
        assert result.raw_report_path is not None
        assert Path(result.raw_report_path).exists()


# ======================================================================
# 9. Parquet Write and Read
# ======================================================================

class TestParquetWriteAndRead:
    def test_parquet_schema_and_types_match_contract(self, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        session = _make_synthetic_session(
            duration_seconds=2400.0,
            drips_percent=91.0,
            battery_drain_percent=5.0,
            battery_drain_rate_mw=5200.0,
        )
        result = CollectorResult(
            collector="sleepstudy",
            collected_at="2026-09-01T12:00:00Z",
            source="powercfg",
            data=[session],
            success=True,
        )

        pipeline = ETLPipeline(machine_id="TEST-MACHINE-01", processed_dir=processed_dir)
        pipeline.run(result)

        df = pd.read_parquet(processed_dir / f"{DEFAULT_DATASET_NAME}.parquet")
        assert list(df.columns) == SLEEPSTUDY_COLUMNS
        assert pd.api.types.is_string_dtype(df["machine_id"])
        assert pd.api.types.is_float_dtype(df["duration_seconds"])
        assert pd.api.types.is_float_dtype(df["drips_percent"])
        assert pd.api.types.is_float_dtype(df["battery_drain_percent"])
        assert pd.api.types.is_float_dtype(df["battery_drain_rate_mw"])


# ======================================================================
# 10. DuckDB Queries Against Persisted Dataset
# ======================================================================

class TestDuckDBQueries:
    def test_duckdb_queries_persisted_dataset(self, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        sessions = [
            _make_synthetic_session("2026-09-01T08:00:00Z", "2026-09-01T09:00:00Z", 3600.0, 90.0, 2.0, 3000.0),
            _make_synthetic_session("2026-09-01T10:00:00Z", "2026-09-01T11:00:00Z", 3600.0, 96.0, 1.5, 2500.0),
        ]
        result = CollectorResult(
            collector="sleepstudy",
            collected_at="2026-09-01T12:00:00Z",
            source="powercfg",
            data=sessions,
            success=True,
        )

        pipeline = ETLPipeline(machine_id="TEST-MACHINE-01", processed_dir=processed_dir)
        pipeline.run(result)

        # Query using pipeline helper
        query_sql = f"""
            SELECT 
                COUNT(*) as total_sessions,
                AVG(duration_seconds) as avg_duration,
                AVG(drips_percent) as avg_drips,
                MIN(battery_drain_percent) as min_drain
            FROM {DEFAULT_DATASET_NAME}
        """
        result_df = pipeline.query(query_sql)

        assert len(result_df) == 1
        assert result_df.iloc[0]["total_sessions"] == 2
        assert result_df.iloc[0]["avg_duration"] == 3600.0
        assert result_df.iloc[0]["avg_drips"] == 93.0
        assert result_df.iloc[0]["min_drain"] == 1.5


# ======================================================================
# 11. Duplicate Processing Behavior (Deduplication)
# ======================================================================

class TestDuplicateProcessingBehavior:
    def test_reprocessing_same_report_is_deterministic(self, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        sessions = [
            _make_synthetic_session("2026-09-01T08:00:00Z", "2026-09-01T09:00:00Z", 3600.0, 90.0),
            _make_synthetic_session("2026-09-01T10:00:00Z", "2026-09-01T11:00:00Z", 3600.0, 95.0),
        ]
        result = CollectorResult(
            collector="sleepstudy",
            collected_at="2026-09-01T12:00:00Z",
            source="powercfg",
            data=sessions,
            success=True,
        )

        pipeline = ETLPipeline(machine_id="TEST-MACHINE-01", processed_dir=processed_dir)

        # Run 1
        summary1 = pipeline.run(result)
        assert summary1.records_persisted == 2

        # Run 2 with identical CollectorResult
        summary2 = pipeline.run(result)
        assert summary2.input_records == 2
        assert summary2.accepted_records == 2
        assert summary2.records_persisted == 2  # Not 4!

        df = pd.read_parquet(processed_dir / f"{DEFAULT_DATASET_NAME}.parquet")
        assert len(df) == 2

    def test_overlapping_session_updates_with_latest_ingestion(self, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        s1 = _make_synthetic_session("2026-09-01T08:00:00Z", "2026-09-01T09:00:00Z", 3600.0, 90.0, battery_drain_rate_mw=3000.0)
        s1_updated = _make_synthetic_session("2026-09-01T08:00:00Z", "2026-09-01T09:00:00Z", 3600.0, 90.0, battery_drain_rate_mw=3100.0)
        s2_new = _make_synthetic_session("2026-09-01T14:00:00Z", "2026-09-01T15:00:00Z", 3600.0, 85.0)

        pipeline = ETLPipeline(machine_id="TEST-MACHINE-01", processed_dir=processed_dir)

        # Ingestion 1
        r1 = CollectorResult("sleepstudy", "2026-09-01T10:00:00Z", "powercfg", [s1], success=True)
        pipeline.run(r1)

        # Ingestion 2
        r2 = CollectorResult("sleepstudy", "2026-09-01T16:00:00Z", "powercfg", [s1_updated, s2_new], success=True)
        summary2 = pipeline.run(r2)

        assert summary2.records_persisted == 2
        df = pd.read_parquet(processed_dir / f"{DEFAULT_DATASET_NAME}.parquet")
        assert len(df) == 2
        # The updated measurement should be present
        matching = df[df["start_time"] == "2026-09-01T08:00:00Z"]
        assert matching.iloc[0]["battery_drain_rate_mw"] == 3100.0


# ======================================================================
# 12. Persistence Failure Handling
# ======================================================================

class TestPersistenceFailureHandling:
    def test_persistence_failure_restores_backup_and_reports_error(self, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        pipeline = ETLPipeline(machine_id="TEST-MACHINE-01", processed_dir=processed_dir)

        # 1. Seed initial data
        s1 = _make_synthetic_session("2026-09-01T08:00:00Z", "2026-09-01T09:00:00Z", 3600.0)
        r1 = CollectorResult("sleepstudy", "2026-09-01T10:00:00Z", "powercfg", [s1], success=True)
        summary1 = pipeline.run(r1)
        assert summary1.success is True

        parquet_file = processed_dir / f"{DEFAULT_DATASET_NAME}.parquet"
        assert parquet_file.exists()
        initial_df = pd.read_parquet(parquet_file)
        assert len(initial_df) == 1

        # 2. Simulate persistence failure on second run
        s2 = _make_synthetic_session("2026-09-01T11:00:00Z", "2026-09-01T12:00:00Z", 3600.0)
        r2 = CollectorResult("sleepstudy", "2026-09-01T13:00:00Z", "powercfg", [s2], success=True)

        with patch.object(pd.DataFrame, "to_parquet", side_effect=IOError("Simulated disk error")):
            summary2 = pipeline.run(r2)

        # Must report failure
        assert summary2.success is False
        assert "Persistence failure" in summary2.error

        # Original parquet file must remain intact and uncorrupted
        assert parquet_file.exists()
        preserved_df = pd.read_parquet(parquet_file)
        assert len(preserved_df) == 1
        assert preserved_df.iloc[0]["start_time"] == "2026-09-01T08:00:00Z"

    def test_persistence_failure_raises_when_requested(self, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        pipeline = ETLPipeline(machine_id="TEST-MACHINE-01", processed_dir=processed_dir)
        r = CollectorResult("sleepstudy", "2026-09-01T10:00:00Z", "powercfg", [_make_synthetic_session()], success=True)

        with patch.object(pd.DataFrame, "to_parquet", side_effect=IOError("Simulated write error")):
            with pytest.raises(ETLPersistenceError, match="Simulated write error"):
                pipeline.run(r, raise_on_error=True)


# ======================================================================
# 13. Machine Identity Preservation
# ======================================================================

class TestMachineIdentity:
    def test_explicit_machine_id_preserved(self, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        result = CollectorResult("sleepstudy", "2026-09-01T10:00:00Z", "powercfg", [_make_synthetic_session()], success=True)
        pipeline = ETLPipeline(machine_id="DESKTOP-ALPHA-42", processed_dir=processed_dir)
        pipeline.run(result)

        df = pd.read_parquet(processed_dir / f"{DEFAULT_DATASET_NAME}.parquet")
        assert df.iloc[0]["machine_id"] == "DESKTOP-ALPHA-42"

    def test_environment_machine_id_used_when_not_provided(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("PARCS_MACHINE_ID", "SERVER-BETA-88")
        processed_dir = tmp_path / "processed"
        result = CollectorResult("sleepstudy", "2026-09-01T10:00:00Z", "powercfg", [_make_synthetic_session()], success=True)
        pipeline = ETLPipeline(machine_id=None, processed_dir=processed_dir)
        pipeline.run(result)

        df = pd.read_parquet(processed_dir / f"{DEFAULT_DATASET_NAME}.parquet")
        assert df.iloc[0]["machine_id"] == "SERVER-BETA-88"

    def test_machine_identity_is_deterministic(self) -> None:
        id1 = get_machine_id()
        id2 = get_machine_id()
        assert id1 == id2
        assert len(id1) > 0


# ======================================================================
# 14. Timestamp Normalization and Invalid Timestamps
# ======================================================================

class TestTimestamps:
    def test_iso_utc_timestamps_normalized(self) -> None:
        dt, s = parse_and_validate_timestamp("2026-09-01T14:30:00Z", "start_time")
        assert s == "2026-09-01T14:30:00Z"
        assert dt.tzinfo is not None

    def test_inverted_timestamps_rejected(self, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        inverted_session = _make_synthetic_session(
            start_time="2026-09-01T15:00:00Z",
            end_time="2026-09-01T14:00:00Z",  # Inverted!
        )
        result = CollectorResult("sleepstudy", "2026-09-01T16:00:00Z", "powercfg", [inverted_session], success=True)
        pipeline = ETLPipeline(machine_id="TEST-MACHINE-01", processed_dir=processed_dir)
        summary = pipeline.run(result)

        assert summary.rejected_records == 1
        assert summary.accepted_records == 0
        assert summary.validation_errors[0].field == "time_range"

    def test_unparseable_timestamp_rejected(self, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        bad_session = _make_synthetic_session(start_time="not-a-valid-date")
        result = CollectorResult("sleepstudy", "2026-09-01T16:00:00Z", "powercfg", [bad_session], success=True)
        pipeline = ETLPipeline(machine_id="TEST-MACHINE-01", processed_dir=processed_dir)
        summary = pipeline.run(result)

        assert summary.rejected_records == 1
        assert summary.validation_errors[0].field == "start_time"

    def test_missing_start_time_rejected(self, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        bad_session = _make_synthetic_session(start_time=None)
        result = CollectorResult("sleepstudy", "2026-09-01T16:00:00Z", "powercfg", [bad_session], success=True)
        pipeline = ETLPipeline(machine_id="TEST-MACHINE-01", processed_dir=processed_dir)
        summary = pipeline.run(result)

        assert summary.rejected_records == 1
        assert summary.validation_errors[0].field == "start_time"


# ======================================================================
# 15. Collector Integration (End-to-End with SleepStudyCollector)
# ======================================================================

class TestEndToEndCollectorIntegration:
    def test_collector_result_flows_into_etl_pipeline(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        processed_dir = tmp_path / "processed"

        # Mock HTML report with 2 sessions
        s1 = {
            "Type": 2,
            "SessionId": 1,
            "EntryTimestampLocal": "2026-09-01T15:30:00Z",
            "ExitTimestampLocal": "2026-09-01T16:11:00Z",
            "Duration": 2_460_000_000,
            "OnAc": False,
            "BatteryCountChanged": False,
            "EntryRemainingCapacity": 40_000,
            "EntryFullChargeCapacity": 50_000,
            "ExitRemainingCapacity": 35_000,
            "Metadata": {
                "Values": [
                    {"Key": "Info.SwLowPowerStateTime", "Value": 22_140_000_000},
                ]
            },
        }
        s2 = {
            "Type": 1,
            "SessionId": 2,
            "EntryTimestampLocal": "2026-09-01T17:00:00Z",
            "ExitTimestampLocal": "2026-09-01T17:30:00Z",
            "Duration": 1_800_000_000,
            "OnAc": True,  # on AC -> battery drain should be None
            "Metadata": {"Values": []},
        }
        report_path = raw_dir / "sleepstudy_mock.html"
        report_path.write_text(_make_mock_sleepstudy_html(s1, s2), encoding="utf-8")

        # 1. Run actual SleepStudyCollector
        collector = SleepStudyCollector(data_dir=raw_dir, report_path=report_path)
        collector_result = collector.collect()

        assert collector_result.success is True
        assert len(collector_result.data) == 2

        # 2. Feed collector result directly into ETL pipeline
        pipeline = ETLPipeline(
            machine_id="SYNTHETIC-HOST",
            processed_dir=processed_dir,
            raw_dir=raw_dir,
        )
        summary = pipeline.run(collector_result)

        assert summary.success is True
        assert summary.input_records == 2
        assert summary.accepted_records == 2
        assert summary.records_persisted == 2

        # 3. Query DuckDB to verify
        df = pipeline.query(f"SELECT * FROM {DEFAULT_DATASET_NAME} ORDER BY start_time")
        assert len(df) == 2
        # Session 1: DRIPS computed
        assert df.iloc[0]["drips_percent"] == 90.0
        assert df.iloc[0]["battery_drain_percent"] == 10.0
        # Session 2: On AC -> battery drain is null
        assert pd.isna(df.iloc[1]["battery_drain_percent"])

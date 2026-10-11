"""Tests for SleepStudy ETL Pipeline.

Covers parsing, schema transformation, DRIPS/battery calculation accuracy,
idempotency, deduplication, error handling, failure preservation, and DuckDB integration.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest

from src.etl.sleepstudy import (
    ETLError,
    ETLParseError,
    SCHEMA_COLUMNS,
    generate_session_key,
    load_and_deduplicate,
    parse_sleepstudy_payload,
    run_sleepstudy_etl,
    transform_standby_sessions,
)
from src.storage.db import get_db_connection
from src.storage.parquet import read_parquet, write_parquet
from src.storage.paths import PROCESSED_DIR, RAW_DIR, ensure_storage_dirs


# ======================================================================
# Fixtures and Helpers
# ======================================================================

def _make_full_report(
    *sessions: dict[str, Any],
    computer_name: str = "TEST-PC",
    report_guid: str = "11111111-2222-3333-4444-555555555555",
) -> str:
    """Create a mock SleepStudy HTML report with LocalSprData payload."""
    payload = {
        "ReportInformation": {
            "ReportVersion": "1.1",
            "ReportGuid": report_guid,
            "ScanTime": "2026-09-02T14:07:26Z",
        },
        "SystemInformation": {
            "ComputerName": computer_name,
            "SystemManufacturer": "TestOEM",
            "SystemProductName": "TestModel",
            "BIOSVersion": "1.0",
            "OSBuild": "26100.1",
        },
        "ScenarioInstances": list(sessions),
    }
    return f"<!DOCTYPE html><html><head></head><body><script>var LocalSprData = {json.dumps(payload)};</script></body></html>"


def _make_minimal_report(*sessions: dict[str, Any]) -> str:
    """Create a minimal mock HTML report with only ScenarioInstances array."""
    blob = json.dumps(list(sessions))
    return f'<html><script>{{"ScenarioInstances":{blob}}}</script></html>'


SAMPLE_STANDBY_TYPE2: dict[str, Any] = {
    "Type": 2,
    "SessionId": 10,
    "EntryTimestamp": "2026-09-01T10:00:00Z",
    "ExitTimestamp": "2026-09-01T10:41:00Z",
    "Duration": 2_460_000_000,  # 2460 seconds
    "OnAc": False,
    "BatteryCountChanged": False,
    "EntryRemainingCapacity": 40_000,
    "EntryFullChargeCapacity": 50_000,
    "ExitRemainingCapacity": 35_000,
    "ExitFullChargeCapacity": 50_000,
    "EnterReason": "Transition To Sleep",
    "ExitReason": "Input Keyboard",
    "Metadata": {
        "Values": [
            {"Key": "Info.SwLowPowerStateTime", "Value": 22_140_000_000},
            {"Key": "Info.HwLowPowerStateTime", "Value": 20_000_000_000},
        ]
    },
}

SAMPLE_SCREEN_OFF_TYPE1: dict[str, Any] = {
    "Type": 1,
    "SessionId": 11,
    "EntryTimestamp": "2026-09-01T11:00:00Z",
    "ExitTimestamp": "2026-09-01T11:05:00Z",
    "Duration": 300_000_000,  # 300 seconds
    "OnAc": True,
    "BatteryCountChanged": False,
    "EntryRemainingCapacity": 50_000,
    "EntryFullChargeCapacity": 50_000,
    "ExitRemainingCapacity": 50_000,
    "ExitFullChargeCapacity": 50_000,
    "EnterReason": "Power Button",
    "ExitReason": "Lid",
    "Metadata": {"Values": []},
}

SAMPLE_ACTIVE_TYPE0: dict[str, Any] = {
    "Type": 0,
    "SessionId": 12,
    "EntryTimestamp": "2026-09-01T12:00:00Z",
    "ExitTimestamp": "2026-09-01T13:00:00Z",
    "Duration": 3_600_000_000,
    "OnAc": False,
    "EnterReason": "Initialization",
    "ExitReason": "SwitchToAC",
}

SAMPLE_SHUTDOWN_TYPE7: dict[str, Any] = {
    "Type": 7,
    "SessionId": 13,
    "EntryTimestamp": "2026-09-01T20:00:00Z",
    "ExitTimestamp": "2026-09-02T08:00:00Z",
    "Duration": 43_200_000_000,
    "OnAc": False,
}


@pytest.fixture
def cleanup_standby_parquet():
    """Ensure standby_sessions.parquet is cleaned up before and after test."""
    p = PROCESSED_DIR / "standby_sessions.parquet"
    bak = PROCESSED_DIR / "standby_sessions.parquet.bak"
    for f in (p, bak):
        if f.exists():
            f.unlink()
    yield
    for f in (p, bak):
        if f.exists():
            f.unlink()


# ======================================================================
# 1. Parsing and Extraction Tests
# ======================================================================

class TestParsingAndExtraction:
    def test_parse_valid_full_report(self) -> None:
        html = _make_full_report(SAMPLE_STANDBY_TYPE2, computer_name="MY-LAPTOP")
        header, scenarios = parse_sleepstudy_payload(html)

        assert header["SystemInformation"]["ComputerName"] == "MY-LAPTOP"
        assert header["ReportInformation"]["ReportVersion"] == "1.1"
        assert len(scenarios) == 1
        assert scenarios[0]["SessionId"] == 10

    def test_parse_fallback_minimal_report(self) -> None:
        html = _make_minimal_report(SAMPLE_STANDBY_TYPE2)
        header, scenarios = parse_sleepstudy_payload(html)

        assert header["SystemInformation"]["ComputerName"] == "UNKNOWN"
        assert len(scenarios) == 1
        assert scenarios[0]["Type"] == 2

    def test_extract_multiple_sessions(self) -> None:
        html = _make_full_report(SAMPLE_STANDBY_TYPE2, SAMPLE_SCREEN_OFF_TYPE1)
        header, scenarios = parse_sleepstudy_payload(html)
        df = transform_standby_sessions(header, scenarios, "mock.html")

        assert len(df) == 2
        assert set(df["session_type"]) == {1, 2}

    def test_filter_includes_only_types_1_and_2(self) -> None:
        html = _make_full_report(
            SAMPLE_STANDBY_TYPE2,
            SAMPLE_SCREEN_OFF_TYPE1,
            SAMPLE_ACTIVE_TYPE0,
            SAMPLE_SHUTDOWN_TYPE7,
        )
        header, scenarios = parse_sleepstudy_payload(html)
        df = transform_standby_sessions(header, scenarios, "mock.html")

        # Must include Type 1 and Type 2, strictly excluding Types 0 and 7
        assert len(df) == 2
        assert list(df["session_type"]) == [2, 1]
        assert list(df["session_type_name"]) == ["Modern Standby", "Screen Off"]


# ======================================================================
# 2. Calculations and Formula Accuracy
# ======================================================================

class TestCalculationsAndFormulas:
    def test_drips_formula_sw_and_hw(self) -> None:
        html = _make_full_report(SAMPLE_STANDBY_TYPE2)
        header, scenarios = parse_sleepstudy_payload(html)
        df = transform_standby_sessions(header, scenarios, "mock.html")

        # SW DRIPS: round(22_140_000_000 / 2_460_000_000 * 10) = 90.0
        # HW DRIPS: round(20_000_000_000 / 2_460_000_000 * 10) = 81.0
        assert df.iloc[0]["drips_percent"] == 90.0
        assert df.iloc[0]["hw_drips_percent"] == 81.0

    def test_hw_drips_none_when_sw_drips_is_zero(self) -> None:
        s = {
            **SAMPLE_STANDBY_TYPE2,
            "Metadata": {
                "Values": [
                    {"Key": "Info.SwLowPowerStateTime", "Value": 0},
                    {"Key": "Info.HwLowPowerStateTime", "Value": 10_000_000_000},
                ]
            },
        }
        html = _make_full_report(s)
        header, scenarios = parse_sleepstudy_payload(html)
        df = transform_standby_sessions(header, scenarios, "mock.html")

        assert df.iloc[0]["drips_percent"] == 0.0
        assert pd.isna(df.iloc[0]["hw_drips_percent"])

    def test_drips_none_when_missing_metadata(self) -> None:
        html = _make_full_report(SAMPLE_SCREEN_OFF_TYPE1)  # has empty Metadata.Values
        header, scenarios = parse_sleepstudy_payload(html)
        df = transform_standby_sessions(header, scenarios, "mock.html")

        assert pd.isna(df.iloc[0]["drips_percent"])
        assert pd.isna(df.iloc[0]["hw_drips_percent"])

    def test_battery_drain_calculations(self) -> None:
        html = _make_full_report(SAMPLE_STANDBY_TYPE2)
        header, scenarios = parse_sleepstudy_payload(html)
        df = transform_standby_sessions(header, scenarios, "mock.html")

        # discharge = 40000 - 35000 = 5000 mWh
        # drain_percent = round(100 * 5000 / 50000, 1) = 10.0%
        # drain_rate_mw = round(5000 * 3_600_000_000 / 2_460_000_000) = 7317 mW
        assert df.iloc[0]["battery_drain_mwh"] == 5000.0
        assert df.iloc[0]["battery_drain_percent"] == 10.0
        assert df.iloc[0]["battery_drain_rate_mw"] == 7317.0

    def test_battery_drain_none_on_ac_power(self) -> None:
        html = _make_full_report(SAMPLE_SCREEN_OFF_TYPE1)  # OnAc: True
        header, scenarios = parse_sleepstudy_payload(html)
        df = transform_standby_sessions(header, scenarios, "mock.html")

        assert bool(df.iloc[0]["on_ac"]) is True
        assert pd.isna(df.iloc[0]["battery_drain_mwh"])
        assert pd.isna(df.iloc[0]["battery_drain_percent"])
        assert pd.isna(df.iloc[0]["battery_drain_rate_mw"])

    def test_battery_drain_none_when_charging(self) -> None:
        charging_session = {
            **SAMPLE_STANDBY_TYPE2,
            "EntryRemainingCapacity": 30_000,
            "ExitRemainingCapacity": 40_000,  # Gained capacity!
        }
        html = _make_full_report(charging_session)
        header, scenarios = parse_sleepstudy_payload(html)
        df = transform_standby_sessions(header, scenarios, "mock.html")

        assert pd.isna(df.iloc[0]["battery_drain_mwh"])
        assert pd.isna(df.iloc[0]["battery_drain_percent"])
        assert pd.isna(df.iloc[0]["battery_drain_rate_mw"])

    def test_battery_drain_none_when_battery_count_changed(self) -> None:
        s = {**SAMPLE_STANDBY_TYPE2, "BatteryCountChanged": True}
        html = _make_full_report(s)
        header, scenarios = parse_sleepstudy_payload(html)
        df = transform_standby_sessions(header, scenarios, "mock.html")

        assert pd.isna(df.iloc[0]["battery_drain_mwh"])
        assert pd.isna(df.iloc[0]["battery_drain_percent"])
        assert pd.isna(df.iloc[0]["battery_drain_rate_mw"])


# ======================================================================
# 3. Schema, Types, and Deterministic Keys
# ======================================================================

class TestSchemaAndKeys:
    def test_deterministic_session_key(self) -> None:
        key1 = generate_session_key("HOST1", "2026-09-01T10:00:00Z", "2026-09-01T11:00:00Z", 2)
        key2 = generate_session_key("HOST1", "2026-09-01T10:00:00Z", "2026-09-01T11:00:00Z", 2)
        key_diff = generate_session_key("HOST2", "2026-09-01T10:00:00Z", "2026-09-01T11:00:00Z", 2)

        assert key1 == key2
        assert len(key1) == 32
        assert key1 != key_diff

    def test_timestamp_normalization(self) -> None:
        html = _make_full_report(SAMPLE_STANDBY_TYPE2)
        header, scenarios = parse_sleepstudy_payload(html)
        df = transform_standby_sessions(header, scenarios, "mock.html")

        assert df.iloc[0]["start_time"].tzinfo is not None
        assert df.iloc[0]["end_time"].tzinfo is not None
        assert df.iloc[0]["duration_seconds"] == 2460.0

    def test_parquet_schema_and_types(self, cleanup_standby_parquet) -> None:
        html = _make_full_report(SAMPLE_STANDBY_TYPE2, SAMPLE_SCREEN_OFF_TYPE1)
        res = run_sleepstudy_etl(html_content=html)
        assert res.success is True

        df = read_parquet("standby_sessions")
        assert list(df.columns) == SCHEMA_COLUMNS
        assert df["session_id"].dtype == "int32"
        assert df["session_type"].dtype == "int16"
        assert df["duration_seconds"].dtype == "float64"
        assert df["on_ac"].dtype == "bool"


# ======================================================================
# 4. Validation and Error Handling
# ======================================================================

class TestValidationAndErrorHandling:
    def test_malformed_html_raises_parse_error(self, cleanup_standby_parquet) -> None:
        with pytest.raises(ETLParseError, match="No valid SleepStudy payload"):
            run_sleepstudy_etl(html_content="<html><body><h1>No data</h1></body></html>")

    def test_empty_html_raises_parse_error(self, cleanup_standby_parquet) -> None:
        with pytest.raises(ETLParseError, match="empty"):
            run_sleepstudy_etl(html_content="   ")

    def test_malformed_json_raises_parse_error(self, cleanup_standby_parquet) -> None:
        with pytest.raises(ETLParseError, match="Malformed JSON"):
            run_sleepstudy_etl(html_content="<script>var LocalSprData = {not valid json};</script>")

    def test_invalid_timestamps_rejected(self) -> None:
        inverted = {
            **SAMPLE_STANDBY_TYPE2,
            "EntryTimestamp": "2026-09-01T12:00:00Z",
            "ExitTimestamp": "2026-09-01T10:00:00Z",  # Inverted!
        }
        html = _make_full_report(inverted)
        header, scenarios = parse_sleepstudy_payload(html)
        df = transform_standby_sessions(header, scenarios, "mock.html")

        # Inverted row must be dropped
        assert len(df) == 0

    def test_missing_optional_fields_uses_defaults(self) -> None:
        minimal_session = {
            "Type": 2,
            "SessionId": 99,
            "EntryTimestamp": "2026-09-01T10:00:00Z",
            "ExitTimestamp": "2026-09-01T10:10:00Z",
            "Duration": 600_000_000,
        }
        html = _make_full_report(minimal_session)
        header, scenarios = parse_sleepstudy_payload(html)
        df = transform_standby_sessions(header, scenarios, "mock.html")

        assert len(df) == 1
        assert df.iloc[0]["enter_reason"] == "Unknown"
        assert df.iloc[0]["exit_reason"] == "Unknown"
        assert bool(df.iloc[0]["on_ac"]) is False

    def test_empty_report_does_not_crash(self, cleanup_standby_parquet) -> None:
        html = _make_full_report()  # No sessions
        res = run_sleepstudy_etl(html_content=html)
        assert res.success is True
        assert res.records_extracted == 0
        assert res.records_persisted == 0


# ======================================================================
# 5. Idempotency, Deduplication, and Crash Safety
# ======================================================================

class TestIdempotencyAndDeduplication:
    def test_repeated_runs_are_idempotent(self, cleanup_standby_parquet) -> None:
        html = _make_full_report(SAMPLE_STANDBY_TYPE2, SAMPLE_SCREEN_OFF_TYPE1)

        res1 = run_sleepstudy_etl(html_content=html)
        assert res1.records_extracted == 2
        assert res1.records_persisted == 2

        # Second run with exact same content
        res2 = run_sleepstudy_etl(html_content=html)
        assert res2.records_extracted == 2
        assert res2.records_persisted == 2

        df = read_parquet("standby_sessions")
        assert len(df) == 2

    def test_overlapping_reports_merged(self, cleanup_standby_parquet) -> None:
        session_a = {**SAMPLE_STANDBY_TYPE2, "SessionId": 1}
        session_b = {**SAMPLE_SCREEN_OFF_TYPE1, "SessionId": 2}
        session_c = {
            **SAMPLE_STANDBY_TYPE2,
            "SessionId": 3,
            "EntryTimestamp": "2026-09-01T15:00:00Z",
            "ExitTimestamp": "2026-09-01T16:00:00Z",
        }

        # Report 1 has A and B
        html1 = _make_full_report(session_a, session_b)
        run_sleepstudy_etl(html_content=html1)

        # Report 2 has B (overlapping) and C (new)
        html2 = _make_full_report(session_b, session_c)
        res2 = run_sleepstudy_etl(html_content=html2)

        df = read_parquet("standby_sessions")
        # Should have exactly 3 unique sessions (A, B, C)
        assert len(df) == 3
        assert res2.records_persisted == 3

    def test_conflicting_duplicate_resolution(self, cleanup_standby_parquet) -> None:
        # Same session key, but second ingestion has updated reasons
        s1 = {**SAMPLE_STANDBY_TYPE2, "ExitReason": "Unknown"}
        s2 = {**SAMPLE_STANDBY_TYPE2, "ExitReason": "Input Keyboard"}

        html1 = _make_full_report(s1)
        run_sleepstudy_etl(html_content=html1)

        html2 = _make_full_report(s2)
        run_sleepstudy_etl(html_content=html2)

        df = read_parquet("standby_sessions")
        assert len(df) == 1
        assert df.iloc[0]["exit_reason"] == "Input Keyboard"

    def test_preservation_of_existing_data_on_write_failure(self, cleanup_standby_parquet) -> None:
        # First, seed valid data
        html = _make_full_report(SAMPLE_STANDBY_TYPE2)
        run_sleepstudy_etl(html_content=html)
        initial_df = read_parquet("standby_sessions")
        assert len(initial_df) == 1

        # Now attempt to load corrupted or failing write
        new_row = pd.DataFrame([{"invalid": "data"}])

        with patch("src.etl.sleepstudy.write_parquet", side_effect=IOError("Simulated disk error")):
            with pytest.raises(IOError, match="Simulated disk error"):
                load_and_deduplicate(new_row, "standby_sessions")

        # Existing parquet must still be intact and uncorrupted!
        preserved_df = read_parquet("standby_sessions")
        assert len(preserved_df) == 1
        assert preserved_df.iloc[0]["session_key"] == initial_df.iloc[0]["session_key"]


# ======================================================================
# 6. DuckDB Query Integration
# ======================================================================

class TestDuckDBIntegration:
    def test_duckdb_queries_standby_sessions(self, cleanup_standby_parquet) -> None:
        html = _make_full_report(SAMPLE_STANDBY_TYPE2, SAMPLE_SCREEN_OFF_TYPE1)
        run_sleepstudy_etl(html_content=html)

        db = get_db_connection()
        query_sql = """
            SELECT 
                session_type_name,
                COUNT(*) as count,
                AVG(duration_seconds) as avg_duration,
                AVG(drips_percent) as avg_drips
            FROM standby_sessions
            GROUP BY session_type_name
            ORDER BY session_type_name
        """
        result = db.query_dataset("standby_sessions", query_sql).df()
        db.close()

        assert len(result) == 2
        names = list(result["session_type_name"])
        assert "Modern Standby" in names
        assert "Screen Off" in names


# ======================================================================
# 7. Real Available Report Ingestion
# ======================================================================

class TestRealReportIngestion:
    def test_process_actual_available_report(self, cleanup_standby_parquet) -> None:
        real_reports = list(RAW_DIR.glob("sleepstudy-*.html"))
        if not real_reports:
            pytest.skip("No real SleepStudy reports available in data/raw/")

        target_report = real_reports[0]
        result = run_sleepstudy_etl(report_path=target_report)

        assert result.success is True
        assert result.records_extracted == 12  # Verified from report structure
        assert result.records_persisted == 12

        df = read_parquet("standby_sessions")
        assert len(df) == 12
        assert set(df["session_type"]).issubset({1, 2})
        assert df["computer_name"].iloc[0] == "MANOJ"

        # DuckDB query check on real data
        db = get_db_connection()
        stats = db.query_dataset(
            "standby_sessions",
            "SELECT COUNT(*) as n, AVG(duration_seconds) as avg_dur FROM standby_sessions"
        ).df()
        db.close()

        assert stats.iloc[0]["n"] == 12
        assert stats.iloc[0]["avg_dur"] > 0

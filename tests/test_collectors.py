"""Tests for the SleepStudy collector.

Uses mock HTML fixtures — does not require administrator privileges or a
real SleepStudy report to run.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from src.collectors.base import BaseCollector, CollectorResult
from src.collectors.sleepstudy import SleepStudyCollector


# ======================================================================
# Fixtures / helpers
# ======================================================================

def _make_report(*sessions: dict[str, Any]) -> str:
    """Wrap session dicts in a minimal SleepStudy-style HTML string."""
    blob = json.dumps(list(sessions))
    return (
        '<!DOCTYPE html><html><head><title>System Power Report</title></head>'
        "<body><script>"
        f'{{"ScenarioInstances":{blob}}}'
        "</script></body></html>"
    )


def _write_report(tmp: Path, *sessions: dict[str, Any]) -> Path:
    """Write a mock report file and return its path."""
    path = tmp / "sleepstudy.html"
    path.write_text(_make_report(*sessions), encoding="utf-8")
    return path


# A well-formed Modern Standby session with all six fields computable.
STANDBY_SESSION: dict[str, Any] = {
    "Type": 2,
    "SessionId": 1,
    "ActivityLevel": 0,
    "EnterReason": "Power Button",
    "ExitReason": "Input Keyboard",
    "EntryTimestamp": "2026-09-01T10:00:00Z",
    "EntryTimestampLocal": "2026-09-01T15:30:00Z",
    "ExitTimestamp": "2026-09-01T10:41:00Z",
    "ExitTimestampLocal": "2026-09-01T16:11:00Z",
    "Duration": 2_460_000_000,  # 2 460 seconds in microseconds
    "OnAc": False,
    "BatteryCountChanged": False,
    "EntryRemainingCapacity": 40_000,  # mWh
    "EntryFullChargeCapacity": 50_000,
    "ExitRemainingCapacity": 35_000,
    "ExitFullChargeCapacity": 50_000,
    "HasTraceSessionData": True,
    "Metadata": {
        "FriendlyName": "Detailed Session Information",
        "Values": [
            {"Key": "Info.SwLowPowerStateTime", "Value": 22_140_000_000},
            {"Key": "Info.HwLowPowerStateTime", "Value": 20_000_000_000},
        ],
    },
}

# Active session (Type 0) — DRIPS not applicable.
ACTIVE_SESSION: dict[str, Any] = {
    "Type": 0,
    "SessionId": 2,
    "EntryTimestampLocal": "2026-09-01T12:00:00Z",
    "ExitTimestampLocal": "2026-09-01T13:00:00Z",
    "Duration": 3_600_000_000,  # 3 600 seconds
    "OnAc": False,
    "BatteryCountChanged": False,
    "EntryRemainingCapacity": 45_000,
    "EntryFullChargeCapacity": 50_000,
    "ExitRemainingCapacity": 40_000,
    "ExitFullChargeCapacity": 50_000,
    "Metadata": {"Values": []},
}

# Shutdown session (Type 7) — no battery/DRIPS fields expected.
SHUTDOWN_SESSION: dict[str, Any] = {
    "Type": 7,
    "SessionId": 3,
    "EntryTimestampLocal": "2026-09-01T20:00:00Z",
    "ExitTimestampLocal": "2026-09-02T08:00:00Z",
    "Duration": 43_200_000_000,
    "OnAc": False,
    "BatteryCountChanged": False,
    "EntryRemainingCapacity": 50_000,
    "EntryFullChargeCapacity": 50_000,
    "ExitRemainingCapacity": 50_000,
    "ExitFullChargeCapacity": 50_000,
    "Metadata": {"Values": []},
}


# ======================================================================
# 1. Successful report generation / parsing
# ======================================================================


class TestSuccessfulParsing:
    """Verify end-to-end parsing of a valid mock report."""

    def test_parse_valid_report_returns_success(self, tmp_path: Path) -> None:
        report = _write_report(tmp_path, STANDBY_SESSION)
        collector = SleepStudyCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()

        assert result.success is True
        assert result.error is None
        assert result.collector == "sleepstudy"
        assert result.source == "powercfg /sleepstudy"
        assert result.collected_at  # non-empty ISO string
        assert result.raw_report_path is not None

    def test_parse_returns_correct_session_count(self, tmp_path: Path) -> None:
        report = _write_report(tmp_path, STANDBY_SESSION, ACTIVE_SESSION)
        collector = SleepStudyCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()

        assert isinstance(result.data, list)
        assert len(result.data) == 2

    def test_raw_report_preserved(self, tmp_path: Path) -> None:
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        report = _write_report(src_dir, STANDBY_SESSION)

        raw_dir = tmp_path / "raw"
        collector = SleepStudyCollector(data_dir=raw_dir, report_path=report)
        result = collector.collect()

        assert result.raw_report_path is not None
        assert Path(result.raw_report_path).exists()
        assert Path(result.raw_report_path).parent.resolve() == raw_dir.resolve()


# ======================================================================
# 2. Valid session extraction — all six fields
# ======================================================================


class TestSessionExtraction:
    """Verify correct extraction of the six required fields."""

    @pytest.fixture()
    def session(self, tmp_path: Path) -> dict[str, Any]:
        report = _write_report(tmp_path, STANDBY_SESSION)
        collector = SleepStudyCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert result.data
        return result.data[0]

    def test_start_time(self, session: dict) -> None:
        assert session["start_time"] == "2026-09-01T15:30:00Z"

    def test_end_time(self, session: dict) -> None:
        assert session["end_time"] == "2026-09-01T16:11:00Z"

    def test_duration_seconds(self, session: dict) -> None:
        assert session["duration_seconds"] == 2460.0

    def test_drips_percent(self, session: dict) -> None:
        # round(22_140_000_000 / 2_460_000_000 * 10) = round(90.0) = 90
        assert session["drips_percent"] == 90

    def test_battery_drain_percent(self, session: dict) -> None:
        # round(100 * 5000 / 50000, 1) = 10.0
        assert session["battery_drain_percent"] == 10.0

    def test_battery_drain_rate_mw(self, session: dict) -> None:
        # round(5000 * 3_600_000_000 / 2_460_000_000) = round(7317.07) = 7317
        assert session["battery_drain_rate_mw"] == 7317

    def test_active_session_no_drips(self, tmp_path: Path) -> None:
        report = _write_report(tmp_path, ACTIVE_SESSION)
        collector = SleepStudyCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert result.data[0]["drips_percent"] is None

    def test_shutdown_session_no_battery(self, tmp_path: Path) -> None:
        report = _write_report(tmp_path, SHUTDOWN_SESSION)
        collector = SleepStudyCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        s = result.data[0]
        assert s["drips_percent"] is None
        assert s["battery_drain_percent"] is None
        assert s["battery_drain_rate_mw"] is None


# ======================================================================
# 3. Missing / optional fields
# ======================================================================


class TestMissingFields:
    """Return None when optional data is absent rather than crashing."""

    def test_no_drips_metadata(self, tmp_path: Path) -> None:
        session = {**STANDBY_SESSION, "Metadata": {"Values": []}}
        report = _write_report(tmp_path, session)
        collector = SleepStudyCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert result.data[0]["drips_percent"] is None

    def test_no_metadata_key(self, tmp_path: Path) -> None:
        session = {k: v for k, v in STANDBY_SESSION.items() if k != "Metadata"}
        report = _write_report(tmp_path, session)
        collector = SleepStudyCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert result.data[0]["drips_percent"] is None

    def test_zero_duration(self, tmp_path: Path) -> None:
        session = {**STANDBY_SESSION, "Duration": 0}
        report = _write_report(tmp_path, session)
        collector = SleepStudyCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        s = result.data[0]
        assert s["duration_seconds"] is None
        assert s["drips_percent"] is None

    def test_battery_count_changed(self, tmp_path: Path) -> None:
        session = {**STANDBY_SESSION, "BatteryCountChanged": True}
        report = _write_report(tmp_path, session)
        collector = SleepStudyCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        s = result.data[0]
        assert s["battery_drain_percent"] is None
        assert s["battery_drain_rate_mw"] is None

    def test_battery_charging_returns_none(self, tmp_path: Path) -> None:
        """Battery gained charge → drain fields should be None."""
        session = {
            **STANDBY_SESSION,
            "EntryRemainingCapacity": 35_000,
            "ExitRemainingCapacity": 40_000,
        }
        report = _write_report(tmp_path, session)
        collector = SleepStudyCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        s = result.data[0]
        assert s["battery_drain_percent"] is None
        assert s["battery_drain_rate_mw"] is None

    def test_missing_timestamps_fallback(self, tmp_path: Path) -> None:
        """If local timestamps are absent, fall back to UTC timestamps."""
        session = {
            "Type": 2,
            "SessionId": 5,
            "EntryTimestamp": "2026-09-01T10:00:00Z",
            "ExitTimestamp": "2026-09-01T11:00:00Z",
            "Duration": 3_600_000_000,
            "Metadata": {"Values": []},
        }
        report = _write_report(tmp_path, session)
        collector = SleepStudyCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        s = result.data[0]
        assert s["start_time"] == "2026-09-01T10:00:00Z"
        assert s["end_time"] == "2026-09-01T11:00:00Z"

    def test_zero_full_charge_capacity(self, tmp_path: Path) -> None:
        session = {**STANDBY_SESSION, "EntryFullChargeCapacity": 0}
        report = _write_report(tmp_path, session)
        collector = SleepStudyCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        s = result.data[0]
        assert s["battery_drain_percent"] is None
        assert s["battery_drain_rate_mw"] is None


# ======================================================================
# 4. powercfg failure
# ======================================================================


class TestPowercfgFailure:
    """Handle subprocess failures gracefully."""

    @patch("src.collectors.sleepstudy.subprocess.run")
    def test_nonzero_returncode(self, mock_run: Any, tmp_path: Path) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "powercfg /sleepstudy", stderr="requires admin"
        )
        collector = SleepStudyCollector(data_dir=tmp_path)
        result = collector.collect()

        assert result.success is False
        assert "powercfg failed" in result.error
        assert result.data is None

    @patch("src.collectors.sleepstudy.subprocess.run")
    def test_permission_error(self, mock_run: Any, tmp_path: Path) -> None:
        mock_run.side_effect = PermissionError("Access denied")
        collector = SleepStudyCollector(data_dir=tmp_path)
        result = collector.collect()

        assert result.success is False
        assert "Administrator privileges" in result.error

    @patch("src.collectors.sleepstudy.platform.system", return_value="Linux")
    def test_non_windows_os(self, _mock: Any, tmp_path: Path) -> None:
        collector = SleepStudyCollector(data_dir=tmp_path)
        result = collector.collect()

        assert result.success is False
        assert "Windows" in result.error


# ======================================================================
# 5. Missing report
# ======================================================================


class TestMissingReport:
    """Handle missing report files gracefully."""

    def test_report_path_does_not_exist(self, tmp_path: Path) -> None:
        collector = SleepStudyCollector(
            data_dir=tmp_path,
            report_path=tmp_path / "nonexistent.html",
        )
        result = collector.collect()

        assert result.success is False
        assert "not found" in result.error.lower()

    @patch("src.collectors.sleepstudy.subprocess.run")
    def test_powercfg_succeeds_but_file_missing(
        self, mock_run: Any, tmp_path: Path
    ) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["powercfg"], returncode=0, stdout="", stderr=""
        )
        collector = SleepStudyCollector(data_dir=tmp_path)
        result = collector.collect()

        assert result.success is False
        assert "not found" in result.error.lower()


# ======================================================================
# 6. Malformed / unexpected report structure
# ======================================================================


class TestMalformedReport:
    """Handle unexpected report content without crashing."""

    def test_no_scenario_instances_marker(self, tmp_path: Path) -> None:
        report = tmp_path / "bad.html"
        report.write_text("<html><body>No data here</body></html>", encoding="utf-8")
        collector = SleepStudyCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()

        assert result.success is False
        assert "ScenarioInstances" in result.error

    def test_empty_scenario_instances(self, tmp_path: Path) -> None:
        report = tmp_path / "empty.html"
        report.write_text(
            '{"ScenarioInstances":[]}', encoding="utf-8"
        )
        collector = SleepStudyCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()

        assert result.success is True
        assert result.data == []

    def test_truncated_json(self, tmp_path: Path) -> None:
        report = tmp_path / "trunc.html"
        report.write_text(
            '{"ScenarioInstances":[{"Type":1', encoding="utf-8"
        )
        collector = SleepStudyCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()

        assert result.success is False
        assert "Unterminated" in result.error or "Invalid" in result.error

    def test_invalid_json_in_array(self, tmp_path: Path) -> None:
        report = tmp_path / "invalid.html"
        report.write_text(
            '{"ScenarioInstances":[not valid json]}', encoding="utf-8"
        )
        collector = SleepStudyCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()

        assert result.success is False

    def test_session_with_only_type(self, tmp_path: Path) -> None:
        """A minimal session dict should still produce a result (mostly None)."""
        report = _write_report(tmp_path, {"Type": 2})
        collector = SleepStudyCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()

        assert result.success is True
        s = result.data[0]
        assert s["start_time"] is None
        assert s["end_time"] is None
        assert s["duration_seconds"] is None
        assert s["drips_percent"] is None
        assert s["battery_drain_percent"] is None
        assert s["battery_drain_rate_mw"] is None


# ======================================================================
# BaseCollector contract
# ======================================================================


class TestBaseCollectorContract:
    """SleepStudyCollector must satisfy the BaseCollector interface."""

    def test_is_subclass(self) -> None:
        assert issubclass(SleepStudyCollector, BaseCollector)

    def test_name_property(self) -> None:
        collector = SleepStudyCollector()
        assert collector.name == "sleepstudy"

    def test_collect_returns_collector_result(self, tmp_path: Path) -> None:
        report = _write_report(tmp_path, STANDBY_SESSION)
        collector = SleepStudyCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert isinstance(result, CollectorResult)

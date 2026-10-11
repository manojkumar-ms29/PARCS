"""Tests for the EventLog collector."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from src.collectors.base import BaseCollector, CollectorResult
from src.collectors.eventlog import EventLogCollector


# ======================================================================
# Fixtures / helpers
# ======================================================================

def _write_report(tmp: Path, *events: dict[str, Any]) -> Path:
    """Write a mock JSON report file and return its path."""
    path = tmp / "eventlog.json"
    path.write_text(json.dumps(list(events)), encoding="utf-8")
    return path


VALID_EVENT: dict[str, Any] = {
    "timestamp": "2026-09-01T10:05:00.0000000Z",
    "event_id": 506,
    "provider": "Microsoft-Windows-Kernel-Power",
    "level": "Information",
    "log_name": "System",
    "message": "The system is entering connected standby",
}

WARNING_EVENT: dict[str, Any] = {
    "timestamp": "2026-09-01T10:10:00.0000000Z",
    "event_id": 219,
    "provider": "Microsoft-Windows-Kernel-PnP",
    "level": "Warning",
    "log_name": "System",
    "message": "The driver \\Driver\\WudfRd failed to load for the device.",
}

# ======================================================================
# 1. Successful report generation / parsing
# ======================================================================

class TestSuccessfulParsing:
    @pytest.fixture
    def times(self) -> tuple[datetime, datetime]:
        start = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        end = datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc)
        return start, end

    def test_parse_valid_report_returns_success(self, tmp_path: Path, times: tuple[datetime, datetime]) -> None:
        start, end = times
        report = _write_report(tmp_path, VALID_EVENT)
        collector = EventLogCollector(start_time=start, end_time=end, data_dir=tmp_path, report_path=report)
        result = collector.collect()

        assert result.success is True
        assert result.error is None
        assert result.collector == "eventlog"
        assert result.source == "powershell Get-WinEvent"
        assert result.collected_at
        assert result.raw_report_path is not None

    def test_parse_returns_correct_event_count(self, tmp_path: Path, times: tuple[datetime, datetime]) -> None:
        start, end = times
        report = _write_report(tmp_path, VALID_EVENT, WARNING_EVENT)
        collector = EventLogCollector(start_time=start, end_time=end, data_dir=tmp_path, report_path=report)
        result = collector.collect()

        assert isinstance(result.data, list)
        assert len(result.data) == 2

    def test_raw_report_preserved(self, tmp_path: Path, times: tuple[datetime, datetime]) -> None:
        start, end = times
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        report = _write_report(src_dir, VALID_EVENT)

        raw_dir = tmp_path / "raw"
        collector = EventLogCollector(start_time=start, end_time=end, data_dir=raw_dir, report_path=report)
        result = collector.collect()

        assert result.raw_report_path is not None
        assert Path(result.raw_report_path).exists()
        assert Path(result.raw_report_path).parent.resolve() == raw_dir.resolve()

# ======================================================================
# 2. Valid event extraction
# ======================================================================

class TestEventExtraction:
    @pytest.fixture
    def event(self, tmp_path: Path) -> dict[str, Any]:
        start = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        end = datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc)
        report = _write_report(tmp_path, VALID_EVENT)
        collector = EventLogCollector(start_time=start, end_time=end, data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert result.data
        return result.data[0]

    def test_timestamp(self, event: dict) -> None:
        assert event["timestamp"] == "2026-09-01T10:05:00.0000000Z"

    def test_event_id(self, event: dict) -> None:
        assert event["event_id"] == 506

    def test_provider(self, event: dict) -> None:
        assert event["provider"] == "Microsoft-Windows-Kernel-Power"

    def test_level(self, event: dict) -> None:
        assert event["level"] == "Information"

    def test_log_name(self, event: dict) -> None:
        assert event["log_name"] == "System"

    def test_message(self, event: dict) -> None:
        assert event["message"] == "The system is entering connected standby"

    def test_null_message(self, tmp_path: Path) -> None:
        start = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        end = datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc)
        session = {**VALID_EVENT, "message": None}
        report = _write_report(tmp_path, session)
        collector = EventLogCollector(start_time=start, end_time=end, data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert result.data[0]["message"] == ""

# ======================================================================
# 3. Empty / Malformed Results
# ======================================================================

class TestEmptyMalformedResults:
    @pytest.fixture
    def times(self) -> tuple[datetime, datetime]:
        start = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        end = datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc)
        return start, end

    def test_empty_results(self, tmp_path: Path, times: tuple[datetime, datetime]) -> None:
        start, end = times
        report = tmp_path / "empty.json"
        report.write_text("[]", encoding="utf-8")
        collector = EventLogCollector(start_time=start, end_time=end, data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert result.success is True
        assert result.data == []

    def test_malformed_json(self, tmp_path: Path, times: tuple[datetime, datetime]) -> None:
        start, end = times
        report = tmp_path / "bad.json"
        report.write_text("[{bad json", encoding="utf-8")
        collector = EventLogCollector(start_time=start, end_time=end, data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert result.success is False
        assert "Malformed JSON" in result.error

    def test_empty_file(self, tmp_path: Path, times: tuple[datetime, datetime]) -> None:
        start, end = times
        report = tmp_path / "empty_file.json"
        report.write_text("", encoding="utf-8")
        collector = EventLogCollector(start_time=start, end_time=end, data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert result.success is True
        assert result.data == []

    def test_single_object_result(self, tmp_path: Path, times: tuple[datetime, datetime]) -> None:
        start, end = times
        report = tmp_path / "single.json"
        report.write_text(json.dumps(VALID_EVENT), encoding="utf-8")
        collector = EventLogCollector(start_time=start, end_time=end, data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert result.success is True
        assert len(result.data) == 1

# ======================================================================
# 4. Command/API Failures and Environment
# ======================================================================

class TestFailures:
    @pytest.fixture
    def times(self) -> tuple[datetime, datetime]:
        start = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        end = datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc)
        return start, end

    @patch("src.collectors.eventlog.subprocess.run")
    def test_nonzero_returncode(self, mock_run: Any, tmp_path: Path, times: tuple[datetime, datetime]) -> None:
        start, end = times
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "powershell Get-WinEvent", stderr="requires admin"
        )
        collector = EventLogCollector(start_time=start, end_time=end, data_dir=tmp_path)
        result = collector.collect()

        assert result.success is False
        assert "powershell failed" in result.error
        assert result.data is None

    @patch("src.collectors.eventlog.subprocess.run")
    def test_permission_error(self, mock_run: Any, tmp_path: Path, times: tuple[datetime, datetime]) -> None:
        start, end = times
        mock_run.side_effect = PermissionError("Access denied")
        collector = EventLogCollector(start_time=start, end_time=end, data_dir=tmp_path)
        result = collector.collect()

        assert result.success is False
        assert "Administrator privileges" in result.error

    @patch("src.collectors.eventlog.platform.system", return_value="Linux")
    def test_non_windows_os(self, _mock: Any, tmp_path: Path, times: tuple[datetime, datetime]) -> None:
        start, end = times
        collector = EventLogCollector(start_time=start, end_time=end, data_dir=tmp_path)
        result = collector.collect()

        assert result.success is False
        assert "Windows" in result.error

    def test_missing_report_file(self, tmp_path: Path, times: tuple[datetime, datetime]) -> None:
        start, end = times
        collector = EventLogCollector(start_time=start, end_time=end, data_dir=tmp_path, report_path=tmp_path / "missing.json")
        result = collector.collect()
        
        assert result.success is False
        assert "not found" in result.error.lower()

    def test_invalid_time_range(self, tmp_path: Path) -> None:
        start = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
        end = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc) # end is before start
        collector = EventLogCollector(start_time=start, end_time=end, data_dir=tmp_path)
        result = collector.collect()
        
        assert result.success is False
        assert "start_time cannot be after end_time" in result.error

# ======================================================================
# BaseCollector contract
# ======================================================================

class TestBaseCollectorContract:
    def test_is_subclass(self) -> None:
        assert issubclass(EventLogCollector, BaseCollector)

    def test_name_property(self) -> None:
        start = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        end = datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc)
        collector = EventLogCollector(start_time=start, end_time=end)
        assert collector.name == "eventlog"

    def test_collect_returns_collector_result(self, tmp_path: Path) -> None:
        start = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        end = datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc)
        report = _write_report(tmp_path, VALID_EVENT)
        collector = EventLogCollector(start_time=start, end_time=end, data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert isinstance(result, CollectorResult)

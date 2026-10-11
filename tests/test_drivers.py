"""Tests for the Driver collector."""

from __future__ import annotations

import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from src.collectors.base import BaseCollector, CollectorResult
from src.collectors.drivers import DriverCollector


# ======================================================================
# Fixtures / helpers
# ======================================================================

def _write_report(tmp: Path, *drivers: dict[str, Any]) -> Path:
    """Write a mock JSON report file and return its path."""
    path = tmp / "drivers.json"
    path.write_text(json.dumps(list(drivers)), encoding="utf-8")
    return path


VALID_DRIVER: dict[str, Any] = {
    "device_name": "Intel(R) Wi-Fi 6 AX201 160MHz",
    "friendly_name": "Intel(R) Wi-Fi 6 AX201 160MHz",
    "provider": "Intel",
    "version": "22.130.0.5",
    "date": "2022-03-22T00:00:00.0000000Z",
    "device_class": "Net",
    "device_id": "PCI\\VEN_8086&DEV_06F0",
    "is_signed": True,
}

ANOTHER_DRIVER: dict[str, Any] = {
    "device_name": "Generic software device",
    "friendly_name": None,
    "provider": "Microsoft",
    "version": "10.0.22621.1",
    "date": "2006-06-21T00:00:00.0000000Z",
    "device_class": "SoftwareDevice",
    "device_id": "SWD\\MSRRAS\\{5E259276-BC7E-40E3-B93B-8F89B5F3ABC0}",
    "is_signed": True,
}


# ======================================================================
# 1. Successful report generation / parsing
# ======================================================================

class TestSuccessfulParsing:
    def test_parse_valid_report_returns_success(self, tmp_path: Path) -> None:
        report = _write_report(tmp_path, VALID_DRIVER)
        collector = DriverCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()

        assert result.success is True
        assert result.error is None
        assert result.collector == "drivers"
        assert result.source == "powershell Get-WmiObject Win32_PnPSignedDriver"
        assert result.collected_at
        assert result.raw_report_path is not None

    def test_parse_returns_correct_driver_count(self, tmp_path: Path) -> None:
        report = _write_report(tmp_path, VALID_DRIVER, ANOTHER_DRIVER)
        collector = DriverCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()

        assert isinstance(result.data, list)
        assert len(result.data) == 2

    def test_raw_report_preserved(self, tmp_path: Path) -> None:
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        report = _write_report(src_dir, VALID_DRIVER)

        raw_dir = tmp_path / "raw"
        collector = DriverCollector(data_dir=raw_dir, report_path=report)
        result = collector.collect()

        assert result.raw_report_path is not None
        assert Path(result.raw_report_path).exists()
        assert Path(result.raw_report_path).parent.resolve() == raw_dir.resolve()


# ======================================================================
# 2. Valid driver extraction
# ======================================================================

class TestDriverExtraction:
    @pytest.fixture
    def driver(self, tmp_path: Path) -> dict[str, Any]:
        report = _write_report(tmp_path, VALID_DRIVER)
        collector = DriverCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert result.data
        return result.data[0]

    def test_device_name(self, driver: dict) -> None:
        assert driver["device_name"] == "Intel(R) Wi-Fi 6 AX201 160MHz"

    def test_provider(self, driver: dict) -> None:
        assert driver["provider"] == "Intel"

    def test_version(self, driver: dict) -> None:
        assert driver["version"] == "22.130.0.5"

    def test_date(self, driver: dict) -> None:
        assert driver["date"] == "2022-03-22T00:00:00.0000000Z"

    def test_device_class(self, driver: dict) -> None:
        assert driver["device_class"] == "Net"

    def test_device_id(self, driver: dict) -> None:
        assert driver["device_id"] == "PCI\\VEN_8086&DEV_06F0"
        
    def test_is_signed(self, driver: dict) -> None:
        assert driver["is_signed"] is True

    def test_null_fields_normalized_to_empty_strings(self, tmp_path: Path) -> None:
        session = {**VALID_DRIVER, "friendly_name": None, "provider": None}
        report = _write_report(tmp_path, session)
        collector = DriverCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        
        assert result.data[0]["friendly_name"] == ""
        assert result.data[0]["provider"] == ""


# ======================================================================
# 3. Empty / Malformed / Missing Results
# ======================================================================

class TestEmptyMalformedResults:
    def test_empty_results(self, tmp_path: Path) -> None:
        report = tmp_path / "empty.json"
        report.write_text("[]", encoding="utf-8")
        collector = DriverCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert result.success is True
        assert result.data == []

    def test_malformed_json(self, tmp_path: Path) -> None:
        report = tmp_path / "bad.json"
        report.write_text("[{bad json", encoding="utf-8")
        collector = DriverCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert result.success is False
        assert "Malformed JSON" in result.error

    def test_empty_file(self, tmp_path: Path) -> None:
        report = tmp_path / "empty_file.json"
        report.write_text("", encoding="utf-8")
        collector = DriverCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert result.success is True
        assert result.data == []

    def test_single_object_result(self, tmp_path: Path) -> None:
        report = tmp_path / "single.json"
        report.write_text(json.dumps(VALID_DRIVER), encoding="utf-8")
        collector = DriverCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert result.success is True
        assert len(result.data) == 1

    def test_missing_snapshot(self, tmp_path: Path) -> None:
        report = tmp_path / "missing.json"
        collector = DriverCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert result.success is False
        assert "Report not found" in result.error


# ======================================================================
# 4. Command/API Failures and Environment
# ======================================================================

class TestFailures:
    @patch("src.collectors.drivers.subprocess.run")
    def test_nonzero_returncode(self, mock_run: Any, tmp_path: Path) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "powershell Get-WmiObject", stderr="requires admin"
        )
        collector = DriverCollector(data_dir=tmp_path)
        result = collector.collect()
        assert result.success is False
        assert "powershell failed (rc=1): requires admin" in result.error

    @patch("src.collectors.drivers.subprocess.run")
    def test_permission_error(self, mock_run: Any, tmp_path: Path) -> None:
        mock_run.side_effect = PermissionError("Access is denied")
        collector = DriverCollector(data_dir=tmp_path)
        result = collector.collect()
        assert result.success is False
        assert "Permission denied" in result.error

    @patch("src.collectors.drivers.subprocess.run")
    def test_timeout(self, mock_run: Any, tmp_path: Path) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired("powershell", 60)
        collector = DriverCollector(data_dir=tmp_path)
        result = collector.collect()
        assert result.success is False
        assert "timed out" in result.error

    @patch("src.collectors.drivers.platform.system")
    def test_non_windows_execution(self, mock_system: Any, tmp_path: Path) -> None:
        mock_system.return_value = "Linux"
        collector = DriverCollector(data_dir=tmp_path)
        result = collector.collect()
        assert result.success is False
        assert "requires Windows" in result.error

    @patch("src.collectors.drivers.subprocess.run")
    def test_unexpected_error(self, mock_run: Any, tmp_path: Path) -> None:
        mock_run.side_effect = RuntimeError("Something terrible happened")
        collector = DriverCollector(data_dir=tmp_path)
        result = collector.collect()
        assert result.success is False
        assert "Collection failed" in result.error


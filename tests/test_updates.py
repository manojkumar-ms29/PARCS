"""Tests for the Update collector."""

from __future__ import annotations

import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from src.collectors.base import CollectorResult
from src.collectors.updates import UpdateCollector


# ======================================================================
# Fixtures / helpers
# ======================================================================

def _write_report(tmp: Path, *updates: dict[str, Any]) -> Path:
    """Write a mock JSON report file and return its path."""
    path = tmp / "updates.json"
    path.write_text(json.dumps(list(updates)), encoding="utf-8")
    return path


VALID_UPDATE: dict[str, Any] = {
    "title": "2024-01 Cumulative Update for Windows 11 Version 22H2 for x64-based Systems (KB5034204)",
    "update_id": "12345678-1234-1234-1234-123456789012",
    "kb_id": "KB5034204",
    "operation": 1,
    "result": 2,
    "timestamp": "2024-01-25T14:30:00.0000000Z",
}

ANOTHER_UPDATE: dict[str, Any] = {
    "title": "Security Intelligence Update for Microsoft Defender Antivirus - KB2267602 (Version 1.403.1111.0)",
    "update_id": "87654321-4321-4321-4321-210987654321",
    "kb_id": "KB2267602",
    "operation": 1,
    "result": 2,
    "timestamp": "2024-01-24T12:00:00.0000000Z",
}


# ======================================================================
# 1. Successful report generation / parsing
# ======================================================================

class TestSuccessfulParsing:
    def test_parse_valid_report_returns_success(self, tmp_path: Path) -> None:
        report = _write_report(tmp_path, VALID_UPDATE)
        collector = UpdateCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()

        assert result.success is True
        assert result.error is None
        assert result.collector == "updates"
        assert result.source == "powershell Microsoft.Update.Session"
        assert result.collected_at
        assert result.raw_report_path is not None

    def test_parse_returns_correct_update_count(self, tmp_path: Path) -> None:
        report = _write_report(tmp_path, VALID_UPDATE, ANOTHER_UPDATE)
        collector = UpdateCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()

        assert isinstance(result.data, list)
        assert len(result.data) == 2

    def test_raw_report_preserved(self, tmp_path: Path) -> None:
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        report = _write_report(src_dir, VALID_UPDATE)

        raw_dir = tmp_path / "raw"
        collector = UpdateCollector(data_dir=raw_dir, report_path=report)
        result = collector.collect()

        assert result.raw_report_path is not None
        assert Path(result.raw_report_path).exists()
        assert Path(result.raw_report_path).parent.resolve() == raw_dir.resolve()


# ======================================================================
# 2. Valid update extraction
# ======================================================================

class TestUpdateExtraction:
    @pytest.fixture
    def update(self, tmp_path: Path) -> dict[str, Any]:
        report = _write_report(tmp_path, VALID_UPDATE)
        collector = UpdateCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert result.data
        return result.data[0]

    def test_title(self, update: dict) -> None:
        assert update["title"] == "2024-01 Cumulative Update for Windows 11 Version 22H2 for x64-based Systems (KB5034204)"

    def test_update_id(self, update: dict) -> None:
        assert update["update_id"] == "12345678-1234-1234-1234-123456789012"

    def test_kb_id(self, update: dict) -> None:
        assert update["kb_id"] == "KB5034204"

    def test_operation(self, update: dict) -> None:
        assert update["operation"] == 1

    def test_result_code(self, update: dict) -> None:
        assert update["result"] == 2
        
    def test_timestamp(self, update: dict) -> None:
        assert update["timestamp"] == "2024-01-25T14:30:00.0000000Z"

    def test_null_fields_normalized_to_none_or_empty(self, tmp_path: Path) -> None:
        session = {**VALID_UPDATE, "title": None, "kb_id": None, "update_id": None}
        report = _write_report(tmp_path, session)
        collector = UpdateCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        
        assert result.data[0]["title"] == ""
        assert result.data[0]["kb_id"] is None
        assert result.data[0]["update_id"] is None


# ======================================================================
# 3. Empty / Malformed / Missing Results
# ======================================================================

class TestEmptyMalformedResults:
    def test_empty_results(self, tmp_path: Path) -> None:
        report = tmp_path / "empty.json"
        report.write_text("[]", encoding="utf-8")
        collector = UpdateCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert result.success is True
        assert result.data == []

    def test_malformed_json(self, tmp_path: Path) -> None:
        report = tmp_path / "bad.json"
        report.write_text("[{bad json", encoding="utf-8")
        collector = UpdateCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert result.success is False
        assert "Malformed JSON" in result.error

    def test_empty_file(self, tmp_path: Path) -> None:
        report = tmp_path / "empty_file.json"
        report.write_text("", encoding="utf-8")
        collector = UpdateCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert result.success is True
        assert result.data == []

    def test_single_object_result(self, tmp_path: Path) -> None:
        report = tmp_path / "single.json"
        report.write_text(json.dumps(VALID_UPDATE), encoding="utf-8")
        collector = UpdateCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert result.success is True
        assert len(result.data) == 1

    def test_missing_snapshot(self, tmp_path: Path) -> None:
        report = tmp_path / "missing.json"
        collector = UpdateCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert result.success is False
        assert "Report not found" in result.error


# ======================================================================
# 4. Command/API Failures and Environment
# ======================================================================

class TestFailures:
    @patch("src.collectors.updates.subprocess.run")
    def test_nonzero_returncode(self, mock_run: Any, tmp_path: Path) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "powershell Microsoft.Update.Session", stderr="requires admin"
        )
        collector = UpdateCollector(data_dir=tmp_path)
        result = collector.collect()
        assert result.success is False
        assert "powershell failed (rc=1): requires admin" in result.error

    @patch("src.collectors.updates.subprocess.run")
    def test_permission_error(self, mock_run: Any, tmp_path: Path) -> None:
        mock_run.side_effect = PermissionError("Access is denied")
        collector = UpdateCollector(data_dir=tmp_path)
        result = collector.collect()
        assert result.success is False
        assert "Permission denied" in result.error

    @patch("src.collectors.updates.subprocess.run")
    def test_timeout(self, mock_run: Any, tmp_path: Path) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired("powershell", 60)
        collector = UpdateCollector(data_dir=tmp_path)
        result = collector.collect()
        assert result.success is False
        assert "timed out" in result.error

    @patch("src.collectors.updates.platform.system")
    def test_non_windows_execution(self, mock_system: Any, tmp_path: Path) -> None:
        mock_system.return_value = "Linux"
        collector = UpdateCollector(data_dir=tmp_path)
        result = collector.collect()
        assert result.success is False
        assert "requires Windows" in result.error

    @patch("src.collectors.updates.subprocess.run")
    def test_unexpected_error(self, mock_run: Any, tmp_path: Path) -> None:
        mock_run.side_effect = RuntimeError("Something terrible happened")
        collector = UpdateCollector(data_dir=tmp_path)
        result = collector.collect()
        assert result.success is False
        assert "Collection failed" in result.error


# ======================================================================
# 5. Base Collector Contract
# ======================================================================

class TestBaseCollectorContract:
    def test_is_subclass(self) -> None:
        from src.collectors.base import BaseCollector
        assert issubclass(UpdateCollector, BaseCollector)

    def test_name_property(self) -> None:
        collector = UpdateCollector()
        assert collector.name == "updates"

    def test_collect_returns_collector_result(self, tmp_path: Path) -> None:
        report = tmp_path / "empty.json"
        report.write_text("[]", encoding="utf-8")
        collector = UpdateCollector(data_dir=tmp_path, report_path=report)
        result = collector.collect()
        assert isinstance(result, CollectorResult)

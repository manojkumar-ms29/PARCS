"""Event Log collector for PARCS.

Gathers relevant Windows Event Log telemetry that can later help PARCS
correlate Modern Standby regressions with system-level events.
"""

from __future__ import annotations

import json
import logging
import platform
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from src.collectors.base import BaseCollector, CollectorResult

logger = logging.getLogger(__name__)


class EventLogCollector(BaseCollector):
    """Collector that extracts telemetry from Windows Event Logs.

    Executes a PowerShell script to fetch events from the System log
    within a specified time window, focusing on power, PnP, and error events.

    Args:
        start_time: The beginning of the time window to collect.
        end_time: The end of the time window to collect.
        data_dir: Directory to store raw reports. Defaults to ``data/raw/``.
        report_path: Path to an existing JSON report to parse instead of
            running PowerShell. Useful for testing or re-processing.
    """

    _SOURCE = "powershell Get-WinEvent"

    def __init__(
        self,
        start_time: datetime,
        end_time: datetime,
        data_dir: str | Path | None = None,
        report_path: str | Path | None = None,
    ) -> None:
        self.start_time = start_time
        self.end_time = end_time
        project_root = Path(__file__).resolve().parent.parent.parent
        self._data_dir = Path(data_dir) if data_dir else project_root / "data" / "raw"
        self._report_path = Path(report_path) if report_path else None

    @property
    def name(self) -> str:
        return "eventlog"

    def collect(self) -> CollectorResult:
        """Execute collection and extract relevant events."""
        try:
            report_path = self._resolve_report()
            raw_text = report_path.read_text(encoding="utf-8")
            
            # The PS script outputs an array or a single object or nothing.
            if not raw_text.strip():
                events = []
            else:
                try:
                    parsed = json.loads(raw_text)
                    if isinstance(parsed, dict):
                        events = [parsed]
                    elif isinstance(parsed, list):
                        events = parsed
                    else:
                        events = []
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Malformed JSON output from Event Log: {exc}") from exc
            
            normalized_events = [self._normalize_event(e) for e in events if e]
            raw_path = self._preserve_raw_report(report_path)

            return CollectorResult(
                collector=self.name,
                collected_at=self._now_iso(),
                source=self._SOURCE,
                data=normalized_events,
                raw_report_path=str(raw_path),
            )
        except PermissionError as exc:
            return self._error_result(
                f"Administrator privileges or Event Log access required: {exc}",
                source=self._SOURCE,
            )
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or exc.output or "").strip()
            return self._error_result(
                f"powershell failed (rc={exc.returncode}): {stderr}",
                source=self._SOURCE,
            )
        except FileNotFoundError as exc:
            return self._error_result(str(exc), source=self._SOURCE)
        except ValueError as exc:
            return self._error_result(str(exc), source=self._SOURCE)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error during Event Log collection")
            return self._error_result(
                f"Collection failed: {exc}", source=self._SOURCE
            )

    def _resolve_report(self) -> Path:
        """Return the path to the report to parse."""
        if self._report_path is not None:
            if not self._report_path.exists():
                raise FileNotFoundError(f"Report not found: {self._report_path}")
            return self._report_path
        return self._generate_report()

    def _generate_report(self) -> Path:
        """Run PowerShell to gather event logs and save to a JSON file."""
        if platform.system() != "Windows":
            raise OSError("EventLog collector requires Windows")
            
        if self.start_time > self.end_time:
            raise ValueError("start_time cannot be after end_time")

        self._data_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = self._data_dir / f"eventlog-{stamp}.json"

        ps_script = self._build_powershell_script()
        
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", "-"],
            input=ps_script,
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                "powershell Get-WinEvent",
                output=result.stdout,
                stderr=result.stderr,
            )
            
        output.write_text(result.stdout, encoding="utf-8")
        
        return output

    def _build_powershell_script(self) -> str:
        """Build the PowerShell script to collect events."""
        start_iso = self.start_time.isoformat()
        end_iso = self.end_time.isoformat()
        
        return f"""
$ErrorActionPreference = 'Stop'
$FormatEnumerationLimit = -1
$start = [datetime]::Parse('{start_iso}', $null, [System.Globalization.DateTimeStyles]::RoundtripKind)
$end = [datetime]::Parse('{end_iso}', $null, [System.Globalization.DateTimeStyles]::RoundtripKind)

$filter = @{{
    LogName = 'System'
    StartTime = $start
    EndTime = $end
}}

try {{
    $events = Get-WinEvent -FilterHashtable $filter
}} catch [System.Management.Automation.ItemNotFoundException] {{
    $events = @()
}} catch {{
    if ($_.Exception.Message -match 'No events were found') {{
        $events = @()
    }} else {{
        throw $_
    }}
}}

$result = @()
foreach ($e in $events) {{
    $provider = $e.ProviderName
    $level = $e.Level
    
    # Include Error(2), Warning(3), Critical(1) OR Power/PnP/Boot related events
    if ($level -le 3 -or $provider -match 'Power' -or $provider -match 'PnP' -or $provider -match 'Boot') {{
        $levelName = $e.LevelDisplayName
        if ([string]::IsNullOrEmpty($levelName)) {{
            $levelName = "Unknown($level)"
        }}
        $result += [PSCustomObject]@{{
            timestamp = $e.TimeCreated.ToUniversalTime().ToString('o')
            event_id = $e.Id
            provider = $provider
            level = $levelName
            log_name = $e.LogName
            message = $e.Message
        }}
    }}
}}

$result | ConvertTo-Json -Depth 2 -Compress
"""

    def _preserve_raw_report(self, report_path: Path) -> Path:
        """Ensure the raw report is stored in *data_dir*."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        try:
            if report_path.parent.resolve() == self._data_dir.resolve():
                return report_path
        except (ValueError, OSError):
            pass

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = self._data_dir / f"eventlog-{stamp}.json"
        shutil.copy2(report_path, dest)
        return dest
        
    def _normalize_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Ensure all fields are present and properly typed."""
        # Some event messages might be null
        msg = event.get("message")
        return {
            "timestamp": event.get("timestamp"),
            "event_id": event.get("event_id"),
            "provider": event.get("provider"),
            "level": event.get("level"),
            "log_name": event.get("log_name"),
            "message": str(msg) if msg is not None else "",
        }

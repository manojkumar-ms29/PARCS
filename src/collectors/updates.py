"""Windows Update history collector for PARCS.

Gathers snapshots of Windows Update history to help PARCS
correlate regressions with update installations.
"""

from __future__ import annotations

import json
import logging
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from src.collectors.base import BaseCollector, CollectorResult

logger = logging.getLogger(__name__)


class UpdateCollector(BaseCollector):
    """Collector that extracts a snapshot of Windows Update history.

    Executes a PowerShell script to fetch update telemetry from the
    Windows Update COM API (Microsoft.Update.Session).

    Args:
        data_dir: Directory to store raw reports. Defaults to ``data/raw/``.
        report_path: Path to an existing JSON report to parse instead of
            running PowerShell. Useful for testing or re-processing.
    """

    _SOURCE = "powershell Microsoft.Update.Session"

    def __init__(
        self,
        data_dir: str | Path | None = None,
        report_path: str | Path | None = None,
    ) -> None:
        project_root = Path(__file__).resolve().parent.parent.parent
        self._data_dir = Path(data_dir) if data_dir else project_root / "data" / "raw"
        self._report_path = Path(report_path) if report_path else None

    @property
    def name(self) -> str:
        return "updates"

    def collect(self) -> CollectorResult:
        """Execute collection and extract update records."""
        try:
            report_path = self._resolve_report()
            raw_text = report_path.read_text(encoding="utf-8")
            
            if not raw_text.strip():
                updates = []
            else:
                try:
                    parsed = json.loads(raw_text)
                    if isinstance(parsed, dict):
                        updates = [parsed]
                    elif isinstance(parsed, list):
                        updates = parsed
                    else:
                        updates = []
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Malformed JSON output from Update collection: {exc}") from exc
            
            normalized_updates = [self._normalize_update(u) for u in updates if u]
            raw_path = self._preserve_raw_report(report_path)

            return CollectorResult(
                collector=self.name,
                collected_at=self._now_iso(),
                source=self._SOURCE,
                data=normalized_updates,
                raw_report_path=str(raw_path),
            )
        except PermissionError as exc:
            return self._error_result(
                f"Permission denied accessing updates or writing report: {exc}",
                source=self._SOURCE,
            )
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or exc.output or "").strip()
            return self._error_result(
                f"powershell failed (rc={exc.returncode}): {stderr}",
                source=self._SOURCE,
            )
        except subprocess.TimeoutExpired as exc:
            return self._error_result(
                f"powershell command timed out: {exc}",
                source=self._SOURCE,
            )
        except FileNotFoundError as exc:
            return self._error_result(str(exc), source=self._SOURCE)
        except ValueError as exc:
            return self._error_result(str(exc), source=self._SOURCE)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error during Update collection")
            return self._error_result(
                f"Collection failed: {exc}", source=self._SOURCE
            )

    def _normalize_update(self, raw_update: dict[str, Any]) -> dict[str, Any]:
        """Normalize a raw update record."""
        return {
            "timestamp": raw_update.get("timestamp") or None,
            "title": raw_update.get("title") or "",
            "kb_id": raw_update.get("kb_id") or None,
            "operation": raw_update.get("operation") or None,
            "result": raw_update.get("result") or None,
            "update_id": raw_update.get("update_id") or None,
        }

    def _resolve_report(self) -> Path:
        """Return the path to the report to parse."""
        if self._report_path is not None:
            if not self._report_path.exists():
                raise FileNotFoundError(f"Report not found: {self._report_path}")
            return self._report_path
        return self._generate_report()

    def _generate_report(self) -> Path:
        """Run PowerShell to gather update details and save to a JSON file."""
        if platform.system() != "Windows":
            raise OSError("Update collector requires Windows")
            
        self._data_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = self._data_dir / f"updates-{stamp}.json"

        ps_script = self._build_powershell_script()
        
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", "-"],
            input=ps_script,
            capture_output=True,
            text=True,
            timeout=120,
        )
        
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                "powershell Microsoft.Update.Session",
                output=result.stdout,
                stderr=result.stderr,
            )
            
        output.write_text(result.stdout, encoding="utf-8")
        
        return output

    def _preserve_raw_report(self, report_path: Path) -> Path:
        """Ensure the raw report is preserved in the data directory."""
        import shutil
        
        if report_path.parent.resolve() == self._data_dir.resolve():
            return report_path
            
        self._data_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = self._data_dir / f"updates-imported-{stamp}.json"
        shutil.copy2(report_path, dest)
        return dest

    def _build_powershell_script(self) -> str:
        """Build the PowerShell script to collect update history."""
        script = """
$ErrorActionPreference = 'Stop'
try {
    $Session = New-Object -ComObject "Microsoft.Update.Session"
    $Searcher = $Session.CreateUpdateSearcher()
    $HistoryCount = $Searcher.GetTotalHistoryCount()
    
    if ($HistoryCount -eq 0) {
        @() | ConvertTo-Json -Compress
    } else {
        $History = $Searcher.QueryHistory(0, $HistoryCount)
        $History | Select-Object @(
            @{Name='title'; Expression={$_.Title}},
            @{Name='update_id'; Expression={$_.UpdateIdentity.UpdateID}},
            @{Name='kb_id'; Expression={
                if (![string]::IsNullOrEmpty($_.Title) -and $_.Title -match '(KB\\d+)') {
                    $matches[1]
                } else {
                    $null
                }
            }},
            @{Name='operation'; Expression={$_.Operation}},
            @{Name='result'; Expression={$_.ResultCode}},
            @{Name='timestamp'; Expression={
                if ($_.Date) {
                    try { $_.Date.ToUniversalTime().ToString('o') } catch { $_.Date }
                } else { $null }
            }}
        ) | ConvertTo-Json -Depth 2 -Compress
    }
} catch {
    Write-Error "Failed to query update history: $_"
    exit 1
}
"""
        return script.replace('\n', '\r\n')

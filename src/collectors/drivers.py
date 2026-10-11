"""Windows Driver collector for PARCS.

Gathers snapshots of installed/recognized drivers to help PARCS
correlate regressions with driver state changes.
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


class DriverCollector(BaseCollector):
    """Collector that extracts a snapshot of Windows drivers.

    Executes a PowerShell script to fetch driver telemetry from WMI
    (Win32_PnPSignedDriver).

    Args:
        data_dir: Directory to store raw reports. Defaults to ``data/raw/``.
        report_path: Path to an existing JSON report to parse instead of
            running PowerShell. Useful for testing or re-processing.
    """

    _SOURCE = "powershell Get-WmiObject Win32_PnPSignedDriver"

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
        return "drivers"

    def collect(self) -> CollectorResult:
        """Execute collection and extract driver records."""
        try:
            report_path = self._resolve_report()
            raw_text = report_path.read_text(encoding="utf-8")
            
            if not raw_text.strip():
                drivers = []
            else:
                try:
                    parsed = json.loads(raw_text)
                    if isinstance(parsed, dict):
                        drivers = [parsed]
                    elif isinstance(parsed, list):
                        drivers = parsed
                    else:
                        drivers = []
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Malformed JSON output from Driver collection: {exc}") from exc
            
            # Normalize records
            normalized_drivers = [self._normalize_driver(d) for d in drivers if d]
            raw_path = self._preserve_raw_report(report_path)

            return CollectorResult(
                collector=self.name,
                collected_at=self._now_iso(),
                source=self._SOURCE,
                data=normalized_drivers,
                raw_report_path=str(raw_path),
            )
        except PermissionError as exc:
            return self._error_result(
                f"Permission denied accessing drivers or writing report: {exc}",
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
            logger.exception("Unexpected error during Driver collection")
            return self._error_result(
                f"Collection failed: {exc}", source=self._SOURCE
            )

    def _normalize_driver(self, raw_driver: dict[str, Any]) -> dict[str, Any]:
        """Normalize a raw driver record from WMI."""
        return {
            "device_name": raw_driver.get("device_name") or "",
            "friendly_name": raw_driver.get("friendly_name") or "",
            "provider": raw_driver.get("provider") or "",
            "version": raw_driver.get("version") or "",
            "date": raw_driver.get("date") or "",
            "device_class": raw_driver.get("device_class") or "",
            "device_id": raw_driver.get("device_id") or "",
            "is_signed": bool(raw_driver.get("is_signed")),
        }

    def _resolve_report(self) -> Path:
        """Return the path to the report to parse."""
        if self._report_path is not None:
            if not self._report_path.exists():
                raise FileNotFoundError(f"Report not found: {self._report_path}")
            return self._report_path
        return self._generate_report()

    def _generate_report(self) -> Path:
        """Run PowerShell to gather driver details and save to a JSON file."""
        if platform.system() != "Windows":
            raise OSError("Driver collector requires Windows")
            
        self._data_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = self._data_dir / f"drivers-{stamp}.json"

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
                "powershell Get-WmiObject Win32_PnPSignedDriver",
                output=result.stdout,
                stderr=result.stderr,
            )
            
        output.write_text(result.stdout, encoding="utf-8")
        
        return output

    def _preserve_raw_report(self, report_path: Path) -> Path:
        """Ensure the raw report is preserved in the data directory."""
        import shutil
        
        # If it was dynamically generated, it's already in self._data_dir
        if report_path.parent.resolve() == self._data_dir.resolve():
            return report_path
            
        # Otherwise, we copy the provided file to the data dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = self._data_dir / f"drivers-imported-{stamp}.json"
        shutil.copy2(report_path, dest)
        return dest

    def _build_powershell_script(self) -> str:
        """Build the PowerShell script to collect drivers."""
        script = """
$ErrorActionPreference = 'Stop'
Get-WmiObject Win32_PnPSignedDriver | Select-Object @(
    @{Name='device_name'; Expression={$_.DeviceName}},
    @{Name='friendly_name'; Expression={$_.FriendlyName}},
    @{Name='provider'; Expression={$_.Manufacturer}},
    @{Name='version'; Expression={$_.DriverVersion}},
    @{Name='date'; Expression={
        if ($_.DriverDate) {
            try { $_.ConvertToDateTime($_.DriverDate).ToUniversalTime().ToString('o') } catch { $_.DriverDate }
        } else { $null }
    }},
    @{Name='device_class'; Expression={$_.DeviceClass}},
    @{Name='device_id'; Expression={$_.DeviceID}},
    @{Name='is_signed'; Expression={[bool]$_.IsSigned}}
) | ConvertTo-Json -Depth 2 -Compress
"""
        return script.replace('\n', '\r\n')

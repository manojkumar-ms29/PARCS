"""SleepStudy collector for PARCS.

Executes ``powercfg /sleepstudy`` on Windows, captures the generated HTML
report, extracts standby-session telemetry, and returns structured data.

The raw HTML report is preserved in ``data/raw/`` for the later ETL layer.
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

# Session Duration field is in microseconds.
_US_PER_SECOND = 1_000_000

# SwLowPowerStateTime is in 100 ns ticks; Duration is in microseconds.
# The Windows report uses:  round(100 * Sw_100ns / Duration_us / 10)
# which simplifies to:     round(Sw_100ns / Duration_us * 10)
# and equals:              round(Sw_us / Duration_us * 100)
#   since Sw_us = Sw_100ns / 10.
_DRIPS_SCALE = 10  # 100 / 10

# HOUR_TO_US = 60 * 60 * 1_000_000 used by the Windows report for drain-rate.
_HOUR_US = 3_600_000_000


class SleepStudyCollector(BaseCollector):
    """Collector that extracts standby-session telemetry from Windows SleepStudy.

    Runs ``powercfg /sleepstudy`` to generate an HTML report, then parses the
    embedded JSON data to extract per-session metrics.

    Args:
        data_dir: Directory to store raw reports.  Defaults to ``data/raw/``.
        report_path: Path to an existing report to parse instead of running
            powercfg.  Useful for testing or re-processing old reports.
    """

    _SOURCE = "powercfg /sleepstudy"

    def __init__(
        self,
        data_dir: str | Path | None = None,
        report_path: str | Path | None = None,
    ) -> None:
        project_root = Path(__file__).resolve().parent.parent.parent
        self._data_dir = Path(data_dir) if data_dir else project_root / "data" / "raw"
        self._report_path = Path(report_path) if report_path else None

    @property
    def name(self) -> str:  # noqa: D401
        return "sleepstudy"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collect(self) -> CollectorResult:
        """Execute collection: generate or read report, extract sessions.

        Returns:
            CollectorResult whose ``data`` field is a list of session dicts,
            each containing exactly the six required fields.
        """
        try:
            report_path = self._resolve_report()
            html = report_path.read_text(encoding="utf-8")
            sessions = self._extract_sessions(html)
            raw_path = self._preserve_raw_report(report_path)

            return CollectorResult(
                collector=self.name,
                collected_at=self._now_iso(),
                source=self._SOURCE,
                data=sessions,
                raw_report_path=str(raw_path),
            )
        except PermissionError as exc:
            return self._error_result(
                f"Administrator privileges required: {exc}",
                source=self._SOURCE,
            )
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or exc.output or "").strip()
            return self._error_result(
                f"powercfg failed (rc={exc.returncode}): {stderr}",
                source=self._SOURCE,
            )
        except FileNotFoundError as exc:
            return self._error_result(str(exc), source=self._SOURCE)
        except ValueError as exc:
            return self._error_result(str(exc), source=self._SOURCE)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error during SleepStudy collection")
            return self._error_result(
                f"Collection failed: {exc}", source=self._SOURCE
            )

    # ------------------------------------------------------------------
    # Report generation / resolution
    # ------------------------------------------------------------------

    def _resolve_report(self) -> Path:
        """Return the path to the report to parse.

        If *report_path* was provided at construction, validate it exists.
        Otherwise generate a fresh report via ``powercfg``.
        """
        if self._report_path is not None:
            if not self._report_path.exists():
                raise FileNotFoundError(
                    f"Report not found: {self._report_path}"
                )
            return self._report_path
        return self._generate_report()

    def _generate_report(self) -> Path:
        """Run ``powercfg /sleepstudy`` and return the output path.

        Raises:
            OSError: If not running on Windows.
            subprocess.CalledProcessError: If powercfg exits non-zero.
            FileNotFoundError: If the report file was not created.
        """
        if platform.system() != "Windows":
            raise OSError("SleepStudy collector requires Windows")

        self._data_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = self._data_dir / f"sleepstudy-{stamp}.html"

        result = subprocess.run(
            ["powercfg", "/sleepstudy", "/output", str(output)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                "powercfg /sleepstudy",
                output=result.stdout,
                stderr=result.stderr,
            )
        if not output.exists():
            raise FileNotFoundError(
                f"powercfg completed but report not found at {output}"
            )
        return output

    # ------------------------------------------------------------------
    # Raw-report preservation
    # ------------------------------------------------------------------

    def _preserve_raw_report(self, report_path: Path) -> Path:
        """Ensure the raw report is stored in *data_dir*.

        If the report already lives in *data_dir* it is returned as-is;
        otherwise a timestamped copy is created.
        """
        self._data_dir.mkdir(parents=True, exist_ok=True)
        try:
            if report_path.parent.resolve() == self._data_dir.resolve():
                return report_path
        except (ValueError, OSError):
            pass

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = self._data_dir / f"sleepstudy-{stamp}.html"
        shutil.copy2(report_path, dest)
        return dest

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _extract_sessions(self, html: str) -> list[dict[str, Any]]:
        """Parse the HTML report and return a list of session dicts."""
        raw = self._parse_scenario_instances(html)
        return [self._extract_fields(s) for s in raw]

    @staticmethod
    def _parse_scenario_instances(html: str) -> list[dict[str, Any]]:
        """Locate and parse the ``ScenarioInstances`` JSON array.

        The SleepStudy HTML embeds a JavaScript data object that contains
        ``"ScenarioInstances":[…]``.  This method bracket-matches the array
        and returns the parsed list.

        Raises:
            ValueError: If the marker is not found or the JSON is invalid.
        """
        marker = '"ScenarioInstances":['
        idx = html.find(marker)
        if idx == -1:
            raise ValueError(
                "ScenarioInstances not found in report — "
                "the file may be empty or in an unexpected format"
            )

        array_start = idx + len(marker) - 1  # position of '['
        depth = 0
        in_string = False
        escape = False

        for i in range(array_start, len(html)):
            ch = html[i]
            if escape:
                escape = False
                continue
            if ch == "\\" and in_string:
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(html[array_start : i + 1])
                    except json.JSONDecodeError as exc:
                        raise ValueError(
                            f"Invalid ScenarioInstances JSON: {exc}"
                        ) from exc

        raise ValueError("Unterminated ScenarioInstances array")

    # ------------------------------------------------------------------
    # Per-session field extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_fields(session: dict[str, Any]) -> dict[str, Any]:
        """Extract the six required fields from one raw session dict.

        Fields:
            start_time          – local ISO 8601 entry timestamp
            end_time            – local ISO 8601 exit timestamp
            duration_seconds    – session length in seconds
            drips_percent       – Software DRIPS % (standby sessions only)
            battery_drain_percent – capacity lost as % of full charge
            battery_drain_rate_mw – average drain in milliwatts
        """
        start = session.get("EntryTimestampLocal") or session.get("EntryTimestamp")
        end = session.get("ExitTimestampLocal") or session.get("ExitTimestamp")

        dur_us = session.get("Duration")
        dur_s: float | None = None
        if isinstance(dur_us, (int, float)) and dur_us > 0:
            dur_s = round(dur_us / _US_PER_SECOND, 2)

        return {
            "start_time": start,
            "end_time": end,
            "duration_seconds": dur_s,
            "drips_percent": _drips_percent(session),
            "battery_drain_percent": _drain_percent(session),
            "battery_drain_rate_mw": _drain_rate(session),
        }


# ======================================================================
# Private helpers — intentionally module-level to keep the class slim
# ======================================================================


def _meta_value(metadata: dict[str, Any] | None, key: str) -> Any:
    """Look up *key* in ``Metadata.Values`` (a list of {Key, Value} dicts)."""
    if not metadata:
        return None
    values = metadata.get("Values")
    if not isinstance(values, list):
        return None
    for entry in values:
        if isinstance(entry, dict) and entry.get("Key") == key:
            return entry.get("Value")
    return None


def _drips_percent(session: dict[str, Any]) -> float | None:
    """Compute Software DRIPS % using the Windows report formula.

    Only meaningful for Type 1 (Screen Off) and Type 2 (Modern Standby).

    Formula (matches the rendered report):
        ``round(100 * SwLowPowerStateTime_100ns / Duration_us / 10)``
    """
    if session.get("Type") not in (1, 2):
        return None

    dur_us = session.get("Duration")
    if not isinstance(dur_us, (int, float)) or dur_us <= 0:
        return None

    sw = _meta_value(session.get("Metadata"), "Info.SwLowPowerStateTime")
    if not isinstance(sw, (int, float)):
        return None

    pct = round(sw / dur_us * _DRIPS_SCALE)
    return max(0, min(100, pct))


def _valid_battery(session: dict[str, Any]) -> tuple[int, int, int] | None:
    """Return (discharge_mwh, entry_full, dur_us) if battery drain is valid."""
    if session.get("Type") not in (0, 1, 2):
        return None
    if session.get("BatteryCountChanged", False):
        return None

    entry_rem = session.get("EntryRemainingCapacity")
    exit_rem = session.get("ExitRemainingCapacity")
    entry_full = session.get("EntryFullChargeCapacity")

    if not all(isinstance(v, (int, float)) for v in (entry_rem, exit_rem, entry_full)):
        return None
    if entry_full <= 0:
        return None

    discharge = entry_rem - exit_rem
    if discharge <= 0:
        return None

    dur_us = session.get("Duration")
    if not isinstance(dur_us, (int, float)) or dur_us <= 0:
        return None

    return discharge, entry_full, dur_us


def _drain_percent(session: dict[str, Any]) -> float | None:
    """Battery drain as % of full-charge capacity."""
    vals = _valid_battery(session)
    if vals is None:
        return None
    discharge, entry_full, _ = vals
    return round(100 * discharge / entry_full, 1)


def _drain_rate(session: dict[str, Any]) -> float | None:
    """Average drain rate in milliwatts (mW)."""
    vals = _valid_battery(session)
    if vals is None:
        return None
    discharge, _, dur_us = vals
    rate = round(discharge * _HOUR_US / dur_us)
    return rate if rate > 0 else None

"""SleepStudy ETL Pipeline for PARCS.

Transforms raw Windows SleepStudy HTML reports into validated, deduplicated,
and normalized standby session records stored as Parquet and queryable via DuckDB.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.storage.parquet import read_parquet, write_parquet
from src.storage.paths import PROCESSED_DIR, RAW_DIR, ensure_storage_dirs

logger = logging.getLogger(__name__)

# Target dataset name for processed standby sessions
DATASET_NAME = "standby_sessions"

# Scaling constants from Windows SleepStudy
_US_PER_SECOND = 1_000_000
_DRIPS_SCALE = 10  # round(100 * ticks / dur_us / 10)
_HOUR_US = 3_600_000_000

# Verified session type names
SESSION_TYPE_NAMES: dict[int, str] = {
    1: "Screen Off",
    2: "Modern Standby",
}

SCHEMA_COLUMNS = [
    "session_key",
    "computer_name",
    "session_id",
    "session_type",
    "session_type_name",
    "start_time",
    "end_time",
    "duration_seconds",
    "enter_reason",
    "exit_reason",
    "on_ac",
    "drips_percent",
    "hw_drips_percent",
    "battery_drain_mwh",
    "battery_drain_percent",
    "battery_drain_rate_mw",
    "report_guid",
    "source_file",
    "ingested_at",
]


class ETLError(Exception):
    """Base exception for ETL processing failures."""


class ETLParseError(ETLError):
    """Raised when an HTML report or its embedded payload cannot be parsed."""


class ETLValidationError(ETLError):
    """Raised when record validation fails critically."""


@dataclass
class ETLResult:
    """Summary of an ETL pipeline run.

    Attributes:
        records_extracted: Number of valid standby sessions extracted from report.
        records_persisted: Total number of records in target dataset after deduplication.
        dataset_path: Path to the resulting Parquet file, if written/updated.
        source_file: Basename of the source raw file.
        success: Whether the ETL run completed successfully.
        error: Error description if collection/processing failed.
    """

    records_extracted: int
    records_persisted: int
    dataset_path: Path | None = None
    source_file: str = ""
    success: bool = True
    error: str | None = None


def generate_session_key(
    computer_name: str, start_time_utc: str, end_time_utc: str, session_type: int
) -> str:
    """Generate a deterministic 32-character hex primary key for a session.

    Formula:
        SHA256(f"{computer_name}|{start_time_utc}|{end_time_utc}|{session_type}")[:32]
    """
    normalized_comp = (computer_name or "UNKNOWN").strip().upper()
    key_src = f"{normalized_comp}|{start_time_utc}|{end_time_utc}|{session_type}"
    return hashlib.sha256(key_src.encode("utf-8")).hexdigest()[:32]


def _meta_value(metadata: dict[str, Any] | None, key: str) -> Any:
    """Extract value for given Key from Metadata.Values list."""
    if not metadata or not isinstance(metadata, dict):
        return None
    values = metadata.get("Values")
    if not isinstance(values, list):
        return None
    for entry in values:
        if isinstance(entry, dict) and entry.get("Key") == key:
            return entry.get("Value")
    return None


def _find_balanced_closing(
    text: str, start_idx: int, open_ch: str = "{", close_ch: str = "}"
) -> int:
    """Find index of the matching closing bracket in text starting at start_idx."""
    depth = 0
    in_string = False
    escape = False

    for i in range(start_idx, len(text)):
        ch = text[i]
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
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i + 1
    return -1


def parse_sleepstudy_payload(html: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Parse raw SleepStudy HTML and return (header_dict, scenario_instances_list).

    Tries to locate `LocalSprData = { ... }`. If not found, falls back to
    `"ScenarioInstances":[ ... ]` for compatibility with mock fixtures.

    Raises:
        ETLParseError: If neither structure is found or if JSON decoding fails.
    """
    if not html or not html.strip():
        raise ETLParseError("SleepStudy HTML content is empty")

    # 1. Primary: search for LocalSprData = { ... }
    match_spr = re.search(r"(?:var|let|const)?\s*LocalSprData\s*=\s*\{", html)
    if match_spr:
        start_idx = match_spr.end() - 1
        end_idx = _find_balanced_closing(html, start_idx, "{", "}")
        if end_idx != -1:
            try:
                data = json.loads(html[start_idx:end_idx])
                if isinstance(data, dict):
                    header = {
                        "ReportInformation": data.get("ReportInformation") or {},
                        "SystemInformation": data.get("SystemInformation") or {},
                    }
                    scenarios = data.get("ScenarioInstances") or []
                    if isinstance(scenarios, list):
                        return header, scenarios
            except json.JSONDecodeError as exc:
                raise ETLParseError(
                    f"Malformed JSON in LocalSprData payload: {exc}"
                ) from exc

    # 2. Fallback: search for "ScenarioInstances":[ ... ]
    match_scen = re.search(r'"ScenarioInstances"\s*:\s*\[', html)
    if match_scen:
        start_idx = match_scen.end() - 1
        end_idx = _find_balanced_closing(html, start_idx, "[", "]")
        if end_idx != -1:
            try:
                scenarios = json.loads(html[start_idx:end_idx])
                if isinstance(scenarios, list):
                    header = {
                        "ReportInformation": {},
                        "SystemInformation": {"ComputerName": "UNKNOWN"},
                    }
                    return header, scenarios
            except json.JSONDecodeError as exc:
                raise ETLParseError(
                    f"Malformed JSON in ScenarioInstances array: {exc}"
                ) from exc

    raise ETLParseError("No valid SleepStudy payload found in HTML content")


def _compute_drips(session: dict[str, Any]) -> tuple[float | None, float | None]:
    """Compute Software DRIPS % and Hardware DRIPS % using Windows report formulas.

    Only valid for Type 1 (Screen Off) and Type 2 (Modern Standby).

    Formula (matches Windows SleepStudy HTML engine):
        Software DRIPS: round(100 * Sw / Duration / 10)
        Hardware DRIPS: if Sw == 0 or Hw is undefined -> None
                        else round(100 * Hw / Duration / 10)
    """
    if session.get("Type") not in (1, 2):
        return None, None

    dur_us = session.get("Duration")
    if not isinstance(dur_us, (int, float)) or dur_us <= 0:
        return None, None

    sw = _meta_value(session.get("Metadata"), "Info.SwLowPowerStateTime")
    hw = _meta_value(session.get("Metadata"), "Info.HwLowPowerStateTime")

    sw_pct: float | None = None
    if isinstance(sw, (int, float)):
        calculated_sw = round(sw / dur_us * _DRIPS_SCALE)
        sw_pct = float(max(0, min(100, calculated_sw)))

    hw_pct: float | None = None
    if sw_pct is not None and sw_pct > 0 and isinstance(hw, (int, float)):
        calculated_hw = round(hw / dur_us * _DRIPS_SCALE)
        hw_pct = float(max(0, min(100, calculated_hw)))

    return sw_pct, hw_pct


def _compute_battery_drain(
    session: dict[str, Any],
) -> tuple[float | None, float | None, float | None]:
    """Compute (drain_mwh, drain_percent, drain_rate_mw) under verified validity rules.

    Valid only when:
        - Session is on DC battery (OnAc == False)
        - BatteryCountChanged == False
        - Capacities are valid numbers
        - EntryFullChargeCapacity > 0
        - Discharge > 0 (device was not charging or capacity unchanged)
        - Duration > 0
    """
    if session.get("Type") not in (1, 2):
        return None, None, None

    if session.get("OnAc", False):
        return None, None, None

    if session.get("BatteryCountChanged", False):
        return None, None, None

    entry_rem = session.get("EntryRemainingCapacity")
    exit_rem = session.get("ExitRemainingCapacity")
    entry_full = session.get("EntryFullChargeCapacity")

    if not all(isinstance(v, (int, float)) for v in (entry_rem, exit_rem, entry_full)):
        return None, None, None

    if entry_full <= 0:
        return None, None, None

    discharge = entry_rem - exit_rem
    if discharge <= 0:
        return None, None, None

    dur_us = session.get("Duration")
    if not isinstance(dur_us, (int, float)) or dur_us <= 0:
        return None, None, None

    drain_mwh = float(round(discharge))
    drain_pct = float(round(100 * discharge / entry_full, 1))
    rate_mw = float(round(discharge * _HOUR_US / dur_us))
    drain_rate_mw = rate_mw if rate_mw > 0 else None

    return drain_mwh, drain_pct, drain_rate_mw


def _clean_reason(reason: Any) -> str:
    """Normalize reason strings, replacing placeholders with 'Unknown'."""
    if not reason or not isinstance(reason, str):
        return "Unknown"
    s = reason.strip()
    if not s or s == "----":
        return "Unknown"
    return s


def transform_standby_sessions(
    header: dict[str, Any], scenarios: list[dict[str, Any]], source_file: str
) -> pd.DataFrame:
    """Transform extracted SleepStudy scenarios into the approved schema DataFrame.

    Filters strictly for eligible standby session types (Type 1 and Type 2).
    """
    sys_info = header.get("SystemInformation") or {}
    report_info = header.get("ReportInformation") or {}

    computer_name = str(sys_info.get("ComputerName") or "UNKNOWN").strip().upper()
    report_guid = report_info.get("ReportGuid")
    if report_guid is not None:
        report_guid = str(report_guid).strip()

    ingested_at = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []

    for s in scenarios:
        if not isinstance(s, dict):
            continue

        session_type = s.get("Type")
        if session_type not in (1, 2):
            continue

        session_type_name = SESSION_TYPE_NAMES[session_type]
        session_id = s.get("SessionId")
        if not isinstance(session_id, int):
            session_id = 0

        # Timestamps
        start_raw = s.get("EntryTimestamp") or s.get("EntryTimestampLocal")
        end_raw = s.get("ExitTimestamp") or s.get("ExitTimestampLocal")

        if not start_raw or not end_raw:
            continue

        try:
            start_dt = pd.to_datetime(start_raw, utc=True)
            end_dt = pd.to_datetime(end_raw, utc=True)
        except Exception:  # noqa: BLE001
            continue

        if pd.isna(start_dt) or pd.isna(end_dt) or end_dt < start_dt:
            # Reject inverted or unparseable timestamps
            continue

        # Duration
        dur_us = s.get("Duration")
        if not isinstance(dur_us, (int, float)) or dur_us < 0:
            continue
        duration_s = round(dur_us / _US_PER_SECOND, 2)

        # Deterministic primary key
        start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        session_key = generate_session_key(
            computer_name, start_iso, end_iso, session_type
        )

        on_ac = bool(s.get("OnAc", False))
        enter_reason = _clean_reason(s.get("EnterReason"))
        exit_reason = _clean_reason(s.get("ExitReason"))

        drips_pct, hw_drips_pct = _compute_drips(s)
        drain_mwh, drain_pct, drain_rate_mw = _compute_battery_drain(s)

        rows.append(
            {
                "session_key": session_key,
                "computer_name": computer_name,
                "session_id": int(session_id),
                "session_type": int(session_type),
                "session_type_name": session_type_name,
                "start_time": start_dt,
                "end_time": end_dt,
                "duration_seconds": float(duration_s),
                "enter_reason": enter_reason,
                "exit_reason": exit_reason,
                "on_ac": on_ac,
                "drips_percent": drips_pct,
                "hw_drips_percent": hw_drips_pct,
                "battery_drain_mwh": drain_mwh,
                "battery_drain_percent": drain_pct,
                "battery_drain_rate_mw": drain_rate_mw,
                "report_guid": report_guid,
                "source_file": source_file,
                "ingested_at": ingested_at,
            }
        )

    if not rows:
        return _empty_standby_dataframe()

    df = pd.DataFrame(rows)
    return _enforce_schema_dtypes(df)


def _empty_standby_dataframe() -> pd.DataFrame:
    """Return an empty DataFrame structured with the exact schema columns."""
    df = pd.DataFrame(columns=SCHEMA_COLUMNS)
    return _enforce_schema_dtypes(df)


def _enforce_schema_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure DataFrame columns and dtypes strictly match the contract."""
    # Ensure all columns present
    for col in SCHEMA_COLUMNS:
        if col not in df.columns:
            df[col] = None

    df = df[SCHEMA_COLUMNS].copy()

    # Cast dtypes
    df["session_key"] = df["session_key"].astype(str)
    df["computer_name"] = df["computer_name"].astype(str)
    df["session_id"] = pd.to_numeric(df["session_id"], errors="coerce").fillna(0).astype("int32")
    df["session_type"] = pd.to_numeric(df["session_type"], errors="coerce").fillna(0).astype("int16")
    df["session_type_name"] = df["session_type_name"].astype(str)
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True)
    df["end_time"] = pd.to_datetime(df["end_time"], utc=True)
    df["duration_seconds"] = pd.to_numeric(df["duration_seconds"], errors="coerce").astype("float64")
    df["enter_reason"] = df["enter_reason"].astype(str)
    df["exit_reason"] = df["exit_reason"].astype(str)
    df["on_ac"] = df["on_ac"].astype(bool)
    df["drips_percent"] = pd.to_numeric(df["drips_percent"], errors="coerce").astype("float64")
    df["hw_drips_percent"] = pd.to_numeric(df["hw_drips_percent"], errors="coerce").astype("float64")
    df["battery_drain_mwh"] = pd.to_numeric(df["battery_drain_mwh"], errors="coerce").astype("float64")
    df["battery_drain_percent"] = pd.to_numeric(df["battery_drain_percent"], errors="coerce").astype("float64")
    df["battery_drain_rate_mw"] = pd.to_numeric(df["battery_drain_rate_mw"], errors="coerce").astype("float64")
    df["source_file"] = df["source_file"].astype(str)
    df["ingested_at"] = pd.to_datetime(df["ingested_at"], utc=True)

    return df


def load_and_deduplicate(
    new_df: pd.DataFrame, dataset_name: str = DATASET_NAME
) -> tuple[pd.DataFrame, int]:
    """Merge new records with existing Parquet dataset, deduplicate, and persist.

    Deduplication Policy:
        - Match on primary key `session_key`.
        - Sort by `ingested_at` ascending and keep latest record (`keep="last"`).
        - If write fails, the previous processed dataset is preserved intact.

    Returns:
        tuple[persisted_df, records_persisted_count]
    """
    ensure_storage_dirs()
    target_parquet = PROCESSED_DIR / f"{dataset_name}.parquet"
    backup_parquet = PROCESSED_DIR / f"{dataset_name}.parquet.bak"

    # 1. Read existing records if present
    if target_parquet.exists():
        try:
            existing_df = read_parquet(dataset_name)
        except Exception as exc:
            logger.error("Failed to read existing dataset %s: %s", target_parquet, exc)
            raise ETLError(f"Existing dataset {dataset_name} is unreadable: {exc}") from exc
    else:
        existing_df = pd.DataFrame()

    # 2. If new_df is empty, preserve existing data and do not write
    if new_df.empty:
        count = len(existing_df)
        return existing_df, count

    # 3. Combine and deduplicate
    if not existing_df.empty:
        combined = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        combined = new_df.copy()

    # Sort so latest ingestion takes precedence on conflicting session_key
    deduped = (
        combined.sort_values(by=["session_key", "ingested_at"])
        .drop_duplicates(subset=["session_key"], keep="last")
        .reset_index(drop=True)
    )
    deduped = _enforce_schema_dtypes(deduped)

    # 4. Safe write with backup protection
    if target_parquet.exists():
        shutil.copy2(target_parquet, backup_parquet)

    try:
        write_parquet(deduped, dataset_name)
        if backup_parquet.exists():
            backup_parquet.unlink()
    except Exception as exc:
        logger.error("Write to %s failed: %s. Restoring backup if available.", target_parquet, exc)
        if backup_parquet.exists():
            shutil.move(backup_parquet, target_parquet)
        raise

    return deduped, len(deduped)


def run_sleepstudy_etl(
    report_path: str | Path | None = None, html_content: str | None = None
) -> ETLResult:
    """Execute the SleepStudy ETL pipeline for a report file or raw HTML string.

    Args:
        report_path: Path to raw HTML report. If None and html_content is None,
            the newest report in `data/raw/` is processed.
        html_content: Raw HTML text string (useful for testing or direct piping).

    Returns:
        ETLResult describing extracted and persisted record counts.
    """
    # 1. Resolve input source
    if html_content is not None:
        source_name = Path(report_path).name if report_path else "inline_html"
        raw_html = html_content
    elif report_path is not None:
        p = Path(report_path)
        if not p.exists():
            raise FileNotFoundError(f"Report file not found: {p}")
        source_name = p.name
        raw_html = p.read_text(encoding="utf-8")
    else:
        # Default: pick most recent sleepstudy HTML in RAW_DIR
        ensure_storage_dirs()
        candidates = sorted(RAW_DIR.glob("sleepstudy-*.html"), key=lambda f: f.stat().st_mtime)
        if not candidates:
            raise FileNotFoundError(f"No SleepStudy reports found in {RAW_DIR}")
        p = candidates[-1]
        source_name = p.name
        raw_html = p.read_text(encoding="utf-8")

    # 2. Parse payload
    header, scenarios = parse_sleepstudy_payload(raw_html)

    # 3. Transform and validate
    extracted_df = transform_standby_sessions(header, scenarios, source_name)
    extracted_count = len(extracted_df)

    # 4. Merge, deduplicate, and persist
    persisted_df, persisted_count = load_and_deduplicate(extracted_df, DATASET_NAME)
    target_path = PROCESSED_DIR / f"{DATASET_NAME}.parquet"

    return ETLResult(
        records_extracted=extracted_count,
        records_persisted=persisted_count,
        dataset_path=target_path if target_path.exists() else None,
        source_file=source_name,
        success=True,
    )

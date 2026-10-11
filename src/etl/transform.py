"""PARCS ETL Transform and Schema Validation.

Defines the normalized SleepStudy schema, validation rules,
machine identity resolution, and timestamp normalization.
"""

from __future__ import annotations

import hashlib
import logging
import os
import platform
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0.0"
DEFAULT_DATASET_NAME = "sleepstudy"

# Required columns for the normalized SleepStudy dataset
SLEEPSTUDY_COLUMNS = [
    "machine_id",
    "collected_at",
    "start_time",
    "end_time",
    "duration_seconds",
    "drips_percent",
    "battery_drain_percent",
    "battery_drain_rate_mw",
]


@dataclass
class RecordValidationError:
    """Detailed information about an invalid record."""

    record_index: int
    field: str
    message: str
    raw_record: dict[str, Any] | None = None
    error_type: str = "validation_error"


@dataclass
class ValidationResult:
    """Outcome of validating a batch of records."""

    valid_records: list[dict[str, Any]] = field(default_factory=list)
    rejected_records: list[dict[str, Any]] = field(default_factory=list)
    errors: list[RecordValidationError] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.valid_records) + len(self.rejected_records)


def get_machine_id(override: str | None = None) -> str:
    """Resolve a stable machine identifier from configuration, environment, or system.

    Precedence:
    1. Explicit override argument.
    2. PARCS_MACHINE_ID environment variable.
    3. platform.node() (host name).
    4. socket.gethostname().

    Raises:
        ValueError: If machine identity cannot be determined.
    """
    if override and str(override).strip():
        return str(override).strip()

    env_id = os.environ.get("PARCS_MACHINE_ID", "").strip()
    if env_id:
        return env_id

    try:
        node = platform.node().strip()
        if node:
            return node.upper()
    except Exception:  # noqa: BLE001
        pass

    try:
        host = socket.gethostname().strip()
        if host:
            return host.upper()
    except Exception:  # noqa: BLE001
        pass

    raise ValueError("Unable to determine stable machine identity. Please set PARCS_MACHINE_ID.")


def generate_record_fingerprint(machine_id: str, start_time: str, end_time: str) -> str:
    """Compute a deterministic 32-character hex fingerprint for a standby session.

    Ensures identical sessions can be deduplicated across runs.
    """
    normalized_machine = (machine_id or "UNKNOWN").strip().upper()
    key_str = f"{normalized_machine}|{start_time}|{end_time}"
    return hashlib.sha256(key_str.encode("utf-8")).hexdigest()[:32]


def parse_and_validate_timestamp(ts: Any, field_name: str) -> tuple[datetime, str]:
    """Parse and validate an ISO 8601 timestamp string or datetime.

    Preserves source timestamp format while normalizing to a standardized string
    and datetime object for comparison.

    Raises:
        ValueError: If the timestamp is null, empty, or unparseable.
    """
    if ts is None:
        raise ValueError(f"Missing required timestamp '{field_name}'")

    if isinstance(ts, datetime):
        dt = ts
        if dt.tzinfo is not None:
            dt_utc = dt.astimezone(timezone.utc)
            return dt_utc, dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        return dt, dt.isoformat()

    if not isinstance(ts, str) or not ts.strip():
        raise ValueError(f"Timestamp '{field_name}' must be a non-empty string or datetime")

    s = ts.strip()
    iso_candidate = s
    if iso_candidate.endswith("Z"):
        iso_candidate = iso_candidate[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(iso_candidate)
    except Exception as exc:
        raise ValueError(f"Invalid ISO 8601 timestamp for '{field_name}': {ts}") from exc

    if dt.tzinfo is not None:
        dt_utc = dt.astimezone(timezone.utc)
        return dt_utc, dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Timezone-naive: preserve string representation, return naive datetime for local comparison
    return dt, s


def validate_sleepstudy_record(
    raw_record: Any,
    index: int,
    machine_id: str,
    collected_at: str,
) -> tuple[dict[str, Any] | None, list[RecordValidationError]]:
    """Validate and normalize a single SleepStudy record.

    Validates:
    - Dict structure.
    - Required fields: start_time, end_time, duration_seconds.
    - Chronological order: end_time >= start_time.
    - Value ranges:
        * duration_seconds >= 0.0
        * drips_percent: 0.0 <= x <= 100.0 (if present)
        * battery_drain_percent: 0.0 <= x <= 100.0 (if present)
        * battery_drain_rate_mw: x >= 0.0 (if present)

    Returns:
        (normalized_record, errors): tuple of normalized dict (or None) and list of errors.
    """
    errors: list[RecordValidationError] = []

    if not isinstance(raw_record, dict):
        errors.append(
            RecordValidationError(
                record_index=index,
                field="_root",
                message=f"Record at index {index} is not a dictionary",
                error_type="malformed_input",
            )
        )
        return None, errors

    # 1. Machine ID
    if not machine_id:
        errors.append(
            RecordValidationError(
                record_index=index,
                field="machine_id",
                message="machine_id is missing or empty",
                raw_record=raw_record,
                error_type="missing_field",
            )
        )

    # 2. Timestamps
    start_dt: datetime | None = None
    start_str: str | None = None
    try:
        start_dt, start_str = parse_and_validate_timestamp(raw_record.get("start_time"), "start_time")
    except ValueError as exc:
        errors.append(
            RecordValidationError(
                record_index=index,
                field="start_time",
                message=str(exc),
                raw_record=raw_record,
                error_type="invalid_timestamp",
            )
        )

    end_dt: datetime | None = None
    end_str: str | None = None
    try:
        end_dt, end_str = parse_and_validate_timestamp(raw_record.get("end_time"), "end_time")
    except ValueError as exc:
        errors.append(
            RecordValidationError(
                record_index=index,
                field="end_time",
                message=str(exc),
                raw_record=raw_record,
                error_type="invalid_timestamp",
            )
        )

    # Chronology check if both timestamps are valid
    if start_dt is not None and end_dt is not None:
        if (start_dt.tzinfo is None) != (end_dt.tzinfo is None):
            errors.append(
                RecordValidationError(
                    record_index=index,
                    field="time_range",
                    message="Mixed timezone-aware and timezone-naive timestamps cannot be compared",
                    raw_record=raw_record,
                    error_type="invalid_timestamp",
                )
            )
        elif end_dt < start_dt:
            errors.append(
                RecordValidationError(
                    record_index=index,
                    field="time_range",
                    message=f"end_time ({end_str}) must be greater than or equal to start_time ({start_str})",
                    raw_record=raw_record,
                    error_type="invalid_timestamp",
                )
            )

    # 3. Duration
    raw_duration = raw_record.get("duration_seconds")
    duration_s: float | None = None
    if raw_duration is not None:
        try:
            val = float(raw_duration)
            if pd.isna(val) or val < 0:
                errors.append(
                    RecordValidationError(
                        record_index=index,
                        field="duration_seconds",
                        message=f"duration_seconds must be non-negative, got {raw_duration}",
                        raw_record=raw_record,
                        error_type="invalid_range",
                    )
                )
            else:
                duration_s = round(val, 2)
        except (ValueError, TypeError):
            errors.append(
                RecordValidationError(
                    record_index=index,
                    field="duration_seconds",
                    message=f"duration_seconds must be a number, got {raw_duration}",
                    raw_record=raw_record,
                    error_type="invalid_type",
                )
            )
    else:
        # If duration was not provided, but start and end are valid, derive duration
        if start_dt is not None and end_dt is not None and end_dt >= start_dt:
            duration_s = round((end_dt - start_dt).total_seconds(), 2)
        else:
            errors.append(
                RecordValidationError(
                    record_index=index,
                    field="duration_seconds",
                    message="duration_seconds is missing and cannot be computed",
                    raw_record=raw_record,
                    error_type="missing_field",
                )
            )

    # 4. Optional measurements (must remain None if absent)
    # DRIPS %
    raw_drips = raw_record.get("drips_percent")
    drips_val: float | None = None
    if raw_drips is not None:
        try:
            val = float(raw_drips)
            if pd.isna(val):
                drips_val = None
            elif not (0.0 <= val <= 100.0):
                errors.append(
                    RecordValidationError(
                        record_index=index,
                        field="drips_percent",
                        message=f"drips_percent must be between 0.0 and 100.0, got {raw_drips}",
                        raw_record=raw_record,
                        error_type="invalid_range",
                    )
                )
            else:
                drips_val = float(val)
        except (ValueError, TypeError):
            errors.append(
                RecordValidationError(
                    record_index=index,
                    field="drips_percent",
                    message=f"drips_percent must be numeric, got {raw_drips}",
                    raw_record=raw_record,
                    error_type="invalid_type",
                )
            )

    # Battery drain %
    raw_drain_pct = raw_record.get("battery_drain_percent")
    drain_pct_val: float | None = None
    if raw_drain_pct is not None:
        try:
            val = float(raw_drain_pct)
            if pd.isna(val):
                drain_pct_val = None
            elif not (0.0 <= val <= 100.0):
                errors.append(
                    RecordValidationError(
                        record_index=index,
                        field="battery_drain_percent",
                        message=f"battery_drain_percent must be between 0.0 and 100.0, got {raw_drain_pct}",
                        raw_record=raw_record,
                        error_type="invalid_range",
                    )
                )
            else:
                drain_pct_val = float(val)
        except (ValueError, TypeError):
            errors.append(
                RecordValidationError(
                    record_index=index,
                    field="battery_drain_percent",
                    message=f"battery_drain_percent must be numeric, got {raw_drain_pct}",
                    raw_record=raw_record,
                    error_type="invalid_type",
                )
            )

    # Battery drain rate mW
    raw_rate = raw_record.get("battery_drain_rate_mw")
    drain_rate_val: float | None = None
    if raw_rate is not None:
        try:
            val = float(raw_rate)
            if pd.isna(val):
                drain_rate_val = None
            elif val < 0.0:
                errors.append(
                    RecordValidationError(
                        record_index=index,
                        field="battery_drain_rate_mw",
                        message=f"battery_drain_rate_mw must be non-negative, got {raw_rate}",
                        raw_record=raw_record,
                        error_type="invalid_range",
                    )
                )
            else:
                drain_rate_val = float(val)
        except (ValueError, TypeError):
            errors.append(
                RecordValidationError(
                    record_index=index,
                    field="battery_drain_rate_mw",
                    message=f"battery_drain_rate_mw must be numeric, got {raw_rate}",
                    raw_record=raw_record,
                    error_type="invalid_type",
                )
            )

    if errors:
        return None, errors

    normalized: dict[str, Any] = {
        "machine_id": machine_id,
        "collected_at": collected_at,
        "start_time": start_str,
        "end_time": end_str,
        "duration_seconds": duration_s,
        "drips_percent": drips_val,
        "battery_drain_percent": drain_pct_val,
        "battery_drain_rate_mw": drain_rate_val,
    }

    return normalized, []


def transform_and_validate_sleepstudy(
    records: Any,
    machine_id: str,
    collected_at: str,
) -> ValidationResult:
    """Validate a collection of raw SleepStudy records and separate valid from rejected."""
    result = ValidationResult()

    if records is None:
        return result

    if isinstance(records, dict):
        records = [records]
    elif not isinstance(records, list):
        result.errors.append(
            RecordValidationError(
                record_index=0,
                field="_root",
                message=f"Expected list of records, got {type(records).__name__}",
                error_type="malformed_input",
            )
        )
        return result

    for i, raw_item in enumerate(records):
        norm, item_errors = validate_sleepstudy_record(raw_item, i, machine_id, collected_at)
        if item_errors:
            result.rejected_records.append(raw_item if isinstance(raw_item, dict) else {"raw": raw_item})
            result.errors.extend(item_errors)
        elif norm is not None:
            result.valid_records.append(norm)

    return result


def records_to_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert normalized records into a strongly-typed pandas DataFrame."""
    if not records:
        df = pd.DataFrame(columns=SLEEPSTUDY_COLUMNS)
    else:
        df = pd.DataFrame(records)

    for col in SLEEPSTUDY_COLUMNS:
        if col not in df.columns:
            df[col] = None

    df = df[SLEEPSTUDY_COLUMNS].copy()

    df["machine_id"] = df["machine_id"].astype(str)
    df["collected_at"] = df["collected_at"].astype(str)
    df["start_time"] = df["start_time"].astype(str)
    df["end_time"] = df["end_time"].astype(str)
    df["duration_seconds"] = pd.to_numeric(df["duration_seconds"], errors="coerce").astype("float64")
    df["drips_percent"] = pd.to_numeric(df["drips_percent"], errors="coerce").astype("float64")
    df["battery_drain_percent"] = pd.to_numeric(df["battery_drain_percent"], errors="coerce").astype("float64")
    df["battery_drain_rate_mw"] = pd.to_numeric(df["battery_drain_rate_mw"], errors="coerce").astype("float64")

    return df

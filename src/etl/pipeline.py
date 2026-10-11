"""PARCS ETL Pipeline Orchestration.

Orchestrates data flow from CollectorResult objects to raw preservation,
record normalization and validation, Parquet persistence, and DuckDB accessibility.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from src.collectors.base import CollectorResult
from src.etl.transform import (
    DEFAULT_DATASET_NAME,
    RecordValidationError,
    ValidationResult,
    get_machine_id,
    records_to_dataframe,
    transform_and_validate_sleepstudy,
)
from src.storage.db import DuckDBManager, get_db_connection
from src.storage.parquet import read_parquet, write_parquet
from src.storage.paths import PROCESSED_DIR, RAW_DIR, ensure_storage_dirs
from src.storage.raw import save_raw_data

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Structured Exceptions
# ----------------------------------------------------------------------


class ETLError(Exception):
    """Base exception for all ETL pipeline failures."""


class ETLCollectorError(ETLError):
    """Raised when collector execution reported a failure."""


class ETLInputError(ETLError):
    """Raised when input to the ETL pipeline is missing or malformed."""


class ETLValidationError(ETLError):
    """Raised when record validation fails critically."""


class ETLPersistenceError(ETLError):
    """Raised when Parquet or DB persistence operations fail."""


# ----------------------------------------------------------------------
# Execution Summary
# ----------------------------------------------------------------------


@dataclass
class ETLExecutionSummary:
    """Detailed summary of an ETL pipeline run.

    Attributes:
        collectors_processed: Names of all collectors handled in this run.
        successful_collectors: Names of collectors that succeeded.
        failed_collectors: Names of collectors that reported failures.
        input_records: Total raw records received.
        accepted_records: Valid records that passed schema validation.
        rejected_records: Records that failed schema validation.
        records_persisted: Total records stored in target dataset after deduplication.
        output_files: Paths to persisted output files (e.g., Parquet).
        validation_errors: Detailed list of errors for rejected records.
        success: Whether the pipeline completed successfully without unhandled errors.
        error: Descriptive error message if run failed.
    """

    collectors_processed: list[str] = field(default_factory=list)
    successful_collectors: list[str] = field(default_factory=list)
    failed_collectors: list[str] = field(default_factory=list)
    input_records: int = 0
    accepted_records: int = 0
    rejected_records: int = 0
    records_persisted: int = 0
    output_files: list[str] = field(default_factory=list)
    validation_errors: list[RecordValidationError] = field(default_factory=list)
    success: bool = True
    error: str | None = None


# ----------------------------------------------------------------------
# Pipeline Orchestrator
# ----------------------------------------------------------------------


class ETLPipeline:
    """ETL Pipeline for transforming collector outputs into analytics-ready datasets.

    Args:
        machine_id: Explicit machine identifier. If None, resolved from environment/system.
        dataset_name: Target Parquet dataset name in the processed directory.
        processed_dir: Directory to persist Parquet datasets. Defaults to data/processed/.
        raw_dir: Directory where raw reports are stored. Defaults to data/raw/.
    """

    def __init__(
        self,
        machine_id: str | None = None,
        dataset_name: str = DEFAULT_DATASET_NAME,
        processed_dir: Path | str | None = None,
        raw_dir: Path | str | None = None,
    ) -> None:
        self.machine_id = machine_id
        self.dataset_name = dataset_name
        self.processed_dir = Path(processed_dir) if processed_dir else PROCESSED_DIR
        self.raw_dir = Path(raw_dir) if raw_dir else RAW_DIR

    def run(
        self,
        collector_results: CollectorResult | Sequence[CollectorResult],
        raise_on_error: bool = False,
    ) -> ETLExecutionSummary:
        """Execute ETL pipeline on one or more CollectorResult objects.

        Args:
            collector_results: A single CollectorResult or sequence of results.
            raise_on_error: If True, raise structured exceptions instead of
                recording failure status in the summary.

        Returns:
            ETLExecutionSummary describing execution metrics and errors.
        """
        ensure_storage_dirs()
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

        # Normalize input to sequence
        if isinstance(collector_results, CollectorResult):
            results = [collector_results]
        elif isinstance(collector_results, (list, tuple)):
            results = list(collector_results)
        else:
            msg = f"Expected CollectorResult or Sequence[CollectorResult], got {type(collector_results).__name__}"
            if raise_on_error:
                raise ETLInputError(msg)
            return ETLExecutionSummary(success=False, error=msg)

        summary = ETLExecutionSummary()
        sleepstudy_valid_records: list[dict[str, Any]] = []

        for result in results:
            summary.collectors_processed.append(result.collector)

            # 1. Raw Report Preservation
            self._ensure_raw_preserved(result)

            # 2. Check Collection Success
            if not result.success or result.error:
                summary.failed_collectors.append(result.collector)
                err_msg = f"Collector '{result.collector}' failed: {result.error or 'unknown error'}"
                logger.error(err_msg)
                summary.success = False
                summary.error = err_msg
                if raise_on_error:
                    raise ETLCollectorError(err_msg)
                continue

            summary.successful_collectors.append(result.collector)

            # 3. Handle collector data
            raw_data = result.data
            if raw_data is None:
                raw_items: list[Any] = []
            elif isinstance(raw_data, list):
                raw_items = raw_data
            elif isinstance(raw_data, dict):
                raw_items = [raw_data]
            else:
                err_msg = f"Collector '{result.collector}' returned invalid data type: {type(raw_data).__name__}"
                summary.success = False
                summary.error = err_msg
                if raise_on_error:
                    raise ETLInputError(err_msg)
                continue

            # Route by collector type
            if result.collector == "sleepstudy":
                summary.input_records += len(raw_items)
                try:
                    resolved_machine = get_machine_id(self.machine_id)
                except ValueError as exc:
                    summary.success = False
                    summary.error = str(exc)
                    if raise_on_error:
                        raise ETLInputError(str(exc)) from exc
                    continue

                val_result: ValidationResult = transform_and_validate_sleepstudy(
                    records=raw_items,
                    machine_id=resolved_machine,
                    collected_at=result.collected_at,
                )
                summary.accepted_records += len(val_result.valid_records)
                summary.rejected_records += len(val_result.rejected_records)
                summary.validation_errors.extend(val_result.errors)
                sleepstudy_valid_records.extend(val_result.valid_records)
            else:
                # Event log, driver, or update collectors
                # Preserved in raw storage; normalized schemas introduced separately
                logger.debug(
                    "Collector '%s' processed and raw report preserved; normalized dataset deferred.",
                    result.collector,
                )

        # 4. Determine outcome if any collector failed
        if summary.failed_collectors and not sleepstudy_valid_records:
            # Failed collector must not silently produce a successful empty dataset
            summary.success = False
            return summary

        # 5. Handle empty or all-rejected records
        if not sleepstudy_valid_records:
            if summary.input_records > 0 and summary.rejected_records == summary.input_records:
                # All records were rejected
                summary.success = False
                summary.error = f"All {summary.input_records} input records failed validation"
                if raise_on_error:
                    raise ETLValidationError(summary.error)
                return summary

            # Successful run with zero records
            target_path = self.processed_dir / f"{self.dataset_name}.parquet"
            if target_path.exists():
                summary.output_files.append(str(target_path))
                try:
                    summary.records_persisted = len(pd.read_parquet(target_path))
                except Exception:  # noqa: BLE001
                    pass
            return summary

        # 6. Deduplication and Parquet Persistence
        new_df = records_to_dataframe(sleepstudy_valid_records)
        target_path = self.processed_dir / f"{self.dataset_name}.parquet"
        backup_path = self.processed_dir / f"{self.dataset_name}.parquet.bak"

        try:
            persisted_df, persisted_count = self._persist_records(
                new_df=new_df,
                target_path=target_path,
                backup_path=backup_path,
            )
            summary.records_persisted = persisted_count
            summary.output_files.append(str(target_path))
        except Exception as exc:
            err_msg = f"Persistence failure writing dataset '{self.dataset_name}': {exc}"
            logger.exception(err_msg)
            summary.success = False
            summary.error = err_msg
            if raise_on_error:
                raise ETLPersistenceError(err_msg) from exc
            return summary

        return summary

    def _ensure_raw_preserved(self, result: CollectorResult) -> None:
        """Verify raw report preservation, saving in-memory data if no report path exists."""
        if result.raw_report_path:
            p = Path(result.raw_report_path)
            if not p.exists():
                logger.warning("Collector '%s' specified raw_report_path that does not exist: %s", result.collector, p)
            return

        # If data is present but raw_report_path is not set, persist raw data
        if result.data is not None:
            try:
                saved = save_raw_data(result.data, source_name=result.collector, ext="json")
                result.raw_report_path = str(saved)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to save raw data for collector '%s': %s", result.collector, exc)

    def _persist_records(
        self,
        new_df: pd.DataFrame,
        target_path: Path,
        backup_path: Path,
    ) -> tuple[pd.DataFrame, int]:
        """Combine with existing Parquet dataset, deduplicate deterministically, and write safely."""
        if target_path.exists():
            try:
                existing_df = pd.read_parquet(target_path)
            except Exception as exc:
                raise ETLPersistenceError(f"Existing Parquet file is corrupted or unreadable: {exc}") from exc
        else:
            existing_df = pd.DataFrame()

        if not existing_df.empty:
            combined = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            combined = new_df.copy()

        # Deterministic deduplication:
        # Match on (machine_id, start_time, end_time).
        # Order by collected_at so later collections update/confirm existing records.
        deduped = (
            combined.sort_values(by=["collected_at"])
            .drop_duplicates(subset=["machine_id", "start_time", "end_time"], keep="last")
            .reset_index(drop=True)
        )
        deduped = records_to_dataframe(deduped.to_dict(orient="records"))

        # Backup existing target file if present
        if target_path.exists():
            shutil.copy2(target_path, backup_path)

        try:
            deduped.to_parquet(target_path, index=False)
            if backup_path.exists():
                backup_path.unlink()
        except Exception:
            # Restore previous version if write fails
            if backup_path.exists():
                shutil.move(backup_path, target_path)
            raise

        return deduped, len(deduped)

    def query(self, sql: str) -> pd.DataFrame:
        """Query the persisted dataset directly using DuckDB."""
        target_path = self.processed_dir / f"{self.dataset_name}.parquet"
        if not target_path.exists():
            raise FileNotFoundError(f"Dataset {self.dataset_name} not found at {target_path}")

        db = get_db_connection()
        try:
            db.conn.execute(f"CREATE OR REPLACE VIEW {self.dataset_name} AS SELECT * FROM '{target_path.as_posix()}'")
            return db.query_to_df(sql)
        finally:
            db.close()


def run_etl_pipeline(
    collector_results: CollectorResult | Sequence[CollectorResult],
    machine_id: str | None = None,
    dataset_name: str = DEFAULT_DATASET_NAME,
    processed_dir: Path | str | None = None,
    raise_on_error: bool = False,
) -> ETLExecutionSummary:
    """Convenience helper to run the ETL pipeline."""
    pipeline = ETLPipeline(
        machine_id=machine_id,
        dataset_name=dataset_name,
        processed_dir=processed_dir,
    )
    return pipeline.run(collector_results, raise_on_error=raise_on_error)

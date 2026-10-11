"""PARCS ETL pipelines."""

from src.etl.pipeline import (
    ETLCollectorError,
    ETLError,
    ETLExecutionSummary,
    ETLInputError,
    ETLPersistenceError,
    ETLPipeline,
    ETLValidationError,
    run_etl_pipeline,
)
from src.etl.sleepstudy import (
    ETLParseError,
    ETLResult,
    load_and_deduplicate,
    parse_sleepstudy_payload,
    run_sleepstudy_etl,
    transform_standby_sessions,
)
from src.etl.transform import (
    DEFAULT_DATASET_NAME,
    RecordValidationError,
    SLEEPSTUDY_COLUMNS,
    ValidationResult,
    generate_record_fingerprint,
    get_machine_id,
    records_to_dataframe,
    transform_and_validate_sleepstudy,
    validate_sleepstudy_record,
)

__all__ = [
    # Pipeline & Execution
    "ETLPipeline",
    "run_etl_pipeline",
    "ETLExecutionSummary",
    "ETLError",
    "ETLCollectorError",
    "ETLInputError",
    "ETLValidationError",
    "ETLPersistenceError",
    # Transform & Schema
    "DEFAULT_DATASET_NAME",
    "SLEEPSTUDY_COLUMNS",
    "RecordValidationError",
    "ValidationResult",
    "get_machine_id",
    "generate_record_fingerprint",
    "transform_and_validate_sleepstudy",
    "validate_sleepstudy_record",
    "records_to_dataframe",
    # Backwards-compatible SleepStudy functions
    "ETLParseError",
    "ETLResult",
    "load_and_deduplicate",
    "parse_sleepstudy_payload",
    "run_sleepstudy_etl",
    "transform_standby_sessions",
]

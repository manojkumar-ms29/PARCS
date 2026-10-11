"""Pydantic models and schemas for PARCS FastAPI backend."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str = Field(default="healthy", description="Application health status")
    service: str = Field(default="PARCS API", description="Service name")
    version: str = Field(default="1.0.0", description="API version")
    timestamp: str = Field(description="ISO 8601 UTC timestamp")


class DateRange(BaseModel):
    """Start and end timestamps for telemetry dataset."""

    start: str | None = None
    end: str | None = None


class DatasetsAvailable(BaseModel):
    """Flags indicating which datasets are persisted in storage."""

    sleepstudy: bool = False
    changes: bool = False


class TelemetrySummaryResponse(BaseModel):
    """Telemetry availability and machine summary."""

    total_sessions: int = 0
    total_changes: int = 0
    machines: list[str] = Field(default_factory=list)
    date_range: DateRange | None = None
    datasets_available: DatasetsAvailable
    is_synthetic: bool = False
    status: str = "ok"
    message: str = "Telemetry summary retrieved."


class DemoSeedResponse(BaseModel):
    """Response returned when synthetic demonstration data is seeded."""

    success: bool
    is_synthetic: bool = True
    session_records: int
    change_records: int
    machines: list[str]
    output_files: list[str]


class BaselineItem(BaseModel):
    """Baseline entry per machine and metric."""

    machine_id: str
    metric: str
    observation_count: int | None = None
    valid_count: int | None = None
    excluded_count: int | None = None
    median: float | None = None
    mad: float | None = None
    iqr: float | None = None
    dispersion_scale: float | None = None
    zero_mad_fallback: bool | None = None
    readiness: str
    min_observations: int


class AnomalyItem(BaseModel):
    """Anomaly evaluation record."""

    source_row_index: int
    machine_id: str
    start_time: str | None = None
    end_time: str | None = None
    metric: str
    observed_value: float | None = None
    baseline_median: float | None = None
    deviation_score: float | None = None
    threshold: float | None = None
    is_anomaly: bool
    status: str
    reason: str


class RegressionItem(BaseModel):
    """Regression evaluation record."""

    source_row_index: int
    machine_id: str
    start_time: str | None = None
    end_time: str | None = None
    metric: str
    observed_value: float | None = None
    baseline_median: float | None = None
    deviation_score: float | None = None
    direction: str
    is_regression: bool
    status: str
    consecutive_count: int
    required_consecutive: int
    reason: str


class CorrelationItem(BaseModel):
    """Change correlation record."""

    source_row_index: int
    machine_id: str
    metric: str
    start_time: str | None = None
    end_time: str | None = None
    regression_status: str
    is_correlated: bool
    correlation_status: str
    change_id: str | None = None
    change_type: str | None = None
    change_timestamp: str | None = None
    change_description: str | None = None
    temporal_offset_seconds: float | None = None
    temporal_relation: str
    window_before_seconds: float
    window_after_seconds: float
    reason: str
    explanation: str


class ChangeItem(BaseModel):
    """System change record."""

    machine_id: str
    timestamp: str | None = None
    change_type: str
    change_id: str
    description: str
    is_synthetic: bool | None = None

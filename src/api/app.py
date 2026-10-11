"""FastAPI application for PARCS telemetry, analytics, and change correlation."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.models import (
    AnomalyItem,
    BaselineItem,
    ChangeItem,
    CorrelationItem,
    DemoSeedResponse,
    HealthResponse,
    RegressionItem,
    TelemetrySummaryResponse,
)
from src.api.service import AnalyticsService
from src.utils.demo_data import seed_demo_datasets

logger = logging.getLogger(__name__)

app = FastAPI(
    title="PARCS API",
    description="Predictive Analytics & Real-Time Intelligence System for Modern Standby",
    version="1.0.0",
)

# Enable CORS for local dashboards and web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = AnalyticsService()


# ----------------------------------------------------------------------
# Health & Telemetry Summary
# ----------------------------------------------------------------------


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Report application health",
    tags=["System"],
)
def get_health() -> HealthResponse:
    """Report backend health status and UTC timestamp."""
    return HealthResponse(
        status="healthy",
        service="PARCS API",
        version="1.0.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get(
    "/api/telemetry/summary",
    response_model=TelemetrySummaryResponse,
    summary="Summarize available telemetry and machines",
    tags=["Telemetry"],
)
def get_telemetry_summary() -> TelemetrySummaryResponse:
    """Summarize active datasets, machine IDs, and date intervals."""
    try:
        summary_dict = service.get_telemetry_summary()
        return TelemetrySummaryResponse(**summary_dict)
    except Exception as exc:
        logger.exception("Error generating telemetry summary: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to summarize telemetry datasets.",
        ) from exc


# ----------------------------------------------------------------------
# Analytics Endpoints
# ----------------------------------------------------------------------


@app.get(
    "/api/analytics/baselines",
    response_model=list[BaselineItem],
    summary="Retrieve machine statistical baselines",
    tags=["Analytics"],
)
def get_baselines(
    machine_id: Annotated[str | None, Query(description="Optional machine ID filter")] = None,
    min_observations: Annotated[int, Query(ge=1, description="Minimum observations for ready baseline")] = 10,
) -> list[BaselineItem]:
    """Retrieve statistical baselines (Median, MAD, IQR, readiness) partitioned by machine."""
    try:
        items = service.get_baselines(machine_id=machine_id, min_observations=min_observations)
        return [BaselineItem(**item) for item in items]
    except Exception as exc:
        logger.exception("Error calculating baselines: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute statistical baselines.",
        ) from exc


@app.get(
    "/api/analytics/anomalies",
    response_model=list[AnomalyItem],
    summary="Retrieve detected statistical anomalies",
    tags=["Analytics"],
)
def get_anomalies(
    machine_id: Annotated[str | None, Query(description="Optional machine ID filter")] = None,
    threshold: Annotated[float, Query(gt=0, description="Modified Z-score cutoff")] = 3.5,
) -> list[AnomalyItem]:
    """Retrieve sessions evaluated against machine baselines for anomalous deviations."""
    try:
        items = service.get_anomalies(machine_id=machine_id, threshold=threshold)
        return [AnomalyItem(**item) for item in items]
    except Exception as exc:
        logger.exception("Error detecting anomalies: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute anomaly evaluation.",
        ) from exc


@app.get(
    "/api/analytics/regressions",
    response_model=list[RegressionItem],
    summary="Retrieve detected sustained performance regressions",
    tags=["Analytics"],
)
def get_regressions(
    machine_id: Annotated[str | None, Query(description="Optional machine ID filter")] = None,
    threshold: Annotated[float, Query(gt=0, description="Modified Z-score harmful cutoff")] = 2.0,
    min_consecutive: Annotated[int, Query(ge=1, description="Required consecutive sessions")] = 3,
    only_regressions: Annotated[bool, Query(description="Filter only flagged regression sessions")] = False,
) -> list[RegressionItem]:
    """Retrieve sustained directional regressions evaluated in chronological sequence."""
    try:
        items = service.get_regressions(
            machine_id=machine_id,
            threshold=threshold,
            min_consecutive=min_consecutive,
            only_regressions=only_regressions,
        )
        return [RegressionItem(**item) for item in items]
    except Exception as exc:
        logger.exception("Error detecting regressions: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute regression detection.",
        ) from exc


@app.get(
    "/api/analytics/correlations",
    response_model=list[CorrelationItem],
    summary="Retrieve regressions correlated with system changes",
    tags=["Analytics"],
)
def get_correlations(
    machine_id: Annotated[str | None, Query(description="Optional machine ID filter")] = None,
    window_before_hours: Annotated[float, Query(ge=0, description="Look-back window hours")] = 24.0,
    window_after_hours: Annotated[float, Query(ge=0, description="Look-forward window hours")] = 2.0,
    only_regressions: Annotated[bool, Query(description="Evaluate only qualifying regressions")] = True,
) -> list[CorrelationItem]:
    """Retrieve system changes matching regressions within the configured temporal window."""
    try:
        items = service.get_correlations(
            machine_id=machine_id,
            window_before_hours=window_before_hours,
            window_after_hours=window_after_hours,
            only_regressions=only_regressions,
        )
        return [CorrelationItem(**item) for item in items]
    except Exception as exc:
        logger.exception("Error correlating changes: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to correlate system changes.",
        ) from exc


@app.get(
    "/api/changes",
    response_model=list[ChangeItem],
    summary="Retrieve system changes telemetry",
    tags=["Telemetry"],
)
def get_changes(
    machine_id: Annotated[str | None, Query(description="Optional machine ID filter")] = None,
) -> list[ChangeItem]:
    """Retrieve collected driver, Windows Update, and event log changes."""
    try:
        items = service.get_changes(machine_id=machine_id)
        return [ChangeItem(**item) for item in items]
    except Exception as exc:
        logger.exception("Error loading system changes: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system changes.",
        ) from exc


# ----------------------------------------------------------------------
# Demonstration Seeder
# ----------------------------------------------------------------------


@app.post(
    "/api/demo/seed",
    response_model=DemoSeedResponse,
    summary="Seed deterministic synthetic demonstration data",
    tags=["Demonstration"],
)
def seed_demo_data() -> DemoSeedResponse:
    """Seed synthetic demonstration datasets covering ready baselines, regressions, and sparse history."""
    try:
        summary = seed_demo_datasets()
        return DemoSeedResponse(**summary)
    except Exception as exc:
        logger.exception("Error seeding demonstration data: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to seed synthetic demo datasets.",
        ) from exc

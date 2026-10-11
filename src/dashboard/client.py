"""HTTP Client for PARCS FastAPI backend with graceful fallback.

Allows the Streamlit dashboard to interact with the backend API service,
while providing resilient fallbacks when running in standalone mode.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.api.service import AnalyticsService

logger = logging.getLogger(__name__)

DEFAULT_API_URL = "http://127.0.0.1:8000"


class PARCSApiClient:
    """Client for querying PARCS FastAPI backend."""

    def __init__(self, base_url: str = DEFAULT_API_URL, timeout: float = 1.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._local_fallback = AnalyticsService()
        self._online_status: bool | None = None

    def is_online(self) -> bool:
        """Check whether the API backend is reachable, caching status for the session."""
        if self._online_status is not None:
            return self._online_status

        try:
            with httpx.Client(timeout=min(self.timeout, 0.5)) as client:
                res = client.get(f"{self.base_url}/health")
                self._online_status = (res.status_code == 200)
        except Exception:  # noqa: BLE001
            self._online_status = False

        return self._online_status

    def get_health(self) -> dict[str, Any]:
        """Check API backend health."""
        if self.is_online():
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    res = client.get(f"{self.base_url}/health")
                    if res.status_code == 200:
                        data = res.json()
                        data["connection"] = "online"
                        return data
            except Exception as exc:  # noqa: BLE001
                logger.debug("API health check failed: %s", exc)
                self._online_status = False

        return {
            "status": "offline",
            "service": "PARCS API (Local Mode)",
            "connection": "offline",
            "version": "1.0.0",
            "timestamp": None,
        }

    def get_telemetry_summary(self) -> dict[str, Any]:
        """Retrieve telemetry summary."""
        if self.is_online():
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    res = client.get(f"{self.base_url}/api/telemetry/summary")
                    if res.status_code == 200:
                        return res.json()
            except Exception as exc:  # noqa: BLE001
                logger.debug("API get_telemetry_summary failed, using fallback: %s", exc)
                self._online_status = False

        return self._local_fallback.get_telemetry_summary()


    def get_baselines(
        self,
        machine_id: str | None = None,
        min_observations: int = 10,
    ) -> list[dict[str, Any]]:
        """Retrieve machine statistical baselines."""
        if self.is_online():
            try:
                params: dict[str, Any] = {"min_observations": min_observations}
                if machine_id:
                    params["machine_id"] = machine_id
                with httpx.Client(timeout=self.timeout) as client:
                    res = client.get(f"{self.base_url}/api/analytics/baselines", params=params)
                    if res.status_code == 200:
                        return res.json()
            except Exception as exc:  # noqa: BLE001
                logger.debug("API get_baselines failed, using fallback: %s", exc)
                self._online_status = False

        return self._local_fallback.get_baselines(machine_id=machine_id, min_observations=min_observations)

    def get_anomalies(
        self,
        machine_id: str | None = None,
        threshold: float = 3.5,
    ) -> list[dict[str, Any]]:
        """Retrieve detected statistical anomalies."""
        if self.is_online():
            try:
                params: dict[str, Any] = {"threshold": threshold}
                if machine_id:
                    params["machine_id"] = machine_id
                with httpx.Client(timeout=self.timeout) as client:
                    res = client.get(f"{self.base_url}/api/analytics/anomalies", params=params)
                    if res.status_code == 200:
                        return res.json()
            except Exception as exc:  # noqa: BLE001
                logger.debug("API get_anomalies failed, using fallback: %s", exc)
                self._online_status = False

        return self._local_fallback.get_anomalies(machine_id=machine_id, threshold=threshold)

    def get_regressions(
        self,
        machine_id: str | None = None,
        threshold: float = 2.0,
        min_consecutive: int = 3,
        only_regressions: bool = False,
    ) -> list[dict[str, Any]]:
        """Retrieve sustained performance regressions."""
        if self.is_online():
            try:
                params: dict[str, Any] = {
                    "threshold": threshold,
                    "min_consecutive": min_consecutive,
                    "only_regressions": only_regressions,
                }
                if machine_id:
                    params["machine_id"] = machine_id
                with httpx.Client(timeout=self.timeout) as client:
                    res = client.get(f"{self.base_url}/api/analytics/regressions", params=params)
                    if res.status_code == 200:
                        return res.json()
            except Exception as exc:  # noqa: BLE001
                logger.debug("API get_regressions failed, using fallback: %s", exc)
                self._online_status = False

        return self._local_fallback.get_regressions(
            machine_id=machine_id,
            threshold=threshold,
            min_consecutive=min_consecutive,
            only_regressions=only_regressions,
        )

    def get_correlations(
        self,
        machine_id: str | None = None,
        window_before_hours: float = 24.0,
        window_after_hours: float = 2.0,
        only_regressions: bool = True,
    ) -> list[dict[str, Any]]:
        """Retrieve change correlation records."""
        if self.is_online():
            try:
                params: dict[str, Any] = {
                    "window_before_hours": window_before_hours,
                    "window_after_hours": window_after_hours,
                    "only_regressions": only_regressions,
                }
                if machine_id:
                    params["machine_id"] = machine_id
                with httpx.Client(timeout=self.timeout) as client:
                    res = client.get(f"{self.base_url}/api/analytics/correlations", params=params)
                    if res.status_code == 200:
                        return res.json()
            except Exception as exc:  # noqa: BLE001
                logger.debug("API get_correlations failed, using fallback: %s", exc)
                self._online_status = False

        return self._local_fallback.get_correlations(
            machine_id=machine_id,
            window_before_hours=window_before_hours,
            window_after_hours=window_after_hours,
            only_regressions=only_regressions,
        )

    def get_changes(self, machine_id: str | None = None) -> list[dict[str, Any]]:
        """Retrieve system changes dataset."""
        if self.is_online():
            try:
                params: dict[str, Any] = {}
                if machine_id:
                    params["machine_id"] = machine_id
                with httpx.Client(timeout=self.timeout) as client:
                    res = client.get(f"{self.base_url}/api/changes", params=params)
                    if res.status_code == 200:
                        return res.json()
            except Exception as exc:  # noqa: BLE001
                logger.debug("API get_changes failed, using fallback: %s", exc)
                self._online_status = False

        return self._local_fallback.get_changes(machine_id=machine_id)

    def seed_demo_data(self) -> dict[str, Any]:
        """Request the API to seed synthetic demo data."""
        if self.is_online():
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    res = client.post(f"{self.base_url}/api/demo/seed")
                    if res.status_code == 200:
                        return res.json()
            except Exception as exc:  # noqa: BLE001
                logger.debug("API seed_demo_data failed, using local seeder: %s", exc)
                self._online_status = False

        from src.utils.demo_data import seed_demo_datasets
        return seed_demo_datasets()


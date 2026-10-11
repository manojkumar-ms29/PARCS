"""Base collector interface for PARCS.

All PARCS collectors inherit from BaseCollector and return CollectorResult.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class CollectorResult:
    """Standardized result returned by all PARCS collectors.

    Attributes:
        collector: Name of the collector that produced this result.
        collected_at: ISO 8601 UTC timestamp when collection occurred.
        source: Description of the data source (e.g. command, API).
        data: Extracted structured data (collector-specific).
        raw_report_path: Path to the preserved raw report, if any.
        error: Error message if collection failed.
        success: Whether collection completed successfully.
    """

    collector: str
    collected_at: str
    source: str
    data: list[dict[str, Any]] | dict[str, Any] | None = None
    raw_report_path: str | None = None
    error: str | None = None
    success: bool = True


class BaseCollector(ABC):
    """Abstract base class for all PARCS data collectors.

    Subclasses must implement the ``name`` property and ``collect()`` method.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this collector."""
        ...

    @abstractmethod
    def collect(self) -> CollectorResult:
        """Execute collection and return structured results."""
        ...

    def _now_iso(self) -> str:
        """Return current UTC time as ISO 8601 string."""
        return datetime.now(timezone.utc).isoformat()

    def _error_result(self, error: str, source: str = "") -> CollectorResult:
        """Create a failed CollectorResult with an error message."""
        return CollectorResult(
            collector=self.name,
            collected_at=self._now_iso(),
            source=source,
            data=None,
            error=error,
            success=False,
        )

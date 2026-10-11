"""PARCS FastAPI Backend Module."""

from src.api.app import app
from src.api.service import AnalyticsService

__all__ = ["app", "AnalyticsService"]

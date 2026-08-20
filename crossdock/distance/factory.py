"""Factory for DistanceProvider adapters."""

from __future__ import annotations

from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from crossdock.config import Settings, get_settings
from crossdock.distance.haversine import HaversineDistanceProvider
from crossdock.distance.osrm import OsrmDistanceProvider
from crossdock.distance.osrm_client import OsrmClient


class DistanceProvider(Protocol):
    def distance_km(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float: ...

    def distance_matrix(
        self,
        points: list[tuple[float, float]],
    ) -> NDArray[np.float64]: ...


def build_osrm_client(settings: Settings | None = None) -> OsrmClient:
    cfg = settings or get_settings()
    return OsrmClient(
        cfg.osrm_url,
        profile=cfg.osrm_profile,
        timeout_s=cfg.osrm_timeout_s,
    )


def get_distance_provider(settings: Settings | None = None) -> DistanceProvider:
    """Return OSRM provider when enabled, otherwise haversine (no I/O)."""
    cfg = settings or get_settings()
    if cfg.use_osrm:
        return OsrmDistanceProvider(build_osrm_client(cfg))
    return HaversineDistanceProvider()

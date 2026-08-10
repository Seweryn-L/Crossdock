"""DistanceProvider port — haversine (Faza 1) / OSRM (Faza 2)."""

from __future__ import annotations

from typing import Protocol

import numpy as np
from numpy.typing import NDArray


class DistanceProvider(Protocol):
    """Port: distances in kilometres between geographic points."""

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
    ) -> NDArray[np.float64]:
        """Return NxN matrix of kilometres; diagonal is 0."""
        ...

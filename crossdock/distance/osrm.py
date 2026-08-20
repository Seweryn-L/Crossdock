"""OSRM DistanceProvider adapter — road network distances (Faza 2)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from crossdock.distance.osrm_client import OsrmClient


class OsrmDistanceProvider:
    """Faza 2 adapter: road distances via OSRM ``/table`` (HTTP I/O)."""

    def __init__(self, client: OsrmClient) -> None:
        self._client = client

    def distance_km(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        matrix = self.distance_matrix([(lat1, lon1), (lat2, lon2)])
        return float(matrix[0, 1])

    def distance_matrix(
        self,
        points: list[tuple[float, float]],
    ) -> NDArray[np.float64]:
        metres = self._client.table_distances_m(points)
        n = len(points)
        matrix = np.zeros((n, n), dtype=np.float64)
        for i in range(n):
            for j in range(n):
                matrix[i, j] = metres[i][j] / 1000.0
        return matrix

    def route_polyline(self, points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        return self._client.route_polyline(points)

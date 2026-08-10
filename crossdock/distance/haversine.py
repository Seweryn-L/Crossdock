"""Straight-line (haversine) distance — Faza 1 DistanceProvider adapter."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 points in kilometres."""
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    d_phi = np.radians(lat2 - lat1)
    d_lambda = np.radians(lon2 - lon1)
    a = np.sin(d_phi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(d_lambda / 2) ** 2
    return float(2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a)))


class HaversineDistanceProvider:
    """Faza 1 adapter: straight-line distances (no I/O)."""

    def distance_km(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        return haversine_km(lat1, lon1, lat2, lon2)

    def distance_matrix(
        self,
        points: list[tuple[float, float]],
    ) -> NDArray[np.float64]:
        n = len(points)
        matrix = np.zeros((n, n), dtype=np.float64)
        for i in range(n):
            lat_i, lon_i = points[i]
            for j in range(i + 1, n):
                lat_j, lon_j = points[j]
                d = haversine_km(lat_i, lon_i, lat_j, lon_j)
                matrix[i, j] = d
                matrix[j, i] = d
        return matrix

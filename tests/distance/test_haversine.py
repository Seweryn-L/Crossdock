"""Haversine distance provider tests."""

from __future__ import annotations

import numpy as np

from crossdock.distance.haversine import HaversineDistanceProvider, haversine_km

# Approx. Antwerp (51.22, 4.40) - Brussels (50.85, 4.35) ~40-50 km.
ANTWERP = (51.2213, 4.4051)
BRUSSELS = (50.8503, 4.3517)


def test_antwerp_brussels_distance_plausible() -> None:
    km = haversine_km(*ANTWERP, *BRUSSELS)
    assert 35.0 < km < 55.0


def test_distance_matrix_symmetric_zero_diagonal() -> None:
    provider = HaversineDistanceProvider()
    points = [ANTWERP, BRUSSELS, (51.176, 4.836)]
    matrix = provider.distance_matrix(points)
    assert matrix.shape == (3, 3)
    assert np.allclose(np.diag(matrix), 0.0)
    assert np.allclose(matrix, matrix.T)

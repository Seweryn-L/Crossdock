"""OSRM client and DistanceProvider tests (mocked httpx — no real OSRM)."""

from __future__ import annotations

import httpx
import numpy as np
import pytest

from crossdock.distance.osrm import OsrmDistanceProvider
from crossdock.distance.osrm_client import OsrmClient


def _handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if "/table/" in url:
        # 2x2 matrix: 0 / 12345 m
        return httpx.Response(
            200,
            json={
                "code": "Ok",
                "distances": [
                    [0.0, 12345.0],
                    [12345.0, 0.0],
                ],
            },
        )
    if "/route/" in url:
        return httpx.Response(
            200,
            json={
                "code": "Ok",
                "routes": [
                    {
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [4.84, 51.18],
                                [4.85, 51.185],
                                [4.90, 51.20],
                            ],
                        }
                    }
                ],
            },
        )
    return httpx.Response(404, json={"code": "NoRoute"})


@pytest.fixture
def osrm_client() -> OsrmClient:
    transport = httpx.MockTransport(_handler)
    return OsrmClient("http://osrm.test", profile="driving", transport=transport)


def test_table_distances_m(osrm_client: OsrmClient) -> None:
    matrix = osrm_client.table_distances_m([(51.18, 4.84), (51.20, 4.90)])
    assert matrix == [[0.0, 12345.0], [12345.0, 0.0]]


def test_table_cache_hits(osrm_client: OsrmClient) -> None:
    a = osrm_client.table_distances_m([(51.18, 4.84), (51.20, 4.90)])
    b = osrm_client.table_distances_m([(51.18, 4.84), (51.20, 4.90)])
    assert a == b


def test_route_polyline_lat_lon_order(osrm_client: OsrmClient) -> None:
    poly = osrm_client.route_polyline([(51.18, 4.84), (51.20, 4.90)])
    assert poly[0] == (51.18, 4.84)
    assert poly[-1] == (51.20, 4.90)
    assert len(poly) == 3


def test_distance_provider_km(osrm_client: OsrmClient) -> None:
    provider = OsrmDistanceProvider(osrm_client)
    matrix = provider.distance_matrix([(51.18, 4.84), (51.20, 4.90)])
    assert matrix.shape == (2, 2)
    assert np.isclose(matrix[0, 1], 12.345)
    assert provider.distance_km(51.18, 4.84, 51.20, 4.90) == pytest.approx(12.345)

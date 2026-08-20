"""OSRM HTTP client — table (matrix) + route (geometry)."""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any

import httpx


def _coord_key(
    points: list[tuple[float, float]], *, decimals: int = 5
) -> tuple[tuple[float, float], ...]:
    return tuple((round(lat, decimals), round(lon, decimals)) for lat, lon in points)


def _lon_lat_path(points: list[tuple[float, float]]) -> str:
    """OSRM expects lon,lat (not lat,lon)."""
    return ";".join(f"{lon},{lat}" for lat, lon in points)


class _LruCache:
    """Simple thread-safe LRU for pickle-friendly keys."""

    def __init__(self, maxsize: int = 256) -> None:
        self._maxsize = maxsize
        self._data: OrderedDict[Any, Any] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: Any) -> Any | None:
        with self._lock:
            if key not in self._data:
                return None
            self._data.move_to_end(key)
            return self._data[key]

    def put(self, key: Any, value: Any) -> None:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = value
            while len(self._data) > self._maxsize:
                self._data.popitem(last=False)


class OsrmClient:
    """Sync OSRM client for use inside ``run.io_bound`` (thread pool)."""

    def __init__(
        self,
        base_url: str,
        *,
        profile: str = "driving",
        timeout_s: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        cache_size: int = 256,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._profile = profile
        self._timeout = timeout_s
        self._transport = transport
        self._table_cache = _LruCache(cache_size)
        self._route_cache = _LruCache(cache_size)

    def _client(self) -> httpx.Client:
        kwargs: dict[str, Any] = {"timeout": self._timeout, "base_url": self._base_url}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.Client(**kwargs)

    def table_distances_m(self, points: list[tuple[float, float]]) -> list[list[float]]:
        """Return NxN distance matrix in metres via ``/table``."""
        if len(points) < 1:
            return []
        if len(points) == 1:
            return [[0.0]]
        key = ("table", self._profile, _coord_key(points))
        cached = self._table_cache.get(key)
        if cached is not None:
            return cached

        path = f"/table/v1/{self._profile}/{_lon_lat_path(points)}"
        with self._client() as client:
            response = client.get(path, params={"annotations": "distance"})
            response.raise_for_status()
            payload = response.json()
        if payload.get("code") != "Ok":
            raise RuntimeError(f"OSRM table failed: {payload.get('code')}")
        distances = payload.get("distances")
        if not isinstance(distances, list) or len(distances) != len(points):
            raise RuntimeError("OSRM table response missing distances matrix")
        matrix: list[list[float]] = []
        for row in distances:
            if not isinstance(row, list) or len(row) != len(points):
                raise RuntimeError("OSRM table row size mismatch")
            matrix.append([float(0.0 if cell is None else cell) for cell in row])
        self._table_cache.put(key, matrix)
        return matrix

    def route_polyline(self, points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """Return road geometry as (lat, lon) points via ``/route``."""
        if len(points) < 2:
            return list(points)
        key = ("route", self._profile, _coord_key(points))
        cached = self._route_cache.get(key)
        if cached is not None:
            return cached

        path = f"/route/v1/{self._profile}/{_lon_lat_path(points)}"
        with self._client() as client:
            response = client.get(
                path,
                params={"overview": "full", "geometries": "geojson"},
            )
            response.raise_for_status()
            payload = response.json()
        if payload.get("code") != "Ok":
            raise RuntimeError(f"OSRM route failed: {payload.get('code')}")
        routes = payload.get("routes") or []
        if not routes:
            raise RuntimeError("OSRM route response has no routes")
        geometry = routes[0].get("geometry") or {}
        coords = geometry.get("coordinates")
        if not isinstance(coords, list) or not coords:
            raise RuntimeError("OSRM route response missing geometry")
        polyline = [(float(lat), float(lon)) for lon, lat in coords]
        self._route_cache.put(key, polyline)
        return polyline

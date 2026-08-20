"""Bearing helper for map direction arrows."""

from __future__ import annotations

import math

_EARTH_RADIUS_KM = 6371.0


def bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing from point 1 to point 2 in degrees (0 = north)."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)
    y = math.sin(d_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, a)))


def segment_arrows(
    polyline: list[tuple[float, float]] | tuple[tuple[float, float], ...],
    *,
    color: str,
    min_distance_km: float = 8.0,
) -> list[dict[str, float | str]]:
    """Direction arrows along a polyline, spaced by minimum ground distance.

    Dense OSRM geometry would otherwise place an arrow on every tiny segment.
    With ``min_distance_km <= 0``, falls back to one arrow per distinct segment
    (legacy behaviour).
    """
    points = list(polyline)
    out: list[dict[str, float | str]] = []
    if len(points) < 2:
        return out

    if min_distance_km <= 0:
        for i in range(len(points) - 1):
            lat1, lon1 = points[i]
            lat2, lon2 = points[i + 1]
            if lat1 == lat2 and lon1 == lon2:
                continue
            out.append(
                {
                    "lat": (lat1 + lat2) / 2.0,
                    "lon": (lon1 + lon2) / 2.0,
                    "bearing": bearing_degrees(lat1, lon1, lat2, lon2),
                    "color": color,
                }
            )
        return out

    dist_since_arrow = min_distance_km  # force first eligible segment
    for i in range(len(points) - 1):
        lat1, lon1 = points[i]
        lat2, lon2 = points[i + 1]
        if lat1 == lat2 and lon1 == lon2:
            continue
        seg_km = _haversine_km(lat1, lon1, lat2, lon2)
        dist_since_arrow += seg_km
        if dist_since_arrow < min_distance_km:
            continue
        out.append(
            {
                "lat": (lat1 + lat2) / 2.0,
                "lon": (lon1 + lon2) / 2.0,
                "bearing": bearing_degrees(lat1, lon1, lat2, lon2),
                "color": color,
            }
        )
        dist_since_arrow = 0.0
    return out


def leg_arrows(
    polyline: list[tuple[float, float]] | tuple[tuple[float, float], ...],
    waypoints: list[tuple[float, float]] | tuple[tuple[float, float], ...],
    *,
    color: str,
    arrows_per_leg: int = 1,
) -> list[dict[str, float | str]]:
    """Place a few arrows per stop-to-stop leg using dense polyline geometry."""
    points = list(polyline)
    stops = list(waypoints)
    if len(points) < 2 or len(stops) < 2:
        return segment_arrows(points, color=color)

    def _nearest_index(target: tuple[float, float], start_at: int = 0) -> int:
        best_i = start_at
        best_d = float("inf")
        t_lat, t_lon = target
        for i in range(start_at, len(points)):
            d = _haversine_km(points[i][0], points[i][1], t_lat, t_lon)
            if d < best_d:
                best_d = d
                best_i = i
        return best_i

    out: list[dict[str, float | str]] = []
    idx = 0
    n = max(1, arrows_per_leg)
    for s in range(len(stops) - 1):
        i0 = _nearest_index(stops[s], idx)
        i1 = _nearest_index(stops[s + 1], i0)
        if i1 <= i0:
            i1 = min(len(points) - 1, i0 + 1)
        idx = i1
        span = i1 - i0
        if span <= 0:
            continue
        for k in range(n):
            t = (k + 1) / (n + 1)
            pos = i0 + max(0, min(span - 1, int(span * t)))
            lat1, lon1 = points[pos]
            lat2, lon2 = points[min(pos + 1, len(points) - 1)]
            if lat1 == lat2 and lon1 == lon2:
                continue
            out.append(
                {
                    "lat": (lat1 + lat2) / 2.0,
                    "lon": (lon1 + lon2) / 2.0,
                    "bearing": bearing_degrees(lat1, lon1, lat2, lon2),
                    "color": color,
                }
            )
    return out

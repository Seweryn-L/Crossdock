"""Bearing helper for map direction arrows."""

from __future__ import annotations

import math


def bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing from point 1 to point 2 in degrees (0 = north)."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)
    y = math.sin(d_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def segment_arrows(
    polyline: list[tuple[float, float]] | tuple[tuple[float, float], ...],
    *,
    color: str,
) -> list[dict[str, float | str]]:
    """Midpoint arrows for consecutive polyline points."""
    points = list(polyline)
    out: list[dict[str, float | str]] = []
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

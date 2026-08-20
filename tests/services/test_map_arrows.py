"""Tests for map direction arrow spacing helpers."""

from __future__ import annotations

from crossdock.services.map_arrows import leg_arrows, segment_arrows


def _dense_polyline() -> list[tuple[float, float]]:
    # ~1 km steps along a meridian near depot (lat deltas ~0.009)
    return [(51.176 + i * 0.009, 4.836) for i in range(40)]


def test_segment_arrows_spaced_fewer_than_every_segment() -> None:
    poly = _dense_polyline()
    dense = segment_arrows(poly, color="#111", min_distance_km=0)
    spaced = segment_arrows(poly, color="#111", min_distance_km=8.0)
    assert len(dense) == len(poly) - 1
    assert len(spaced) < len(dense)
    assert len(spaced) >= 1
    assert all(a["color"] == "#111" for a in spaced)
    assert all("bearing" in a for a in spaced)


def test_leg_arrows_one_per_stop_leg() -> None:
    # Dense geometry between three stops
    waypoints = [
        (51.176, 4.836),
        (51.5, 4.836),
        (51.8, 4.836),
        (51.176, 4.836),
    ]
    polyline: list[tuple[float, float]] = []
    for i in range(len(waypoints) - 1):
        lat1, lon1 = waypoints[i]
        lat2, lon2 = waypoints[i + 1]
        steps = 20
        for s in range(steps):
            t = s / steps
            polyline.append((lat1 + (lat2 - lat1) * t, lon1 + (lon2 - lon1) * t))
    polyline.append(waypoints[-1])

    arrows = leg_arrows(polyline, waypoints, color="#e41a1c", arrows_per_leg=1)
    # 3 legs (depot→A, A→B, B→depot)
    assert len(arrows) == 3
    assert all(a["color"] == "#e41a1c" for a in arrows)

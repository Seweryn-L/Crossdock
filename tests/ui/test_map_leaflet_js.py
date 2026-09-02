"""Tests for map Leaflet JS helpers."""

from __future__ import annotations

from crossdock.ui.map_leaflet_js import invalidate_map_javascript


def test_invalidate_map_javascript_targets_map_element() -> None:
    js = invalidate_map_javascript(99)
    assert "'c' + 99" in js
    assert "invalidateSize" in js

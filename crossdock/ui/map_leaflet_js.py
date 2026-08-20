"""Small Leaflet helpers for /map (arrows + invalidateSize)."""

from __future__ import annotations

import json


def arrows_javascript(map_element_id: int, arrows: list[dict[str, float | str]]) -> str:
    """Inject spaced direction arrows onto an already-initialized NiceGUI leaflet map."""
    payload = json.dumps(arrows, ensure_ascii=False)
    return f"""
(() => {{
  const host = document.getElementById('c' + {map_element_id});
  const map = host && (host.map || (host.__vueParentComponent
    && host.__vueParentComponent.ctx
    && host.__vueParentComponent.ctx.map));
  if (!map || !window.L) return;
  if (window.__cdArrowLayer) {{
    try {{ map.removeLayer(window.__cdArrowLayer); }} catch (e) {{}}
  }}
  const layer = L.layerGroup();
  const arrows = {payload};
  arrows.forEach(a => {{
    const icon = L.divIcon({{
      className: '',
      html: '<div style="transform:rotate(' + a.bearing +
        'deg);color:' + a.color +
        ';font-size:18px;text-shadow:0 0 3px #fff;">▲</div>',
      iconSize: [20, 20],
      iconAnchor: [10, 10],
    }});
    L.marker([a.lat, a.lon], {{icon: icon, interactive: false}}).addTo(layer);
  }});
  layer.addTo(map);
  window.__cdArrowLayer = layer;
}})();
"""


def clear_arrows_javascript(map_element_id: int) -> str:
    return f"""
(() => {{
  const host = document.getElementById('c' + {map_element_id});
  const map = host && (host.map || (host.__vueParentComponent
    && host.__vueParentComponent.ctx
    && host.__vueParentComponent.ctx.map));
  if (!map || !window.__cdArrowLayer) return;
  try {{ map.removeLayer(window.__cdArrowLayer); }} catch (e) {{}}
  window.__cdArrowLayer = null;
}})();
"""


def invalidate_map_javascript(map_element_id: int) -> str:
    return f"""
(() => {{
  const host = document.getElementById('c' + {map_element_id});
  const map = host && (host.map || (host.__vueParentComponent
    && host.__vueParentComponent.ctx
    && host.__vueParentComponent.ctx.map));
  if (!map) return;
  setTimeout(() => {{ try {{ map.invalidateSize(); }} catch (e) {{}} }}, 80);
}})();
"""

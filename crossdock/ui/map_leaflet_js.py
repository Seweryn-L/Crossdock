"""Small Leaflet helpers for /map (arrows + invalidateSize + tooltips)."""

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


def bind_route_overlays_javascript(
    map_element_id: int,
    routes: list[dict[str, object]],
) -> str:
    """Bind hover tooltips + click popups on polylines after NiceGUI drew them.

    ``routes`` items: polyline (list of [lat,lon]), tooltip_html, detail_html, color.
    Matches layers by approximate first/last point + color.
    """
    payload = json.dumps(routes, ensure_ascii=False)
    return f"""
(() => {{
  const host = document.getElementById('c' + {map_element_id});
  const map = host && (host.map || (host.__vueParentComponent
    && host.__vueParentComponent.ctx
    && host.__vueParentComponent.ctx.map));
  if (!map || !window.L) return;
  const routes = {payload};
  const nearly = (a, b) => Math.abs(a - b) < 1e-5;
  map.eachLayer(layer => {{
    if (!layer.getLatLngs || !layer.options) return;
    const latlngs = layer.getLatLngs();
    if (!latlngs || !latlngs.length) return;
    const flat = Array.isArray(latlngs[0]) ? latlngs.flat() : latlngs;
    if (flat.length < 2) return;
    const first = flat[0];
    const last = flat[flat.length - 1];
    const color = layer.options.color;
    for (const r of routes) {{
      const pts = r.polyline || [];
      if (pts.length < 2) continue;
      const p0 = pts[0];
      const p1 = pts[pts.length - 1];
      if (r.color && color && r.color !== color) continue;
      if (!nearly(first.lat, p0[0]) || !nearly(first.lng, p0[1])) continue;
      if (!nearly(last.lat, p1[0]) || !nearly(last.lng, p1[1])) continue;
      if (r.tooltip_html) {{
        layer.bindTooltip(r.tooltip_html, {{
          sticky: true,
          opacity: 0.95,
          className: 'cd-map-route-tooltip',
        }});
      }}
      if (r.detail_html) {{
        layer.bindPopup(r.detail_html);
      }}
      break;
    }}
  }});
}})();
"""

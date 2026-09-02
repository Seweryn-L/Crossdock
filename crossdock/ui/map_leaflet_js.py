"""Small Leaflet helpers for /map (invalidateSize after layout changes)."""

from __future__ import annotations


def invalidate_map_javascript(map_element_id: int) -> str:
    return f"""
(() => {{
  const host = document.getElementById('c' + {map_element_id});
  const vue = host && host.__vueParentComponent;
  const map = (vue && vue.ctx && vue.ctx.map) || (host && host.map) || null;
  if (!map) return;
  setTimeout(() => {{ try {{ map.invalidateSize(); }} catch (e) {{}} }}, 80);
}})();
"""

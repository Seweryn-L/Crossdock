"""Leaflet boot / filter helpers for the /map page (injected via ui.run_javascript)."""

from __future__ import annotations

# Runs in the browser; keeps route layers, arrows, and sequence markers under one API.
CD_MAP_JS = """
window.__cdMap = window.__cdMap || {
  map: null,
  depot: null,
  routes: {},
  showArrows: true,
  statusFilter: '',
  isolated: null,
  hidden: {},
  hover: null,
};

window.__cdMapResolve = function(hostId) {
  const host = document.getElementById(hostId);
  if (!host) return null;
  return host.map || (host.__vueParentComponent
    && host.__vueParentComponent.ctx
    && host.__vueParentComponent.ctx.map) || null;
};

window.__cdMapClear = function() {
  const st = window.__cdMap;
  if (!st.map) return;
  Object.values(st.routes).forEach(r => {
    if (r.polyline) st.map.removeLayer(r.polyline);
    (r.markers || []).forEach(m => st.map.removeLayer(m));
    (r.arrows || []).forEach(a => st.map.removeLayer(a));
  });
  if (st.depot) { st.map.removeLayer(st.depot); st.depot = null; }
  st.routes = {};
};

window.__cdMapBoot = function(hostId, data) {
  const map = window.__cdMapResolve(hostId);
  if (!map || !window.L) return;
  const st = window.__cdMap;
  st.map = map;
  window.__cdMapClear();

  if (data.depot) {
    st.depot = L.marker([data.depot.lat, data.depot.lon], {title: data.depot.title || 'Magazyn'})
      .addTo(map)
      .bindPopup(data.depot.popup || '');
  }

  (data.routes || []).forEach(route => {
    const approved = route.status === 'approved';
    const pl = L.polyline(route.polyline, {
      color: route.color,
      weight: approved ? 5 : 3,
      opacity: approved ? 0.9 : 0.45,
      dashArray: approved ? null : '8 8',
    }).addTo(map);
    pl._cdBase = {
      weight: approved ? 5 : 3,
      opacity: approved ? 0.9 : 0.45,
      dashArray: approved ? null : '8 8',
      color: route.color,
    };

    const markers = (route.markers || []).map(mk => {
      const seq = mk.sequence != null ? String(mk.sequence) : '';
      const icon = L.divIcon({
        className: '',
        html: '<div class="cd-map-seq-badge" style="--badge-bg:' + route.color + '">' +
          (seq || '•') + '</div>',
        iconSize: [22, 22],
        iconAnchor: [11, 11],
      });
      const marker = L.marker([mk.lat, mk.lon], {
        icon,
        title: seq ? (seq + ' · ' + mk.label) : mk.label,
      }).addTo(map);
      if (mk.popup) marker.bindPopup(mk.popup);
      return marker;
    });

    const arrows = (route.arrows || []).map(a => {
      const icon = L.divIcon({
        className: '',
        html: '<div style="transform:rotate(' + a.bearing +
          'deg);color:' + a.color +
          ';font-size:18px;text-shadow:0 0 3px #fff;">▲</div>',
        iconSize: [20, 20],
        iconAnchor: [10, 10],
      });
      return L.marker([a.lat, a.lon], {icon: icon, interactive: false}).addTo(map);
    });

    st.routes[route.code] = {
      status: route.status,
      polyline: pl,
      markers,
      arrows,
      bounds: route.polyline,
    };
  });

  window.__cdMapApply({
    statusFilter: st.statusFilter,
    isolated: st.isolated,
    hidden: st.hidden,
    showArrows: st.showArrows,
    hover: st.hover,
    fit: true,
  });
};

window.__cdMapVisibleCodes = function() {
  const st = window.__cdMap;
  return Object.keys(st.routes).filter(code => {
    const r = st.routes[code];
    if (st.statusFilter && r.status !== st.statusFilter) return false;
    if (st.hidden && st.hidden[code]) return false;
    if (st.isolated && st.isolated !== code) return false;
    return true;
  });
};

window.__cdMapApply = function(opts) {
  const st = window.__cdMap;
  if (!st.map) return;
  if (opts.statusFilter !== undefined) st.statusFilter = opts.statusFilter || '';
  if (opts.isolated !== undefined) st.isolated = opts.isolated;
  if (opts.hidden !== undefined) st.hidden = opts.hidden || {};
  if (opts.showArrows !== undefined) st.showArrows = !!opts.showArrows;
  if (opts.hover !== undefined) st.hover = opts.hover;

  const visible = new Set(window.__cdMapVisibleCodes());
  Object.keys(st.routes).forEach(code => {
    const r = st.routes[code];
    const show = visible.has(code);
    const base = r.polyline._cdBase;
    if (show) {
      st.map.addLayer(r.polyline);
      r.markers.forEach(m => st.map.addLayer(m));
      const dim = st.hover && st.hover !== code;
      const focus = st.hover === code || st.isolated === code;
      r.polyline.setStyle({
        color: base.color,
        weight: focus ? base.weight + 2 : (dim ? Math.max(2, base.weight - 1) : base.weight),
        opacity: dim ? Math.min(0.25, base.opacity) : (focus ? 1.0 : base.opacity),
        dashArray: base.dashArray,
      });
      if (st.showArrows) {
        r.arrows.forEach(a => st.map.addLayer(a));
      } else {
        r.arrows.forEach(a => st.map.removeLayer(a));
      }
    } else {
      st.map.removeLayer(r.polyline);
      r.markers.forEach(m => st.map.removeLayer(m));
      r.arrows.forEach(a => st.map.removeLayer(a));
    }
  });

  if (opts.fit) window.__cdMapFit();
};

window.__cdMapFit = function() {
  const st = window.__cdMap;
  if (!st.map) return;
  const visible = window.__cdMapVisibleCodes();
  const latlngs = [];
  if (st.depot) latlngs.push(st.depot.getLatLng());
  visible.forEach(code => {
    (st.routes[code].bounds || []).forEach(p => latlngs.push(L.latLng(p[0], p[1])));
  });
  if (latlngs.length >= 2) {
    st.map.fitBounds(L.latLngBounds(latlngs), {padding: [40, 40]});
  } else if (latlngs.length === 1) {
    st.map.setView(latlngs[0], st.map.getZoom());
  }
  setTimeout(() => { try { st.map.invalidateSize(); } catch (e) {} }, 50);
};

window.__cdMapInvalidate = function() {
  const st = window.__cdMap;
  if (!st.map) return;
  setTimeout(() => { try { st.map.invalidateSize(); } catch (e) {} }, 80);
};
"""

"""Genera grafana/dashboards/campus.json a partir del catálogo.
Cada gráfica muestra en la leyenda: promedio, máximo, mínimo y último valor.
Uso: python make_dashboard.py"""
import json
import os

from catalogo import DEVICES

DS = {"type": "influxdb", "uid": "influx"}


def flux(dev, field):
    return (f'from(bucket: "iot")\n  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)\n'
            f'  |> filter(fn: (r) => r._measurement == "iot" and r.device == "{dev}" and r._field == "{field}")\n'
            f'  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)\n'
            f'  |> map(fn: (r) => ({{r with _field: "{field}"}}))\n  |> keep(columns: ["_time", "_value", "_field"])')


def thresholds(steps):
    return {"mode": "absolute", "steps": [{"color": "green", "value": None}] +
            [{"color": c, "value": v} for v, c in steps]}


KPIS = [  # (dispositivo, variable, título, unidad, umbrales)
    ("clima", "temp", "Temperatura exterior", "celsius", [(30, "orange"), (33, "red")]),
    ("aire", "aqi", "Índice calidad aire", "none", [(50, "yellow"), (100, "orange"), (150, "red")]),
    ("salon", "co2", "CO2 salón", "ppm", [(1000, "orange"), (1200, "red")]),
    ("tanque", "nivel", "Nivel tanque", "percent", None),
    ("parqueadero", "ocupacion_pct", "Ocupación parqueadero", "percent", [(80, "orange"), (95, "red")]),
    ("bus", "velocidad", "Velocidad bus", "velocitykmh", None),
]

panels, pid, y = [], 1, 0
panels.append({"type": "row", "title": "Resumen (KPIs y alertas visuales)", "id": pid, "collapsed": False,
               "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}, "panels": []})
pid += 1
y += 1
for i, (dev, field, title, unit, steps) in enumerate(KPIS):
    th = thresholds(steps) if steps else {"mode": "absolute", "steps": [
        {"color": "red", "value": None}, {"color": "orange", "value": 20}, {"color": "green", "value": 30}]}
    panels.append({
        "type": "stat", "title": title, "id": pid, "datasource": DS,
        "gridPos": {"h": 5, "w": 4, "x": 4 * i, "y": y},
        "targets": [{"refId": "A", "datasource": DS, "query": flux(dev, field)}],
        "fieldConfig": {"defaults": {"unit": unit, "thresholds": th, "color": {"mode": "thresholds"}}, "overrides": []},
        "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                    "colorMode": "background", "graphMode": "area", "textMode": "value"}})
    pid += 1
y += 5

for dev, meta in DEVICES.items():
    panels.append({"type": "row", "title": meta["title"], "id": pid, "collapsed": False,
                   "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}, "panels": []})
    pid += 1
    y += 1
    fields = list(meta["fields"].items())
    w = 24 // min(3, len(fields)) if len(fields) <= 3 else 8
    for j, (field, (unit, label)) in enumerate(fields):
        x = (j % (24 // w)) * w
        if j and x == 0:
            y += 8
        panels.append({
            "type": "timeseries", "title": label, "id": pid, "datasource": DS,
            "gridPos": {"h": 8, "w": w, "x": x, "y": y},
            "targets": [{"refId": "A", "datasource": DS, "query": flux(dev, field)}],
            "fieldConfig": {"defaults": {"unit": unit, "custom": {"lineWidth": 2, "fillOpacity": 10,
                            "showPoints": "never", "spanNulls": True}, "displayName": label}, "overrides": []},
            "options": {"legend": {"displayMode": "table", "placement": "bottom", "showLegend": True,
                                   "calcs": ["mean", "max", "min", "lastNotNull"]},
                        "tooltip": {"mode": "single"}}})
        pid += 1
    y += 8

dash = {
    "uid": "campus-unab", "title": "IoT Campus UNAB", "tags": ["iot", "unab"], "timezone": "America/Bogota",
    "schemaVersion": 39, "version": 1, "editable": True, "refresh": "30s",
    "time": {"from": "now-6d", "to": "now"},
    "timepicker": {"refresh_intervals": ["10s", "30s", "1m", "5m", "15m"]},
    "panels": panels,
}
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "grafana", "dashboards", "campus.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(dash, f, ensure_ascii=False, indent=1)
print("Dashboard generado:", os.path.normpath(out), "-", len(panels), "paneles")

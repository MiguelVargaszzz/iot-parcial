"""Cliente mínimo de InfluxDB 2 por HTTP (solo requiere 'requests')."""
import csv
import io
import os

import requests

URL = os.getenv("INFLUX_URL", "http://influxdb:8086")
ORG = os.getenv("INFLUX_ORG", "unab")
BUCKET = os.getenv("INFLUX_BUCKET", "iot")
TOKEN = os.getenv("INFLUX_TOKEN", "")
H = {"Authorization": f"Token {TOKEN}"}


def query(flux):
    """Ejecuta Flux y devuelve una lista de dicts (todas las tablas juntas)."""
    r = requests.post(f"{URL}/api/v2/query", params={"org": ORG}, data=flux.encode(),
                      headers={**H, "Content-Type": "application/vnd.flux", "Accept": "application/csv"}, timeout=120)
    r.raise_for_status()
    rows, header = [], None
    for row in csv.reader(io.StringIO(r.text)):
        if not row or all(c == "" for c in row):
            header = None
            continue
        if header is None:
            header = row
            continue
        rows.append(dict(zip(header, row)))
    return rows


def write(lines):
    for i in range(0, len(lines), 5000):
        r = requests.post(f"{URL}/api/v2/write", params={"org": ORG, "bucket": BUCKET, "precision": "s"},
                          data="\n".join(lines[i:i + 5000]).encode(), headers=H, timeout=120)
        r.raise_for_status()


def delete(start_iso, stop_iso):
    r = requests.post(f"{URL}/api/v2/delete", params={"org": ORG, "bucket": BUCKET}, headers=H, timeout=120,
                      json={"start": start_iso, "stop": stop_iso, "predicate": '_measurement="iot"'})
    r.raise_for_status()

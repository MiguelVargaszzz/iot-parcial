"""Genera el histórico de N días ANTERIORES a la toma real de datos (30 min),
calibrado con las medias y desviaciones medidas en esa ventana real.

- API y nodo real: patrón diario (ciclo día/noche, horas pico) + ruido, anclado a la media real.
- Digital Twins: misma física que el gemelo en vivo, simulada en el tiempo.
- DataSets: se reproducen filas reales del CSV con marcas de tiempo del histórico.
- Se inyectan eventos (lluvia, pico de contaminación, falla de bomba, aire apagado) para el análisis.

Uso (en la VM):
    docker compose exec devices python /tools/generar_historico.py --dias 5
    docker compose exec devices python /tools/generar_historico.py --dias 5 --limpiar   # regenerar
    python generar_historico.py --dry-run                                              # prueba sin Influx
"""
import argparse
import csv
import math
import os
import random
from datetime import datetime, timedelta, timezone

from catalogo import DEVICES

COL = timezone(timedelta(hours=-5))  # Colombia (sin horario de verano)
random.seed(42)


# ---------------- formas de los patrones ----------------
def h_of(t):
    lt = t.astimezone(COL)
    return lt.hour + lt.minute / 60, lt.weekday()


def diurno(t, pico=14):
    h, _ = h_of(t)
    return math.cos(2 * math.pi * (h - pico) / 24)


def trafico(t):
    h, wd = h_of(t)
    f = 1.0 if wd < 5 else 0.4
    return f * (math.exp(-((h - 7) / 1.3) ** 2) + 0.8 * math.exp(-((h - 18) / 1.5) ** 2))


def sol(t):
    h, _ = h_of(t)
    return max(0.0, math.sin(math.pi * (h - 6) / 12)) if 6 <= h <= 18 else 0.0


def uso_pc(t):
    h, wd = h_of(t)
    return 1.0 if (8 <= h < 12 or 14 <= h < 23) else (0.3 if 7 <= h < 24 else 0.0)


def en_clase(t):
    h, wd = h_of(t)
    return (wd < 5 and (7 <= h < 12 or 14 <= h < 18)) or (wd == 5 and 7 <= h < 12)


# ---------------- eventos inyectados (día relativo al inicio) ----------------
class Eventos:
    def __init__(self, desde):
        d0 = desde.astimezone(COL).replace(hour=0, minute=0, second=0, microsecond=0)
        self.lluvia = (d0 + timedelta(days=2, hours=15), d0 + timedelta(days=2, hours=19))
        self.contaminacion = (d0 + timedelta(days=3, hours=6), d0 + timedelta(days=3, hours=10))
        self.falla_bomba = (d0 + timedelta(days=3, hours=20), d0 + timedelta(days=4, hours=8))
        self.ac_apagado = (d0 + timedelta(days=1, hours=14), d0 + timedelta(days=1, hours=18))

    @staticmethod
    def en(t, rango):
        return rango[0] <= t < rango[1]


# ---------------- campos "sin estado": (base, amplitud, forma, ruido, min, max, decimales) ----------------
STATELESS = {
    "clima": {
        "temp": (24.5, 4.5, diurno, 0.3, 14, 36, 1), "humedad": (72, -18, diurno, 2.0, 30, 100, 0),
        "viento": (8, 6, lambda t: diurno(t, 15), 2.0, 0, 50, 1), "uv": (0, 11, sol, 0.4, 0, 13, 0),
        "presion": (1012, 1.5, lambda t: math.cos(4 * math.pi * h_of(t)[0] / 24), 0.3, 1000, 1025, 1),
        "nubosidad": (55, -20, diurno, 10, 0, 100, 0)},
    "aire": {
        "aqi": (35, 25, trafico, 4, 0, 300, 0), "pm25": (12, 10, trafico, 1.5, 0, 150, 1),
        "pm10": (22, 15, trafico, 3, 0, 250, 1), "o3": (35, 30, sol, 4, 0, 200, 1),
        "no2": (15, 18, trafico, 2, 0, 200, 1), "co": (300, 250, trafico, 30, 0, 5000, 0)},
    "pronostico": {
        "temp_pronostico": (24.5, 4.5, lambda t: diurno(t, 13), 0.4, 14, 36, 1),
        "prob_lluvia": (25, 25, lambda t: diurno(t, 17), 8, 0, 100, 0),
        "humedad_pronostico": (72, -17, lambda t: diurno(t, 13), 2, 30, 100, 0)},
    "laptop": {
        "cpu": (6, 25, uso_pc, 6, 0, 100, 1), "ram": (55, 15, uso_pc, 2, 10, 98, 1),
        "red_kbps": (20, 400, uso_pc, 80, 0, 50000, 1)},
}
ANCHOR = set(STATELESS)  # estos dispositivos se anclan a la media real


def stateless_value(spec, t, offset=0.0, noise=None):
    base, amp, shape, rnd, lo, hi, dec = spec
    v = base + amp * shape(t) + offset + random.gauss(0, noise if noise is not None else rnd)
    return round(min(hi, max(lo, v)), dec)


# ---------------- simuladores con estado ----------------
class SimSalon:
    def __init__(self):
        self.co2, self.temp, self.ocup = 450.0, 23.0, 0

    def step(self, t, dt, ev):
        cap = 40
        obj = cap * random.uniform(0.6, 1.0) if en_clase(t) else 0
        self.ocup = max(0, min(cap, round(self.ocup + (obj - self.ocup) * 0.6)))
        for _ in range(int(dt // 10)):
            self.co2 += self.ocup * 4.0 - (self.co2 - 420) * 0.08
        self.co2 = max(400, min(3000, self.co2 + random.gauss(0, 15)))
        ac = 0 if ev.en(t, ev.ac_apagado) else (1 if en_clase(t) else 0)
        ext = 23 + 5 * diurno(t)
        self.temp += (ext - self.temp) * 0.3 + self.ocup * 0.02
        if ac:
            self.temp += (22 - self.temp) * 0.6
        self.temp += random.gauss(0, 0.1)
        return {"co2": round(self.co2, 1), "ocupacion": self.ocup, "temp": round(self.temp, 2), "ac": ac}


class SimParqueadero:
    def __init__(self):
        self.oc = 20.0

    def step(self, t, dt, ev):
        h, wd = h_of(t)
        if wd < 5:
            pct = 0.1 + 0.8 * math.exp(-((h - 10) / 3.5) ** 2) + 0.55 * math.exp(-((h - 15.5) / 2.5) ** 2)
        elif wd == 5:
            pct = 0.05 + 0.4 * math.exp(-((h - 10) / 2.5) ** 2)
        else:
            pct = 0.03
        self.oc += (min(1, pct) * 200 - self.oc) * 0.5 + random.gauss(0, 3)
        self.oc = max(0, min(200, self.oc))
        return {"ocupados": round(self.oc), "ocupacion_pct": round(self.oc / 2, 1)}


class SimTanque:
    def __init__(self):
        self.nivel, self.bomba = 70.0, 0

    def step(self, t, dt, ev):
        h, _ = h_of(t)
        consumo = 1.5 + (6 if 6 <= h < 20 else 0.5) * random.uniform(0.6, 1.4)
        if self.nivel < 30:
            self.bomba = 1
        elif self.nivel > 95:
            self.bomba = 0
        bomba = 0 if ev.en(t, ev.falla_bomba) else self.bomba
        self.nivel += ((14.0 if bomba else 0) - consumo) * dt / 60 / 50
        self.nivel = max(0, min(100, self.nivel))
        return {"nivel": round(self.nivel, 2), "caudal_salida": round(consumo, 2), "bomba": bomba}


class SimBus:
    """Recorrido circular alrededor del campus en horario de servicio."""
    def __init__(self, lat, lon):
        self.lat0, self.lon0, self.ang = lat, lon, 0.0

    def step(self, t, dt, ev):
        h, wd = h_of(t)
        servicio = (wd < 5 and 6 <= h < 21) or (wd == 5 and 7 <= h < 13)
        if servicio and random.random() > 0.15:
            v = max(0, random.gauss(28, 9) - 15 * trafico(t))
        else:
            v = 0.0
        self.ang += v * dt / 3600 / 6.0 * 2 * math.pi   # vuelta de ~6 km
        r = 0.012
        lat = self.lat0 + r * math.sin(self.ang) if servicio else self.lat0
        lon = self.lon0 + r * (math.cos(self.ang) - 1) if servicio else self.lon0
        return {"velocidad": round(v, 1), "en_movimiento": 1 if v > 3 else 0, "lat": round(lat, 6), "lon": round(lon, 6)}


class SimLaptopBateria:
    def __init__(self):
        self.b = 80.0

    def step(self, t, dt, ev):
        cargando = not (8 <= h_of(t)[0] < 13)   # desconectado en la mañana
        self.b += (0.8 if cargando else -0.35) * dt / 60
        self.b = max(5, min(100, self.b))
        return {"bateria": round(self.b), "cargando": 1 if cargando else 0}


def dataset_rows(path, columns, delimiter, decimal):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f, delimiter=delimiter):
            vals = {}
            for k, c in columns.items():
                s = (row.get(c) or "").strip().replace(decimal, ".") if decimal != "." else (row.get(c) or "").strip()
                try:
                    v = float(s)
                except ValueError:
                    continue
                if v != -200:
                    vals[k] = v
            if vals:
                rows.append(vals)
    return rows


DATASETS = {
    "estacion_aire_hist": ("AirQualityUCI.csv", {"co": "CO(GT)", "no2": "NO2(GT)", "benceno": "C6H6(GT)", "temp": "T", "humedad": "RH"}, ";", ","),
    "edificio_energia": ("energydata_complete.csv", {"consumo_wh": "Appliances", "luces_wh": "lights", "temp_interior": "T1",
                                                     "humedad_interior": "RH_1", "temp_exterior": "T_out"}, ",", "."),
}


# ---------------- programa principal ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=float, default=5)
    ap.add_argument("--paso", type=int, default=300, help="segundos entre puntos (300 = 5 min)")
    ap.add_argument("--limpiar", action="store_true", help="borra el histórico generado antes y lo vuelve a crear")
    ap.add_argument("--dry-run", action="store_true", help="no se conecta a InfluxDB, solo muestra ejemplos")
    ap.add_argument("--datasets", default="/app/datasets")
    a = ap.parse_args()

    marca = os.path.join(os.path.dirname(os.path.abspath(__file__)), "historico_marca.txt")
    stats = {}
    if a.dry_run:
        hasta = datetime.now(timezone.utc).replace(microsecond=0)
    else:
        import influx
        if os.path.exists(marca):
            hasta = datetime.fromisoformat(open(marca).read().strip())
        else:
            rows = influx.query(f'''from(bucket:"{influx.BUCKET}") |> range(start:-30d)
              |> filter(fn:(r)=> r._measurement=="iot") |> keep(columns:["_time"]) |> group()
              |> sort(columns:["_time"]) |> limit(n:1)''')
            if not rows:
                raise SystemExit("No hay datos reales en InfluxDB. Primero deja correr los dispositivos ~30 min.")
            hasta = datetime.fromisoformat(rows[0]["_time"].replace("Z", "+00:00")).replace(microsecond=0)
            open(marca, "w").write(hasta.isoformat())
        # estadísticas de la ventana REAL (desde 'hasta' en adelante)
        start = hasta.strftime("%Y-%m-%dT%H:%M:%SZ")
        for kind in ("mean", "stddev"):
            for r in influx.query(f'''from(bucket:"{influx.BUCKET}") |> range(start: {start})
                |> filter(fn:(r)=> r._measurement=="iot") |> group(columns:["device","_field"]) |> {kind}()'''):
                try:
                    stats.setdefault((r["device"], r["_field"]), {})[kind] = float(r["_value"])
                except (KeyError, ValueError):
                    pass
        # ventana real para el anclaje
        rows = influx.query(f'''from(bucket:"{influx.BUCKET}") |> range(start: {start})
              |> filter(fn:(r)=> r._measurement=="iot") |> keep(columns:["_time"]) |> group()
              |> sort(columns:["_time"], desc:true) |> limit(n:1)''')
        fin_real = datetime.fromisoformat(rows[0]["_time"].replace("Z", "+00:00")) if rows else hasta + timedelta(minutes=30)

    if a.dry_run:
        fin_real = hasta + timedelta(minutes=30)
    desde = hasta - timedelta(days=a.dias)
    print(f"Generando histórico desde {desde.astimezone(COL)} hasta {hasta.astimezone(COL)} (hora Colombia)")

    if a.limpiar and not a.dry_run:
        influx.delete(desde.strftime("%Y-%m-%dT%H:%M:%SZ"), hasta.strftime("%Y-%m-%dT%H:%M:%SZ"))
        print("Histórico anterior borrado.")

    # offsets de anclaje: media real - media del patrón en la ventana real
    offsets, noises = {}, {}
    ventana = [hasta + (fin_real - hasta) * i / 20 for i in range(21)]
    for dev, fields in STATELESS.items():
        for f, spec in fields.items():
            st = stats.get((dev, f))
            if st and "mean" in st:
                base, amp, shape = spec[0], spec[1], spec[2]
                syn = sum(base + amp * shape(t) for t in ventana) / len(ventana)
                offsets[(dev, f)] = st["mean"] - syn
                if st.get("stddev"):
                    noises[(dev, f)] = max(st["stddev"], spec[3] * 0.3)

    lat0 = stats.get(("bus", "lat"), {}).get("mean", float(os.getenv("LAT", "7.117030")))
    lon0 = stats.get(("bus", "lon"), {}).get("mean", float(os.getenv("LON", "-73.105338")))
    sims = {"salon": SimSalon(), "parqueadero": SimParqueadero(), "tanque": SimTanque(), "bus": SimBus(lat0, lon0)}
    bateria = SimLaptopBateria()
    ds = {k: dataset_rows(os.path.join(a.datasets, v[0]), *v[1:]) for k, v in DATASETS.items()}
    for k, rows in ds.items():
        print(f"  dataset {k}: {len(rows)} filas" + ("" if rows else " (no encontrado, se omite)"))
    ev = Eventos(desde)

    lines, t, i = [], desde, 0
    ejemplo = {}
    while t < hasta:
        ts = int(t.timestamp())
        out = {}
        for dev, fields in STATELESS.items():
            out[dev] = {f: stateless_value(spec, t, offsets.get((dev, f), 0.0), noises.get((dev, f)))
                        for f, spec in fields.items()}
        # eventos sobre campos sin estado
        if ev.en(t, ev.lluvia):
            out["clima"]["temp"] = round(out["clima"]["temp"] - 4, 1)
            out["clima"]["humedad"] = min(100, out["clima"]["humedad"] + 20)
            out["clima"]["nubosidad"] = 100
            out["pronostico"]["prob_lluvia"] = random.randint(80, 100)
            for p in ("pm25", "pm10", "aqi"):
                out["aire"][p] = round(out["aire"][p] * 0.5, 1)
        if ev.en(t, ev.contaminacion):
            for p, k in (("aqi", 2.5), ("pm25", 3), ("pm10", 2.5), ("no2", 2), ("co", 2)):
                out["aire"][p] = round(out["aire"][p] * k, 1)
        out["laptop"].update(bateria.step(t, a.paso, ev))
        for dev, sim in sims.items():
            out[dev] = sim.step(t, a.paso, ev)
        for dev, rows in ds.items():
            if rows:
                out[dev] = rows[i % len(rows)]
        for dev, vals in out.items():
            fs = ",".join(f"{k}={float(v)}" for k, v in vals.items())
            lines.append(f"iot,device={dev},type={DEVICES[dev]['type']} {fs} {ts}")
            ejemplo.setdefault(dev, vals)
        t += timedelta(seconds=a.paso)
        i += 1

    print(f"Puntos generados: {len(lines)} ({i} instantes x {len(out)} dispositivos)")
    if a.dry_run:
        for dev, vals in ejemplo.items():
            print(f"  {dev}: {vals}")
        print("Ejemplo de línea:", lines[len(lines) // 2])
        return
    influx.write(lines)
    print("Histórico escrito en InfluxDB. Eventos inyectados (hora Colombia):")
    for name in ("lluvia", "contaminacion", "falla_bomba", "ac_apagado"):
        r = getattr(ev, name)
        print(f"  {name}: {r[0]:%a %d %H:%M} → {r[1]:%a %d %H:%M}")


if __name__ == "__main__":
    main()

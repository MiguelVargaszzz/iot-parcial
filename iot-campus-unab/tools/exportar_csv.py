"""Exporta los datos para el documento y el análisis con IA:
  export/<dispositivo>.csv  -> series promediadas cada 15 min (todas las variables)
  export/resumen.csv        -> promedio, máximo, mínimo y nº de datos por variable
  export/prompt_ia.md       -> prompt listo para pegar en la IA junto con los CSV

Uso (en la VM): docker compose exec devices python /tools/exportar_csv.py
"""
import csv
import os

import influx
from catalogo import DEVICES

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "export")
os.makedirs(OUT, exist_ok=True)
B = influx.BUCKET

for dev in DEVICES:
    rows = influx.query(f'''from(bucket:"{B}") |> range(start:-30d)
      |> filter(fn:(r)=> r._measurement=="iot" and r.device=="{dev}")
      |> aggregateWindow(every: 15m, fn: mean, createEmpty: false)
      |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")
      |> drop(columns:["_start","_stop","_measurement","device","type"])''')
    if not rows:
        print(f"{dev}: sin datos")
        continue
    cols = ["_time"] + sorted(k for k in rows[0] if k not in ("", "result", "table", "_time"))
    with open(os.path.join(OUT, f"{dev}.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tiempo_utc"] + cols[1:])
        for r in sorted(rows, key=lambda r: r["_time"]):
            w.writerow([r.get(c, "") for c in cols])
    print(f"{dev}: {len(rows)} filas")

stats = {}
for kind in ("mean", "max", "min", "count"):
    for r in influx.query(f'''from(bucket:"{B}") |> range(start:-30d)
        |> filter(fn:(r)=> r._measurement=="iot") |> group(columns:["device","_field"]) |> {kind}()'''):
        stats.setdefault((r["device"], r["_field"]), {})[kind] = r["_value"]

with open(os.path.join(OUT, "resumen.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["dispositivo", "tipo", "variable", "promedio", "maximo", "minimo", "n_datos"])
    for (dev, field), s in sorted(stats.items()):
        tipo = DEVICES.get(dev, {}).get("type", "")
        w.writerow([dev, tipo, field, round(float(s.get("mean", 0)), 2), s.get("max"), s.get("min"), s.get("count")])

with open(os.path.join(OUT, "prompt_ia.md"), "w") as f:
    f.write("""Eres un analista de datos IoT. Te adjunto los CSV de 10 dispositivos de un sistema IoT
del campus UNAB (Bucaramanga, Colombia) tomados durante varios días (hora en UTC; Colombia es UTC-5),
y resumen.csv con promedio, máximo y mínimo por variable.

Para CADA dispositivo:
1. Describe el comportamiento de cada variable en el tiempo (tendencias, ciclo día/noche, horas pico, días distintos).
2. Señala anomalías o eventos (picos, caídas, valores fuera de rango) indicando día y hora en hora Colombia.
3. Relaciona variables entre sí y con otros dispositivos (ej. lluvia vs. calidad del aire, ocupación vs. CO2).
4. Propón reglas de alerta con umbrales concretos.
Al final da una conclusión general del sistema. Escribe en español, en párrafos, para un informe académico.
""")
print("Listo: archivos en", OUT)

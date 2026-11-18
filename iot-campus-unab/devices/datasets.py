"""Dispositivos que reproducen un DataSet (CSV) fila por fila como si fueran sensores.
Retroceso: off = pausa, set fila (saltar a una fila), set_interval (velocidad de reproducción)."""
import csv
import os

from common import Device


class CsvReplay(Device):
    type = "dataset"

    def __init__(self, device_id, file, columns, delimiter=",", decimal=".", missing=(-200,), interval=10):
        super().__init__(device_id, interval)
        self.file = file
        self.columns = columns          # {campo_publicado: columna_csv}
        self.delimiter = delimiter
        self.decimal = decimal
        self.missing = set(missing)
        self.rows = []
        self.params["fila"] = 0
        self._load()

    def _num(self, s):
        if s is None or str(s).strip() == "":
            return None
        try:
            v = float(str(s).replace(self.decimal, ".") if self.decimal != "." else s)
        except ValueError:
            return None
        return None if v in self.missing else v

    def _load(self):
        if not os.path.exists(self.file):
            self.log.warning("no existe %s: este dataset no publicará hasta que copies el CSV", self.file)
            return
        with open(self.file, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f, delimiter=self.delimiter):
                vals = {k: self._num(row.get(c)) for k, c in self.columns.items()}
                vals = {k: v for k, v in vals.items() if v is not None}
                if vals:
                    self.rows.append(vals)
        self.log.info("dataset cargado: %d filas", len(self.rows))

    def on_param(self, key, value):
        if key == "fila":
            self.params["fila"] = int(value)

    def read(self):
        if not self.rows:
            return None
        i = int(self.params["fila"]) % len(self.rows)
        self.params["fila"] = i + 1
        return {**self.rows[i], "fila": i}

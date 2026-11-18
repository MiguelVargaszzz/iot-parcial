"""Gemelos digitales (Digital Twins) con física sencilla y actuadores controlables."""
import math
import random
from datetime import datetime

from common import Device


def hora():
    n = datetime.now()
    return n.hour + n.minute / 60, n.weekday()


def en_clase(h, wd):
    return wd < 5 and (7 <= h < 12 or 14 <= h < 18) or (wd == 5 and 7 <= h < 12)


class Salon(Device):
    """Salón de clase: CO2, ocupación, temperatura y aire acondicionado.
    Retroceso: set ac (0/1), set setpoint (°C), set ventilacion (0.02-0.3)."""
    type = "digital_twin"

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.params.update({"ac": 1, "setpoint": 22.0, "ventilacion": 0.08, "capacidad": 40})
        self.co2, self.temp, self.ocup = 450.0, 24.0, 0

    def read(self):
        h, wd = hora()
        cap = int(self.params["capacidad"])
        objetivo = cap * random.uniform(0.6, 1.0) if en_clase(h, wd) else random.choice([0, 0, 0, 2])
        self.ocup = max(0, min(cap, round(self.ocup + (objetivo - self.ocup) * 0.3)))
        self.co2 += self.ocup * 4.0 - (self.co2 - 420) * float(self.params["ventilacion"]) + random.gauss(0, 5)
        self.co2 = max(400, min(3000, self.co2))
        ext = 23 + 5 * math.cos(2 * math.pi * (h - 14) / 24)
        self.temp += (ext - self.temp) * 0.05 + self.ocup * 0.004
        if int(self.params["ac"]):
            self.temp += (float(self.params["setpoint"]) - self.temp) * 0.15
        self.temp += random.gauss(0, 0.05)
        return {"co2": round(self.co2, 1), "ocupacion": self.ocup, "temp": round(self.temp, 2), "ac": int(self.params["ac"])}


class Parqueadero(Device):
    """Parqueadero del campus. Retroceso: set capacidad (calibrar cupos)."""
    type = "digital_twin"

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.params["capacidad"] = 200
        self.ocupados = 20.0

    def read(self):
        h, wd = hora()
        cap = int(self.params["capacidad"])
        if wd < 5:
            pct = 0.1 + 0.8 * math.exp(-((h - 10) / 3.5) ** 2) + 0.55 * math.exp(-((h - 15.5) / 2.5) ** 2)
        elif wd == 5:
            pct = 0.05 + 0.4 * math.exp(-((h - 10) / 2.5) ** 2)
        else:
            pct = 0.03
        objetivo = min(1.0, pct) * cap
        self.ocupados += (objetivo - self.ocupados) * 0.2 + random.gauss(0, 1.5)
        self.ocupados = max(0, min(cap, self.ocupados))
        oc = round(self.ocupados)
        return {"ocupados": oc, "ocupacion_pct": round(100 * oc / cap, 1), "capacidad": cap}


class Tanque(Device):
    """Tanque de agua. Retroceso: set bomba (0/1), set modo_auto (0/1), set umbral (%)."""
    type = "digital_twin"

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.params.update({"bomba": 0, "modo_auto": 1, "umbral": 30})
        self.nivel = 70.0

    def on_param(self, key, value):
        if key == "bomba":
            self.params["modo_auto"] = 0  # control manual desactiva el automático

    def read(self):
        h, wd = hora()
        consumo = 1.5 + (6 if 6 <= h < 20 else 0.5) * random.uniform(0.6, 1.4)   # L/min
        if int(self.params["modo_auto"]):
            if self.nivel < float(self.params["umbral"]):
                self.params["bomba"] = 1
            elif self.nivel > 95:
                self.params["bomba"] = 0
        entrada = 14.0 if int(self.params["bomba"]) else 0.0
        self.nivel += (entrada - consumo) * self.interval / 60 / 50   # tanque de 5000 L
        self.nivel = max(0, min(100, self.nivel))
        return {"nivel": round(self.nivel, 2), "caudal_salida": round(consumo, 2), "bomba": int(self.params["bomba"])}

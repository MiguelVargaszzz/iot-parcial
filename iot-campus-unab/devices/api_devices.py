"""Dispositivos de tipo API: Azure Maps Weather (clima, aire, pronóstico) y GPS Ruta UNAB."""
import os

import requests

from common import Device

AZ_KEY = os.getenv("AZURE_MAPS_KEY", "")
LAT = os.getenv("LAT", "7.117030")
LON = os.getenv("LON", "-73.105338")
AZ_BASE = "https://atlas.microsoft.com/weather"


def g(d, *keys, default=None):
    """Lee claves anidadas sin romperse si alguna no existe."""
    for k in keys:
        if isinstance(d, dict) and k in d:
            d = d[k]
        else:
            return default
    return d


def az_get(path, **extra):
    params = {"api-version": "1.1", "query": f"{LAT},{LON}", "subscription-key": AZ_KEY, "language": "es-MX"}
    params.update(extra)
    r = requests.get(f"{AZ_BASE}/{path}/json", params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def clean(d):
    return {k: v for k, v in d.items() if isinstance(v, (int, float))}


class ClimaActual(Device):
    """Azure Maps - Current Conditions."""
    type = "api"

    def read(self):
        r = az_get("currentConditions")["results"][0]
        return clean({
            "temp": g(r, "temperature", "value"),
            "sensacion": g(r, "realFeelTemperature", "value"),
            "humedad": g(r, "relativeHumidity"),
            "viento": g(r, "wind", "speed", "value"),
            "uv": g(r, "uvIndex"),
            "presion": g(r, "pressure", "value"),
            "nubosidad": g(r, "cloudCover"),
        })


class CalidadAire(Device):
    """Azure Maps - Air Quality current."""
    type = "api"
    MAP = {"PM2.5": "pm25", "PM10": "pm10", "O3": "o3", "NO2": "no2", "CO": "co", "SO2": "so2"}

    def read(self):
        r = az_get("airQuality/current", pollutants="true")["results"][0]
        out = {"aqi": g(r, "globalIndex")}
        for p in r.get("pollutants", []):
            name = self.MAP.get(p.get("type"))
            if name:
                out[name] = g(p, "concentration", "value")
        return clean(out)


class Pronostico(Device):
    """Azure Maps - Hourly forecast. Retroceso: set horas_adelante (1-12)."""
    type = "api"

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.params["horas_adelante"] = 1

    def read(self):
        h = max(1, min(12, int(self.params.get("horas_adelante", 1))))
        f = az_get("forecast/hourly", duration=12)["forecasts"][h - 1]
        return clean({
            "temp_pronostico": g(f, "temperature", "value"),
            "prob_lluvia": g(f, "precipitationProbability"),
            "humedad_pronostico": g(f, "relativeHumidity"),
            "viento_pronostico": g(f, "wind", "speed", "value"),
        })


class BusRutaUnab(Device):
    """API GPS de la Ruta UNAB (Basic Auth). Busca lat/lon/velocidad en la respuesta."""
    type = "api"
    KEYS = {"lat": ("lat", "latitud", "latitude"),
            "lon": ("lon", "lng", "longitud", "longitude"),
            "velocidad": ("velocidad", "speed", "vel")}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.url = os.getenv("GPS_URL")
        self.auth = (os.getenv("GPS_USER", ""), os.getenv("GPS_PASS", ""))
        self.warned = False

    def _search(self, obj, found):
        if isinstance(obj, dict):
            for k, v in obj.items():
                kl = k.lower()
                for name, aliases in self.KEYS.items():
                    if name not in found and kl in aliases:
                        try:
                            found[name] = float(v)
                        except (TypeError, ValueError):
                            pass
                self._search(v, found)
        elif isinstance(obj, list):
            for it in obj:
                self._search(it, found)

    def read(self):
        r = requests.get(self.url, auth=self.auth, timeout=20)
        r.raise_for_status()
        data = r.json()
        found = {}
        self._search(data, found)
        if not found and not self.warned:
            self.log.warning("no encontré lat/lon/velocidad. Respuesta: %s", str(data)[:500])
            self.warned = True
        if "velocidad" in found:
            found["en_movimiento"] = 1 if found["velocidad"] > 3 else 0
        return found

"""Arranca los 9 dispositivos que corren en la nube (el dispositivo real corre en tu PC)."""
import time

from api_devices import BusRutaUnab, CalidadAire, ClimaActual, Pronostico
from datasets import CsvReplay
from twins import Parqueadero, Salon, Tanque

DEVICES = [
    # API (consultan cada 60 s para no gastar cuota de Azure Maps)
    ClimaActual("clima", interval=60),
    CalidadAire("aire", interval=60),
    Pronostico("pronostico", interval=120),
    BusRutaUnab("bus", interval=20),
    # Digital Twins
    Salon("salon", interval=10),
    Parqueadero("parqueadero", interval=15),
    Tanque("tanque", interval=10),
    # DataSets (UCI Machine Learning Repository)
    CsvReplay("estacion_aire_hist", "datasets/AirQualityUCI.csv",
              {"co": "CO(GT)", "no2": "NO2(GT)", "benceno": "C6H6(GT)", "temp": "T", "humedad": "RH"},
              delimiter=";", decimal=",", interval=10),
    CsvReplay("edificio_energia", "datasets/energydata_complete.csv",
              {"consumo_wh": "Appliances", "luces_wh": "lights", "temp_interior": "T1",
               "humedad_interior": "RH_1", "temp_exterior": "T_out"},
              interval=10),
]

if __name__ == "__main__":
    for d in DEVICES:
        d.start()
    while True:
        time.sleep(60)

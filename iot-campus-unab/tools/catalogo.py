"""Catálogo de dispositivos y variables (lo usan el generador, el exportador y el dashboard)."""

DEVICES = {
    "laptop": {"type": "real", "title": "Nodo real · Computador", "fields": {
        "cpu": ("percent", "CPU"), "ram": ("percent", "RAM"), "bateria": ("percent", "Batería"),
        "red_kbps": ("Kbits", "Tráfico de red")}},
    "clima": {"type": "api", "title": "API · Clima actual (Azure Maps)", "fields": {
        "temp": ("celsius", "Temperatura"), "humedad": ("percent", "Humedad"), "viento": ("velocitykmh", "Viento"),
        "uv": ("none", "Índice UV"), "presion": ("pressurehpa", "Presión"), "nubosidad": ("percent", "Nubosidad")}},
    "aire": {"type": "api", "title": "API · Calidad del aire (Azure Maps)", "fields": {
        "aqi": ("none", "AQI"), "pm25": ("conμgm3", "PM2.5"), "pm10": ("conμgm3", "PM10"),
        "o3": ("conμgm3", "O3"), "no2": ("conμgm3", "NO2"), "co": ("conμgm3", "CO")}},
    "pronostico": {"type": "api", "title": "API · Pronóstico horario (Azure Maps)", "fields": {
        "temp_pronostico": ("celsius", "Temp. pronosticada"), "prob_lluvia": ("percent", "Prob. lluvia"),
        "humedad_pronostico": ("percent", "Humedad pronosticada")}},
    "bus": {"type": "api", "title": "API · Bus Ruta UNAB (GPS)", "fields": {
        "velocidad": ("velocitykmh", "Velocidad"), "en_movimiento": ("none", "En movimiento"),
        "lat": ("none", "Latitud"), "lon": ("none", "Longitud")}},
    "salon": {"type": "digital_twin", "title": "Digital Twin · Salón de clase", "fields": {
        "co2": ("ppm", "CO2"), "ocupacion": ("short", "Ocupación"), "temp": ("celsius", "Temperatura"), "ac": ("none", "Aire acond.")}},
    "parqueadero": {"type": "digital_twin", "title": "Digital Twin · Parqueadero", "fields": {
        "ocupados": ("short", "Cupos ocupados"), "ocupacion_pct": ("percent", "Ocupación")}},
    "tanque": {"type": "digital_twin", "title": "Digital Twin · Tanque de agua", "fields": {
        "nivel": ("percent", "Nivel"), "caudal_salida": ("short", "Caudal salida (L/min)"), "bomba": ("none", "Bomba")}},
    "estacion_aire_hist": {"type": "dataset", "title": "DataSet · Estación de calidad del aire (UCI)", "fields": {
        "co": ("short", "CO (mg/m3)"), "no2": ("conμgm3", "NO2"), "benceno": ("conμgm3", "Benceno"),
        "temp": ("celsius", "Temperatura"), "humedad": ("percent", "Humedad")}},
    "edificio_energia": {"type": "dataset", "title": "DataSet · Consumo energético edificio (UCI)", "fields": {
        "consumo_wh": ("watth", "Consumo electrodomésticos"), "luces_wh": ("watth", "Luces"),
        "temp_interior": ("celsius", "Temp. interior"), "humedad_interior": ("percent", "Humedad interior"),
        "temp_exterior": ("celsius", "Temp. exterior")}},
}

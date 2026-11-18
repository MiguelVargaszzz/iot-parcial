# IoT Campus UNAB · Proyecto Final IoT a la Medida

Sistema IoT para monitorear el ambiente, la movilidad y los recursos del campus UNAB (Bucaramanga).
Tiene 10 dispositivos de los cuatro tipos (Real, Digital Twin, API, DataSet), un broker MQTT,
almacenamiento en InfluxDB, visualización en Grafana y un panel web de control (retroceso).
Todo está desplegado en una VM de Azure con dominio propio y HTTPS.

## Arquitectura

```
[Dispositivos]                     [VM Azure · Docker]
 laptop (real, en tu PC) ──MQTT:1883──► Mosquitto ──► Telegraf ──► InfluxDB ──► Grafana ─┐
 clima/aire/pronostico (API Azure Maps)    ▲    │                                          │
 bus (API GPS Ruta UNAB)                   │    └──► Back FastAPI ◄── Panel web            │
 salon/parqueadero/tanque (Digital Twin)   │        (comandos /cmd = retroceso)            │
 estacion_aire_hist/edificio_energia (CSV) │                                               │
                                     unab/<id>/cmd                 Caddy (HTTPS) ◄─────────┘
                                                                  https://DOMINIO/  y  /grafana/
```

### Topics MQTT
| Topic | Dirección | Contenido |
|---|---|---|
| `unab/<id>/data` | dispositivo → broker (QoS 1) | `{"device":"salon","type":"digital_twin","co2":812,...}` |
| `unab/<id>/cmd` | panel → dispositivo (QoS 1) | `{"action":"off"}`, `{"action":"set_interval","value":30}`, `{"action":"calibrate","field":"temp","offset":-0.5}`, `{"action":"set","key":"ac","value":0}`, `{"action":"reset"}` |
| `unab/<id>/status` | dispositivo → broker (retained + LWT) | estado: encendido, intervalo, offsets, parámetros |

---

## PASO A PASO

### 1. Crear la máquina virtual en Azure
1. Activa **Azure for Students** con tu correo institucional en https://azure.microsoft.com/free/students
2. En https://portal.azure.com ve a **Máquinas virtuales → Crear → Máquina virtual de Azure**.
3. En la pestaña **Básico**:
   - Suscripción: *Azure for Students*. Grupo de recursos: **Crear nuevo → `rg-iot`**
   - Nombre: `vm-iot` · Región: *East US 2* (si sale "no disponible para la suscripción", prueba otra)
   - Imagen: **Ubuntu Server 24.04 LTS - x64 Gen2**
   - Tamaño: **Standard_B2s** (2 vCPU, 4 GB). Si no aparece, usa uno de 2 vCPU y 4 GB.
   - Autenticación: **Contraseña** · Usuario: `azureuser` · una contraseña fuerte
   - Puertos de entrada: marca **SSH (22), HTTP (80), HTTPS (443)**
4. **Revisar y crear → Crear**. Espera 1-2 minutos.
5. En la VM: **Redes → Configuración de red → Crear regla de puerto → Regla de puerto de entrada**:
   - Puerto de destino: `1883` · Protocolo: TCP · Acción: Permitir · Nombre: `MQTT` → Agregar.
6. Haz la IP fija: en la VM da clic en la **IP pública → Configuración → Asignación: Estática → Guardar**. Copia esa IP.

> Cuando terminen la sustentación, **detén la VM** (botón Detener) para no gastar crédito.

### 2. Dominio propio gratis (DuckDNS)
1. Entra a https://www.duckdns.org e inicia sesión con GitHub o Google.
2. Crea un subdominio (ej. `campusunab`) y en **current ip** pon la IP de la VM → **update ip**.
3. Tu URL será `https://campusunab.duckdns.org`.

### 3. Subir el proyecto a GitHub (en tu PC)
```bash
cd iot-campus-unab
git init
git add .
git commit -m "Proyecto IoT Campus UNAB"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/iot-campus-unab.git
git push -u origin main
```
(Crea antes el repo vacío en github.com. El `.env` no se sube porque está en `.gitignore`.)

### 4. Instalar y levantar todo en la VM
Desde PowerShell o una terminal en tu PC:
```bash
ssh azureuser@TU_IP
```
Ya dentro de la VM:
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
exit
```
Vuelve a conectarte con `ssh azureuser@TU_IP` y luego:
```bash
git clone https://github.com/TU_USUARIO/iot-campus-unab.git
cd iot-campus-unab
cp .env.example .env
nano .env        # llena DOMAIN, claves, AZURE_MAPS_KEY, GPS_USER, GPS_PASS. Guarda con Ctrl+O, Enter, Ctrl+X
chmod +x setup.sh
./setup.sh       # genera tokens y crea el usuario MQTT. ANOTA el CONTROL_TOKEN que imprime
```

**Datasets** (antes de levantar todo):
```bash
sudo apt install -y unzip
cd devices/datasets
wget -O aq.zip https://archive.ics.uci.edu/static/public/360/air+quality.zip && unzip -o aq.zip
wget -O en.zip https://archive.ics.uci.edu/static/public/374/appliances+energy+prediction.zip && unzip -o en.zip
ls      # deben estar AirQualityUCI.csv y energydata_complete.csv
cd ../..
```
(Si un enlace falla, busca "Air Quality" y "Appliances energy prediction" en https://archive.ics.uci.edu)

**Levantar:**
```bash
docker compose up -d --build
docker compose ps                 # todos deben estar "running"
docker compose logs -f devices    # ves los dispositivos conectándose y publicando (Ctrl+C para salir)
```

### 5. Verificar
- Panel de control (retroceso): `https://TU_DOMINIO/`. Pega el CONTROL_TOKEN arriba a la derecha.
- Grafana: `https://TU_DOMINIO/grafana/` (usuario `admin`, clave `GRAFANA_ADMIN_PASS`) → Dashboards → *IoT Campus UNAB*.
- El certificado HTTPS puede tardar 1 minuto en emitirse la primera vez.

Si el bus no muestra datos, mira `docker compose logs devices | grep bus`: el script imprime la respuesta
de la API para que ajustes los nombres de los campos en `devices/api_devices.py`.

### 6. Conectar el dispositivo REAL (tu PC)
En tu computador (con Python instalado):
```bash
cd real_device
pip install paho-mqtt psutil
python real_device.py --host TU_DOMINIO --user iot --password TU_MQTT_PASS
```
Déjalo corriendo. Mide CPU, RAM, batería y tráfico de red reales.

### 7. Toma real de datos: 30 minutos
Deja todo corriendo **30 minutos**. Mientras tanto, prueba el retroceso y toma capturas:
- Apagar y encender un dispositivo, cambiar el intervalo.
- `salon` → Ajustar `ac` = 0 (apaga el aire: la temperatura sube) o `setpoint` = 20.
- `tanque` → Ajustar `bomba` = 1, `umbral` = 50.
- `clima` → Calibrar `temp` con offset `-0.5`.
- `parqueadero` → Ajustar `capacidad` = 150.
- `pronostico` → Ajustar `horas_adelante` = 6.

También se puede enviar un comando por MQTT directo:
```bash
docker compose exec mosquitto mosquitto_pub -u iot -P TU_MQTT_PASS -t unab/salon/cmd -m '{"action":"set","key":"ac","value":0}'
docker compose exec mosquitto mosquitto_sub -u iot -P TU_MQTT_PASS -t 'unab/#' -v     # ver todo el tráfico
```

### 8. Generar el histórico de los otros días (con IA)
Cuando tengas los 30 minutos reales:
```bash
docker compose exec devices python /tools/generar_historico.py --dias 5
```
- Toma la media y la desviación de tus 30 min reales y genera 5 días **anteriores**, con puntos cada 5 min.
- Usa patrones de día y noche, horas pico, la física de los gemelos y filas reales de los datasets.
- Inserta eventos para analizar: una tarde de lluvia, un pico de contaminación, una falla de la bomba en la noche y el aire del salón apagado una tarde. El script imprime las fechas.
- Para regenerarlo: agrega `--limpiar`.

En el documento declara que el histórico se generó con un modelo asistido por IA y calibrado con la toma real de 30 min.

### 9. Alertas y reglas en Grafana
En Grafana ve a **Alerting → Alert rules → New alert rule**. Crea por lo menos estas tres:

| Regla | Query (Flux) | Condición |
|---|---|---|
| CO2 alto en salón | `from(bucket:"iot") \|> range(start:-5m) \|> filter(fn:(r)=>r.device=="salon" and r._field=="co2")` | Reduce *Last* · Threshold **> 1200** |
| Calidad del aire mala | igual, con `device=="aire"` y `_field=="aqi"` | **> 100** |
| Tanque bajo | igual, con `device=="tanque"` y `_field=="nivel"` | **< 20** |

Para cada una: Folder *IoT Campus UNAB*, grupo de evaluación `iot-1m` (cada 1 m), pending 1m → **Save**.
Para dispararlas en vivo usa el panel: en `salon` pon `ventilacion` = 0.02, y en `tanque` pon `bomba` = 0 y `umbral` = 0.

El dashboard ya trae en cada gráfica **promedio, máximo, mínimo y último valor**, y KPIs con colores por umbral.
El selector de tiempo de arriba a la derecha sirve para mostrar última hora, 24 h o 6 días (el ajuste de tiempo que pide el enunciado).

### 10. Exportar datos y análisis con IA
```bash
docker compose exec devices python /tools/exportar_csv.py
```
Copia los archivos a tu PC (desde tu PC):
```bash
scp -r azureuser@TU_IP:~/iot-campus-unab/tools/export ./export
```
Sube los CSV y `resumen.csv` a una IA junto con el texto de `prompt_ia.md`. Pega el análisis en el documento.

### 11. Entrega
- PDF con las secciones del enunciado, las capturas de Grafana y del panel de retroceso, y el análisis de la IA.
- Link del repo de GitHub y URL `https://TU_DOMINIO` (y `/grafana/`).

---

## Dispositivos

| # | ID | Tipo | Variables (rango aprox.) | Protocolo | Retroceso |
|---|---|---|---|---|---|
| 1 | laptop | Real | CPU 0–100 %, RAM 0–100 %, batería 0–100 %, red 0–50000 kbps | MQTT | on/off, intervalo, calibrar |
| 2 | clima | API Azure Maps | temp 14–36 °C, humedad 30–100 %, viento 0–50 km/h, UV 0–13, presión 1000–1025 hPa, nubosidad 0–100 % | HTTPS REST → MQTT | on/off, intervalo, calibrar |
| 3 | aire | API Azure Maps | AQI 0–300, PM2.5, PM10, O3, NO2, CO (µg/m³) | HTTPS REST → MQTT | on/off, intervalo, calibrar |
| 4 | pronostico | API Azure Maps | temp. pronosticada, prob. lluvia 0–100 %, humedad | HTTPS REST → MQTT | `horas_adelante` 1–12 |
| 5 | bus | API GPS Ruta UNAB | lat, lon, velocidad 0–80 km/h, en movimiento 0/1 | HTTP REST (Basic Auth) → MQTT | on/off, intervalo |
| 6 | salon | Digital Twin | CO2 400–3000 ppm, ocupación 0–40, temp, aire acondicionado 0/1 | MQTT | `ac`, `setpoint`, `ventilacion`, `capacidad` |
| 7 | parqueadero | Digital Twin | ocupados 0–200, ocupación 0–100 % | MQTT | `capacidad` (calibración) |
| 8 | tanque | Digital Twin | nivel 0–100 %, caudal 0–10 L/min, bomba 0/1 | MQTT | `bomba`, `modo_auto`, `umbral` |
| 9 | estacion_aire_hist | DataSet UCI Air Quality | CO, NO2, benceno, temp, humedad | MQTT | pausa (off), `fila`, intervalo |
| 10 | edificio_energia | DataSet UCI Appliances Energy | consumo Wh, luces Wh, temp. int/ext, humedad | MQTT | pausa (off), `fila`, intervalo |

## Estructura
```
docker-compose.yml   servicios: mosquitto, influxdb, telegraf, grafana, devices, back, caddy
mosquitto/           configuración del broker (usuario/clave)
telegraf/            MQTT → InfluxDB
grafana/             datasource y dashboard aprovisionados
devices/             9 dispositivos (API, Digital Twin, DataSet) en Python
real_device/         dispositivo real (tu PC)
back/                API FastAPI + panel web de control (retroceso)
caddy/               proxy HTTPS con certificado automático
tools/               generador de histórico, exportador CSV, generador del dashboard
```

#!/usr/bin/env bash
# Prepara el proyecto: genera tokens que falten y crea el usuario del broker MQTT.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "No existe .env. Ejecuta: cp .env.example .env  y llénalo." ; exit 1
fi

gen() { openssl rand -hex 24; }
for VAR in INFLUX_TOKEN CONTROL_TOKEN; do
  if grep -qE "^${VAR}=$" .env; then
    sed -i "s|^${VAR}=$|${VAR}=$(gen)|" .env
    echo "Generado ${VAR}"
  fi
done

set -a; source .env; set +a

docker run --rm -v "$(pwd)/mosquitto:/mosquitto/config" eclipse-mosquitto:2 \
  sh -c "mosquitto_passwd -b -c /mosquitto/config/passwd '$MQTT_USER' '$MQTT_PASS' && chown mosquitto:mosquitto /mosquitto/config/passwd && chmod 0700 /mosquitto/config/passwd"
echo "Usuario MQTT '$MQTT_USER' creado."
echo "Listo. Ahora: docker compose up -d --build"
echo "Tu CONTROL_TOKEN (para el panel de retroceso) es: $CONTROL_TOKEN"

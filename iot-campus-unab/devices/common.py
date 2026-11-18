"""Clase base para todos los dispositivos: publica datos por MQTT y recibe
comandos de retroceso (on/off, intervalo, calibración, set de actuadores)."""
import json
import logging
import os
import threading
import time

import paho.mqtt.client as mqtt

BROKER = os.getenv("MQTT_HOST", "mosquitto")
PORT = int(os.getenv("MQTT_PORT", "1883"))
USER = os.getenv("MQTT_USER", "")
PASS = os.getenv("MQTT_PASS", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")


class Device(threading.Thread):
    type = "generic"

    def __init__(self, device_id, interval=10):
        super().__init__(daemon=True)
        self.id = device_id
        self.default_interval = interval
        self.interval = interval
        self.enabled = True
        self.offsets = {}          # calibración por variable
        self.params = {}           # parámetros ajustables (actuadores, setpoints)
        self.log = logging.getLogger(device_id)
        self.base = f"unab/{device_id}"
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"dev-{device_id}")
        if USER:
            self.client.username_pw_set(USER, PASS)
        self.client.will_set(f"{self.base}/status", json.dumps({"device": device_id, "online": False}), qos=1, retain=True)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    # ---------- MQTT ----------
    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        client.subscribe(f"{self.base}/cmd", qos=1)
        self.log.info("conectado al broker, escuchando %s/cmd", self.base)
        self.publish_status()

    def _on_message(self, client, userdata, msg):
        try:
            cmd = json.loads(msg.payload.decode())
        except Exception:
            self.log.warning("comando inválido: %s", msg.payload)
            return
        action = cmd.get("action")
        self.log.info("comando recibido: %s", cmd)
        if action == "on":
            self.enabled = True
        elif action == "off":
            self.enabled = False
        elif action == "set_interval":
            self.interval = max(2, int(cmd.get("value", self.interval)))
        elif action == "calibrate":
            self.offsets[cmd["field"]] = float(cmd.get("offset", 0))
        elif action == "reset":
            self.offsets = {}
            self.interval = self.default_interval
            self.enabled = True
        elif action == "set":
            self.params[cmd["key"]] = cmd.get("value")
            self.on_param(cmd["key"], cmd.get("value"))
        else:
            self.log.warning("acción desconocida: %s", action)
        self.publish_status()

    def publish_status(self):
        status = {"device": self.id, "type": self.type, "online": True, "enabled": self.enabled,
                  "interval": self.interval, "offsets": self.offsets, "params": self.params}
        self.client.publish(f"{self.base}/status", json.dumps(status), qos=1, retain=True)

    # ---------- para sobrescribir ----------
    def on_param(self, key, value):
        pass

    def read(self) -> dict:
        raise NotImplementedError

    # ---------- ciclo principal ----------
    def run(self):
        while True:
            try:
                self.client.connect(BROKER, PORT, 60)
                break
            except Exception as e:
                self.log.warning("broker no disponible (%s), reintento en 5 s", e)
                time.sleep(5)
        self.client.loop_start()
        while True:
            t0 = time.time()
            if self.enabled:
                try:
                    data = self.read()
                    if data:
                        for field, off in self.offsets.items():
                            if isinstance(data.get(field), (int, float)):
                                data[field] = round(data[field] + off, 3)
                        payload = {"device": self.id, "type": self.type, **data}
                        self.client.publish(f"{self.base}/data", json.dumps(payload), qos=1)
                except Exception as e:
                    self.log.error("error leyendo: %s", e)
            while time.time() - t0 < self.interval:
                time.sleep(0.5)

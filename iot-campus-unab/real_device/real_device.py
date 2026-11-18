"""DISPOSITIVO REAL: tu computador como nodo IoT. Mide CPU, RAM, batería y tráfico de red
con sus sensores reales y los publica por MQTT al broker en la nube.

Uso (en tu PC):
    pip install paho-mqtt psutil
    python real_device.py --host TU_IP_O_DOMINIO --user iot --password TU_CLAVE

Retroceso: escucha unab/laptop/cmd (on, off, set_interval, calibrate, reset).
"""
import argparse
import json
import time

import paho.mqtt.client as mqtt
import psutil

p = argparse.ArgumentParser()
p.add_argument("--host", required=True)
p.add_argument("--port", type=int, default=1883)
p.add_argument("--user", required=True)
p.add_argument("--password", required=True)
p.add_argument("--id", default="laptop")
args = p.parse_args()

BASE = f"unab/{args.id}"
state = {"enabled": True, "interval": 10, "offsets": {}}


def publish_status(c):
    c.publish(f"{BASE}/status", json.dumps({"device": args.id, "type": "real", "online": True, **state}), qos=1, retain=True)


def on_connect(c, u, f, rc, props=None):
    print("Conectado al broker. Escuchando", f"{BASE}/cmd")
    c.subscribe(f"{BASE}/cmd", qos=1)
    publish_status(c)


def on_message(c, u, msg):
    try:
        cmd = json.loads(msg.payload.decode())
    except Exception:
        return
    a = cmd.get("action")
    print("Comando recibido:", cmd)
    if a == "on":
        state["enabled"] = True
    elif a == "off":
        state["enabled"] = False
    elif a == "set_interval":
        state["interval"] = max(2, int(cmd.get("value", 10)))
    elif a == "calibrate":
        state["offsets"][cmd["field"]] = float(cmd.get("offset", 0))
    elif a == "reset":
        state.update({"enabled": True, "interval": 10, "offsets": {}})
    publish_status(c)


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"dev-{args.id}")
client.username_pw_set(args.user, args.password)
client.will_set(f"{BASE}/status", json.dumps({"device": args.id, "online": False}), qos=1, retain=True)
client.on_connect = on_connect
client.on_message = on_message
client.connect(args.host, args.port, 60)
client.loop_start()

net_prev = psutil.net_io_counters()
t_prev = time.time()
psutil.cpu_percent()
while True:
    time.sleep(state["interval"])
    if not state["enabled"]:
        continue
    now = time.time()
    net = psutil.net_io_counters()
    kbps = (net.bytes_sent + net.bytes_recv - net_prev.bytes_sent - net_prev.bytes_recv) * 8 / 1000 / (now - t_prev)
    net_prev, t_prev = net, now
    data = {"cpu": psutil.cpu_percent(), "ram": psutil.virtual_memory().percent, "red_kbps": round(kbps, 1)}
    bat = psutil.sensors_battery()
    if bat:
        data["bateria"] = bat.percent
        data["cargando"] = 1 if bat.power_plugged else 0
    for k, off in state["offsets"].items():
        if k in data:
            data[k] = round(data[k] + off, 2)
    client.publish(f"{BASE}/data", json.dumps({"device": args.id, "type": "real", **data}), qos=1)
    print("Publicado:", data)

"""Back-end: escucha estado y datos de todos los dispositivos y publica los comandos
de retroceso que se envían desde el panel web."""
import json
import os
import threading

import paho.mqtt.client as mqtt
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse

TOKEN = os.getenv("CONTROL_TOKEN", "")
STATE = {}   # device -> {"status": {...}, "last": {...}}
lock = threading.Lock()

app = FastAPI(title="IoT Campus UNAB")


def on_connect(c, u, f, rc, props=None):
    c.subscribe([("unab/+/status", 1), ("unab/+/data", 0)])


def on_message(c, u, msg):
    try:
        payload = json.loads(msg.payload.decode())
    except Exception:
        return
    _, device, kind = msg.topic.split("/")
    with lock:
        d = STATE.setdefault(device, {"status": {}, "last": {}})
        d["status" if kind == "status" else "last"] = payload


mq = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="back-control")
mq.username_pw_set(os.getenv("MQTT_USER", ""), os.getenv("MQTT_PASS", ""))
mq.on_connect = on_connect
mq.on_message = on_message
mq.connect_async(os.getenv("MQTT_HOST", "mosquitto"), 1883, 60)
mq.loop_start()


@app.get("/")
def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


@app.get("/api/devices")
def devices():
    with lock:
        return dict(sorted(STATE.items()))


@app.post("/api/cmd/{device}")
def command(device: str, cmd: dict, x_token: str = Header(default="")):
    if TOKEN and x_token != TOKEN:
        raise HTTPException(401, "token inválido")
    if "action" not in cmd:
        raise HTTPException(400, "falta 'action'")
    mq.publish(f"unab/{device}/cmd", json.dumps(cmd), qos=1)
    return {"ok": True, "topic": f"unab/{device}/cmd", "cmd": cmd}

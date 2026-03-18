#!/usr/bin/env python3
"""
Bus Digital Controller - Backend GPIO Server
Raspberry Pi 3 B+ - Pines accesibles con pantalla ARD-510 montada
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import time

app = Flask(__name__)
CORS(app)

try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    SIMULATION = False
    print("✅ RPi.GPIO cargado correctamente")
except ImportError:
    SIMULATION = True
    print("⚠️  Modo simulación")

# ─── Pines accesibles con pantalla ARD-510 montada ───────────────────────────
LED_CONFIG = {
    "LED_1": {"pin": 5,  "name": "BIT 7", "color": "#ff4444"},
    "LED_2": {"pin": 6,  "name": "BIT 6", "color": "#ff8844"},
    "LED_3": {"pin": 13, "name": "BIT 5", "color": "#ffff44"},
    "LED_4": {"pin": 19, "name": "BIT 4", "color": "#44ff44"},
    "LED_5": {"pin": 26, "name": "BIT 3", "color": "#4488ff"},
    "LED_6": {"pin": 12, "name": "BIT 2", "color": "#aa44ff"},
    "LED_7": {"pin": 16, "name": "BIT 1", "color": "#ff44aa"},
    "LED_8": {"pin": 20, "name": "BIT 0", "color": "#44ffff"},
}

PWM_PINS = {5, 6, 13, 19, 12}

state = {led: {"on": False, "brightness": 100, "blink": False, "blink_pattern": "slow"}
         for led in LED_CONFIG}
pwm_objects = {}
blink_threads = {}

def init_gpio():
    if SIMULATION:
        return
    for led_id, cfg in LED_CONFIG.items():
        pin = cfg["pin"]
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)
        if pin in PWM_PINS:
            pwm = GPIO.PWM(pin, 1000)
            pwm.start(0)
            pwm_objects[led_id] = pwm

def set_led_output(led_id, on, brightness=100):
    cfg = LED_CONFIG[led_id]
    pin = cfg["pin"]
    if SIMULATION:
        print(f"[SIM] {led_id} (GPIO{pin}): {'ON' if on else 'OFF'} @ {brightness}%")
        return
    if led_id in pwm_objects:
        duty = (brightness / 100.0) * 100 if on else 0
        pwm_objects[led_id].ChangeDutyCycle(duty)
    else:
        GPIO.output(pin, GPIO.HIGH if on else GPIO.LOW)

BLINK_PATTERNS = {
    "slow":  (1.0, 1.0),
    "fast":  (0.15, 0.15),
    "pulse": (0.05, 0.95),
    "sos":   (0.1, 0.1),
}

def blink_worker(led_id):
    while state[led_id]["blink"] and state[led_id]["on"]:
        pattern = state[led_id]["blink_pattern"]
        on_t, off_t = BLINK_PATTERNS.get(pattern, (0.5, 0.5))
        set_led_output(led_id, True, state[led_id]["brightness"])
        time.sleep(on_t)
        if not state[led_id]["blink"]:
            break
        set_led_output(led_id, False)
        time.sleep(off_t)
    if state[led_id]["on"] and not state[led_id]["blink"]:
        set_led_output(led_id, True, state[led_id]["brightness"])

def start_blink(led_id):
    if led_id in blink_threads and blink_threads[led_id].is_alive():
        return
    t = threading.Thread(target=blink_worker, args=(led_id,), daemon=True)
    blink_threads[led_id] = t
    t.start()

@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify({
        "simulation": SIMULATION,
        "leds": {
            led_id: {
                **state[led_id],
                "name": LED_CONFIG[led_id]["name"],
                "color": LED_CONFIG[led_id]["color"],
                "pin": LED_CONFIG[led_id]["pin"],
                "pwm": led_id in pwm_objects or SIMULATION,
            }
            for led_id in LED_CONFIG
        }
    })

@app.route("/api/led/<led_id>", methods=["POST"])
def control_led(led_id):
    if led_id not in LED_CONFIG:
        return jsonify({"error": "LED no encontrado"}), 404
    data = request.get_json()
    if "on" in data:
        state[led_id]["on"] = bool(data["on"])
    if "brightness" in data:
        state[led_id]["brightness"] = max(0, min(100, int(data["brightness"])))
    if "blink" in data:
        state[led_id]["blink"] = bool(data["blink"])
    if "blink_pattern" in data:
        state[led_id]["blink_pattern"] = data["blink_pattern"]
    if state[led_id]["blink"] and state[led_id]["on"]:
        start_blink(led_id)
    else:
        state[led_id]["blink"] = False
        set_led_output(led_id, state[led_id]["on"], state[led_id]["brightness"])
    return jsonify({"ok": True, "state": state[led_id]})

@app.route("/api/all", methods=["POST"])
def control_all():
    data = request.get_json()
    for led_id in LED_CONFIG:
        if "on" in data:
            state[led_id]["on"] = bool(data["on"])
            state[led_id]["blink"] = False
            set_led_output(led_id, state[led_id]["on"], state[led_id]["brightness"])
    return jsonify({"ok": True})

@app.route("/api/bus/write", methods=["POST"])
def bus_write():
    data = request.get_json()
    value = int(data.get("byte", 0)) & 0xFF
    msb_first = data.get("msb_first", True)
    led_ids = list(LED_CONFIG.keys())[:8]
    bits = [(value >> i) & 1 for i in range(7, -1, -1)] if msb_first else \
           [(value >> i) & 1 for i in range(8)]
    for i, led_id in enumerate(led_ids):
        state[led_id]["on"] = bool(bits[i])
        state[led_id]["blink"] = False
        set_led_output(led_id, state[led_id]["on"])
    return jsonify({"ok": True, "byte": value, "binary": f"{value:08b}", "hex": f"0x{value:02X}"})

import atexit
@atexit.register
def cleanup():
    if not SIMULATION:
        for pwm in pwm_objects.values():
            pwm.stop()
        GPIO.cleanup()
    print("GPIO limpiado.")

if __name__ == "__main__":
    init_gpio()
    print("🚀 Servidor en http://0.0.0.0:5000")
    print(f"   Modo: {'SIMULACIÓN' if SIMULATION else 'HARDWARE REAL'}")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)

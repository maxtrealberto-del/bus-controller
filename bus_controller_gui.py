#!/usr/bin/env python3
"""
Bus Digital Controller - Interfaz Tkinter compacta
Raspberry Pi 3 B+ con pantalla táctil ARD-510 (800x480 resistiva)
Todo visible sin scroll
"""

import tkinter as tk
from tkinter import font
import threading
import time

# ─── GPIO Setup ──────────────────────────────────────────────────────────────
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    SIMULATION = False
    print("✅ RPi.GPIO cargado")
except ImportError:
    SIMULATION = True
    print("⚠️  Modo simulación")

# ─── Configuración de pines ───────────────────────────────────────────────────
LED_CONFIG = [
    {"pin": 5,  "nombre": "BIT 7", "color": "#ff4444", "color_dim": "#3a1111"},
    {"pin": 6,  "nombre": "BIT 6", "color": "#ff8844", "color_dim": "#3a2211"},
    {"pin": 13, "nombre": "BIT 5", "color": "#ffff44", "color_dim": "#3a3a11"},
    {"pin": 19, "nombre": "BIT 4", "color": "#44ff44", "color_dim": "#113a11"},
    {"pin": 26, "nombre": "BIT 3", "color": "#4488ff", "color_dim": "#112244"},
    {"pin": 12, "nombre": "BIT 2", "color": "#aa44ff", "color_dim": "#220d3a"},
    {"pin": 16, "nombre": "BIT 1", "color": "#ff44aa", "color_dim": "#3a1128"},
    {"pin": 20, "nombre": "BIT 0", "color": "#44ffff", "color_dim": "#113a3a"},
]

PWM_PINS = {5, 6, 13, 19, 12}

led_state = [{"on": False, "brightness": 100, "blink": False, "pattern": "SLOW"}
             for _ in LED_CONFIG]
pwm_objects = {}
blink_threads = {}

def init_gpio():
    if SIMULATION:
        return
    for i, cfg in enumerate(LED_CONFIG):
        pin = cfg["pin"]
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)
        if pin in PWM_PINS:
            pwm = GPIO.PWM(pin, 1000)
            pwm.start(0)
            pwm_objects[i] = pwm

def set_led(i, on, brightness=100):
    pin = LED_CONFIG[i]["pin"]
    if SIMULATION:
        print(f"[SIM] LED{i} GPIO{pin}: {'ON' if on else 'OFF'} {brightness}%")
        return
    if i in pwm_objects:
        pwm_objects[i].ChangeDutyCycle((brightness / 100.0) * 100 if on else 0)
    else:
        GPIO.output(pin, GPIO.HIGH if on else GPIO.LOW)

PATTERNS = {"SLOW": (1.0,1.0), "FAST": (0.15,0.15), "PULSE": (0.05,0.95), "SOS": (0.1,0.1)}

def blink_worker(i):
    while led_state[i]["blink"] and led_state[i]["on"]:
        on_t, off_t = PATTERNS.get(led_state[i]["pattern"], (0.5, 0.5))
        set_led(i, True, led_state[i]["brightness"])
        time.sleep(on_t)
        if not led_state[i]["blink"]:
            break
        set_led(i, False)
        time.sleep(off_t)
    if led_state[i]["on"] and not led_state[i]["blink"]:
        set_led(i, True, led_state[i]["brightness"])

def start_blink(i):
    if i in blink_threads and blink_threads[i].is_alive():
        return
    t = threading.Thread(target=blink_worker, args=(i,), daemon=True)
    blink_threads[i] = t
    t.start()

# ─── GUI ──────────────────────────────────────────────────────────────────────
class BusControlApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Bus Digital Controller")
        self.root.configure(bg="#0a0c10")
        self.root.geometry("800x480")
        self.root.resizable(False, False)
        self.root.overrideredirect(True)  # quita la barra de titulo del sistema

        self.fn_title = tk.font.Font(family="Courier", size=10, weight="bold")
        self.fn_btn   = tk.font.Font(family="Courier", size=9,  weight="bold")
        self.fn_small = tk.font.Font(family="Courier", size=7)
        self.fn_hex   = tk.font.Font(family="Courier", size=20, weight="bold")

        self.hex_value  = tk.StringVar(value="0x00")
        self.bus_binary = tk.StringVar(value="00000000")
        self.bus_dec    = tk.StringVar(value="DEC: 0")
        self.led_frames = []

        self._build_ui()
        self._update_bus_display()

    def _build_ui(self):
        # ── Header ──
        header = tk.Frame(self.root, bg="#0f1218", pady=3)
        header.pack(fill="x")
        tk.Label(header, text="⬡ BUS DIGITAL CONTROLLER",
                 font=self.fn_title, fg="#00e5ff", bg="#0f1218").pack(side="left", padx=10)
        modo = "SIMULACIÓN" if SIMULATION else "HARDWARE REAL"
        color_modo = "#ffaa00" if SIMULATION else "#00ff88"
        tk.Label(header, text=f"● {modo}",
                 font=self.fn_small, fg=color_modo, bg="#0f1218").pack(side="right", padx=6)
        tk.Button(header, text="✕ SALIR", font=self.fn_small,
                  bg="#ff3d71", fg="white", relief="flat", padx=6,
                  command=self._salir).pack(side="right", padx=4)

        # ── Body ──
        body = tk.Frame(self.root, bg="#0a0c10")
        body.pack(fill="both", expand=True, padx=4, pady=3)

        # ── Izquierda: grid de 8 LEDs en 2 columnas x 4 filas ──
        left = tk.Frame(body, bg="#0a0c10")
        left.pack(side="left", fill="both", expand=True)

        for i, cfg in enumerate(LED_CONFIG):
            row = i % 4
            col = i // 4
            card = self._make_led_card(left, i, cfg)
            card.grid(row=row, column=col, padx=3, pady=2, sticky="nsew")
            left.columnconfigure(col, weight=1)
            left.rowconfigure(row, weight=1)

        # ── Derecha: Bus writer ──
        right = tk.Frame(body, bg="#0a0c10", width=215)
        right.pack(side="right", fill="y", padx=(6,2))
        right.pack_propagate(False)
        self._build_bus_panel(right)

    def _make_led_card(self, parent, i, cfg):
        frame = tk.Frame(parent, bg="#0f1218",
                         highlightbackground="#1e2530", highlightthickness=1)

        # Fila superior: indicador + nombre + pin
        top = tk.Frame(frame, bg="#0f1218")
        top.pack(fill="x", padx=5, pady=(4,1))

        indicator = tk.Label(top, text="●", font=tk.font.Font(size=11),
                             fg=cfg["color_dim"], bg="#0f1218")
        indicator.pack(side="left")
        tk.Label(top, text=cfg["nombre"],
                 font=self.fn_btn, fg="#c8d6e5", bg="#0f1218").pack(side="left", padx=3)
        tk.Label(top, text=f"GPIO{cfg['pin']}",
                 font=self.fn_small, fg="#4a5568", bg="#0f1218").pack(side="right")

        # Botón ON/OFF
        btn = tk.Button(frame, text="OFF ○", font=self.fn_btn,
                        bg="#1a1e26", fg="#4a5568", relief="flat", pady=5,
                        command=lambda idx=i: self._toggle_led(idx))
        btn.pack(fill="x", padx=5, pady=2)

        # Botones parpadeo en una sola fila
        brow = tk.Frame(frame, bg="#0f1218")
        brow.pack(fill="x", padx=5, pady=(0,4))
        for p in ["SLW","FST","PLS","SOS"]:
            tk.Button(brow, text=p, font=self.fn_small,
                     bg="#1a1e26", fg="#4a5568", relief="flat",
                     command=lambda idx=i, pat=p: self._set_blink(idx,
                         {"SLW":"SLOW","FST":"FAST","PLS":"PULSE","SOS":"SOS"}[pat])
                     ).pack(side="left", expand=True, fill="x", padx=1)
        tk.Button(brow, text="✕", font=self.fn_small,
                 bg="#1a1e26", fg="#ff3d71", relief="flat",
                 command=lambda idx=i: self._stop_blink(idx)
                 ).pack(side="left", expand=True, fill="x", padx=1)

        self.led_frames.append({
            "indicator": indicator, "btn": btn,
            "color": cfg["color"], "color_dim": cfg["color_dim"],
        })
        return frame

    def _build_bus_panel(self, parent):
        # Display valor del bus
        tk.Label(parent, text="BUS WRITER",
                 font=self.fn_small, fg="#4a5568", bg="#0a0c10").pack(anchor="w")

        disp = tk.Frame(parent, bg="#0f1218",
                        highlightbackground="#1e2530", highlightthickness=1)
        disp.pack(fill="x", pady=(2,4))
        tk.Label(disp, textvariable=self.hex_value,
                 font=self.fn_hex, fg="#00e5ff", bg="#0f1218").pack(pady=3)
        tk.Label(disp, textvariable=self.bus_binary,
                 font=self.fn_small, fg="#4a5568", bg="#0f1218").pack()
        tk.Label(disp, textvariable=self.bus_dec,
                 font=self.fn_small, fg="#4a5568", bg="#0f1218").pack(pady=(0,3))

        # Teclado hex 4x4
        pad = tk.Frame(parent, bg="#0a0c10")
        pad.pack(fill="x")
        for row_keys in [['0','1','2','3'],['4','5','6','7'],
                          ['8','9','A','B'],['C','D','E','F']]:
            row = tk.Frame(pad, bg="#0a0c10")
            row.pack(fill="x", pady=1)
            for k in row_keys:
                tk.Button(row, text=k, font=self.fn_btn,
                         bg="#1a1e26", fg="#c8d6e5", relief="flat", pady=6,
                         command=lambda c=k: self._hex_append(c)
                         ).pack(side="left", expand=True, fill="x", padx=1)

        # CLR y backspace
        crow = tk.Frame(pad, bg="#0a0c10")
        crow.pack(fill="x", pady=1)
        tk.Button(crow, text="CLR", font=self.fn_btn,
                 bg="#1a1e26", fg="#ff3d71", relief="flat", pady=6,
                 command=self._hex_clear).pack(side="left", expand=True, fill="x", padx=1)
        tk.Button(crow, text="⌫", font=self.fn_btn,
                 bg="#1a1e26", fg="#ff3d71", relief="flat", pady=6,
                 command=self._hex_backspace).pack(side="left", expand=True, fill="x", padx=1)

        # Enviar
        tk.Button(pad, text="⚡ ENVIAR", font=self.fn_btn,
                 bg="#00ff88", fg="#0a0c10", relief="flat", pady=8,
                 command=self._send_bus).pack(fill="x", pady=3)

        # Presets
        tk.Label(parent, text="PRESETS",
                 font=self.fn_small, fg="#4a5568", bg="#0a0c10").pack(anchor="w")
        for vals in [["0x00","0xFF","0xAA"],["0x55","0x0F","0xF0"]]:
            row = tk.Frame(parent, bg="#0a0c10")
            row.pack(fill="x", pady=1)
            for v in vals:
                tk.Button(row, text=v, font=self.fn_small,
                         bg="#1a1e26", fg="#4a5568", relief="flat", pady=4,
                         command=lambda val=v: self._set_hex(val)
                         ).pack(side="left", expand=True, fill="x", padx=1)

        # Global
        tk.Label(parent, text="GLOBAL",
                 font=self.fn_small, fg="#4a5568", bg="#0a0c10").pack(anchor="w", pady=(4,1))
        tk.Button(parent, text="▶ TODOS ON", font=self.fn_btn,
                 bg="#00e5ff", fg="#0a0c10", relief="flat", pady=6,
                 command=lambda: self._all_leds(True)).pack(fill="x", pady=1)
        tk.Button(parent, text="■ TODOS OFF", font=self.fn_btn,
                 bg="#ff3d71", fg="white", relief="flat", pady=6,
                 command=lambda: self._all_leds(False)).pack(fill="x", pady=1)

    # ── Acciones ──────────────────────────────────────────────────────────────
    def _toggle_led(self, i):
        led_state[i]["on"] = not led_state[i]["on"]
        led_state[i]["blink"] = False
        set_led(i, led_state[i]["on"], led_state[i]["brightness"])
        self._update_card(i)
        self._update_bus_display()

    def _set_brightness(self, i, var):
        led_state[i]["brightness"] = var.get()
        if led_state[i]["on"]:
            set_led(i, True, led_state[i]["brightness"])

    def _set_blink(self, i, pattern):
        led_state[i]["on"] = True
        led_state[i]["blink"] = True
        led_state[i]["pattern"] = pattern
        start_blink(i)
        self._update_card(i)

    def _stop_blink(self, i):
        led_state[i]["blink"] = False
        self._update_card(i)

    def _all_leds(self, on):
        for i in range(len(LED_CONFIG)):
            led_state[i]["on"] = on
            led_state[i]["blink"] = False
            set_led(i, on, led_state[i]["brightness"])
            self._update_card(i)
        self._update_bus_display()

    def _update_card(self, i):
        card = self.led_frames[i]
        on = led_state[i]["on"]
        card["indicator"].config(fg=card["color"] if on else card["color_dim"])
        card["btn"].config(
            text="ON ●" if on else "OFF ○",
            bg=card["color"] if on else "#1a1e26",
            fg="#0a0c10" if on else "#4a5568"
        )
        self._update_bus_display()

    def _update_bus_display(self):
        byte = 0
        for i in range(8):
            if led_state[i]["on"]:
                byte |= (1 << (7 - i))
        self.hex_value.set(f"0x{byte:02X}")
        self.bus_binary.set(f"{byte:08b}")
        self.bus_dec.set(f"DEC: {byte}")

    def _hex_append(self, c):
        current = self.hex_value.get().replace("0x","").replace("0X","")
        current = current[-1:] + c if len(current) >= 2 else current + c
        self.hex_value.set(f"0x{current.upper()[-2:]}")

    def _hex_clear(self):
        self.hex_value.set("0x00")

    def _hex_backspace(self):
        current = self.hex_value.get().replace("0x","")
        self.hex_value.set(f"0x{(current[:-1] or '0').upper()}")

    def _set_hex(self, val):
        self.hex_value.set(val)

    def _send_bus(self):
        try:
            value = int(self.hex_value.get(), 16) & 0xFF
        except:
            return
        for i in range(8):
            led_state[i]["on"] = bool((value >> (7 - i)) & 1)
            led_state[i]["blink"] = False
            set_led(i, led_state[i]["on"])
            self._update_card(i)
        self._update_bus_display()

    def _salir(self):
        if not SIMULATION:
            for pwm in pwm_objects.values():
                pwm.stop()
            GPIO.cleanup()
        self.root.destroy()

if __name__ == "__main__":
    init_gpio()
    root = tk.Tk()
    app = BusControlApp(root)
    root.mainloop()

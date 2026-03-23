#!/usr/bin/env python3
"""
Bus Digital Controller - Control por Teclado
Raspberry Pi 3 B+ 
Teclas 1-8: toggle individual de cada LED
Teclas hex + Enter: escribe byte al bus
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
    {"pin": 5,  "nombre": "BIT 7", "tecla": "1", "color": "#ff4444", "color_dim": "#3a1111"},
    {"pin": 6,  "nombre": "BIT 6", "tecla": "2", "color": "#ff8844", "color_dim": "#3a2211"},
    {"pin": 13, "nombre": "BIT 5", "tecla": "3", "color": "#ffff44", "color_dim": "#3a3a11"},
    {"pin": 19, "nombre": "BIT 4", "tecla": "4", "color": "#44ff44", "color_dim": "#113a11"},
    {"pin": 26, "nombre": "BIT 3", "tecla": "5", "color": "#4488ff", "color_dim": "#112244"},
    {"pin": 12, "nombre": "BIT 2", "tecla": "6", "color": "#aa44ff", "color_dim": "#220d3a"},
    {"pin": 16, "nombre": "BIT 1", "tecla": "7", "color": "#ff44aa", "color_dim": "#3a1128"},
    {"pin": 20, "nombre": "BIT 0", "tecla": "8", "color": "#44ffff", "color_dim": "#113a3a"},
]

led_state = [False] * 8
pwm_objects = {}

def init_gpio():
    if SIMULATION:
        return
    for i, cfg in enumerate(LED_CONFIG):
        pin = cfg["pin"]
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

def set_led(i, on):
    pin = LED_CONFIG[i]["pin"]
    if SIMULATION:
        print(f"[SIM] {LED_CONFIG[i]['nombre']} GPIO{pin}: {'ON' if on else 'OFF'}")
        return
    GPIO.output(pin, GPIO.HIGH if on else GPIO.LOW)

# ─── GUI ──────────────────────────────────────────────────────────────────────
class KeyboardController:
    def __init__(self, root):
        self.root = root
        self.root.title("Bus Controller — Teclado")
        self.root.configure(bg="#0a0c10")
        self.root.geometry("800x480")
        self.root.resizable(False, False)
        self.root.overrideredirect(True)

        self.fn_title = tk.font.Font(family="Courier", size=11, weight="bold")
        self.fn_big   = tk.font.Font(family="Courier", size=26, weight="bold")
        self.fn_btn   = tk.font.Font(family="Courier", size=10, weight="bold")
        self.fn_small = tk.font.Font(family="Courier", size=8)
        self.fn_key   = tk.font.Font(family="Courier", size=14, weight="bold")

        self.hex_buffer = ""  # buffer para entrada hex
        self.hex_var    = tk.StringVar(value="_")
        self.bus_hex    = tk.StringVar(value="0x00")
        self.bus_bin    = tk.StringVar(value="00000000")
        self.bus_dec    = tk.StringVar(value="DEC: 0")
        self.status_var = tk.StringVar(value="Listo — presiona una tecla")

        self.led_indicators = []
        self.led_btns = []

        self._build_ui()
        self._bind_keys()
        self._update_display()

    def _build_ui(self):
        # ── Header ──
        header = tk.Frame(self.root, bg="#0f1218", pady=4)
        header.pack(fill="x")
        tk.Label(header, text="⌨  BUS CONTROLLER — TECLADO",
                 font=self.fn_title, fg="#00e5ff", bg="#0f1218").pack(side="left", padx=12)
        modo = "SIMULACIÓN" if SIMULATION else "HARDWARE REAL"
        color_modo = "#ffaa00" if SIMULATION else "#00ff88"
        tk.Label(header, text=f"● {modo}",
                 font=self.fn_small, fg=color_modo, bg="#0f1218").pack(side="right", padx=8)
        tk.Button(header, text="✕", font=self.fn_btn,
                  bg="#ff3d71", fg="white", relief="flat", padx=10,
                  command=self._salir).pack(side="right", padx=4)

        # ── Body ──
        body = tk.Frame(self.root, bg="#0a0c10")
        body.pack(fill="both", expand=True, padx=8, pady=4)

        # ── Izquierda: 8 LEDs ──
        left = tk.Frame(body, bg="#0a0c10")
        left.pack(side="left", fill="both", expand=True)

        tk.Label(left, text="TECLAS  1-8  →  TOGGLE INDIVIDUAL",
                 font=self.fn_small, fg="#4a5568", bg="#0a0c10").pack(anchor="w", pady=(0,4))

        grid = tk.Frame(left, bg="#0a0c10")
        grid.pack(fill="both", expand=True)

        for i, cfg in enumerate(LED_CONFIG):
            row = i % 4
            col = i // 4

            card = tk.Frame(grid, bg="#0f1218",
                           highlightbackground="#1e2530", highlightthickness=1)
            card.grid(row=row, column=col, padx=3, pady=2, sticky="nsew")
            grid.columnconfigure(col, weight=1)
            grid.rowconfigure(row, weight=1)

            # Fila interior
            inner = tk.Frame(card, bg="#0f1218")
            inner.pack(fill="both", expand=True, padx=6, pady=4)

            # Tecla asignada
            key_lbl = tk.Label(inner, text=f"[{cfg['tecla']}]",
                              font=self.fn_key, fg="#4a5568", bg="#0f1218", width=4)
            key_lbl.pack(side="left")

            # Indicador + nombre
            indicator = tk.Label(inner, text="●",
                                font=tk.font.Font(size=14),
                                fg=cfg["color_dim"], bg="#0f1218")
            indicator.pack(side="left", padx=4)

            tk.Label(inner, text=cfg["nombre"],
                    font=self.fn_btn, fg="#c8d6e5", bg="#0f1218").pack(side="left")

            # Estado ON/OFF
            btn = tk.Label(inner, text="OFF",
                          font=self.fn_btn, fg="#4a5568", bg="#1a1e26",
                          width=5, relief="flat", padx=4)
            btn.pack(side="right")

            self.led_indicators.append(indicator)
            self.led_btns.append(btn)

        # ── Derecha: entrada hex + display bus ──
        right = tk.Frame(body, bg="#0a0c10", width=220)
        right.pack(side="right", fill="y", padx=(8,0))
        right.pack_propagate(False)

        tk.Label(right, text="ENTRADA HEX + ENTER",
                 font=self.fn_small, fg="#4a5568", bg="#0a0c10").pack(anchor="w")

        # Buffer de entrada
        buf_frame = tk.Frame(right, bg="#0f1218",
                            highlightbackground="#1e2530", highlightthickness=1)
        buf_frame.pack(fill="x", pady=(2,6))
        tk.Label(buf_frame, text="ESCRIBE:",
                 font=self.fn_small, fg="#4a5568", bg="#0f1218").pack(pady=(4,0))
        tk.Label(buf_frame, textvariable=self.hex_var,
                 font=self.fn_big, fg="#ffff44", bg="#0f1218").pack(pady=4)
        tk.Label(buf_frame, text="luego presiona ENTER",
                 font=self.fn_small, fg="#4a5568", bg="#0f1218").pack(pady=(0,6))

        # Display del bus actual
        tk.Label(right, text="BUS ACTUAL",
                 font=self.fn_small, fg="#4a5568", bg="#0a0c10").pack(anchor="w", pady=(4,0))

        bus_frame = tk.Frame(right, bg="#0f1218",
                            highlightbackground="#1e2530", highlightthickness=1)
        bus_frame.pack(fill="x", pady=(2,6))
        tk.Label(bus_frame, textvariable=self.bus_hex,
                 font=self.fn_big, fg="#00e5ff", bg="#0f1218").pack(pady=(6,0))
        tk.Label(bus_frame, textvariable=self.bus_bin,
                 font=self.fn_small, fg="#4a5568", bg="#0f1218").pack()
        tk.Label(bus_frame, textvariable=self.bus_dec,
                 font=self.fn_small, fg="#4a5568", bg="#0f1218").pack(pady=(0,6))

        # Teclas especiales
        tk.Label(right, text="TECLAS ESPECIALES",
                 font=self.fn_small, fg="#4a5568", bg="#0a0c10").pack(anchor="w", pady=(4,2))

        especiales = [
            ("0", "Apagar todos", "#ff3d71"),
            ("9", "Encender todos", "#00e5ff"),
            ("ESC", "Limpiar buffer", "#ffaa00"),
            ("F1", "Alternar todos", "#aa44ff"),
        ]
        for tecla, desc, color in especiales:
            row = tk.Frame(right, bg="#0a0c10")
            row.pack(fill="x", pady=1)
            tk.Label(row, text=f"[{tecla}]", font=self.fn_btn,
                    fg=color, bg="#1a1e26", width=5, relief="flat").pack(side="left", padx=2)
            tk.Label(row, text=desc, font=self.fn_small,
                    fg="#c8d6e5", bg="#0a0c10").pack(side="left", padx=4)

        # Status bar
        status = tk.Frame(self.root, bg="#0f1218", pady=3)
        status.pack(fill="x", side="bottom")
        tk.Label(status, textvariable=self.status_var,
                 font=self.fn_small, fg="#00e5ff", bg="#0f1218").pack(side="left", padx=12)

    def _bind_keys(self):
        self.root.bind("<Key>", self._on_key)
        self.root.focus_set()

    def _on_key(self, event):
        key = event.keysym.upper()
        char = event.char.upper()

        # Teclas 1-8: toggle individual
        if char in "12345678":
            i = int(char) - 1
            led_state[i] = not led_state[i]
            set_led(i, led_state[i])
            self._update_display()
            nombre = LED_CONFIG[i]["nombre"]
            estado = "ON" if led_state[i] else "OFF"
            self.status_var.set(f"Tecla [{char}] → {nombre}: {estado}")
            return

        # Tecla 0: apagar todos
        if char == "0":
            for i in range(8):
                led_state[i] = False
                set_led(i, False)
            self._update_display()
            self.status_var.set("Tecla [0] → TODOS OFF")
            return

        # Tecla 9: encender todos
        if char == "9":
            for i in range(8):
                led_state[i] = True
                set_led(i, True)
            self._update_display()
            self.status_var.set("Tecla [9] → TODOS ON")
            return

        # F1: alternar todos
        if key == "F1":
            nuevo = not any(led_state)
            for i in range(8):
                led_state[i] = nuevo
                set_led(i, nuevo)
            self._update_display()
            self.status_var.set(f"F1 → TODOS {'ON' if nuevo else 'OFF'}")
            return

        # ESC: limpiar buffer hex
        if key == "ESCAPE":
            self.hex_buffer = ""
            self.hex_var.set("_")
            self.status_var.set("Buffer limpiado")
            return

        # Backspace: borrar último carácter del buffer
        if key == "BACKSPACE":
            self.hex_buffer = self.hex_buffer[:-1]
            self.hex_var.set(self.hex_buffer or "_")
            return

        # Enter: enviar buffer hex al bus
        if key == "RETURN":
            if self.hex_buffer:
                try:
                    value = int(self.hex_buffer, 16) & 0xFF
                    for i in range(8):
                        led_state[i] = bool((value >> (7 - i)) & 1)
                        set_led(i, led_state[i])
                    self._update_display()
                    self.status_var.set(f"Bus ← 0x{value:02X} | {value:08b}")
                except ValueError:
                    self.status_var.set(f"⚠ Valor inválido: {self.hex_buffer}")
                self.hex_buffer = ""
                self.hex_var.set("_")
            return

        # Letras A-F y números para buffer hex
        if char in "0123456789ABCDEF":
            if len(self.hex_buffer) < 2:
                self.hex_buffer += char
                self.hex_var.set(self.hex_buffer)
                self.status_var.set(f"Buffer: {self.hex_buffer} — presiona ENTER para enviar")

    def _update_display(self):
        byte = 0
        for i in range(8):
            if led_state[i]:
                byte |= (1 << (7 - i))
            # Actualizar indicadores
            cfg = LED_CONFIG[i]
            self.led_indicators[i].config(
                fg=cfg["color"] if led_state[i] else cfg["color_dim"])
            self.led_btns[i].config(
                text="ON " if led_state[i] else "OFF",
                fg="#0a0c10" if led_state[i] else "#4a5568",
                bg=cfg["color"] if led_state[i] else "#1a1e26")

        self.bus_hex.set(f"0x{byte:02X}")
        self.bus_bin.set(f"{byte:08b}")
        self.bus_dec.set(f"DEC: {byte}")

    def _salir(self):
        if not SIMULATION:
            GPIO.cleanup()
        self.root.destroy()

# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_gpio()
    root = tk.Tk()
    app = KeyboardController(root)
    root.mainloop()
EOF
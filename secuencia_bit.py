#!/usr/bin/env python3
"""
Bus Digital Controller - Control por Secuencia
Raspberry Pi 3 B+
3 botones con encendido/apagado en secuencia con retardo
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
    {"pin": 20, "nombre": "BIT 0", "color": "#44ffff",  "color_dim": "#113a3a"},
    {"pin": 16, "nombre": "BIT 1", "color": "#ff44aa",  "color_dim": "#3a1128"},
    {"pin": 12, "nombre": "BIT 2", "color": "#aa44ff",  "color_dim": "#220d3a"},
    {"pin": 26, "nombre": "BIT 3", "color": "#4488ff",  "color_dim": "#112244"},
    {"pin": 19, "nombre": "BIT 4", "color": "#44ff44",  "color_dim": "#113a11"},
    {"pin": 13, "nombre": "BIT 5", "color": "#ffff44",  "color_dim": "#3a3a11"},
    {"pin": 6,  "nombre": "BIT 6", "color": "#ff8844",  "color_dim": "#3a2211"},
    {"pin": 5,  "nombre": "BIT 7", "color": "#ff4444",  "color_dim": "#3a1111"},
    {"pin": 21, "nombre": "BIT 8", "color": "#ffffff",  "color_dim": "#2a2a2a"},
]

# ─── Grupos de botones ────────────────────────────────────────────────────────
GRUPOS = [
    {"nombre": "GRUPO 1", "bits": [0, 1, 2], "color": "#00e5ff",  "color_off": "#113a3a"},
    {"nombre": "GRUPO 2", "bits": [3, 4, 5], "color": "#00ff88",  "color_off": "#113a22"},
    {"nombre": "GRUPO 3", "bits": [6, 7, 8], "color": "#ff8800",  "color_off": "#3a2200"},
]

RETARDO = 2.0  # segundos entre cada bit

led_state = [False] * 9
grupo_state = [False] * 3   # True = encendido
grupo_running = [False] * 3 # True = secuencia en curso

def init_gpio():
    if SIMULATION:
        return
    for cfg in LED_CONFIG:
        GPIO.setup(cfg["pin"], GPIO.OUT)
        GPIO.output(cfg["pin"], GPIO.LOW)

def set_led(i, on):
    pin = LED_CONFIG[i]["pin"]
    led_state[i] = on
    if SIMULATION:
        print(f"[SIM] {LED_CONFIG[i]['nombre']} GPIO{pin}: {'ON' if on else 'OFF'}")
        return
    GPIO.output(pin, GPIO.HIGH if on else GPIO.LOW)

# ─── GUI ──────────────────────────────────────────────────────────────────────
class SequenceController:
    def __init__(self, root):
        self.root = root
        self.root.title("Bus Controller — Secuencia")
        self.root.configure(bg="#0a0c10")
        self.root.geometry("800x480")
        self.root.resizable(False, False)
        self.root.overrideredirect(True)

        self.fn_title  = tk.font.Font(family="Courier", size=11, weight="bold")
        self.fn_big    = tk.font.Font(family="Courier", size=22, weight="bold")
        self.fn_btn    = tk.font.Font(family="Courier", size=12, weight="bold")
        self.fn_small  = tk.font.Font(family="Courier", size=8)
        self.fn_status = tk.font.Font(family="Courier", size=9)
        self.fn_hex    = tk.font.Font(family="Courier", size=18, weight="bold")

        self.bus_hex   = tk.StringVar(value="0x000")
        self.bus_bin   = tk.StringVar(value="000000000")
        self.bus_dec   = tk.StringVar(value="DEC: 0")
        self.status_vars = [tk.StringVar(value="Apagado") for _ in range(3)]

        self.btn_widgets   = []
        self.led_indicators = []
        self.grupo_labels  = []

        self._build_ui()
        self._update_bus_display()

    def _build_ui(self):
        # ── Header ──
        header = tk.Frame(self.root, bg="#0f1218", pady=4)
        header.pack(fill="x")
        tk.Label(header, text="⬡ BUS CONTROLLER — SECUENCIA",
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
        body.pack(fill="both", expand=True, padx=8, pady=6)

        # ── Izquierda: 3 botones de grupo ──
        left = tk.Frame(body, bg="#0a0c10")
        left.pack(side="left", fill="both", expand=True)

        tk.Label(left, text="CONTROL DE GRUPOS",
                 font=self.fn_small, fg="#4a5568", bg="#0a0c10").pack(anchor="w", pady=(0,6))

        for g, grupo in enumerate(GRUPOS):
            card = tk.Frame(left, bg="#0f1218",
                           highlightbackground="#1e2530", highlightthickness=1)
            card.pack(fill="x", pady=4, ipady=6)

            # Fila superior: nombre + bits asignados
            top = tk.Frame(card, bg="#0f1218")
            top.pack(fill="x", padx=10, pady=(6,2))
            tk.Label(top, text=grupo["nombre"],
                    font=self.fn_btn, fg=grupo["color"], bg="#0f1218").pack(side="left")
            bits_texto = "  →  " + "  ·  ".join(
                LED_CONFIG[b]["nombre"] for b in grupo["bits"])
            tk.Label(top, text=bits_texto,
                    font=self.fn_small, fg="#4a5568", bg="#0f1218").pack(side="left", padx=8)

            # Indicadores de bits
            ind_row = tk.Frame(card, bg="#0f1218")
            ind_row.pack(fill="x", padx=10, pady=2)
            grupo_inds = []
            for b in grupo["bits"]:
                cfg = LED_CONFIG[b]
                ind = tk.Label(ind_row, text=f"● {cfg['nombre']}",
                              font=self.fn_small, fg=cfg["color_dim"], bg="#0f1218",
                              width=10)
                ind.pack(side="left", padx=4)
                grupo_inds.append(ind)
            self.led_indicators.append(grupo_inds)

            # Status de la secuencia
            status_lbl = tk.Label(card, textvariable=self.status_vars[g],
                                 font=self.fn_status, fg="#4a5568", bg="#0f1218")
            status_lbl.pack(anchor="w", padx=10, pady=(2,4))
            self.grupo_labels.append(status_lbl)

            # Botón ON/OFF grande y táctil
            btn = tk.Button(card,
                           text=f"▶  ENCENDER  {grupo['nombre']}",
                           font=self.fn_btn,
                           bg=grupo["color_off"], fg=grupo["color"],
                           activebackground=grupo["color"],
                           activeforeground="#0a0c10",
                           relief="flat", pady=12,
                           command=lambda idx=g: self._toggle_grupo(idx))
            btn.pack(fill="x", padx=10, pady=(2,8))
            self.btn_widgets.append(btn)

        # ── Derecha: display del bus ──
        right = tk.Frame(body, bg="#0a0c10", width=200)
        right.pack(side="right", fill="y", padx=(10,0))
        right.pack_propagate(False)

        tk.Label(right, text="ESTADO DEL BUS",
                 font=self.fn_small, fg="#4a5568", bg="#0a0c10").pack(anchor="w")

        bus_frame = tk.Frame(right, bg="#0f1218",
                            highlightbackground="#1e2530", highlightthickness=1)
        bus_frame.pack(fill="x", pady=(2,8))
        tk.Label(bus_frame, textvariable=self.bus_hex,
                 font=self.fn_hex, fg="#00e5ff", bg="#0f1218").pack(pady=(8,0))
        tk.Label(bus_frame, textvariable=self.bus_bin,
                 font=self.fn_small, fg="#4a5568", bg="#0f1218").pack(pady=2)
        tk.Label(bus_frame, textvariable=self.bus_dec,
                 font=self.fn_small, fg="#4a5568", bg="#0f1218").pack(pady=(0,8))

        # Display de todos los bits
        tk.Label(right, text="BITS INDIVIDUALES",
                 font=self.fn_small, fg="#4a5568", bg="#0a0c10").pack(anchor="w", pady=(8,4))

        bits_frame = tk.Frame(right, bg="#0f1218",
                             highlightbackground="#1e2530", highlightthickness=1)
        bits_frame.pack(fill="x")
        self.all_bit_labels = []
        for i in range(9):
            cfg = LED_CONFIG[i]
            row = tk.Frame(bits_frame, bg="#0f1218")
            row.pack(fill="x", padx=8, pady=1)
            tk.Label(row, text=cfg["nombre"],
                    font=self.fn_small, fg="#4a5568", bg="#0f1218", width=6).pack(side="left")
            lbl = tk.Label(row, text="○ OFF",
                          font=self.fn_small, fg="#4a5568", bg="#0f1218")
            lbl.pack(side="left", padx=4)
            self.all_bit_labels.append(lbl)

        # Retardo actual
        tk.Label(right, text=f"RETARDO: {RETARDO}s por bit",
                 font=self.fn_small, fg="#4a5568", bg="#0a0c10").pack(anchor="w", pady=(12,0))

        # Botón apagar todo
        tk.Button(right, text="■ APAGAR TODO",
                 font=self.fn_btn, bg="#ff3d71", fg="white",
                 relief="flat", pady=8,
                 command=self._apagar_todo).pack(fill="x", pady=(8,0))

    # ── Lógica de secuencia ───────────────────────────────────────────────────
    def _toggle_grupo(self, g):
        if grupo_running[g]:
            return  # ya hay una secuencia corriendo, ignorar

        if not grupo_state[g]:
            # Encender en secuencia normal
            t = threading.Thread(target=self._secuencia_encender, args=(g,), daemon=True)
        else:
            # Apagar en secuencia inversa
            t = threading.Thread(target=self._secuencia_apagar, args=(g,), daemon=True)
        t.start()

    def _secuencia_encender(self, g):
        grupo_running[g] = True
        grupo = GRUPOS[g]
        bits = grupo["bits"]

        self.root.after(0, lambda: self.status_vars[g].set("Encendiendo..."))
        self.root.after(0, lambda: self.btn_widgets[g].config(
            text=f"⏳  ENCENDIENDO...", state="disabled",
            bg="#2a2a2a", fg="#888888"))

        for idx, b in enumerate(bits):
            set_led(b, True)
            self.root.after(0, self._update_all)
            self.root.after(0, lambda g=g, idx=idx: self.status_vars[g].set(
                f"Encendido {LED_CONFIG[GRUPOS[g]['bits'][idx]]['nombre']}..."))
            time.sleep(RETARDO)

        grupo_state[g] = True
        grupo_running[g] = False
        self.root.after(0, lambda: self.status_vars[g].set("✅ Encendido completo"))
        self.root.after(0, lambda: self.btn_widgets[g].config(
            text=f"■  APAGAR  {grupo['nombre']}",
            state="normal",
            bg="#3a1111", fg="#ff4444"))

    def _secuencia_apagar(self, g):
        grupo_running[g] = True
        grupo = GRUPOS[g]
        bits = list(reversed(grupo["bits"]))  # orden inverso

        self.root.after(0, lambda: self.status_vars[g].set("Apagando..."))
        self.root.after(0, lambda: self.btn_widgets[g].config(
            text=f"⏳  APAGANDO...", state="disabled",
            bg="#2a2a2a", fg="#888888"))

        for idx, b in enumerate(bits):
            set_led(b, False)
            self.root.after(0, self._update_all)
            self.root.after(0, lambda g=g, idx=idx, bits=bits: self.status_vars[g].set(
                f"Apagado {LED_CONFIG[bits[idx]]['nombre']}..."))
            time.sleep(RETARDO)

        grupo_state[g] = False
        grupo_running[g] = False
        self.root.after(0, lambda: self.status_vars[g].set("Apagado"))
        self.root.after(0, lambda: self.btn_widgets[g].config(
            text=f"▶  ENCENDER  {grupo['nombre']}",
            state="normal",
            bg=grupo["color_off"], fg=grupo["color"]))

    def _apagar_todo(self):
        for i in range(9):
            set_led(i, False)
        for g in range(3):
            grupo_state[g] = False
            grupo_running[g] = False
            self.status_vars[g].set("Apagado")
            grupo = GRUPOS[g]
            self.btn_widgets[g].config(
                text=f"▶  ENCENDER  {grupo['nombre']}",
                state="normal",
                bg=grupo["color_off"], fg=grupo["color"])
        self._update_all()

    def _update_all(self):
        # Actualizar indicadores de grupo
        for g, grupo in enumerate(GRUPOS):
            for idx, b in enumerate(grupo["bits"]):
                cfg = LED_CONFIG[b]
                on = led_state[b]
                self.led_indicators[g][idx].config(
                    fg=cfg["color"] if on else cfg["color_dim"])

        # Actualizar lista de bits
        for i in range(9):
            cfg = LED_CONFIG[i]
            on = led_state[i]
            self.all_bit_labels[i].config(
                text="● ON " if on else "○ OFF",
                fg=cfg["color"] if on else "#4a5568")

        self._update_bus_display()

    def _update_bus_display(self):
        byte = 0
        for i in range(9):
            if led_state[i]:
                byte |= (1 << i)
        self.bus_hex.set(f"0x{byte:03X}")
        self.bus_bin.set(f"{byte:09b}")
        self.bus_dec.set(f"DEC: {byte}")

    def _salir(self):
        if not SIMULATION:
            GPIO.cleanup()
        self.root.destroy()

# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_gpio()
    root = tk.Tk()
    app = SequenceController(root)
    root.mainloop()

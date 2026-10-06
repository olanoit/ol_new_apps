#!/usr/bin/env python3
"""GUI de escritorio (Windows) para el agente local ESC/POS.

Tkinter puro (sin dependencias de UI externas, pensado para empaquetarse con PyInstaller +
Inno Setup en un ``.exe`` que corre en la PC Windows del local) — pero en vez
de monitorear una carpeta de ventas de balanza, administra el servidor HTTP
del Camino A y el cliente websocket del Camino B definidos en
``al_pos_local_agent.py`` (mismo directorio). Esta GUI no reimplementa
nada de la lógica de impresión/bus — solo la arranca, la detiene y refleja
su actividad en pantalla vía el hook ``stats_cb`` que ese módulo expone.

Pensado para el caso "el servidor de Odoo no tiene ruta de red hacia la
impresora" (Odoo.sh, o cualquier hosting fuera de la LAN del local) con una
PC Windows del local que se puede dejar siempre encendida (mismo modelo de
despliegue que el Monitor de Balanza) — no para un Raspberry Pi headless,
donde sigue aplicando ``al_pos_local_agent.py`` directo + systemd (ver
``README.md`` en esta misma carpeta, o ``docs/GUIA_INSTALACION_TECNICO.md``).
"""
import logging
import queue
import secrets
import socket
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    import al_pos_local_agent as agent
except Exception as exc:  # pragma: no cover - solo puede pasar con una instalación rota
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "No se pudo cargar el agente",
        f"No se pudo importar al_pos_local_agent.py desde:\n{BASE_DIR}\n\n"
        f"Error: {exc}\n\n"
        "Verifica que ambos archivos estén en la misma carpeta.",
    )
    sys.exit(1)


# ─── Estilo — misma identidad visual que Monitor de Balanza ────────────────────

COLORS = {
    "bg":        "#16181b",
    "panel":     "#1e2124",
    "card":      "#25282c",
    "card_alt":  "#2c3034",
    "border":    "#3a3f45",
    "accent":    "#f2a63e",
    "accent_dim":"#8a5f22",
    "green":     "#6bcf8f",
    "red":       "#f0685f",
    "orange":    "#e8974a",
    "blue":      "#6aa3e0",
    "teal":      "#45c2b1",
    "text":      "#f3f1ea",
    "text_dim":  "#9a9fa6",
    "text_hint": "#6d7278",
    "input_bg":  "#121315",
    "input_fg":  "#e7e4da",
    "log_bg":    "#0d0e10",
    "log_text":  "#c7c4ba",
    "log_info":  "#6aa3e0",
    "log_ok":    "#6bcf8f",
    "log_warn":  "#e8974a",
    "log_error": "#f0685f",
}

FONT_BODY    = ("Segoe UI", 9)
FONT_LABEL   = ("Segoe UI", 9, "bold")
FONT_TITLE   = ("Segoe UI", 16, "bold")
FONT_SECTION = ("Segoe UI", 10, "bold")
FONT_READOUT = ("Consolas", 12, "bold")

_CFG_PAD_X = 14
_CFG_PAD_Y = 10


class QueueHandler(logging.Handler):
    """Bridge estándar logging-thread -> Tk main loop (mismo patrón que
    app_balanza.py): el logging real ocurre en hilos de fondo (servidor
    HTTP, BusListener), y Tkinter solo puede tocarse de forma segura desde
    el hilo principal — así que acá solo se encola el record, y
    ``ScaleMonitorApp``-equivalente (``AgentGuiApp``) lo drena con
    ``root.after()``."""

    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(record)


def _lighten(hex_color: str, amount: int = 20) -> str:
    try:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return (f"#{min(255, r + amount):02x}"
                f"{min(255, g + amount):02x}"
                f"{min(255, b + amount):02x}")
    except Exception:
        return hex_color


def _blend(hex_color: str, hex_bg: str, ratio: float = 0.35) -> str:
    try:
        c = hex_color.lstrip("#")
        bgc = hex_bg.lstrip("#")
        cr, cg, cb = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        br, bg_, bb = int(bgc[0:2], 16), int(bgc[2:4], 16), int(bgc[4:6], 16)
        r = round(cr + (br - cr) * ratio)
        g = round(cg + (bg_ - cg) * ratio)
        b = round(cb + (bb - cb) * ratio)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color


class AgentGuiApp:
    CONFIG_FILE = BASE_DIR / "agent_gui_config.yaml"

    def __init__(self):
        self.server = None
        self.server_thread: Optional[threading.Thread] = None
        self.bus_listener: Optional[agent.BusListener] = None
        self.log_queue: queue.Queue = queue.Queue()
        self.stats_queue: queue.Queue = queue.Queue()
        self.config = self._load_config()

        self.root = tk.Tk()
        self._setup_window()
        self._setup_logging()
        self._build_ui()
        self._apply_config_to_vars()
        self._start_log_consumer()
        self._update_badge("stopped")
        self._update_bus_badge("inactive")

    # ── Configuración (persistencia en YAML, junto al script) ──────────────

    def _load_config(self) -> dict:
        defaults = {
            "server": {
                "listen_host": "0.0.0.0",
                "listen_port": 8765,
                "allowed_printers": "",
                "token": "",
                "cors_origin": "*",
                "tls_enabled": False,
                "tls_hostname": "",
            },
            "bus": {
                "odoo_url": "",
                "odoo_db": "",
                "bus_channel": "",
                "ack_path": "",
            },
            "log_level": "INFO",
        }
        if self.CONFIG_FILE.exists():
            try:
                import yaml
                with open(self.CONFIG_FILE, encoding="utf-8") as f:
                    u = yaml.safe_load(f) or {}
                for s, v in u.items():
                    if s in defaults and isinstance(v, dict):
                        defaults[s].update(v)
                    else:
                        defaults[s] = v
            except Exception:
                pass
        return defaults

    def _apply_config_to_vars(self):
        s, b = self.config["server"], self.config["bus"]
        self.var_listen_host.set(s.get("listen_host", "0.0.0.0"))
        self.var_listen_port.set(str(s.get("listen_port", 8765)))
        self.var_allowed_printers.set(s.get("allowed_printers", ""))
        self.var_token.set(s.get("token", ""))
        self.var_cors_origin.set(s.get("cors_origin", "*"))
        self.var_tls_enabled.set(bool(s.get("tls_enabled", False)))
        self.var_tls_hostname.set(s.get("tls_hostname", ""))
        self.var_odoo_url.set(b.get("odoo_url", ""))
        self.var_odoo_db.set(b.get("odoo_db", ""))
        self.var_bus_channel.set(b.get("bus_channel", ""))
        self.var_ack_path.set(b.get("ack_path", ""))
        self.var_log_level.set(self.config.get("log_level", "INFO"))

    def _save_config(self):
        try:
            import yaml
            cfg = {
                "server": {
                    "listen_host": self.var_listen_host.get().strip() or "0.0.0.0",
                    "listen_port": int(self.var_listen_port.get().strip() or 8765),
                    "allowed_printers": self.var_allowed_printers.get().strip(),
                    "token": self.var_token.get().strip(),
                    "cors_origin": self.var_cors_origin.get().strip() or "*",
                    "tls_enabled": bool(self.var_tls_enabled.get()),
                    "tls_hostname": self.var_tls_hostname.get().strip(),
                },
                "bus": {
                    "odoo_url": self.var_odoo_url.get().strip(),
                    "odoo_db": self.var_odoo_db.get().strip(),
                    "bus_channel": self.var_bus_channel.get().strip(),
                    "ack_path": self.var_ack_path.get().strip(),
                },
                "log_level": self.var_log_level.get().strip() or "INFO",
            }
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
            self.config = cfg
            logging.getLogger().setLevel(getattr(logging, cfg["log_level"], logging.INFO))
            self._log_gui("Configuración guardada correctamente", "ok")
            return cfg
        except ImportError:
            messagebox.showerror("Error", "PyYAML no instalado.\nEjecuta:  pip install pyyaml")
            return None
        except ValueError:
            messagebox.showerror("Puerto inválido", "El puerto del agente debe ser un número.")
            self.nb.select(1)
            return None
        except Exception as e:
            messagebox.showerror("Error al guardar", str(e))
            return None

    def _build_env(self) -> dict:
        """Traduce los campos de la GUI al mismo formato de variables de
        entorno que ``al_pos_local_agent.Config`` ya sabe leer en modo
        CLI/systemd — una sola fuente de verdad para el parseo/validación
        (allow-list, puerto, etc.), la GUI no repite esa lógica."""
        return {
            "AL_AGENT_LISTEN_HOST": self.var_listen_host.get().strip() or "0.0.0.0",
            "AL_AGENT_LISTEN_PORT": self.var_listen_port.get().strip() or "8765",
            "AL_AGENT_ALLOWED_PRINTERS": self.var_allowed_printers.get().strip(),
            "AL_AGENT_TOKEN": self.var_token.get().strip(),
            "AL_AGENT_CORS_ORIGIN": self.var_cors_origin.get().strip() or "*",
            "AL_AGENT_TLS_ENABLED": "1" if self.var_tls_enabled.get() else "0",
            "AL_AGENT_TLS_HOSTNAME": self.var_tls_hostname.get().strip(),
            "AL_AGENT_ODOO_URL": self.var_odoo_url.get().strip(),
            "AL_AGENT_ODOO_DB": self.var_odoo_db.get().strip(),
            "AL_AGENT_BUS_CHANNEL": self.var_bus_channel.get().strip(),
            # Explícito a propósito (incluso vacío): un campo vacío debe
            # desactivar el ACK, no caer al default del módulo — ver
            # Config.__init__ en al_pos_local_agent.py.
            "AL_AGENT_ACK_PATH": self.var_ack_path.get().strip(),
        }

    # ── Ventana ──────────────────────────────────────────────────────────

    def _setup_window(self):
        self.root.title(f"Agente ESC/POS — Odoo 19 (v{agent.AGENT_VERSION})")
        self.root.geometry("1060x760")
        self.root.minsize(880, 620)
        self.root.configure(bg=COLORS["bg"])
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_logging(self):
        # Reemplaza el StreamHandler que al_pos_local_agent.py deja
        # instalado al importarse (logging.basicConfig a nivel de módulo):
        # en un .exe empaquetado como "windowed" (sin consola) sys.stderr
        # puede ser None, y logging revienta al intentar escribir ahí. La
        # GUI es la única salida de logs que importa acá.
        root_log = logging.getLogger()
        root_log.handlers.clear()
        root_log.setLevel(logging.DEBUG)
        h = QueueHandler(self.log_queue)
        h.setFormatter(logging.Formatter("%(message)s"))
        root_log.addHandler(h)

    # ── Construcción UI ─────────────────────────────────────────────────

    def _build_ui(self):
        header = tk.Frame(self.root, bg=COLORS["panel"], pady=12)
        header.pack(fill="x")

        tk.Label(
            header, text="🖨  Agente ESC/POS",
            font=FONT_TITLE, bg=COLORS["panel"], fg=COLORS["accent"],
        ).pack(side="left", padx=20)

        tk.Label(
            header, text=f"Impresión de red · Odoo 19 · v{agent.AGENT_VERSION}",
            font=FONT_BODY, bg=COLORS["panel"], fg=COLORS["text_dim"],
        ).pack(side="left", padx=(0, 20))

        # Badge Camino B (izquierda del principal — es secundario/opcional)
        self.bus_badge_frame = tk.Frame(header, bg=COLORS["panel"])
        self.bus_badge_frame.pack(side="right", padx=(20, 8))
        self.bus_badge_canvas = tk.Canvas(
            self.bus_badge_frame, width=16, height=16,
            bg=COLORS["panel"], highlightthickness=0,
        )
        self.bus_badge_canvas.pack(side="left", padx=(0, 6))
        self._bus_glow = self.bus_badge_canvas.create_oval(1, 1, 15, 15, outline="", fill=COLORS["panel"])
        self._bus_lamp = self.bus_badge_canvas.create_oval(4, 4, 12, 12, outline="", fill=COLORS["text_hint"])
        self.bus_badge_label = tk.Label(
            self.bus_badge_frame, text="Camino B: inactivo",
            font=FONT_BODY, bg=COLORS["panel"], fg=COLORS["text_dim"],
        )
        self.bus_badge_label.pack(side="left")

        # Badge principal (servidor Camino A — siempre presente)
        self.badge_frame = tk.Frame(header, bg=COLORS["panel"])
        self.badge_frame.pack(side="right", padx=20)
        self.badge_canvas = tk.Canvas(
            self.badge_frame, width=22, height=22,
            bg=COLORS["panel"], highlightthickness=0,
        )
        self.badge_canvas.pack(side="left", padx=(0, 6))
        self._badge_glow = self.badge_canvas.create_oval(2, 2, 20, 20, outline="", fill=COLORS["panel"])
        self._badge_lamp = self.badge_canvas.create_oval(6, 6, 16, 16, outline="", fill=COLORS["red"])
        self.badge_label = tk.Label(
            self.badge_frame, text="Detenido",
            font=FONT_LABEL, bg=COLORS["panel"], fg=COLORS["text_dim"],
        )
        self.badge_label.pack(side="left")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=COLORS["panel"],
                        foreground=COLORS["text_dim"], padding=[18, 9],
                        font=("Segoe UI", 9))
        style.map("TNotebook.Tab",
                  background=[("selected", COLORS["card"])],
                  foreground=[("selected", COLORS["text"])],
                  font=[("selected", ("Segoe UI", 9, "bold"))])
        style.configure("Vertical.TScrollbar",
                        background=COLORS["card"], troughcolor=COLORS["bg"],
                        borderwidth=0, arrowcolor=COLORS["text_dim"])
        # `tk.Checkbutton` clásico dibuja el indicador con los colores del
        # propio widget (bg/selectcolor) — en un tema oscuro personalizado
        # como este, terminaba prácticamente invisible (casi el mismo color
        # marcado y sin marcar, confirmado por el usuario: "se ve mal, no
        # se nota si tildó"). `ttk.Checkbutton` con el tema "clam" (ya en
        # uso arriba) sí permite pintar el indicador con `style.map()` —
        # acá con el color de acento cuando está marcado, para que el
        # estado se note de un vistazo.
        style.configure("Dark.TCheckbutton", background=COLORS["card"],
                        foreground=COLORS["text"], font=("Segoe UI", 9))
        style.map("Dark.TCheckbutton",
                  background=[("active", COLORS["card"])],
                  indicatorcolor=[("selected", COLORS["accent"]), ("!selected", COLORS["input_bg"])],
                  indicatorbackground=[("selected", COLORS["accent"]), ("!selected", COLORS["input_bg"])])

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        t1 = tk.Frame(self.nb, bg=COLORS["bg"])
        self.nb.add(t1, text="  🖨  Agente  ")
        self._build_control_tab(t1)

        t2 = tk.Frame(self.nb, bg=COLORS["bg"])
        self.nb.add(t2, text="  ⚙  Configuración  ")
        self._build_config_tab(t2)

        t3 = tk.Frame(self.nb, bg=COLORS["bg"])
        self.nb.add(t3, text="  📋  Registros  ")
        self._build_logs_tab(t3)

    # ── Tab Agente (monitor) ────────────────────────────────────────────

    def _build_control_tab(self, parent):
        action_card = self._card(parent, "Acciones")
        row = tk.Frame(action_card, bg=COLORS["card"], pady=12)
        row.pack(fill="x", padx=14)

        self.btn_start = self._btn(row, "▶  Iniciar", COLORS["green"], self._on_start)
        self.btn_start.pack(side="left", padx=(0, 6))

        self.btn_stop = self._btn(row, "⏹  Detener", COLORS["red"], self._on_stop)
        self.btn_stop.pack(side="left", padx=(0, 6))
        self.btn_stop.configure(state="disabled")

        self.btn_restart = self._btn(row, "↺  Reiniciar", COLORS["orange"], self._on_restart)
        self.btn_restart.pack(side="left", padx=(0, 6))
        self.btn_restart.configure(state="disabled")

        self._btn(
            row, "  Test de conexión  ", COLORS["accent"], self._on_test
        ).pack(side="right")

        # Estadísticas Camino A (ticket normal del POS)
        ticket_card = self._card(parent, "Actividad — ticket del POS (Camino A)")
        tg = tk.Frame(ticket_card, bg=COLORS["card"], pady=10, padx=14)
        tg.pack(fill="x")

        self.stat_vars = {k: tk.StringVar(value="—") for k in (
            "tickets_ok", "tickets_error", "last_ticket", "last_ticket_time",
            "cashbox_ok", "cashbox_error",
        )}
        for k in ("tickets_ok", "tickets_error", "cashbox_ok", "cashbox_error"):
            self.stat_vars[k].set("0")

        ticket_defs = [
            ("Tickets impresos",      "tickets_ok",       COLORS["green"]),
            ("Errores de impresión",  "tickets_error",    COLORS["red"]),
            ("Último ticket",         "last_ticket",      COLORS["text"]),
            ("Hora último ticket",    "last_ticket_time", COLORS["text_dim"]),
            ("Cajón abierto",         "cashbox_ok",        COLORS["teal"]),
            ("Errores de cajón",      "cashbox_error",     COLORS["red"]),
        ]
        self._stat_grid(tg, ticket_defs, self.stat_vars)

        # Estadísticas Camino B (comprobantes del backend)
        voucher_card = self._card(parent, "Actividad — comprobantes del backend (Camino B, opcional)")
        vg = tk.Frame(voucher_card, bg=COLORS["card"], pady=10, padx=14)
        vg.pack(fill="x")

        self.bus_stat_vars = {k: tk.StringVar(value="—") for k in (
            "vouchers_ok", "vouchers_error", "last_voucher", "last_voucher_time",
        )}
        self.bus_stat_vars["vouchers_ok"].set("0")
        self.bus_stat_vars["vouchers_error"].set("0")

        voucher_defs = [
            ("Comprobantes impresos", "vouchers_ok",        COLORS["green"]),
            ("Errores de comprobante","vouchers_error",     COLORS["red"]),
            ("Último comprobante",    "last_voucher",       COLORS["text"]),
            ("Hora último comprobante","last_voucher_time", COLORS["text_dim"]),
        ]
        self._stat_grid(vg, voucher_defs, self.bus_stat_vars)

        # Actividad reciente
        self._log_card = self._card(parent, "Actividad reciente", expand=True)
        self.mini_log = scrolledtext.ScrolledText(
            self._log_card, height=6,
            bg=COLORS["log_bg"], fg=COLORS["log_text"],
            font=("Consolas", 9), relief="flat",
            state="disabled", wrap="word",
            selectbackground=COLORS["border"],
        )
        self.mini_log.pack(fill="both", expand=True, padx=8, pady=8)
        self._configure_log_tags(self.mini_log)

    # ── Tab Configuración ───────────────────────────────────────────────

    def _build_config_tab(self, parent):
        canvas = tk.Canvas(parent, bg=COLORS["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        frame = tk.Frame(canvas, bg=COLORS["bg"])
        win_id = canvas.create_window((0, 0), window=frame, anchor="nw")

        def _on_frame_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(e):
            canvas.itemconfig(win_id, width=e.width)

        frame.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def section(icon, title, subtitle=""):
            outer = tk.Frame(frame, bg=COLORS["bg"])
            outer.pack(fill="x", padx=_CFG_PAD_X, pady=(_CFG_PAD_Y, 0))
            tk.Frame(outer, bg=COLORS["accent"], width=4).pack(side="left", fill="y", padx=(0, 10))
            inner = tk.Frame(outer, bg=COLORS["card"])
            inner.pack(side="left", fill="both", expand=True)
            hdr = tk.Frame(inner, bg=COLORS["card_alt"])
            hdr.pack(fill="x")
            tk.Label(hdr, text=f"  {icon}  {title}", bg=COLORS["card_alt"], fg=COLORS["text"],
                     font=("Segoe UI", 10, "bold"), pady=8).pack(side="left", padx=4)
            if subtitle:
                tk.Label(hdr, text=subtitle, bg=COLORS["card_alt"], fg=COLORS["text_dim"],
                         font=("Segoe UI", 8)).pack(side="left", padx=(0, 10))
            body = tk.Frame(inner, bg=COLORS["card"])
            body.pack(fill="both", expand=True, padx=16, pady=12)
            body.columnconfigure(1, weight=1)
            return body

        def field_row(body, row_idx, label, var, hint=""):
            tk.Label(body, text=label, width=22, anchor="w", bg=COLORS["card"], fg=COLORS["text_dim"],
                     font=("Segoe UI", 9)).grid(row=row_idx, column=0, sticky="w", padx=(0, 12), pady=6)
            entry = tk.Entry(body, textvariable=var, bg=COLORS["input_bg"], fg=COLORS["input_fg"],
                             insertbackground=COLORS["input_fg"], relief="flat", font=("Segoe UI", 9),
                             highlightthickness=1, highlightbackground=COLORS["border"],
                             highlightcolor=COLORS["accent"])
            entry.grid(row=row_idx, column=1, sticky="ew", pady=6,
                       columnspan=2 if not hint else 1)
            if hint:
                tk.Label(body, text=hint, anchor="w", bg=COLORS["card"], fg=COLORS["text_hint"],
                         font=("Segoe UI", 8)).grid(row=row_idx, column=2, sticky="w", padx=(8, 0))
            return entry

        def check_row(body, row_idx, label, var, hint=""):
            tk.Label(body, text=label, width=22, anchor="w", bg=COLORS["card"], fg=COLORS["text_dim"],
                     font=("Segoe UI", 9)).grid(row=row_idx, column=0, sticky="w", padx=(0, 12), pady=6)
            # Texto explícito (Activado/Desactivado) además del indicador de
            # color — no depender solo del color para que el estado se note
            # (ver el comentario junto a "Dark.TCheckbutton", arriba).
            state_label = tk.Label(body, bg=COLORS["card"], font=("Segoe UI", 9, "bold"))
            state_label.grid(row=row_idx, column=1, sticky="w", padx=(72, 0), pady=6)

            def _refresh_state_label(*_args):
                if var.get():
                    state_label.configure(text="✓ Activado", fg=COLORS["green"])
                else:
                    state_label.configure(text="Desactivado", fg=COLORS["text_hint"])

            chk = ttk.Checkbutton(body, variable=var, style="Dark.TCheckbutton")
            chk.grid(row=row_idx, column=1, sticky="w", pady=6)
            # `trace_add` (no solo `command=`) para que también se actualice
            # cuando `_apply_config_to_vars()` hace `var.set(...)` al cargar
            # `agent_gui_config.yaml`, no solo al hacer clic.
            var.trace_add("write", _refresh_state_label)
            _refresh_state_label()
            if hint:
                tk.Label(body, text=hint, anchor="w", bg=COLORS["card"], fg=COLORS["text_hint"],
                         font=("Segoe UI", 8)).grid(row=row_idx, column=2, sticky="w", padx=(8, 0))
            return chk

        def token_row(body, row_idx, label, var, hint=""):
            tk.Label(body, text=label, width=22, anchor="w", bg=COLORS["card"], fg=COLORS["text_dim"],
                     font=("Segoe UI", 9)).grid(row=row_idx, column=0, sticky="w", padx=(0, 12), pady=6)
            entry = tk.Entry(body, textvariable=var, bg=COLORS["input_bg"], fg=COLORS["input_fg"],
                             insertbackground=COLORS["input_fg"], relief="flat", font=("Segoe UI", 9),
                             highlightthickness=1, highlightbackground=COLORS["border"],
                             highlightcolor=COLORS["accent"])
            entry.grid(row=row_idx, column=1, sticky="ew", padx=(0, 8), pady=6)

            def _generate():
                var.set(secrets.token_hex(32))

            btn = tk.Button(body, text="  Generar  ", command=_generate,
                            bg=COLORS["accent_dim"], fg="#fff", relief="flat",
                            cursor="hand2", font=("Segoe UI", 9), padx=4, pady=3)
            btn.grid(row=row_idx, column=2, sticky="e", pady=6)
            btn.bind("<Enter>", lambda e: btn.configure(bg=_lighten(COLORS["accent_dim"])))
            btn.bind("<Leave>", lambda e: btn.configure(bg=COLORS["accent_dim"]))
            if hint:
                tk.Label(body, text=hint, anchor="w", bg=COLORS["card"], fg=COLORS["text_hint"],
                         font=("Segoe UI", 8)).grid(row=row_idx + 1, column=1, columnspan=2, sticky="w")
            return entry

        self.var_listen_host = tk.StringVar()
        self.var_listen_port = tk.StringVar()
        self.var_allowed_printers = tk.StringVar()
        self.var_token = tk.StringVar()
        self.var_cors_origin = tk.StringVar()
        self.var_tls_enabled = tk.BooleanVar()
        self.var_tls_hostname = tk.StringVar()
        self.var_odoo_url = tk.StringVar()
        self.var_odoo_db = tk.StringVar()
        self.var_bus_channel = tk.StringVar()
        self.var_ack_path = tk.StringVar()
        self.var_log_level = tk.StringVar()

        b1 = section("🖨", "Servidor del agente", "Camino A — siempre activo, atiende el ticket normal del POS")
        field_row(b1, 0, "Impresoras permitidas", self.var_allowed_printers,
                  hint="IP:puerto separados por coma")
        field_row(b1, 1, "Interfaz de escucha", self.var_listen_host)
        field_row(b1, 2, "Puerto del agente", self.var_listen_port)
        token_row(b1, 3, "Token compartido", self.var_token,
                  hint="Recomendado — evita que cualquiera en la red mande trabajos de impresión.")
        field_row(b1, 5, "CORS origin", self.var_cors_origin,
                  hint="'*' salvo que se quiera acotar al dominio de Odoo")

        b1b = section(
            "🔒", "Seguridad (HTTPS)",
            "Obligatorio si Odoo está detrás de HTTPS (Odoo.sh u otro hosting con TLS)",
        )
        check_row(b1b, 0, "Habilitar HTTPS", self.var_tls_enabled,
                  hint="Certificado autofirmado, generado una sola vez y reutilizado en cada arranque.")
        field_row(b1b, 1, "Hostname / IP del certificado", self.var_tls_hostname,
                  hint="Mismo host que vas a poner en 'URL del agente local' en Odoo (sin https:// ni puerto).")
        tk.Label(
            b1b,
            text="Sin esto, el navegador del cajero bloquea el ticket con \"Mixed Content\" "
                 "cuando Odoo es HTTPS y el agente responde por HTTP plano — no es un error de "
                 "configuración, es el navegador cortando la petición antes de que salga. La "
                 "primera vez, hay que abrir https://<host>:<puerto>/health y aceptar la "
                 "advertencia de seguridad del certificado autofirmado.",
            anchor="w", justify="left", wraplength=520, bg=COLORS["card"], fg=COLORS["text_hint"],
            font=("Segoe UI", 8),
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))

        b2 = section("🔄", "Conexión con Odoo", "Camino B, opcional — comprobantes que imprime el backend")
        field_row(b2, 0, "URL de Odoo", self.var_odoo_url,
                  hint="ej. https://mi-instancia.odoo.com")
        field_row(b2, 1, "Base de datos", self.var_odoo_db)
        token_row(b2, 2, "Canal del agente", self.var_bus_channel,
                  hint="Copiar desde Ajustes → Punto de Venta → el PDV en Odoo — no generar acá.")
        field_row(b2, 4, "Ruta del ACK", self.var_ack_path,
                  hint="Vacío desactiva la confirmación de impresión hacia Odoo")

        b3 = section("📋", "Registro")
        tk.Label(b3, text="Nivel de log", width=22, anchor="w", bg=COLORS["card"], fg=COLORS["text_dim"],
                 font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", padx=(0, 12), pady=6)
        combo = ttk.Combobox(b3, textvariable=self.var_log_level, state="readonly",
                             values=["DEBUG", "INFO", "WARNING", "ERROR"], width=15)
        combo.grid(row=0, column=1, sticky="w", pady=6)

        save_row = tk.Frame(frame, bg=COLORS["bg"])
        save_row.pack(fill="x", padx=_CFG_PAD_X, pady=(_CFG_PAD_Y, _CFG_PAD_Y))
        self._btn(save_row, "  Guardar configuración  ", COLORS["accent"],
                  self._save_config).pack(side="left")

    # ── Tab Registros ────────────────────────────────────────────────────

    def _build_logs_tab(self, parent):
        card = self._card(parent, "Registro completo", expand=True)
        self.log_text = scrolledtext.ScrolledText(
            card, bg=COLORS["log_bg"], fg=COLORS["log_text"],
            font=("Consolas", 9), relief="flat",
            state="disabled", wrap="word",
            selectbackground=COLORS["border"],
        )
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)
        self._configure_log_tags(self.log_text)

    def _configure_log_tags(self, widget):
        for tag, color in [
            ("OK",      COLORS["log_ok"]),
            ("INFO",    COLORS["log_info"]),
            ("WARNING", COLORS["log_warn"]),
            ("ERROR",   COLORS["log_error"]),
            ("DEBUG",   COLORS["text_hint"]),
            ("TIME",    COLORS["text_hint"]),
        ]:
            widget.tag_configure(tag, foreground=color)

    # ── Acciones ─────────────────────────────────────────────────────────

    def _on_start(self):
        cfg = self._save_config()
        if not cfg:
            return

        try:
            config = agent.Config(env=self._build_env())
        except ValueError as e:
            messagebox.showwarning("Configuración incompleta", str(e))
            self.nb.select(1)
            return

        if agent.EscposNetwork is None:
            messagebox.showerror(
                "Falta python-escpos",
                "No está instalada la librería python-escpos.\n\n"
                "Ejecuta:  pip install -r requirements.txt",
            )
            return

        try:
            server, bus_listener = agent.create_server(config, stats_cb=self._on_stats_event)
        except OSError as e:
            messagebox.showerror(
                "No se pudo iniciar",
                f"No se pudo abrir el puerto {config.listen_port}.\n\n{e}\n\n"
                "¿Hay otra copia del agente corriendo, o el puerto lo usa otro programa?",
            )
            return

        self.server = server
        self.bus_listener = bus_listener
        self.server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        self.server_thread.start()

        if bus_listener is not None:
            bus_listener.start()
            self._update_bus_badge("connecting")
        else:
            want_bus = bool(config.odoo_url or config.odoo_db or config.bus_channel)
            self._update_bus_badge("error" if want_bus else "inactive")
            if want_bus:
                self._log_gui(
                    "Camino B configurado pero incompleto o con dependencias "
                    "faltantes — revisa Configuración y Registros.", "warning",
                )

        self._update_badge("running")
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.btn_restart.configure(state="normal")
        scheme = "https" if server.tls_enabled else "http"
        self._log_gui(
            f"Agente iniciado — escuchando en {scheme}://{config.listen_host}:{config.listen_port}", "ok",
        )
        if server.tls_enabled:
            self._log_gui(
                f"HTTPS activo — la primera vez, abrir https://{config.tls_hostname}:"
                f"{config.listen_port}/health en el navegador del cajero y aceptar la "
                "advertencia de seguridad antes de la primera venta.", "warning",
            )
        elif config.tls_enabled and agent.x509 is None:
            self._log_gui(
                "HTTPS pedido pero falta instalar 'cryptography' — el agente arrancó "
                "solo por HTTP (pip install -r requirements.txt).", "error",
            )

    def _on_stop(self):
        if self.bus_listener is not None:
            self.bus_listener.stop()
            self.bus_listener = None
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        self.server_thread = None
        self._update_badge("stopped")
        self._update_bus_badge("inactive")
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.btn_restart.configure(state="disabled")
        self._log_gui("Agente detenido", "warning")

    def _on_restart(self):
        self._log_gui("Reiniciando agente...", "warning")
        self._on_stop()
        self.root.after(800, self._on_start)

    def _on_test(self):
        printers_raw = self.var_allowed_printers.get().strip()
        if not printers_raw:
            messagebox.showwarning(
                "Impresoras no configuradas",
                "Define al menos una impresora en Configuración (IP:puerto).",
            )
            self.nb.select(1)
            return
        try:
            printers = agent._parse_allowed_printers(printers_raw)
        except ValueError as e:
            messagebox.showwarning("Formato inválido", str(e))
            self.nb.select(1)
            return

        odoo_url = self.var_odoo_url.get().strip()
        odoo_db = self.var_odoo_db.get().strip()

        self._log_gui("Probando conexión...", "info")

        # `test()` corre en un hilo de fondo — Tk no se puede tocar desde
        # ahí de forma confiable (confirmado en pruebas: incluso
        # `root.after()` desde otro hilo puede romper con "main thread is
        # not in main loop"). En vez de inventar un segundo mecanismo de
        # cruce de hilos, se reusa el mismo camino ya thread-safe que usan
        # BusListener/AgentRequestHandler: el logger estándar, cuyo
        # QueueHandler (`_setup_logging`) solo hace `queue.Queue.put()`
        # (thread-safe) y `_consume_logs()` lo drena en el hilo principal.
        test_log = logging.getLogger("al_pos_local_agent_gui.test")

        def test():
            for host, port in sorted(printers):
                try:
                    with socket.create_connection((host, port), timeout=3):
                        pass
                    test_log.info("✓ Impresora %s:%s alcanzable", host, port)
                except OSError as e:
                    test_log.error("✗ Impresora %s:%s no responde (%s)", host, port, e)

            if odoo_url and odoo_db:
                if agent.requests is None:
                    test_log.error("✗ Falta instalar 'requests' para probar Odoo")
                    return
                try:
                    r = agent.requests.get(
                        f"{odoo_url.rstrip('/')}/web/login",
                        params={"db": odoo_db}, timeout=8, allow_redirects=False,
                    )
                    if r.status_code in (200, 302):
                        test_log.info(
                            "✓ Servidor Odoo (%s) alcanzable, base '%s' válida", odoo_url, odoo_db,
                        )
                    else:
                        test_log.error(
                            "✗ Odoo respondió HTTP %s — revisa URL/base de datos", r.status_code,
                        )
                except Exception as e:
                    test_log.error("✗ No se pudo conectar con Odoo (%s): %s", odoo_url, e)
            elif odoo_url or odoo_db:
                test_log.warning(
                    "Camino B incompleto — falta URL de Odoo o nombre de base de datos.",
                )

        threading.Thread(target=test, daemon=True).start()

    # ── Eventos de actividad (llamados desde hilos de fondo) ───────────────

    def _on_stats_event(self, event, data):
        """Hook pasado a `agent.create_server()` — se invoca desde el hilo
        del servidor HTTP o del BusListener, nunca desde el hilo principal
        de Tk. `root.after()` llamado directo desde un hilo ajeno no es
        confiable (confirmado en pruebas: puede romper con "main thread is
        not in main loop" incluso con el mainloop corriendo) — así que acá
        solo se encola en `stats_queue` (`queue.Queue.put` sí es
        thread-safe, no toca Tk) y `_consume_stats()`, que corre en el hilo
        de Tk, es quien la drena y aplica los cambios a los widgets."""
        self.stats_queue.put((event, data))

    def _apply_stats_event(self, event, data):
        now = datetime.now().strftime("%H:%M:%S")
        target = f"{data.get('ip', '?')}:{data.get('port', '?')}" if "ip" in data else "—"

        if event == "ticket_printed":
            self._bump(self.stat_vars, "tickets_ok")
            self.stat_vars["last_ticket"].set(target)
            self.stat_vars["last_ticket_time"].set(now)
            self._log_gui(f"Ticket impreso en {target}", "ok")
        elif event == "ticket_failed":
            self._bump(self.stat_vars, "tickets_error")
            self._log_gui(f"Error imprimiendo ticket en {target}: {data.get('error', '')}", "error")
        elif event == "cashbox_opened":
            self._bump(self.stat_vars, "cashbox_ok")
            self._log_gui(f"Cajón abierto en {target}", "ok")
        elif event == "cashbox_failed":
            self._bump(self.stat_vars, "cashbox_error")
            self._log_gui(f"Error abriendo cajón en {target}: {data.get('error', '')}", "error")
        elif event == "voucher_printed":
            self._bump(self.bus_stat_vars, "vouchers_ok")
            self.bus_stat_vars["last_voucher"].set(f"Orden #{data.get('order_id', '?')}")
            self.bus_stat_vars["last_voucher_time"].set(now)
            self._log_gui(f"Comprobante impreso (orden #{data.get('order_id')})", "ok")
        elif event == "voucher_failed":
            self._bump(self.bus_stat_vars, "vouchers_error")
            self._log_gui(
                f"Error imprimiendo comprobante (orden #{data.get('order_id')}): "
                f"{data.get('error', '')}", "error",
            )
        elif event == "bus_connected":
            self._update_bus_badge("connected")
            self._log_gui("Camino B: conectado al bus de Odoo", "ok")
        elif event == "bus_disconnected":
            self._update_bus_badge("disconnected")
            self._log_gui("Camino B: desconectado, reintentando...", "warning")

    def _bump(self, vars_dict, key):
        vars_dict[key].set(str(int(vars_dict[key].get()) + 1))

    # ── Widgets reutilizables ───────────────────────────────────────────

    def _stat_grid(self, parent, defs, textvars):
        for i, (lbl, key, color) in enumerate(defs):
            col = (i % 3) * 2
            r = i // 3
            tk.Label(parent, text=lbl, bg=COLORS["card"], fg=COLORS["text_dim"],
                     font=FONT_BODY).grid(row=r, column=col, sticky="w", pady=6, padx=(0, 8))
            chip = tk.Frame(parent, bg=COLORS["input_bg"],
                             highlightthickness=1, highlightbackground=COLORS["border"])
            chip.grid(row=r, column=col + 1, sticky="w", pady=6, padx=(0, 26))
            tk.Label(chip, textvariable=textvars[key], bg=COLORS["input_bg"], fg=color,
                     font=FONT_READOUT, padx=8, pady=2).pack()

    def _card(self, parent, title, expand=False):
        f = tk.LabelFrame(
            parent, text=f"  {title}  ",
            bg=COLORS["card"], fg=COLORS["text_dim"],
            font=FONT_SECTION, bd=1, relief="solid", labelanchor="nw",
        )
        kwargs = {"fill": "x", "padx": 14, "pady": (10, 0)}
        if expand:
            kwargs = {"fill": "both", "expand": True, "padx": 14, "pady": (10, 0)}
        f.pack(**kwargs)
        return f

    def _btn(self, parent, text, color, cmd, width=None, pady=8):
        kw = dict(
            text=text, command=cmd, bg=color,
            fg="#1a1508" if color == COLORS["accent"] else "#fff",
            relief="flat", cursor="hand2", font=FONT_LABEL, pady=pady, padx=14,
        )
        if width:
            kw["width"] = width
        b = tk.Button(parent, **kw)
        b.bind("<Enter>", lambda e: b.configure(bg=_lighten(color)))
        b.bind("<Leave>", lambda e: b.configure(bg=color))
        return b

    def _update_badge(self, state):
        d = {
            "running": (COLORS["green"], "Activo"),
            "stopped": (COLORS["red"], "Detenido"),
            "error": (COLORS["orange"], "Error"),
        }
        color, label = d.get(state, (COLORS["text_dim"], "Desconocido"))
        glow = _blend(color, COLORS["panel"], ratio=0.55)
        self.badge_canvas.itemconfig(self._badge_glow, fill=glow)
        self.badge_canvas.itemconfig(self._badge_lamp, fill=color)
        self.badge_label.configure(text=label, fg=color)

    def _update_bus_badge(self, state):
        d = {
            "inactive": (COLORS["text_hint"], "Camino B: inactivo"),
            "connecting": (COLORS["orange"], "Camino B: conectando..."),
            "connected": (COLORS["green"], "Camino B: conectado"),
            "disconnected": (COLORS["red"], "Camino B: desconectado"),
            "error": (COLORS["orange"], "Camino B: configuración incompleta"),
        }
        color, label = d.get(state, (COLORS["text_dim"], "Camino B: desconocido"))
        glow = _blend(color, COLORS["panel"], ratio=0.55)
        self.bus_badge_canvas.itemconfig(self._bus_glow, fill=glow)
        self.bus_badge_canvas.itemconfig(self._bus_lamp, fill=color)
        self.bus_badge_label.configure(text=label, fg=color)

    def _log_gui(self, msg, level="info"):
        ts = datetime.now().strftime("%H:%M:%S")
        tag = level.upper()
        for w in (self.log_text, self.mini_log):
            w.configure(state="normal")
            w.insert("end", f"{ts}  ", "TIME")
            w.insert("end", f"{msg}\n", tag)
            w.see("end")
            w.configure(state="disabled")

    def _start_log_consumer(self):
        self._consume_logs()
        self._consume_stats()

    def _consume_stats(self):
        try:
            while True:
                event, data = self.stats_queue.get_nowait()
                self._apply_stats_event(event, data)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._consume_stats)

    def _consume_logs(self):
        try:
            while True:
                rec = self.log_queue.get_nowait()
                ts = datetime.fromtimestamp(rec.created).strftime("%H:%M:%S")
                msg = rec.getMessage()
                tag = {
                    "DEBUG": "DEBUG", "INFO": "INFO",
                    "WARNING": "WARNING", "ERROR": "ERROR", "CRITICAL": "ERROR",
                }.get(rec.levelname, "INFO")
                if tag == "INFO" and "✓" in msg:
                    tag = "OK"
                for w in (self.log_text, self.mini_log):
                    w.configure(state="normal")
                    w.insert("end", f"{ts}  ", "TIME")
                    w.insert("end", f"{msg}\n", tag)
                    w.see("end")
                    w.configure(state="disabled")
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._consume_logs)

    def _on_close(self):
        running = self.server is not None
        if running:
            if messagebox.askyesno("Salir", "El agente está activo.\n¿Detenerlo y salir?"):
                self._on_stop()
                self.root.destroy()
        else:
            self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    AgentGuiApp().run()

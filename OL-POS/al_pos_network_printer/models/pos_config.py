import secrets

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.al_pos_network_printer.controllers.main import (
    print_test_ticket,
    release_connection,
    retry_print_receipt,
)


class PosConfig(models.Model):
    _inherit = "pos.config"

    # Toggle propio, mismo rol que `other_devices` (core) para
    # el bloque Epson: activa/oculta toda la sección "Impresora ESC/POS de
    # red" en Ajustes/la ficha del PDV. Antes esa sección vivía físicamente
    # anidada DENTRO del bloque nativo "ePos Printer" (Epson) — visible u
    # oculta según `pos_other_devices`/`other_devices`, el toggle de OTRO
    # proveedor, sin relación real con este módulo (pedido en vivo). Con un
    # toggle propio: activar este módulo oculta
    # el bloque nativo Epson y viceversa (mutuamente excluyentes, mismo
    # criterio que ya exigía `_check_single_receipt_printer_backend` como
    # validación al guardar, ahora también reflejado en la UI antes de
    # llegar a esa validación).
    #
    # Migración (`post_init_hook`, ver `__init__.py`): en un `pos.config`
    # que ya tenía `escpos_printer_ip` configurado antes de que existiera
    # este campo, se activa solo — sin eso, al actualizar el módulo la
    # sección entera desaparecería de la vista (toggle apagado por
    # default) aunque el ticket siguiera imprimiendo igual, dando la falsa
    # impresión de que se perdió la configuración.
    escpos_network_printer_enabled = fields.Boolean(
        string="Impresora ESC/POS de red",
        default=False,
        help="Activar para configurar una impresora térmica ESC/POS genérica "
             "de red (Xprinter, Zjiang, Gainscha y similares) como recibo "
             "principal, sin IoT Box. Mutuamente excluyente con 'ePos "
             "Printer' (Epson) de Odoo — activar uno oculta el otro.",
    )

    # El core (`point_of_sale/models/pos_config.py`) ya resuelve el mismo
    # caso de uso para impresoras Epson con `epson_printer_ip`, usando el
    # protocolo ePOS-XML propio de Epson (navegador -> impresora, sin pasar
    # por el backend de Odoo). Las impresoras ESC/POS genéricas de red no
    # hablan ese protocolo, así que necesitan su propio campo y su propio
    # camino de impresión (vía `PosNetworkPrinterController`, ver
    # controllers/main.py).
    escpos_printer_ip = fields.Char(
        string="IP de impresora de red (ESC/POS)",
        help="Dirección IP o nombre de host de una impresora térmica ESC/POS "
             "genérica conectada a la misma red que el POS (no Epson: use el "
             "campo nativo 'Epson Printer IP' de Odoo para esas).",
    )
    escpos_printer_port = fields.Char(
        string="Puerto de impresora de red (ESC/POS)",
        default="9100",
        help="Puerto TCP de la impresora ESC/POS. 9100 es el puerto estándar "
             "RAW/JetDirect usado por la gran mayoría de impresoras térmicas.",
    )

    # Interruptor explícito entre "backend" (comportamiento de siempre,
    # on-premise) y "agent" (Camino A/B vía agent/al_pos_local_agent.py,
    # ver agent/README.md). Antes esto se inferia de
    # si `escpos_agent_url` tenía algo cargado — funcionaba, pero obligaba a
    # vaciar/rellenar ese campo cada vez que se quería probar el agente en
    # local y volver atrás, perdiendo el valor. Con un campo propio, la
    # URL/token/canal pueden quedar siempre completos y este campo es el
    # único que decide cuál camino se usa — pensado sobre todo para poder
    # alternar y probar el agente contra una instancia local sin tocar el
    # resto de la configuración.
    escpos_printer_mode = fields.Selection(
        [("backend", "Backend de Odoo (por defecto)"), ("agent", "Agente local")],
        string="Método de impresión ESC/POS",
        default="backend",
        help="'Backend de Odoo': el servidor le habla directo a la "
             "impresora — lo normal en una instalación on-premise. 'Agente "
             "local': el ticket (navegador) y los comprobantes del backend "
             "se mandan al agente standalone configurado abajo en vez de "
             "hablarle directo a la impresora — necesario cuando el "
             "servidor Odoo no tiene ruta de red hacia la impresora (ej. "
             "Odoo.sh), o para probar el agente sin perder esta "
             "configuración. "
             "IMPORTANTE: después de guardar este cambio hay que recargar "
             "(F5) o volver a entrar a la pestaña del POS que ya estaba "
             "abierta — el objeto impresora del navegador se arma una sola "
             "vez al cargar esa pestaña (afterProcessServerData, igual que "
             "la impresora Epson del core), así que sigue usando el modo "
             "viejo hasta que se recargue, aunque el ticket normal siga "
             "saliendo igual por la impresora (por eso puede parecer que "
             "\"no cambió nada\").",
    )

    # Toggle amigable para 2 campos del core (`iface_print_auto` +
    # `iface_print_skip_screen`) que hay que activar JUNTOS para que el
    # ticket salga solo sin que el cajero toque nada — ver `nextPage`/
    # `canPrintReceipt` en
    # `point_of_sale/static/src/app/utils/order_payment_validation.js`:
    # con los 2 en True, el pago va directo a FeedbackScreen e imprime sin
    # preguntar; si `iface_print_auto` es False, no importa el valor del
    # otro, vuelve el flujo normal (ReceiptScreen, imprimir a mano). No es
    # un campo propio de este módulo en el sentido de que dependa de
    # `escpos_printer_mode`/IP — aplica igual con cualquier impresora
    # (Epson, IoT, ESC/POS de red), `compute`+`inverse` en vez de un campo
    # `related` simple porque hace falta tocar los 2 campos del core a la
    # vez desde un solo toggle. `store=False` (default): no hace falta
    # buscar/agrupar por esto, es un atajo de UI, no un dato propio.
    escpos_auto_print = fields.Boolean(
        string="Imprimir automáticamente al pagar",
        compute="_compute_escpos_auto_print",
        inverse="_inverse_escpos_auto_print",
        help="Al marcar y GUARDAR: Odoo imprime el ticket solo, apenas se "
             "confirma el pago, sin que el cajero tenga que tocar nada "
             "(activa 'Automatic Receipt Printing' + 'Skip Preview "
             "Screen' del core — pasa directo a la pantalla de feedback). "
             "Al desmarcar y guardar: vuelve el proceso normal (pantalla "
             "de recibo, impresión manual). Requiere alguna impresora ya "
             "configurada (ESC/POS de red, Epson, o IoT Box) — sin "
             "ninguna, el navegador va a intentar imprimir igual con su "
             "diálogo nativo.",
    )

    def _compute_escpos_auto_print(self):
        for config in self:
            config.escpos_auto_print = config.iface_print_auto

    def _inverse_escpos_auto_print(self):
        for config in self:
            config.iface_print_auto = config.escpos_auto_print
            config.iface_print_skip_screen = config.escpos_auto_print

    # Cola de reintento en background (ver
    # controllers/main.py::_enqueue_escpos_retry) — opt-in, inactiva por
    # defecto. Aunque el módulo ya trae `queue_job` como dependencia dura
    # (necesaria para que el mecanismo exista), encolar un job por cada
    # ticket que falla es un cambio de comportamiento real (el fallo ya no
    # termina ahí, reintenta solo por un rato) que un administrador podría
    # no querer sin haberlo decidido explícitamente — mismo criterio que ya
    # usa `escpos_require_agent_authorization` para otro opt-in de este
    # módulo. Solo aplica al modo "backend" (ver `escpos_printer_mode`): en
    # modo "agent" el backend nunca ve el fallo, así que este campo no
    # tiene nada que hacer ahí — la vista lo oculta en ese caso.
    escpos_retry_queue_enabled = fields.Boolean(
        string="Reintentar impresión fallida en segundo plano",
        default=False,
        help="Si la impresión falla (impresora apagada, sin papel, red "
             "caída un momento) tras el reintento inmediato del backend, "
             "encola un trabajo que reintenta solo, con espaciado "
             "creciente, hasta que la impresora vuelva a responder — sin "
             "depender de que el cajero note o reintente el popup nativo "
             "de impresión. Inactivo por defecto: un fallo se comporta "
             "igual que siempre (solo el popup de reintento manual). Solo "
             "aplica con método de impresión 'Backend de Odoo'.",
    )

    # Camino A del agente local (ver
    # agent/README.md, Camino A) — para cuando el
    # backend de Odoo NO tiene ruta de red hacia la impresora (Odoo.sh, o
    # cualquier hosting fuera de la LAN del local): en vez de que el
    # navegador le mande el ticket al backend (que no podría reenviarlo a la
    # impresora), le habla directo a un agente HTTP standalone que sí está
    # en esa red (ver agent/al_pos_local_agent.py). Vacío por defecto —
    # con eso, el módulo sigue funcionando exactamente igual que hasta
    # ahora, sin agente, hablando siempre por el backend.
    escpos_agent_url = fields.Char(
        string="URL del agente local ESC/POS (opcional)",
        help="Si se completa, el ticket se manda directo desde el navegador "
             "del cajero a este agente (ej. http://192.168.0.50:8765) en "
             "vez de pasar por el backend de Odoo — necesario cuando el "
             "servidor Odoo no tiene ruta de red hacia la impresora (ej. "
             "Odoo.sh). Dejar vacío en una instalación on-premise normal: "
             "ahí el backend ya imprime directo, sin necesitar esto.",
    )
    escpos_agent_token = fields.Char(
        string="Token del agente local ESC/POS",
        help="Token compartido que el navegador manda en el header "
             "X-Agent-Token al agente configurado arriba, si el agente "
             "exige uno (AL_AGENT_TOKEN en su configuración). Dejar vacío "
             "si el agente no tiene token configurado.",
    )

    # Camino B del agente local (Fase 2, ver
    # agent/README.md): a diferencia del ticket
    # normal (Camino A, arriba — lo dispara el navegador), un comprobante
    # generado en el servidor lo imprime el propio BACKEND, dentro de un job
    # de queue_job o de la misma request que lo genera — sin
    # ningún navegador de por medio. Ahí no hay forma de que "hable directo"
    # a un agente HTTP como en el Camino A; hace falta que el agente esté
    # escuchando de antemano por un canal saliente (el bus/websocket de
    # Odoo, ver controllers/main.py::print_pdf_bytes)
    # y el backend le publique el trabajo ahí.
    #
    # Generado automáticamente (nunca lo tipea el administrador) con
    # secrets.token_hex(32) — mismo patrón que iot.box.token
    # (ee19/iot/models/iot_box.py::_default_token, ahí con token_hex(16)).
    # Es el secreto real de este canal: bus.bus._sendone() advierte
    # explícito que el "target" no debe ser adivinable por un atacante — acá
    # se usa el doble de bytes que el ejemplo oficial porque no hay ninguna
    # razón real para ahorrar en esto.
    escpos_agent_channel = fields.Char(
        string="Canal del agente local (bus, Camino B)",
        default=lambda self: secrets.token_hex(32),
        copy=False,
        readonly=True,
        help="Canal secreto del bus de Odoo que usa el agente local para "
             "recibir los comprobantes que imprime el backend cuando este "
             "no tiene ruta de red directa hacia la impresora (Odoo.sh). "
             "Generado solo, no se edita a mano — usar el botón "
             "'Regenerar canal' si se sospecha que se filtró.",
    )

    # Interruptor del diálogo bloqueante "Autorizar conexión con la
    # impresora" (ver static/src/overrides/services/pos_store.js::pay()) —
    # inactivo por defecto. Se agregó en vivo (2026-09-15, en una prueba en
    # Odoo.sh) porque mientras se termina de ajustar el agente
    # por HTTPS del lado del local (certificado, Private/Local Network
    # Access, CORS — ver agent/README.md §Problemas conocidos), el gate bloqueaba el cobro
    # aunque el ticket en sí no dependiera de eso para nada (backend
    # directo, o Camino A ya andando pero el chequeo previo todavía no).
    # Con esto en `False` el pago sigue exactamente como antes de que
    # existiera el diálogo (comportamiento histórico del módulo); activarlo
    # una vez confirmado que el agente por HTTPS autoriza bien de punta a
    # punta, para volver a exigirlo antes de cada cobro.
    escpos_require_agent_authorization = fields.Boolean(
        string="Bloquear pago hasta autorizar el agente",
        default=False,
        help="Con el método de impresión en 'Agente local' por HTTPS, exige "
             "confirmar que el navegador puede contactar al agente ANTES de "
             "dejar pagar (evita cobrar y recién ahí enterarse de que el "
             "ticket no va a salir). Inactivo por defecto: el pago sigue "
             "igual que siempre, sin este chequeo previo — el ticket se "
             "intenta imprimir igual al final, y si el agente no responde "
             "ahí se ve el error, como antes de que existiera este diálogo.",
    )

    def write(self, vals):
        # Si el TPV deja de imprimir en modo "backend" contra un destino
        # (cambia a "agent", o cambia de IP/puerto mientras sigue en
        # "backend"), el backend tiene que soltar la conexión persistente
        # que tenía abierta ahí — confirmado en vivo (2026-09-09): sin
        # esto, esa conexión (con su hilo de keep-alive) queda viva para
        # siempre en el proceso de Odoo y compite con la conexión nueva
        # del agente por el único socket que la mayoría de las térmicas
        # ESC/POS acepta a la vez ("Connection reset by peer" del lado del
        # agente, aunque el backend nunca reportó ningún error porque su
        # propio reintento de keep-alive sí seguía reconectando bien).
        stale_targets = set()
        if {"escpos_printer_mode", "escpos_printer_ip", "escpos_printer_port"} & vals.keys():
            for config in self:
                if config.escpos_printer_ip and config.escpos_printer_mode == "backend":
                    stale_targets.add(
                        (config.escpos_printer_ip, config.escpos_printer_port or "9100")
                    )
        res = super().write(vals)
        for host, port in stale_targets:
            still_used = self.env["pos.config"].sudo().search_count([
                ("escpos_printer_ip", "=", host),
                ("escpos_printer_port", "=", port),
                ("escpos_printer_mode", "=", "backend"),
            ], limit=1)
            if not still_used:
                release_connection(host, int(port))
        return res

    def action_test_escpos_printer(self):
        """Botón "Probar impresora" (ver `views/pos_config_view.xml`) —
        imprime un ticket de texto real para confirmar que el backend de
        Odoo puede alcanzar la impresora configurada.

        Solo aplica con `escpos_printer_mode == "backend"`: en modo
        "Agente local" el backend de Odoo NO tiene ruta de red hacia la
        impresora (esa es la razón de ser del agente — ver
        `escpos_printer_mode` más arriba), así que no hay forma de que
        este botón imprima de verdad desde acá. Para ese modo ya existe
        "Probar agente" (`TestEscposAgent`, más abajo en la vista), que
        confirma que el agente responde — la impresión real de prueba en
        ese caso la hace la GUI standalone del agente (botón "Test de
        conexión", `agent/al_pos_local_agent_gui.py`).
        """
        self.ensure_one()
        if self.escpos_printer_mode != "backend":
            raise ValidationError(
                "El método de impresión está en 'Agente local' — use el "
                "botón 'Probar agente' de más abajo para confirmar que el "
                "agente responde. El backend de Odoo no tiene ruta de red "
                "directa a la impresora en ese modo (por eso existe el "
                "agente)."
            )
        if not self.escpos_printer_ip:
            raise ValidationError("Configure primero la IP de la impresora ESC/POS de red.")
        port = int(self.escpos_printer_port or 9100)
        lines = [
            self.env.company.name,
            self.name,
            fields.Datetime.to_string(fields.Datetime.now()),
            f"{self.escpos_printer_ip}:{port}",
            "-" * 32,
            "Si ve este ticket, la conexion",
            "backend -> impresora funciona.",
        ]
        try:
            print_test_ticket(self.escpos_printer_ip, port, lines)
        except UserError:
            # Ya viene con un mensaje claro y accionable (ej. "falta
            # instalar python-escpos") — no lo re-envolvemos.
            raise
        except Exception as exc:
            raise ValidationError(
                f"No se pudo imprimir en {self.escpos_printer_ip}:{port} — "
                f"{exc}. Revise que la impresora esté encendida, en la "
                "misma red que el servidor Odoo, y que el puerto sea el "
                "correcto."
            ) from exc
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Ticket de prueba enviado",
                "message": f"Revise la impresora en {self.escpos_printer_ip}:{port}.",
                "type": "success",
                "sticky": False,
            },
        }

    def action_regenerate_escpos_agent_channel(self):
        """Rotación manual del canal — ver el campo de arriba. Cualquier
        agente que siga conectado con el canal viejo deja de recibir nada
        apenas se guarda esto (tiene que reconfigurarse con el nuevo valor
        y reconectar)."""
        for config in self:
            config.escpos_agent_channel = secrets.token_hex(32)

    def _escpos_retry_print_receipt_job(self, ip, port, img_b64):
        """Cuerpo del job de `queue_job` encolado por
        `controllers/main.py::_enqueue_escpos_retry` cuando este PDV es el
        recibo principal que falló al imprimir — delega en
        `retry_print_receipt`, ver su docstring para la lógica real (acá
        solo hace falta el `self` porque `queue_job` siempre encola sobre
        un recordset, nunca una función suelta)."""
        self.ensure_one()
        retry_print_receipt(self.env, ip, port, img_b64)

    def _escpos_receipt_printer_active(self):
        """True si este PDV imprime su recibo principal en la impresora
        ESC/POS de red: el toggle "Impresora ESC/POS de red" activo Y una IP
        cargada. Único criterio para todo el módulo (y para los módulos que
        impriman por aquí): con el toggle apagado la IP/puerto/modo
        pueden quedar guardados, pero el PDV imprime como en el nativo
        (Epson/IoT si están configurados, si no el diálogo del navegador).
        Antes bastaba con que hubiera IP — apagar el toggle solo ocultaba la
        sección y el PDV seguía mandando todo a la impresora de red (pedido
        en vivo 2026-09-28). El espejo en el POS está en
        static/src/overrides/services/pos_store.js::afterProcessServerData.
        """
        self.ensure_one()
        return bool(self.escpos_network_printer_enabled and self.escpos_printer_ip)

    @api.constrains("epson_printer_ip", "escpos_printer_ip", "escpos_network_printer_enabled")
    def _check_single_receipt_printer_backend(self):
        # Si se configuran ambos campos a la vez, el POS igual tendría que
        # elegir uno solo para el recibo principal (ver la rama nueva en
        # `afterProcessServerData`, static/src/overrides/services/pos_store.js).
        # Es más seguro prohibir la ambigüedad de plano que resolverla en
        # silencio con una prioridad implícita que el administrador no vería
        # reflejada en la UI.
        # Solo cuenta la ESC/POS si está ACTIVA: con el toggle apagado se
        # puede usar Epson aunque la IP de la ESC/POS siga guardada.
        for config in self:
            if config.epson_printer_ip and config._escpos_receipt_printer_active():
                raise ValidationError(
                    "Configure solo una impresora de recibo principal: Epson "
                    "(ePOS) o una impresora ESC/POS genérica de red, no ambas "
                    "a la vez."
                )

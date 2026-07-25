from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class ResUsers(models.Model):
    _inherit = "res.users"

    # Vista de productos del TPV preferida por cajero. Si está vacía, el
    # frontend del TPV usa `pos.config.default_product_view`. Se puede fijar
    # desde las Preferencias del usuario (backend) o automáticamente desde
    # el conmutador del frontend del TPV, lo que ocurra último.
    pos_product_view_mode = fields.Selection(
        selection=[
            ("grid", "Cuadrícula"),
            ("list", "Lista"),
        ],
        string="Vista de productos del TPV",
        help=(
            "Vista de productos preferida por este usuario en la interfaz "
            "del TPV. Dejar vacío para usar el valor por defecto de la "
            "configuración del TPV. Se actualiza automáticamente cuando el "
            "usuario cambia de vista desde la pantalla del TPV."
        ),
    )

    # --- Exposición de datos al frontend -----------------------------------
    @api.model
    def _load_pos_data_fields(self, config):
        # Añade nuestro campo a la pequeña lista blanca que
        # `point_of_sale.models.res_users` envía al frontend del TPV.
        return super()._load_pos_data_fields(config) + ["pos_product_view_mode"]

    # --- Setter seguro invocable desde el frontend del TPV ------------------
    def set_pos_product_view_mode(self, mode):
        """Persiste la vista de productos del TPV preferida por el usuario.

        Los cajeros normalmente no tienen permiso de escritura sobre
        `res.users`, así que usamos `sudo()` tras verificar que la llamada
        apunta SOLO al registro del propio usuario que llama. Esto mantiene
        la superficie de ataque mínima y aun así permite que el botón
        conmutador persista entre sesiones.
        """
        if mode not in ("grid", "list"):
            return False
        # Defensivo: solo se permite la automodificación.
        if self.ids != [self.env.uid]:
            raise AccessError(_("Solo puedes cambiar tu propia preferencia de vista del TPV."))
        self.sudo().write({"pos_product_view_mode": mode})
        return True

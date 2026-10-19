# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    pharmacy_care_reminder_days = fields.Integer(
        string='Recordar recompra con', default=5,
        help='Días antes de que se acabe el tratamiento en que se recuerda la recompra.')
    pharmacy_care_send_email = fields.Boolean(
        string='Correo de recompra al paciente',
        help='Además de la actividad del responsable, envía un correo al paciente.')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pharmacy_care_reminder_days = fields.Integer(
        related='company_id.pharmacy_care_reminder_days', readonly=False)
    pharmacy_care_send_email = fields.Boolean(
        related='company_id.pharmacy_care_send_email', readonly=False)

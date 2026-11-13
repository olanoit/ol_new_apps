# -*- coding: utf-8 -*-
from odoo import models


class IrModelFields(models.Model):
    _inherit = 'ir.model.fields'

    # Buscar un campo también por su nombre técnico (p. ej. "email"), como
    # ir.model con el nombre del modelo. Lo usan los selectores de campos de
    # las restricciones por rol, que muestran solo la etiqueta.
    _rec_names_search = ['field_description', 'name']

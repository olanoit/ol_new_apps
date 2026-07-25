# -*- coding: utf-8 -*-
"""Modelo transient para listar hojas detectadas dentro de un Excel.

Se usa como destino de un ``Many2one`` en cada wizard que herede de
``al.import.payroll.mixin``. Cada registro representa una hoja del libro
cargado y queda ligado al wizard concreto por ``res_model`` + ``res_id``.
"""
from odoo import fields, models


class ImportPayrollSheet(models.TransientModel):
    _name = 'al.import.payroll.sheet'
    _description = 'Hoja candidata para asistentes de importación'
    _order = 'sequence, id'

    name = fields.Char(string='Nombre de hoja', required=True)
    sequence = fields.Integer(default=10)
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)

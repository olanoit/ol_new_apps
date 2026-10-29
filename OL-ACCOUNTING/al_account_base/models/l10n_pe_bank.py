# -*- coding: utf-8 -*-
from odoo import fields, models


class L10nPeBank(models.Model):
    """Banco (entidad financiera).

    Odoo 20 retiró ``res.bank``: el banco es un texto de la cuenta bancaria.
    La suite necesita identificar el banco para lo que depende de él (formato
    de pago masivo, plantillas de cobranza y cheques, tesorería), así que lo
    lleva en este catálogo, enlazado desde ``res.partner.bank``."""
    _name = 'l10n_pe.bank'
    _description = 'Banco'
    _order = 'sequence, name'

    name = fields.Char(string='Nombre', required=True)
    bic = fields.Char(string='Código BIC/SWIFT')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    # Banco de origen al actualizar desde 19 (res.bank), para traducir los
    # datos que otros módulos guardaban por banco.
    legacy_res_bank_id = fields.Integer(readonly=True, copy=False, index=True)

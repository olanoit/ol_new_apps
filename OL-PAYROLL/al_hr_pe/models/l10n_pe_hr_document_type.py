# -*- coding: utf-8 -*-
"""Tipo de documento de identidad del trabajador y del derechohabiente.

Odoo 20 retiró ``l10n_latam_base`` (y con él ``l10n_latam.identification.type``,
donde se colgaban los códigos de planilla): en los contactos el documento es
ahora un identificador de ``res.partner.additional_identifiers``. El empleado
no tiene equivalente nativo, así que el tipo de documento queda en este
catálogo, enlazado con la clave del identificador de Odoo (``code``).
"""
from odoo import fields, models


class L10nPeHrDocumentType(models.Model):
    _name = 'l10n_pe.hr.document.type'
    _description = 'Tipo de documento (planillas)'
    _order = 'sequence, id'

    name = fields.Char(string='Nombre', required=True, translate=True)
    code = fields.Char(
        string='Identificador de Odoo', required=True,
        help='Clave del identificador en los contactos (PE_DNI, PE_CE, '
             'PASSPORT…). El RUC es PE_RUC.')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    l10n_pe_hr_sunat_code = fields.Char(
        string='Código SUNAT (planillas)',
        help='Código del tipo de documento en la planilla electrónica '
             'PLAME.')
    l10n_pe_hr_afp_code = fields.Char(
        string='Código AFP',
        help='Código del tipo de documento en AFPNet.')

    _code_uniq = models.Constraint(
        'UNIQUE(code)', 'Ya existe un tipo de documento con ese identificador.')

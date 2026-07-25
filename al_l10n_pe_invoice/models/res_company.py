# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    represent_id = fields.Many2one(
        comodel_name='res.partner',
        string='Representante',
        # is_company (almacenado), no company_type: en v19 company_type es un
        # compute sin search y el name_search del widget rompe con
        # "Cannot convert res.partner.company_type to SQL".
        domain=[('is_company', '=', False)],
        help='Persona cuya firma aparece en el bloque de firmas del reporte de comprobantes.',
    )
    represent_dni = fields.Char(string='DNI', related='represent_id.vat')
    company_eslogan_pdf = fields.Text(
        string='Eslogan',
        help='Texto mostrado bajo los datos de la compañía en el reporte de comprobantes.',
    )
    active_fep_signatures = fields.Boolean(
        string='Activar firmas',
        help='Muestra el bloque de firma y "recibido conforme" en el reporte A4 de comprobantes.',
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    active_fep_signatures = fields.Boolean(
        related='company_id.active_fep_signatures', readonly=False)
    company_eslogan_pdf = fields.Text(
        related='company_id.company_eslogan_pdf', readonly=False)
    represent_id = fields.Many2one(
        related='company_id.represent_id', readonly=False)

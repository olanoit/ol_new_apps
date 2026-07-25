# -*- coding: utf-8 -*-
"""Configuración del fotocheck (carné de identificación del personal).

Port de ``hr_fotocheck_config.py`` v18. Se mantiene el nombre técnico
``hr.fotocheck.config`` para poder migrar los datos v18 sin renombrar
tablas. Cambios v19:

* Una configuración por compañía (constraint UNIQUE): el reporte toma
  la configuración de la compañía del empleado — el v18 hacía
  ``search([], limit=1)`` y en multicompañía imprimía los logos de
  otra empresa.
* El fondo del anverso sale del binario ``fondo_front`` (el v18 lo
  ignoraba y usaba una imagen estática hardcodeada del módulo).
"""
from odoo import api, fields, models


class HrFotocheckConfig(models.Model):
    _name = 'hr.fotocheck.config'
    _description = 'Configuración de fotocheck'
    _order = 'company_id'

    name = fields.Char(
        string='Nombre', default='Configuración de fotocheck',
        required=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    # Logos de certificaciones (ISO, homologaciones, etc.) que se
    # imprimen en la franja superior del anverso.
    logo_cert_1 = fields.Binary(string='Logo certificado 1')
    logo_cert_2 = fields.Binary(string='Logo certificado 2')
    logo_cert_3 = fields.Binary(string='Logo certificado 3')
    logo_cert_4 = fields.Binary(string='Logo certificado 4')
    logo_cert_5 = fields.Binary(string='Logo certificado 5')

    fondo_front = fields.Binary(
        string='Imagen de fondo (anverso)',
        help='Fondo completo de la cara frontal del carné.')
    backimg = fields.Binary(
        string='Imagen de reverso',
        help='Imagen a página completa de la cara posterior.')

    _company_uniq = models.Constraint(
        'UNIQUE(company_id)',
        'Ya existe una configuración de fotocheck para esa compañía.')

    @api.model
    def _get_for_company(self, company):
        """Configuración de la compañía dada (para el QWeb del carné)."""
        return self.search([('company_id', '=', company.id)], limit=1)

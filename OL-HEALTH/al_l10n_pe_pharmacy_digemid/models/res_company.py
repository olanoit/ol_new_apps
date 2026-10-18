# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    pharmacy_establishment_category = fields.Selection([
        ('pharmacy', 'Farmacia'),
        ('drugstore', 'Botica'),
    ], string='Tipo de establecimiento',
        help='Farmacia: de propiedad de un químico farmacéutico. Botica: de otro propietario.')
    pharmacy_authorization_number = fields.Char(string='Autorización sanitaria')
    pharmacy_authorization_date = fields.Date(string='Fecha de la autorización')
    pharmacy_microenterprise = fields.Boolean(
        string='Microempresa',
        help='Las microempresas están exceptuadas del 30 % de genéricos (Ley 32033).')
    pharmacy_adverse_event_days = fields.Integer(
        string='Plazo de reacciones no graves (días)', default=15,
        help='BPOF 7.5.3.12 indica 15 días calendario; las graves, 24 horas.')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pharmacy_establishment_category = fields.Selection(
        related='company_id.pharmacy_establishment_category', readonly=False)
    pharmacy_authorization_number = fields.Char(
        related='company_id.pharmacy_authorization_number', readonly=False)
    pharmacy_authorization_date = fields.Date(
        related='company_id.pharmacy_authorization_date', readonly=False)
    pharmacy_microenterprise = fields.Boolean(
        related='company_id.pharmacy_microenterprise', readonly=False)
    pharmacy_adverse_event_days = fields.Integer(
        related='company_id.pharmacy_adverse_event_days', readonly=False)

# -*- coding: utf-8 -*-
from odoo import fields, models


class HrMembership(models.Model):
    """Afiliación previsional (AFP/ONP) con sus tasas vigentes.

    Cambio de diseño vs v18: allí ``company_id`` era requerido y un wizard
    duplicaba las AFP en cada compañía (las tasas divergían y había que
    mantenerlas N veces). Las tasas AFP/ONP las fija la SBS — son
    nacionales — así que en v19 los registros son globales (override por
    compañía posible) y lo único realmente por compañía, la cuenta
    contable, es ``company_dependent``.
    """
    _name = 'hr.membership'
    _description = 'Afiliación (AFP/ONP)'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(string='Entidad', tracking=True, required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', index=True,
        help='Vacío: entidad global (tasas SBS compartidas). Con '
             'compañía: override propio.')
    fixed_commision = fields.Float(string='Comisión sobre flujo %', tracking=True)
    mixed_commision = fields.Float(string='Comisión mixta %', tracking=True)
    prima_insurance = fields.Float(string='Prima de seguros %', tracking=True)
    retirement_fund = fields.Float(string='Aporte fondo de pensiones %', tracking=True)
    insurable_remuneration = fields.Float(
        string='Remuneración máxima asegurable', tracking=True,
        help='Tope sobre el que se calcula la prima de seguro (lo publica '
             'la SBS trimestralmente).')
    account_id = fields.Many2one(
        'account.account', string='Cuenta contable',
        company_dependent=True,
        help='Cuenta del pasivo por aportes a esta entidad. Es por '
             'compañía: cada una configura la suya sobre el registro '
             'global.')
    is_afp = fields.Boolean(string='Es AFP', default=False, tracking=True)

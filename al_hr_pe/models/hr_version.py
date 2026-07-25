# -*- coding: utf-8 -*-
from odoo import api, fields, models

# En v18 estos campos vivían en hr.contract; en v19 el contrato se fusionó
# en hr.version (versionado del empleado), así que la localización cuelga
# de aquí. Los M2O a catálogos globales no llevan check_company (patrón
# global-or-own; la regla de seguridad acota lo visible).


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_pe_labor_regime = fields.Selection(
        selection=[
            ('general', 'Régimen general'),
            ('small', 'Pequeña empresa'),
            ('micro', 'Microempresa'),
            ('practicante', 'Practicante'),
            ('construccion', 'Construcción civil'),
        ],
        string='Régimen laboral (PE)', default='general', tracking=True,
        help='Régimen laboral peruano: determina divisores de CTS y '
             'gratificación (p. ej. pequeña empresa computa /24 y /12) y '
             'derechos del trabajador.')
    l10n_pe_cuspp = fields.Char(
        string='CUSPP', size=12, tracking=True,
        help='Código Único del Sistema Privado de Pensiones del afiliado '
             '(AFP). Vacío para afiliados a ONP.')
    l10n_pe_commission_type = fields.Selection(
        selection=[('flow', 'Comisión sobre flujo'),
                   ('mixed', 'Comisión mixta')],
        string='Tipo de comisión AFP (PE)', default='flow', tracking=True,
        help='Esquema de comisión del afiliado AFP: sobre la remuneración '
             '(flujo) o mixta (flujo + saldo).')
    membership_id = fields.Many2one(
        'hr.membership', string='Afiliación (AFP/ONP)', tracking=True,
        help='Entidad previsional del trabajador.')
    is_afp = fields.Boolean(related='membership_id.is_afp')
    social_insurance_id = fields.Many2one(
        'hr.social.insurance', string='Seguro social', tracking=True,
        help='EsSalud / EPS del trabajador (determina la tasa del aporte '
             'del empleador y del bono extraordinario de gratificación).')
    worker_type_id = fields.Many2one(
        'hr.worker.type', string='Tipo de trabajador (T08)', tracking=True)
    situation_id = fields.Many2one(
        'hr.situation', string='Situación (T15)', tracking=True)
    situation_code = fields.Char(
        related='situation_id.code', string='Código de situación')
    situation_reason_id = fields.Many2one(
        'hr.reasons.leave', string='Motivo de baja (T17)', tracking=True)
    contributions_ids = fields.Many2many(
        'hr.contributions', string='Aportes adicionales',
        help='Aportes del empleador aplicables a este trabajador '
             '(p. ej. SENATI, SCTR).')
    l10n_pe_less_than_four = fields.Boolean(
        string='Empleador con menos de 4 trabajadores')
    l10n_pe_other_employers = fields.Boolean(
        string='Ingresos de otros empleadores',
        help='Percibe rentas de 5ta de otro empleador (afecta la '
             'proyección de renta anual).')
    l10n_pe_is_older = fields.Boolean(
        string='Mayor de 65 años', compute='_compute_l10n_pe_is_older',
        help='Los mayores de 65 no aportan prima de seguro AFP sobre el '
             'tope asegurable.')
    l10n_pe_exception = fields.Selection(
        selection=[
            ('L', 'L — Trabajador de dirección'),
            ('U', 'U — Sin fiscalización inmediata'),
            ('J', 'J — Jornada reducida'),
            ('I', 'I — Tiempo parcial'),
            ('P', 'P — Servicio intermitente'),
            ('O', 'O — Otros'),
        ],
        string='Excepción de jornada (PLAME)')
    l10n_pe_work_type = fields.Selection(
        selection=[
            ('N', 'N — Normal'),
            ('C', 'C — Confianza'),
            ('M', 'M — Minero'),
            ('P', 'P — Pesquero'),
        ],
        string='Tipo de labor (PLAME)', default='N')

    @api.depends('employee_id.birthday', 'date_version')
    def _compute_l10n_pe_is_older(self):
        for version in self:
            birthday = version.employee_id.birthday
            ref = version.date_version or fields.Date.today()
            version.l10n_pe_is_older = bool(
                birthday
                and (ref.year - birthday.year
                     - ((ref.month, ref.day) < (birthday.month, birthday.day))
                     ) >= 65)

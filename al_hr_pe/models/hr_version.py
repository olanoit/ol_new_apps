# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

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

    # ------------------------------------------------------------------
    # T-Registro — estructura 05 «Datos del trabajador»
    # Los códigos son los del Anexo 2 de la Planilla Electrónica; los
    # catálogos largos van a tablas propias y los cortos a selecciones
    # cuya clave ES el código SUNAT (así el exportador no traduce nada).
    # ------------------------------------------------------------------
    l10n_pe_labor_regime_id = fields.Many2one(
        'l10n_pe.hr.labor.regime', string='Régimen laboral (T33)',
        tracking=True,
        help='Régimen laboral tal como lo codifica SUNAT. Al elegirlo se '
             'ajusta la familia de cálculo de CTS, gratificación y '
             'vacaciones.')
    l10n_pe_education_level_id = fields.Many2one(
        'l10n_pe.hr.education.level', string='Situación educativa (T09)',
        help='Obligatorio en el T-Registro. Si es superior completa, SUNAT '
             'pide además los datos de estudios concluidos (estructura 29).')
    l10n_pe_occupation_id = fields.Many2one(
        'l10n_pe.hr.occupation', string='Ocupación (T30)',
        help='Ocupación del trabajador según la tabla de SUNAT. Las '
             'disponibles dependen de la categoría ocupacional.')
    l10n_pe_occupational_category_id = fields.Many2one(
        'l10n_pe.hr.occupational.category',
        string='Categoría ocupacional (T24)')
    l10n_pe_contract_type_id = fields.Many2one(
        'l10n_pe.hr.contract.type', string='Tipo de contrato (T12)',
        tracking=True)
    l10n_pe_disability = fields.Boolean(
        string='Tiene discapacidad',
        help='Ley 29973: da derecho a la cuota de empleo y a la deducción '
             'adicional del impuesto a la renta del empleador.')
    l10n_pe_sctr_pension = fields.Boolean(
        string='Cobertura SCTR pensión',
        help='Trabajador en actividad de riesgo del Anexo 5 del '
             'D.S. 009-97-SA con cobertura de pensión por el SCTR.')
    l10n_pe_alternative_schedule = fields.Boolean(
        string='Sujeto a régimen alternativo',
        help='Jornada acumulativa, atípica o compensatoria '
             '(art. 4 del D.S. 007-2002-TR).')
    l10n_pe_max_working_day = fields.Boolean(
        string='Sujeto a jornada máxima', default=True,
        help='Desmarcar para el personal de dirección, sin fiscalización '
             'inmediata o de servicio intermitente.')
    l10n_pe_night_shift = fields.Boolean(
        string='Sujeto a horario nocturno',
        help='Trabajo entre las 22:00 y las 06:00: la remuneración no '
             'puede ser menor a la RMV más una sobretasa del 35 %.')
    l10n_pe_unionized = fields.Boolean(string='Es sindicalizado')
    l10n_pe_fifth_income = fields.Boolean(
        string='Percibe rentas de 5ta categoría', default=True)
    l10n_pe_pay_periodicity = fields.Selection(
        selection=[('1', '1 — Mensual'), ('2', '2 — Quincenal'),
                   ('3', '3 — Semanal'), ('4', '4 — Diaria'),
                   ('5', '5 — Otros')],
        string='Periodicidad de la remuneración (T13)', default='1')
    l10n_pe_payment_type = fields.Selection(
        selection=[('1', '1 — Efectivo'), ('2', '2 — Depósito en cuenta'),
                   ('3', '3 — Otros')],
        string='Tipo de pago (T16)', default='2')
    l10n_pe_special_situation = fields.Selection(
        selection=[
            ('0', '0 — Ninguna'),
            ('1', '1 — Dirección, presencial'),
            ('2', '2 — Confianza, presencial'),
            ('3', '3 — Dirección, teletrabajo mixto'),
            ('4', '4 — Confianza, teletrabajo mixto'),
            ('5', '5 — Dirección, teletrabajo completo'),
            ('6', '6 — Confianza, teletrabajo completo'),
            ('7', '7 — Teletrabajo mixto'),
            ('8', '8 — Teletrabajo completo'),
        ],
        string='Situación especial (T35)', default='0')
    l10n_pe_double_taxation = fields.Selection(
        selection=[('0', '0 — Ninguno'), ('1', '1 — Canadá'),
                   ('2', '2 — Chile'), ('3', '3 — CAN'),
                   ('4', '4 — Brasil'), ('5', '5 — México'),
                   ('6', '6 — Corea'), ('7', '7 — Suiza'),
                   ('8', '8 — Portugal')],
        string='Convenio de doble tributación (T25)', default='0')
    l10n_pe_cas_vat = fields.Char(
        string='RUC del trabajador (CAS)', size=11,
        help='Solo para el régimen CAS (tipo de trabajador 67).')

    @api.onchange('l10n_pe_labor_regime_id')
    def _onchange_l10n_pe_labor_regime_id(self):
        """El régimen SUNAT fija la familia de cálculo (eco en el formulario).

        Se mantienen los dos campos a propósito: SUNAT distingue 27
        regímenes y el motor de beneficios solo necesita cinco familias
        (los divisores de CTS, gratificación y vacaciones).
        """
        for version in self:
            if version.l10n_pe_labor_regime_id:
                version.l10n_pe_labor_regime = (
                    version.l10n_pe_labor_regime_id.regime_kind)

    @api.model
    def _l10n_pe_sync_regime_vals(self, vals):
        """Propaga el régimen SUNAT a la familia de cálculo.

        El ``onchange`` solo actúa en el formulario: sin esto, un ``write``
        desde código o desde el importador Excel dejaría la familia de
        cálculo desincronizada y la CTS saldría con el divisor de otro
        régimen. Si el llamador fija ambos campos, respeta lo que pidió.
        """
        regime_id = vals.get('l10n_pe_labor_regime_id')
        if regime_id and 'l10n_pe_labor_regime' not in vals:
            regime = self.env['l10n_pe.hr.labor.regime'].browse(regime_id)
            if regime.regime_kind:
                vals = dict(vals, l10n_pe_labor_regime=regime.regime_kind)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(
            [self._l10n_pe_sync_regime_vals(vals) for vals in vals_list])

    def write(self, vals):
        return super().write(self._l10n_pe_sync_regime_vals(vals))

    @api.onchange('l10n_pe_occupational_category_id')
    def _onchange_l10n_pe_occupational_category_id(self):
        """La ocupación elegida debe seguir siendo válida para la categoría."""
        for version in self:
            occupation = version.l10n_pe_occupation_id
            category = version.l10n_pe_occupational_category_id
            if occupation and category and not occupation._l10n_pe_allowed_for(
                    category):
                version.l10n_pe_occupation_id = False

    @api.constrains('l10n_pe_cas_vat')
    def _check_l10n_pe_cas_vat(self):
        for version in self.filtered('l10n_pe_cas_vat'):
            vat = version.l10n_pe_cas_vat.strip()
            if not (vat.isdigit() and len(vat) == 11):
                raise ValidationError(_(
                    'El RUC del trabajador debe tener 11 dígitos.'))

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

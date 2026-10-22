from odoo import api, fields, models, tools
from odoo.tools import SQL

from .res_partner import HOLD_STATES, RATINGS


class L10nPeCollectionPortfolio(models.Model):
    """Cartera: cada cuota abierta por cobrar con su gestor, zona, atraso y tramo.

    Vista SQL para tablas dinámicas. El gestor y la zona son campos por
    compañía del contacto (jsonb): se toman de la compañía del apunte o, si no
    tiene valor, de su compañía raíz. Las cuentas que no son cobranza
    (anticipos, detracciones) se excluyen en la acción del menú, porque
    dependen de la configuración de cada compañía: el campo ``in_collection``
    las filtra en el menú y en el tablero.
    """
    _name = 'l10n_pe.collection.portfolio'
    _description = 'Cartera por cobrar'
    _auto = False
    _order = 'days_overdue desc, date_maturity'
    # Para que Odoo vuelque estos campos antes de consultar la vista.
    _depends = {
        'account.move.line': [
            'move_id', 'company_id', 'account_id', 'partner_id', 'date', 'date_maturity', 'currency_id',
            'amount_residual', 'amount_residual_currency', 'parent_state', 'reconciled',
            'l10n_pe_collection_in_dispute',
        ],
        'res.partner': [
            'commercial_partner_id', 'followup_responsible_id', 'l10n_pe_collection_zone_id',
            'l10n_pe_collection_rating', 'l10n_pe_collection_hold',
        ],
        'l10n_pe.collection.promise': ['partner_id', 'state', 'date'],
        'l10n_pe.collection.bucket': ['company_id', 'days_from', 'days_to'],
        'l10n_pe.collection.prediction': ['move_line_id', 'predicted_date', 'predicted_delay', 'confidence',
                                          'late_risk'],
    }

    move_line_id = fields.Many2one('account.move.line', string='Apunte', readonly=True)
    move_id = fields.Many2one('account.move', string='Documento', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Cliente', readonly=True)
    user_id = fields.Many2one('res.users', string='Gestor', readonly=True)
    zone_id = fields.Many2one('l10n_pe.collection.zone', string='Zona', readonly=True)
    account_id = fields.Many2one('account.account', string='Cuenta', readonly=True)
    date = fields.Date(string='Emisión', readonly=True)
    date_maturity = fields.Date(string='Vencimiento', readonly=True)
    days_overdue = fields.Integer(string='Días de atraso', readonly=True, aggregator='max')
    bucket_id = fields.Many2one('l10n_pe.collection.bucket', string='Tramo', readonly=True)
    is_overdue = fields.Boolean(string='Vencido', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)
    company_currency_id = fields.Many2one('res.currency', string='Moneda de la compañía', readonly=True)
    amount_residual_currency = fields.Monetary(string='Saldo (moneda)', currency_field='currency_id',
                                               readonly=True, aggregator=None)
    amount_residual = fields.Monetary(string='Saldo', currency_field='company_currency_id', readonly=True)
    in_dispute = fields.Boolean(string='En disputa', readonly=True,
                                help='Documento con un reclamo abierto: fuera del seguimiento.')
    rating = fields.Selection(RATINGS, string='Calificación', readonly=True)
    hold = fields.Selection(HOLD_STATES, string='Bloqueo de crédito', readonly=True)
    promise_date = fields.Date(string='Compromiso', readonly=True,
                               help='Fecha del compromiso de pago pendiente más próximo del cliente.')
    predicted_date = fields.Date(string='Pago previsto', readonly=True,
                                 help='Fecha en que se espera cobrar la cuota según la predicción de pago.')
    predicted_delay = fields.Integer(string='Atraso previsto', readonly=True, aggregator='avg',
                                     help='Días después del vencimiento en que se espera cobrarla.')
    prediction_confidence = fields.Selection([('high', 'Alta'), ('medium', 'Media'), ('low', 'Baja')],
                                             string='Confianza', readonly=True)
    late_risk = fields.Boolean(string='Se atrasará', readonly=True,
                               help='Se espera cobrarla más tarde que el atraso relevante de Ajustes.')
    in_collection = fields.Boolean(string='En cobranza', compute='_compute_in_collection',
                                   search='_search_in_collection',
                                   help='Falso para los anticipos y las detracciones por cobrar.')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(SQL("""
            CREATE OR REPLACE VIEW %s AS (
                -- Hoy en Lima: con el servidor en UTC, CURRENT_DATE adelanta un día
                -- la cartera desde las 19:00 de Perú.
                WITH today AS (SELECT (now() AT TIME ZONE 'America/Lima')::date AS d),
                line AS (
                    SELECT aml.id, aml.move_id, aml.company_id, aml.account_id, aml.date,
                           COALESCE(aml.date_maturity, aml.date) AS date_maturity,
                           aml.currency_id, aml.amount_residual, aml.amount_residual_currency,
                           COALESCE(aml.l10n_pe_collection_in_dispute, FALSE) AS in_dispute,
                           p.commercial_partner_id AS partner_id,
                           split_part(c.parent_path, '/', 1) AS root_key,
                           c.currency_id AS company_currency_id
                      FROM account_move_line aml
                      JOIN account_account acc ON acc.id = aml.account_id
                      JOIN res_partner p ON p.id = aml.partner_id
                      JOIN res_company c ON c.id = aml.company_id
                     WHERE acc.account_type = 'asset_receivable'
                       AND aml.parent_state = 'posted'
                       AND NOT aml.reconciled
                       AND aml.amount_residual != 0
                )
                SELECT line.id, line.id AS move_line_id, line.move_id, line.company_id, line.partner_id,
                       COALESCE(cp.followup_responsible_id ->> line.company_id::text,
                                cp.followup_responsible_id ->> line.root_key)::int AS user_id,
                       COALESCE(cp.l10n_pe_collection_zone_id ->> line.company_id::text,
                                cp.l10n_pe_collection_zone_id ->> line.root_key)::int AS zone_id,
                       line.account_id, line.date, line.date_maturity,
                       ((SELECT d FROM today) - line.date_maturity) AS days_overdue,
                       ((SELECT d FROM today) > line.date_maturity) AS is_overdue,
                       (SELECT b.id FROM l10n_pe_collection_bucket b
                         WHERE (b.company_id IS NULL OR b.company_id::text = line.root_key)
                           AND ((SELECT d FROM today) - line.date_maturity) >= b.days_from
                           AND (COALESCE(b.days_to, 0) = 0 OR ((SELECT d FROM today) - line.date_maturity) <= b.days_to)
                         ORDER BY b.days_from DESC LIMIT 1) AS bucket_id,
                       line.currency_id, line.company_currency_id,
                       line.amount_residual_currency, line.amount_residual, line.in_dispute,
                       COALESCE(cp.l10n_pe_collection_rating ->> line.company_id::text,
                                cp.l10n_pe_collection_rating ->> line.root_key) AS rating,
                       COALESCE(cp.l10n_pe_collection_hold ->> line.company_id::text,
                                cp.l10n_pe_collection_hold ->> line.root_key) AS hold,
                       (SELECT MIN(pr.date) FROM l10n_pe_collection_promise pr
                         WHERE pr.partner_id = line.partner_id AND pr.state = 'pending') AS promise_date,
                       pred.predicted_date, pred.predicted_delay, pred.confidence AS prediction_confidence,
                       COALESCE(pred.late_risk, FALSE) AS late_risk
                  FROM line
                  JOIN res_partner cp ON cp.id = line.partner_id
             LEFT JOIN l10n_pe_collection_prediction pred ON pred.move_line_id = line.id
            )
        """, SQL.identifier(self._table)))

    def _excluded_accounts(self):
        excluded = self.env['account.account']
        for company in self.env.companies:
            excluded |= company._l10n_pe_collection_excluded_accounts()
        return excluded

    def _compute_in_collection(self):
        excluded = self._excluded_accounts()
        for line in self:
            line.in_collection = line.account_id not in excluded

    def _search_in_collection(self, operator, value):
        if operator != 'in':
            return NotImplemented
        excluded = self._excluded_accounts().ids
        if True in value and False in value:
            return []
        return [('account_id', 'not in' if True in value else 'in', excluded)]

    @api.model
    def action_open(self, overdue=False):
        """Cartera sin las cuentas que no son cobranza (según la compañía)."""
        domain = [('in_collection', '=', True)]
        if overdue:
            domain.append(('is_overdue', '=', True))
        action = self.env['ir.actions.act_window']._for_xml_id('al_l10n_pe_collection.action_collection_portfolio')
        action['domain'] = domain
        return action

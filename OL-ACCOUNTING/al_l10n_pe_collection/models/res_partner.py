from datetime import timedelta

from dateutil.relativedelta import relativedelta

from werkzeug.urls import url_encode

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.payment import utils as payment_utils

RATINGS = [('A', 'A · Puntual'), ('B', 'B · Atraso leve'), ('C', 'C · Riesgo'), ('D', 'D · Alto riesgo')]
HOLD_STATES = [('auto', 'Bloqueado por mora'), ('manual', 'Bloqueado manualmente'), ('released', 'Liberado')]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_pe_collection_zone_id = fields.Many2one(
        'l10n_pe.collection.zone', string='Zona de cobranza', company_dependent=True,
        help='Agrupa la cartera; la zona propone el gestor.')
    l10n_pe_collection_promise_ids = fields.One2many(
        'l10n_pe.collection.promise', 'partner_id', string='Compromisos de pago')
    l10n_pe_collection_debtor_type = fields.Selection(
        [('auto', 'Según su documento'), ('consumer', 'Consumidor'), ('business', 'Empresa')],
        string='Tipo de deudor', default='auto',
        help='Los consumidores (sin RUC) están protegidos por el art. 62 del Código de Protección al '
             'Consumidor: sin llamadas ni visitas fuera de horario, fines de semana ni feriados.')
    l10n_pe_collection_reminder_consent = fields.Boolean(
        string='Acepta recordatorios antes del vencimiento',
        help='Sin este consentimiento no se envían a un consumidor los niveles de seguimiento previos '
             'al vencimiento.')
    l10n_pe_collection_score = fields.Integer(
        string='Puntaje de cobranza', company_dependent=True, readonly=True,
        help='0 a 100 según atraso promedio, deuda más antigua, compromisos incumplidos y % vencido. '
             'Se recalcula cada día.')
    l10n_pe_collection_rating = fields.Selection(
        RATINGS, string='Calificación de cobranza', company_dependent=True, readonly=True)
    l10n_pe_collection_priority = fields.Float(
        string='Prioridad de cobranza', company_dependent=True, readonly=True, digits=(16, 2),
        help='Vencido ponderado por el riesgo: ordena la cola de trabajo del gestor.')
    l10n_pe_collection_max_days = fields.Integer(
        string='Días de la deuda más antigua', company_dependent=True, readonly=True)
    l10n_pe_collection_rated_on = fields.Date(string='Calificado el', company_dependent=True, readonly=True)
    l10n_pe_collection_hold = fields.Selection(
        HOLD_STATES, string='Bloqueo de crédito', company_dependent=True, readonly=True,
        help='Un cliente bloqueado no puede confirmar pedidos de venta.')
    l10n_pe_collection_hold_until = fields.Date(
        string='Liberado hasta', company_dependent=True,
        help='Tras esta fecha vuelven a aplicarse las reglas de bloqueo por mora.')
    l10n_pe_collection_interest_rate = fields.Float(
        string='Interés moratorio pactado (TEA %)', company_dependent=True, digits=(7, 4),
        help='Vacío: la tasa de la compañía.')
    l10n_pe_collection_interest_warning = fields.Char(
        string='Aviso de tope de interés', compute='_compute_l10n_pe_collection_interest_warning')
    l10n_pe_collection_action_count = fields.Integer(
        string='Gestiones', compute='_compute_l10n_pe_collection_counts')
    l10n_pe_collection_promise_count = fields.Integer(
        string='Compromisos', compute='_compute_l10n_pe_collection_counts')
    l10n_pe_collection_dispute_count = fields.Integer(
        string='Reclamos', compute='_compute_l10n_pe_collection_counts')

    @api.onchange('l10n_pe_collection_zone_id')
    def _onchange_l10n_pe_collection_zone_id(self):
        if self.l10n_pe_collection_zone_id.user_id and not self.followup_responsible_id:
            self.followup_responsible_id = self.l10n_pe_collection_zone_id.user_id

    def _compute_l10n_pe_collection_counts(self):
        actions = dict(self.env['l10n_pe.collection.action']._read_group(
            [('partner_id', 'in', self.ids)], ['partner_id'], ['__count']))
        promises = dict(self.env['l10n_pe.collection.promise']._read_group(
            [('partner_id', 'in', self.ids)], ['partner_id'], ['__count']))
        disputes = dict(self.env['l10n_pe.collection.dispute']._read_group(
            [('partner_id', 'in', self.ids)], ['partner_id'], ['__count']))
        for partner in self:
            partner.l10n_pe_collection_action_count = actions.get(partner, 0)
            partner.l10n_pe_collection_promise_count = promises.get(partner, 0)
            partner.l10n_pe_collection_dispute_count = disputes.get(partner, 0)

    # ------------------------------------------------------------------
    # Cartera del cliente
    # ------------------------------------------------------------------

    def _l10n_pe_collection_open_lines(self, company=None):
        """Cuotas abiertas por cobrar del cliente (sin anticipos ni detracciones)."""
        self.ensure_one()
        company = company or self.env.company
        return self.env['account.move.line'].search([
            ('partner_id', 'child_of', self.commercial_partner_id.id),
            ('company_id', 'child_of', company.root_id.id),
            ('parent_state', '=', 'posted'),
            ('account_id.account_type', '=', 'asset_receivable'),
            ('account_id', 'not in', company._l10n_pe_collection_excluded_accounts().ids),
            ('reconciled', '=', False),
            ('amount_residual', '!=', 0.0),
        ], order='date_maturity, date, id')

    def _l10n_pe_collection_average_delay(self, company=None, today=None):
        """Atraso promedio (días) con que el cliente pagó sus facturas del
        historial configurado, ponderado por importe. Cero sin historial."""
        weighted, total = self._l10n_pe_collection_delay_data(company, today)
        return round(weighted / total) if total else 0

    def _l10n_pe_collection_delay_data(self, company=None, today=None):
        """(días × importe, importe) de las cuotas pagadas del historial."""
        self.ensure_one()
        company = company or self.env.company
        today = today or fields.Date.context_today(self)
        since = today - relativedelta(months=company.root_id.l10n_pe_collection_history_months or 12)
        invoices = self.env['account.move'].search([
            ('commercial_partner_id', '=', self.commercial_partner_id.id),
            ('company_id', 'child_of', company.root_id.id),
            ('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
            ('payment_state', 'in', ('paid', 'in_payment')),
            ('invoice_date', '>=', since),
        ])
        weighted = total = 0.0
        for invoice in invoices:
            terms = invoice.line_ids.filtered(lambda l: l.display_type == 'payment_term')
            for term in terms:
                partials = term.matched_credit_ids
                if not partials:
                    continue
                paid_on = max(partials.mapped('max_date'))
                due = term.date_maturity or invoice.invoice_date
                amount = abs(term.balance)
                weighted += (paid_on - due).days * amount
                total += amount
        return weighted, total

    def _l10n_pe_collection_log(self, body):
        """Deja constancia en el historial del cliente a nombre del usuario."""
        # sudo: el gestor de cobranza no tiene permiso de escritura sobre los
        # contactos, que es lo que Odoo exige para publicar o programar actividades.
        return self.sudo().message_post(body=body, author_id=self.env.user.partner_id.id)

    # ------------------------------------------------------------------
    # Consumidor (art. 62 de la Ley 29571)
    # ------------------------------------------------------------------

    def _l10n_pe_collection_is_consumer(self):
        """Persona sin RUC, salvo que el contacto diga otra cosa."""
        self.ensure_one()
        partner = self.commercial_partner_id
        if partner.l10n_pe_collection_debtor_type != 'auto':
            return partner.l10n_pe_collection_debtor_type == 'consumer'
        code = partner.l10n_latam_identification_type_id.l10n_pe_vat_code \
            if 'l10n_latam_identification_type_id' in partner._fields else False
        return code != '6' and not partner.is_company

    # ------------------------------------------------------------------
    # Calificación de riesgo y bloqueo
    # ------------------------------------------------------------------

    def _l10n_pe_collection_risk(self, company=None, today=None):
        """Puntaje (0-100), calificación, prioridad y días de la deuda más antigua."""
        self.ensure_one()
        company = company or self.env.company
        today = today or fields.Date.context_today(self)
        lines = self._l10n_pe_collection_open_lines(company).filtered(lambda l: l.amount_residual > 0)
        lines = lines.filtered(lambda l: not l.l10n_pe_collection_in_dispute)
        total = sum(lines.mapped('amount_residual'))
        overdue_lines = lines.filtered(lambda l: (l.date_maturity or l.date) < today)
        overdue = sum(overdue_lines.mapped('amount_residual'))
        max_days = max([(today - (l.date_maturity or l.date)).days for l in overdue_lines], default=0)
        # Atraso de lo ya pagado y de lo vencido que sigue abierto: sin esto, un
        # cliente que nunca pagó no tiene historial y quedaba bien calificado.
        weighted, paid_total = self._l10n_pe_collection_delay_data(company, today)
        for line in overdue_lines:
            weighted += (today - (line.date_maturity or line.date)).days * line.amount_residual
        delay_base = paid_total + overdue
        delay = weighted / delay_base if delay_base else 0
        broken = self.env['l10n_pe.collection.promise'].sudo().search_count([
            # sudo: el cron califica a todos los clientes, no solo los del gestor.
            ('partner_id', '=', self.commercial_partner_id.id),
            ('company_id', 'child_of', company.root_id.id),
            ('state', 'in', ('broken', 'partial')),
            ('evaluated_on', '>=', today - relativedelta(months=12)),
        ])
        score = 100.0
        score -= min(max(delay, 0) / 60.0, 1.0) * 40
        score -= min(max_days / 120.0, 1.0) * 30
        score -= min(broken / 3.0, 1.0) * 20
        score -= (overdue / total if total > 0 else 0.0) * 10
        score = round(score)
        rating = 'A' if score >= 80 else 'B' if score >= 60 else 'C' if score >= 40 else 'D'
        return {
            'score': score, 'rating': rating, 'max_days': max_days,
            'priority': round(overdue * (1 + (100 - score) / 100.0), 2),
        }

    def _l10n_pe_collection_hold_rule(self, company, risk):
        root = company.root_id
        return bool((root.l10n_pe_collection_hold_days and risk['max_days'] > root.l10n_pe_collection_hold_days)
                    or (root.l10n_pe_collection_hold_rating_d and risk['rating'] == 'D'))

    def _l10n_pe_collection_rate(self, company=None, today=None):
        """Califica a los clientes y aplica el bloqueo automático."""
        company = company or self.env.company
        today = today or fields.Date.context_today(self)
        for partner in self:
            partner = partner.with_company(company)
            risk = partner._l10n_pe_collection_risk(company, today)
            vals = {
                'l10n_pe_collection_score': risk['score'], 'l10n_pe_collection_rating': risk['rating'],
                'l10n_pe_collection_priority': risk['priority'], 'l10n_pe_collection_max_days': risk['max_days'],
                'l10n_pe_collection_rated_on': today,
            }
            hold = partner.l10n_pe_collection_hold
            if hold == 'released' and partner.l10n_pe_collection_hold_until \
                    and partner.l10n_pe_collection_hold_until < today:
                hold = False
                vals['l10n_pe_collection_hold_until'] = False
            if hold not in ('manual', 'released'):
                new_hold = 'auto' if partner._l10n_pe_collection_hold_rule(company, risk) else False
                if new_hold != (partner.l10n_pe_collection_hold or False):
                    partner._l10n_pe_collection_log(_('Bloqueo de crédito por mora aplicado.') if new_hold
                                         else _('Bloqueo de crédito por mora levantado.'))
                hold = new_hold
            vals['l10n_pe_collection_hold'] = hold
            partner.sudo().write(vals)  # sudo: campos de solo lectura que solo escribe la app.

    @api.model
    def _cron_l10n_pe_collection_rating(self):
        today = fields.Date.context_today(self)
        for company in self.env['res.company'].search([('parent_id', '=', False)]):
            Portfolio = self.env['l10n_pe.collection.portfolio'].sudo().with_company(company)
            # sudo: el cron califica toda la cartera, no la de un gestor.
            partners = Portfolio.search([('company_id', 'child_of', company.id)]).partner_id
            rated = self.with_company(company).sudo().search([('l10n_pe_collection_rating', '!=', False)])
            held = self.with_company(company).sudo().search([('l10n_pe_collection_hold', '!=', False)])
            (partners | rated | held).commercial_partner_id._l10n_pe_collection_rate(company, today)

    def _l10n_pe_collection_is_on_hold(self, company=None):
        self.ensure_one()
        partner = self.commercial_partner_id.with_company(company or self.env.company)
        return partner.l10n_pe_collection_hold in ('auto', 'manual')

    def action_l10n_pe_collection_hold(self):
        for partner in self.commercial_partner_id:
            # sudo: campo de solo lectura; el gestor no escribe contactos.
            partner.sudo().write({'l10n_pe_collection_hold': 'manual', 'l10n_pe_collection_hold_until': False})
            partner._l10n_pe_collection_log(_('Bloqueo de crédito manual.'))
        return True

    def action_l10n_pe_collection_release(self):
        if not self.env.user.has_group('al_l10n_pe_collection.group_collection_manager'):
            raise UserError(_('Solo el administrador de cobranza libera un bloqueo de crédito.'))
        until = fields.Date.context_today(self) + timedelta(days=7)
        for partner in self.commercial_partner_id:
            partner.sudo().write({'l10n_pe_collection_hold': 'released',
                                  'l10n_pe_collection_hold_until': partner.l10n_pe_collection_hold_until or until})
            partner._l10n_pe_collection_log(_('Bloqueo de crédito liberado hasta el %s.',
                                        partner.l10n_pe_collection_hold_until.strftime('%d/%m/%Y')))
        return True

    @api.depends_context('company')
    @api.depends('l10n_pe_collection_interest_rate')
    def _compute_l10n_pe_collection_interest_warning(self):
        caps = self.env['l10n_pe.collection.rate.cap']
        for partner in self:
            partner.l10n_pe_collection_interest_warning = caps._l10n_pe_rate_warning(
                partner.l10n_pe_collection_interest_rate)

    def action_l10n_pe_collection_rate_now(self):
        self.commercial_partner_id._l10n_pe_collection_rate()
        return True

    # ------------------------------------------------------------------
    # Intereses moratorios
    # ------------------------------------------------------------------

    def _l10n_pe_collection_interest_rate_value(self, company=None):
        self.ensure_one()
        company = company or self.env.company
        partner = self.commercial_partner_id.with_company(company)
        return partner.l10n_pe_collection_interest_rate or company.root_id.l10n_pe_collection_interest_rate

    def _l10n_pe_collection_interest(self, line, today=None, company=None):
        """Interés moratorio de una cuota vencida: (saldo en su moneda, saldo en
        moneda de la compañía, días). Ver ``_l10n_pe_collection_interest_detail``."""
        detail = self._l10n_pe_collection_interest_detail(line, today, company)
        return detail['amount'], detail['amount_company'], detail['days']

    def _l10n_pe_collection_interest_detail(self, line, today=None, company=None):
        """Interés moratorio de una cuota vencida con TEA y año de 360 días, desde el
        vencimiento o desde el último interés facturado. En cada tramo, la tasa pactada
        se recorta al moratorio máximo del BCRP vigente para la moneda de la cuota.

        :return: dict con ``amount``, ``amount_company``, ``days``, ``capped`` (se aplicó
            el tope) y ``uncovered`` (días sin tope registrado).
        """
        self.ensure_one()
        today = today or fields.Date.context_today(self)
        rate = self._l10n_pe_collection_interest_rate_value(company)
        start = max(filter(None, [line.date_maturity or line.date, line.l10n_pe_collection_interest_date]))
        days = (today - start).days
        detail = {'amount': 0.0, 'amount_company': 0.0, 'days': 0, 'capped': False, 'uncovered': 0}
        if rate <= 0 or days <= 0 or line.amount_residual <= 0 or line.l10n_pe_collection_in_dispute:
            return detail
        caps = self.env['l10n_pe.collection.rate.cap']
        factor, capped, uncovered = caps._l10n_pe_interest_factor(
            rate, start, today, caps._l10n_pe_currency_type(line.currency_id))
        detail.update(
            amount=line.currency_id.round(line.amount_residual_currency * factor),
            amount_company=line.company_currency_id.round(line.amount_residual * factor),
            days=days, capped=capped, uncovered=uncovered)
        return detail

    # ------------------------------------------------------------------
    # Pago en línea
    # ------------------------------------------------------------------

    #: Prefijo de las transacciones del enlace de pago del saldo: al confirmarse se
    #: aplican a las facturas más antiguas del cliente.
    _L10N_PE_COLLECTION_TX_PREFIX = 'COB'

    def _l10n_pe_collection_payment_url(self, company=None):
        """Enlace para pagar en línea el saldo del cliente, o '' si no corresponde
        (desactivado, sin pasarela en línea activa o sin saldo)."""
        self.ensure_one()
        company = company or self.env.company
        if not company.root_id.l10n_pe_collection_online_payment:
            return ''
        # sudo: los gestores no leen la configuración de las pasarelas.
        providers_sudo = self.env['payment.provider'].sudo().search([
            ('state', 'in', ('enabled', 'test')), ('code', '!=', 'custom'),
            ('company_id', 'in', (company | company.root_id).ids)], limit=1)
        if not providers_sudo:
            return ''
        partner = self.commercial_partner_id
        amount = company.currency_id.round(partner._l10n_pe_collection_statement_values(company)['total'])
        if amount <= 0:
            return ''
        currency = company.currency_id
        params = {
            'reference': self._L10N_PE_COLLECTION_TX_PREFIX,
            'amount': amount,
            'currency_id': currency.id,
            'partner_id': partner.id,
            'company_id': company.id,
            'access_token': payment_utils.generate_access_token(partner.id, amount, currency.id, env=self.env),
        }
        return '%s/payment/pay?%s' % (company.get_base_url(), url_encode(params))

    def _l10n_pe_collection_fifo_invoices(self, amount, company=None):
        """Facturas abiertas más antiguas del cliente que cubren ``amount``."""
        self.ensure_one()
        company = company or self.env.company
        invoices = self.env['account.move']
        covered = 0.0
        for line in self._l10n_pe_collection_open_lines(company).filtered(
                lambda l: l.amount_residual > 0 and l.move_id.move_type == 'out_invoice'
                and not l.l10n_pe_collection_in_dispute):
            if company.currency_id.compare_amounts(covered, amount) >= 0:
                break
            if line.move_id not in invoices:
                invoices |= line.move_id
            covered += line.amount_residual
        return invoices

    # ------------------------------------------------------------------
    # Accesos
    # ------------------------------------------------------------------

    def action_l10n_pe_collection_actions(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('al_l10n_pe_collection.action_collection_action')
        action.update(domain=[('partner_id', '=', self.id)],
                      context={'default_partner_id': self.id})
        return action

    def action_l10n_pe_collection_promises(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('al_l10n_pe_collection.action_collection_promise')
        action.update(domain=[('partner_id', '=', self.id)],
                      context={'default_partner_id': self.id})
        return action

    def action_l10n_pe_collection_new_action(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Registrar gestión'),
            'res_model': 'l10n_pe.collection.action',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_partner_id': self.commercial_partner_id.id},
        }

    @api.model
    def action_l10n_pe_collection_worklist(self):
        """Cola de trabajo: el gestor ve sus clientes; el administrador, todos."""
        action = self.env['ir.actions.act_window']._for_xml_id('al_l10n_pe_collection.action_collection_worklist')
        if self.env.user.has_group('al_l10n_pe_collection.group_collection_manager'):
            action['context'] = {}
        return action

    def action_l10n_pe_collection_disputes(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('al_l10n_pe_collection.action_collection_dispute')
        action.update(domain=[('partner_id', '=', self.id)], context={'default_partner_id': self.id})
        return action

    def action_l10n_pe_collection_new_dispute(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Registrar reclamo'),
            'res_model': 'l10n_pe.collection.dispute',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_partner_id': self.commercial_partner_id.id},
        }

    def action_l10n_pe_collection_file(self):
        return self.env.ref('al_l10n_pe_collection.action_report_collection_file').report_action(
            self.commercial_partner_id, config=False)

    def _l10n_pe_collection_file_values(self, company=None):
        """Expediente de cobranza: todo lo que acredita la gestión de cobro."""
        self.ensure_one()
        company = company or self.env.company
        partner = self.commercial_partner_id
        root = [('company_id', 'child_of', company.root_id.id)]
        # sudo: el expediente sustenta la provisión ante SUNAT y debe mostrar las
        # gestiones de todos los gestores, no solo las del usuario que lo imprime.
        actions_sudo = self.env['l10n_pe.collection.action'].sudo().search(
            [('partner_id', '=', partner.id)] + root, order='date')
        promises_sudo = self.env['l10n_pe.collection.promise'].sudo().search(
            [('partner_id', '=', partner.id)] + root, order='date_agreed, id')
        disputes_sudo = self.env['l10n_pe.collection.dispute'].sudo().search(
            [('partner_id', '=', partner.id)] + root, order='date, id')
        bureaus_sudo = self.env['l10n_pe.collection.bureau'].sudo().search(
            [('partner_id', '=', partner.id)] + root, order='id')
        messages_sudo = self.env['mail.message'].sudo().search([
            ('model', '=', 'res.partner'), ('res_id', '=', partner.id), ('message_type', 'in', ('email', 'email_outgoing', 'comment'))],
            order='date')
        return {
            'statement': partner._l10n_pe_collection_statement_values(company),
            'actions': actions_sudo, 'promises': promises_sudo, 'disputes': disputes_sudo,
            'bureaus': bureaus_sudo, 'emails': messages_sudo,
        }

    def action_l10n_pe_collection_statement(self):
        return self.env.ref('al_l10n_pe_collection.action_report_statement').report_action(self, config=False)

    def action_l10n_pe_collection_send_statement(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Enviar estado de cuenta'),
            'res_model': 'l10n_pe.collection.statement.send',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_partner_ids': self.commercial_partner_id.ids},
        }

    def _l10n_pe_collection_statement_values(self, company=None, today=None):
        """Documentos y totales del estado de cuenta."""
        self.ensure_one()
        company = company or self.env.company
        today = today or fields.Date.context_today(self)
        lines = self._l10n_pe_collection_open_lines(company)
        documents = []
        overdue = due = credit = interest = 0.0
        for line in lines:
            interest_currency, interest_company, _days = self._l10n_pe_collection_interest(line, today, company)
            interest += interest_company
            move = line.move_id
            residual = line.amount_residual
            is_credit = residual < 0  # nota de crédito o pago sin aplicar: saldo a favor
            days = 0 if is_credit else (today - (line.date_maturity or line.date)).days
            documents.append({
                'line': line,
                'document': move.l10n_latam_document_type_id.name if 'l10n_latam_document_type_id' in move._fields
                and move.l10n_latam_document_type_id else '',
                'name': move.name,
                'date': move.invoice_date or move.date,
                'date_due': line.date_maturity or line.date,
                'days': max(days, 0),
                'currency': line.currency_id,
                'total_currency': line.amount_currency,
                'residual_currency': line.amount_residual_currency,
                'residual': residual,
                'overdue': days > 0,
                'is_credit': is_credit,
                'in_dispute': line.l10n_pe_collection_in_dispute,
                'interest_currency': interest_currency,
            })
            if is_credit:
                credit += residual
            elif days > 0:
                overdue += residual
            else:
                due += residual
        return {'documents': documents, 'overdue': overdue, 'due': due, 'credit': credit,
                'interest': interest, 'total': overdue + due + credit,
                'currency': company.currency_id, 'today': today}

from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models


class L10nPeCollectionDashboard(models.TransientModel):
    """Indicadores del gestor elegido (o de todos); el tablero gráfico es la hoja de
    cálculo «Cobranza» de la app Tableros."""
    _name = 'l10n_pe.collection.dashboard'
    _description = 'Indicadores del gestor'

    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    user_id = fields.Many2one(
        'res.users', string='Gestor',
        default=lambda self: False if self.env.user.has_group('al_l10n_pe_collection.group_collection_manager')
        else self.env.user, help='Vacío: toda la cartera.')
    portfolio_amount = fields.Monetary(string='Cartera', compute='_compute_kpis')
    overdue_amount = fields.Monetary(string='Vencido', compute='_compute_kpis')
    overdue_percent = fields.Float(string='% vencido', compute='_compute_kpis', digits=(5, 1))
    overdue_90_amount = fields.Monetary(string='Vencido más de 90 días', compute='_compute_kpis')
    due_soon_amount = fields.Monetary(string='Vence en 7 días', compute='_compute_kpis')
    partner_overdue_count = fields.Integer(string='Clientes con deuda vencida', compute='_compute_kpis')
    promises_today_count = fields.Integer(string='Compromisos de hoy', compute='_compute_kpis')
    promises_pending_amount = fields.Monetary(string='Comprometido pendiente', compute='_compute_kpis')
    promises_broken_count = fields.Integer(string='Incumplidos (30 días)', compute='_compute_kpis')
    promises_kept_rate = fields.Float(string='Cumplimiento de compromisos (90 días, %)', compute='_compute_kpis',
                                      digits=(5, 1))
    dso = fields.Float(string='DSO (días)', compute='_compute_kpis', digits=(6, 1),
                       help='Días de venta pendientes de cobro: cartera ÷ ventas de los últimos 90 días × 90.')
    collected_month_amount = fields.Monetary(string='Cobrado en el mes', compute='_compute_kpis')
    target_month_amount = fields.Monetary(string='Meta del mes', compute='_compute_kpis')
    target_progress = fields.Float(string='Avance de la meta (%)', compute='_compute_kpis', digits=(5, 1))

    def _compute_display_name(self):
        for board in self:
            board.display_name = _('Indicadores del gestor')

    def _portfolio_domain(self):
        self.ensure_one()
        company = self.company_id
        domain = [('company_id', 'child_of', company.root_id.id),
                  ('account_id', 'not in', company._l10n_pe_collection_excluded_accounts().ids)]
        if self.user_id:
            domain.append(('user_id', '=', self.user_id.id))
        return domain

    def _promise_domain(self):
        self.ensure_one()
        domain = [('company_id', 'child_of', self.company_id.root_id.id)]
        if self.user_id:
            domain.append(('user_id', '=', self.user_id.id))
        return domain

    @api.depends('user_id', 'company_id')
    def _compute_kpis(self):
        today = fields.Date.context_today(self)
        Portfolio = self.env['l10n_pe.collection.portfolio']
        Promise = self.env['l10n_pe.collection.promise']
        tools = self.env['l10n_pe.collection.tools']
        for board in self:
            company = board.company_id
            lines = Portfolio.search(board._portfolio_domain())
            overdue = lines.filtered('is_overdue')
            board.portfolio_amount = sum(lines.mapped('amount_residual'))
            board.overdue_amount = sum(overdue.mapped('amount_residual'))
            board.overdue_percent = 100.0 * board.overdue_amount / board.portfolio_amount \
                if board.portfolio_amount else 0.0
            board.overdue_90_amount = sum(overdue.filtered(lambda l: l.days_overdue > 90).mapped('amount_residual'))
            # Solo documentos por cobrar: un saldo a favor del cliente no «vence».
            board.due_soon_amount = sum(lines.filtered(
                lambda l: l.amount_residual > 0 and today <= l.date_maturity <= today + timedelta(days=7)
            ).mapped('amount_residual'))
            board.partner_overdue_count = len(overdue.partner_id)
            promises = Promise.search(board._promise_domain())
            board.promises_today_count = len(promises.filtered(lambda p: p.state == 'pending' and p.date == today))
            board.promises_pending_amount = sum(promises.filtered(lambda p: p.state == 'pending').mapped('amount'))
            recent = promises.filtered(lambda p: p.evaluated_on and p.evaluated_on >= today - timedelta(days=30))
            board.promises_broken_count = len(recent.filtered(lambda p: p.state in ('broken', 'partial')))
            closed = promises.filtered(lambda p: p.state in ('kept', 'partial', 'broken')
                                       and p.evaluated_on and p.evaluated_on >= today - timedelta(days=90))
            board.promises_kept_rate = 100.0 * len(closed.filtered(lambda p: p.state == 'kept')) / len(closed) \
                if closed else 0.0
            partners = tools._scope_partners(company, board.user_id) if board.user_id else None
            board.dso = board._dso(today, partners)
            month_start = today.replace(day=1)
            month_end = month_start + relativedelta(months=1, days=-1)
            board.collected_month_amount = tools._collected(company, month_start, month_end, partners)
            targets = self.env['l10n_pe.collection.target'].search([
                ('company_id', '=', company.id), ('date_from', '<=', today), ('date_to', '>=', today)]
                + ([('user_id', '=', board.user_id.id)] if board.user_id else []))
            board.target_month_amount = sum(targets.mapped('amount'))
            board.target_progress = 100.0 * board.collected_month_amount / board.target_month_amount \
                if board.target_month_amount else 0.0

    def _dso(self, today, partners=None):
        """Cartera ÷ ventas a crédito de los últimos 90 días × 90."""
        domain = [('company_id', 'child_of', self.company_id.root_id.id), ('state', '=', 'posted'),
                  ('move_type', 'in', ('out_invoice', 'out_refund')),
                  ('invoice_date', '>', today - timedelta(days=90)), ('invoice_date', '<=', today)]
        if partners is not None:
            domain.append(('commercial_partner_id', 'in', partners.commercial_partner_id.ids))
        groups = self.env['account.move']._read_group(domain, aggregates=['amount_total_signed:sum'])
        sales = groups[0][0] if groups else 0.0
        return round(self.portfolio_amount / sales * 90, 1) if sales else 0.0

    # ------------------------------------------------------------------
    # Accesos
    # ------------------------------------------------------------------

    def _open_portfolio(self, extra_domain, name):
        action = self.env['l10n_pe.collection.portfolio'].action_open()
        action['domain'] = self._portfolio_domain() + extra_domain
        action['name'] = name
        return action

    def action_open_portfolio(self):
        return self._open_portfolio([], _('Cartera'))

    def action_open_overdue(self):
        return self._open_portfolio([('is_overdue', '=', True)], _('Cartera vencida'))

    def action_open_due_soon(self):
        today = fields.Date.context_today(self)
        return self._open_portfolio([('amount_residual', '>', 0), ('date_maturity', '>=', today),
                                     ('date_maturity', '<=', today + timedelta(days=7))], _('Vence en 7 días'))

    def action_open_promises(self):
        action = self.env['ir.actions.act_window']._for_xml_id('al_l10n_pe_collection.action_collection_promise')
        action['domain'] = self._promise_domain()
        return action

    def action_refresh(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'current'}

    @api.model
    def action_open_dashboard(self):
        board = self.create({})
        return {'type': 'ir.actions.act_window', 'name': _('Indicadores del gestor'), 'res_model': self._name,
                'res_id': board.id, 'view_mode': 'form', 'target': 'current'}

    # ------------------------------------------------------------------
    # Resumen diario a cada gestor
    # ------------------------------------------------------------------

    @api.model
    def _digest_values(self, user, company, today):
        Portfolio = self.env['l10n_pe.collection.portfolio'].sudo()
        # sudo: el cron arma el resumen de cada gestor, con su cartera aunque el
        # usuario del cron no tenga sus permisos.
        promises_sudo = self.env['l10n_pe.collection.promise'].sudo().search([
            ('user_id', '=', user.id), ('company_id', 'child_of', company.root_id.id), ('state', '=', 'pending'),
            ('date', '<=', today)], order='date')
        broken_sudo = self.env['l10n_pe.collection.promise'].sudo().search([
            ('user_id', '=', user.id), ('company_id', 'child_of', company.root_id.id),
            ('state', 'in', ('broken', 'partial')), ('evaluated_on', '=', today)])
        excluded = company._l10n_pe_collection_excluded_accounts().ids
        base = [('user_id', '=', user.id), ('company_id', 'child_of', company.root_id.id),
                ('account_id', 'not in', excluded)]
        due_soon = Portfolio.search(base + [('date_maturity', '>=', today),
                                            ('date_maturity', '<=', today + timedelta(days=3))])
        new_overdue = Portfolio.search(base + [('date_maturity', '=', today - timedelta(days=1))])
        activities_sudo = self.env['mail.activity'].sudo().search([
            ('user_id', '=', user.id), ('res_model', '=', 'res.partner'), ('date_deadline', '<=', today)],
            order='date_deadline')
        return {
            'user': user, 'company': company, 'today': today, 'currency': company.currency_id,
            'promises': promises_sudo, 'broken': broken_sudo, 'due_soon': due_soon, 'new_overdue': new_overdue,
            'activities': activities_sudo,
        }

    @api.model
    def _cron_collection_digest(self):
        today = fields.Date.context_today(self)
        companies = self.env['res.company'].search([('parent_id', '=', False), ('l10n_pe_collection_digest', '=', True)])
        for company in companies:
            users = self.env['l10n_pe.collection.portfolio'].sudo().search(
                [('company_id', 'child_of', company.id), ('user_id', '!=', False)]).user_id
            users |= self.env['l10n_pe.collection.promise'].sudo().search(
                [('company_id', 'child_of', company.id), ('state', '=', 'pending')]).user_id
            for user in users.filtered(lambda u: u.email and u.active):
                self._send_digest(user, company, today)

    @api.model
    def _send_digest(self, user, company, today):
        values = self._digest_values(user, company, today)
        if not any(values[key] for key in ('promises', 'broken', 'due_soon', 'new_overdue', 'activities')):
            return False
        body = self.env['ir.qweb']._render('al_l10n_pe_collection.collection_digest_mail', values)
        return self.env['mail.mail'].sudo().create({
            'subject': _('Cobranza del %(date)s · %(company)s', date=today.strftime('%d/%m/%Y'),
                         company=company.name),
            'body_html': body,
            'email_to': user.email_formatted,
            'email_from': company.email_formatted or user.email_formatted,
            'auto_delete': True,
        })

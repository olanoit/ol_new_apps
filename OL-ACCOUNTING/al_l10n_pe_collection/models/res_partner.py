from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_pe_collection_zone_id = fields.Many2one(
        'l10n_pe.collection.zone', string='Zona de cobranza', company_dependent=True,
        help='Agrupa la cartera; la zona propone el gestor.')
    l10n_pe_collection_promise_ids = fields.One2many(
        'l10n_pe.collection.promise', 'partner_id', string='Compromisos de pago')
    l10n_pe_collection_action_count = fields.Integer(
        string='Gestiones', compute='_compute_l10n_pe_collection_counts')
    l10n_pe_collection_promise_count = fields.Integer(
        string='Compromisos', compute='_compute_l10n_pe_collection_counts')

    @api.onchange('l10n_pe_collection_zone_id')
    def _onchange_l10n_pe_collection_zone_id(self):
        if self.l10n_pe_collection_zone_id.user_id and not self.followup_responsible_id:
            self.followup_responsible_id = self.l10n_pe_collection_zone_id.user_id

    def _compute_l10n_pe_collection_counts(self):
        actions = dict(self.env['l10n_pe.collection.action']._read_group(
            [('partner_id', 'in', self.ids)], ['partner_id'], ['__count']))
        promises = dict(self.env['l10n_pe.collection.promise']._read_group(
            [('partner_id', 'in', self.ids)], ['partner_id'], ['__count']))
        for partner in self:
            partner.l10n_pe_collection_action_count = actions.get(partner, 0)
            partner.l10n_pe_collection_promise_count = promises.get(partner, 0)

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
        return round(weighted / total) if total else 0

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
        overdue = due = credit = 0.0
        for line in lines:
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
            })
            if is_credit:
                credit += residual
            elif days > 0:
                overdue += residual
            else:
                due += residual
        return {'documents': documents, 'overdue': overdue, 'due': due, 'credit': credit,
                'total': overdue + due + credit,
                'currency': company.currency_id, 'today': today}

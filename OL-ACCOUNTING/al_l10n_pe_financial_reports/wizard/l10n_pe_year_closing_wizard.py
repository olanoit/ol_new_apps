# -*- coding: utf-8 -*-
"""Cierre del ejercicio.

1. Determinación del resultado: las reglas (``l10n_pe.closing.rule``) saldan,
   en orden, las cuentas de resultados y de las clases 8 y 9: 9 contra 79,
   saldos intermediarios de gestión (80 a 85), resultado (89) y resultados
   acumulados (59). Un asiento por regla.
2. Opcional: cierre de las cuentas de balance al último día del ejercicio y
   su reapertura el primer día del siguiente, ambos en el diario de cierre
   para que los informes (que excluyen ese diario) no dupliquen saldos.

Los asientos se crean en borrador para que el contador los revise.
«Publicar» los publica y concilia cada línea de reapertura con su línea de
cierre en las cuentas conciliables, para que las partidas abiertas sigan
siendo las de los comprobantes.
"""
from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import _, api, Command, fields, models
from odoo.exceptions import UserError

RESULT_GROUPS = ('income', 'expense')


class L10nPeYearClosingWizard(models.TransientModel):
    _name = 'l10n_pe.year.closing.wizard'
    _description = 'Cierre del ejercicio (Perú)'
    _check_company_auto = True

    # El cierre es del RUC: siempre en la compañía raíz, con los apuntes de
    # todas sus sucursales.
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True,
        default=lambda self: self.env.company.root_id)
    date_to = fields.Date(
        string='Cierre al', required=True, default=lambda self: self._default_date_to(),
        help='Último día del ejercicio que se cierra.')
    journal_id = fields.Many2one(
        'account.journal', string='Diario de cierre', required=True, check_company=True,
        default=lambda self: self._default_journal(),
        domain="[('company_id', '=', company_id), ('l10n_pe_journal_kind', '=', 'closing')]",
        help='Diario de naturaleza «Cierre». Los estados financieros no '
             'cuentan sus asientos.')
    include_balance = fields.Boolean(
        string='Cerrar y reabrir las cuentas de balance',
        help='Salda todas las cuentas de balance al cierre y las reabre el '
             'primer día del ejercicio siguiente, como se lleva el Libro '
             'diario. Odoo arrastra los saldos por sí mismo: estos asientos '
             'solo sirven para los libros. Ambos van en el diario de cierre; '
             'el Libro mayor y los saldos por empresa al 31/12 los incluyen '
             'y muestran las cuentas de balance en cero ese día.')
    move_ids = fields.Many2many(
        'account.move', string='Asientos del cierre', compute='_compute_move_ids')

    def _default_date_to(self):
        fiscalyear = self.env.company.compute_fiscalyear_dates(fields.Date.context_today(self))
        return fiscalyear['date_from'] - relativedelta(days=1)

    def _default_journal(self):
        Journal = self.env['account.journal']
        return Journal.search([
            ('company_id', '=', self.env.company.root_id.id),
            ('l10n_pe_journal_kind', '=', 'closing'),
        ], limit=1)

    @api.depends('company_id', 'date_to')
    def _compute_move_ids(self):
        for wizard in self:
            wizard.move_ids = wizard._l10n_pe_get_closing_moves()

    def _l10n_pe_get_closing_moves(self):
        self.ensure_one()
        if not self.date_to:
            return self.env['account.move']
        return self.env['account.move'].search([
            ('company_id', '=', self.company_id.id),
            ('l10n_pe_closing_date', '=', self.date_to),
        ], order='date, id')

    def _l10n_pe_branches(self):
        """La compañía raíz y sus sucursales. La regla de los apuntes solo
        deja ver las compañías activas en el selector: el cierre las lee
        todas y exige que el usuario tenga acceso a cada una."""
        # sudo: hay que ver también las sucursales a las que el usuario no
        # tiene acceso para avisarle; solo se devuelven sus ids tras validarlo.
        branches_sudo = self.env['res.company'].sudo().search([('id', 'child_of', self.company_id.id)])
        missing_sudo = branches_sudo - self.env.user.company_ids
        if missing_sudo:
            raise UserError(_(
                'El cierre incluye todas las sucursales del RUC y usted no tiene '
                'acceso a: %(companies)s.', companies=', '.join(missing_sudo.mapped('name'))))
        return self.env['res.company'].browse(branches_sudo.ids)

    def _l10n_pe_move_lines(self, branches):
        return self.env['account.move.line'].with_context(allowed_company_ids=branches.ids)

    def _l10n_pe_rules(self):
        return self.env['l10n_pe.closing.rule'].search([
            ('company_id', 'in', (False, self.company_id.id))])

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def action_generate(self):
        self.ensure_one()
        fiscalyear = self.company_id.compute_fiscalyear_dates(self.date_to)
        if fiscalyear['date_to'] != self.date_to:
            raise UserError(_(
                'El cierre va al último día del ejercicio: %(date)s.',
                date=fields.Date.to_string(fiscalyear['date_to'])))
        moves = self._l10n_pe_get_closing_moves()
        if any(move.state == 'posted' for move in moves):
            raise UserError(_(
                'El cierre al %(date)s ya está publicado. Para rehacerlo, pase '
                'antes sus asientos a borrador.', date=fields.Date.to_string(self.date_to)))
        moves.unlink()

        vals_list, retained = self._l10n_pe_result_moves_vals(fiscalyear['date_from'])
        if self.include_balance:
            vals_list += self._l10n_pe_balance_moves_vals(retained)
        if not vals_list:
            raise UserError(_('No hay saldos que cerrar en el ejercicio.'))
        self.env['account.move'].create(vals_list)
        return self._l10n_pe_action_open_moves()

    def action_post(self):
        self.ensure_one()
        moves = self._l10n_pe_get_closing_moves().filtered(lambda move: move.state == 'draft')
        if not moves:
            raise UserError(_('No hay asientos de cierre en borrador que publicar.'))
        moves.action_post()
        self._l10n_pe_reconcile_reopening()
        return self._l10n_pe_action_open_moves()

    def _l10n_pe_action_open_moves(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cierre del ejercicio %(date)s', date=fields.Date.to_string(self.date_to)),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self._l10n_pe_get_closing_moves().ids)],
            'context': {'create': False},
        }

    # ------------------------------------------------------------------
    # Determinación del resultado
    # ------------------------------------------------------------------

    def _l10n_pe_is_result_account(self, account):
        """Cuentas que salda la determinación del resultado: las de
        resultados y las de las clases 8 y 9 que no son de balance (la 882
        Impuesto a la renta diferido es un pasivo)."""
        if account.internal_group in RESULT_GROUPS:
            return True
        return (account.code or '')[:1] in ('8', '9') \
            and account.internal_group not in ('asset', 'liability')

    def _l10n_pe_find_account(self, code):
        """Cuenta destino de una regla. El plan peruano rellena los códigos
        (la 791 es 7910000): vale el código exacto o, si no existe, la primera
        cuenta que empieza por él."""
        if not code:
            return self.env['account.account']
        code = code.strip()
        Account = self.env['account.account'].with_company(self.company_id)
        domain = Account._check_company_domain(self.company_id)
        return Account.search([*domain, ('code', '=', code)], limit=1) \
            or Account.search([*domain, ('code', '=like', code + '%')], order='code', limit=1)

    def _l10n_pe_account(self, code):
        account = self._l10n_pe_find_account(code)
        if not account:
            raise UserError(_(
                'No existe la cuenta %(code)s, que usa una regla del cierre del '
                'ejercicio. Créela o corrija la regla.', code=code))
        return account

    def _l10n_pe_move_vals(self, ref, date, step, lines):
        return {
            'move_type': 'entry',
            'journal_id': self.journal_id.id,
            'date': date,
            'ref': ref,
            'l10n_pe_closing_date': self.date_to,
            'l10n_pe_closing_step': step,
            'line_ids': lines,
        }

    def _l10n_pe_result_moves_vals(self, date_from):
        """Asientos de la determinación del resultado y lo que dejan en las
        cuentas que no son de resultados (la 59), para el cierre de balance."""
        currency = self.company_id.currency_id
        branches = self._l10n_pe_branches()
        groups = self._l10n_pe_move_lines(branches)._read_group([
            ('company_id', 'in', branches.ids),
            ('parent_state', '=', 'posted'),
            ('date', '>=', date_from),
            ('date', '<=', self.date_to),
            ('journal_id.l10n_pe_journal_kind', '!=', 'closing'),
        ], ['account_id'], ['balance:sum'])
        balances = defaultdict(float)
        for account, balance in groups:
            account = account.with_company(self.company_id)
            if self._l10n_pe_is_result_account(account):
                balances[account] += currency.round(balance)

        vals_list = []
        for rule in self._l10n_pe_rules():
            prefixes = rule._get_source_prefixes()
            targets = self._l10n_pe_find_account(rule.target_code) \
                | self._l10n_pe_find_account(rule.loss_code)
            sources = sorted(
                (account for account, balance in balances.items()
                 if account not in targets
                 and (account.code or '').startswith(prefixes)
                 and not currency.is_zero(balance)),
                key=lambda account: account.code)
            if not sources:
                continue
            # Una cuenta destino que falta solo es error si la regla se usa:
            # una empresa sin clase 9 no necesita la 791.
            target = self._l10n_pe_account(rule.target_code)
            loss = self._l10n_pe_account(rule.loss_code) if rule.loss_code else target
            lines = []
            net = 0.0
            for account in sources:
                balance = balances.pop(account)
                net += balance
                lines.append(Command.create({
                    'account_id': account.id, 'name': rule.name, 'balance': -balance}))
            net = currency.round(net)
            if not currency.is_zero(net):
                # Neto deudor: pérdida.
                destination = loss if net > 0 else target
                lines.append(Command.create({
                    'account_id': destination.id, 'name': rule.name, 'balance': net}))
                balances[destination] += net
            vals_list.append(self._l10n_pe_move_vals(rule.name, self.date_to, 'result', lines))

        leftovers = sorted(
            account.code for account, balance in balances.items()
            if self._l10n_pe_is_result_account(account) and not currency.is_zero(balance))
        if leftovers:
            raise UserError(_(
                'Estas cuentas siguen con saldo después del cierre porque '
                'ninguna regla las salda: %(codes)s. Revise las reglas en '
                'Perú ▸ Configuración ▸ Contabilidad ▸ Reglas del cierre del '
                'ejercicio.', codes=', '.join(leftovers)))
        retained = {account: balance for account, balance in balances.items()
                    if not currency.is_zero(balance)}
        return vals_list, retained

    # ------------------------------------------------------------------
    # Cierre de balance y reapertura
    # ------------------------------------------------------------------

    def _l10n_pe_balance_moves_vals(self, retained):
        company = self.company_id
        currency = company.currency_id
        branches = self._l10n_pe_branches()
        groups = self._l10n_pe_move_lines(branches)._read_group([
            ('company_id', 'in', branches.ids),
            ('parent_state', '=', 'posted'),
            ('date', '<=', self.date_to),
            ('account_id.internal_group', 'in', ('asset', 'liability', 'equity')),
        ], ['account_id', 'partner_id', 'currency_id'], ['balance:sum', 'amount_currency:sum'])

        totals = defaultdict(lambda: [0.0, 0.0])
        for account, partner, line_currency, balance, amount_currency in groups:
            account = account.with_company(company)
            if self._l10n_pe_is_result_account(account):
                continue
            if line_currency == currency:
                amount_currency = 0.0
            key = (account, partner if account.reconcile else self.env['res.partner'], line_currency)
            totals[key][0] += balance
            totals[key][1] += amount_currency
        # Lo que la determinación del resultado lleva a la 59 (aún en borrador).
        for account, balance in retained.items():
            totals[(account, self.env['res.partner'], currency)][0] += balance

        closing_lines = []
        for (account, partner, line_currency), (balance, amount_currency) in sorted(
                totals.items(), key=lambda item: (item[0][0].code, item[0][1].id or 0)):
            balance = currency.round(balance)
            if line_currency == currency:
                amount_currency = balance
            amount_currency = line_currency.round(amount_currency)
            if currency.is_zero(balance) and line_currency.is_zero(amount_currency):
                continue
            vals = {'account_id': account.id, 'partner_id': partner.id, 'currency_id': line_currency.id}
            if balance * amount_currency < 0 or (not balance) != (not amount_currency):
                # La diferencia de cambio deja saldo y monto en moneda con
                # signos distintos (o uno en cero): una línea no puede llevar
                # ambos, así que el monto en moneda y el saldo van por separado.
                closing_lines.append({**vals, 'amount_currency': -amount_currency, 'balance': 0.0})
                closing_lines.append({**vals, 'amount_currency': 0.0, 'balance': -balance})
            else:
                closing_lines.append({**vals, 'amount_currency': -amount_currency, 'balance': -balance})
        closing_lines = [line for line in closing_lines if line['balance'] or line['amount_currency']]
        if not closing_lines:
            return []

        residual = currency.round(-sum(line['balance'] for line in closing_lines))
        if not currency.is_zero(residual):
            # Resultados de ejercicios que no se cerraron: siguen en las
            # cuentas de resultados y se reconocen aquí en la 59.
            last_rule = self._l10n_pe_rules()[-1:]
            if not last_rule:
                raise UserError(_('Defina las reglas del cierre del ejercicio.'))
            # La línea debita la 59 cuando el balance tiene saldo deudor, es
            # decir, cuando hay utilidad sin cerrar: va a la cuenta de
            # utilidades. Acreditar la 59 es saldar una pérdida.
            code = last_rule.loss_code if residual < 0 and last_rule.loss_code else last_rule.target_code
            closing_lines.append({
                'account_id': self._l10n_pe_account(code).id,
                'currency_id': currency.id,
                'amount_currency': residual,
                'balance': residual,
                'name': _('Resultados de ejercicios anteriores sin cierre'),
            })

        name_close = _('Cierre de cuentas de balance')
        name_open = _('Reapertura de cuentas de balance')
        return [
            self._l10n_pe_move_vals(name_close, self.date_to, 'balance', [
                Command.create({'name': name_close, **line}) for line in closing_lines]),
            self._l10n_pe_move_vals(name_open, self.date_to + relativedelta(days=1), 'reopening', [
                Command.create({
                    'name': name_open, **line,
                    'amount_currency': -line['amount_currency'],
                    'balance': -line['balance'],
                }) for line in closing_lines]),
        ]

    def _l10n_pe_reconcile_reopening(self):
        moves = self._l10n_pe_get_closing_moves().filtered(lambda move: move.state == 'posted')
        closing = moves.filtered(lambda move: move.l10n_pe_closing_step == 'balance')
        reopening = moves.filtered(lambda move: move.l10n_pe_closing_step == 'reopening')
        if not (closing and reopening):
            return
        # Cada línea de reapertura es la inversa exacta de una línea de cierre
        # (misma cuenta, empresa y moneda, importes opuestos): se concilian de
        # dos en dos, también las que la moneda extranjera partió en dos.
        openings = defaultdict(list)
        for line in reopening.line_ids.filtered(lambda line: line.account_id.reconcile and not line.reconciled):
            openings[(line.account_id, line.partner_id, line.currency_id,
                      line.balance, line.amount_currency)].append(line)
        for line in closing.line_ids.filtered(lambda line: line.account_id.reconcile and not line.reconciled):
            key = (line.account_id, line.partner_id, line.currency_id, -line.balance, -line.amount_currency)
            if openings.get(key):
                (line | openings[key].pop()).reconcile()

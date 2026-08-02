# -*- coding: utf-8 -*-
"""Cierre mensual de tipo de cambio (Perú).

El ajuste de cada grupo (cuenta, o cuenta+socio si la cuenta se lleva con
detalle) se calcula sobre **saldos acumulados**::

    ajuste = saldo_ME_acumulado × T.C._cierre − saldo_MN_contabilizado

donde ambos saldos suman *todos* los apuntes publicados hasta la fecha de
cierre. Ese acumulado ya incluye:

* los ajustes de los cierres de meses anteriores (que llevan
  ``amount_currency = 0``: mueven soles pero no moneda extranjera), y
* las diferencias de cambio **realizadas** que Odoo genera al conciliar un
  cobro/pago con su factura (también con ``amount_currency = 0``).

Por eso la fórmula es auto-correctora: la diferencia que arroja es
exactamente la variación no reconocida desde el último cierre, sin
histórico paralelo de saldos y sin riesgo de duplicar el ajuste.
"""
import json
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command

from .analytic_tools import merge_analytic_distributions

MONTHS = [
    ('01', 'Enero'), ('02', 'Febrero'), ('03', 'Marzo'), ('04', 'Abril'),
    ('05', 'Mayo'), ('06', 'Junio'), ('07', 'Julio'), ('08', 'Agosto'),
    ('09', 'Septiembre'), ('10', 'Octubre'), ('11', 'Noviembre'),
    ('12', 'Diciembre'),
]


class L10nPeExchangeClosure(models.Model):
    _name = 'l10n_pe.exchange.closure'
    _inherit = ['analytic.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Cierre de tipo de cambio'
    _order = 'date desc, id desc'
    _check_company_auto = True

    # ------------------------------------------------------------------ #
    # Período                                                             #
    # ------------------------------------------------------------------ #
    name = fields.Char(
        string='Período', compute='_compute_name', store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True,
        default=lambda self: self.env.company)
    company_currency_id = fields.Many2one(
        related='company_id.currency_id', string='Moneda de la compañía')
    currency_id = fields.Many2one(
        'res.currency', string='Moneda extranjera', required=True,
        default=lambda self: self.env.ref('base.USD', raise_if_not_found=False),
        help='Moneda de las partidas a revaluar. En Perú, dólar americano.')
    month = fields.Selection(
        MONTHS, string='Mes', required=True,
        default=lambda self: '%02d' % fields.Date.context_today(self).month)
    year = fields.Integer(
        string='Año', required=True,
        default=lambda self: fields.Date.context_today(self).year)
    date = fields.Date(
        string='Fecha de cierre', compute='_compute_dates', store=True,
        help='Último día del mes: fecha del balance y del asiento de ajuste.')

    # ------------------------------------------------------------------ #
    # Tipo de cambio                                                      #
    # ------------------------------------------------------------------ #
    rate_day = fields.Selection(
        selection=[
            ('last', 'Último día del mes'),
            ('previous', 'Penúltimo día del mes'),
        ],
        string='T.C. del día', default='last', required=True,
        help='Fecha cuyo tipo de cambio se usa. SUNAT publica el T.C. del '
             'día siguiente al de la operación, por lo que algunas empresas '
             'toman el penúltimo día del mes como cierre.')
    rate_date = fields.Date(
        string='Fecha del T.C.', compute='_compute_dates', store=True)
    rate_purchase = fields.Float(
        string='T.C. compra', digits='Dual_Currency_TRM', tracking=True,
        help='Se aplica a las cuentas de activo (art. 34.d del Reglamento '
             'de la LIR).')
    rate_sale = fields.Float(
        string='T.C. venta', digits='Dual_Currency_TRM', tracking=True,
        help='Se aplica a las cuentas de pasivo (art. 34.d del Reglamento '
             'de la LIR).')

    # ------------------------------------------------------------------ #
    # Contabilización                                                     #
    # ------------------------------------------------------------------ #
    journal_id = fields.Many2one(
        'account.journal', string='Diario', check_company=True,
        domain="[('type', '=', 'general')]",
        default=lambda self: self.env.company.l10n_pe_exchange_closing_journal_id)
    move_id = fields.Many2one(
        'account.move', string='Asiento de ajuste', copy=False, readonly=True,
        check_company=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('computed', 'Calculado'),
            ('posted', 'Contabilizado'),
            ('cancel', 'Cancelado'),
        ],
        string='Estado', default='draft', required=True, tracking=True,
        copy=False)
    line_ids = fields.One2many(
        'l10n_pe.exchange.closure.line', 'closure_id', string='Detalle',
        copy=False)

    # ------------------------------------------------------------------ #
    # Analítica                                                           #
    # ------------------------------------------------------------------ #
    analytic_source = fields.Selection(
        selection=[
            ('origin', 'Heredada de los apuntes de origen'),
            ('fixed', 'Distribución fija de este cierre'),
            ('none', 'Sin analítica'),
        ],
        string='Analítica', default='origin', required=True,
        help='De dónde sale la distribución analítica del resultado por '
             'diferencia de cambio.\n'
             '· Heredada: cada renglón toma la analítica de los apuntes que '
             'forman su saldo (para las cuentas de balance, la de las líneas '
             'de ingreso o gasto de sus documentos), ponderada por importe. '
             'Es lo que hace que la diferencia de cambio de una factura caiga '
             'en el mismo centro de costo que la factura.\n'
             '· Fija: se aplica a todo el cierre la distribución indicada '
             'aquí.\n'
             '· Sin analítica: el asiento no genera apuntes analíticos.')

    # ------------------------------------------------------------------ #
    # Totales y vista previa                                              #
    # ------------------------------------------------------------------ #
    amount_gain = fields.Monetary(
        string='Ganancia', compute='_compute_amounts',
        currency_field='company_currency_id')
    amount_loss = fields.Monetary(
        string='Pérdida', compute='_compute_amounts',
        currency_field='company_currency_id')
    amount_net = fields.Monetary(
        string='Neto al resultado', compute='_compute_amounts',
        currency_field='company_currency_id',
        help='Ganancia menos pérdida: efecto neto en el resultado del mes.')
    preview_data = fields.Text(
        string='Vista previa', compute='_compute_preview_data')

    # ------------------------------------------------------------------ #
    # Cálculos                                                            #
    # ------------------------------------------------------------------ #
    @api.depends('month', 'year', 'currency_id')
    def _compute_name(self):
        labels = dict(MONTHS)
        for closure in self:
            if closure.month and closure.year:
                closure.name = '%s %s' % (labels[closure.month], closure.year)
            else:
                closure.name = '/'

    @api.depends('month', 'year', 'rate_day')
    def _compute_dates(self):
        for closure in self:
            if closure.month and closure.year:
                first = date(closure.year, int(closure.month), 1)
                last = first + relativedelta(months=1, days=-1)
                closure.date = last
                closure.rate_date = (
                    last if closure.rate_day == 'last'
                    else last - relativedelta(days=1))
            else:
                closure.date = False
                closure.rate_date = False

    @api.depends('line_ids.adjustment')
    def _compute_amounts(self):
        for closure in self:
            adjustments = closure.line_ids.mapped('adjustment')
            closure.amount_gain = sum(a for a in adjustments if a > 0)
            closure.amount_loss = sum(-a for a in adjustments if a < 0)
            closure.amount_net = closure.amount_gain - closure.amount_loss

    @api.depends('line_ids.adjustment', 'line_ids.analytic_distribution',
                 'journal_id', 'state')
    def _compute_preview_data(self):
        columns = [
            {'field': 'account_id', 'label': _('Cuenta')},
            {'field': 'partner_id', 'label': _('Socio')},
            {'field': 'name', 'label': _('Etiqueta')},
            {'field': 'debit', 'label': _('Debe'),
             'class': 'text-end text-nowrap'},
            {'field': 'credit', 'label': _('Haber'),
             'class': 'text-end text-nowrap'},
        ]
        for closure in self:
            if closure.state != 'computed' or not closure.journal_id:
                closure.preview_data = False
                continue
            move_vals = closure._get_move_vals()
            if not move_vals['line_ids']:
                closure.preview_data = False
                continue
            preview = self.env['account.move']._move_dict_to_preview_vals(
                move_vals, closure.company_currency_id)
            closure.preview_data = json.dumps({
                'groups_vals': [preview],
                'options': {'columns': columns},
            })

    @api.constrains('year')
    def _check_year(self):
        for closure in self:
            if not 1990 <= closure.year <= 2999:
                raise ValidationError(_('El año %s no es válido.', closure.year))

    @api.constrains('currency_id', 'company_id')
    def _check_currency(self):
        for closure in self:
            if closure.currency_id == closure.company_currency_id:
                raise ValidationError(_(
                    'La moneda del cierre debe ser distinta de la moneda de '
                    'la compañía.'))

    @api.constrains('company_id', 'currency_id', 'year', 'month', 'state')
    def _check_unique_period(self):
        """Un solo cierre vivo por mes, moneda y compañía.

        Los cancelados no cuentan: dejan rastro pero permiten rehacer el mes.
        """
        for closure in self:
            if closure.state == 'cancel':
                continue
            duplicate = self.search([
                ('company_id', '=', closure.company_id.id),
                ('currency_id', '=', closure.currency_id.id),
                ('year', '=', closure.year),
                ('month', '=', closure.month),
                ('state', '!=', 'cancel'),
                ('id', '!=', closure.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'Ya existe el cierre %(name)s para %(currency)s en esta '
                    'compañía.', name=duplicate.name,
                    currency=closure.currency_id.name))

    # ------------------------------------------------------------------ #
    # Tipo de cambio                                                      #
    # ------------------------------------------------------------------ #
    def _find_rate_record(self):
        """Último T.C. publicado en o antes de la fecha de cierre."""
        self.ensure_one()
        return self.env['res.currency.rate'].search([
            ('currency_id', '=', self.currency_id.id),
            ('company_id', 'in', (False, self.company_id.root_id.id)),
            ('name', '<=', self.rate_date),
        ], order='name desc', limit=1)

    def action_fetch_rate(self):
        """Trae el T.C. compra/venta de la fecha de cierre.

        Si no hay registro para esa fecha se intenta descargarlo (apis.net.pe
        vía ``al_l10n_pe_currency``) antes de tomar el último publicado.
        """
        for closure in self:
            closure._check_editable()
            if not closure.rate_date:
                raise UserError(_('Indique primero el mes y el año.'))
            rate = closure._find_rate_record()
            if not rate or rate.name != closure.rate_date:
                closure.currency_id.l10n_pe_update_date_apis(closure.rate_date)
                rate = closure._find_rate_record()
            if not rate:
                raise UserError(_(
                    'No hay ningún tipo de cambio registrado para %(currency)s '
                    'al %(date)s. Regístrelo manualmente en Contabilidad → '
                    'Configuración → Tipos de cambio.',
                    currency=closure.currency_id.name, date=closure.rate_date))
            # `rate` nativo va en "unidades de moneda extranjera por 1 de la
            # compañía"; su inversa es el T.C. tal como se lee en Perú.
            fallback = (1.0 / rate.rate) if rate.rate else 0.0
            closure.rate_purchase = rate.rate_purchase or fallback
            closure.rate_sale = rate.rate_sale or fallback
            if rate.name != closure.rate_date:
                closure.message_post(body=_(
                    'No había T.C. publicado al %(asked)s; se tomó el del '
                    '%(used)s.', asked=closure.rate_date, used=rate.name))
        return True

    # ------------------------------------------------------------------ #
    # Núcleo del cálculo                                                  #
    # ------------------------------------------------------------------ #
    def _get_aml_domain(self, mode=None):
        """Apuntes publicados en moneda extranjera hasta la fecha de cierre.

        Se excluye el propio asiento del cierre para que un recálculo tras
        cancelar no arrastre su ajuste anterior.
        """
        self.ensure_one()
        domain = [
            ('parent_state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
            ('date', '<=', self.date),
            ('currency_id', '=', self.currency_id.id),
            ('account_id.l10n_pe_exchange_closing', '!=', False),
        ]
        if mode:
            domain.append(('account_id.l10n_pe_exchange_closing', '=', mode))
        if self.move_id:
            domain.append(('move_id', '!=', self.move_id.id))
        return domain

    def _get_closing_groups(self):
        """Saldos acumulados agrupados según el modo de cada cuenta."""
        self.ensure_one()
        AML = self.env['account.move.line']
        # Los ids de los apuntes solo hacen falta para heredar la analítica;
        # en los demás modos se evita traerlos.
        with_origin = self.analytic_source == 'origin'
        aggregates = ['amount_currency:sum', 'balance:sum']
        if with_origin:
            aggregates.append('id:array_agg')
        groups = []
        for mode, groupby in (('summary', ['account_id']),
                              ('detail', ['account_id', 'partner_id'])):
            domain = self._get_aml_domain(mode)
            offset = len(groupby)
            for row in AML._read_group(domain, groupby, aggregates):
                groups.append({
                    'account': row[0],
                    'partner': (row[1] if mode == 'detail'
                                else self.env['res.partner']),
                    'amount_currency': row[offset],
                    'balance': row[offset + 1],
                    'aml_ids': row[offset + 2] if with_origin else [],
                })
        return groups

    def _get_group_analytic_distribution(self, group):
        """Distribución analítica que se llevará el resultado de este grupo.

        En modo «heredada» se combinan las distribuciones de los apuntes que
        forman el saldo, ponderadas por importe; si ninguno tiene analítica
        se usa la distribución fija del cierre como respaldo.
        """
        self.ensure_one()
        if self.analytic_source == 'none':
            return False
        if self.analytic_source == 'fixed':
            return self.analytic_distribution or False
        amls = self.env['account.move.line'].browse(group.get('aml_ids') or [])
        precision = self.env['decimal.precision'].precision_get(
            'Percentage Analytic')
        distribution = merge_analytic_distributions(
            [(aml._l10n_pe_closing_analytic_distribution(), aml.balance)
             for aml in amls],
            precision=precision)
        return distribution or self.analytic_distribution or False

    def _prepare_line_vals(self, group):
        """Convierte un grupo de saldos en los valores de una línea."""
        self.ensure_one()
        company_currency = self.company_currency_id
        account = group['account']
        rate_type = account._l10n_pe_closing_rate_type()
        rate = self.rate_purchase if rate_type == 'purchase' else self.rate_sale
        balance_adjusted = company_currency.round(
            group['amount_currency'] * rate)
        adjustment = company_currency.round(balance_adjusted - group['balance'])
        return {
            'account_id': account.id,
            'partner_id': group['partner'].id or False,
            'amount_currency': group['amount_currency'],
            'balance': group['balance'],
            'rate': rate,
            'rate_type': rate_type,
            'balance_adjusted': balance_adjusted,
            'adjustment': adjustment,
            'analytic_distribution': self._get_group_analytic_distribution(
                group),
        }

    def _check_editable(self):
        labels = dict(self._fields['state'].selection)
        for closure in self:
            if closure.state not in ('draft', 'computed'):
                raise UserError(_(
                    'El cierre %(name)s está en estado «%(state)s»: vuélvalo '
                    'a borrador para modificarlo.', name=closure.name,
                    state=labels[closure.state]))

    def _check_ready(self):
        """Validaciones previas al cálculo y a la contabilización."""
        self.ensure_one()
        if not self.journal_id:
            raise UserError(_(
                'Configure el diario del cierre de tipo de cambio en Perú → '
                'Configuración → Ajustes, o indíquelo en este cierre.'))
        if self.rate_purchase <= 0 or self.rate_sale <= 0:
            raise UserError(_(
                'Traiga o registre los tipos de cambio de compra y venta '
                'antes de calcular.'))
        company = self.company_id
        if not (company.income_currency_exchange_account_id
                and company.expense_currency_exchange_account_id):
            raise UserError(_(
                'Configure las cuentas de ganancia y pérdida por diferencia '
                'de cambio de la compañía %s.', company.display_name))
        later = self.search([
            ('company_id', '=', company.id),
            ('currency_id', '=', self.currency_id.id),
            ('state', '=', 'posted'),
            ('date', '>', self.date),
            ('id', '!=', self.id),
        ], limit=1)
        if later:
            raise UserError(_(
                'Existe un cierre posterior contabilizado (%s). Los cierres '
                'deben hacerse en orden cronológico: cancélelo antes de '
                'procesar un mes anterior.', later.name))

    # ------------------------------------------------------------------ #
    # Asiento                                                             #
    # ------------------------------------------------------------------ #
    def _get_move_vals(self):
        """Valores del asiento de ajuste (una línea por grupo con ajuste)."""
        self.ensure_one()
        company_currency = self.company_currency_id
        gloss = _('Cierre de tipo de cambio %s', self.name)
        move_lines = []
        # Contrapartidas agrupadas por (naturaleza, distribución analítica):
        # sin analítica quedan las dos líneas de siempre; con analítica se
        # abre una por cada distribución distinta.
        counterparts = {}
        for line in self.line_ids:
            adjustment = line.adjustment
            if company_currency.is_zero(adjustment):
                continue
            move_lines.append(Command.create({
                'name': gloss,
                'account_id': line.account_id.id,
                'partner_id': line.partner_id.id or False,
                'currency_id': self.currency_id.id,
                # El ajuste solo mueve moneda nacional: el saldo en moneda
                # extranjera no cambia, cambia su equivalente en soles.
                'amount_currency': 0.0,
                'debit': adjustment if adjustment > 0 else 0.0,
                'credit': -adjustment if adjustment < 0 else 0.0,
                'l10n_pe_gloss': gloss,
                'l10n_pe_closing_rate': line.rate,
                # Sin analítica en la línea de balance: el apunte analítico
                # se genera con signo contrario al de la contrapartida y
                # ambos se anularían entre sí.
            }))
            distribution = line.analytic_distribution or False
            key = (adjustment > 0,
                   json.dumps(distribution or {}, sort_keys=True))
            counterpart = counterparts.setdefault(
                key, {'amount': 0.0, 'distribution': distribution})
            counterpart['amount'] += abs(adjustment)

        # Contrapartida separada por naturaleza: la norma peruana informa la
        # ganancia y la pérdida por diferencia de cambio por separado.
        for (is_gain, _key), counterpart in sorted(
                counterparts.items(), key=lambda item: (not item[0][0],
                                                        item[0][1])):
            amount = company_currency.round(counterpart['amount'])
            if company_currency.is_zero(amount):
                continue
            account = (self.company_id.income_currency_exchange_account_id
                       if is_gain
                       else self.company_id.expense_currency_exchange_account_id)
            label = (_('Ganancia por diferencia de cambio %s', self.name)
                     if is_gain
                     else _('Pérdida por diferencia de cambio %s', self.name))
            move_lines.append(Command.create({
                'name': label,
                'account_id': account.id,
                'debit': 0.0 if is_gain else amount,
                'credit': amount if is_gain else 0.0,
                'l10n_pe_gloss': gloss,
                'analytic_distribution': counterpart['distribution'],
            }))
        return {
            'move_type': 'entry',
            'company_id': self.company_id.id,
            'journal_id': self.journal_id.id,
            'date': self.date,
            'ref': gloss,
            'l10n_pe_gloss': gloss,
            'l10n_pe_exchange_closure_id': self.id,
            'line_ids': move_lines,
        }

    # ------------------------------------------------------------------ #
    # Acciones                                                            #
    # ------------------------------------------------------------------ #
    def action_compute(self):
        for closure in self:
            closure._check_editable()
            closure._check_ready()
            closure.line_ids.unlink()
            company_currency = closure.company_currency_id
            vals = []
            for group in closure._get_closing_groups():
                line_vals = closure._prepare_line_vals(group)
                # Se descartan los grupos totalmente saldados (una factura ya
                # cobrada deja saldo cero en ambas monedas).
                if (company_currency.is_zero(line_vals['balance'])
                        and closure.currency_id.is_zero(
                            line_vals['amount_currency'])):
                    continue
                vals.append(Command.create(line_vals))
            closure.line_ids = vals
            closure.state = 'computed'
        return True

    def action_post(self):
        for closure in self:
            if closure.state != 'computed':
                raise UserError(_(
                    'Calcule el cierre %s antes de contabilizarlo.',
                    closure.name))
            closure._check_ready()
            move_vals = closure._get_move_vals()
            if not move_vals['line_ids']:
                raise UserError(_(
                    'No hay diferencia de cambio que ajustar en %s: los '
                    'saldos en moneda extranjera ya están valuados al tipo '
                    'de cambio de cierre.', closure.name))
            move = self.env['account.move'].with_company(
                closure.company_id).create(move_vals)
            move.action_post()
            closure.write({'move_id': move.id, 'state': 'posted'})
            closure.message_post(body=_(
                'Asiento de cierre %s contabilizado.', move.name))
        return True

    def action_cancel(self):
        for closure in self:
            if closure.move_id and closure.move_id.state != 'cancel':
                closure.move_id.button_draft()
                closure.move_id.button_cancel()
            closure.state = 'cancel'
        return True

    def action_draft(self):
        for closure in self:
            move = closure.move_id
            if move and move.state == 'posted':
                raise UserError(_(
                    'Cancele primero el cierre %s: su asiento sigue '
                    'contabilizado.', closure.name))
            closure.move_id = False
            if move:
                move.button_draft()
                move.unlink()
            closure.state = 'draft'
        return True

    def action_open_move(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'name': _('Asiento de cierre'),
        }

    # ------------------------------------------------------------------ #
    # Ciclo de vida                                                       #
    # ------------------------------------------------------------------ #
    @api.ondelete(at_uninstall=False)
    def _unlink_except_posted(self):
        if any(closure.state == 'posted' for closure in self):
            raise UserError(_(
                'No se puede eliminar un cierre contabilizado. Cancélelo '
                'primero.'))

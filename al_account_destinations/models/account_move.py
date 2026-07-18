# -*- coding: utf-8 -*-
"""Asiento de destino (dinámica de cuentas PE): al contabilizar un comprobante,
las cuentas de gasto por naturaleza (clase 6) se reflejan automáticamente en
cuentas por función/destino (clase 9), o viceversa, usando la cuenta de carga
(78/79) como contrapartida.

Refactor v19: se eliminó la red de seguridad de balance (el bloque generado ya
cuadra por diseño) y el código de depuración. Campos y modelos prefijados con
`l10n_pe_` según la convención de localización. La glosa y `l10n_pe_is_pe()` se
heredan del módulo base `al_account_base`.
"""
import logging

from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_round

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_is_destiny_entry = fields.Boolean(
        string='Es asiento de destino', default=False, copy=False, readonly=True,
        help='Marca los asientos generados automáticamente por la dinámica de '
             'destinos (no se procesan de nuevo).')
    l10n_pe_destiny_move_id = fields.Many2one(
        'account.move', string='Asiento de destino', readonly=True, copy=False,
        ondelete='cascade')
    l10n_pe_origin_move_id = fields.Many2one(
        'account.move', string='Comprobante de origen', readonly=True, copy=False,
        ondelete='cascade')

    # ------------------------------------------------------------------ #
    # Ciclo de vida: propagar borrador/cancelación al asiento de destino  #
    # ------------------------------------------------------------------ #

    def button_draft(self):
        res = super().button_draft()
        for move in self:
            destiny = move.l10n_pe_destiny_move_id
            if destiny and destiny.state not in ('draft', 'cancel'):
                destiny.button_draft()
        return res

    def button_cancel(self):
        res = super().button_cancel()
        for move in self:
            destiny = move.l10n_pe_destiny_move_id
            if destiny and destiny.state != 'cancel':
                destiny.button_cancel()
        return res

    def _post(self, soft=True):
        posted = super()._post(soft)
        # No reprocesar el propio asiento de destino (evita recursión).
        for move in posted.filtered(lambda m: m.l10n_pe_is_pe() and not m.l10n_pe_is_destiny_entry):
            move._l10n_pe_create_destiny_entry()
        return posted

    # ------------------------------------------------------------------ #
    # Generación del asiento de destino                                   #
    # ------------------------------------------------------------------ #

    def _l10n_pe_get_ga_journal(self):
        """Diario 'Gastos Automáticos' (GA); se crea si no existe."""
        self.ensure_one()
        Journal = self.env['account.journal']
        journal = Journal.search(
            [('code', '=', 'GA'), ('company_id', '=', self.company_id.id)], limit=1)
        if not journal:
            journal = Journal.create({
                'name': 'Gastos Automáticos', 'type': 'general',
                'code': 'GA', 'company_id': self.company_id.id,
            })
        return journal

    def _l10n_pe_create_destiny_entry(self):
        """Crea (o regenera) el asiento de destino de este comprobante."""
        self.ensure_one()
        line_vals = self._l10n_pe_get_destiny_lines()
        if not line_vals:
            return
        move_vals = {
            'move_type': 'entry',
            'ref': _('Destino: %s', self.name),
            'date': self.date,
            'partner_id': self.partner_id.id,
            'journal_id': self._l10n_pe_get_ga_journal().id,
            'l10n_pe_origin_move_id': self.id,
            'company_id': self.company_id.id,
            'l10n_pe_is_destiny_entry': True,
            'line_ids': line_vals,
        }
        if self.l10n_pe_destiny_move_id:
            destiny = self.l10n_pe_destiny_move_id
            if destiny.state != 'draft':
                destiny.button_draft()
            destiny.line_ids.unlink()
            destiny.write(dict(move_vals, name=False))
        else:
            destiny = self.create(move_vals)
        destiny.action_post()
        self.l10n_pe_destiny_move_id = destiny.id

    def _l10n_pe_get_destiny_lines(self):
        """Líneas del asiento de destino, generadas por cada línea de origen
        cuya cuenta trabaja con destinos."""
        self.ensure_one()
        line_vals = []
        for line in self.line_ids:
            account = line.account_id
            if account.l10n_pe_work_destinies and not account.l10n_pe_no_destiny:
                line_vals.extend(self._l10n_pe_build_destiny_lines(line))
        return line_vals

    def _l10n_pe_build_destiny_lines(self, line):
        """Genera las líneas de distribución (auto-balanceadas) para una línea
        de origen: reparte su importe entre las cuentas destino según su
        porcentaje y contabiliza la contrapartida en la cuenta de carga."""
        self.ensure_one()
        account = line.account_id
        dest_lines = account.l10n_pe_destiny_ids
        if not dest_lines:
            raise ValidationError(_(
                'La cuenta %s trabaja con destinos pero no tiene cuentas de '
                'destino configuradas.\nConfigúrelas (o active "Desactivar '
                'destinos" en la cuenta).', account.code))
        if not account.l10n_pe_load_account_id:
            raise ValidationError(_(
                'No existe una cuenta de carga para la cuenta: %s', account.code))
        account.l10n_pe_check_destiny_percentage()

        currency = line.currency_id or line.company_currency_id
        base_amount = line.debit - line.credit
        is_debit = base_amount >= 0
        base_abs = abs(base_amount)

        vals = []
        distributed = 0.0
        last = len(dest_lines) - 1
        for i, dest in enumerate(dest_lines):
            if i == last:
                amount = base_abs - distributed  # remanente exacto → cuadre
            else:
                amount = float_round(base_abs * dest.percentage,
                                     precision_rounding=currency.rounding)
            distributed += amount
            vals.append(self._l10n_pe_prepare_line(line, dest.dest_account_id, amount, is_debit))
        # Contrapartida: cuenta de carga con el signo opuesto por el total.
        vals.append(self._l10n_pe_prepare_line(
            line, account.l10n_pe_load_account_id, base_abs, not is_debit))
        return [(0, 0, v) for v in vals]

    def _l10n_pe_prepare_line(self, line, account, amount, is_debit):
        currency = line.currency_id or line.company_currency_id
        amount = abs(amount)
        return {
            'name': self.name or _('Distribución de destino'),
            'account_id': account.id,
            'partner_id': self.partner_id.id,
            'debit': amount if is_debit else 0.0,
            'credit': 0.0 if is_debit else amount,
            'currency_id': currency.id,
            'amount_currency': amount if is_debit else -amount,
        }

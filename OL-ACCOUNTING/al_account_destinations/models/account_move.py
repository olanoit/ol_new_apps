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
    # Sin cascada en la base de datos: un ``ON DELETE CASCADE`` borraría el
    # comprobante de origen (publicado) al eliminar su asiento de destino, y
    # viceversa, saltándose los controles del ORM. El asiento de destino se
    # elimina por el ORM en ``unlink``.
    l10n_pe_destiny_move_id = fields.Many2one(
        'account.move', string='Asiento de destino', readonly=True, copy=False,
        ondelete='set null')
    l10n_pe_origin_move_id = fields.Many2one(
        'account.move', string='Comprobante de origen', readonly=True, copy=False,
        ondelete='set null')

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

    def unlink(self):
        # Al eliminar el comprobante de origen se elimina también su asiento
        # de destino, por el ORM: si este sigue publicado, el borrado se
        # rechaza con el control nativo.
        destinies = self.l10n_pe_destiny_move_id - self
        if destinies:
            destinies.unlink()
        return super().unlink()

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
        # sudo: quien publica una factura (grupo Facturación) no tiene permiso
        # de crear diarios; el diario GA es infraestructura de la dinámica de
        # destinos y se crea una sola vez por compañía.
        journal_sudo = self.env['account.journal'].sudo().search(
            [('code', '=', 'GA'), ('company_id', '=', self.company_id.id)], limit=1)
        if not journal_sudo:
            journal_sudo = journal_sudo.create({
                'name': 'Gastos Automáticos', 'type': 'general',
                'code': 'GA', 'company_id': self.company_id.id,
            })
        return journal_sudo.sudo(False)

    def _l10n_pe_create_destiny_entry(self):
        """Crea (o regenera) el asiento de destino de este comprobante."""
        self.ensure_one()
        line_vals = self._l10n_pe_get_destiny_lines()
        if not line_vals:
            # Ya no hay nada que distribuir (p. ej. se cambió la cuenta 6 por
            # otra sin destino): el destino anterior no puede quedar vivo.
            destiny = self.l10n_pe_destiny_move_id
            if destiny:
                if destiny.state == 'posted':
                    destiny.button_draft()
                if destiny.state == 'draft':
                    destiny.button_cancel()
                self.l10n_pe_destiny_move_id = False
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
            # Se conserva el número: borrarlo hacía que cada republicación
            # consumiera uno nuevo del diario GA y dejara huecos en el
            # correlativo del Libro Diario. Solo se renumera si cambió el
            # periodo de la fecha.
            destiny.write(move_vals)
            if destiny.name and destiny.name != '/' and not destiny._sequence_matches_date():
                destiny.name = False
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
            # La dinámica (6→9 o 9→6) y el código de la cuenta dependen de la
            # compañía: se evalúan en la del comprobante, no en la activa.
            account = line.account_id.with_company(self.company_id)
            if account.l10n_pe_work_destinies and not account.l10n_pe_no_destiny:
                line_vals.extend(self._l10n_pe_build_destiny_lines(line))
        return line_vals

    def _l10n_pe_build_destiny_lines(self, line):
        """Genera las líneas de distribución (auto-balanceadas) para una línea
        de origen: reparte su importe entre las cuentas destino según su
        porcentaje y contabiliza la contrapartida en la cuenta de carga."""
        self.ensure_one()
        account = line.account_id.with_company(self.company_id)
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

        # El asiento de destino se lleva en la moneda de la compañía: reparte
        # el importe en soles (debe/haber) de la línea de origen.
        currency = line.company_currency_id
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
            vals.append(self._l10n_pe_prepare_line(
                line, dest.dest_account_id, amount, is_debit,
                # la analítica (centro de costo) acompaña al destino, no a la carga 79
                analytic_distribution=line.analytic_distribution))
        # Contrapartida: cuenta de carga con el signo opuesto por el total.
        vals.append(self._l10n_pe_prepare_line(
            line, account.l10n_pe_load_account_id, base_abs, not is_debit))
        return [(0, 0, v) for v in vals]

    def _l10n_pe_prepare_line(self, line, account, amount, is_debit, analytic_distribution=None):
        # Moneda de la compañía: con la divisa del comprobante, el
        # ``amount_currency`` explícito quedaría con el importe en soles.
        currency = line.company_currency_id
        amount = abs(amount)
        return {
            'name': self.name or _('Distribución de destino'),
            'account_id': account.id,
            'partner_id': self.partner_id.id,
            'debit': amount if is_debit else 0.0,
            'credit': 0.0 if is_debit else amount,
            'currency_id': currency.id,
            'amount_currency': amount if is_debit else -amount,
            'analytic_distribution': analytic_distribution or False,
        }

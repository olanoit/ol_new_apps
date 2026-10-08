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
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round

from .account_account import PERCENTAGE_TOLERANCE

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

    def _l10n_pe_get_destination_journal(self):
        """Diario de destinos configurado en Ajustes ▸ Perú (el de la compañía
        o, en una sucursal, el de su raíz). No se busca ni se crea ningún
        diario por su código interno: lo elige el usuario."""
        self.ensure_one()
        journal = self.company_id.l10n_pe_destination_journal_id \
            or self.company_id.root_id.l10n_pe_destination_journal_id
        if not journal:
            raise UserError(_(
                'Configure el diario de los asientos de destino de %s en '
                'Ajustes ▸ Perú ▸ Asientos de destino.', self.company_id.name))
        return journal

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
            'journal_id': self._l10n_pe_get_destination_journal().id,
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
            # La dinámica (6→9 o 9→6), el código de la cuenta y su reparto
            # dependen de la compañía: se evalúan en la del comprobante (y,
            # como el código, en su compañía raíz).
            account = line.account_id.with_company(self.company_id)
            if account.l10n_pe_work_destinies and not account.l10n_pe_no_destiny:
                line_vals.extend(self._l10n_pe_build_destiny_lines(line))
        return line_vals

    def _l10n_pe_destination_portions(self, line):
        """Reparto de una línea de origen: ``[(cuenta destino, fracción,
        distribución analítica)]`` que suma 1.

        1. La parte distribuida a cuentas analíticas con cuenta de destino
           (centros de costo) va a esa cuenta, con su analítica.
        2. El resto, al reparto por cuenta (porcentajes de la cuenta 6).
        Sin ninguna de las dos configuraciones no hay destino (lista vacía).
        """
        self.ensure_one()
        account = line.account_id.with_company(self.company_id)
        distribution = line.analytic_distribution or {}
        analytic_ids = {int(aid) for key in distribution for aid in key.split(',') if aid}
        analytics = self.env['account.analytic.account'].browse(analytic_ids).exists()
        destination_of = {a.id: a.l10n_pe_destination_account_id
                          for a in analytics if a.l10n_pe_destination_account_id}
        portions, covered, rest_distribution = [], 0.0, {}
        for key, pct in distribution.items():
            targets = [destination_of[int(aid)] for aid in key.split(',')
                       if aid and int(aid) in destination_of]
            if targets:
                portions.append((targets[0], pct / 100.0, {key: 100.0}))
                covered += pct / 100.0
            else:
                rest_distribution[key] = pct
        if covered > 1.0 + PERCENTAGE_TOLERANCE:
            # Varios planes en claves separadas pueden sumar más del 100 %:
            # el reparto de destino se normaliza sobre lo que sí tiene destino.
            portions = [(dest, fraction / covered, analytic)
                        for dest, fraction, analytic in portions]
            covered = 1.0
        rest = 1.0 - covered
        if rest > PERCENTAGE_TOLERANCE:
            dest_lines = account.l10n_pe_destiny_ids
            if not dest_lines:
                if portions:
                    raise ValidationError(_(
                        'El %(pct).2f%% del importe de la cuenta %(code)s no tiene '
                        'destino: su distribución analítica no usa centros de '
                        'costo con cuenta de destino y la cuenta no tiene un '
                        'reparto propio.', pct=rest * 100, code=account.code))
                return []
            account.l10n_pe_check_destiny_percentage()
            # La analítica que no decide el destino acompaña al resto.
            total_rest = sum(rest_distribution.values())
            analytic = ({key: pct * 100.0 / total_rest for key, pct in rest_distribution.items()}
                        if total_rest else False)
            for dest in dest_lines:
                portions.append((dest.dest_account_id, rest * dest.percentage, analytic))
        return portions

    def _l10n_pe_build_destiny_lines(self, line):
        """Genera las líneas de distribución (auto-balanceadas) para una línea
        de origen: reparte su importe entre las cuentas destino y contabiliza
        la contrapartida en la cuenta de carga."""
        self.ensure_one()
        account = line.account_id.with_company(self.company_id)
        portions = self._l10n_pe_destination_portions(line)
        if not portions:
            return []
        load_account = account.l10n_pe_load_account_id \
            or self.company_id.l10n_pe_destination_load_account_id
        if not load_account:
            raise ValidationError(_(
                'No hay cuenta de carga para la cuenta %s: indique la cuenta de '
                'carga por defecto (791) en Ajustes ▸ Perú o una propia en la cuenta.',
                account.code))

        # El asiento de destino se lleva en la moneda de la compañía: reparte
        # el importe en soles (debe/haber) de la línea de origen.
        currency = line.company_currency_id
        base_amount = line.debit - line.credit
        is_debit = base_amount >= 0
        base_abs = abs(base_amount)

        vals = []
        distributed = 0.0
        last = len(portions) - 1
        for i, (dest_account, fraction, analytic) in enumerate(portions):
            if i == last:
                amount = base_abs - distributed  # remanente exacto → cuadre
            else:
                amount = float_round(base_abs * fraction,
                                     precision_rounding=currency.rounding)
            distributed += amount
            # la analítica (centro de costo) acompaña al destino, no a la carga 79
            vals.append(self._l10n_pe_prepare_line(
                line, dest_account, amount, is_debit, analytic_distribution=analytic))
        vals.append(self._l10n_pe_prepare_line(
            line, load_account, base_abs, not is_debit))
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

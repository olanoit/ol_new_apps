"""Versión 8:

1. Configura las cuentas de letras del PCGE en las compañías que no las tienen
   (solo combinaciones faltantes).
2. Enlaza a su letra el apunte de destino (cobranza o descuento) de los envíos
   al banco anteriores: sin el vínculo, la letra aparecía «Pagado» aunque el
   cliente no hubiera pagado. Se identifica por el número de letra y el mismo
   signo que el apunte de la letra en el canje.
3. Las letras sin tipo pasan a «En cartera».
"""
from odoo import SUPERUSER_ID, api


def link_bank_lines(env):
    letters = env['l10n_pe.letter'].search([
        '|', ('canje_move_id', '!=', False), ('canje_move_ids', '!=', False)])
    fixed = env['l10n_pe.letter.line']
    for letter in letters:
        for move in letter.canje_move_id | letter.canje_move_ids:
            for letter_line in letter.letter_line_ids:
                counter = letter.account_id.line_ids.filtered(
                    lambda l: l.l10n_pe_letter_line_id == letter_line)
                sign = sum(counter.mapped('amount_currency'))
                destination = move.line_ids.filtered(
                    lambda l: not l.l10n_pe_letter_line_id and l.name == letter_line.nro_letter
                    and l.amount_currency * sign > 0)
                if destination:
                    destination.write({'l10n_pe_letter_line_id': letter_line.id})
                    fixed |= letter_line
    if fixed:
        fixed._compute_payment_state()
        env.add_to_compute(fixed._fields['adeudado'], fixed)
        fixed.flush_recordset()
    return fixed


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['l10n_pe.letter.account.config']._l10n_pe_create_default_configs()
    link_bank_lines(env)
    # 3. Las letras sin tipo están en cartera (antes no tenían valor por defecto).
    env['l10n_pe.letter.line'].search([('letter_type', '=', False)]).write(
        {'letter_type': 'portfolio'})

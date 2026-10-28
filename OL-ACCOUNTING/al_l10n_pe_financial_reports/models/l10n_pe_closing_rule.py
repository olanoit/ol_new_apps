# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

PREFIXES_RE = re.compile(r'^\s*\d+(\s*,\s*\d+)*\s*$')


class L10nPeClosingRule(models.Model):
    """Paso del asiento de cierre del ejercicio.

    Cada regla salda las cuentas cuyo código empieza por alguno de sus
    prefijos y lleva el neto a la cuenta destino. Las reglas se aplican en
    orden y cada una ve los saldos que dejaron las anteriores, así que un
    prefijo amplio en una regla posterior solo recoge lo que quedó.
    """
    _name = 'l10n_pe.closing.rule'
    _description = 'Regla del cierre del ejercicio (Perú)'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Paso', required=True, translate=True)
    source_prefixes = fields.Char(
        string='Cuentas que salda', required=True,
        help='Prefijos de código separados por comas, por ejemplo «62,64». '
             'Solo se saldan cuentas de resultados y de las clases 8 y 9.')
    target_code = fields.Char(
        string='Cuenta destino', required=True,
        help='Código exacto de la cuenta que recibe el neto, por ejemplo '
             '«821».')
    loss_code = fields.Char(
        string='Cuenta destino si es pérdida',
        help='Si se indica, el neto deudor (pérdida) va a esta cuenta y el '
             'acreedor (utilidad) a la cuenta destino. Por ejemplo 892 frente '
             'a 891.')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía',
        domain="[('parent_id', '=', False)]",
        help='Vacía: la regla vale para todos los RUC de la base. Con '
             'compañía: solo para ese RUC (se elige la raíz).')

    @api.constrains('source_prefixes', 'target_code', 'loss_code')
    def _check_codes(self):
        for rule in self:
            if not PREFIXES_RE.match(rule.source_prefixes or ''):
                raise ValidationError(_(
                    'La regla «%(rule)s»: las cuentas que salda deben ser '
                    'prefijos numéricos separados por comas.', rule=rule.name))
            for code in (rule.target_code, rule.loss_code):
                if code and not code.strip().isdigit():
                    raise ValidationError(_(
                        'La regla «%(rule)s»: la cuenta destino debe ser un '
                        'código numérico.', rule=rule.name))

    def _get_source_prefixes(self):
        self.ensure_one()
        return tuple(prefix.strip() for prefix in self.source_prefixes.split(',') if prefix.strip())

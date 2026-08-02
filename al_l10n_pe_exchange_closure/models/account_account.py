# -*- coding: utf-8 -*-
"""Marcado de las cuentas que entran al cierre de tipo de cambio.

Solo son elegibles las cuentas de balance (activo y pasivo): la diferencia
de cambio se calcula sobre partidas monetarias, no sobre resultados. Odoo
no distingue "monetario / no monetario", así que la selección es manual —
p. ej. 104 Bancos ME, 121 Facturas por cobrar ME o 421 Facturas por pagar
ME entran; 33 Inmuebles (no monetario) no.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Grupos internos que admiten ajuste por diferencia de cambio.
MONETARY_GROUPS = ('asset', 'liability')


class AccountAccount(models.Model):
    _inherit = 'account.account'

    l10n_pe_exchange_closing = fields.Selection(
        selection=[
            ('summary', 'Sin detalle (consolidado por cuenta)'),
            ('detail', 'Con detalle (por socio)'),
        ],
        string='Cierre de tipo de cambio',
        help='Incluye la cuenta en el cierre mensual de tipo de cambio.\n'
             '· Sin detalle: un solo apunte de ajuste por cuenta (caja, '
             'bancos, préstamos).\n'
             '· Con detalle: un apunte por socio, para poder conciliar el '
             'ajuste con el documento (cuentas por cobrar y por pagar).')
    l10n_pe_exchange_rate_type = fields.Selection(
        selection=[
            ('auto', 'Automático (activo → compra / pasivo → venta)'),
            ('purchase', 'Siempre compra'),
            ('sale', 'Siempre venta'),
        ],
        string='T.C. a aplicar', default='auto', required=True,
        help='Regla del art. 34.d del Reglamento de la LIR: los activos se '
             'ajustan al T.C. compra y los pasivos al T.C. venta. El '
             'automático lo deduce del tipo de cuenta; el forzado sirve '
             'para cuentas de enlace cuya naturaleza real es la contraria.')
    l10n_pe_exchange_closing_eligible = fields.Boolean(
        string='Admite cierre de T.C.', compute='_compute_l10n_pe_eligible',
        store=True,
        help='Verdadero para las cuentas de activo y pasivo, las únicas que '
             'pueden mantener partidas monetarias en moneda extranjera.')

    @api.depends('internal_group')
    def _compute_l10n_pe_eligible(self):
        for account in self:
            account.l10n_pe_exchange_closing_eligible = (
                account.internal_group in MONETARY_GROUPS)

    @api.constrains('l10n_pe_exchange_closing', 'account_type')
    def _check_l10n_pe_exchange_closing(self):
        for account in self:
            if (account.l10n_pe_exchange_closing
                    and account.internal_group not in MONETARY_GROUPS):
                raise ValidationError(_(
                    'La cuenta %(account)s no es de activo ni de pasivo, no '
                    'puede entrar al cierre de tipo de cambio.',
                    account=account.display_name))

    @api.onchange('l10n_pe_exchange_closing')
    def _onchange_l10n_pe_exchange_closing(self):
        # Sin marca de cierre el tipo de T.C. no aplica: se devuelve al valor
        # por defecto para no dejar configuraciones huérfanas.
        if not self.l10n_pe_exchange_closing:
            self.l10n_pe_exchange_rate_type = 'auto'

    def _l10n_pe_closing_rate_type(self):
        """Devuelve 'purchase' o 'sale' según la naturaleza de la cuenta."""
        self.ensure_one()
        if self.l10n_pe_exchange_rate_type in ('purchase', 'sale'):
            return self.l10n_pe_exchange_rate_type
        return 'purchase' if self.internal_group == 'asset' else 'sale'

# -*- coding: utf-8 -*-
from odoo import fields, models

# Sentido de la dinámica de destinos (PCGE peruano).
L10N_PE_DEST_TYPE_SELECTION = [
    ('6a9', 'Destino de cuenta clase 6 a 9'),
    ('9a6', 'Destino de cuenta clase 9 a 6'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_dest_type = fields.Selection(
        selection=L10N_PE_DEST_TYPE_SELECTION,
        string='Tipo de destino', required=True, default='6a9',
        help='Sentido del asiento de destino: de gasto por naturaleza (6) a '
             'función (9), que es lo que indica el PCGE, o viceversa para quien '
             'registra por función.')
    l10n_pe_destination_journal_id = fields.Many2one(
        'account.journal', string='Diario de destinos', check_company=True,
        domain="[('type', '=', 'general')]",
        help='Diario de los asientos de destino (tipo Varios). Obligatorio para '
             'generar destinos; se elige en Ajustes ▸ Perú.')
    l10n_pe_destination_load_account_id = fields.Many2one(
        'account.account', string='Cuenta de carga por defecto', check_company=True,
        domain="['|', '|', ('code', '=like', '72%'), ('code', '=like', '78%'), ('code', '=like', '79%')]",
        help='Contrapartida del asiento de destino (normalmente 791 Cargas '
             'imputables a cuentas de costos y gastos). Una cuenta puede '
             'indicar otra (78, 72) en su configuración de destinos.')

    def _get_company_root_delegated_field_names(self):
        # El sentido y la carga son del RUC, como el plan de cuentas: Odoo los
        # copia a las sucursales y los muestra de solo lectura. El diario sí
        # puede ser propio de cada sucursal.
        return super()._get_company_root_delegated_field_names() + [
            'l10n_pe_dest_type',
            'l10n_pe_destination_load_account_id',
        ]

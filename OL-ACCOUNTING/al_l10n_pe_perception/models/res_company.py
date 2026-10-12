# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_perception_agent = fields.Boolean(
        string='Agente de percepción (venta interna)',
        help='La compañía fue designada agente de percepción del IGV en la venta interna de '
             'los bienes del Apéndice 1 de la Ley 29173 (R.S. 058-2006/SUNAT).')
    l10n_pe_perception_fuel_agent = fields.Boolean(
        string='Agente de percepción (combustibles)',
        help='La compañía fue designada agente de percepción del IGV en la venta de '
             'combustibles líquidos derivados del petróleo (R.S. 128-2002/SUNAT).')
    l10n_pe_perception_account_id = fields.Many2one(
        'account.account', string='Cuenta del IGV percibido por pagar',
        check_company=True,
        help='Pasivo con SUNAT por las percepciones cobradas a los clientes (se declara y '
             'paga con el F.V. 697).')
    l10n_pe_perception_journal_id = fields.Many2one(
        'account.journal', string='Diario de percepciones',
        check_company=True, domain=[('type', '=', 'general')],
        help='Diario del asiento de cada comprobante de percepción emitido.')
    l10n_pe_perception_sequence_id = fields.Many2one(
        'ir.sequence', string='Numeración de los comprobantes de percepción',
        check_company=True, copy=False,
        help='Serie P001 del comprobante de percepción electrónico. Se crea al emitir el '
             'primero si está vacía.')
    l10n_pe_perception_received_account_id = fields.Many2one(
        'account.account', string='Cuenta de percepciones por aplicar',
        check_company=True,
        help='IGV – Régimen de percepciones: crédito por las percepciones que nos cobran '
             'los proveedores y la Aduana, que se aplica en el F.V. 621.')
    l10n_pe_perception_received_journal_id = fields.Many2one(
        'account.journal', string='Diario de percepciones que nos cobran',
        check_company=True, domain=[('type', '=', 'general')])

    def _get_company_root_delegated_field_names(self):
        # SUNAT designa agente de percepción al RUC: las sucursales llevan la
        # condición de su compañía raíz.
        return super()._get_company_root_delegated_field_names() + [
            'l10n_pe_perception_agent',
            'l10n_pe_perception_fuel_agent',
        ]

    def _l10n_pe_perception_sequence(self):
        """Secuencia de la serie P001 del RUC (la de la compañía raíz, para que
        las sucursales no repitan números); se crea la primera vez."""
        self.ensure_one()
        root = self.root_id or self
        if not root.l10n_pe_perception_sequence_id:
            # sudo: el contador que emite crea una sola vez la secuencia de su
            # RUC, aunque no administre las secuencias ni la compañía raíz.
            root_sudo = root.sudo()
            root_sudo.l10n_pe_perception_sequence_id = self.env['ir.sequence'].sudo().create({
                'name': self.env._('Comprobantes de percepción (%s)', root.name),
                'code': 'al_l10n_pe_perception.cpe',
                'prefix': 'P001-',
                'padding': 8,
                'company_id': root.id,
            })
        # sudo: la secuencia es de la compañía raíz, que el usuario de una
        # sucursal puede no tener entre sus compañías permitidas.
        return root.sudo().l10n_pe_perception_sequence_id


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_perception_agent = fields.Boolean(
        related='company_id.l10n_pe_perception_agent', readonly=False)
    l10n_pe_perception_fuel_agent = fields.Boolean(
        related='company_id.l10n_pe_perception_fuel_agent', readonly=False)
    l10n_pe_perception_account_id = fields.Many2one(
        related='company_id.l10n_pe_perception_account_id', readonly=False)
    l10n_pe_perception_journal_id = fields.Many2one(
        related='company_id.l10n_pe_perception_journal_id', readonly=False)
    l10n_pe_perception_received_account_id = fields.Many2one(
        related='company_id.l10n_pe_perception_received_account_id', readonly=False)
    l10n_pe_perception_received_journal_id = fields.Many2one(
        related='company_id.l10n_pe_perception_received_journal_id', readonly=False)

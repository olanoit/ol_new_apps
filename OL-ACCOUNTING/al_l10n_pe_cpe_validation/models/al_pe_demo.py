# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import Command, api, fields, models


class AlPeDemo(models.AbstractModel):
    _inherit = 'al.pe.demo'

    @api.model
    def _load_demo_cpe_validation(self):
        """Tres facturas de proveedor en borrador con el resultado de la
        consulta a SUNAT ya registrado (válido, observado y no informado);
        no se llama a SUNAT."""
        company = self._demo_company()
        if not company:
            return
        env = self._demo_env(company)
        journal = env['account.journal'].search([
            *env['account.journal']._check_company_domain(company), ('type', '=', 'purchase'),
            ('l10n_latam_use_documents', '=', True)], limit=1)
        if not journal:
            return
        day = fields.Date.context_today(self) - timedelta(days=7)
        rows = [
            ('1', 'Distribuidora S.A.C.', '2061000111', 'F001-00004521', 2000.0,
             {'estadoCp': '1', 'estadoRuc': '00', 'condDomiRuc': '00', 'observaciones': []}),
            ('2', 'Servicios Generales E.I.R.L.', '2061000222', 'F002-00000318', 711.86,
             {'estadoCp': '1', 'estadoRuc': '00', 'condDomiRuc': '12', 'observaciones': []}),
            ('3', 'Importaciones S.R.L.', '2061000333', 'F001-00009910', 1000.0,
             {'estadoCp': '0', 'estadoRuc': '00', 'condDomiRuc': '00',
              'observaciones': ['- El comprobante de pago consultado no ha sido informado a SUNAT.']}),
        ]
        tax = self._demo_tax(env, 'purchase')
        for key, name, body, number, amount, data in rows:
            xmlid = 'al_l10n_pe_cpe_validation.demo_bill_%s' % key
            if self._demo_ref(xmlid):
                continue
            partner = self._demo_partner(env, 'al_l10n_pe_cpe_validation.demo_vendor_%s' % key, name,
                                         self._demo_ruc(body))
            move = self._demo_record(xmlid, env['account.move'], {
                'move_type': 'in_invoice', 'partner_id': partner.id, 'journal_id': journal.id,
                'invoice_date': day, 'l10n_latam_document_type_id': env.ref('l10n_pe.document_type01').id,
                'l10n_latam_document_number': number,
                'invoice_line_ids': [Command.create({'name': 'Mercadería', 'quantity': 1,
                                                     'price_unit': amount, 'tax_ids': [Command.set(tax.ids)]})],
            })
            move._l10n_pe_cpe_apply(data)

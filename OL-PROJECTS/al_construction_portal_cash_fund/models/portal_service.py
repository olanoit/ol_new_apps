# -*- coding: utf-8 -*-
"""Caja chica y entrega a rendir del residente en el portal (paquete 6,
CR-55).

El fondo es de un contacto (``l10n_pe.cash.fund.partner_id``): el residente lo
usa con o sin ficha de empleado. Cada comprobante es la factura del
proveedor en borrador con la analítica de la obra; «Rendir» arma la rendición
del fondo en borrador. Contabilidad publica los comprobantes y confirma la
rendición en el escritorio."""
import re

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError

#: Comprobantes que el residente registra (catálogo 10 de SUNAT): factura,
#: recibo por honorarios, boleta, ticket y recibo de servicios públicos.
DOCUMENT_CODES = ('01', '02', '03', '12', '14')
RUC = re.compile(r'^\d{11}$')


class ConstructionPortalService(models.AbstractModel):
    _inherit = 'construction.portal.service'

    def _resident_features(self):
        features = super()._resident_features()
        features['expense'] = True
        return features

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------
    def _resident_funds(self, company):
        """Fondos entregados al residente (a su contacto o a su empresa)."""
        partner = self.env.user.partner_id
        # sudo: solo los fondos del contacto del residente.
        return self.env['l10n_pe.cash.fund'].sudo().search([
            ('partner_id', 'in', (partner | partner.commercial_partner_id).ids),
            ('state', '=', 'open'), ('company_id', '=', company.id)], order='date desc, id desc')

    def _fund_receipts(self, fund):
        # sudo: los comprobantes que el residente registró con ese fondo.
        return self.env['account.move'].sudo().search([
            ('construction_portal_fund_id', '=', fund.id), ('move_type', '=', 'in_invoice'),
            ('state', '!=', 'cancel')], order='invoice_date desc, id desc')

    def _receipt_settlement(self, move):
        # sudo: la rendición del fondo que lleva el comprobante.
        return self.env['l10n_pe.cash.settlement.document'].sudo().search([
            ('move_id', '=', move.id), ('settlement_id.state', '!=', 'cancel')],
            limit=1).settlement_id

    def _fund_data(self, fund):
        receipts = self._fund_receipts(fund)
        rows, sent = [], 0.0
        for move in receipts:
            settlement = self._receipt_settlement(move)
            state = 'approved' if settlement.state == 'posted' else \
                'sent' if settlement else 'registered'
            if settlement:
                sent += move.amount_total
            rows.append({
                'id': move.id, 'number': move.l10n_latam_document_number or move.ref or '',
                'doc_type': move.l10n_latam_document_type_id.name or '',
                'partner': move.partner_id.name or '', 'vat': move.partner_id.vat or '',
                'date': fields.Date.to_string(move.invoice_date) if move.invoice_date else '',
                'amount': move.amount_total, 'state': state,
                'state_label': {'registered': self.env._('Por rendir'),
                                'sent': self.env._('Rendido'),
                                'approved': self.env._('Aprobado')}[state],
                'task': move.construction_portal_task_id.display_name or self.env._(
                    'Gastos generales de la obra'),
            })
        delivered = fund.amount_delivered - fund.amount_returned
        types = dict(fund._fields['fund_type']._description_selection(self.env))
        return {
            'id': fund.id, 'name': fund.display_name, 'type': fund.fund_type,
            'type_label': types.get(fund.fund_type, ''), 'purpose': fund.purpose or '',
            'currency': fund.currency_id.symbol or '',
            'date_due': fund.date_due and fields.Date.to_string(fund.date_due) or '',
            'overdue': fund.is_overdue,
            # Entregado, rendido, aprobado y por rendir (CR-55, punto 3).
            'delivered': delivered, 'sent': sent, 'approved': fund.amount_settled,
            'balance': delivered - sent, 'receipts': rows,
        }

    @api.model
    def sync(self, project_id):
        data = super().sync(project_id)
        if 'resident' not in data:
            return data
        project, _members = self._project(project_id)
        company = project.company_id or self.env.company
        types = self.env['l10n_latam.document.type'].sudo().search([
            ('code', 'in', DOCUMENT_CODES), ('country_id.code', '=', 'PE'),
            ('internal_type', 'in', ('invoice', False))], order='code')
        data['resident']['cash'] = {
            'funds': [self._fund_data(fund) for fund in self._resident_funds(company)],
            'doc_types': [[t.id, '%s · %s' % (t.name, t.code)] for t in types],
        }
        return data

    # ------------------------------------------------------------------
    # Registrar un comprobante
    # ------------------------------------------------------------------
    def _fund_of_resident(self, project, fund_id):
        company = project.company_id or self.env.company
        fund = self._resident_funds(company).filtered(lambda f: f.id == int(fund_id or 0))
        if not fund:
            raise AccessError(self.env._('Ese fondo no es suyo o ya no está entregado.'))
        return fund

    def _supplier(self, ruc, company):
        """El proveedor por su RUC; si no está, se crea con el RUC (sus datos
        los completa Contabilidad o la consulta del RUC)."""
        ruc = (ruc or '').strip()
        if not RUC.match(ruc):
            raise UserError(self.env._('El RUC del emisor tiene 11 dígitos.'))
        Partner = self.env['res.partner'].sudo()
        partner = Partner.search([('vat', '=', ruc), ('company_id', 'in', (company.id, False))],
                                 limit=1)
        if not partner:
            ruc_type = self.env.ref('l10n_pe.it_RUC', raise_if_not_found=False)
            partner = Partner.create({
                'name': self.env._('Proveedor RUC %s', ruc), 'vat': ruc, 'is_company': True,
                'l10n_latam_identification_type_id': ruc_type.id if ruc_type else False,
                'country_id': self.env.ref('base.pe').id})
        return partner

    def _expense_journal(self, company):
        if hasattr(company, '_l10n_pe_expense_journal'):
            journal = company._l10n_pe_expense_journal()
            if journal:
                return journal
        return self.env['account.journal'].sudo().search([
            *self.env['account.journal']._check_company_domain(company),
            ('type', '=', 'purchase')], limit=1)

    @api.model
    def expense(self, values):
        """Comprobante pagado con el fondo (CR-55, punto 1): factura del
        proveedor en borrador con la obra y la partida (o los gastos
        generales de la obra) y la foto."""
        submission = self._submission('expense', values.get('uuid'))
        if submission:
            return {'status': 'done', 'ids': submission.res_ids, 'duplicate': True}
        project, members = self._resident_project(values.get('project_id'))
        company = project.company_id or self.env.company
        fund = self._fund_of_resident(project, values.get('fund_id'))
        doc_type = self.env['l10n_latam.document.type'].sudo().browse(
            int(values.get('doc_type_id') or 0)).exists()
        if not doc_type or doc_type.code not in DOCUMENT_CODES:
            raise UserError(self.env._('Elija el tipo de comprobante.'))
        number = (values.get('number') or '').strip().upper()
        if not number:
            raise UserError(self.env._('Indique el número del comprobante (serie y número).'))
        amount = float(values.get('amount') or 0.0)
        if amount <= 0:
            raise UserError(self.env._('El monto del comprobante debe ser mayor que cero.'))
        day = self._portal_date(values.get('date'), company)
        partner = self._supplier(values.get('ruc'), company)
        # sudo: comprobante repetido del mismo proveedor.
        if self.env['account.move'].sudo().search_count([
                ('move_type', '=', 'in_invoice'), ('partner_id', '=', partner.id),
                ('state', '!=', 'cancel'),
                # El número no se guarda aparte: está en la referencia (los del
                # portal) o al final del nombre del comprobante («BOL B001-101»).
                '|', ('ref', '=', number), ('name', '=like', '%% %s' % number)]):
            raise UserError(self.env._('El comprobante %(number)s de %(partner)s ya está '
                                       'registrado.', number=number, partner=partner.name))
        task = self.env['project.task']
        if values.get('task_id'):
            task = self._lines(project, members).task_id.filtered(
                lambda t: t.id == int(values['task_id']))
            if not task:
                raise AccessError(self.env._('Esa partida no es de su obra.'))
            analytic = project.account_id
        else:
            analytic = project.construction_portal_overhead_area_id or project.account_id
        attachments = self._photos(values.get('photos'), 'account.move', required=True)
        journal = self._expense_journal(company)
        if not journal:
            raise UserError(self.env._('La compañía no tiene un diario de compras.'))
        description = (values.get('description') or '').strip() or self.env._(
            'Gasto de la obra %s', project.display_name)
        line = {'name': description, 'quantity': 1.0, 'price_unit': amount,
                'analytic_distribution': {str(analytic.id): 100.0} if analytic else False}
        tax = company.account_purchase_tax_id
        if doc_type.code == '01' and tax and tax.amount_type == 'percent' and not tax.price_include:
            # Factura: el monto del comprobante incluye el IGV.
            line.update(price_unit=fund.currency_id.round(amount / (1 + tax.amount / 100.0)),
                        tax_ids=[Command.set(tax.ids)])
        else:
            line['tax_ids'] = [Command.clear()]
        # sudo: el comprobante lo registra el residente con su fondo; queda en
        # borrador para que lo revise Contabilidad.
        move = self.env['account.move'].sudo().with_company(company).create({
            'move_type': 'in_invoice', 'journal_id': journal.id, 'partner_id': partner.id,
            'invoice_date': day, 'date': day, 'currency_id': fund.currency_id.id,
            'l10n_latam_document_type_id': doc_type.id, 'l10n_latam_document_number': number,
            'ref': number, 'invoice_line_ids': [Command.create(line)],
            'construction_portal_fund_id': fund.id, 'construction_portal_project_id': project.id,
            'construction_portal_task_id': task.id or False,
            'construction_portal_user_id': self.env.uid,
        })
        attachments.write({'res_id': move.id})
        move.message_post(body=self.env._(
            'Registrado en obra por %(user)s desde el portal; pagado con %(fund)s.',
            user=self.env.user.name, fund=fund.display_name), author_id=self.env.user.partner_id.id)
        self._portal_register('expense', values['uuid'], move)
        return {'status': 'done', 'ids': str(move.id), 'name': number,
                'amount': move.amount_total}

    # ------------------------------------------------------------------
    # Rendir
    # ------------------------------------------------------------------
    @api.model
    def settle(self, values):
        """Rendición del fondo con los comprobantes elegidos (CR-55, punto
        2): queda en borrador; Contabilidad publica los comprobantes y la
        confirma."""
        submission = self._submission('settle', values.get('uuid'))
        if submission:
            return {'status': 'done', 'ids': submission.res_ids, 'duplicate': True}
        project, _members = self._resident_project(values.get('project_id'))
        fund = self._fund_of_resident(project, values.get('fund_id'))
        wanted = {int(i) for i in values.get('receipt_ids') or []}
        receipts = self._fund_receipts(fund).filtered(lambda m: m.id in wanted)
        if not receipts or len(receipts) != len(wanted):
            raise UserError(self.env._('Elija sus comprobantes de este fondo.'))
        sent = receipts.filtered(lambda m: self._receipt_settlement(m))
        if sent:
            raise UserError(self.env._('Ya se rindieron: %s.', ', '.join(
                sent.mapped(lambda m: m.l10n_latam_document_number or m.ref or ''))))
        # sudo: la rendición la arma el residente con sus comprobantes; la
        # confirma Contabilidad.
        settlement = self.env['l10n_pe.cash.settlement'].sudo().create({
            'fund_id': fund.id, 'date': fields.Date.context_today(self),
            'note': (values.get('note') or '').strip() or self.env._(
                'Rendición enviada desde el portal de obra por %s.', self.env.user.name),
            'document_line_ids': [Command.create({'move_id': move.id, 'amount': move.amount_total})
                                  for move in receipts],
        })
        settlement.message_post(body=self.env._(
            'Rendición enviada desde el portal de obra con %(count)s comprobantes por %(amount)s.',
            count=len(receipts), amount=sum(receipts.mapped('amount_total'))),
            author_id=self.env.user.partner_id.id)
        self._portal_register('settle', values['uuid'], settlement)
        return {'status': 'done', 'ids': str(settlement.id), 'name': settlement.display_name,
                'amount': settlement.amount_total}

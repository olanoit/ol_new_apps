# -*- coding: utf-8 -*-
from lxml import etree

from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_print_guia_remision(self):
        return self.env.ref(
            'al_l10n_pe_delivery_guide_report.action_report_guia_remision'
        ).report_action(self)

    def _get_grouped_move_lines(self):
        """Detalle de bienes: una línea por movimiento, en el orden del XML
        (``DespatchLine`` por movimiento con cantidad), con sus series o
        lotes. Antes se agrupaba por producto y la numeración y el número de
        líneas no coincidían con el XML enviado a SUNAT."""
        self.ensure_one()
        lines = []
        for move in self.move_ids.filtered(lambda m: m.quantity > 0):
            lines.append({
                'product': move.product_id,
                'uom': move.product_uom,
                'quantity': move.quantity,
                # ordenados: un set no tiene orden y cada impresión variaba
                'lots': sorted({ml.lot_id.name for ml in move.move_line_ids if ml.lot_id}),
            })
        return lines

    @api.model
    def _l10n_pe_report_quantity(self, quantity):
        """Cantidad sin redondear a 2 decimales (el XML lleva hasta 10)."""
        text = ('%.10f' % quantity).rstrip('0').rstrip('.')
        return text or '0'

    def _l10n_pe_report_issue_date(self):
        """Fecha de emisión del XML enviado (``cbc:IssueDate``, la del envío
        en hora de Lima); sin XML aún, la de validación de la entrega."""
        self.ensure_one()
        name = '%s-09-%s.xml' % (self.company_id.vat, self.l10n_latam_document_number)
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', self._name), ('res_id', '=', self.id), ('name', '=', name),
        ], limit=1, order='id desc') if self.l10n_latam_document_number else False
        if attachment and attachment.raw:
            try:
                tree = etree.fromstring(attachment.raw)
                issue = tree.findtext('{*}IssueDate')
                if issue:
                    return fields.Date.to_date(issue)
            except etree.XMLSyntaxError:
                pass
        return False

    def _l10n_pe_report_departure_partner(self):
        """Punto de partida: el mismo contacto que usa el XML de la guía
        (``warehouse_address`` en ``_l10n_pe_edi_get_delivery_guide_values``):
        la dirección del almacén del tipo de operación o, si no tiene, la de
        la compañía."""
        self.ensure_one()
        return self.picking_type_id.warehouse_id.partner_id or self.company_id.partner_id

    @api.model
    def _l10n_pe_report_address_line(self, partner):
        """Dirección en una línea: calle, distrito, provincia y
        departamento (el orden del XML de la guía)."""
        parts = [partner.street, partner.l10n_pe_district.name, partner.city,
                 partner.state_id.name]
        return ' - '.join(part for part in parts if part)

    @api.depends('move_ids.weight', 'shipping_weight')
    def _cal_weight(self):
        # EXTENDS stock_delivery: si la suma de pesos de línea es 0 (p. ej.
        # productos sin peso configurado), usa el peso de envío estimado
        # en vez de reportar 0 KGM en la guía.
        super()._cal_weight()
        for picking in self:
            if not picking.weight:
                picking.weight = picking.shipping_weight

    def _l10n_pe_edi_get_delivery_guide_values(self):
        # EXTENDS l10n_pe_edi_stock: fuerza el recálculo del peso antes de
        # armar el XML, para no depender del orden de escritura de los
        # movimientos relacionados. Se hace por el mecanismo de cálculo del
        # ORM, no asignando el campo a mano sobre una entrega ya hecha.
        self.env.add_to_compute(self._fields['weight'], self)
        self._recompute_recordset(['weight'])
        return super()._l10n_pe_edi_get_delivery_guide_values()

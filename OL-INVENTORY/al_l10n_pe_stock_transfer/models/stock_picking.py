# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

# Motivo 04 del catálogo 20 de SUNAT: traslado entre establecimientos de la
# misma empresa (destinatario = remitente; partida y llegada, establecimientos
# del remitente).
REASON_INTERNAL = '04'


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    l10n_pe_has_third_party_goods = fields.Boolean(
        string='Con bienes de terceros', compute='_compute_l10n_pe_third_party', store=True,
        help='Algún bien de la transferencia tiene un propietario que no es la compañía '
             '(consignación): no se valoriza ni entra al kardex valorizado.')
    l10n_pe_third_party_owner_ids = fields.Many2many(
        'res.partner', string='Propietarios de los bienes', compute='_compute_l10n_pe_third_party',
        help='Propietarios de los bienes de terceros de la transferencia.')
    l10n_pe_edi_origin_address_id = fields.Many2one(
        'res.partner', string='Punto de partida', compute='_compute_l10n_pe_edi_addresses',
        help='Establecimiento de origen: la dirección del almacén de la ubicación de origen '
             '(o la de la compañía).')
    l10n_pe_edi_destination_address_id = fields.Many2one(
        'res.partner', string='Punto de llegada', compute='_compute_l10n_pe_edi_addresses',
        help='Establecimiento de destino de un traslado interno: la dirección del almacén '
             'de la ubicación de destino (o la de la compañía).')
    l10n_pe_edi_guide_allowed = fields.Boolean(
        compute='_compute_l10n_pe_edi_guide_allowed',
        help='La transferencia admite guía de remisión: una salida, o un traslado interno '
             'entre establecimientos distintos.')

    # ------------------------------------------------------------------
    # Bienes de terceros
    # ------------------------------------------------------------------

    @api.depends('owner_id', 'move_line_ids.owner_id')
    def _compute_l10n_pe_third_party(self):
        for picking in self:
            owners = (picking.owner_id | picking.move_line_ids.owner_id).filtered(
                lambda p: not p.l10n_pe_is_company_partner)
            picking.l10n_pe_third_party_owner_ids = owners
            picking.l10n_pe_has_third_party_goods = bool(owners)

    def _l10n_pe_third_party_note(self):
        """Texto del propietario para las observaciones de la guía: el XML de
        la GRE no tiene un campo para el propietario de los bienes."""
        self.ensure_one()
        owners = self.l10n_pe_third_party_owner_ids
        if not owners:
            return ''
        return self.env._('Bienes de propiedad de %s.', ', '.join(
            '%s%s' % (owner.name, ' (%s)' % owner.vat if owner.vat else '') for owner in owners))

    # ------------------------------------------------------------------
    # Traslado entre establecimientos
    # ------------------------------------------------------------------

    @api.depends('location_id', 'location_dest_id', 'picking_type_id', 'company_id')
    def _compute_l10n_pe_edi_addresses(self):
        for picking in self:
            company_partner = picking.company_id.partner_id
            origin = picking.location_id.warehouse_id.partner_id \
                if picking.picking_type_code == 'internal' else picking.picking_type_id.warehouse_id.partner_id
            picking.l10n_pe_edi_origin_address_id = origin or company_partner
            destination = picking.location_dest_id.warehouse_id.partner_id
            picking.l10n_pe_edi_destination_address_id = (
                destination or company_partner if picking.picking_type_code == 'internal' else False)

    @api.model
    def _l10n_pe_establishment_key(self, partner):
        """Identifica el establecimiento: su código de anexo SUNAT o, sin él,
        su dirección (calle y distrito)."""
        code = (partner.l10n_pe_annex_code or '').strip()
        if code:
            return ('annex', code)
        return ('address', (partner.street or '').strip().lower(), partner.l10n_pe_district.id)

    def _l10n_pe_is_internal_establishment_transfer(self):
        self.ensure_one()
        if self.picking_type_code != 'internal':
            return False
        origin, destination = self.l10n_pe_edi_origin_address_id, self.l10n_pe_edi_destination_address_id
        return bool(origin and destination) and (
            self._l10n_pe_establishment_key(origin) != self._l10n_pe_establishment_key(destination))

    @api.depends('picking_type_code', 'location_id', 'location_dest_id')
    def _compute_l10n_pe_edi_guide_allowed(self):
        for picking in self:
            picking.l10n_pe_edi_guide_allowed = picking.picking_type_code == 'outgoing' \
                or picking._l10n_pe_is_internal_establishment_transfer()

    def _compute_l10n_pe_edi_reason_for_transfer(self):
        # EXTENDS l10n_pe_edi_stock: un traslado interno propone el motivo 04
        # (el nativo propone siempre 01, venta).
        internal = self.filtered(lambda p: not p.l10n_pe_edi_reason_for_transfer
                                 and p.l10n_pe_edi_transport_type and p.picking_type_code == 'internal')
        internal.l10n_pe_edi_reason_for_transfer = REASON_INTERNAL
        return super(StockPicking, self - internal)._compute_l10n_pe_edi_reason_for_transfer()

    def action_send_delivery_guide(self):
        # EXTENDS l10n_pe_edi_stock: admite traslados internos entre
        # establecimientos; el punto de llegada (partner_id del XML) es la
        # dirección del almacén de destino.
        for picking in self.filtered(lambda p: p.picking_type_code == 'internal'):
            if not picking._l10n_pe_is_internal_establishment_transfer():
                raise UserError(self.env._(
                    'La transferencia %s no sale del establecimiento: el origen y el destino '
                    'tienen la misma dirección, así que no lleva guía de remisión.', picking.name))
            if not picking.partner_id:
                picking.partner_id = picking.l10n_pe_edi_destination_address_id
        return super().action_send_delivery_guide()

    def _l10n_pe_edi_generate_missing_data_error_list(self):
        errors = super()._l10n_pe_edi_generate_missing_data_error_list()
        if self.l10n_pe_edi_reason_for_transfer == REASON_INTERNAL:
            if self.picking_type_code == 'internal' and not self._l10n_pe_is_internal_establishment_transfer():
                errors.append(self.env._('Con motivo 04 el origen y el destino deben ser establecimientos distintos.'))
        return errors

    def _l10n_pe_edi_get_delivery_guide_values(self):
        values = super()._l10n_pe_edi_get_delivery_guide_values()
        company_partner = self.company_id.partner_id
        origin = self.l10n_pe_edi_origin_address_id or values['warehouse_address']
        values['warehouse_address'] = origin
        internal = self.l10n_pe_edi_reason_for_transfer == REASON_INTERNAL
        # Motivo 04: destinatario = remitente y, en partida y llegada, el código
        # de establecimiento anexo con el RUC del remitente.
        values.update({
            'l10n_pe_delivery_customer': company_partner if internal else self.partner_id,
            'l10n_pe_internal_transfer': internal,
            'l10n_pe_origin_annex': (origin.l10n_pe_annex_code or '').strip() or '0',
            'l10n_pe_destination_annex': (self.partner_id.l10n_pe_annex_code or '').strip() or '0',
        })
        note = self._l10n_pe_third_party_note()
        if note:
            observation = self.l10n_pe_edi_observation
            values['l10n_pe_edi_observation'] = ('%s %s' % (observation, note)) if observation else note
        return values

    def _l10n_pe_report_departure_partner(self):
        # EXTENDS al_l10n_pe_delivery_guide_report: el mismo punto de partida que el XML.
        self.ensure_one()
        return self.l10n_pe_edi_origin_address_id or super()._l10n_pe_report_departure_partner()

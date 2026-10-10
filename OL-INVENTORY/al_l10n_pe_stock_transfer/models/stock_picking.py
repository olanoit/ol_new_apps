# -*- coding: utf-8 -*-
from contextlib import contextmanager

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.addons.l10n_pe_edi_stock.models import stock_picking as pe_stock

# Catálogo 20 de SUNAT (anexo de la R.S. 240-2024/SUNAT). El estándar trae
# 01, 03, 04, 05, 13, 14, 17 y 18; se añaden los que faltan para cubrir los
# traslados habituales de la empresa. El 19 (mercancía extranjera) no: exige
# datos del terminal y del almacén aduanero que Odoo no tiene.
EXTRA_REASONS = [
    ('02', 'Compra'),
    ('06', 'Devolución'),
    ('07', 'Recojo de bienes transformados'),
    ('08', 'Importación'),
    ('09', 'Exportación'),
]
# Motivo 04: traslado entre establecimientos de la misma empresa (destinatario
# = remitente; partida y llegada, establecimientos del remitente).
REASON_INTERNAL = '04'
REASON_RETURN = '06'
REASON_OTHER = '13'
# Ingresos: la empresa traslada los bienes desde el proveedor, el
# transformador o el puerto hasta su almacén; es remitente y destinataria.
INCOMING_REASONS = ('02', '07', '08')
# Comercio exterior: exigen la declaración aduanera (catálogo 61: 50 DAM, 52 DS).
CUSTOMS_REASONS = ('08', '09')
CUSTOMS_DOCUMENTS = ('50', '52')


@contextmanager
def _native_reason_labels():
    """El estándar arma la descripción del motivo con un diccionario de su
    lista fija (``PE_TRANSFER_REASONS``): mientras se arma el XML se le suman
    los motivos de este módulo para que no falle con ellos."""
    added = [reason for reason in EXTRA_REASONS if reason not in pe_stock.PE_TRANSFER_REASONS]
    pe_stock.PE_TRANSFER_REASONS.extend(added)
    try:
        yield
    finally:
        for reason in added:
            pe_stock.PE_TRANSFER_REASONS.remove(reason)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    l10n_pe_edi_reason_for_transfer = fields.Selection(
        selection_add=EXTRA_REASONS, ondelete={code: 'set null' for code, _label in EXTRA_REASONS})
    l10n_pe_edi_reason_description = fields.Char(
        string='Descripción del motivo',
        help='Obligatoria con el motivo 13 «Otros»: qué traslado es (exhibición, demostración, '
             'devolución de un equipo alquilado…). Va en la guía en lugar del nombre del motivo.')

    l10n_pe_has_third_party_goods = fields.Boolean(
        string='Con bienes de terceros', compute='_compute_l10n_pe_has_third_party_goods', store=True,
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

    def _l10n_pe_third_party_owners(self):
        self.ensure_one()
        return (self.owner_id | self.move_line_ids.owner_id).filtered(
            lambda p: not p.l10n_pe_is_company_partner)

    @api.depends('owner_id', 'move_line_ids.owner_id')
    def _compute_l10n_pe_third_party(self):
        for picking in self:
            picking.l10n_pe_third_party_owner_ids = picking._l10n_pe_third_party_owners()

    @api.depends('owner_id', 'move_line_ids.owner_id')
    def _compute_l10n_pe_has_third_party_goods(self):
        for picking in self:
            picking.l10n_pe_has_third_party_goods = bool(picking._l10n_pe_third_party_owners())

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

    @api.depends('location_id', 'location_dest_id', 'picking_type_id', 'company_id', 'partner_id',
                 'l10n_pe_edi_reason_for_transfer')
    def _compute_l10n_pe_edi_addresses(self):
        for picking in self:
            company_partner = picking.company_id.partner_id
            if picking._l10n_pe_is_incoming_guide():
                # Ingreso trasladado por la empresa: parte del proveedor
                # (transformador, puerto) y llega a su almacén.
                picking.l10n_pe_edi_origin_address_id = picking.partner_id
                picking.l10n_pe_edi_destination_address_id = (
                    picking.location_dest_id.warehouse_id.partner_id
                    or picking.picking_type_id.warehouse_id.partner_id or company_partner)
                continue
            origin = picking.location_id.warehouse_id.partner_id \
                if picking.picking_type_code == 'internal' else picking.picking_type_id.warehouse_id.partner_id
            picking.l10n_pe_edi_origin_address_id = origin or company_partner
            destination = picking.location_dest_id.warehouse_id.partner_id
            picking.l10n_pe_edi_destination_address_id = (
                destination or company_partner if picking.picking_type_code == 'internal' else False)

    def _l10n_pe_is_incoming_guide(self):
        """Recepción cuyo traslado lo hace la empresa (motivos 02, 07, 08)."""
        self.ensure_one()
        return self.picking_type_code == 'incoming' and self.l10n_pe_edi_reason_for_transfer in INCOMING_REASONS

    def _l10n_pe_is_own_address(self, partner):
        """La dirección es de la empresa: su contacto o uno de sus hijos
        (las direcciones de sus almacenes)."""
        return bool(partner) and partner.commercial_partner_id == self.company_id.partner_id

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

    @api.depends('picking_type_code', 'location_id', 'location_dest_id', 'l10n_pe_edi_reason_for_transfer')
    def _compute_l10n_pe_edi_guide_allowed(self):
        for picking in self:
            picking.l10n_pe_edi_guide_allowed = picking.picking_type_code == 'outgoing' \
                or picking._l10n_pe_is_internal_establishment_transfer() \
                or picking._l10n_pe_is_incoming_guide()

    def _l10n_pe_is_return_to_owner(self):
        """Salida que devuelve bienes de terceros a su propietario, o
        devolución de una recepción (al proveedor)."""
        self.ensure_one()
        if self.picking_type_code != 'outgoing':
            return False
        if self.move_ids.origin_returned_move_id:
            return True
        return bool(self.partner_id) and self.partner_id.commercial_partner_id in \
            self.l10n_pe_third_party_owner_ids.commercial_partner_id

    def _l10n_pe_proposed_reason(self):
        """Motivo propuesto: el del tipo de operación; si no tiene, 04 entre
        establecimientos, 06 en devoluciones (al proveedor o al dueño de los
        bienes de terceros) y 02 en las recepciones. Sin ninguno, el estándar
        (01, venta)."""
        self.ensure_one()
        if self.picking_type_id.l10n_pe_edi_default_reason:
            return self.picking_type_id.l10n_pe_edi_default_reason
        if self.picking_type_code == 'internal':
            return REASON_INTERNAL
        if self._l10n_pe_is_return_to_owner():
            return REASON_RETURN
        if self.picking_type_code == 'incoming':
            return INCOMING_REASONS[0]
        return False

    @api.depends('l10n_pe_edi_transport_type')
    def _compute_l10n_pe_edi_reason_for_transfer(self):
        # EXTENDS l10n_pe_edi_stock: propone el motivo según la operación (el
        # nativo propone siempre 01, venta).
        # El estándar pone 01 al crear la transferencia, antes de elegir la
        # modalidad: ese 01 automático se reemplaza por la propuesta cuando la
        # operación no es una venta (traslado interno, recepción, devolución o
        # motivo del tipo de operación).
        proposed = self.env['stock.picking']
        for picking in self.filtered(lambda p: p.l10n_pe_edi_reason_for_transfer in (False, '01')
                                     and p.l10n_pe_edi_transport_type):
            reason = picking._l10n_pe_proposed_reason()
            if reason:
                picking.l10n_pe_edi_reason_for_transfer = reason
                proposed |= picking
        return super(StockPicking, self - proposed)._compute_l10n_pe_edi_reason_for_transfer()

    def action_send_delivery_guide(self):
        # EXTENDS l10n_pe_edi_stock: admite traslados internos entre
        # establecimientos y recepciones trasladadas por la empresa; en un
        # traslado interno el punto de llegada (partner_id del XML) es la
        # dirección del almacén de destino.
        for picking in self.filtered(lambda p: p.picking_type_code == 'incoming'):
            if not picking._l10n_pe_is_incoming_guide():
                raise UserError(self.env._(
                    'La recepción %s solo lleva guía de la empresa si ella hace el traslado: elija '
                    'el motivo 02 Compra, 07 Recojo de bienes transformados u 08 Importación. Si el '
                    'proveedor trae los bienes, la guía la emite él.', picking.name))
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
        reason = self.l10n_pe_edi_reason_for_transfer
        if reason == REASON_INTERNAL:
            if self.picking_type_code == 'internal' and not self._l10n_pe_is_internal_establishment_transfer():
                errors.append(self.env._('Con motivo 04 el origen y el destino deben ser establecimientos distintos.'))
        if reason == REASON_OTHER and not (self.l10n_pe_edi_reason_description or '').strip():
            errors.append(self.env._('Con el motivo 13 «Otros» describa el traslado en «Descripción del motivo».'))
        if reason in INCOMING_REASONS and self.picking_type_code != 'incoming':
            errors.append(self.env._('Los motivos 02, 07 y 08 son de ingreso: se usan en una recepción.'))
        if reason in CUSTOMS_REASONS and (self.l10n_pe_edi_related_document_type not in CUSTOMS_DOCUMENTS
                                          or not self.l10n_pe_edi_document_number):
            errors.append(self.env._('Con importación o exportación indique la declaración aduanera (DAM o DS) '
                                     'y su número en el documento relacionado.'))
        return errors

    def _l10n_pe_address_type(self, partner):
        """``(RUC, código de establecimiento)`` de ``cbc:AddressTypeCode``: un
        establecimiento propio va con el RUC de la empresa y su código anexo;
        el de un tercero con RUC, con su RUC y 0 (como el estándar); sin RUC,
        no se informa."""
        if self._l10n_pe_is_own_address(partner):
            return self.company_id.vat, (partner.l10n_pe_annex_code or '').strip() or '0'
        if partner.l10n_latam_identification_type_id.l10n_pe_vat_code == '6' and partner.vat:
            return partner.vat, '0'
        return False, False

    def _l10n_pe_edi_get_delivery_guide_values(self):
        with _native_reason_labels():
            values = super()._l10n_pe_edi_get_delivery_guide_values()
        company_partner = self.company_id.partner_id
        incoming = self._l10n_pe_is_incoming_guide()
        origin = self.l10n_pe_edi_origin_address_id or values['warehouse_address']
        arrival = self._l10n_pe_report_arrival_partner()
        values['warehouse_address'] = origin
        internal = self.l10n_pe_edi_reason_for_transfer == REASON_INTERNAL
        if self.l10n_pe_edi_reason_for_transfer == REASON_OTHER and self.l10n_pe_edi_reason_description:
            values['reason_for_transfer'] = self.l10n_pe_edi_reason_description.strip()[:100]
        origin_ruc, origin_annex = self._l10n_pe_address_type(origin)
        arrival_ruc, arrival_annex = self._l10n_pe_address_type(arrival)
        # Motivo 04 y los ingresos (02, 07, 08): destinatario = remitente.
        values.update({
            'l10n_pe_delivery_customer': company_partner if (internal or incoming) else self.partner_id,
            'l10n_pe_internal_transfer': internal,
            'l10n_pe_arrival_address': arrival,
            'l10n_pe_origin_ruc': origin_ruc,
            'l10n_pe_origin_annex': origin_annex,
            'l10n_pe_arrival_ruc': arrival_ruc,
            'l10n_pe_arrival_annex': arrival_annex,
            # compatibilidad con la plantilla anterior
            'l10n_pe_destination_annex': arrival_annex or '0',
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

    def _l10n_pe_report_arrival_partner(self):
        """Punto de llegada del PDF, el mismo del XML: en un ingreso, el
        almacén de la empresa; en lo demás, el contacto de la transferencia."""
        self.ensure_one()
        if self._l10n_pe_is_incoming_guide() or (
                self.picking_type_code == 'internal' and not self.partner_id):
            # En un traslado interno el contacto se completa al enviar la guía;
            # antes, la llegada es el almacén de destino.
            return self.l10n_pe_edi_destination_address_id
        return self.partner_id

    def _l10n_pe_report_receiver(self):
        """Destinatario del PDF, el mismo del XML."""
        self.ensure_one()
        if self.l10n_pe_edi_reason_for_transfer == REASON_INTERNAL or self._l10n_pe_is_incoming_guide():
            return self.company_id.partner_id
        return self.partner_id.commercial_partner_id

    def _l10n_pe_report_reason_label(self):
        """Motivo del PDF: con 13 «Otros», su descripción."""
        self.ensure_one()
        # El informe se imprime en el idioma del contacto, que puede faltar (un
        # traslado interno): el motivo va en el de la compañía.
        env = self.with_context(lang=self.company_id.partner_id.lang or self.env.lang).env
        label = dict(self._fields['l10n_pe_edi_reason_for_transfer']._description_selection(env)).get(
            self.l10n_pe_edi_reason_for_transfer, '')
        if self.l10n_pe_edi_reason_for_transfer == REASON_OTHER and self.l10n_pe_edi_reason_description:
            return '%s: %s' % (label, self.l10n_pe_edi_reason_description)
        return label

# -*- coding: utf-8 -*-
"""Caja de farmacia: datos que el TPV necesita (producto, empleado, usuario,
ajustes de la compañía), lotes disponibles por vencimiento (FEFO) y el
registro de la receta y la dispensación al guardar la venta."""
import logging

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

PHARMACY_PRODUCT_FIELDS = [
    'pharmacy_ok', 'pharmacy_sale_condition', 'pharmacy_equivalence_key', 'pharmacy_product_type',
    'pharmacy_composition', 'pharmacy_cold_chain', 'pharmacy_linked_company', 'pharmacy_ingredient_ids',
    'pharmacy_bioequivalent', 'pharmacy_bioequivalent_ids',
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + PHARMACY_PRODUCT_FIELDS


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + [
            'pharmacy_prescription_policy', 'pharmacy_pharmacist_policy']


class ResUsers(models.Model):
    _inherit = 'res.users'

    pharmacy_is_pharmacist = fields.Boolean(compute='_compute_pharmacy_is_pharmacist')

    def _compute_pharmacy_is_pharmacist(self):
        group = self.env.ref('al_pharmacy_base.group_pharmacy_pharmacist')
        for user in self:
            user.pharmacy_is_pharmacist = group in user.all_group_ids

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + ['pharmacy_is_pharmacist']


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + ['pharmacy_role']


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    @api.model
    def get_existing_lots(self, company_id, config_id, product_id):
        """Solo lotes disponibles (no en cuarentena, bloqueados ni vencidos),
        el que vence primero arriba (FEFO)."""
        lots = super().get_existing_lots(company_id, config_id, product_id)
        records = self.env['stock.lot'].browse([lot['id'] for lot in lots])
        # Un lote vencido nunca se vende, aunque el cron diario aún no lo marque.
        available = {lot.id: lot for lot in records
                     if lot.pharmacy_state == 'available' and not lot._pharmacy_is_expired()}
        far_future = fields.Datetime.to_datetime('9999-12-31')
        result = [lot for lot in lots if lot['id'] in available]
        result.sort(key=lambda lot: available[lot['id']].expiration_date or far_future)
        return result

    @api.model
    def get_pharmacy_lot_expiry(self, config_id, product_id, lot_names):
        """Descuento por vencer de los lotes elegidos en la caja:
        ``{lote: {'discount': %, 'expiration_date': 'AAAA-MM-DD'}}``."""
        self.check_access('read')
        config = self.env['pos.config'].browse(config_id).exists()
        if not config or not lot_names:
            return {}
        if config.company_id not in self.env.companies:
            raise AccessError(self.env._('La caja no es de una compañía permitida.'))
        # Quien atiende la caja no necesariamente lee lotes de inventario; solo
        # se devuelven la fecha de vencimiento y el descuento de la escala.
        lots_sudo = self.env['stock.lot'].sudo().with_company(config.company_id).search([
            ('product_id', '=', product_id), ('name', 'in', lot_names),
            '|', ('company_id', '=', False), ('company_id', '=', config.company_id.id)])
        result = {}
        for lot in lots_sudo:
            if not lot.expiration_date:
                continue
            result[lot.name] = {
                'discount': lot.pharmacy_expiry_discount,
                # Día del vencimiento en la hora local de la caja, no en UTC.
                'expiration_date': fields.Date.to_string(
                    fields.Date.context_today(self, lot.expiration_date)),
            }
        return result


class PosOrder(models.Model):
    _inherit = 'pos.order'

    pharmacy_prescription_number = fields.Char(string='Número de receta', copy=False)
    pharmacy_prescription_date = fields.Date(string='Fecha de la receta', copy=False)
    pharmacy_prescriber_name = fields.Char(string='Prescriptor', copy=False)
    pharmacy_prescriber_license = fields.Char(string='Colegiatura del prescriptor', copy=False)
    pharmacy_patient_name = fields.Char(string='Paciente', copy=False,
                                        help='Si la venta no tiene cliente.')
    pharmacy_exception_employee_id = fields.Many2one(
        'hr.employee', string='Excepción autorizada por', copy=False, check_company=True,
        help='Químico farmacéutico que autorizó vender sin receta.')
    pharmacy_exception_user_id = fields.Many2one(
        'res.users', string='Excepción autorizada por (usuario)', copy=False,
        help='Químico farmacéutico que autorizó vender sin receta, si la caja no usa empleados.')
    pharmacy_no_pharmacist_alert = fields.Boolean(
        string='Vendido sin Q.F.', copy=False,
        help='Se vendió un producto con receta sin químico farmacéutico en la caja.')
    pharmacy_prescription_id = fields.Many2one('pharmacy.prescription', string='Receta',
                                               copy=False, readonly=True, check_company=True)

    @api.model
    def _process_order(self, order, existing_order):
        order_id = super()._process_order(order, existing_order)
        pos_order = self.browse(order_id)
        if pos_order.state in ('paid', 'done') and not pos_order.pharmacy_prescription_id:
            pos_order._pharmacy_register_dispensation()
        return order_id

    def _pharmacy_prescription_lines(self):
        self.ensure_one()
        return self.lines.filtered(
            lambda line: line.qty > 0 and line.product_id.pharmacy_ok
            and line.product_id.product_tmpl_id._pharmacy_needs_prescription())

    def _pharmacy_register_dispensation(self):
        """Receta, dispensación y asientos del libro de una venta pagada. Un
        dato que falte no impide guardar la venta: queda anotado en el libro
        de ocurrencias para que el Q.F. lo complete."""
        self.ensure_one()
        lines = self._pharmacy_prescription_lines()
        if not lines:
            return
        # La venta la sincroniza quien atiende (técnico o Q.F.): la receta y
        # la dispensación son registros del establecimiento que se crean en
        # su nombre, aunque no tenga permiso de escritura en ellos.
        self_sudo = self.sudo()
        Logbook = self.env['pharmacy.logbook.entry']
        warehouse = self.config_id.picking_type_id.warehouse_id
        products = ', '.join(lines.product_id.mapped('display_name'))
        authorizer = self.pharmacy_exception_employee_id or self.pharmacy_exception_user_id
        if authorizer:
            Logbook._log('exception', self.env._(
                'Venta %(order)s sin receta autorizada por %(employee)s: %(products)s.',
                order=self.name, employee=authorizer.name,
                products=products), warehouse=warehouse, record=self)
        if self.pharmacy_no_pharmacist_alert:
            Logbook._log('alert', self.env._(
                'Venta %(order)s de productos con receta sin químico farmacéutico en la caja '
                '(%(cashier)s): %(products)s.', order=self.name,
                cashier=(self.employee_id or self.user_id).name, products=products),
                warehouse=warehouse, record=self)
        if not (self.pharmacy_prescription_number or self.pharmacy_prescriber_license):
            return
        try:
            with self.env.cr.savepoint():
                prescription = self_sudo._pharmacy_create_prescription(lines, warehouse)
                self_sudo.pharmacy_prescription_id = prescription
        except (UserError, ValidationError) as error:
            _logger.info('Receta de %s no registrada: %s', self.name, error)
            Logbook._log('other', self.env._(
                'La receta de la venta %(order)s no se pudo registrar: %(error)s',
                order=self.name, error=error), warehouse=warehouse, record=self)

    def _pharmacy_get_prescriber(self):
        Partner = self.env['res.partner']
        license_number = (self.pharmacy_prescriber_license or '').strip()
        prescriber = Partner.search([('pharmacy_prescriber_license', '=', license_number),
                                     ('pharmacy_is_prescriber', '=', True)], limit=1) \
            if license_number else Partner
        if not prescriber and (license_number or self.pharmacy_prescriber_name):
            prescriber = Partner.create({
                'name': self.pharmacy_prescriber_name or self.env._('Colegiatura %s', license_number),
                'pharmacy_is_prescriber': True,
                'pharmacy_prescriber_license': license_number,
                'is_company': False,
            })
        return prescriber

    def _pharmacy_get_patient(self):
        if self.partner_id:
            return self.partner_id
        if self.pharmacy_patient_name:
            return self.env['res.partner'].create({'name': self.pharmacy_patient_name})
        return self.env['res.partner']

    def _pharmacy_create_prescription(self, lines, warehouse):
        self.ensure_one()
        special = any(line.product_id.pharmacy_sale_condition == 'controlled' for line in lines)
        prescription = self.env['pharmacy.prescription'].create({
            'prescription_number': self.pharmacy_prescription_number,
            'prescription_type': 'special' if special else 'common',
            'date': self.pharmacy_prescription_date or fields.Date.context_today(self),
            'prescriber_id': self._pharmacy_get_prescriber().id,
            'patient_id': self._pharmacy_get_patient().id,
            'warehouse_id': warehouse.id,
            'company_id': self.company_id.id,
            'line_ids': [(0, 0, {'product_id': line.product_id.id, 'quantity': line.qty})
                         for line in lines],
        })
        prescription.action_validate()
        pharmacist = self.employee_id if self.employee_id.pharmacy_role == 'pharmacist' else \
            self.pharmacy_exception_employee_id
        Lot = self.env['stock.lot']
        for line in lines:
            lot_name = line.pack_lot_ids[:1].lot_name
            lot = Lot.search([('product_id', '=', line.product_id.id), ('name', '=', lot_name)],
                             limit=1) if lot_name else Lot
            prescription._dispense(line.product_id, line.qty, lot=lot, source=self.name,
                                   pharmacist=pharmacist,
                                   purchaser_name=self.partner_id.name or self.pharmacy_patient_name,
                                   purchaser_vat=self.partner_id._pharmacy_identification_number() if self.partner_id else False)
        return prescription

# -*- coding: utf-8 -*-
"""Receta médica y dispensación (Manual BPOF, RM 554-2022/MINSA, 7.5.2).

La receta guarda los datos que exige la norma (prescriptor y colegiatura,
paciente, medicamentos en DCI, posología, vigencia) y lo dispensado contra
cada línea: entregas parciales, alternativas entregadas y retención con
folio. Las ventas (TPV u otras) registran la dispensación.
"""
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

PRESCRIPTION_STATES = [
    ('draft', 'Borrador'),
    ('valid', 'Vigente'),
    ('partial', 'Dispensada en parte'),
    ('dispensed', 'Dispensada'),
    ('expired', 'Vencida'),
    ('cancelled', 'Anulada'),
]


class PharmacyPrescription(models.Model):
    _name = 'pharmacy.prescription'
    _description = 'Receta médica'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Referencia', readonly=True, copy=False, default='/')
    prescription_number = fields.Char(string='Número de receta', tracking=True,
                                      help='El número impreso en la receta, si tiene.')
    prescription_type = fields.Selection([
        ('common', 'Receta común'),
        ('special', 'Receta especial'),
    ], string='Tipo', required=True, default='common', tracking=True,
        help='La receta especial es la de estupefacientes y psicotrópicos.')
    date = fields.Date(string='Fecha de emisión', required=True, default=fields.Date.context_today,
                       tracking=True)
    validity_days = fields.Integer(string='Vigencia (días)', default=30, required=True)
    expiry_date = fields.Date(string='Vence', compute='_compute_expiry_date', store=True)
    prescriber_id = fields.Many2one(
        'res.partner', string='Prescriptor', tracking=True,
        domain="[('pharmacy_is_prescriber', '=', True)]")
    prescriber_license = fields.Char(related='prescriber_id.pharmacy_prescriber_license',
                                     string='Colegiatura')
    health_facility = fields.Char(string='Establecimiento de salud')
    patient_id = fields.Many2one('res.partner', string='Paciente', tracking=True)
    diagnosis = fields.Char(string='Diagnóstico', groups='al_pharmacy_base.group_pharmacy_pharmacist')
    attachment_ids = fields.Many2many('ir.attachment', string='Imagen de la receta')
    line_ids = fields.One2many('pharmacy.prescription.line', 'prescription_id', string='Medicamentos',
                               copy=True)
    dispensation_ids = fields.One2many('pharmacy.dispensation', 'prescription_id',
                                       string='Dispensaciones')
    retained = fields.Boolean(string='Retenida', tracking=True,
                              help='La receta original queda en el establecimiento.')
    retention_folio = fields.Char(string='Folio', tracking=True)
    manual_state = fields.Selection([('draft', 'Borrador'), ('valid', 'Validada'),
                                     ('cancelled', 'Anulada')], default='draft', copy=False)
    state = fields.Selection(PRESCRIPTION_STATES, string='Estado', compute='_compute_state',
                             store=True, tracking=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Local', check_company=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('pharmacy.prescription') or '/'
        return super().create(vals_list)

    @api.depends('date', 'validity_days')
    def _compute_expiry_date(self):
        for prescription in self:
            prescription.expiry_date = prescription.date and (
                prescription.date + timedelta(days=prescription.validity_days))

    @api.depends('manual_state', 'expiry_date', 'line_ids.remaining_qty',
                 'line_ids.dispensed_qty')
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for prescription in self:
            lines = prescription.line_ids
            if prescription.manual_state in ('draft', 'cancelled'):
                prescription.state = prescription.manual_state
            elif lines and all(line.remaining_qty <= 0 for line in lines):
                prescription.state = 'dispensed'
            elif prescription.expiry_date and prescription.expiry_date < today:
                prescription.state = 'expired'
            elif any(line.dispensed_qty for line in lines):
                prescription.state = 'partial'
            else:
                prescription.state = 'valid'

    def _check_validity(self):
        """Lo mínimo de BPOF 7.5.2.9 para atender la receta."""
        for prescription in self:
            missing = []
            if not prescription.prescriber_id:
                missing.append(self.env._('prescriptor'))
            elif not prescription.prescriber_id.pharmacy_prescriber_license:
                missing.append(self.env._('colegiatura del prescriptor'))
            if not prescription.patient_id:
                missing.append(self.env._('paciente'))
            if not prescription.line_ids:
                missing.append(self.env._('medicamentos'))
            if missing:
                raise ValidationError(self.env._('Faltan datos en la receta %(name)s: %(missing)s.',
                                                 name=prescription.name, missing=', '.join(missing)))
            if prescription.prescriber_id.pharmacy_prescriber_status == 'disabled':
                raise ValidationError(self.env._(
                    'El prescriptor %s figura inhábil en su colegio profesional.',
                    prescription.prescriber_id.name))

    def action_validate(self):
        self._check_validity()
        self.manual_state = 'valid'

    def action_cancel(self):
        if self.dispensation_ids:
            raise UserError(self.env._('Una receta con dispensaciones no se anula.'))
        self.manual_state = 'cancelled'

    def action_draft(self):
        self.filtered(lambda p: not p.dispensation_ids).manual_state = 'draft'

    @api.model
    def _cron_expire_prescriptions(self):
        """El estado guardado no cambia solo con la fecha: se recalcula a
        diario para las recetas vigentes que ya vencieron."""
        prescriptions = self.search([('state', 'in', ('valid', 'partial')),
                                     ('expiry_date', '<', fields.Date.context_today(self))])
        self.env.add_to_compute(self._fields['state'], prescriptions)
        prescriptions.flush_recordset(['state'])
        return prescriptions

    def _find_line(self, product):
        """Línea de la receta que cubre ``product``: el mismo producto, un
        equivalente o el mismo principio activo."""
        self.ensure_one()
        for line in self.line_ids:
            if line._matches(product) and line.remaining_qty > 0:
                return line
        return self.env['pharmacy.prescription.line']

    def _check_can_dispense(self, product, quantity):
        self.ensure_one()
        if self.state in ('draft', 'cancelled'):
            raise UserError(self.env._('La receta %s no está validada.', self.name))
        if self.state == 'expired' or (self.expiry_date
                                       and self.expiry_date < fields.Date.context_today(self)):
            raise UserError(self.env._('La receta %(name)s venció el %(date)s (BPOF 7.5.2.13).',
                                       name=self.name, date=self.expiry_date))
        line = self._find_line(product)
        if not line:
            raise UserError(self.env._('La receta %(name)s no incluye %(product)s o ya se '
                                       'dispensó por completo.', name=self.name,
                                       product=product.display_name))
        if quantity > line.remaining_qty:
            raise UserError(self.env._('La receta %(name)s solo cubre %(qty)s más de %(product)s.',
                                       name=self.name, qty=line.remaining_qty,
                                       product=product.display_name))
        return line

    def _dispense(self, product, quantity, lot=None, source=False, pharmacist=None,
                  purchaser_name=False, purchaser_vat=False):
        """Registra la dispensación de ``quantity`` de ``product``."""
        self.ensure_one()
        line = self._check_can_dispense(product, quantity)
        return self.env['pharmacy.dispensation'].create({
            'prescription_id': self.id,
            'prescription_line_id': line.id,
            'product_id': product.id,
            'quantity': quantity,
            'lot_id': lot.id if lot else False,
            'source': source,
            'pharmacist_id': pharmacist.id if pharmacist else False,
            'purchaser_name': purchaser_name,
            'purchaser_vat': purchaser_vat,
        })

    def _allergy_warnings(self):
        """Principios activos de la receta a los que el paciente es alérgico."""
        self.ensure_one()
        # Lectura interna de un campo restringido para avisar, sin mostrar
        # la ficha de salud a quien atiende.
        patient_sudo = self.patient_id.sudo()
        allergies = patient_sudo.pharmacy_allergy_ids
        products = self.line_ids.product_id.product_tmpl_id
        ingredients = products.pharmacy_ingredient_line_ids.ingredient_id | self.line_ids.ingredient_id
        return allergies & ingredients


class PharmacyPrescriptionLine(models.Model):
    _name = 'pharmacy.prescription.line'
    _description = 'Medicamento de la receta'
    _order = 'prescription_id, sequence, id'

    prescription_id = fields.Many2one('pharmacy.prescription', required=True, ondelete='cascade',
                                      index=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one('product.product', string='Producto',
                                 domain="[('pharmacy_ok', '=', True)]")
    ingredient_id = fields.Many2one('pharmacy.ingredient', string='Principio activo (DCI)',
                                    help='Si la receta indica solo la DCI, cualquier producto con '
                                         'ese principio activo la cubre.')
    strength = fields.Char(string='Concentración')
    quantity = fields.Float(string='Cantidad', required=True, default=1.0, digits='Product Unit')
    posology = fields.Char(string='Posología', help='Por ejemplo «1 tableta cada 8 horas».')
    duration = fields.Char(string='Duración', help='Por ejemplo «7 días».')
    dispensation_ids = fields.One2many('pharmacy.dispensation', 'prescription_line_id')
    dispensed_qty = fields.Float(string='Dispensado', compute='_compute_quantities', store=True,
                                 digits='Product Unit')
    remaining_qty = fields.Float(string='Pendiente', compute='_compute_quantities', store=True,
                                 digits='Product Unit')

    @api.constrains('product_id', 'ingredient_id')
    def _check_product_or_ingredient(self):
        for line in self:
            if not line.product_id and not line.ingredient_id:
                raise ValidationError(self.env._('Indique el producto o el principio activo.'))

    @api.depends('quantity', 'dispensation_ids.quantity')
    def _compute_quantities(self):
        for line in self:
            line.dispensed_qty = sum(line.dispensation_ids.mapped('quantity'))
            line.remaining_qty = line.quantity - line.dispensed_qty

    def _matches(self, product):
        self.ensure_one()
        template = product.product_tmpl_id
        if self.product_id:
            if self.product_id == product:
                return True
            key = self.product_id.product_tmpl_id.pharmacy_equivalence_key
            return bool(key) and key == template.pharmacy_equivalence_key
        return self.ingredient_id in template.pharmacy_ingredient_line_ids.ingredient_id


class PharmacyDispensation(models.Model):
    _name = 'pharmacy.dispensation'
    _description = 'Dispensación'
    _order = 'date desc, id desc'
    _check_company_auto = True

    prescription_id = fields.Many2one('pharmacy.prescription', string='Receta', required=True,
                                      ondelete='restrict', index=True, check_company=True)
    prescription_line_id = fields.Many2one('pharmacy.prescription.line', string='Línea de la receta',
                                           ondelete='restrict', index=True)
    date = fields.Datetime(string='Fecha', required=True, default=fields.Datetime.now)
    product_id = fields.Many2one('product.product', string='Producto entregado', required=True,
                                 check_company=True)
    quantity = fields.Float(string='Cantidad', required=True, digits='Product Unit')
    lot_id = fields.Many2one('stock.lot', string='Lote', check_company=True)
    is_alternative = fields.Boolean(
        string='Alternativa', compute='_compute_is_alternative', store=True,
        help='Se entregó un producto distinto del prescrito (BPOF 7.5.2.28).')
    pharmacist_id = fields.Many2one('hr.employee', string='Químico farmacéutico',
                                    check_company=True)
    user_id = fields.Many2one('res.users', string='Registró', default=lambda self: self.env.user,
                              readonly=True)
    purchaser_name = fields.Char(string='Adquiriente')
    purchaser_vat = fields.Char(string='Documento del adquiriente')
    source = fields.Char(string='Documento de venta')
    company_id = fields.Many2one(related='prescription_id.company_id', store=True, index=True)

    @api.depends('product_id', 'prescription_line_id.product_id')
    def _compute_is_alternative(self):
        for dispensation in self:
            prescribed = dispensation.prescription_line_id.product_id
            dispensation.is_alternative = bool(prescribed) and prescribed != dispensation.product_id

    @api.ondelete(at_uninstall=False)
    def _unlink_never(self):
        raise UserError(self.env._('Las dispensaciones no se borran: son parte del libro de recetas.'))

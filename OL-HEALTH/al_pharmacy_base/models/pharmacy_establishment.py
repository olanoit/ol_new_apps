# -*- coding: utf-8 -*-
"""Gobierno del establecimiento: químicos farmacéuticos, director técnico por
local, turnos y libro de ocurrencias (Manual BPOF, RM 554-2022/MINSA, 7.2 y
7.3)."""
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

PHARMACY_ROLES = [
    ('technician', 'Técnico en farmacia'),
    ('pharmacist', 'Químico farmacéutico'),
]

LOGBOOK_TYPES = [
    ('rotation', 'Rotación de químicos farmacéuticos'),
    ('absence', 'Ausencia del director técnico'),
    ('adverse_event', 'Sospecha de reacción adversa'),
    ('exception', 'Dispensación autorizada por el Q.F.'),
    ('alert', 'Alerta sin Q.F. en turno'),
    ('incident', 'Incidente'),
    ('other', 'Otra observación'),
]


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    pharmacy_role = fields.Selection(
        PHARMACY_ROLES, string='Función en farmacia',
        help='Solo el químico farmacéutico dispensa productos con receta.')
    pharmacy_license_number = fields.Char(
        string='Colegiatura (COP)', help='Número de colegiatura del Colegio Químico Farmacéutico.')


class HrEmployeePublic(models.Model):
    """La función y la colegiatura son datos públicos del profesional: deben
    estar en el perfil público, o quien no es de RR. HH. (el TPV con pos_hr,
    por ejemplo) no puede leer empleados."""
    _inherit = 'hr.employee.public'

    pharmacy_role = fields.Selection(related='employee_id.pharmacy_role')
    pharmacy_license_number = fields.Char(related='employee_id.pharmacy_license_number')


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    pharmacy_director_id = fields.Many2one(
        'hr.employee', string='Director técnico', check_company=True,
        domain="[('pharmacy_role', '=', 'pharmacist')]",
        help='Químico farmacéutico responsable del establecimiento (un solo director técnico '
             'por local).')
    pharmacy_establishment_code = fields.Char(
        string='Código de establecimiento',
        help='Código que la autoridad sanitaria asignó al local.')


class PharmacyShift(models.Model):
    _name = 'pharmacy.shift'
    _description = 'Turno del químico farmacéutico'
    _order = 'date_start desc, id desc'
    _check_company_auto = True

    employee_id = fields.Many2one(
        'hr.employee', string='Químico farmacéutico', required=True, check_company=True,
        domain="[('pharmacy_role', '=', 'pharmacist')]")
    warehouse_id = fields.Many2one('stock.warehouse', string='Local', required=True,
                                   check_company=True)
    date_start = fields.Datetime(string='Inicio', required=True, default=fields.Datetime.now)
    date_end = fields.Datetime(string='Fin', required=True)
    role = fields.Selection([
        ('director', 'Director técnico'),
        ('replacement', 'Reemplazo del director técnico'),
        ('assistant', 'Q.F. asistente'),
    ], string='Rol', required=True, default='assistant')
    note = fields.Char(string='Observación')
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)

    @api.depends('employee_id', 'warehouse_id', 'date_start')
    def _compute_display_name(self):
        for shift in self:
            shift.display_name = '%s · %s' % (shift.employee_id.name or '',
                                             shift.warehouse_id.name or '')

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for shift in self:
            if shift.date_end <= shift.date_start:
                raise ValidationError(self.env._('El turno termina después de empezar.'))

    @api.model_create_multi
    def create(self, vals_list):
        shifts = super().create(vals_list)
        for shift in shifts.filtered(lambda s: s.role == 'replacement'):
            self.env['pharmacy.logbook.entry'].create({
                'entry_type': 'absence',
                'warehouse_id': shift.warehouse_id.id,
                'company_id': shift.company_id.id,
                'description': self.env._(
                    'Reemplazo del director técnico: %(employee)s (COP %(license)s) del '
                    '%(start)s al %(end)s.',
                    employee=shift.employee_id.name,
                    license=shift.employee_id.pharmacy_license_number or '-',
                    start=fields.Datetime.to_string(shift.date_start),
                    end=fields.Datetime.to_string(shift.date_end)),
            })
        return shifts

    @api.model
    def _get_pharmacists_on_duty(self, warehouse, when=None):
        when = when or fields.Datetime.now()
        shifts = self.search([
            ('warehouse_id', '=', warehouse.id),
            ('date_start', '<=', when), ('date_end', '>=', when),
        ])
        return shifts.employee_id


class PharmacyLogbookEntry(models.Model):
    """Libro de ocurrencias: solo se agregan asientos. Un error se corrige con
    un asiento nuevo que cita al anterior (BPOF 7.3.6), nunca editándolo."""
    _name = 'pharmacy.logbook.entry'
    _description = 'Libro de ocurrencias'
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    date = fields.Datetime(string='Fecha', required=True, readonly=True, default=fields.Datetime.now)
    user_id = fields.Many2one('res.users', string='Registrado por', required=True, readonly=True,
                              default=lambda self: self.env.user)
    warehouse_id = fields.Many2one('stock.warehouse', string='Local', check_company=True)
    entry_type = fields.Selection(LOGBOOK_TYPES, string='Tipo', required=True, default='other')
    description = fields.Text(string='Detalle', required=True)
    correction_of_id = fields.Many2one(
        'pharmacy.logbook.entry', string='Corrige a', check_company=True,
        help='Asiento anterior que este corrige: el original queda legible.')
    res_model = fields.Char(string='Documento (modelo)', readonly=True)
    res_id = fields.Many2oneReference(string='Documento', model_field='res_model', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company = self.env['res.company'].browse(vals.get('company_id')) or self.env.company
                vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code(
                    'pharmacy.logbook.entry') or '/'
        return super().create(vals_list)

    def write(self, vals):
        raise UserError(self.env._(
            'El libro de ocurrencias no se modifica: registre un asiento nuevo que corrija '
            'al anterior.'))

    @api.ondelete(at_uninstall=False)
    def _unlink_never(self):
        raise UserError(self.env._('Los asientos del libro de ocurrencias no se borran.'))

    def action_correct(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pharmacy.logbook.entry',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_correction_of_id': self.id,
                'default_entry_type': self.entry_type,
                'default_warehouse_id': self.warehouse_id.id,
            },
        }

    @api.model
    def _log(self, entry_type, description, warehouse=None, record=None):
        """Asiento desde otro proceso (dispensación autorizada, alerta, SRA)."""
        # El asiento lo crea el sistema en nombre de quien hizo la operación:
        # un técnico puede disparar una alerta aunque no gestione el libro.
        logbook_sudo = self.sudo()
        return logbook_sudo.create({
            'entry_type': entry_type,
            'description': description,
            'warehouse_id': warehouse.id if warehouse else False,
            'user_id': self.env.user.id,
            'company_id': (record.company_id.id if record and 'company_id' in record._fields
                           and record.company_id else self.env.company.id),
            'res_model': record._name if record else False,
            'res_id': record.id if record else False,
        })


class ResCompany(models.Model):
    _inherit = 'res.company'

    pharmacy_prescription_policy = fields.Selection([
        ('block', 'Bloquear la venta sin receta'),
        ('warn', 'Solo avisar'),
    ], string='Venta sin receta', default='block', required=True,
        help='Productos con receta médica. Con «Bloquear», un químico farmacéutico puede '
             'autorizar la excepción y queda en el libro de ocurrencias. Los controlados nunca '
             'admiten excepción.')
    pharmacy_pharmacist_policy = fields.Selection([
        ('warn', 'Avisar'),
        ('block', 'Bloquear'),
    ], string='Sin Q.F. en turno', default='warn', required=True,
        help='Qué hacer al vender un producto con receta si quien atiende no es químico '
             'farmacéutico. Cada aviso queda en el libro de ocurrencias.')
    pharmacy_expiry_alert_days = fields.Integer(
        string='Avisar vencimientos con', default=90,
        help='Días antes del vencimiento del lote en que se avisa.')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pharmacy_prescription_policy = fields.Selection(
        related='company_id.pharmacy_prescription_policy', readonly=False)
    pharmacy_pharmacist_policy = fields.Selection(
        related='company_id.pharmacy_pharmacist_policy', readonly=False)
    pharmacy_expiry_alert_days = fields.Integer(
        related='company_id.pharmacy_expiry_alert_days', readonly=False)

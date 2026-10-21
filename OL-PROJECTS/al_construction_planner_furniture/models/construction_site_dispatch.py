# -*- coding: utf-8 -*-
"""Formato del lote del módulo (paquete 1.10, M110-09) y despacho a obra por
departamento (M110-05).

* El lote del módulo sale de un formato por compañía con claves de la obra,
  el departamento, la tipología y el módulo. Por defecto es el de siempre,
  «<nombre de la obra> <departamento>».
* Un tipo de operación marcado «Despacho a obra por unidad» lleva la obra y
  el departamento en sus transferencias: al reservarla, los módulos del
  departamento que van en ella quedan «En tránsito»; al validarla, los que
  salieron pasan a «En obra» y la transferencia nombra los que faltan."""
import re
from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

DEFAULT_LOT_PATTERN = '{obra_nombre} {unidad}'
LOT_KEYS = ('obra', 'obra_prefijo', 'obra_nombre', 'unidad', 'unidad_num', 'tipologia',
            'modulo')
# Sin str.format: Odoo 19 lo parchea y devuelve la plantilla sin formatear
# si una clave se parece a un atributo prohibido.
LOT_KEY_RE = re.compile(r'\{([^{}]*)\}')


def lot_pattern_keys(pattern):
    return LOT_KEY_RE.findall(pattern or '')


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_module_lot_pattern = fields.Char(
        string='Formato del lote del módulo', default=DEFAULT_LOT_PATTERN,
        help='Claves: {obra}, {obra_prefijo}, {obra_nombre}, {unidad}, {unidad_num}, '
             '{tipologia} y {modulo}. Por ejemplo {obra_prefijo}-{unidad_num}-{tipologia}-{modulo}.')
    construction_dispatch_picking_type_id = fields.Many2one(
        'stock.picking.type', string='Tipo de operación del envío a obra',
        domain="[('code', 'in', ('internal', 'outgoing')), ('company_id', '=', id)]",
        help='Tipo de operación del envío de módulos del planificador. Vacío: el tipo interno '
             'del primer almacén de la compañía.')

    @api.constrains('construction_module_lot_pattern')
    def _check_construction_module_lot_pattern(self):
        for company in self:
            unknown = sorted(set(lot_pattern_keys(company.construction_module_lot_pattern))
                             - set(LOT_KEYS))
            if unknown:
                raise ValidationError(self.env._(
                    'Claves desconocidas en el formato del lote: %(unknown)s. Las válidas son '
                    '%(valid)s.', unknown=', '.join('{%s}' % key for key in unknown),
                    valid=', '.join('{%s}' % key for key in LOT_KEYS)))


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_module_lot_pattern = fields.Char(
        related='company_id.construction_module_lot_pattern', readonly=False)
    construction_dispatch_picking_type_id = fields.Many2one(
        related='company_id.construction_dispatch_picking_type_id', readonly=False)


class ConstructionResourcePlan(models.Model):
    _inherit = 'construction.resource.plan'

    @api.model
    def _module_lot_values(self, project, product, apartment):
        """Valores de las claves del formato del lote."""
        code = (getattr(project, 'construction_code', False) or '') or project.name or ''
        digits = ''.join(re.findall(r'\d', apartment.name or ''))
        module = self.env['construction.typology.module'].search(
            [('product_id', '=', product.id)], limit=1)
        return {
            'obra': code,
            'obra_prefijo': code.split('-')[0],
            'obra_nombre': project.name or '',
            'unidad': apartment.name or '',
            'unidad_num': digits.zfill(4) if digits else '',
            'tipologia': module.typology_id.code or '',
            'modulo': module.code or '',
        }

    @api.model
    def _module_lot_name(self, project, product, apartment, company=None):
        """Nombre del lote del módulo en el departamento según el formato de
        la compañía (M110-09)."""
        company = company or project.company_id or self.env.company
        pattern = company.construction_module_lot_pattern or DEFAULT_LOT_PATTERN
        values = self._module_lot_values(project, product, apartment)
        name = LOT_KEY_RE.sub(lambda match: values.get(match.group(1), ''), pattern)
        return ' '.join(name.split()), values

    def _module_lot(self, product, apartment):
        """Lote del módulo en el departamento (se crea la primera vez)."""
        self.ensure_one()
        name, values = self._module_lot_name(self.project_id, product, apartment,
                                             self.company_id)
        pattern = self.company_id.construction_module_lot_pattern or DEFAULT_LOT_PATTERN
        if 'unidad_num' in lot_pattern_keys(pattern) and not values['unidad_num']:
            self.message_post(body=self.env._(
                '%s no tiene número en su nombre: el lote %s queda sin el número de la unidad.',
                apartment.display_name, name))
        Lot = self.env['stock.lot']
        lot = Lot.search([('product_id', '=', product.id), ('name', '=', name)], limit=1)
        return lot or Lot.create({'product_id': product.id, 'name': name,
                                  'company_id': self.company_id.id})

    def _department_lot(self, product, apartment):
        """Alias del paquete 1.8: el lote sale del formato (M110-09)."""
        return self._module_lot(product, apartment)

    def _construction_dispatch_picking_type(self):
        """Tipo de operación del envío a obra: el del ajuste o, sin ajuste, el
        interno del primer almacén (como hasta el paquete 1.9)."""
        self.ensure_one()
        picking_type = self.company_id.construction_dispatch_picking_type_id
        if picking_type:
            return picking_type, picking_type.default_location_src_id
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)], limit=1)
        return warehouse.int_type_id, warehouse.lot_stock_id

    def action_ship_modules(self, apartments, loose=None):
        picking = super().action_ship_modules(apartments, loose)
        if len(apartments) == 1 and 'construction_apartment_task_id' in picking._fields:
            picking.construction_apartment_task_id = apartments
        return picking


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    construction_site_dispatch = fields.Boolean(
        string='Despacho a obra por unidad',
        help='Las transferencias de este tipo llevan obra y departamento, y al validarlas los '
             'módulos del departamento pasan a «En obra».')


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    construction_site_dispatch = fields.Boolean(
        related='picking_type_id.construction_site_dispatch', string='Despacho a obra por unidad')
    construction_apartment_task_id = fields.Many2one(
        'project.task', string='Departamento', index='btree_not_null',
        domain="[('project_id', '=', construction_project_id), "
               "('construction_level', '=', 'apartment')]",
        help='Departamento (unidad) que recibe los módulos del despacho (paquete 1.10, M110-05).')

    # ------------------------------------------------------------------
    # Obra propuesta desde la ubicación de destino
    # ------------------------------------------------------------------
    @api.model
    def _construction_project_from_location(self, location):
        """La obra cuya ubicación es el destino o una ubicación madre de él."""
        Project = self.env['project.project']
        if not location or 'construction_location_id' not in Project._fields:
            return Project
        projects = Project.search([('construction_location_id', 'parent_of', location.id)])
        return projects.sorted(
            lambda p: len(p.construction_location_id.parent_path or ''), reverse=True)[:1]

    @api.onchange('location_dest_id', 'picking_type_id')
    def _onchange_construction_dispatch_project(self):
        for picking in self:
            if picking.construction_site_dispatch and not picking.construction_project_id:
                picking.construction_project_id = picking._construction_project_from_location(
                    picking.location_dest_id)

    @api.onchange('construction_project_id')
    def _onchange_construction_dispatch_apartment(self):
        for picking in self:
            apartment = picking.construction_apartment_task_id
            if apartment and apartment.project_id != picking.construction_project_id:
                picking.construction_apartment_task_id = False

    @api.model_create_multi
    def create(self, vals_list):
        pickings = super().create(vals_list)
        for picking in pickings.filtered(
                lambda p: p.construction_site_dispatch and not p.construction_project_id):
            project = self._construction_project_from_location(picking.location_dest_id)
            if project:
                picking.construction_project_id = project
        return pickings

    # ------------------------------------------------------------------
    # Módulos del departamento
    # ------------------------------------------------------------------
    def _construction_department_modules(self):
        """{producto del módulo: tareas de módulo del departamento} por id."""
        self.ensure_one()
        # Logística despacha sin acceso al plan: solo se leen las tareas de
        # módulo del departamento y el producto de su módulo de tipología.
        tasks_sudo = self.env['project.task'].sudo().search([
            ('construction_apartment_task_id', '=', self.construction_apartment_task_id.id),
            ('construction_level', '=', 'module')], order='id')
        result = defaultdict(lambda: self.env['project.task'].sudo())
        for task in tasks_sudo:
            typology = task.construction_space_task_id.construction_typology_id
            template = typology.module_line_ids.filtered(
                lambda t, code=task.construction_module_code: t.code == code)[:1]
            if template.product_id:
                result[template.product_id] |= task
        return result

    def _construction_dispatch_pickings(self):
        return self.filtered(lambda p: p.construction_site_dispatch
                             and p.construction_apartment_task_id)

    @staticmethod
    def _construction_available_modules(tasks, picking):
        """Módulos que puede llevar ``picking``: sin otra transferencia hecha y
        sin instalar ni entregar."""
        return tasks.filtered(
            lambda t: t.construction_unit_state not in ('installed', 'delivered')
            and (not t.construction_shipment_picking_id
                 or t.construction_shipment_picking_id == picking
                 or t.construction_shipment_picking_id.state == 'cancel'))

    def _construction_link_dispatch_modules(self):
        """Al confirmar o reservar: los módulos del departamento cuyo producto
        está en la transferencia quedan con ella, hasta la cantidad de cada
        producto (quedan «En tránsito»)."""
        for picking in self._construction_dispatch_pickings().filtered(
                lambda p: p.state not in ('draft', 'done', 'cancel')):
            modules = picking._construction_department_modules()
            Task_sudo = self.env['project.task'].sudo()
            chosen = Task_sudo
            for product, tasks in modules.items():
                moves = picking.move_ids.filtered(
                    lambda m, p=product: m.product_id == p and m.state != 'cancel')
                qty = int(round(sum(m.product_uom._compute_quantity(
                    m.product_uom_qty, product.uom_id) for m in moves)))
                available = self._construction_available_modules(tasks, picking).sorted(
                    lambda t: (t.construction_shipment_picking_id != picking, t.id))
                chosen |= available[:qty]
            linked = Task_sudo.search([('construction_shipment_picking_id', '=', picking.id)])
            (linked - chosen).write({'construction_shipment_picking_id': False})
            (chosen - linked).write({'construction_shipment_picking_id': picking.id})

    def _construction_request_apartment(self):
        """Departamento de las líneas del requerimiento de obra que lleva la
        transferencia, si es uno solo. El enlace del movimiento con la línea
        es del requerimiento de obra, que este puente no exige."""
        self.ensure_one()
        Task = self.env['project.task']
        if 'construction_request_line_id' not in self.env['stock.move']._fields:
            return Task
        # Logística no lee necesariamente las tareas de la obra: solo se
        # busca el departamento de las líneas que despacha.
        moves_sudo = self.sudo().move_ids.filtered(lambda m: m.state != 'cancel')
        apartments = moves_sudo.construction_request_line_id.task_id.construction_apartment_task_id
        if len(apartments) != 1 or (self.construction_project_id
                                    and apartments.project_id != self.construction_project_id):
            return Task
        return apartments.sudo(False)

    def _construction_fill_request_apartment(self):
        """Un despacho a obra por unidad de un requerimiento toma el
        departamento de sus líneas (paquete 1.11): el almacenero no lo
        escribe a mano en cada despacho de material."""
        for picking in self.filtered(lambda p: p.construction_site_dispatch
                                     and not p.construction_apartment_task_id
                                     and p.state not in ('done', 'cancel')):
            apartment = picking._construction_request_apartment()
            if apartment:
                picking.construction_apartment_task_id = apartment
                if not picking.construction_project_id:
                    picking.construction_project_id = apartment.project_id

    def action_confirm(self):
        self._construction_fill_request_apartment()
        res = super().action_confirm()
        self._construction_link_dispatch_modules()
        self._construction_propose_dispatch_lots()
        return res

    def action_assign(self):
        res = super().action_assign()
        self._construction_link_dispatch_modules()
        return res

    # ------------------------------------------------------------------
    # Lote del departamento (M110-09)
    # ------------------------------------------------------------------
    def _construction_expected_lot_name(self, product):
        self.ensure_one()
        name, _values = self.env['construction.resource.plan']._module_lot_name(
            self.construction_project_id, product, self.construction_apartment_task_id,
            self.company_id)
        return name

    def _construction_propose_dispatch_lots(self):
        """Cada línea propone el lote del departamento, si ya existe."""
        Lot = self.env['stock.lot']
        for picking in self._construction_dispatch_pickings():
            for move in picking.move_ids.filtered(
                    lambda m: m.product_id.tracking != 'none' and not m.construction_lot_id
                    and m.state not in ('done', 'cancel')):
                name = picking._construction_expected_lot_name(move.product_id)
                lot = Lot.search([('product_id', '=', move.product_id.id), ('name', '=', name)],
                                 limit=1)
                if lot:
                    move.construction_lot_id = lot

    # ------------------------------------------------------------------
    # Validar
    # ------------------------------------------------------------------
    def button_validate(self):
        self._construction_fill_request_apartment()
        missing = self.filtered(lambda p: p.construction_site_dispatch and (
            not p.construction_project_id or not p.construction_apartment_task_id))
        if missing:
            raise UserError(self.env._(
                'Indique la obra y el departamento de %s: su tipo de operación es un despacho a '
                'obra por unidad.', ', '.join(missing.mapped('name'))))
        return super().button_validate()

    def _action_done(self):
        res = super()._action_done()
        for picking in self._construction_dispatch_pickings().filtered(
                lambda p: p.state == 'done'):
            picking._construction_dispatch_done()
        return res

    def _construction_dispatch_done(self):
        """Los módulos que salieron pasan a «En obra» con la transferencia; los
        que no, quedan sin ella; la transferencia nombra los que faltan."""
        self.ensure_one()
        project = self.construction_project_id
        modules = self._construction_department_modules()
        Task_sudo = self.env['project.task'].sudo()
        dispatched = Task_sudo
        wrong_lots = []
        for move in self.move_ids.filtered(lambda m: m.state == 'done'):
            product = move.product_id
            if product.product_tmpl_id.construction_project_id != project or product not in modules:
                continue
            qty = int(round(move.product_uom._compute_quantity(move.quantity, product.uom_id)))
            available = self._construction_available_modules(modules[product], self).filtered(
                lambda t: t not in dispatched).sorted(
                lambda t: (t.construction_shipment_picking_id != self, t.id))
            dispatched |= available[:qty]
            if product.tracking != 'none':
                expected = self._construction_expected_lot_name(product)
                wrong_lots += [line.lot_id.name for line in move.move_line_ids
                               if line.lot_id and line.lot_id.name != expected]
        linked = Task_sudo.search([('construction_shipment_picking_id', '=', self.id)])
        (linked - dispatched).write({'construction_shipment_picking_id': False})
        dispatched.write({'construction_shipment_picking_id': self.id,
                          'construction_unit_state': 'on_site'})
        all_modules = Task_sudo.union(*modules.values()) if modules else Task_sudo
        pending = all_modules.filtered(
            lambda t: t.construction_unit_state not in ('on_site', 'installed', 'delivered'))
        if pending:
            self.message_post(body=self.env._(
                'No se despacharon: %s.', ', '.join(
                    '%s / %s' % (task.construction_space_task_id.name, task.name)
                    for task in pending)))
        if wrong_lots:
            self.message_post(body=self.env._(
                'Lotes que no corresponden al departamento %(apartment)s: %(lots)s.',
                apartment=self.construction_apartment_task_id.display_name,
                lots=', '.join(sorted(set(wrong_lots)))))

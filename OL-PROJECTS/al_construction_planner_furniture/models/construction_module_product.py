# -*- coding: utf-8 -*-
"""Productos del proyecto y envíos de planta a obra (v1.8, M18-15 y M18-16).

* Al aprobar el plan se crea en el maestro un producto fabricado por cada
  módulo de cada tipología de la obra (decidido por Vicente el 16-oct-2026):
  se identifica por obra, tipología y posición en el mueble (el código del
  módulo), lleva como atributos el tipo de módulo y el método de unión, su
  lista de materiales sale de la receta del módulo y se sigue por lote: un
  lote por departamento dice qué módulo va a qué ambiente. Al cerrar la obra
  los productos se archivan.
* La orden de fabricación «por módulo» produce esos productos con el lote de
  su departamento.
* Cada envío de planta a obra es una transferencia de inventario con los
  módulos producidos (con su departamento y ambiente) y los recursos sueltos;
  la guía de remisión sale de la transferencia con la localización peruana.
  Al recibirla en obra, los módulos pasan a «En obra»; lo que no llega o llega
  dañado queda con foto en el historial de la transferencia.
"""
from collections import defaultdict

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from .construction_furniture_model import JOIN_METHODS, MODULE_CLASSES

SHIPMENT_STATES = [
    ('planned', 'Planificado'),
    ('produced', 'Producido'),
    ('in_transit', 'En tránsito'),
    ('on_site', 'En obra'),
    ('installed', 'Instalado'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_module_categ_id = fields.Many2one(
        'product.category', string='Categoría de los productos de módulo',
        help='Categoría con la que se crean los productos de los módulos: su método de costo y '
             'sus cuentas. Sin ella, el producto usa el método de costo de la compañía.')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_module_categ_id = fields.Many2one(
        related='company_id.construction_module_categ_id', readonly=False)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    construction_project_id = fields.Many2one(
        'project.project', string='Obra del módulo', index='btree_not_null',
        help='Producto de un módulo de esta obra: se archiva al cerrar el plan.')


class ConstructionTypologyModule(models.Model):
    _inherit = 'construction.typology.module'

    product_id = fields.Many2one(
        'product.product', string='Producto del módulo', readonly=True, copy=False,
        help='Producto fabricado del módulo en la obra (se crea al aprobar el plan).')

    def _module_product_code(self):
        self.ensure_one()
        project = self.typology_id.project_id
        prefix = (getattr(project, 'construction_code', False) or 'OBRA%s' % project.id)
        return '%s-%s-%s' % (prefix, self.typology_id.code, self.code)

    def _attribute_values(self):
        """Valores de los atributos «Tipo de módulo» y «Método de unión»."""
        self.ensure_one()
        values = self.env['product.attribute.value']
        labels = {'construction_module_class': dict(MODULE_CLASSES).get(self.module_class),
                  'construction_join_method': dict(JOIN_METHODS).get(self.join_method)}
        for key, label in labels.items():
            if not label:
                continue
            attribute = self.env.ref('al_construction_planner_furniture.attribute_%s' % key[13:])
            value = attribute.value_ids.filtered(lambda v: v.name == label)[:1]
            if not value:
                value = self.env['product.attribute.value'].create(
                    {'attribute_id': attribute.id, 'name': label})
            values |= value
        return values

    @api.model
    def _construction_module_bom_values(self, company):
        """Etapas y planta de la lista del producto de módulo (paquete 1.10,
        M110-02): solo las etapas que consume la orden de fabricación (sin
        instalación ni acabado) y, con cadena de plantas, la planta de la
        última etapa. Los materiales sin etapa se conservan."""
        Stage = self.env['construction.stage']
        chain = Stage._production_chain(company)
        picking_type = chain[-1:].with_company(company).production_picking_type_id
        return Stage._production_codes(), picking_type

    def _ensure_product(self):
        """Producto fabricado del módulo con su lista de materiales."""
        Product = self.env['product.product']
        Bom = self.env['mrp.bom']
        created = Product
        for module in self:
            company = module.typology_id.company_id or self.env.company
            codes, picking_type = self._construction_module_bom_values(company)
            typology = module.typology_id
            if module.product_id and module.product_id.active:
                continue
            values = module._attribute_values()
            template_vals = {
                'name': '%s · %s · %s' % (typology.project_id.name, typology.code,
                                          module.name or module.code),
                'default_code': module._module_product_code(),
                'type': 'consu', 'is_storable': True, 'tracking': 'lot',
                'sale_ok': False, 'purchase_ok': False,
                'company_id': typology.company_id.id,
                'construction_project_id': typology.project_id.id,
                'categ_id': company.construction_module_categ_id.id,
                'attribute_line_ids': [Command.create({
                    'attribute_id': value.attribute_id.id,
                    'value_ids': [Command.set(value.ids)]}) for value in values],
            }
            # Odoo 20: «Fabricar» es ruta de almacén y se aplica sola al
            # producto con lista de materiales; ya no se enlaza al producto.
            template = self.env['product.template'].create(template_vals)
            product = template.product_variant_id
            module.product_id = product
            lines = [Command.create({
                'product_id': material.product_id.id, 'product_qty': material.qty,
                'uom_id': (material.uom_id or material.product_id.uom_id).id,
                'construction_consumption_stage': material.stage or False})
                for material in module.material_ids
                if not material.stage or material.stage in codes]
            if not lines and module.bom_id:
                lines = [Command.create({
                    'product_id': line.product_id.id, 'product_qty': line.product_qty,
                    'uom_id': line.uom_id.id,
                    'construction_consumption_stage': line.construction_consumption_stage})
                    for line in module.bom_id.bom_line_ids
                    if not line.construction_consumption_stage
                    or line.construction_consumption_stage in codes]
            if lines:
                Bom.create({'product_tmpl_id': template.id, 'product_id': product.id,
                            'product_qty': 1.0, 'type': 'normal',
                            'company_id': typology.company_id.id, 'bom_line_ids': lines,
                            'picking_type_id': picking_type.id or False})
            created |= product
        return created


class ConstructionResourcePlan(models.Model):
    _inherit = 'construction.resource.plan'

    def _construction_on_approve(self, previous):
        values = super()._construction_on_approve(previous)
        self._create_module_products()
        return values

    def _construction_module_templates(self):
        """Módulos de las tipologías con ambientes en la obra del plan."""
        self.ensure_one()
        spaces = self.env['project.task'].search([
            ('project_id', '=', self.project_id.id), ('construction_level', '=', 'space'),
            ('construction_typology_id', '!=', False)])
        return spaces.construction_typology_id.module_line_ids

    def _create_module_products(self):
        """Un producto por módulo de cada tipología de la obra (M18-15)."""
        for plan in self:
            # sudo: quien aprueba (la jefatura) no suele crear productos; los
            # productos del módulo nacen de la aprobación del plan.
            modules_sudo = plan._construction_module_templates().sudo()
            created = modules_sudo._ensure_product()
            if created:
                plan.message_post(body=self.env._(
                    '%s productos de módulo creados en el maestro con su lista de materiales.',
                    len(created)))
            # Paquete 1.10, M110-02: los módulos son los subproductos de la lista
            # de fabricación de su tipología.
            modules_sudo.typology_id._construction_sync_module_byproducts(plan)

    def _construction_on_close(self):
        super()._construction_on_close()
        # Al cerrar la obra, sus productos de módulo se archivan.
        templates_sudo = self.env['product.template'].sudo().search([
            ('construction_project_id', 'in', self.project_id.ids)])
        templates_sudo.action_archive()

    # ------------------------------------------------------------------
    # Órdenes de fabricación por módulo y departamento
    # ------------------------------------------------------------------
    def action_create_module_productions(self, apartments=None):
        """OF de los productos de módulo, una por producto y departamento, con
        el lote del departamento (M18-15)."""
        self.ensure_one()
        self._check_supply_wizard_state()
        Task = self.env['project.task']
        domain = [('project_id', '=', self.project_id.id), ('construction_level', '=', 'module')]
        if apartments:
            domain.append(('construction_apartment_task_id', 'in', apartments.ids))
        modules = Task.search(domain)
        groups = defaultdict(lambda: Task)
        templates = self._construction_module_templates()
        for module in modules:
            template = templates.filtered(
                lambda t, m=module: t.typology_id == m.construction_space_task_id
                .construction_typology_id and t.code == m.construction_module_code)[:1]
            if not template.product_id:
                continue
            groups[(template.product_id, module.construction_apartment_task_id)] |= module
        productions = self.env['mrp.production']
        for (product, apartment), tasks in groups.items():
            lot = self._module_lot(product, apartment)
            production = self.env['mrp.production'].create({
                'product_id': product.id, 'product_qty': len(tasks),
                'uom_id': product.uom_id.id, 'company_id': self.company_id.id,
                'origin': '%s · %s' % (self.display_name, apartment.display_name),
                'construction_module_task_ids': [Command.set(tasks.ids)],
            })
            production.lot_producing_ids = [Command.set(lot.ids)]
            productions |= production
        if not productions:
            raise UserError(self.env._(
                'No hay módulos con producto: apruebe el plan para crear los productos de '
                'módulo.'))
        self._mark_in_progress()
        return {
            'type': 'ir.actions.act_window', 'name': self.env._('Órdenes de fabricación por módulo'),
            'res_model': 'mrp.production', 'view_mode': 'list,form',
            'domain': [('id', 'in', productions.ids)],
        }

    # ------------------------------------------------------------------
    # Envíos de planta a obra (M18-16)
    # ------------------------------------------------------------------
    def _construction_site_location(self):
        """Ubicación de la obra: la del requerimiento de obra si está instalado;
        si no, una ubicación interna con el nombre de la obra."""
        self.ensure_one()
        project = self.project_id
        if 'construction_location_id' in project._fields and project.construction_location_id:
            return project.construction_location_id
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)], limit=1)
        Location = self.env['stock.location'].sudo()
        location = Location.search([('name', '=', project.name), ('usage', '=', 'internal'),
                                    ('location_id', '=', warehouse.view_location_id.id)],
                                   limit=1)
        return location or Location.create({
            'name': project.name, 'usage': 'internal',
            'location_id': warehouse.view_location_id.id, 'company_id': self.company_id.id})

    def action_ship_modules(self, apartments, loose=None):
        """Transferencia de planta a obra con los módulos de los departamentos
        (producto del módulo, lote del departamento) y los recursos sueltos
        ``loose`` = [(producto, cantidad)]."""
        self.ensure_one()
        # Paquete 1.10, M110-05: el tipo de operación del ajuste de la compañía
        # (la planta que arma); sin ajuste, el interno del primer almacén.
        picking_type, source = self._construction_dispatch_picking_type()
        dest = self._construction_site_location()
        Task = self.env['project.task']
        modules = Task.search([('project_id', '=', self.project_id.id),
                               ('construction_level', '=', 'module'),
                               ('construction_apartment_task_id', 'in', apartments.ids)])
        templates = self._construction_module_templates()
        groups = defaultdict(lambda: Task)
        for module in modules:
            template = templates.filtered(
                lambda t, m=module: t.typology_id == m.construction_space_task_id
                .construction_typology_id and t.code == m.construction_module_code)[:1]
            if template.product_id:
                groups[(template.product_id, module.construction_apartment_task_id)] |= module
        if not groups and not loose:
            raise UserError(self.env._('Los departamentos elegidos no tienen módulos con producto.'))
        moves = []
        for (product, apartment), tasks in groups.items():
            moves.append(Command.create({
                'product_id': product.id, 'product_uom_qty': len(tasks),
                'uom_id': product.uom_id.id, 'location_id': source.id,
                'location_dest_id': dest.id,
                'description_picking': '%s · %s' % (apartment.display_name, ', '.join(
                    tasks.construction_space_task_id.mapped('name'))),
                'construction_module_task_ids': [Command.set(tasks.ids)],
                'construction_lot_id': self._module_lot(product, apartment).id,
            }))
        for product, qty in loose or []:
            moves.append(Command.create({
                'product_id': product.id, 'product_uom_qty': qty, 'uom_id': product.uom_id.id,
                'location_id': source.id, 'location_dest_id': dest.id}))
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id, 'location_id': source.id,
            'location_dest_id': dest.id, 'origin': self.display_name,
            'construction_project_id': self.project_id.id, 'move_ids': moves,
        })
        modules.filtered(lambda t: t in Task.union(*groups.values())).sudo().write(
            {'construction_shipment_picking_id': picking.id})
        return picking


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    construction_module_task_ids = fields.Many2many(
        'project.task', 'mrp_production_construction_module_rel', 'production_id', 'task_id',
        string='Módulos de la obra')

    def _post_inventory(self, cancel_backorder=False):
        res = super()._post_inventory(cancel_backorder)
        # Los módulos de la OF terminada quedan «Producido».
        tasks_sudo = self.filtered(lambda p: p.state == 'done').construction_module_task_ids.sudo()
        tasks_sudo.filtered(lambda t: t.construction_unit_state in ('planned', 'production', False)
                            ).write({'construction_unit_state': 'produced'})
        return res


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    construction_project_id = fields.Many2one(
        'project.project', string='Obra', index='btree_not_null',
        help='Envío de planta a obra (v1.8, M18-16).')

    def _action_done(self):
        res = super()._action_done()
        # Recibido en obra: los módulos enviados pasan a «En obra».
        for picking in self.filtered('construction_project_id'):
            tasks_sudo = picking.move_ids.filtered(
                lambda m: m.state == 'done').construction_module_task_ids.sudo()
            tasks_sudo.filtered(lambda t: t.construction_unit_state not in (
                'installed', 'delivered')).write({'construction_unit_state': 'on_site'})
        return res


class StockMove(models.Model):
    _inherit = 'stock.move'

    construction_module_task_ids = fields.Many2many(
        'project.task', 'stock_move_construction_module_rel', 'move_id', 'task_id',
        string='Módulos de la obra')
    construction_lot_id = fields.Many2one('stock.lot', string='Lote del departamento')

    def _action_assign(self, force_qty=False):
        res = super()._action_assign(force_qty=force_qty)
        # El lote del departamento en la línea de la operación.
        for move in self.filtered('construction_lot_id'):
            for line in move.move_line_ids.filtered(lambda l: not l.lot_id):
                line.lot_id = move.construction_lot_id
        return res


class ProjectTask(models.Model):
    _inherit = 'project.task'

    construction_shipment_picking_id = fields.Many2one(
        'stock.picking', string='Envío a obra', index='btree_not_null', copy=False)
    construction_shipment_state = fields.Selection(
        SHIPMENT_STATES, string='Estado del envío', compute='_compute_construction_shipment_state',
        store=True)
    construction_shipment_date = fields.Datetime(
        related='construction_shipment_picking_id.date_done', string='Recibido en obra')

    @api.depends('construction_unit_state', 'construction_shipment_picking_id.state')
    def _compute_construction_shipment_state(self):
        for task in self:
            state = task.construction_unit_state
            picking = task.construction_shipment_picking_id
            if state in ('installed', 'delivered'):
                task.construction_shipment_state = 'installed'
            elif state == 'on_site' or picking.state == 'done':
                task.construction_shipment_state = 'on_site'
            elif picking and picking.state not in ('cancel', 'draft'):
                task.construction_shipment_state = 'in_transit'
            elif state == 'produced':
                task.construction_shipment_state = 'produced'
            else:
                task.construction_shipment_state = 'planned' if task.construction_level == \
                    'module' else False

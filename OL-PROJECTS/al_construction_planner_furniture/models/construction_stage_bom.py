# -*- coding: utf-8 -*-
"""Listas de materiales por etapa (paquete 1.10, M110-02).

La lista de la tipología (``bom_id``) sigue siendo la receta completa, con
todas las etapas: de ella salen el plan y el asistente de siempre. Con una
cadena de plantas en el catálogo de etapas (M110-01), el importador arma
además una lista por cada etapa de la cadena:

* las etapas intermedias fabrican un producto intermedio de la obra (el
  paquete de piezas), en su planta, con sus materiales y el intermedio de la
  etapa anterior;
* la última etapa fabrica el producto de la tipología en su planta
  (``production_bom_id``), con el intermedio anterior, sus materiales y, al
  aprobar el plan, los productos de módulo como subproductos.

Las listas de fabricación van con secuencia 1 y la receta con 1000: Odoo
elige por secuencia. Volver a importar no duplica nada y conserva las
operaciones puestas a mano.

Paquete 1.11: una lista sin operaciones recibe la de la estación de su etapa
(M111-03) y sus cantidades suman las de los módulos ya redondeadas como el
plan, para que plan y lista coincidan (M111-04)."""
from collections import defaultdict

from odoo import Command, fields, models
from odoo.tools import float_round

# La receta queda detrás de las listas de fabricación.
RECIPE_SEQUENCE = 1000
PRODUCTION_SEQUENCE = 1


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    def _construction_add_stage_operation(self, stage, company):
        """Operación de la estación de ``stage`` en las listas sin ninguna
        (también archivada). Devuelve las listas que la recibieron."""
        vals = stage._production_operation_vals(company)
        done = self.browse()
        if not vals:
            return done
        for bom in self:
            if bom.with_context(active_test=False).operation_ids:
                continue
            bom.write({'operation_ids': [Command.create(vals)]})
            done |= bom
        return done


class ConstructionTypology(models.Model):
    _inherit = 'construction.typology'

    production_bom_id = fields.Many2one(
        'mrp.bom', string='Lista de fabricación', readonly=True, copy=False,
        check_company=True,
        help='Lista de la última etapa de la cadena de plantas (paquete 1.10, M110-02): la '
             'usa el asistente de órdenes. Vacía: la orden sale de la lista de materiales.')

    def _construction_project_prefix(self):
        """Prefijo de los códigos de producto de la obra, el mismo que el de
        los productos de módulo."""
        self.ensure_one()
        project = self.project_id
        return getattr(project, 'construction_code', False) or 'OBRA%s' % project.id

    def _construction_stage_materials(self, codes):
        """{(producto, unidad, etapa): cantidad} de las etapas ``codes``: los
        materiales de los módulos o, si no tienen, la receta."""
        self.ensure_one()
        result = defaultdict(float)
        materials = self.module_line_ids.material_ids
        if materials:
            # El plan guarda una línea por módulo con la precisión de la
            # cantidad: se suma lo mismo para no dar excesos de céntimos.
            digits = self.env['decimal.precision'].precision_get('Product Unit')
            for material in materials:
                if material.stage in codes:
                    uom = material.uom_id or material.product_id.uom_id
                    result[(material.product_id, uom, material.stage)] += float_round(
                        material.qty, precision_digits=digits)
            return result
        # La receta la lee quien importa, aunque no administre las listas.
        bom_sudo = self.sudo().bom_id
        factor = 1.0 / (bom_sudo.product_qty or 1.0)
        for line in bom_sudo.bom_line_ids:
            stage = line.construction_consumption_stage
            if stage in codes:
                result[(line.product_id, line.product_uom_id, stage)] += line.product_qty * factor
        return result

    def _construction_intermediate_product(self, stage, company):
        """Producto intermedio que entrega ``stage`` (se crea la primera vez)."""
        self.ensure_one()
        code = '%s-%s-%s' % (self._construction_project_prefix(), self.code,
                             (stage.code or '').upper())
        Product_sudo = self.env['product.product'].sudo().with_context(active_test=False)
        product = Product_sudo.search([('default_code', '=', code),
                                       ('company_id', 'in', (company.id, False))], limit=1)
        category = stage.with_company(company).intermediate_categ_id
        if not product:
            values = {
                'name': '%s · %s · %s' % (stage.name, self.code, self.project_id.name),
                'default_code': code, 'type': 'consu', 'is_storable': True,
                'tracking': 'none', 'sale_ok': False, 'purchase_ok': False,
                'company_id': company.id,
                'construction_project_id': self.project_id.id,
            }
            if category:
                values['categ_id'] = category.id
            product = Product_sudo.create(values)
        else:
            values = {'active': True}
            if category and product.categ_id != category:
                values['categ_id'] = category.id
            product.write(values)
        return product

    def _construction_write_bom(self, bom_sudo, template, stage, company, components,
                                intermediate):
        """Crea o actualiza la lista de una etapa: sus componentes y, si no
        tiene operaciones, la de la estación de la etapa (M111-03). Las
        operaciones y lo demás puesto a mano se conservan."""
        picking_type = stage.with_company(company).production_picking_type_id
        values = {'sequence': PRODUCTION_SEQUENCE, 'picking_type_id': picking_type.id,
                  'project_id': self.project_id.id, 'code': stage._label()}
        if not bom_sudo:
            bom_sudo = self.env['mrp.bom'].sudo().create(dict(
                values, product_tmpl_id=template.id, product_qty=1.0, type='normal',
                company_id=company.id))
        else:
            bom_sudo.write(dict(values, active=True))
        current = {}
        for line in bom_sudo.bom_line_ids:
            key = (line.product_id, line.construction_consumption_stage or False,
                   line.construction_intermediate)
            current.setdefault(key, line)
        commands = []
        wanted = [((product, stage_code, False), {
            'product_qty': qty, 'product_uom_id': uom.id,
            'construction_consumption_stage': stage_code, 'construction_intermediate': False})
            for (product, uom, stage_code), qty in components.items()]
        if intermediate:
            wanted.insert(0, ((intermediate, False, True), {
                'product_qty': 1.0, 'product_uom_id': intermediate.uom_id.id,
                'construction_consumption_stage': False, 'construction_intermediate': True}))
        for key, vals in wanted:
            line = current.pop(key, None)
            if line:
                commands.append(Command.update(line.id, vals))
            else:
                commands.append(Command.create(dict(vals, product_id=key[0].id)))
        commands += [Command.delete(line.id) for line in current.values()]
        bom_sudo.write({'bom_line_ids': commands})
        bom_sudo._construction_add_stage_operation(stage, company)
        return bom_sudo

    def _construction_sync_stage_boms(self, company=None):
        """Listas de fabricación de la tipología según la cadena de plantas de
        la compañía. Devuelve los avisos para el resultado del importador."""
        self.ensure_one()
        company = company or self.company_id or self.env.company
        Stage = self.env['construction.stage']
        chain = Stage._production_chain(company)
        warnings = []
        if not chain:
            return warnings
        template = self.sudo().product_tmpl_id
        if not template:
            return warnings
        materials = self._construction_stage_materials(set(chain.mapped('code')))
        kept = chain.filtered(lambda stage: any(key[2] == stage.code for key in materials))
        if not kept:
            warnings.append(self.env._(
                '%s no tiene materiales de las etapas de la cadena: las órdenes salen de la '
                'lista de materiales.', self.display_name))
            return warnings
        Bom_sudo = self.env['mrp.bom'].sudo().with_context(active_test=False)
        previous = self.env['product.product']
        used = self.env['product.product']
        for index, stage in enumerate(kept):
            components = {key: qty for key, qty in materials.items() if key[2] == stage.code}
            if stage == kept[-1]:
                bom = self._construction_write_bom(
                    self.sudo().production_bom_id, template, stage, company, components,
                    previous)
                if self.production_bom_id != bom:
                    self.sudo().production_bom_id = bom
                continue
            product = self._construction_intermediate_product(stage, company)
            if not stage.with_company(company).intermediate_categ_id:
                warnings.append(self.env._(
                    '%(stage)s no tiene «Categoría de lo que entrega»: %(product)s queda en la '
                    'categoría por defecto.', stage=stage._label(), product=product.default_code))
            bom = Bom_sudo.search([('product_tmpl_id', '=', product.product_tmpl_id.id),
                                   ('company_id', 'in', (company.id, False))], limit=1)
            self._construction_write_bom(bom, product.product_tmpl_id, stage, company,
                                         components, previous)
            used |= product
            previous = product
        # Una etapa que ya no tiene materiales deja de fabricar su intermedio.
        for stage in chain - kept[:-1]:
            code = '%s-%s-%s' % (self._construction_project_prefix(), self.code,
                                 (stage.code or '').upper())
            stale = self.env['product.product'].sudo().search(
                [('default_code', '=', code), ('company_id', 'in', (company.id, False))])
            stale -= used
            if stale:
                Bom_sudo.search([('product_tmpl_id', 'in', stale.product_tmpl_id.ids)]).write(
                    {'active': False})
                stale.product_tmpl_id.write({'active': False})
        return warnings

    def _construction_module_cost(self, plan=None):
        """{módulo: costo de material de las etapas de la cadena}: cantidad por
        el precio del plan del producto o, si el plan no lo tiene, su costo."""
        self.ensure_one()
        company = self.company_id or self.env.company
        codes = set(self.env['construction.stage']._production_chain(company).mapped('code'))
        prices = {}
        if plan:
            # El costo del plan lo lee el sistema al aprobarlo.
            lines_sudo = self.env['construction.resource.plan.line'].sudo().search([
                ('plan_id', '=', plan.id), ('resource_type', '=', 'material'),
                ('product_id', 'in', self.module_line_ids.material_ids.product_id.ids)])
            for line in lines_sudo:
                if line.price_unit_planned and line.product_id not in prices:
                    prices[line.product_id] = line.price_unit_planned
        result = {}
        for module in self.module_line_ids:
            result[module] = sum(
                material.qty * prices.get(material.product_id,
                                          material.product_id.with_company(company).standard_price)
                for material in module.material_ids if material.stage in codes)
        return result

    def _construction_sync_module_byproducts(self, plan=None):
        """Subproductos de la lista de fabricación: un producto de módulo por
        módulo, con participación en el costo según su costo de material. La
        tipología queda con 0 % y sirve de control."""
        for typology in self:
            bom_sudo = typology.sudo().production_bom_id
            modules = typology.module_line_ids.filtered('product_id')
            if not bom_sudo or not modules:
                continue
            costs = typology._construction_module_cost(plan)
            total = sum(costs.get(module, 0.0) for module in modules)
            shares = {}
            for module in modules:
                share = costs.get(module, 0.0) / total * 100 if total else 100.0 / len(modules)
                shares[module] = float_round(share, precision_digits=2)
            biggest = max(modules, key=lambda m: (shares[m], -m.id))
            shares[biggest] = float_round(
                shares[biggest] + 100.0 - sum(shares.values()), precision_digits=2)
            current = {byproduct.product_id: byproduct for byproduct in bom_sudo.byproduct_ids}
            commands = []
            for module in modules:
                product = module.product_id
                vals = {'product_qty': 1.0, 'product_uom_id': product.uom_id.id,
                        'cost_share': shares[module]}
                byproduct = current.pop(product, None)
                if byproduct:
                    commands.append(Command.update(byproduct.id, vals))
                else:
                    commands.append(Command.create(dict(vals, product_id=product.id)))
            commands += [Command.delete(byproduct.id) for byproduct in current.values()]
            bom_sudo.write({'byproduct_ids': commands})


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def action_construction_complete_operations(self):
        """Pone la operación de su etapa en las listas por etapa de la obra que
        no tienen operaciones (M111-03), para obras importadas antes."""
        self.ensure_one()
        company = self.company_id or self.env.company
        chain = self.env['construction.stage']._production_chain(company)
        by_type = {stage.with_company(company).production_picking_type_id: stage
                   for stage in chain}
        # Las listas de la obra las arma el sistema (como el importador).
        boms_sudo = self.env['mrp.bom'].sudo().search([
            ('project_id', '=', self.id), ('sequence', '=', PRODUCTION_SEQUENCE),
            ('picking_type_id', 'in', [t.id for t in by_type])])
        done = self.env['mrp.bom'].sudo()
        for bom_sudo in boms_sudo:
            done |= bom_sudo._construction_add_stage_operation(
                by_type[bom_sudo.picking_type_id], company)
        if done:
            message = self.env._('Operaciones agregadas en %s listas.', len(done))
            kind = 'success'
        else:
            message = self.env._(
                'Ninguna lista sin operaciones con estación en su etapa (Configuración › '
                'Etapas).')
            kind = 'warning'
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': self.env._('Completar operaciones'), 'message': message,
                           'type': kind, 'sticky': False}}

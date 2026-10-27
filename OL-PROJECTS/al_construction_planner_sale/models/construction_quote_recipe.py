# -*- coding: utf-8 -*-
"""Recetas de una cotización sin obra (CR-18, D4).

El envío al presupuesto de una cotización sin obra guarda las recetas que
usan sus partidas como recetas de la cotización, sin tocar la biblioteca de
la compañía. Al crear los niveles de la obra desde la cotización, esas
recetas se copian a la obra una sola vez; desde ahí manda la obra."""
from odoo import fields, models


class ConstructionExecutionTemplate(models.Model):
    _inherit = 'construction.execution.template'

    construction_sale_order_id = fields.Many2one(
        'sale.order', string='Cotización de origen', index='btree_not_null', copy=False,
        ondelete='cascade', check_company=True,
        help='Receta de una cotización sin obra: no es de la biblioteca; se copia a la obra al '
             'crear sus niveles.')

    # El mismo código puede estar en la biblioteca y en cada cotización.
    _code_company_unique = models.UniqueIndex(
        '(code, company_id, COALESCE(project_id, 0), COALESCE(construction_sale_order_id, 0))',
        'Ya hay una receta con ese código en la compañía (y la obra o la cotización).')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # Las recetas de una cotización no se eligen en una obra (sus copias sí).
    construction_execution_template_id = fields.Many2one(
        domain="[('construction_sale_order_id', '=', False), '|', ('project_id', '=', False), "
               "('project_id', '=', project_id)]")


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    construction_execution_template_id = fields.Many2one(
        'construction.execution.template', string='Receta (APU)', copy=True,
        index='btree_not_null', check_company=True,
        help='La receta de la partida en la hoja de trabajo o en el libro de carga.')


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    construction_recipe_ids = fields.One2many(
        'construction.execution.template', 'construction_sale_order_id',
        string='Recetas de la cotización')

    def _construction_offer_locked(self):
        """Cotización confirmada o bloqueada: su precio y su metrado ofertado
        solo cambian por un cambio de obra (CR-18, D3)."""
        self.ensure_one()
        return self.state == 'sale' or self.locked

    def write(self, vals):
        res = super().write(vals)
        if vals.get('project_id'):
            for order in self:
                order._construction_copy_quote_recipes(order.project_id)
        return res

    def _construction_copy_quote_recipes(self, project):
        """Copia a la obra las recetas de la cotización que la obra aún no
        tiene (por código) y deja las partidas apuntando a la copia. Devuelve
        ``{código: receta de la obra}``."""
        self.ensure_one()
        Template = self.env['construction.execution.template']
        if not project:
            return {}
        own = {recipe.code: recipe for recipe in Template.with_context(active_test=False).search(
            [('project_id', '=', project.id)])}
        for recipe in self.construction_recipe_ids:
            if recipe.code not in own:
                own[recipe.code] = recipe.copy({
                    'project_id': project.id, 'construction_sale_order_id': False,
                    'code': recipe.code, 'name': recipe.name})
        for line in self.order_line.filtered('construction_execution_template_id'):
            recipe = line.construction_execution_template_id
            if recipe.construction_sale_order_id and recipe.code in own:
                line.construction_execution_template_id = own[recipe.code]
        return own

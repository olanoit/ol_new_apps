# -*- coding: utf-8 -*-
"""Órdenes de fabricación por módulo y envíos de planta a obra por
departamento (v1.8, M18-15 y M18-16)."""
from odoo import api, fields, models


class ConstructionModuleDispatchWizard(models.TransientModel):
    _name = 'construction.module.dispatch.wizard'
    _description = 'Fabricar o enviar los módulos de la obra'

    plan_id = fields.Many2one('construction.resource.plan', string='Plan', required=True)
    project_id = fields.Many2one(related='plan_id.project_id', string='Obra')
    action = fields.Selection(
        [('production', 'Órdenes de fabricación por módulo'),
         ('shipment', 'Envío de planta a obra')], string='Qué hacer', required=True,
        default='production')
    apartment_ids = fields.Many2many(
        'project.task', string='Departamentos',
        domain="[('project_id', '=', project_id), ('construction_level', '=', 'apartment')]",
        help='Vacío: todos los de la obra.')
    loose_line_ids = fields.One2many('construction.module.dispatch.wizard.line', 'wizard_id',
                                     string='Recursos sueltos')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        task_ids = self.env.context.get('construction_selection_task_ids') or []
        if task_ids and 'apartment_ids' in fields_list:
            tasks = self.env['project.task'].browse(task_ids)
            apartments = tasks.filtered(lambda t: t.construction_level == 'apartment') \
                | tasks.construction_apartment_task_id
            res['apartment_ids'] = [(6, 0, apartments.ids)]
        return res

    def _apartments(self):
        self.ensure_one()
        return self.apartment_ids or self.env['project.task'].search([
            ('project_id', '=', self.project_id.id), ('construction_level', '=', 'apartment')])

    def action_confirm(self):
        self.ensure_one()
        apartments = self._apartments()
        if self.action == 'production':
            return self.plan_id.action_create_module_productions(apartments)
        picking = self.plan_id.action_ship_modules(
            apartments, [(line.product_id, line.qty) for line in self.loose_line_ids])
        return {'type': 'ir.actions.act_window', 'res_model': 'stock.picking',
                'res_id': picking.id, 'view_mode': 'form'}


class ConstructionModuleDispatchWizardLine(models.TransientModel):
    _name = 'construction.module.dispatch.wizard.line'
    _description = 'Recurso suelto del envío'

    wizard_id = fields.Many2one('construction.module.dispatch.wizard', required=True,
                                ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    qty = fields.Float(string='Cantidad', default=1.0)

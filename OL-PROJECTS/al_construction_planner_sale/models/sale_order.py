# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    construction_site_name = fields.Char(
        string='Nombre de la obra',
        help='Con la referencia del cliente como código de obra, la obra que crea esta venta '
             'se llama «<código> <nombre de la obra>» (p. ej. «ROOFG-04-25 ROOF GARDEN»).')

    def _construction_is_site_order(self):
        """Venta de una obra: su proyecto es una obra o creó una."""
        self.ensure_one()
        # sudo: quien factura no siempre lee los proyectos; solo se pregunta
        # si la venta es de una obra.
        order_sudo = self.sudo()
        return bool(order_sudo.project_id.is_construction_site) or bool(
            self.env['project.project'].sudo().search_count(
                [('construction_sale_order_id', '=', self.id)], limit=1))

    def action_confirm(self):
        """CREVAL, paquete 5, CR-44, punto 5 (decisión D2 del 02-nov): al
        confirmar la cotización de una obra sin contrato de obra, nace su
        contrato en borrador con cliente, obra y orden. Si ya tiene uno, no se
        crea otro."""
        res = super().action_confirm()
        for order in self.filtered(lambda o: o.state == 'sale'):
            order._construction_create_draft_contract()
        return res

    def _construction_draft_contract_project(self):
        self.ensure_one()
        # sudo: quien confirma la venta puede no leer proyectos; solo se busca
        # la obra de la venta.
        order_sudo = self.sudo()
        project = order_sudo.project_id if order_sudo.project_id.is_construction_site else \
            self.env['project.project'].sudo().search(
                [('construction_sale_order_id', '=', self.id)], limit=1)
        return project

    def _construction_create_draft_contract(self):
        self.ensure_one()
        project = self._construction_draft_contract_project()
        if not project:
            return False
        # sudo: el contrato de obra lo arma el sistema al confirmar la venta;
        # quien confirma es de Ventas y puede no administrar contratos.
        Contract_sudo = self.env['construction.contract'].sudo()
        if Contract_sudo.search_count([('project_id', '=', project.id),
                                       ('state', '!=', 'cancel')], limit=1):
            return False
        vals = {
            'name': self.env._('Venta %s', self.name),
            'project_id': project.id, 'company_id': self.company_id.id,
            'partner_id': self.partner_id.commercial_partner_id.id,
            'sale_order_id': self.id, 'currency_id': self.currency_id.id,
            'client_order_ref': self.client_order_ref or False,
        }
        template_name = self.company_id['construction_sale_milestone_template'] \
            if 'construction_sale_milestone_template' in self.company_id._fields else False
        if template_name:
            template = self.env['construction.milestone.template'].sudo().search(
                [('name', '=', template_name)], limit=1)
            if template:
                vals['milestone_template_id'] = template.id
        contract_sudo = Contract_sudo.create(vals)
        self.message_post(body=self.env._(
            'Contrato de obra %(contract)s creado en borrador para %(project)s.',
            contract=contract_sudo.name, project=project.display_name))
        return contract_sudo

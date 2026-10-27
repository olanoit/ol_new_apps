# -*- coding: utf-8 -*-
"""«Pedir reposición a planta» (paquete 1.11, M111-23).

La obra pide una pieza que hay que volver a fabricar (falla de fabricación,
daño, pérdida). Al enviarla, se crea la orden de fabricación en borrador en el
tipo de reposición de la planta, con el motivo, y el jefe de producción recibe
una actividad. Quien pide no entra a Fabricación: la reposición muestra el
estado de la orden y del despacho. Al terminar la orden, la pieza sale a la
obra con el «Despacho a obra» del almacén de la planta. La etapa Producción
del requerimiento puede quedar apagada: la pieza no pasa por él."""
from odoo import Command, api, fields, models
from odoo.exceptions import UserError

STATES = [
    ('draft', 'Borrador'),
    ('requested', 'Pedida a planta'),
    ('in_production', 'En fabricación'),
    ('produced', 'Fabricada, por despachar'),
    ('dispatched', 'Despachada a obra'),
    ('done', 'Recibida en obra'),
    ('cancel', 'Cancelada'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_replacement_type_id = fields.Many2one(
        'stock.picking.type', string='Tipo de la reposición a planta',
        domain="[('code', '=', 'mrp_operation'), ('company_id', '=', id)]",
        help='Operación de fabricación de la planta para las reposiciones que pide la obra '
             '(«Producción de piezas · reposición»). Vacío: no se piden reposiciones.')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_replacement_type_id = fields.Many2one(
        related='company_id.construction_replacement_type_id', readonly=False)


class ConstructionReplacementRequest(models.Model):
    _name = 'construction.replacement.request'
    _description = 'Reposición a planta'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(string='Reposición', required=True, readonly=True, copy=False,
                       default=lambda self: self.env._('Nueva'))
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 readonly=True, default=lambda self: self.env.company)
    project_id = fields.Many2one(
        'project.project', string='Obra', required=True, tracking=True, check_company=True,
        domain="[('is_construction_site', '=', True)]")
    task_id = fields.Many2one(
        'project.task', string='Nivel', check_company=True,
        domain="[('project_id', '=', project_id)]",
        help='Ambiente o módulo de la pieza (opcional).')
    request_id = fields.Many2one(
        'construction.material.request', string='Requerimiento de origen', check_company=True,
        readonly=True, copy=False)
    product_id = fields.Many2one(
        'product.product', string='Pieza', required=True, tracking=True, check_company=True,
        domain="[('type', '=', 'consu')]")
    product_qty = fields.Float(string='Cantidad', digits='Product Unit', required=True,
                               default=1.0)
    product_uom_id = fields.Many2one(
        'uom.uom', string='Unidad', compute='_compute_product_uom_id', store=True,
        readonly=False, precompute=True, required=True)
    reason_id = fields.Many2one(
        'construction.production.reason', string='Motivo', required=True, tracking=True,
        check_company=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    reason_note = fields.Text(string='Qué pasó')
    date_required = fields.Date(string='Fecha requerida', tracking=True)
    requested_by = fields.Many2one('res.users', string='Pedida por', required=True,
                                   readonly=True, default=lambda self: self.env.user)
    location_dest_id = fields.Many2one(
        'stock.location', string='Ubicación de obra', check_company=True,
        compute='_compute_location_dest_id', store=True, readonly=False, precompute=True,
        domain="[('usage', '=', 'internal')]")
    picking_type_id = fields.Many2one(
        'stock.picking.type', string='Planta', readonly=True, copy=False,
        check_company=True)
    # Quien pide no lee Fabricación: los datos de la orden y del despacho los
    # da la reposición.
    production_id = fields.Many2one('mrp.production', string='Orden de fabricación',
                                    readonly=True, copy=False, index='btree_not_null')
    production_name = fields.Char(related='production_id.name', string='Orden',
                                  compute_sudo=True)
    production_date = fields.Datetime(
        string='Fecha prevista', compute='_compute_production_info', compute_sudo=True)
    picking_id = fields.Many2one('stock.picking', string='Despacho a obra', readonly=True,
                                 copy=False, index='btree_not_null')
    picking_name = fields.Char(related='picking_id.name', string='Despacho',
                               compute_sudo=True)
    cancelled = fields.Boolean(readonly=True, copy=False)
    state = fields.Selection(STATES, string='Estado', compute='_compute_state', store=True,
                             tracking=True, compute_sudo=True)

    @api.depends('product_id')
    def _compute_product_uom_id(self):
        for request in self:
            request.product_uom_id = request.product_id.uom_id

    @api.depends('project_id')
    def _compute_location_dest_id(self):
        for request in self:
            request.location_dest_id = request.project_id.construction_location_id

    @api.depends('production_id.date_finished', 'production_id.construction_date_confirmed')
    def _compute_production_info(self):
        for request in self:
            production = request.production_id
            confirmed = production.construction_date_confirmed
            request.production_date = fields.Datetime.to_datetime(confirmed) if confirmed \
                else production.date_finished

    @api.depends('cancelled', 'production_id.state', 'picking_id.state',
                 'picking_id.move_ids.location_dest_id')
    def _compute_state(self):
        for request in self:
            production, picking = request.production_id, request.picking_id
            if request.cancelled or production.state == 'cancel':
                state = 'cancel'
            elif not production:
                state = 'draft'
            elif production.state == 'draft':
                state = 'requested'
            elif production.state != 'done':
                state = 'in_production'
            elif not picking or picking.state not in ('done', 'cancel'):
                state = 'produced'
            elif picking.state == 'done':
                state = 'done'
            else:
                state = 'produced'
            request.state = state

    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', self.env._('Nueva')) == self.env._('Nueva'):
                # La secuencia es configuración: la usa quien pide.
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code(
                    'construction.replacement.request') or self.env._('Nueva')
        return super().create(vals_list)

    def action_submit(self):
        """Crea la orden en borrador en el tipo de reposición de la planta y
        avisa al jefe de producción."""
        for request in self:
            if request.state != 'draft':
                raise UserError(self.env._('%s ya se pidió a la planta.', request.name))
            company = request.company_id
            picking_type = company.construction_replacement_type_id
            if not picking_type:
                raise UserError(self.env._(
                    'Elija el tipo de la reposición a planta en Ajustes › Fabricación.'))
            if request.product_uom_id.compare(request.product_qty, 0.0) <= 0:
                raise UserError(self.env._('Indique la cantidad de la pieza.'))
            # Quien pide no tiene permisos de Fabricación: la orden la crea el
            # sistema en la planta, en borrador, para que la planta la revise.
            production_sudo = self.env['mrp.production'].sudo().with_company(company)
            bom_sudo, picking_type = request._construction_replacement_bom(picking_type)
            vals = {
                'product_id': request.product_id.id,
                'product_qty': request.product_qty,
                'product_uom_id': request.product_uom_id.id,
                'bom_id': bom_sudo.id,
                'picking_type_id': picking_type.id,
                'company_id': company.id,
                'origin': ' · '.join(filter(None, [
                    request.name, request.project_id.display_name, request.task_id.name])),
                'construction_reason_id': request.reason_id.id,
                'construction_reason_note': request.reason_note,
                'project_id': request.project_id.id,
            }
            if request.date_required:
                vals['date_deadline'] = fields.Datetime.to_datetime(request.date_required)
            # Responsable: el jefe de producción, nunca quien pide (la orden la
            # crea el sistema con su usuario).
            heads = company._construction_production_heads() - self.env.user
            if heads:
                vals['user_id'] = heads[:1].id
            production_sudo = production_sudo.create(vals)
            for head in heads:
                production_sudo.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=head.id,
                    summary=self.env._('Reposición pedida por la obra'),
                    note=self.env._(
                        '%(request)s: %(qty)s %(product)s para %(project)s (%(reason)s).',
                        request=request.name, qty=request.product_qty,
                        product=request.product_id.display_name,
                        project=request.project_id.display_name, reason=request.reason_id.name),
                    date_deadline=request.date_required or fields.Date.context_today(request))
            request.write({'production_id': production_sudo.id,
                           'picking_type_id': picking_type.id})
            request.message_post(body=self.env._(
                'Pedida a la planta %(plant)s: orden %(order)s.',
                plant=picking_type.warehouse_id.name or picking_type.display_name,
                order=production_sudo.name))
        return True

    def _construction_replacement_bom(self, picking_type):
        """(lista, tipo de operación) de la orden de reposición (paquete 1.12,
        M112-03). La lista del tipo configurado o sin tipo; si no la hay, la
        del producto en otra planta (el plan deja la del módulo en la planta
        de la última etapa), con el tipo de ese almacén que pide motivo. Nunca
        una orden sin lista."""
        self.ensure_one()
        product, company = self.product_id, self.company_id
        # La lista y los tipos de la planta los lee el sistema por quien pide.
        Bom = self.env['mrp.bom'].sudo()
        bom_sudo = Bom._bom_find(
            product, picking_type=picking_type, company_id=company.id)[product]
        if bom_sudo:
            return bom_sudo, picking_type
        bom_sudo = Bom._bom_find(product, company_id=company.id, bom_type='normal')[product]
        if not bom_sudo:
            raise UserError(self.env._(
                '%s no tiene lista de materiales: la planta no puede fabricarla. Pida a '
                'Producción que cree su lista.', product.display_name))
        warehouse = bom_sudo.picking_type_id.warehouse_id
        other_type_sudo = warehouse and self.env['stock.picking.type'].sudo().search([
            ('warehouse_id', '=', warehouse.id), ('code', '=', 'mrp_operation'),
            ('construction_reason_required', '=', True), ('company_id', '=', company.id),
        ], order='sequence, id', limit=1)
        if not other_type_sudo:
            raise UserError(self.env._(
                'La lista de %(product)s es de %(warehouse)s y ese almacén no tiene una operación '
                'de fabricación que pida motivo (posventa o reposición): configúrela en '
                'Inventario › Configuración › Tipos de operación.',
                product=product.display_name,
                warehouse=warehouse.name or bom_sudo.picking_type_id.display_name))
        return bom_sudo, other_type_sudo

    def action_cancel(self):
        for request in self:
            if request.state not in ('draft', 'requested'):
                raise UserError(self.env._(
                    '%s ya está en fabricación: la cancela la planta.', request.name))
            # La orden en borrador la cancela el sistema por quien pide.
            request.production_id.sudo().action_cancel()
        self.write({'cancelled': True})
        return True

    def _construction_dispatch_to_site(self):
        """Despacho a obra de la pieza fabricada, desde lo terminado de la
        orden, con el tipo «Despacho a obra» del almacén de la planta."""
        for request in self.filtered(lambda r: not r.picking_id and r.location_dest_id):
            # Lo crea el sistema al terminar la orden en la planta.
            production_sudo = request.production_id.sudo()
            source = production_sudo.location_dest_id
            warehouse = source.warehouse_id or production_sudo.picking_type_id.warehouse_id
            picking_type = warehouse.construction_dispatch_type_id \
                or request.company_id.construction_dispatch_type_id
            if not picking_type:
                continue
            picking_sudo = self.env['stock.picking'].sudo().create({
                'picking_type_id': picking_type.id,
                'location_id': source.id,
                'location_dest_id': request.location_dest_id.id,
                'origin': '%s · %s' % (request.name, production_sudo.name),
                'project_id': request.project_id.id,
                'company_id': request.company_id.id,
                'move_ids': [Command.create({
                    'product_id': request.product_id.id,
                    'product_uom': request.product_uom_id.id,
                    'product_uom_qty': request.product_qty,
                    'location_id': source.id,
                    'location_dest_id': request.location_dest_id.id,
                    'company_id': request.company_id.id,
                })],
            })
            picking_sudo.action_confirm()
            picking_sudo.action_assign()
            request.picking_id = picking_sudo.id
            request.message_post(body=self.env._(
                'Fabricada: sale a la obra con %s.', picking_sudo.name))

    def action_view_picking(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.picking_id.id,
        }


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    construction_replacement_ids = fields.One2many(
        'construction.replacement.request', 'production_id', string='Reposición a planta')

    def button_mark_done(self):
        res = super().button_mark_done()
        done = self.filtered(lambda p: p.state == 'done')
        # La reposición es de la obra: su despacho lo crea el sistema.
        done.sudo().construction_replacement_ids._construction_dispatch_to_site()
        return res


class ConstructionMaterialRequest(models.Model):
    _inherit = 'construction.material.request'

    def action_construction_replacement(self):
        """«Pedir reposición a planta» desde el requerimiento."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Pedir reposición a planta'),
            'res_model': 'construction.replacement.request',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_project_id': self.project_id.id,
                'default_task_id': self.task_id.id,
                'default_request_id': self.id,
                'default_date_required': self.date_required,
            },
        }

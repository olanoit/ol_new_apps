# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_src_location_id = fields.Many2one(
        'stock.location', string='Origen de los despachos a obra',
        domain="[('usage', '=', 'internal'), ('company_id', 'in', [id, False])]",
        help='Existencias del almacén central. La disponibilidad incluye sus '
             'sububicaciones por familia (child_of).')
    construction_sites_location_id = fields.Many2one(
        'stock.location', string='Ubicación padre de las obras',
        domain="[('company_id', 'in', [id, False])]",
        help='Rama OBRAS: cada obra tiene una sububicación debajo.')
    # Material dañado en obra (CR-16, D5): no sale de la obra, va a esta
    # sububicación de la ubicación de cada obra.
    construction_damaged_location_name = fields.Char(
        string='Sububicación de lo dañado', default='Dañados',
        help='Nombre de la sububicación que se crea dentro de la ubicación de cada obra. '
             'Lo que la obra marca como dañado va ahí: sigue en la obra y en su costo hasta '
             'que Logística decida su destino.')
    construction_code_from_name = fields.Boolean(
        string='El nombre del proyecto empieza con el código de obra',
        help='La primera palabra del nombre del proyecto es el código de la obra '
             '(«ROOFG-04-25 ROOF GARDEN»): la ubicación de la obra se llama con el '
             'código y la cuenta analítica toma el código y el resto del nombre.')
    construction_dispatch_type_id = fields.Many2one(
        'stock.picking.type', string='Tipo de operación del despacho a obra',
        domain="[('code', '=', 'internal'), ('company_id', '=', id)]")
    construction_pr_picking_type_id = fields.Many2one(
        'stock.picking.type', string='Recepción de los requerimientos de compra',
        domain="[('code', '=', 'incoming'), ('company_id', '=', id)]")
    # CREVAL, CR-16: la compra para el almacén central puede llevar la
    # analítica de la obra (sin ella, la compra masiva va sin analítica,
    # v1.6, M16-02).
    construction_stock_purchase_analytic = fields.Boolean(
        string='Compra para el almacén con la analítica del requerimiento',
        help='La línea de compra de un requerimiento que se abastece desde el almacén central '
             'lleva la analítica de la obra (o la del área, si es interno). Úsela si el costo de '
             'la obra se toma de la compra: si el despacho a obra también valoriza el material, '
             'el costo se contaría dos veces.')
    construction_area_plan_id = fields.Many2one(
        'account.analytic.plan', string='Plan analítico de las áreas',
        help='Las cuentas de este plan son las áreas que piden material interno '
             '(Administración, Comercial…).')
    # Vale de despacho (paquete 1.11, M111-19 B).
    construction_slip_dispatch_label = fields.Char(
        string='Firma de quien despacha', translate=True,
        default=lambda self: _('Despachado por (almacén)'))
    construction_slip_receive_site_label = fields.Char(
        string='Firma de quien recibe (obra)', translate=True,
        default=lambda self: _('Recibido por (capataz)'))
    construction_slip_receive_internal_label = fields.Char(
        string='Firma de quien recibe (interno)', translate=True,
        default=lambda self: _('Recibido por (área)'))
    construction_slip_unvalidated_signer = fields.Selection(
        [('printer', 'Quien imprime'), ('blank', 'En blanco')],
        string='Si el despacho no está validado, «Despachado por»', default='printer')
    construction_slip_show_previous = fields.Boolean(
        string='Mostrar la columna «Despachado antes»', default=True)
    # Aprobador del requerimiento interno si quien pide no tiene jefe
    # (M111-19 C y M111-18): vacío, se aprueba al solicitarlo.
    construction_internal_fallback_group_id = fields.Many2one(
        'res.groups', string='Aprueba el requerimiento interno si quien pide no tiene jefe',
        default=lambda self: self.env.ref(
            'al_construction_material_request.group_construction_logistics',
            raise_if_not_found=False))

    # Requerimiento de obra al que no le aplica ninguna regla de aprobación
    # (CREVAL, 7.4): se aprueba al enviarlo o pasa al jefe de la obra.
    construction_site_request_without_rule = fields.Selection(
        [('manager', 'Pasar al jefe de la obra'), ('approve', 'Aprobar al enviar')],
        string='Requerimiento de obra sin regla de aprobación', default='manager',
        required=True)

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        companies._construction_sync_internal_fallback_rule()
        companies._construction_sync_site_fallback_rule()
        return companies

    def write(self, vals):
        res = super().write(vals)
        if 'construction_internal_fallback_group_id' in vals:
            self._construction_sync_internal_fallback_rule()
        if 'construction_site_request_without_rule' in vals:
            self._construction_sync_site_fallback_rule()
        return res

    def _construction_sync_site_fallback_rule(self):
        """Regla «requerimiento de obra sin otra regla → jefe de la obra» de
        cada compañía; archivada si la compañía aprueba al enviar."""
        # Configuración técnica, como la regla del interno sin jefe.
        Definition_sudo = self.env['tier.definition'].sudo().with_context(active_test=False)
        model = self.env['ir.model']._get('construction.material.request')
        field = self.env['ir.model.fields']._get('construction.material.request',
                                                 'project_manager_id')
        for company in self:
            rule = Definition_sudo.search([
                ('construction_site_fallback', '=', True),
                ('company_id', '=', company.id)], limit=1)
            if company.construction_site_request_without_rule != 'manager':
                rule.active = False
                continue
            vals = {
                'name': _('Requerimiento de obra sin otra regla: jefe de la obra'),
                'model_id': model.id,
                'review_type': 'field',
                'reviewer_field_id': field.id,
                'definition_domain': repr([
                    ('request_type', '=', 'site'),
                    ('construction_without_rule', '=', True),
                    ('project_manager_id', '!=', False),
                    ('company_id', '=', company.id)]),
                'company_id': company.id,
                'sequence': 90,
                'approve_sequence': True,
                'active': True,
            }
            if rule:
                rule.write(vals)
            else:
                Definition_sudo.create(dict(vals, construction_site_fallback=True))

    def _construction_sync_internal_fallback_rule(self):
        """Regla de aprobación «interno y sin jefe» de cada compañía, con el
        grupo de la opción; sin grupo, la regla queda archivada."""
        # La regla es configuración técnica: la mantiene la compañía aunque
        # quien guarda los Ajustes no administre las reglas de aprobación.
        Definition_sudo = self.env['tier.definition'].sudo().with_context(active_test=False)
        model = self.env['ir.model']._get('construction.material.request')
        for company in self:
            rule = Definition_sudo.search([
                ('construction_internal_fallback', '=', True),
                ('company_id', '=', company.id)], limit=1)
            group = company.construction_internal_fallback_group_id
            if not group:
                rule.active = False
                continue
            vals = {
                'name': _('Requerimiento interno sin jefe: %s', group.name),
                'model_id': model.id,
                'review_type': 'group',
                'reviewer_group_id': group.id,
                'definition_domain': repr([
                    ('request_type', '=', 'internal'),
                    ('construction_department_manager_id', '=', False),
                    ('company_id', '=', company.id)]),
                'company_id': company.id,
                'sequence': 31,
                'approve_sequence': True,
                'active': True,
            }
            if rule:
                rule.write(vals)
            else:
                Definition_sudo.create(dict(vals, construction_internal_fallback=True))

    def _al_construction_default_area_plan(self):
        """Plan «Área» como plan de las áreas, si existe y no hay otro elegido
        (paquete 1.11, M111-10). Lo llama «Completar configuración» de Ajustes;
        no se hace al procesar, que lo corre Logística sin acceso a los planes
        analíticos ni a la compañía."""
        Plan = self.env['account.analytic.plan']
        area_plan = Plan.search([('name', '=ilike', 'área')], limit=1) \
            or Plan.search([('name', '=ilike', 'area')], limit=1)
        if area_plan:
            self.filtered(lambda c: not c.construction_area_plan_id).write(
                {'construction_area_plan_id': area_plan.id})

    def _al_construction_ensure_setup(self):
        """Completa, sin pisar lo configurado, la ubicación ``OBRAS``, el tipo
        «Despacho a obra» y los valores por defecto a partir del primer
        almacén de la compañía."""
        Location = self.env['stock.location']
        PickingType = self.env['stock.picking.type']
        for company in self:
            warehouse = self.env['stock.warehouse'].search(
                [('company_id', '=', company.id)], limit=1)
            if not warehouse:
                continue
            vals = {}
            if not company.construction_src_location_id:
                vals['construction_src_location_id'] = warehouse.lot_stock_id.id
            sites = company.construction_sites_location_id
            if not sites:
                sites = Location.search([
                    ('location_id', '=', warehouse.view_location_id.id),
                    ('name', '=', 'OBRAS'),
                    ('company_id', '=', company.id),
                ], limit=1) or Location.create({
                    # Interna (no «vista») para que se lea ALM/OBRAS/<obra>.
                    'name': 'OBRAS',
                    'usage': 'internal',
                    'location_id': warehouse.view_location_id.id,
                    'company_id': company.id,
                })
                vals['construction_sites_location_id'] = sites.id
            if not company.construction_dispatch_type_id:
                vals['construction_dispatch_type_id'] = PickingType.create({
                    'name': _('Despacho a obra'),
                    'code': 'internal',
                    'sequence_code': 'OBRA',
                    'warehouse_id': warehouse.id,
                    'company_id': company.id,
                    'default_location_src_id': (
                        vals.get('construction_src_location_id')
                        or company.construction_src_location_id.id),
                    'default_location_dest_id': sites.id,
                }).id
            if not company.construction_pr_picking_type_id:
                vals['construction_pr_picking_type_id'] = warehouse.in_type_id.id
            if vals:
                company.write(vals)

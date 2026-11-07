# -*- coding: utf-8 -*-
"""Avisos al celular del portal de obra (paquete 6, CR-57). Datos
ficticios."""
from odoo.tests import tagged

from .test_resident import ResidentCommon


@tagged('post_install', '-at_install')
class TestPortalNotice(ResidentCommon):

    def _notified(self, record, user):
        return record.message_ids.filtered(lambda m: user.partner_id in m.partner_ids)

    def test_urgent_request_reaches_resident(self):
        """El pedido urgente del capataz llega como aviso al residente (P17)."""
        self.env['tier.definition'].search([
            ('model', '=', 'construction.material.request'),
            ('construction_site_fallback', '=', False)]).active = False
        self.company.construction_site_request_without_rule = 'resident'
        cement = self.env['product.product'].create({'name': 'Cemento aviso (p6)',
                                                     'is_storable': True})
        self.env['construction.resource.plan.line'].with_context(
            construction_plan_force=True).create({
                'plan_id': self.plan.id, 'task_id': self.partida.id, 'resource_type': 'material',
                'product_id': cement.id, 'stage': 'creval_tab', 'qty_planned': 20,
                'price_unit_planned': 30.0, 'product_uom_id': cement.uom_id.id})
        result = self._service(self.foreman_user).material_request({
            'uuid': 'p6-nt-1', 'project_id': self.project.id, 'priority': 'urgent',
            'lines': [{'catalog': 'partida', 'product_id': cement.id,
                       'task_id': self.partida.id, 'qty': 2}]})
        request = self.env['construction.material.request'].browse(int(result['ids']))
        self.assertEqual(request.state, 'to_approve')
        self.assertTrue(self._notified(request, self.resident_user))
        # Sin la regla del residente, no se avisa.
        self.env['construction.portal.notice.rule'].search([
            ('event', '=', 'urgent_request')]).active = False
        result = self._service(self.foreman_user).material_request({
            'uuid': 'p6-nt-2', 'project_id': self.project.id, 'priority': 'urgent',
            'lines': [{'catalog': 'partida', 'product_id': cement.id,
                       'task_id': self.partida.id, 'qty': 1}]})
        other = self.env['construction.material.request'].browse(int(result['ids']))
        self.assertFalse(self._notified(other, self.resident_user))

    def test_push_subscription(self):
        service = self._service(self.resident_user)
        key = service.push_key()['public_key']
        self.assertTrue(key)
        service.push_subscribe({'endpoint': 'https://push.example.com/p6-1',
                                'keys': {'p256dh': 'x', 'auth': 'y'}, 'vapid_public_key': key})
        device = self.env['mail.push.device'].sudo().search([
            ('endpoint', '=', 'https://push.example.com/p6-1')])
        self.assertEqual(device.partner_id, self.resident_user.partner_id)
        service.push_subscribe({'endpoint': 'https://push.example.com/p6-1',
                                'unsubscribe': True})
        self.assertFalse(device.exists())

    def test_decision_follows_rules(self):
        """Validado o rechazado: quien reportó recibe el aviso si su papel lo
        recibe."""
        progress = self._report(3.0, 'p6-nt-3')
        self._service(self.resident_user).resident_progress({
            'uuid': 'p6-nt-4', 'project_id': self.project.id, 'action': 'validate',
            'items': [{'id': progress.id, 'seen_qty': 3.0}]})
        self.assertTrue(self._notified(progress, self.contractor_user))
        self.env['construction.portal.notice.rule'].search([
            ('event', '=', 'progress_decision'), ('role', '=', 'contractor')]).active = False
        other = self._report(2.0, 'p6-nt-5')
        self._service(self.resident_user).resident_progress({
            'uuid': 'p6-nt-6', 'project_id': self.project.id, 'action': 'validate',
            'items': [{'id': other.id, 'seen_qty': 2.0}]})
        self.assertFalse(self._notified(other, self.contractor_user))

    def test_delivery_on_the_way(self):
        """La entrega lista para recibir en la obra avisa una sola vez."""
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.company.id)],
                                                       limit=1)
        site = self.env['stock.location'].create({
            'name': 'Obra aviso (p6)', 'usage': 'internal',
            'location_id': warehouse.view_location_id.id})
        self.project.construction_location_id = site
        product = self.env['product.product'].create({'name': 'Arena aviso (p6)',
                                                      'type': 'consu'})
        picking = self.env['stock.picking'].create({
            'picking_type_id': warehouse.int_type_id.id, 'location_id': warehouse.lot_stock_id.id,
            'location_dest_id': site.id, 'move_ids': [(0, 0, {
                'product_id': product.id, 'product_uom_qty': 3, 'product_uom': product.uom_id.id,
                'location_id': warehouse.lot_stock_id.id, 'location_dest_id': site.id})]})
        picking.action_confirm()
        picking.action_assign()
        self.assertEqual(picking.state, 'assigned')
        Picking = self.env['stock.picking']
        Picking._cron_construction_portal_delivery_notice()
        self.assertTrue(picking.construction_portal_notified)
        self.assertTrue(self._notified(picking, self.resident_user))
        self.assertTrue(self._notified(picking, self.foreman_user))
        count = len(picking.message_ids)
        Picking._cron_construction_portal_delivery_notice()
        self.assertEqual(len(picking.message_ids), count)

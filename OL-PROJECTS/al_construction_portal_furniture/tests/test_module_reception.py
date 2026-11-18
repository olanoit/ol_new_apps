# -*- coding: utf-8 -*-
"""M122-05: recepción de un despacho de módulos por departamento, parcial y
con un módulo dañado, con un usuario de portal. Datos ficticios."""
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import PHOTOS, FurniturePortalCommon


@tagged('post_install', '-at_install')
class TestModuleReception(FurniturePortalCommon):

    def _delivery(self, service, picking):
        deliveries = service.sync(self.project.id)['deliveries']
        return next(row for row in deliveries if row['id'] == picking.id)

    def _values(self, delivery, uuid, statuses=None, **extra):
        statuses = statuses or {}
        modules = [dict({'move_id': module['move_id'], 'task_id': module['id'], 'status': 'ok'},
                        **statuses.get(module['id'], {}))
                   for department in delivery['departments'] for module in department['modules']]
        return dict({'uuid': uuid, 'project_id': self.project.id, 'picking_id': delivery['id'],
                     'photos': PHOTOS, 'modules': modules, 'lines': []}, **extra)

    def test_two_departments_partial_and_damaged(self):
        picking = self._ship(self.apt_501 | self.apt_502)
        service = self._service(self.office_user)
        delivery = self._delivery(service, picking)
        self.assertEqual([d['name'] for d in delivery['departments']], ['Dpto 501', 'Dpto 502'])
        self.assertFalse(delivery['lines'], 'los módulos no van por producto')
        by_department = {d['id']: d['modules'] for d in delivery['departments']}
        self.assertEqual(len(by_department[self.apt_501.id]), 2)
        self.assertEqual(len(by_department[self.apt_502.id]), 4)
        self.assertEqual(sorted(m['label'] for m in by_department[self.apt_501.id]),
                         ['MA-1', 'MB-1'])
        self.assertTrue(all(m['lot'] and m['typology'] == 'C22'
                            for modules in by_department.values() for m in modules))

        missing = self._module(self.closet_502, 'MB1')
        damaged = self._module(self.kitchen_501, 'MA1')
        statuses = {missing.id: {'status': 'missing'},
                    damaged.id: {'status': 'damaged', 'note': 'Costado rayado',
                                 'reason_id': self.reason.id}}
        # «Llegó dañado» pide su foto, y la guía firmada sigue siendo obligatoria.
        with self.assertRaisesRegex(UserError, 'foto del daño'):
            service.module_reception(self._values(delivery, 'p122f-rec-0', statuses))
        statuses[damaged.id]['photos'] = PHOTOS
        with self.assertRaises(UserError):
            service.module_reception(self._values(delivery, 'p122f-rec-0', statuses, photos=[]))
        self.assertEqual(picking.state, 'assigned')

        values = self._values(delivery, 'p122f-rec-1', statuses)
        result = service.module_reception(values)
        self.assertEqual(picking.state, 'done')
        self.assertTrue(result['backorder'])
        self.assertEqual((result['received'], result['missing']), (5, 1))
        backorder = self.env['stock.picking'].search([('backorder_id', '=', picking.id)])
        self.assertEqual(len(backorder), 1)
        # El que no llegó sigue en tránsito en la entrega parcial; los demás, en obra.
        self.assertEqual(missing.construction_shipment_picking_id, backorder)
        self.assertEqual(missing.construction_shipment_state, 'in_transit')
        self.assertNotEqual(missing.construction_unit_state, 'on_site')
        arrived = self.modules - missing
        self.assertEqual(set(arrived.mapped('construction_unit_state')), {'on_site'})
        self.assertEqual(arrived.construction_shipment_picking_id, picking)
        self.assertEqual(backorder.move_ids.construction_module_task_ids, missing)
        self.assertNotIn(missing, picking.move_ids.construction_module_task_ids)
        # No hay movimientos nuevos: lo recibido es lo enviado menos el que falta.
        self.assertEqual(sum(picking.move_ids.mapped('quantity')), 5)
        self.assertEqual(sum(backorder.move_ids.mapped('product_uom_qty')), 1)

        # El dañado entra a la obra y abre su reposición en borrador con la foto.
        replacement = self.env['construction.replacement.request'].search(
            [('task_id', '=', damaged.id)])
        self.assertEqual(len(replacement), 1)
        self.assertEqual(result['replacements'], [replacement.name])
        self.assertEqual(replacement.state, 'draft')
        self.assertEqual(replacement.requested_by, self.office_user)
        self.assertEqual(replacement.project_id, self.project)
        self.assertEqual(replacement.product_id,
                         self.typology_p.module_line_ids.filtered(
                             lambda m: m.code == 'MA1').product_id)
        self.assertEqual(replacement.reason_id, self.reason)
        self.assertEqual(replacement.reason_note, 'Costado rayado')
        self.assertEqual(self.env['ir.attachment'].search_count([
            ('res_model', '=', 'construction.replacement.request'),
            ('res_id', '=', replacement.id)]), 1)

        # Envío repetido sin señal: ni otra validación ni otra reposición.
        again = service.module_reception(values)
        self.assertTrue(again.get('duplicate'))
        self.assertEqual(self.env['construction.replacement.request'].search_count(
            [('task_id', '=', damaged.id)]), 1)

        # La entrega parcial se recibe igual, con su único módulo.
        if backorder.state == 'assigned':
            rest = self._delivery(service, backorder)
            self.assertEqual([m['id'] for d in rest['departments'] for m in d['modules']],
                             missing.ids)
            service.module_reception(self._values(rest, 'p122f-rec-2'))
            self.assertEqual(backorder.state, 'done')
            self.assertEqual(missing.construction_unit_state, 'on_site')

    def test_everything_arrived(self):
        picking = self._ship(self.apt_501)
        service = self._service(self.foreman_user)
        delivery = self._delivery(service, picking)
        result = service.module_reception(self._values(delivery, 'p122f-rec-all'))
        self.assertEqual(picking.state, 'done')
        self.assertFalse(result['backorder'])
        self.assertEqual(result['replacements'], [])
        modules = self.modules.filtered(
            lambda m: m.construction_apartment_task_id == self.apt_501)
        self.assertEqual(set(modules.mapped('construction_unit_state')), {'on_site'})

    def test_never_more_than_sent_and_only_its_modules(self):
        picking = self._ship(self.apt_501)
        service = self._service(self.office_user)
        delivery = self._delivery(service, picking)
        values = self._values(delivery, 'p122f-rec-x')
        # Un módulo que no viene en la entrega (o repetido) se rechaza.
        other = self._module(self.kitchen_502, 'MB1')
        bad = dict(values, modules=values['modules'] + [
            {'move_id': values['modules'][0]['move_id'], 'task_id': other.id, 'status': 'ok'}])
        with self.assertRaises(UserError):
            service.module_reception(bad)
        with self.assertRaises(UserError):
            service.module_reception(dict(values, modules=values['modules'] * 2))
        self.assertEqual(picking.state, 'assigned')

    def test_roles_and_scope(self):
        picking = self._ship(self.apt_501)
        delivery = self._delivery(self._service(self.office_user), picking)
        values = self._values(delivery, 'p122f-rec-r')
        with self.assertRaises(AccessError):
            self._service(self.contractor_user).module_reception(values)
        with self.assertRaises(AccessError):
            self._service(self.outsider_user).module_reception(values)
        # En su propia obra tampoco: la entrega no es de ella.
        with self.assertRaises(UserError):
            self._service(self.outsider_user).module_reception(
                dict(values, project_id=self.other_project.id))
        self.assertEqual(picking.state, 'assigned')

    def test_feature_off_keeps_the_reception_by_product(self):
        picking = self._ship(self.apt_501)
        self.project.construction_profile_id = self.profile_off
        delivery = self._delivery(self._service(self.office_user), picking)
        self.assertNotIn('departments', delivery)
        self.assertEqual(len(delivery['lines']), 2)

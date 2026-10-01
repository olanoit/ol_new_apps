# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, new_test_user


class ConstructionRequestCommon(TransactionCase):
    """Datos ficticios: dos obras, un almacén con sububicaciones por familia."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.company.id)], limit=1)
        cls.company._al_construction_ensure_setup()
        cls.stock = cls.company.construction_src_location_id
        cls.loc_cement = cls.env['stock.location'].create({
            'name': 'Cemento (test)', 'usage': 'internal', 'location_id': cls.stock.id})
        cls.loc_steel = cls.env['stock.location'].create({
            'name': 'Fierro (test)', 'usage': 'internal', 'location_id': cls.stock.id})

        grp = 'al_construction_material_request.group_construction_'
        cls.requester = new_test_user(
            cls.env, 'rqo_residente', groups=f'{grp}requester', name='Residente (test)')
        cls.other_requester = new_test_user(
            cls.env, 'rqo_otro', groups=f'{grp}requester', name='Otro residente (test)')
        cls.approver = new_test_user(
            cls.env, 'rqo_jefe', groups=f'{grp}approver,project.group_project_user',
            name='Jefe de proyecto (test)')
        cls.logistics = new_test_user(
            cls.env, 'rqo_logistica', groups=f'{grp}logistics', name='Logística (test)')
        cls.operations = new_test_user(
            cls.env, 'rqo_gerencia',
            groups='al_construction_material_request.group_construction_operations_manager',
            name='Gerencia de operaciones (test)')

        # Reglas de aprobación propias del test (se apagan las existentes,
        # p. ej. las demo).
        TierDefinition = cls.env['tier.definition']
        TierDefinition.search([('model', '=', 'construction.material.request')]).active = False
        model = cls.env['ir.model']._get('construction.material.request')
        cls.tier_manager = TierDefinition.create({
            'name': 'Nivel 1: jefe de proyecto (test)',
            'model_id': model.id,
            'review_type': 'field',
            'reviewer_field_id': cls.env['ir.model.fields']._get(
                'construction.material.request', 'project_manager_id').id,
            'definition_domain': "[('project_manager_id', '!=', False)]",
            'sequence': 20,
            'approve_sequence': True,
        })
        cls.tier_operations = TierDefinition.create({
            'name': 'Nivel 2: gerencia > 10 000 (test)',
            'model_id': model.id,
            'review_type': 'group',
            'reviewer_group_id': cls.env.ref(
                'al_construction_material_request.group_construction_operations_manager').id,
            'definition_domain': "[('amount_estimated', '>', 10000)]",
            'sequence': 10,
            'approve_sequence': True,
        })

        Project = cls.env['project.project']
        cls.site_a = Project.create({
            'name': 'Colegio A (test)', 'is_construction_site': True,
            'user_id': cls.approver.id})
        cls.site_a.message_subscribe(partner_ids=cls.requester.partner_id.ids)
        cls.site_b = Project.create({
            'name': 'Posta B (test)', 'is_construction_site': True})
        cls.site_b.message_subscribe(partner_ids=cls.other_requester.partner_id.ids)

        cls.uom_unit = cls.env.ref('uom.product_uom_unit')
        Product = cls.env['product.product']
        cls.cement = Product.create({
            'name': 'Cemento bolsa 42.5 kg (test)', 'type': 'consu', 'is_storable': True,
            'standard_price': 30.0})
        cls.steel = Product.create({
            'name': 'Fierro 1/2" (test)', 'type': 'consu', 'is_storable': True,
            'standard_price': 45.0})

    @classmethod
    def _set_stock(cls, product, location, qty):
        cls.env['stock.quant']._update_available_quantity(product, location, qty)

    def _new_request(self, project=None, lines=None, user=None):
        Request = self.env['construction.material.request']
        if user:
            Request = Request.with_user(user)
        return Request.create({
            'project_id': (project or self.site_a).id,
            'line_ids': [
                (0, 0, {'product_id': product.id, 'product_qty': qty})
                for product, qty in ([(self.cement, 100)] if lines is None else lines)
            ],
        })

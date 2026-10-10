# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, new_test_user


class PlannerCommon(TransactionCase):
    """Obra ficticia con la tipología 01 de la especificación (P-12): siete
    módulos sin ancho, armado S/ 54.00 por ambiente más S/ 31.29 de
    actividades por ambiente, y su lista de materiales con una línea sin
    etapa."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.unit = cls.env.ref('uom.product_uom_unit')
        cls.meter = cls.env.ref('uom.product_uom_meter')
        grp = 'al_construction_planner.group_planner_'
        cls.planner = new_test_user(
            cls.env, 'plan_planificador', groups=f'{grp}planner', name='Planificador (test)')
        cls.reporter = new_test_user(
            cls.env, 'plan_capataz', groups=f'{grp}progress', name='Capataz (test)')

        # Sin reglas de aprobación del plan (p. ej. las demo): cada test que
        # las necesita crea las suyas.
        cls.env['tier.definition'].search(
            [('model', '=', 'construction.resource.plan')]).active = False

        cls.project = cls.env['project.project'].create({
            'name': 'Obra MOMEN (test)', 'is_construction_site': True})
        cls.contractor = cls.env['res.partner'].create({'name': 'Armado Gonza (test)'})

        Activity = cls.env['construction.labor.activity']

        def activity(code, name, stage, price, uom=None, **vals):
            return Activity.create(dict({
                'code': code, 'name': name, 'stage': stage, 'default_price': price,
                'uom_id': (uom or cls.unit).id}, **vals))

        cls.act_screw = activity('ARM-TOR', 'Armado módulo tornillo', 'assembly', 6.0,
                                 module_level=True)
        cls.act_dowel = activity('ARM-TAR', 'Armado módulo tarugo', 'assembly', 8.0,
                                 module_level=True)
        cls.act_micro = activity('ARM-MIC', 'Armado microondas', 'assembly', 10.0,
                                 module_level=True)
        cls.act_hood = activity('ARM-CAM', 'Armado módulo de campana', 'assembly', 7.0,
                                module_level=True)
        cls.act_drawer = activity('ARM-CAJ', 'Armado cajonera', 'assembly', 7.0,
                                  module_level=True)
        cls.act_doors = activity('COL-PUE', 'Colocación de puertas', 'assembly', 3.0)
        cls.act_dowelling = activity('ENT', 'Entarugado de muebles', 'assembly', 3.0)
        cls.act_inst_low = activity('INS-BAJ', 'Instalación mueble bajo', 'installation', 16.0,
                                    uom=cls.meter, ml_based=True, ml_group='low')
        cls.act_inst_high = activity('INS-ALT', 'Instalación mueble alto', 'installation', 16.0,
                                     uom=cls.meter, ml_based=True, ml_group='high')
        # Tarifa de la obra (P-14): 18.00 por ML en MOMEN.
        cls.env['construction.labor.rate'].create([
            {'activity_id': cls.act_inst_low.id, 'project_id': cls.project.id,
             'price': 18.0, 'retention_pct': 10.0},
            {'activity_id': cls.act_inst_high.id, 'project_id': cls.project.id,
             'price': 18.0, 'retention_pct': 10.0},
        ])

        Product = cls.env['product.product']

        def product(name, cost=0.0):
            return Product.create({'name': name, 'type': 'consu', 'standard_price': cost})

        cls.p_white = product('Melamina MDP blanco fantasía (test)')
        cls.p_cognac = product('Melamina coñac (test)')
        cls.p_rh = product('Melamina blanco RH fantasía (test)')
        cls.p_hinge = product('Bisagra lateral Danco (test)')
        cls.p_screw = product('Tornillos 4×50 (test)')
        cls.p_cap = product('Tapatornillo blanco (test)')
        cls.kitchen = cls.env['product.template'].create({
            'name': 'Cocina tipo 01 (test)', 'type': 'consu'})
        cls.bom = cls.env['mrp.bom'].create({
            'product_tmpl_id': cls.kitchen.id, 'product_qty': 1.0,
            'bom_line_ids': [
                (0, 0, {'product_id': p.id, 'product_qty': qty,
                        'construction_consumption_stage': stage})
                for p, qty, stage in (
                    (cls.p_white, 1.9591, 'production'),
                    (cls.p_cognac, 0.9360, 'production'),
                    (cls.p_rh, 0.2544, False),
                    (cls.p_hinge, 10, 'assembly'),
                    (cls.p_screw, 121, 'installation'),
                    (cls.p_cap, 78, 'finishing'))]})

        cls.typology = cls.env['construction.typology'].create({
            'project_id': cls.project.id, 'code': '01', 'name': 'Cocina 01',
            'family': 'kitchen', 'product_tmpl_id': cls.kitchen.id, 'bom_id': cls.bom.id,
            'ml_low': 2.12, 'ml_high': 2.10,
            'module_line_ids': [
                (0, 0, {'sequence': seq, 'code': code, 'module_type': mtype,
                        'assembly_activity_id': act.id})
                for seq, code, mtype, act in (
                    (1, 'Tornillo 1', 'low', cls.act_screw),
                    (2, 'Tarugo 1', 'low', cls.act_dowel),
                    (3, 'Tarugo 2', 'high', cls.act_dowel),
                    (4, 'Tarugo 3', 'high', cls.act_dowel),
                    (5, 'Microondas', 'high', cls.act_micro),
                    (6, 'Campana', 'hood', cls.act_hood),
                    (7, 'Cajonera', 'drawer', cls.act_drawer))],
            'activity_line_ids': [
                # 1.93 × 3.00 + 8.5 × 3.00 = 31.29 por ambiente (armado).
                (0, 0, {'activity_id': cls.act_doors.id, 'qty': 1.93}),
                (0, 0, {'activity_id': cls.act_dowelling.id, 'qty': 8.5}),
                (0, 0, {'activity_id': cls.act_inst_low.id, 'qty': 2.12}),
                (0, 0, {'activity_id': cls.act_inst_high.id, 'qty': 2.10})],
        })

        Task = cls.env['project.task']

        def task(name, level, parent=None, **vals):
            return Task.create(dict({
                'name': name, 'project_id': cls.project.id, 'construction_level': level,
                'parent_id': parent.id if parent else False}, **vals))

        cls.task = staticmethod(task)
        cls.floor = task('Piso 05', 'floor')
        cls.apt_501 = task('Dpto 501', 'apartment', cls.floor)
        cls.apt_502 = task('Dpto 502', 'apartment', cls.floor)
        cls.space_501 = task('Cocina', 'space', cls.apt_501,
                             construction_typology_id=cls.typology.id)
        cls.space_502 = task('Cocina', 'space', cls.apt_502,
                             construction_typology_id=cls.typology.id)
        cls.plan = cls.env['construction.resource.plan'].create({'project_id': cls.project.id})

    def _wizard(self, **vals):
        return self.env['construction.plan.generate.wizard'].create(
            dict({'plan_id': self.plan.id}, **vals))

    def _generate(self, **vals):
        wizard = self._wizard(**vals)
        wizard.action_generate()
        return wizard

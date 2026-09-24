# -*- coding: utf-8 -*-
"""Los datos del T-Registro no salen en el perfil público del empleado.

El domicilio, el documento de identidad y los demás campos que añade el
módulo viven en ``hr.employee`` y no existen en ``hr.employee.public``. Si
la ficha los muestra a un usuario interno sin permiso de Recursos Humanos,
Odoo corta la lectura con «los campos … no están disponibles para los
perfiles públicos de los empleados», y la app móvil lo dispara sola al
abrir un empleado.

Por eso los bloques que el módulo inyecta en la pestaña personal llevan
``groups="hr.group_hr_user"`` dentro del arch: en Odoo 19 una vista
heredada no admite ``groups`` en el registro.
"""
from lxml import etree

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

# Bloques que el módulo añade a la pestaña «Personal» de la ficha.
PRIVATE_BLOCKS = (
    ('al_hr_pe.view_employee_form_tregistro_address', 'Domicilio (T-Registro)'),
    ('al_hr_pe.hr_employee_view_form_inherit_pe', 'Perú — Identificación (PLAME)'),
)
ADDRESS_FIELDS = (
    'l10n_pe_road_type_id', 'l10n_pe_road_name', 'l10n_pe_road_number',
    'l10n_pe_district_id', 'l10n_pe_road_type2_id', 'l10n_pe_district2_id',
    'l10n_pe_country_emitter', 'l10n_pe_nationality_code',
)


@tagged('post_install', '-at_install')
class TestEmployeePrivacy(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].create({
            'name': 'Interno sin RR. HH.',
            'login': 'al_hr_pe_interno_sin_rrhh',
            'group_ids': [Command.set([cls.env.ref('base.group_user').id])],
        })
        cls.employee = cls.env['hr.employee'].create({'name': 'Trabajador privado'})

    def test_user_without_hr_access(self):
        hr_user = self.env.ref('hr.group_hr_user')
        self.assertNotIn(hr_user, self.user.all_group_ids,
                         'el usuario de la prueba no debe ser de Recursos Humanos')

    def test_injected_blocks_declare_the_group(self):
        """Cada bloque inyectado en la pestaña personal lleva su grupo."""
        for xmlid, label in PRIVATE_BLOCKS:
            with self.subTest(vista=xmlid):
                arch = etree.fromstring(self.env.ref(xmlid).arch_db)
                nodes = arch.xpath(
                    "//*[self::separator or self::group or self::field]"
                    "[not(ancestor::group) and not(ancestor::separator)]")
                self.assertTrue(nodes, 'la vista %s ya no inyecta nada' % xmlid)
                for node in nodes:
                    self.assertEqual(
                        node.get('groups'), 'hr.group_hr_user',
                        '%s: falta groups en <%s> de «%s»' % (xmlid, node.tag, label))

    def test_form_hides_the_private_fields(self):
        """La ficha que recibe un usuario sin Recursos Humanos no los pide."""
        view = self.env['hr.employee'].with_user(self.user).get_view(
            self.env.ref('hr.view_employee_form').id, 'form')
        names = etree.fromstring(view['arch']).xpath('//field/@name')
        for field in ADDRESS_FIELDS:
            self.assertNotIn(field, names)

    def test_hr_user_still_sees_the_blocks(self):
        """Con permiso de Recursos Humanos, la ficha mantiene los campos."""
        hr_user = self.env['res.users'].create({
            'name': 'Responsable RR. HH.', 'login': 'al_hr_pe_rrhh',
            'group_ids': [Command.set([self.env.ref('base.group_user').id,
                                       self.env.ref('hr.group_hr_user').id])],
        })
        view = self.env['hr.employee'].with_user(hr_user).get_view(
            self.env.ref('hr.view_employee_form').id, 'form')
        names = etree.fromstring(view['arch']).xpath('//field/@name')
        for field in ADDRESS_FIELDS + ('identification_id', 'last_name'):
            self.assertIn(field, names)

    def test_public_profile_is_readable(self):
        """Leer el empleado como perfil público no da error de acceso."""
        public = self.env['hr.employee.public'].with_user(self.user).browse(
            self.employee.id)
        self.assertEqual(public.name, 'Trabajador privado')
        for field in ADDRESS_FIELDS:
            self.assertNotIn(field, self.env['hr.employee.public']._fields,
                             'si se publica, hay que revisar la privacidad')

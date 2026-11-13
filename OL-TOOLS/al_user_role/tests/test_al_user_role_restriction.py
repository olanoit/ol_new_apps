# -*- coding: utf-8 -*-
from lxml import etree

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, JsonRpcException, tagged

from .common import AlUserRoleCommon


@tagged('post_install', '-at_install')
class TestAlUserRoleRestriction(AlUserRoleCommon):
    """Restricciones por rol: vistas, Imprimir / Acciones, dominio de registros
    y opciones generales. Aplican solo si todos los roles del usuario las
    tienen; el Administrador del sistema no tiene restricciones."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Restriction = cls.env['al.user.role.restriction']
        cls.Element = cls.env['al.user.role.view.element']
        cls.ir_partner = cls.env['ir.model']._get('res.partner')
        cls.Element._al_sync(cls.ir_partner)

    # ------------------------------------------------------------------ helpers
    def _field(self, name, model='res.partner'):
        return self.env['ir.model.fields']._get(model, name)

    def _element(self, kind, name):
        element = self.Element.search([
            ('model_id', '=', self.ir_partner.id), ('kind', '=', kind), ('name', '=', name),
        ])
        self.assertTrue(element, f'{kind} {name} no se registró desde las vistas de contacto')
        return element

    def _restrict(self, role, **vals):
        return self.Restriction.create({'role_id': role.id, 'model_id': self.ir_partner.id, **vals})

    def _assign(self, *roles):
        for role in roles:
            self.Line.create({'role_id': role.id, 'user_id': self.user.id})

    def _arch(self, view_type='form', user=None):
        view = self.env['res.partner'].with_user(user or self.user).get_view(view_type=view_type)
        return etree.fromstring(view['arch'])

    def _first(self, arch, xpath):
        nodes = arch.xpath(xpath)
        self.assertTrue(nodes, f'{xpath} no está en la vista')
        return nodes[0]

    # -------------------------------------------------------------------- tests
    def test_view_elements_registered(self):
        page = self._element('page', 'contact_addresses')
        self.assertEqual(page.display_name, f'{page.label} (contact_addresses)')
        self._element('filter', 'type_company')
        self._element('button', 'create_company')
        count = self.Element.search_count([('model_id', '=', self.ir_partner.id)])
        self.Element._al_sync(self.ir_partner)
        self.assertEqual(self.Element.search_count([('model_id', '=', self.ir_partner.id)]), count)

    def test_element_technical_name(self):
        """Nombre técnico de botones, pestañas y filtros (XML ID si abren una acción)."""
        action = self.env.ref('base.action_partner_form')
        self.env['ir.ui.view'].create({
            'name': 'botón de acción', 'model': 'res.partner',
            'inherit_id': self.env.ref('base.view_partner_form').id,
            'arch': f'''<xpath expr="//sheet" position="inside">
                <button name="{action.id}" type="action" string="Abrir contactos"/>
            </xpath>''',
        })
        self.Element._al_sync(self.ir_partner)
        button = self._element('button', str(action.id))
        self.assertEqual(button.technical_name, 'base.action_partner_form')
        self.assertEqual(button.display_name, 'Abrir contactos (base.action_partner_form)')
        self.assertEqual(self.Element.name_search('base.action_partner_form')[0][0], button.id)
        self.assertEqual(self._element('button', 'create_company').technical_name, 'create_company')
        # Botón de acción sin texto: solo el nombre técnico, no el id.
        button.label = button.name
        self.assertEqual(button.display_name, 'base.action_partner_form')


    def test_selectors_show_only_name(self):
        """Selectores de una restricción: desplegable y etiqueta elegida
        muestran solo el nombre; se puede buscar por el nombre técnico."""
        spec = {'display_name': {}}
        email = self._field('email')
        fields_ = self.env['ir.model.fields'].with_context(hide_model=True)
        found = fields_.web_name_search('email', spec, [('model', '=', 'res.partner')])
        self.assertIn(email.id, [r['id'] for r in found], 'Se busca por el nombre técnico.')
        self.assertEqual(next(r for r in found if r['id'] == email.id)['display_name'],
                         email.field_description)

        server = self.env['ir.actions.server'].create({
            'name': 'acción', 'model_id': self.ir_partner.id, 'state': 'code', 'code': 'pass',
        })
        found = self.env['ir.actions.server'].web_name_search('acción', spec, [('id', '=', server.id)])
        self.assertEqual(found[0]['display_name'], 'acción')

        button = self._element('button', 'create_company')
        elements = self.Element.with_context(al_element_label_only=True)
        found = elements.web_name_search('create_company', spec, [('id', '=', button.id)])
        self.assertEqual(found[0]['display_name'], button.label)

    def test_view_element_screens(self):
        """En sus propias pantallas el elemento se ve solo con la etiqueta."""
        page = self._element('page', 'contact_addresses')
        self.assertEqual(page.with_context(al_element_label_only=True).display_name, page.label)
        page.unlink()
        self.Element.browse(self._element('button', 'create_company').ids).action_al_resync()
        self._element('page', 'contact_addresses')
        action = self.env.ref('al_user_role.action_al_user_role_view_element')
        self.assertTrue(action.context and 'al_element_label_only' in action.context)

    def test_without_role_no_restrictions(self):
        self._restrict(self.role_internal, hidden_field_ids=[Command.set(self._field('email').ids)])
        email = self._first(self._arch(), "//field[@name='email']")
        self.assertNotEqual(email.get('invisible'), 'True')

    def test_form_restrictions(self):
        self._assign(self.role_internal)
        # Creada después de asignar el rol: guardar una restricción limpia la caché.
        self._restrict(
            self.role_internal,
            hide_create=True, hide_delete=True, hide_duplicate=True,
            hidden_field_ids=[Command.set(self._field('email').ids)],
            readonly_field_ids=[Command.set(self._field('phone').ids)],
            required_field_ids=[Command.set(self._field('ref').ids)],
            no_open_field_ids=[Command.set(self._field('parent_id').ids)],
            hidden_page_ids=[Command.set(self._element('page', 'contact_addresses').ids)],
            hidden_button_ids=[Command.set(self._element('button', 'create_company').ids)],
        )
        arch = self._arch()
        self.assertEqual(arch.get('create'), 'False')
        self.assertEqual(arch.get('delete'), 'False')
        self.assertEqual(arch.get('duplicate'), 'False')
        self.assertEqual(self._first(arch, "//field[@name='email']").get('invisible'), 'True')
        self.assertEqual(self._first(arch, "//field[@name='phone']").get('readonly'), 'True')
        self.assertEqual(self._first(arch, "//field[@name='ref']").get('required'), 'True')
        self.assertIn("'no_open': True", self._first(arch, "//field[@name='parent_id']").get('options'))
        self.assertEqual(self._first(arch, "//page[@name='contact_addresses']").get('invisible'), 'True')
        self.assertEqual(self._first(arch, "//button[@name='create_company']").get('invisible'), 'True')
        # Lista: se oculta la columna completa.
        self.assertEqual(self._arch('list').get('create'), 'False')

    def test_search_filter_hidden(self):
        self._assign(self.role_internal)
        self._restrict(self.role_internal, hidden_filter_ids=[
            Command.set(self._element('filter', 'type_company').ids)])
        arch = self._arch('search')
        self.assertEqual(self._first(arch, "//filter[@name='type_company']").get('invisible'), 'True')
        self.assertNotEqual(self._first(arch, "//filter[@name='type_person']").get('invisible'), 'True')

    def test_relational_field_without_create(self):
        """Ocultar crear en Etiquetas quita Crear del campo Etiquetas del contacto."""
        self._assign(self.role_internal)
        self.Restriction.create({
            'role_id': self.role_internal.id,
            'model_id': self.env['ir.model']._get('res.partner.category').id,
            'hide_create': True,
        })
        category = self._first(self._arch(), "//field[@name='category_id']")
        self.assertEqual(category.get('can_create'), 'False')

    def test_only_restrictions_shared_by_all_roles(self):
        self._assign(self.role_internal, self.role_contacts)
        self._restrict(self.role_internal, hidden_field_ids=[
            Command.set((self._field('email') | self._field('phone')).ids)])
        arch = self._arch()
        self.assertNotEqual(self._first(arch, "//field[@name='email']").get('invisible'), 'True',
                            'Un rol sin restricción para el modelo no la impone.')
        self._restrict(self.role_contacts, hidden_field_ids=[Command.set(self._field('email').ids)])
        arch = self._arch()
        self.assertEqual(self._first(arch, "//field[@name='email']").get('invisible'), 'True')
        self.assertNotEqual(self._first(arch, "//field[@name='phone']").get('invisible'), 'True')

    def test_system_user_not_restricted(self):
        role_admin = self.Role.create({
            'name': 'Rol admin', 'exclusive_permissions': True,
            'implied_ids': [Command.set(self.env.ref('base.group_system').ids)],
            'readonly_all': True, 'block_debug': True,
        })
        self._restrict(role_admin, hidden_field_ids=[Command.set(self._field('email').ids)])
        self._assign(role_admin)
        self.assertTrue(self.user._is_system())
        self.assertEqual(self.Role.with_user(self.user)._al_ui_restrictions(), {})
        email = self._first(self._arch(), "//field[@name='email']")
        self.assertNotEqual(email.get('invisible'), 'True')

    def test_record_domain(self):
        Partner = self.env['res.partner']
        partner_a = Partner.create({'name': 'Dominio A'})
        partner_b = Partner.create({'name': 'Dominio B'})
        both = partner_a | partner_b
        self._assign(self.role_internal, self.role_contacts)
        self._restrict(self.role_internal, domain="[('name', '=', 'Dominio A')]")
        user_partner = Partner.with_user(self.user)
        self.assertEqual(user_partner.search([('id', 'in', both.ids)]), both,
                         'Solo un rol tiene dominio: no se limita.')
        self._restrict(self.role_contacts, domain="[('id', '=', -1)]")
        self.assertEqual(user_partner.search([('id', 'in', both.ids)]), partner_a)
        # Un dominio con un campo inexistente no se guarda.
        with self.assertRaises(ValidationError):
            self.role_contacts.restriction_ids.domain = "[('no_existe', '=', 1)]"

    def test_print_and_action_menus(self):
        Report = self.env['ir.actions.report']
        report_vals = {
            'model': 'res.partner', 'report_type': 'qweb-pdf',
            'binding_model_id': self.ir_partner.id,
        }
        report_hidden = Report.create({'name': 'oculto', 'report_name': 'al.oculto', **report_vals})
        report_shown = Report.create({'name': 'visible', 'report_name': 'al.visible', **report_vals})
        action_hidden = self.env['ir.actions.server'].create({
            'name': 'acción oculta', 'model_id': self.ir_partner.id,
            'binding_model_id': self.ir_partner.id, 'state': 'code', 'code': 'pass',
        })
        self._assign(self.role_internal)
        self._restrict(
            self.role_internal,
            hidden_report_ids=[Command.set(report_hidden.ids)],
            hidden_server_action_ids=[Command.set(action_hidden.ids)],
        )
        bindings = self.env['ir.actions.actions'].with_user(self.user).get_bindings('res.partner')
        report_ids = {a['id'] for a in bindings.get('report', [])}
        action_ids = {a['id'] for a in bindings.get('action', [])}
        self.assertIn(report_shown.id, report_ids)
        self.assertNotIn(report_hidden.id, report_ids)
        self.assertNotIn(action_hidden.id, action_ids)
        all_ids = {a['id'] for a in self.env['ir.actions.actions'].get_bindings('res.partner')['report']}
        self.assertIn(report_hidden.id, all_ids, 'Sin el rol el informe sigue visible.')

    def test_role_flags(self):
        self.role_internal.write({'readonly_all': True, 'block_debug': True, 'hide_chatter': True})
        self._assign(self.role_internal)
        restrictions = self.Role.with_user(self.user)._al_ui_restrictions()
        self.assertTrue(restrictions['block_debug'])
        self.assertTrue(restrictions['hide_chatter'])
        arch = self._arch()
        self.assertEqual(arch.get('edit'), 'False')
        self.assertEqual(arch.get('create'), 'False')
        session = self.env['ir.http'].with_user(self.user)._al_role_restrictions_session()
        self.assertTrue(session['readonly_all'])

    def test_export_and_archive_in_session(self):
        self._assign(self.role_internal)
        self._restrict(self.role_internal, hide_export=True, hide_archive=True)
        self.assertEqual(self._arch('list').get('export_xlsx'), 'False')
        session = self.env['ir.http'].with_user(self.user)._al_role_restrictions_session()
        self.assertEqual(session['models']['res.partner'],
                         {'hide_export': True, 'hide_archive': True})

    def test_readonly_is_enforced(self):
        """Solo lectura del modelo: real, no solo en la vista."""
        self._assign(self.role_contacts)
        partner = self.env['res.partner'].create({'name': 'Contacto lectura'})
        Partner = self.env['res.partner'].with_user(self.user)
        Partner.browse(partner.id).write({'name': 'cambio permitido'})

        self._restrict(self.role_contacts, is_readonly=True)
        record = Partner.browse(partner.id)
        self.assertEqual(record.name, 'cambio permitido', 'Sigue pudiendo leer.')
        with self.assertRaisesRegex(AccessError, 'solo permite consultar'):
            record.write({'name': 'cambio bloqueado'})
        with self.assertRaises(AccessError):
            Partner.create({'name': 'nuevo'})
        with self.assertRaises(AccessError):
            record.unlink()
        # Otro modelo no cambia.
        self.env['res.partner.category'].with_user(self.user).check_access('read')

    def test_readonly_all_is_enforced(self):
        """Todo en solo lectura: bloquea los modelos de negocio, no los exentos."""
        self._assign(self.role_contacts)
        self.role_contacts.readonly_all = True
        partner = self.env['res.partner'].create({'name': 'Contacto lectura'})
        with self.assertRaises(AccessError):
            partner.with_user(self.user).write({'name': 'cambio bloqueado'})
        # Exentos: favoritos y preferencias propias.
        self.env['ir.filters'].with_user(self.user).create({
            'name': 'favorito', 'model_id': 'res.partner', 'user_ids': [Command.link(self.user.id)],
        })
        self.user.with_user(self.user).write({'signature': '<p>AL</p>'})
        # El Administrador del sistema no tiene restricciones.
        self.assertFalse(self.env['al.user.role']._al_is_readonly_model('res.partner'))

    def test_hidden_fields_out_of_custom_search_and_export(self):
        """Campo oculto: sin filtro ni agrupación personalizada, ni Exportar."""
        self._assign(self.role_contacts)
        self._restrict(self.role_contacts, hidden_field_ids=[Command.set(self._field('email').ids)])
        attrs = ['searchable', 'sortable', 'groupable', 'exportable']
        desc = self.env['res.partner'].with_user(self.user).fields_get(['email', 'phone'], attrs)
        self.assertEqual({a: desc['email'][a] for a in attrs}, dict.fromkeys(attrs, False))
        self.assertTrue(desc['phone']['searchable'] and desc['phone']['exportable'])
        admin_desc = self.env['res.partner'].fields_get(['email'], attrs)
        self.assertTrue(admin_desc['email']['searchable'] and admin_desc['email']['exportable'])
        # Las vistas lo siguen recibiendo (invisible), sin romperse.
        views = self.env['res.partner'].with_user(self.user).get_views([(False, 'form')])
        self.assertFalse(views['models']['res.partner']['fields']['email'].get('searchable', False))

    def test_fields_must_belong_to_model(self):
        with self.assertRaises(ValidationError):
            self._restrict(self.role_internal, hidden_field_ids=[
                Command.set(self._field('login', 'res.users').ids)])

    def test_copy_role_copies_restrictions(self):
        self._restrict(self.role_internal, hide_create=True)
        copy = self.role_internal.copy()
        self.assertEqual(copy.restriction_ids.model_id, self.ir_partner)
        self.assertTrue(copy.restriction_ids.hide_create)


@tagged('post_install', '-at_install')
class TestAlUserRoleRestrictionUi(HttpCase):
    """El cliente web carga con los parches de Exportar / Archivar activos."""

    def test_contacts_list_with_restrictions(self):
        role = self.env['al.user.role'].create({
            'name': 'Rol UI', 'exclusive_permissions': True,
            'implied_ids': [Command.set(self.env.ref('base.group_user').ids)],
            'restriction_ids': [Command.create({
                'model_id': self.env['ir.model']._get('res.partner').id,
                'hide_export': True, 'hide_archive': True, 'hide_create': True,
            })],
        })
        user = self.env['res.users'].create({
            'name': 'Usuario UI', 'login': 'al_usuario_ui', 'password': 'al_usuario_ui',
        })
        self.env['al.user.role.line'].create({'role_id': role.id, 'user_id': user.id})
        self.env['res.partner'].create({'name': 'Contacto UI'})
        # La lista carga sin errores JS y sin el botón Nuevo (create="False").
        self.browser_js(
            '/odoo/action-base.action_partner_form?view_type=list',
            "if (document.querySelector('.o_list_button_add')) {"
            "  console.error('El botón Nuevo no debería estar');"
            "} else { console.log('test successful'); }",
            ready="!!document.querySelector('.o_list_renderer .o_data_row')",
            login='al_usuario_ui',
        )

    def test_block_debug_on_webclient(self):
        """``/odoo?debug=1`` carga sin modo desarrollador si el rol lo bloquea
        (la página es ``auth='none'``: el usuario sale de la sesión)."""
        role = self.env['al.user.role'].create({
            'name': 'Rol sin debug', 'block_debug': True,
            'implied_ids': [Command.set(self.env.ref('base.group_user').ids)],
        })
        user = self.env['res.users'].create({
            'name': 'Usuario sin debug', 'login': 'al_sin_debug', 'password': 'al_sin_debug',
        })
        self.env['al.user.role.line'].create({'role_id': role.id, 'user_id': user.id})
        self.authenticate('al_sin_debug', 'al_sin_debug')
        for debug in ('1', 'assets'):
            html = self.url_open(f'/odoo?debug={debug}').text
            self.assertIn('debug: ""', html, f'?debug={debug} no debe activar el modo desarrollador')
            self.assertIn('"debug_blocked_notice": true', html, 'Debe avisar del bloqueo.')
        # Sin intento de debug no se repite el aviso.
        self.assertNotIn('debug_blocked_notice', self.url_open('/odoo').text)

        # En el navegador: aparece el aviso y Ctrl+K no ofrece activar el debug.
        self.browser_js(
            '/odoo?debug=1',
            "const { registry } = odoo.loader.modules.get('@web/core/registry');"
            "const cmds = registry.category('command_provider').get('debug')"
            "    .provide({ debug: '' }, { searchValue: 'debug' });"
            "if (odoo.debug) { console.error('El modo desarrollador quedó activo'); }"
            "else if (cmds.length) { console.error('Ctrl+K ofrece activar el debug'); }"
            "else { console.log('test successful'); }",
            ready="!!document.querySelector('.o_notification')",
            login='al_sin_debug',
        )
        # Sin el bloqueo (control): el mismo usuario sí entra en modo desarrollador.
        role.block_debug = False
        self.assertIn('debug: "1"', self.url_open('/odoo?debug=1').text)

    def test_hide_send_message(self):
        """"Ocultar Enviar mensaje": el chatter solo registra notas, también en el servidor."""
        role = self.env['al.user.role'].create({
            'name': 'Rol solo notas', 'hide_send_message': True,
            'implied_ids': [Command.set((self.env.ref('base.group_user')
                                         | self.env.ref('base.group_partner_manager')).ids)],
        })
        user = self.env['res.users'].create({
            'name': 'Usuario notas', 'login': 'al_solo_notas', 'password': 'al_solo_notas',
        })
        self.env['al.user.role.line'].create({'role_id': role.id, 'user_id': user.id})
        partner = self.env['res.partner'].create({'name': 'Contacto notas'})
        self.authenticate('al_solo_notas', 'al_solo_notas')

        def post(subtype):
            return self.make_jsonrpc_request('/mail/message/post', {
                'thread_model': 'res.partner', 'thread_id': partner.id,
                'post_data': {'body': f'{subtype}', 'message_type': 'comment',
                              'subtype_xmlid': subtype},
            })
        post('mail.mt_note')
        with self.assertRaises(JsonRpcException):
            post('mail.mt_comment')
        bodies = self.env['mail.message'].search([('model', '=', 'res.partner'), ('res_id', '=', partner.id)]).mapped('body')
        self.assertTrue(any('mail.mt_note' in b for b in bodies))
        self.assertFalse(any('mail.mt_comment' in b for b in bodies))

        # En el navegador: sin "Enviar mensaje", con "Registrar nota".
        self.browser_js(
            f'/odoo/action-base.action_partner_form/{partner.id}',
            "if (document.querySelector('.o-mail-Chatter-sendMessage')) {"
            "  console.error('Enviar mensaje no debería estar');"
            "} else { console.log('test successful'); }",
            ready="!!document.querySelector('.o-mail-Chatter-logNote')",
            login='al_solo_notas',
        )

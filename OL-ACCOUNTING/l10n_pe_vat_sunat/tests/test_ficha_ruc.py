# -*- coding: utf-8 -*-
"""Ficha RUC completa: parser del portal SUNAT por etiquetas, actividades
económicas (CIIU), representantes legales y locales anexos sin duplicarse,
mapeos por defecto y valores por defecto del contacto."""
import datetime
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase

from ..models.l10n_pe_economic_activity import activity_commands
from ..services import activities, sunat_oficial
from odoo.addons.al_account_base.tests.common import use_pe_company

# Maquetación del portal e-consultaruc: cada dato en una fila con la
# etiqueta (h4 terminado en «:») y su valor (p, h4 o tabla).
FICHA_HTML = """
<div class="list-group">
 <div class="list-group-item"><div class="row">
  <div class="col-sm-5"><h4 class="list-group-item-heading">Número de RUC:</h4></div>
  <div class="col-sm-7"><h4 class="list-group-item-heading">20100070970 - SUPERMERCADOS PERUANOS SOCIEDAD ANONIMA</h4></div>
 </div></div>
 <div class="list-group-item"><div class="row">
  <div class="col-sm-5"><h4 class="list-group-item-heading">Tipo Contribuyente:</h4></div>
  <div class="col-sm-7"><p class="list-group-item-text">SOCIEDAD ANONIMA</p></div>
 </div></div>
 <div class="list-group-item"><div class="row">
  <div class="col-sm-5"><h4 class="list-group-item-heading">Nombre Comercial:</h4></div>
  <div class="col-sm-7"><p class="list-group-item-text">PLAZA VEA</p></div>
 </div></div>
 <div class="list-group-item"><div class="row">
  <div class="col-sm-3"><h4 class="list-group-item-heading">Fecha de Inscripción:</h4></div>
  <div class="col-sm-3"><p class="list-group-item-text">09/10/1992</p></div>
  <div class="col-sm-3"><h4 class="list-group-item-heading">Fecha de Inicio de Actividades:</h4></div>
  <div class="col-sm-3"><p class="list-group-item-text">01/10/1992</p></div>
 </div></div>
 <div class="list-group-item"><div class="row">
  <div class="col-sm-5"><h4 class="list-group-item-heading">Estado del Contribuyente:</h4></div>
  <div class="col-sm-7"><p class="list-group-item-text">ACTIVO</p></div>
 </div></div>
 <div class="list-group-item"><div class="row">
  <div class="col-sm-5"><h4 class="list-group-item-heading">Condición del Contribuyente:</h4></div>
  <div class="col-sm-7"><p class="list-group-item-text">HABIDO</p></div>
 </div></div>
 <div class="list-group-item"><div class="row">
  <div class="col-sm-5"><h4 class="list-group-item-heading">Domicilio Fiscal:</h4></div>
  <div class="col-sm-7"><p class="list-group-item-text">CAL. MORELLI NRO. 181 INT. P-2 LIMA - LIMA - SAN BORJA</p></div>
 </div></div>
 <div class="list-group-item"><div class="row">
  <div class="col-sm-3"><h4 class="list-group-item-heading">Sistema Emisión de Comprobante:</h4></div>
  <div class="col-sm-3"><p class="list-group-item-text">MANUAL/COMPUTARIZADO</p></div>
  <div class="col-sm-3"><h4 class="list-group-item-heading">Actividad Comercio Exterior:</h4></div>
  <div class="col-sm-3"><p class="list-group-item-text">IMPORTADOR/EXPORTADOR</p></div>
 </div></div>
 <div class="list-group-item"><div class="row">
  <div class="col-sm-5"><h4 class="list-group-item-heading">Sistema Contabilidad:</h4></div>
  <div class="col-sm-7"><p class="list-group-item-text">COMPUTARIZADO</p></div>
 </div></div>
 <div class="list-group-item"><div class="row">
  <div class="col-sm-5"><h4 class="list-group-item-heading">Actividad(es) Económica(s):</h4></div>
  <div class="col-sm-7"><table class="table tblResultado"><tbody>
   <tr><td>Principal    - 4711 - VENTA AL POR MENOR EN COMERCIOS NO ESPECIALIZADOS</td></tr>
   <tr><td>Secundaria 1 - 5610 - ACTIVIDADES DE RESTAURANTES Y DE SERVICIO MOVIL DE COMIDAS</td></tr>
   <tr><td>Secundaria 2 - CIIU 52110 - VTA. MIN. ALMACENES NO ESPECIALIZADOS</td></tr>
  </tbody></table></div>
 </div></div>
 <div class="list-group-item"><div class="row">
  <div class="col-sm-5"><h4 class="list-group-item-heading">Comprobantes de Pago c/aut. de impresión (F. 806 u 816):</h4></div>
  <div class="col-sm-7"><table class="table tblResultado"><tbody>
   <tr><td>FACTURA</td></tr><tr><td>BOLETA DE VENTA</td></tr>
  </tbody></table></div>
 </div></div>
 <div class="list-group-item"><div class="row">
  <div class="col-sm-5"><h4 class="list-group-item-heading">Sistema de Emisión Electrónica:</h4></div>
  <div class="col-sm-7"><table class="table tblResultado"><tbody>
   <tr><td>FACTURA PORTAL DESDE 01/01/2014</td></tr><tr><td>DESDE LOS SISTEMAS DEL CONTRIBUYENTE. AUTORIZ DESDE 15/01/2014</td></tr>
  </tbody></table></div>
 </div></div>
 <div class="list-group-item"><div class="row">
  <div class="col-sm-5"><h4 class="list-group-item-heading">Emisor electrónico desde:</h4></div>
  <div class="col-sm-7"><p class="list-group-item-text">15/01/2014</p></div>
 </div></div>
 <div class="list-group-item"><div class="row">
  <div class="col-sm-5"><h4 class="list-group-item-heading">Comprobantes Electrónicos:</h4></div>
  <div class="col-sm-7"><p class="list-group-item-text">FACTURA (desde 15/01/2014),BOLETA (desde 01/03/2015)</p></div>
 </div></div>
 <div class="list-group-item"><div class="row">
  <div class="col-sm-5"><h4 class="list-group-item-heading">Afiliado al PLE desde:</h4></div>
  <div class="col-sm-7"><p class="list-group-item-text">01/01/2013</p></div>
 </div></div>
 <div class="list-group-item"><div class="row">
  <div class="col-sm-5"><h4 class="list-group-item-heading">Padrones:</h4></div>
  <div class="col-sm-7"><table class="table tblResultado"><tbody>
   <tr><td>Incorporado al Régimen de Agentes de Retención de IGV (R.S.037-2002) a partir del 01/06/2002</td></tr>
  </tbody></table></div>
 </div></div>
</div>
"""

# Contribuyente dado de baja: el portal agrega la fecha de baja.
BAJA_HTML = """
<div class="list-group">
 <div class="list-group-item"><div class="row">
  <div class="col-sm-5"><h4 class="list-group-item-heading">Número de RUC:</h4></div>
  <div class="col-sm-7"><h4 class="list-group-item-heading">20512345678 - EMPRESA CERRADA S.A.C.</h4></div>
 </div></div>
 <div class="list-group-item"><div class="row">
  <div class="col-sm-5"><h4 class="list-group-item-heading">Tipo Contribuyente:</h4></div>
  <div class="col-sm-7"><p class="list-group-item-text">SOCIEDAD ANONIMA CERRADA</p></div>
 </div></div>
 <div class="list-group-item"><div class="row">
  <div class="col-sm-3"><h4 class="list-group-item-heading">Estado del Contribuyente:</h4></div>
  <div class="col-sm-3"><p class="list-group-item-text">BAJA DE OFICIO</p></div>
  <div class="col-sm-3"><h4 class="list-group-item-heading">Fecha de Baja:</h4></div>
  <div class="col-sm-3"><p class="list-group-item-text">31/03/2017</p></div>
 </div></div>
 <div class="list-group-item"><div class="row">
  <div class="col-sm-5"><h4 class="list-group-item-heading">Condición del Contribuyente:</h4></div>
  <div class="col-sm-7"><p class="list-group-item-text">NO HALLADO</p></div>
 </div></div>
 <div class="list-group-item"><div class="row">
  <div class="col-sm-5"><h4 class="list-group-item-heading">Actividad(es) Económica(s):</h4></div>
  <div class="col-sm-7"><table class="table tblResultado"><tbody><tr><td>-</td></tr></tbody></table></div>
 </div></div>
</div>
"""


@tagged('post_install', '-at_install')
class TestFichaRucParser(TransactionCase):

    def test_full_record_by_label(self):
        r = sunat_oficial._parse_ruc_html(FICHA_HTML, '20100070970')
        self.assertEqual(r.name, 'SUPERMERCADOS PERUANOS SOCIEDAD ANONIMA')
        self.assertEqual(r.taxpayer_type, 'SOCIEDAD ANONIMA')
        self.assertEqual(r.commercial_name, 'PLAZA VEA')
        self.assertEqual(r.registration_date, '09/10/1992')
        self.assertEqual(r.activity_start_date, '01/10/1992')
        self.assertEqual((r.state, r.condition), ('ACTIVO', 'HABIDO'))
        self.assertTrue(r.address.startswith('CAL. MORELLI'))
        self.assertEqual(r.invoice_system, 'MANUAL/COMPUTARIZADO')
        self.assertEqual(r.foreign_trade, 'IMPORTADOR/EXPORTADOR')
        self.assertEqual(r.accounting_system, 'COMPUTARIZADO')
        self.assertEqual(len(r.economic_activities), 3)
        self.assertIn('4711', r.economic_activities[0])
        self.assertEqual(r.printed_documents, 'FACTURA\nBOLETA DE VENTA')
        self.assertIn('FACTURA PORTAL', r.einvoice_systems)
        self.assertEqual(r.einvoice_since, '15/01/2014')
        self.assertIn('BOLETA', r.electronic_documents)
        self.assertEqual(r.ple_since, '01/01/2013')
        self.assertIn('Agentes de Retención', r.padrones)
        self.assertFalse(r.deregistration_date)

    def test_deregistered_taxpayer(self):
        r = sunat_oficial._parse_ruc_html(BAJA_HTML, '20512345678')
        self.assertEqual(r.state, 'BAJA DE OFICIO')
        self.assertEqual(r.deregistration_date, '31/03/2017')
        self.assertEqual(r.condition, 'NO HALLADO')
        self.assertEqual(r.economic_activities, [], 'el «-» del portal no es una actividad')

    def test_activity_text_formats(self):
        self.assertEqual(activities.parse('Principal    - 4711 - VENTA AL POR MENOR'),
                         ('principal', '4711', 'VENTA AL POR MENOR'))
        self.assertEqual(activities.parse('Secundaria 2 - CIIU 52110 - VTA. MIN.'),
                         ('secondary', '52110', 'VTA. MIN.'))
        self.assertEqual(activities.parse('4520 - MANTENIMIENTO'), (None, '4520', 'MANTENIMIENTO'))


@tagged('post_install', '-at_install')
class TestFichaRucPartner(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.pe = cls.env.ref('base.pe')
        cls.company_pe = cls.env['res.company'].create({
            'name': 'FICHA RUC TEST S.A.C.', 'country_id': cls.pe.id})
        cls.company_pe._l10n_pe_seed_default_connections()
        cls.partner = cls.env['res.partner'].create({
            'name': 'SUPERMERCADOS PERUANOS', 'is_company': True, 'country_id': cls.pe.id,
            'vat': '20100070970'})

    def test_catalog_is_loaded(self):
        Activity = self.env['l10n_pe.economic.activity']
        self.assertGreater(Activity.search_count([]), 400)
        retail = Activity.search([('code', '=', '4711')])
        self.assertEqual(retail.display_name[:6], '4711 -')
        self.assertIn(retail, Activity.search([('display_name', 'ilike', '4711')]))

    def test_activities_replace_and_create_unknown(self):
        texts = sunat_oficial._parse_ruc_html(FICHA_HTML, '20100070970').economic_activities
        self.partner.l10n_pe_economic_activity_ids = activity_commands(self.env, texts)
        lines = self.partner.l10n_pe_economic_activity_ids.sorted('sequence')
        self.assertEqual(lines.mapped('kind'), ['principal', 'secondary', 'secondary'])
        self.assertEqual(lines.mapped('code'), ['4711', '5610', '52110'])
        self.assertEqual(lines.mapped('label'), ['Principal', 'Secundaria 1', 'Secundaria 2'])
        self.assertEqual(self.partner.l10n_pe_main_activity_id.code, '4711')
        # La CIIU Rev. 3 de la ficha antigua no estaba: se agregó al catálogo.
        self.assertTrue(self.env['l10n_pe.economic.activity'].search([('code', '=', '52110')]))
        # Reconsultar reemplaza, no acumula.
        self.partner.l10n_pe_economic_activity_ids = activity_commands(self.env, texts[:1])
        self.assertEqual(len(self.partner.l10n_pe_economic_activity_ids), 1)

    def test_internal_user_gets_unknown_activity(self):
        """Un usuario sin permiso sobre el catálogo puede recibir una
        actividad nueva al consultar (se crea con sudo justificado)."""
        user = self.env['res.users'].create({
            'name': 'Ventas', 'login': 'ficha_ruc_user',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        Activity = self.env['l10n_pe.economic.activity'].with_user(user)
        self.assertFalse(Activity.has_access('create'))
        activity = Activity._l10n_pe_get_or_create('99999', 'ACTIVIDAD DE PRUEBA')
        self.assertEqual(activity.code, '99999')

    def test_apply_result_full_record(self):
        result = sunat_oficial._parse_ruc_html(FICHA_HTML, '20100070970')
        sunat = self.company_pe.l10n_pe_api_connection_ids.filtered(
            lambda c: c.name == 'SUNAT (oficial)')
        reps = [{'doc_type': 'DNI', 'doc_number': '10203040', 'name': 'PEREZ GOMEZ JUAN',
                 'position': 'GERENTE GENERAL', 'from_date': '01/02/2019'},
                {'doc_type': 'DNI', 'doc_number': '50607080', 'name': 'DIAZ LUIS',
                 'position': 'DIRECTOR', 'from_date': '01/02/2019'}]
        annex = [{'code': '0003', 'type': 'SUCURSAL', 'address': 'AV. LARCO 123 MIRAFLORES',
                  'activity': '4711 - VENTA AL POR MENOR'}]
        data = dict(vars(result), legal_representatives=reps, annexed_locals=annex)
        with patch.object(type(sunat), '_fetch_data', return_value=data):
            vals, extra = sunat.run('20100070970', 'ruc')
        self.assertEqual(vals['l10n_pe_taxpayer_type'], 'SOCIEDAD ANONIMA')
        self.assertEqual(vals['l10n_pe_registration_date'], datetime.date(1992, 10, 9))
        self.assertEqual(vals['l10n_pe_ple_since'], datetime.date(2013, 1, 1))
        for _i in range(2):  # reconsultar no duplica
            self.partner.with_company(self.company_pe)._apply_api_result('ruc', vals, extra)
        p = self.partner
        self.assertEqual(p.l10n_pe_accounting_system, 'COMPUTARIZADO')
        self.assertEqual(p.l10n_pe_einvoice_since, datetime.date(2014, 1, 15))
        self.assertEqual(p.l10n_pe_main_activity_id.code, '4711')
        reps_children = p.child_ids.filtered('l10n_pe_is_legal_rep')
        self.assertEqual(len(reps_children), 1, 'solo el gerente, y una sola vez')
        self.assertEqual(reps_children.l10n_pe_legal_rep_doc_number, '10203040')
        self.assertEqual(reps_children.l10n_pe_legal_rep_since, datetime.date(2019, 2, 1))
        local = p.child_ids.filtered(lambda c: c.l10n_pe_annex_code == '0003')
        self.assertEqual(len(local), 1)
        self.assertEqual((local.type, local.l10n_pe_annex_type), ('delivery', 'SUCURSAL'))
        self.assertIn('4711', local.l10n_pe_annex_activity)

    def test_existing_contacts_are_updated_not_duplicated(self):
        """Un local o un representante creados antes (sin código ni documento)
        se completan al reconsultar."""
        old_local = self.env['res.partner'].create({
            'name': '0003 - SUCURSAL', 'type': 'delivery', 'parent_id': self.partner.id})
        self.partner._sync_annexed_locals([{'code': '0003', 'type': 'SUCURSAL', 'address': 'X'}])
        self.assertEqual(old_local.l10n_pe_annex_code, '0003')
        self.assertEqual(len(self.partner.child_ids), 1)

    def test_decolecta_full_record_mapping(self):
        decolecta = self.company_pe.l10n_pe_api_connection_ids.filtered(
            lambda c: c.name == 'Decolecta')
        decolecta.token = 'fake'
        response = {
            'razon_social': 'SUPERMERCADOS PERUANOS', 'estado': 'ACTIVO', 'condicion': 'HABIDO',
            'tipo': 'SOCIEDAD ANONIMA', 'tipo_facturacion': 'COMPUTARIZADO',
            'tipo_contabilidad': 'COMPUTARIZADO', 'comercio_exterior': 'SIN ACTIVIDAD',
            'actividad_economica': '4711 - VENTA AL POR MENOR',
        }
        with patch.object(type(decolecta), '_fetch_data', return_value=response):
            vals, extra = decolecta.run('20100070970', 'ruc')
        self.assertEqual(vals['l10n_pe_taxpayer_type'], 'SOCIEDAD ANONIMA')
        self.assertEqual(vals['l10n_pe_invoice_system'], 'COMPUTARIZADO')
        self.assertEqual(vals['l10n_pe_foreign_trade'], 'SIN ACTIVIDAD')
        self.assertEqual(extra['economic_activities'], ['4711 - VENTA AL POR MENOR'])

    def test_sync_default_mappings_is_idempotent(self):
        sunat = self.company_pe.l10n_pe_api_connection_ids.filtered(
            lambda c: c.name == 'SUNAT (oficial)')
        count = len(sunat.mapping_ids)
        sunat.mapping_ids.filtered(lambda m: m.field_name == 'l10n_pe_ple_since').unlink()
        self.company_pe._l10n_pe_sync_default_mappings('SUNAT (oficial)')
        self.company_pe._l10n_pe_sync_default_mappings('SUNAT (oficial)')
        self.assertEqual(len(sunat.mapping_ids), count)

    def test_defaults_for_peruvian_company(self):
        Partner = self.env['res.partner'].with_company(self.company_pe).with_context(
            allowed_company_ids=[self.company_pe.id])
        self.env.user.company_ids |= self.company_pe
        # Solo el comportamiento del formulario: la compañía de prueba no tiene
        # plan contable, así que no se guarda.
        form = Form(Partner.with_user(self.env.user).with_company(self.company_pe))
        # Odoo 20: el tipo sale del identificador (DNI) o del RUC (vat).
        form.additional_identifiers = {'PE_DNI': '45678901'}
        self.assertEqual(form.company_type, 'person')
        form.additional_identifiers = {}
        form.vat = '20100070970'
        self.assertEqual(form.company_type, 'company')


@tagged('post_install', '-at_install')
class TestFichaRucCompletion(TransactionCase):
    """La primera conexión que responde suele ser una API básica: el botón
    «Actualizar» completa la ficha RUC con las demás conexiones y, si
    ninguna la trae, lo avisa."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        pe = cls.env.ref('base.pe')
        cls.company_pe = cls.env['res.company'].create({
            'name': 'FICHA COMPLETA TEST S.A.C.', 'country_id': pe.id})
        cls.company_pe._l10n_pe_seed_default_connections()
        cls.company_pe.l10n_pe_api_connection_ids.write({'token': 'x', 'enabled': True})
        cls.company_pe.write({'l10n_pe_ruc_validation': True, 'l10n_pe_dni_validation': True})
        cls.partner = cls.env['res.partner'].with_company(cls.company_pe).create({
            'name': 'AGROLIGHT PERU S.A.C.', 'is_company': True, 'country_id': pe.id,
            'vat': '20100070970'})

    def _run(self, ficha_ok):
        calls = []

        def fake_run(connection, document, doc_type, quick=False):
            calls.append(connection.name)
            if len(calls) == 1:
                return {'name': 'AGROLIGHT PERU S.A.C.', 'state': 'ACTIVO'}, {}
            if not ficha_ok:
                raise UserError('SUNAT no respondió al GET inicial.')
            return ({'name': 'OTRO NOMBRE', 'l10n_pe_taxpayer_type': 'SOCIEDAD ANONIMA CERRADA',
                     'l10n_pe_accounting_system': 'COMPUTARIZADO'},
                    {'economic_activities': ['Principal - 0161 - ACTIVIDADES DE APOYO A LA AGRICULTURA']})

        Connection = type(self.env['l10n_pe.api.connection'])
        with patch.object(Connection, 'run', fake_run), \
                patch.object(Connection, '_is_usable', lambda self: True):
            action = self.partner.with_company(self.company_pe).action_update_document()
        return calls, action

    def test_second_connection_completes_the_ficha(self):
        calls, action = self._run(ficha_ok=True)
        self.assertGreaterEqual(len(calls), 2)
        self.assertIs(action, True)
        p = self.partner
        self.assertEqual(p.name, 'AGROLIGHT PERU S.A.C.', 'lo de la primera conexión manda')
        self.assertEqual(p.l10n_pe_taxpayer_type, 'SOCIEDAD ANONIMA CERRADA')
        self.assertEqual(p.l10n_pe_main_activity_id.code, '0161')

    def test_warns_when_no_connection_has_the_ficha(self):
        calls, action = self._run(ficha_ok=False)
        self.assertGreaterEqual(len(calls), 2)
        self.assertEqual(action['tag'], 'display_notification')
        self.assertIn('SUNAT no respondió', action['params']['message'])
        self.assertEqual(self.partner.state, 'ACTIVO', 'los datos básicos sí se guardan')

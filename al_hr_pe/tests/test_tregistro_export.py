# -*- coding: utf-8 -*-
"""Exportador de la carga masiva del T-Registro (E04 / E05 / E11).

Las reglas de formato son las del manual del PVS §7.3.1: palote como
separador **y al final de la línea**, sin espacios, campos opcionales
vacíos, fechas dd/mm/aaaa. Un fallo aquí lo rechaza el validador de SUNAT
sin decir por qué, así que se comprueba campo a campo.
"""
import io
import zipfile
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestTregistroExport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create(
            {'name': 'Exporta T-Registro S.A.C.', 'vat': '20512528458'})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))
        cls.dni = cls.env.ref('l10n_pe.it_DNI')
        cls.district = cls.env['l10n_pe.res.city.district'].search(
            [('code', '=', '150101')], limit=1) or \
            cls.env['l10n_pe.res.city.district'].search([], limit=1)

        cls.employee = cls.env['hr.employee'].create({
            'name': 'Ñañez Ordóñez José María',
            'last_name': 'Ñañez', 'm_last_name': 'Ordóñez',
            'names': 'José María',
            'company_id': cls.company.id,
            'identification_id': '03300605',
            'l10n_latam_identification_type_id': cls.dni.id,
            'birthday': date(1970, 12, 12),
            'sex': 'male',
            'private_phone': '073375169',
            'private_email': 'jose@example.com',
            # Domicilio
            'l10n_pe_road_type_id': cls.env.ref('al_hr_pe.road_type_02').id,
            'l10n_pe_road_name': 'Lima',
            'l10n_pe_road_number': '435',
            'l10n_pe_district_id': cls.district.id,
        })
        # La E17 exige establecimiento con código SUNAT en el alta.
        cls.location = cls.env['hr.work.location'].create({
            'name': 'Sede principal', 'company_id': cls.company.id,
            'location_type': 'office',
            'address_id': cls.company.partner_id.id,
            'l10n_pe_establishment_code': '0001',
        })
        cls.employee.work_location_id = cls.location
        cls.reason = cls.env['hr.reasons.leave'].search([], limit=1)
        cls.insurance = cls.env['hr.social.insurance'].search([], limit=1)
        cls.insurance.l10n_pe_tregistro_code = '00'   # EsSalud regular
        cls.membership = cls.env['hr.membership'].search([], limit=1)
        cls.membership.l10n_pe_tregistro_code = '02'  # SNP - ONP
        version = cls.employee.version_id
        version.write({
            'contract_date_start': date(2014, 7, 12),
            'wage': 4300.0,
            'l10n_pe_labor_regime_id': cls.env.ref('al_hr_pe.labor_regime_01').id,
            # Secundaria completa: sin estudios concluidos que declarar,
            # así el fixture se centra en E04/E05/E11.
            'l10n_pe_education_level_id': cls.env.ref(
                'al_hr_pe.education_level_07').id,
            'l10n_pe_occupation_id': cls.env['l10n_pe.hr.occupation'].search(
                [('for_employee', '=', True)], limit=1).id,
            'l10n_pe_occupational_category_id': cls.env.ref(
                'al_hr_pe.occ_category_03').id,
            'l10n_pe_contract_type_id': cls.env.ref(
                'al_hr_pe.contract_type_03').id,
            'l10n_pe_unionized': True,
            # Efectivo: este fixture no ejercita la E30 (tiene su propia
            # batería en TestTregistroExtra).
            'l10n_pe_payment_type': '1',
            'worker_type_id': cls.env['hr.worker.type'].search([], limit=1).id,
            'situation_id': cls.env['hr.situation'].search([], limit=1).id,
            'social_insurance_id': cls.insurance.id,
            'membership_id': cls.membership.id,
        })
        cls.version = version

    # ------------------------------------------------------------------
    # Formato del archivo plano
    # ------------------------------------------------------------------
    def test_line_ends_with_pipe(self):
        """El manual exige palote también al final (error EPR1.59)."""
        line = self.employee._l10n_pe_txt_line(['01', '03300605', '604'])
        self.assertEqual(line, '01|03300605|604|')
        self.assertTrue(line.endswith('|'))

    def test_empty_optional_is_two_pipes(self):
        line = self.employee._l10n_pe_txt_line(['01', '', False, None, '2'])
        self.assertEqual(line, '01||||2|')

    def test_text_is_cleaned(self):
        """Sin tildes, sin palotes y sin dobles espacios."""
        clean = self.employee._l10n_pe_txt_clean(' Ñañez  Ordóñez|José ')
        self.assertEqual(clean, 'NANEZ ORDONEZ JOSE')
        self.assertNotIn('|', clean)

    def test_no_trailing_whitespace(self):
        files = self.employee._l10n_pe_tregistro_files('alta')
        for name, content in files.items():
            for number, line in enumerate(content.splitlines(), start=1):
                self.assertEqual(line, line.rstrip(),
                                 '%s línea %d con espacios al final'
                                 % (name, number))
                self.assertTrue(line.endswith('|'),
                                '%s línea %d sin palote final' % (name, number))

    # ------------------------------------------------------------------
    # Estructuras
    # ------------------------------------------------------------------
    def test_e04_has_41_fields(self):
        row = self.employee._l10n_pe_e04_row()
        self.assertEqual(len(row), 41, 'la E04 tiene 41 columnas')
        self.assertEqual(row[0], '01', 'DNI = 01, con dos dígitos')
        self.assertEqual(row[1], '03300605')
        self.assertEqual(row[2], '604', 'documento peruano → país 604')
        self.assertEqual(row[3], '12/12/1970')
        self.assertEqual(row[4], 'NANEZ', 'apellido sin tilde y en mayúscula')
        self.assertEqual(row[5], 'ORDONEZ')
        self.assertEqual(row[6], 'JOSE MARIA')
        self.assertEqual(row[7], '1', 'sexo masculino = 1')
        # Teléfono partido en código de larga distancia y número
        self.assertEqual((row[9], row[10]), ('', '073375169'))
        self.assertEqual(row[11], 'jose@example.com')
        # Dirección 1 (campos 13-26 → índices 12-25)
        self.assertEqual(row[12], '02', 'T05: jirón')
        self.assertEqual(row[13], 'Lima')
        self.assertEqual(row[14], '435')
        self.assertEqual(row[25], self.district.code, 'ubigeo del distrito')
        self.assertEqual(row[40], '1', 'indicador de centro asistencial')

    def test_e05_has_23_fields(self):
        row = self.employee._l10n_pe_e05_row()
        self.assertEqual(len(row), 23, 'la E05 tiene 23 columnas')
        self.assertEqual(row[3], '01', 'T33: D.Leg. 728')
        self.assertEqual(row[4], '07', 'T09: secundaria completa')
        self.assertEqual(row[9], '03', 'T12: por inicio o incremento')
        self.assertEqual(row[13], '1', 'sindicalizado')
        self.assertEqual(row[15], '4300.00', 'remuneración con 2 decimales')
        self.assertEqual(row[20], '03', 'T24: empleado')

    def test_e11_alta_has_four_rows(self):
        """El alta declara vínculo, tipo de trabajador, salud y pensión."""
        rows = self.employee._l10n_pe_e11_rows('alta')
        self.assertEqual(len(rows), 4)
        for row in rows:
            self.assertEqual(len(row), 9, 'la E11 tiene 9 columnas')
            self.assertEqual(row[3], '1', 'categoría 1 = trabajador')
            self.assertEqual(row[5], '12/07/2014', 'fecha de inicio')
            self.assertFalse(row[6], 'el alta no lleva fecha de fin')
        self.assertEqual([row[4] for row in rows], ['1', '2', '3', '4'],
                         'tipos de registro en orden')
        self.assertEqual(rows[2][7], '00', 'T32: EsSalud regular')
        self.assertEqual(rows[3][7], '02', 'T11: SNP - ONP')

    def test_e11_baja_is_a_single_row(self):
        """La baja solo remite la estructura 11 (manual §II)."""
        self.version.write({
            'contract_date_end': date(2026, 7, 31),
            'situation_reason_id': self.reason.id,
        })
        rows = self.employee._l10n_pe_e11_rows('baja')
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row[4], '1', 'tipo de registro: vínculo')
        self.assertFalse(row[5], 'la baja no lleva fecha de inicio')
        self.assertEqual(row[6], '31/07/2026')
        self.assertEqual(row[7], self.reason.code,
                         'el motivo T17 va en el indicador del tipo de registro')

    # ------------------------------------------------------------------
    # Archivos
    # ------------------------------------------------------------------
    def test_alta_generates_three_files(self):
        files = self.employee._l10n_pe_tregistro_files('alta')
        self.assertEqual(sorted(files), [
            'RP_20512528458.est',
            'RP_20512528458.ide',
            'RP_20512528458.per',
            'RP_20512528458.tra',
        ], 'nombres RP_<RUC>.<ext> del manual §7.1')

    def test_baja_only_generates_per(self):
        self.version.write({
            'contract_date_end': date(2026, 7, 31),
            'situation_reason_id': self.reason.id,
        })
        files = self.employee._l10n_pe_tregistro_files('baja')
        self.assertEqual(list(files), ['RP_20512528458.per'],
                         'la baja no reenvía datos personales ni del trabajador')

    def test_zip_download(self):
        action = self.employee.action_l10n_pe_export_tregistro()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        attachment = self.env['ir.attachment'].search(
            [('res_model', '=', 'res.company'),
             ('res_id', '=', self.company.id)], order='id desc', limit=1)
        self.assertTrue(attachment.name.startswith('tregistro_alta_'))
        import base64
        archive = zipfile.ZipFile(io.BytesIO(base64.b64decode(attachment.datas)))
        self.assertEqual(len(archive.namelist()), 4)
        contenido = archive.read('RP_20512528458.tra').decode('latin-1')
        self.assertTrue(contenido.endswith('|'))

    def test_several_employees_one_line_each(self):
        second = self.env['hr.employee'].create({
            'name': 'Vargas Soto Ana',
            'last_name': 'Vargas', 'm_last_name': 'Soto', 'names': 'Ana',
            'company_id': self.company.id,
            'identification_id': '03300606',
            'l10n_latam_identification_type_id': self.dni.id,
            'birthday': date(1985, 3, 4),
            'sex': 'female',
            'l10n_pe_district_id': self.district.id,
            'work_location_id': self.location.id,
        })
        second.version_id.write({
            'contract_date_start': date(2015, 1, 5),
            'wage': 2500.0,
            'l10n_pe_labor_regime_id': self.version.l10n_pe_labor_regime_id.id,
            'l10n_pe_education_level_id':
                self.version.l10n_pe_education_level_id.id,
            'l10n_pe_payment_type': '1',
            'l10n_pe_occupation_id': self.version.l10n_pe_occupation_id.id,
            'l10n_pe_occupational_category_id':
                self.version.l10n_pe_occupational_category_id.id,
            'l10n_pe_contract_type_id': self.version.l10n_pe_contract_type_id.id,
            'situation_id': self.version.situation_id.id,
            'worker_type_id': self.version.worker_type_id.id,
            'social_insurance_id': self.insurance.id,
            'membership_id': self.membership.id,
        })
        files = (self.employee | second)._l10n_pe_tregistro_files('alta')
        self.assertEqual(len(files['RP_20512528458.ide'].splitlines()), 2)
        self.assertEqual(len(files['RP_20512528458.per'].splitlines()), 8,
                         '4 renglones de períodos por trabajador')

    # ------------------------------------------------------------------
    # Validaciones previas
    # ------------------------------------------------------------------
    def test_blocks_missing_tregistro_data(self):
        self.version.l10n_pe_occupation_id = False
        with self.assertRaises(UserError) as error:
            self.employee._l10n_pe_tregistro_files('alta')
        self.assertIn('ocupación', str(error.exception))

    def test_blocks_missing_ruc(self):
        self.company.vat = False
        with self.assertRaises(UserError):
            self.employee._l10n_pe_tregistro_files('alta')

    def test_blocks_two_companies(self):
        other = self.env['res.company'].create(
            {'name': 'Otra S.A.C.', 'vat': '20131312955'})
        other_employee = self.env['hr.employee'].create(
            {'name': 'Ajeno', 'company_id': other.id})
        with self.assertRaises(UserError):
            (self.employee | other_employee)._l10n_pe_tregistro_files('alta')

    def test_baja_needs_end_date(self):
        with self.assertRaises(UserError) as error:
            self.employee._l10n_pe_tregistro_files('baja')
        self.assertIn('cese', str(error.exception))

    def test_baja_needs_reason(self):
        self.version.contract_date_end = date(2026, 7, 31)
        with self.assertRaises(UserError) as error:
            self.employee._l10n_pe_tregistro_files('baja')
        self.assertIn('motivo de baja', str(error.exception))

    def test_foreign_document_needs_country(self):
        """Con pasaporte, el país emisor sale de la tabla 26, no 604."""
        passport = self.env.ref('l10n_latam_base.it_pass')
        passport.l10n_pe_hr_sunat_code = '7'
        self.employee.l10n_latam_identification_type_id = passport
        doc_type, dummy, country = self.employee._l10n_pe_doc_pair()
        self.assertEqual(doc_type, '07')
        self.assertFalse(country, 'sin código de país no se inventa 604')
        self.employee.l10n_pe_country_emitter = '9061'
        self.assertEqual(self.employee._l10n_pe_doc_pair()[2], '9061')

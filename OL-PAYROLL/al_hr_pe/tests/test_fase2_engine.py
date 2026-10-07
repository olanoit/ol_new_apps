# -*- coding: utf-8 -*-
"""Fase 2: paridad de cálculo del motor de nómina PE.

Fixture de referencia (caso estándar): trabajador régimen general, mes
completo, sueldo 3 000, AFP con comisión sobre flujo, EsSalud 9 %. Las
expectativas se derivan de las TASAS de los datos maestros (no números
mágicos): si la SBS cambia la tasa en data, el test sigue validando la
FÓRMULA.
"""
import base64
from datetime import date
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFase2Engine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'PE Motor SAC',
            'country_id': cls.env.ref('base.pe').id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))
        cls.env.user.company_ids |= cls.company
        cls.env.user.group_ids |= cls.env.ref(
            'hr_payroll.group_hr_payroll_manager')
        cls.param = cls.env['hr.main.parameter'].create({
            'company_id': cls.company.id, 'rmv': 1130.0})
        cls.afp = cls.env['hr.membership'].search(
            [('is_afp', '=', True), ('company_id', '=', False)], limit=1)
        cls.structure = cls.env.ref('al_hr_pe.base_structure')
        cls.employee = cls.env['hr.employee'].create({
            'names': 'María', 'last_name': 'Quispe', 'm_last_name': 'Rojas',
            'company_id': cls.company.id,
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
            'wage': 3000.0,
            'structure_type_id': cls.structure.type_id.id,
        })
        cls.employee.version_id.write({
            'membership_id': cls.afp.id,
            'l10n_pe_commission_type': 'flow',
        })

    def _compute_slip(self):
        slip = self.env['hr.payslip'].create({
            'name': 'Boleta PE test',
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 3, 1),
            'date_to': date(2026, 3, 31),
        })
        slip.compute_sheet()
        return slip

    def _line(self, slip, code):
        return slip.line_ids.filtered(lambda l: l.code == code)

    def test_jor_hours_and_minutes(self):
        """El .jor declara horas y minutos (07/10/2026: antes truncaba)."""
        run = self.env['hr.payslip.run']
        self.assertEqual(run._l10n_pe_hours_minutes(10.5), (10, 30))
        self.assertEqual(run._l10n_pe_hours_minutes(160.0), (160, 0))
        self.assertEqual(run._l10n_pe_hours_minutes(0.0), (0, 0))

    def test_rmv_by_period(self):
        """RMV vigente al cierre de cada periodo: 1 130 en setiembre y 1 230
        desde octubre de 2026 (D.S. 015-2026-TR), aunque el parámetro de la
        compañía diga otra cosa."""
        slips = {}
        for month in (9, 10):
            slip = self.env['hr.payslip'].create({
                'name': 'Boleta RMV %s' % month, 'employee_id': self.employee.id,
                'struct_id': self.structure.id,
                'date_from': date(2026, month, 1),
                'date_to': date(2026, month, 30)})
            slips[month] = slip
        self.assertEqual(slips[9].rmv, 1130.0)
        self.assertEqual(slips[10].rmv, 1230.0)
        self.assertAlmostEqual(slips[10].family_allowance, 123.0)

    def test_snapshot_follows_the_membership(self):
        """Cambiar de afiliación con la boleta en borrador rehace las tasas."""
        slip = self._compute_slip()
        onp = self.env['hr.membership'].search(
            [('is_afp', '=', False), ('company_id', '=', False)], limit=1)
        if not onp:
            self.skipTest('sin ONP en los datos')
        self.employee.version_id.membership_id = onp
        self.assertEqual(slip.membership_id, onp)
        self.assertAlmostEqual(slip.l10n_pe_retirement_fund, onp.retirement_fund)

    def test_snapshot(self):
        slip = self._compute_slip()
        self.assertEqual(slip.rmv, 1130.0)
        self.assertAlmostEqual(slip.family_allowance, 113.0)
        self.assertEqual(slip.membership_id, self.afp)
        self.assertAlmostEqual(
            slip.l10n_pe_retirement_fund, self.afp.retirement_fund)
        self.assertAlmostEqual(
            slip.l10n_pe_commission, self.afp.fixed_commision)

    def test_worked_days_zero_lines(self):
        """Todos los códigos PE tienen línea (aunque cero): las fórmulas
        con worked_days['X'] nunca deben reventar."""
        slip = self._compute_slip()
        codes = set(slip.worked_days_line_ids.mapped('code'))
        for code in ('DLAB', 'FAL', 'TAR', 'DMED', 'DVAC', 'DOM'):
            self.assertIn(code, codes)

    def test_base_afp_essalud_net(self):
        slip = self._compute_slip()
        wage = 3000.0
        bas = self._line(slip, 'BAS')
        self.assertTrue(bas, 'Sin línea BAS')
        # Mes completo → básico = sueldo
        self.assertAlmostEqual(bas.total, wage, places=1)
        # Fondo AFP sobre el afecto (mes completo sin variables = wage)
        a_jub = self._line(slip, 'A_JUB')
        self.assertTrue(a_jub, 'Sin línea A_JUB')
        expected_fund = round(wage * self.afp.retirement_fund / 100, 2)
        self.assertAlmostEqual(abs(a_jub.total), expected_fund, places=1)
        # Comisión sobre flujo
        comfi = self._line(slip, 'COMFI')
        self.assertTrue(comfi, 'Sin línea COMFI')
        expected_com = round(wage * self.afp.fixed_commision / 100, 2)
        self.assertAlmostEqual(abs(comfi.total), expected_com, places=1)
        # EsSalud 9 % del afecto (aporte del empleador)
        essalud = self._line(slip, 'ESSALUD')
        self.assertTrue(essalud, 'Sin línea ESSALUD')
        self.assertAlmostEqual(
            abs(essalud.total), round(wage * 0.09, 2), places=1)
        # Totales PLAME por categoría
        self.assertGreater(slip.worker_contributions, 0)
        self.assertGreater(slip.employer_contributions, 0)
        # Neto = total ingresos − aportes trabajador − descuentos al neto
        neto = self._line(slip, 'NETO')
        if neto:
            ing = sum(slip.line_ids.filtered(
                lambda l: l.category_id == self.env.ref('al_hr_pe.ING')
            ).mapped('total'))
            self.assertAlmostEqual(
                neto.total,
                ing - slip.worker_contributions - slip.net_discounts,
                places=1)

    def test_plame_rem_export(self):
        slip = self._compute_slip()
        self.employee.write({
            'l10n_latam_identification_type_id':
                self.env.ref('l10n_pe.it_DNI').id,
            'identification_id': '44556677',
        })
        run = self.env['hr.payslip.run'].create({
            'name': 'Lote PE 2026-03',
            'date_start': date(2026, 3, 1),
            'date_end': date(2026, 3, 31),
            'company_id': self.company.id,
        })
        slip.payslip_run_id = run
        action = run.export_plame()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'hr.payslip.run'), ('res_id', '=', run.id),
        ], order='id desc', limit=1)
        self.assertTrue(attachment)
        self.assertTrue(attachment.name.endswith('.rem'))

    # ------------------------------------------------------------------
    # Correcciones de la auditoría (27/09/2026)
    # ------------------------------------------------------------------
    def _attachment_text(self, action):
        attachment_id = int(action['url'].split('/')[3].split('?')[0])
        attachment = self.env['ir.attachment'].browse(attachment_id)
        return base64.b64decode(attachment.datas).decode('utf-8')

    def _set_dni(self):
        self.employee.write({
            'l10n_latam_identification_type_id':
                self.env.ref('l10n_pe.it_DNI').id,
            'identification_id': '44556677',
        })

    def test_contributions_by_flag_not_by_name(self):
        """Renombrar la AFP no deja el aporte en cero: se decide por
        is_afp y las tasas, no por el nombre de la entidad."""
        self.afp.name = 'Mi AFP renombrada'
        slip = self._compute_slip()
        wage = 3000.0
        self.assertAlmostEqual(
            abs(self._line(slip, 'A_JUB').total),
            round(wage * self.afp.retirement_fund / 100, 2), places=1)
        self.assertAlmostEqual(
            abs(self._line(slip, 'COMFI').total),
            round(wage * self.afp.fixed_commision / 100, 2), places=1)
        self.assertTrue(self._line(slip, 'SEGI').total)
        self.assertFalse(self._line(slip, 'ONP').total)
        # ONP renombrada: sigue aportando al SNP y nada a la AFP.
        onp = self.env.ref('al_hr_pe.membership_ONP')
        onp.name = 'Sistema Nacional'
        self.employee.version_id.membership_id = onp
        slip = self._compute_slip()
        self.assertAlmostEqual(
            abs(self._line(slip, 'ONP').total),
            round(wage * onp.retirement_fund / 100, 2), places=1)
        self.assertFalse(self._line(slip, 'A_JUB').total)
        self.assertFalse(self._line(slip, 'SEGI').total)

    def test_practicante_no_family_allowance(self):
        """Ley 25129: el practicante no cobra asignación familiar."""
        slip = self._compute_slip()
        slip.l10n_pe_family_allowance_ok = True
        slip.compute_sheet()
        self.assertAlmostEqual(self._line(slip, 'AF').total, 113.0)
        self.employee.version_id.l10n_pe_labor_regime = 'practicante'
        slip.compute_sheet()
        self.assertFalse(self._line(slip, 'AF').total)
        self.assertFalse(self._line(slip, 'ESSALUD').total)

    def test_worked_holiday_pays_double(self):
        """Feriado o descanso laborado: la labor se paga con sobretasa del
        100 % (D.Leg. 713 arts. 3-4 y 9) además del básico completo."""
        slip = self._compute_slip()
        fer = slip.worked_days_line_ids.filtered(lambda l: l.code == 'FER')
        fer.number_of_days = 1.0
        slip.compute_sheet()
        self.assertAlmostEqual(self._line(slip, 'FER').total, 3000.0 / 30 * 2)
        self.assertAlmostEqual(self._line(slip, 'BAS').total, 3000.0, places=1)

    def test_dom_ignores_extra_hours(self):
        """Las horas extra no restan días de descanso al completar DOM."""
        slip = self.env['hr.payslip'].new({
            'employee_id': self.employee.id,
            'version_id': self.employee.version_id.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 3, 1),
            'date_to': date(2026, 3, 31),
        })
        dlab = self.env.ref('al_hr_pe.wd_DLAB')
        he25 = self.env.ref('al_hr_pe.wd_HE25')
        self.assertTrue(he25.is_extra_hours)
        values = [
            {'sequence': 1, 'work_entry_type_id': dlab.id,
             'number_of_days': 22.0, 'number_of_hours': 176.0},
            {'sequence': 25, 'work_entry_type_id': he25.id,
             'number_of_days': 1.0, 'number_of_hours': 8.0},
        ]
        with patch.object(type(self.env['hr.payslip']),
                          '_get_worked_day_lines_values',
                          lambda self, domain=None: [dict(v) for v in values]):
            lines = slip._get_worked_day_lines(check_out_of_version=False)
        dom = self.env.ref('al_hr_pe.wd_DOM')
        dom_days = sum(v['number_of_days'] for v in lines
                       if v['work_entry_type_id'] == dom.id)
        self.assertEqual(dom_days, 31 - 22, 'las 8 h extra no son un día')

    def test_family_allowance_snapshot_on_closed_slip(self):
        """Cargar un hijo después no reescribe una boleta ya cerrada."""
        slip = self._compute_slip()
        self.assertFalse(slip.l10n_pe_family_allowance_ok)
        slip.state = 'validated'
        self.env['l10n_pe.hr.dependent'].create({
            'employee_id': self.employee.id,
            'type_id': self.env.ref('al_hr_pe.dependent_type_05').id,
            'last_name': 'Quispe', 'm_last_name': 'Rojas', 'names': 'Luz',
            'l10n_latam_identification_type_id':
                self.env.ref('l10n_pe.it_DNI').id,
            'identification_id': '71234599',
            'birthday': date(2020, 5, 5),
            'date_start': date(2020, 5, 5),
        })
        slip.invalidate_recordset(['l10n_pe_family_allowance_ok'])
        self.assertFalse(slip.l10n_pe_family_allowance_ok,
                         'la boleta cerrada conserva su snapshot')
        draft = self._compute_slip()
        self.assertTrue(draft.l10n_pe_family_allowance_ok)

    def test_rem_sin_regimen_has_no_afp_commission(self):
        """«SIN RÉGIMEN» no es AFP: no se declara el concepto 0601."""
        self._set_dni()
        self.employee.version_id.membership_id = self.env.ref(
            'al_hr_pe.membership_SIN_REGIMEN')
        slip = self._compute_slip()
        run = self.env['hr.payslip.run'].create({
            'name': 'Lote PE sin régimen',
            'date_start': date(2026, 3, 1),
            'date_end': date(2026, 3, 31),
            'company_id': self.company.id,
        })
        slip.payslip_run_id = run
        content = self._attachment_text(run.export_plame())
        self.assertNotIn('|0601|', content)
        self.assertIn('|0121|', content)

    def test_plame_weekly_lot_declares_the_month(self):
        """Un lote semanal declara el mes entero, una línea por concepto."""
        self._set_dni()
        Period = self.env['hr.period']
        month = Period.create({
            'code': '202603', 'name': 'Marzo 2026',
            'date_start': date(2026, 3, 1), 'date_end': date(2026, 3, 31),
            'company_id': self.company.id,
        })
        weeks = Period.create([{
            'code': '202603-S%02d' % index, 'name': 'Semana %d' % index,
            'date_start': start, 'date_end': end, 'period_type': 'weekly',
            'parent_id': month.id, 'company_id': self.company.id,
        } for index, (start, end) in enumerate([
            (date(2026, 3, 2), date(2026, 3, 8)),
            (date(2026, 3, 9), date(2026, 3, 15))], start=1)])
        slips = self.env['hr.payslip']
        runs = self.env['hr.payslip.run']
        for week in weeks:
            run = self.env['hr.payslip.run'].create({
                'name': week.name, 'date_start': week.date_start,
                'date_end': week.date_end, 'periodo_id': week.id,
                'company_id': self.company.id,
            })
            slip = self.env['hr.payslip'].create({
                'name': week.name, 'employee_id': self.employee.id,
                'struct_id': self.structure.id,
                'date_from': week.date_start, 'date_to': week.date_end,
                'payslip_run_id': run.id,
            })
            slip.compute_sheet()
            slip.state = 'validated'
            self.assertEqual(slip.periodo_id, week)
            slips |= slip
            runs |= run
        self.assertEqual(runs[0].l10n_pe_plame_period_id, month)
        self.assertEqual(runs[0]._l10n_pe_plame_slips(), slips)
        content = self._attachment_text(runs[0].export_plame())
        bas = [line for line in content.split('\r\n') if '|0121|' in line]
        self.assertEqual(len(bas), 1, 'una sola línea por concepto')
        expected = sum(slips.line_ids.filtered(
            lambda l: l.code == 'BAS').mapped('total'))
        self.assertIn('|%.2f|' % expected, bas[0])

# -*- coding: utf-8 -*-
"""Correcciones de la auditoría de construcción civil (27/09/2026).

Cada prueba fija un fallo concreto que la auditoría encontró:

* la tabla propia de la compañía no ganaba nunca a la global;
* el feriado no laborado no pagaba el jornal;
* la movilidad se pagaba en días sin ir a la obra;
* el snapshot de una boleta confirmada cambiaba con la versión;
* el resumen CONAFOVICER recalculaba con la tasa del día;
* el detalle CONAFOVICER no tenía regla multicompañía;
* la descarga de la tabla aceptaba cualquier dirección (SSRF);
* las reglas de pensión redondeaban con ``round()``;
* los códigos globales se podían duplicar.
"""
from datetime import date, datetime, timedelta

from psycopg2 import IntegrityError

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestConstructionAuditFixes(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create(
            {'name': 'Auditoría Obras S.A.C.', 'vat': '20512528458'})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))
        cls.structure = cls.env.ref(
            'al_hr_pe_construction.construction_structure')
        cls.wd_dlab = cls.env.ref('al_hr_pe.wd_DLAB')
        cls.wd_dom = cls.env.ref('al_hr_pe.wd_DOM')
        cls.wd_dmed = cls.env.ref('al_hr_pe.wd_DMED')
        cls.dni = cls.env.ref('l10n_pe.it_DNI')
        cls.operario = cls.env.ref('al_hr_pe_construction.category_operario')
        cls.peon = cls.env.ref('al_hr_pe_construction.category_peon')
        cls.Table = cls.env['l10n_pe.hr.construction.wage.table']
        # Horario propio en hora de Lima (lunes a viernes, el de Odoo por
        # defecto): así el feriado de la prueba cae en día laborable.
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'Obra Lima', 'tz': 'America/Lima',
            'company_id': cls.company.id})

    def _worker(self, seq, category=None):
        employee = self.env['hr.employee'].create({
            'name': 'Obrero Auditoría %d' % seq,
            'company_id': self.company.id,
            'identification_id': '4700000%d' % seq,
            'l10n_latam_identification_type_id': self.dni.id})
        employee.version_id.write({
            'contract_date_start': date(2026, 1, 1),
            'resource_calendar_id': self.calendar.id,
            'l10n_pe_labor_regime': 'construccion',
            'l10n_pe_construction_category_id': (category or self.operario).id,
        })
        return employee

    def _payslip(self, employee, worked, date_from=date(2026, 3, 2),
                 date_to=date(2026, 3, 8)):
        """Boleta semanal con los días trabajados dados: {tipo: días}."""
        payslip = self.env['hr.payslip'].create({
            'name': 'Semana %s' % date_from,
            'employee_id': employee.id,
            'company_id': self.company.id,
            'struct_id': self.structure.id,
            'date_from': date_from, 'date_to': date_to,
        })
        payslip.worked_days_line_ids.unlink()
        payslip.worked_days_line_ids = [Command.create({
            'name': work_entry_type.name,
            'work_entry_type_id': work_entry_type.id,
            'number_of_days': days, 'number_of_hours': days * 8,
            'amount': 0.0,
        }) for work_entry_type, days in worked.items()]
        payslip.compute_sheet()
        return payslip

    @staticmethod
    def _line(payslip, code):
        line = payslip.line_ids.filtered(lambda l: l.code == code)
        return round(sum(line.mapped('total')), 2)

    def _holiday(self, day):
        """Feriado global del horario, como lo deja al_hr_pe_public_holidays:
        de 00:00 a 23:59:59 en Lima (UTC−5), con el concepto DOM."""
        date_from = datetime(day.year, day.month, day.day, 5, 0, 0)
        date_to = date_from + timedelta(hours=23, minutes=59, seconds=59)
        leave = self.env['resource.calendar.leaves'].create({
            'name': 'Feriado de prueba',
            'calendar_id': self.calendar.id,
            'company_id': self.company.id,
            'date_from': date_from,
            'date_to': date_to,
            'work_entry_type_id': self.wd_dom.id,
        })
        # hr_holidays reinterpreta las fechas del create en el huso del
        # usuario; el write las deja tal cual (mismo truco que el módulo
        # de feriados).
        leave.write({'date_from': date_from, 'date_to': date_to})
        return leave

    # ------------------------------------------------------------------
    # Tabla propia frente a la global
    # ------------------------------------------------------------------
    def test_company_table_overrides_the_global_one(self):
        """La tabla propia se solapa con la global y la sustituye."""
        global_table = self.env.ref('al_hr_pe_construction.wage_table_2026')
        own = self.Table.create({
            'name': 'Convenio de obra 2026',
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 12, 31),
            'company_id': self.company.id,
            'line_ids': [Command.create({
                'category_id': self.operario.id, 'daily_wage': 95.0,
                'mobility_amount': 9.0})],
        })
        self.assertEqual(
            self.Table._get_table_for_date(date(2026, 3, 1), self.company),
            own, 'la propia de la compañía manda sobre la global')
        other = self.env['res.company'].create({'name': 'Otra obra S.A.C.'})
        self.assertEqual(
            self.Table._get_table_for_date(date(2026, 3, 1), other),
            global_table, 'otra compañía sigue con la global')
        worker = self._worker(1)
        self.assertAlmostEqual(worker.version_id.l10n_pe_daily_wage, 95.0,
                               places=2)

    # ------------------------------------------------------------------
    # Feriado no laborado y movilidad
    # ------------------------------------------------------------------
    def test_unworked_holiday_pays_the_wage_but_not_mobility(self):
        """Semana con feriado el miércoles 4: 4 días + feriado = 5 pagados.

        Horario de lunes a viernes: el feriado llega como descanso (DOM)
        junto con el sábado y el domingo. Se paga el jornal del feriado
        (D.Leg. 713, descanso remunerado), no la movilidad.
        """
        worker = self._worker(2)
        without = self._payslip(worker, {self.wd_dlab: 4, self.wd_dom: 3})
        self.assertEqual(self._line(without, 'JOR'), round(89.30 * 4, 2),
                         'sin descanso de feriado en el horario no hay nada '
                         'que pagar aparte')
        self._holiday(date(2026, 3, 4))
        payslip = self._payslip(worker, {self.wd_dlab: 4, self.wd_dom: 3})
        self.assertEqual(payslip._l10n_pe_construction_holiday_days(), 1.0)
        self.assertEqual(self._line(payslip, 'JOR'), round(89.30 * 5, 2))
        self.assertEqual(self._line(payslip, 'MOV'), round(8.60 * 4, 2),
                         'la movilidad solo va con los días en obra')

    def test_worked_holiday_pays_rest_labour_and_surcharge(self):
        """Feriado trabajado (D.Leg. 713 art. 9): descanso + labor + 100 %.

        El tareaje deja el día como descanso (DOM) y como labor en feriado
        (FER) a la vez. Se paga el feriado como descanso remunerado, el
        jornal del día trabajado y la sobretasa del 100 % sobre el jornal,
        sin contar el día dos veces más.
        """
        worker = self._worker(8)
        wd_fer = self.env.ref('al_hr_pe.wd_FER')
        self._holiday(date(2026, 3, 4))
        payslip = self._payslip(
            worker, {self.wd_dlab: 4, wd_fer: 1, self.wd_dom: 3})
        self.assertEqual(self._line(payslip, 'JOR'), round(89.30 * 6, 2),
                         '4 días + el feriado trabajado + el feriado '
                         'como descanso remunerado')
        self.assertEqual(self._line(payslip, 'FER100'), 89.30)
        self.assertEqual(self._line(payslip, 'MOV'), round(8.60 * 5, 2))
        self.assertEqual(
            round(self._line(payslip, 'TREM') - (
                self._line(payslip, 'JOR') + self._line(payslip, 'DSO')
                + self._line(payslip, 'BUC')), 2),
            89.30, 'la sobretasa es remuneración afecta (entra en TREM)')

    def test_worked_holiday_does_not_inflate_the_dso(self):
        """El D.S.O. es un sexto de los días que generan descanso: el
        feriado trabajado (FER) se paga aparte y no suma otro sexto."""
        worker = self._worker(9)
        wd_fer = self.env.ref('al_hr_pe.wd_FER')
        self._holiday(date(2026, 3, 4))
        payslip = self._payslip(
            worker, {self.wd_dlab: 4, wd_fer: 1, self.wd_dom: 3})
        self.assertEqual(self._line(payslip, 'DSO'), round(89.30 * 5 / 6, 2))

    def test_holiday_outside_the_period_is_ignored(self):
        worker = self._worker(3)
        self._holiday(date(2026, 3, 11))
        payslip = self._payslip(worker, {self.wd_dlab: 5, self.wd_dom: 2})
        self.assertFalse(payslip._l10n_pe_construction_holiday_days())
        self.assertEqual(self._line(payslip, 'JOR'), round(89.30 * 5, 2))

    def test_mobility_excludes_medical_rest(self):
        """El descanso médico paga jornal, pero no hay traslado a la obra."""
        worker = self._worker(4)
        payslip = self._payslip(worker, {self.wd_dlab: 4, self.wd_dmed: 2})
        self.assertEqual(self._line(payslip, 'JOR'), round(89.30 * 6, 2))
        self.assertEqual(self._line(payslip, 'MOV'), round(8.60 * 4, 2))

    # ------------------------------------------------------------------
    # Snapshot de la boleta confirmada
    # ------------------------------------------------------------------
    def test_confirmed_payslip_keeps_its_wage_and_category(self):
        worker = self._worker(5)
        payslip = self._payslip(worker, {self.wd_dlab: 6})
        payslip.action_payslip_done()
        self.assertIn(payslip.state, ('validated', 'paid'))
        worker.version_id.l10n_pe_construction_category_id = self.peon
        self.env.flush_all()
        self.assertAlmostEqual(payslip.l10n_pe_daily_wage, 89.30, places=2)
        self.assertEqual(payslip.l10n_pe_construction_category_id,
                         self.operario)

    def test_draft_payslip_follows_the_version(self):
        worker = self._worker(6)
        payslip = self._payslip(worker, {self.wd_dlab: 6})
        worker.version_id.l10n_pe_construction_category_id = self.peon
        self.assertAlmostEqual(payslip.l10n_pe_daily_wage, 62.80, places=2)
        self.assertEqual(payslip.l10n_pe_construction_category_id, self.peon)

    # ------------------------------------------------------------------
    # CONAFOVICER
    # ------------------------------------------------------------------
    def _month(self, company):
        self.env['hr.period.generator'].create({
            'year': 2026, 'company_id': company.id,
            'generate_weekly': True}).action_generate()
        return self.env['hr.period'].search(
            [('code', '=', '202603'), ('company_id', '=', company.id)])

    def test_summary_uses_what_was_withheld(self):
        """Si la tasa cambia después, se deposita lo retenido, no otra cosa."""
        month = self._month(self.company)
        worker = self._worker(7)
        payslip = self._payslip(worker, {self.wd_dlab: 6})
        payslip.action_payslip_done()
        self.assertEqual(self._line(payslip, 'CONAF'), -12.50)
        self.company.l10n_pe_conafovicer_rate = 3.0
        summary = self.env['l10n_pe.hr.conafovicer'].create({
            'period_id': month.id, 'company_id': self.company.id})
        summary.action_compute()
        self.assertEqual(round(summary.amount_total, 2), 12.50)
        self.assertEqual(round(summary.amount_base, 2), 625.10)

    def test_paid_summary_reopens_only_for_the_manager(self):
        month = self._month(self.company)
        summary = self.env['l10n_pe.hr.conafovicer'].create({
            'period_id': month.id, 'company_id': self.company.id,
            'state': 'paid'})
        officer = self.env['res.users'].create({
            'name': 'Oficial de nómina', 'login': 'al_pe_constr_officer',
            'company_id': self.company.id,
            'company_ids': [Command.set(self.company.ids)],
            'group_ids': [Command.set([
                self.env.ref('base.group_user').id,
                self.env.ref('hr_payroll.group_hr_payroll_user').id])],
        })
        with self.assertRaises(UserError):
            summary.with_user(officer).action_draft()
        summary.action_draft()
        self.assertEqual(summary.state, 'draft')

    def test_conafovicer_lines_are_isolated_by_company(self):
        other = self.env['res.company'].create(
            {'name': 'Otra constructora S.A.C.'})
        self.env.user.company_ids = [(4, other.id)]
        other_env = self.env(context=dict(
            self.env.context, allowed_company_ids=other.ids))
        month = self._month(other)
        employee = other_env['hr.employee'].create({
            'name': 'Obrero ajeno', 'company_id': other.id})
        summary = other_env['l10n_pe.hr.conafovicer'].create({
            'period_id': month.id, 'company_id': other.id})
        other_env['l10n_pe.hr.conafovicer.line'].create({
            'summary_id': summary.id, 'employee_id': employee.id,
            'wage_amount': 100.0, 'dso_amount': 0.0, 'base': 100.0,
            'amount': 2.0})
        officer = self.env['res.users'].create({
            'name': 'Nómina A', 'login': 'al_pe_constr_company_a',
            'company_id': self.company.id,
            'company_ids': [Command.set(self.company.ids)],
            'group_ids': [Command.set([
                self.env.ref('base.group_user').id,
                self.env.ref('hr_payroll.group_hr_payroll_user').id])],
        })
        lines = self.env['l10n_pe.hr.conafovicer.line'].with_user(
            officer).with_context(allowed_company_ids=self.company.ids
                                  ).search([('company_id', '=', other.id)])
        self.assertFalse(lines, 'el detalle de otra compañía no se ve')

    # ------------------------------------------------------------------
    # Descarga de la tabla: sin SSRF
    # ------------------------------------------------------------------
    def test_download_only_from_allowed_https_hosts(self):
        check = self.Table._l10n_pe_check_url
        self.assertTrue(check(
            'https://www.capeco.org/descargas/CC2026/tabla.pdf'))
        self.assertTrue(check('https://www.gob.pe/tabla.pdf'))
        for url in ('http://www.capeco.org/tabla.pdf',
                    'https://127.0.0.1/tabla.pdf',
                    'https://169.254.169.254/latest/meta-data',
                    'https://capeco.org.evil.com/tabla.pdf',
                    'file:///etc/passwd',
                    'https://intranet.local/tabla.pdf'):
            with self.subTest(url=url), self.assertRaises(UserError):
                check(url)

    def test_admin_can_allow_another_host(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'al_hr_pe_construction.wage_table_hosts', 'sindicato.example.pe')
        self.assertTrue(self.Table._l10n_pe_check_url(
            'https://descargas.sindicato.example.pe/tabla.pdf'))

    # ------------------------------------------------------------------
    # Redondeo de pensiones y códigos globales únicos
    # ------------------------------------------------------------------
    def test_pension_rounding_is_half_up(self):
        """10 % de 103.85 = 10.385 → 10.39 (round() de Python da 10.38)."""
        payslip = self.env['hr.payslip']
        self.assertEqual(payslip._l10n_pe_percent(103.85, 10.0), 10.39)
        self.assertEqual(payslip._l10n_pe_percent(796.56, 13.0), 103.55,
                         'el ONP oficial del operario')

    def test_onp_rule_uses_the_sunat_rounding(self):
        onp = self.env.ref('al_hr_pe_construction.rule_ONP')
        self.assertIn('_l10n_pe_percent', onp.amount_python_compute)
        self.assertNotIn('round(', onp.amount_python_compute)

    def test_global_category_code_is_unique(self):
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError), \
                self.cr.savepoint():
            self.env['l10n_pe.hr.construction.category'].create({
                'name': 'Operario duplicado', 'code': 'OPE',
                'buc_percent': 32.0})
            self.env.flush_all()

    def test_sunat_codes_match_the_base_structure(self):
        """Los conceptos que existen en BASE usan su mismo código SUNAT."""
        # La «indemnización» del convenio (15 %) es la CTS del régimen:
        # 0904, no el 0501 de la indemnización por despido de BASE.
        self.assertEqual(
            self.env.ref('al_hr_pe_construction.rule_INDEM').sunat_code,
            '0904')
        pairs = (('rule_BEXT', 'BONI_EX'), ('rule_VAC10', 'VAC'))
        base_rules = self.env.ref('al_hr_pe.base_structure').rule_ids
        for xmlid, base_code in pairs:
            with self.subTest(regla=xmlid):
                rule = self.env.ref('al_hr_pe_construction.%s' % xmlid)
                base = base_rules.filtered(lambda r: r.code == base_code)
                self.assertEqual(rule.sunat_code, base.sunat_code)

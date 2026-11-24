# -*- coding: utf-8 -*-
"""CREVAL, paquete 8: correcciones de la carga de un presupuesto completo.

CR-66 orden de venta del contrato al confirmar; CR-67 fechas de PLAN en el
horario y la zona horaria de la obra; CR-68 etapas y títulos con las fechas
de PLAN; CR-70 nombres de la plantilla de niveles; CR-71 «Asignar contrata»
desde el menú y casilla «Toda la obra». Datos ficticios."""
from datetime import date, datetime

from odoo import Command
from odoo.tests import Form, HttpCase, new_test_user, tagged

from .test_budget_book_creval import TestBudgetBook


@tagged('post_install', '-at_install')
class TestCrevalPackage8(TestBudgetBook):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.partner_id.tz = 'America/Lima'
        cls.company.construction_site_calendar_id = False
        cls.seller = new_test_user(
            cls.env, 'ventas_p8', name='Comercial (test paquete 8)',
            groups='sales_team.group_sale_salesman_all_leads')
        grp = 'al_construction_planner.group_planner_'
        cls.planner = new_test_user(
            cls.env, 'planificador_p8', name='Planificador (test paquete 8)',
            groups=f'{grp}planner,{grp}amounts')
        cls.Stage = cls.env['construction.space.stage']

    # ------------------------------------------------------------------
    # Ayudas
    # ------------------------------------------------------------------
    def _plan_dates(self, start, end):
        def edit(book):
            sheet = book['PLAN']
            sheet.cell(row=2, column=5, value=start)
            sheet.cell(row=2, column=6, value=end)
        return edit

    def _send_plan(self, start='2026-07-13', end='2026-07-26', user=None):
        if user:
            # Los insumos del libro los crea quien arma el presupuesto; el
            # planificador envía el plan con el maestro ya cargado.
            self._send(self._book()).action_import()
        wizard = self._send(self._edited_book(self._plan_dates(start, end)), target='plan')
        if user:
            wizard = wizard.with_user(user)
        wizard.action_import()
        plan = self.env['construction.resource.plan'].search(
            [('project_id', '=', self.project.id)], order='id desc', limit=1)
        return plan

    def _task(self, item):
        line = self.order.order_line.filtered(lambda l: l.construction_budget_item == item)
        return self.env['project.task'].search([('sale_line_id', '=', line.id)])

    # ------------------------------------------------------------------
    # CR-66
    # ------------------------------------------------------------------
    def test_cr66_confirm_links_the_contract_order(self):
        self._send(self._book()).action_import()
        self.assertFalse(self.project.construction_sale_order_id)
        self.order.with_user(self.seller).action_confirm()
        self.assertEqual(self.project.construction_sale_order_id, self.order)
        # El historial se escribe al cerrar la transacción.
        self.env.cr.precommit.run()
        tracking = self.env['mail.tracking.value'].search([
            ('mail_message_id.model', '=', 'project.project'),
            ('mail_message_id.res_id', '=', self.project.id),
            ('field_id.name', '=', 'construction_sale_order_id')])
        self.assertEqual(len(tracking), 1)
        message = tracking.mail_message_id
        self.assertEqual(message.author_id, self.seller.partner_id)
        self.assertIn(self.order.name, message.body)
        # El contrato de obra en borrador (CR-44) sigue naciendo, uno solo.
        self.assertEqual(self.env['construction.contract'].search_count(
            [('project_id', '=', self.project.id)]), 1)

    def test_cr66_current_order_is_not_replaced(self):
        self._send(self._book()).action_import()
        self.order.action_confirm()
        second = self.order.copy({'project_id': self.project.id})
        second.with_user(self.seller).action_confirm()
        self.assertEqual(self.project.construction_sale_order_id, self.order)
        notice = second.message_ids.filtered(lambda m: self.order.name in (m.body or ''))
        self.assertTrue(notice)
        self.assertIn('Calendario e ingresos', notice[0].body)

    def test_cr66_other_orders_do_not_change(self):
        plain = self.env['project.project'].create({'name': 'Proyecto que no es obra (test)'})
        order = self.env['sale.order'].create({
            'partner_id': self.customer.id, 'project_id': plain.id})
        order.action_confirm()
        self.assertFalse(plain.construction_sale_order_id)
        no_project = self.env['sale.order'].create({'partner_id': self.customer.id})
        no_project.action_confirm()
        self.assertEqual(no_project.state, 'sale')

    # ------------------------------------------------------------------
    # CR-67
    # ------------------------------------------------------------------
    def test_cr67_site_hours_in_the_company_timezone(self):
        company = self.company
        monday = date(2026, 7, 13)
        # Sin horario de obra: 08:00 y 17:00 de Lima (UTC−5).
        self.assertEqual(company._construction_site_datetime(monday),
                         datetime(2026, 7, 13, 13, 0))
        self.assertEqual(company._construction_site_datetime(monday, end=True),
                         datetime(2026, 7, 13, 22, 0))
        self.assertEqual(company._construction_site_date(datetime(2026, 7, 13, 13, 0)), monday)
        # A las 00:00 UTC, en Lima todavía es el día anterior.
        self.assertEqual(company._construction_site_date(datetime(2026, 7, 13, 0, 0)),
                         date(2026, 7, 12))
        company.partner_id.tz = 'America/Bogota'
        self.assertEqual(company._construction_site_date(
            company._construction_site_datetime(monday)), monday)
        # Una zona al este de UTC da el mismo día.
        company.partner_id.tz = 'Asia/Tokyo'
        self.assertEqual(company._construction_site_datetime(monday),
                         datetime(2026, 7, 12, 23, 0))
        self.assertEqual(company._construction_site_date(datetime(2026, 7, 12, 23, 0)), monday)
        # Sin zona en la compañía, la del usuario.
        company.partner_id.tz = False
        self.env.user.tz = 'America/Lima'
        self.assertEqual(company._construction_site_datetime(monday),
                         datetime(2026, 7, 13, 13, 0))

    def test_cr67_site_calendar_gives_the_hours(self):
        calendar = self.env['resource.calendar'].create({
            'name': 'Horario de obra (test paquete 8)', 'company_id': self.company.id,
            'tz': 'America/Lima', 'attendance_ids': [Command.clear()] + [
                Command.create({'name': 'Obra', 'dayofweek': str(day), 'hour_from': 7.5,
                                'hour_to': 16.5, 'day_period': 'morning'})
                for day in range(5)]})
        self.company.construction_site_calendar_id = calendar
        monday = date(2026, 7, 13)
        self.assertEqual(self.company._construction_site_datetime(monday),
                         datetime(2026, 7, 13, 12, 30))
        self.assertEqual(self.company._construction_site_datetime(monday, end=True),
                         datetime(2026, 7, 13, 21, 30))
        # Domingo, sin horario: 08:00 y 17:00.
        self.assertEqual(self.company._construction_site_datetime(date(2026, 7, 26), end=True),
                         datetime(2026, 7, 26, 22, 0))

    def test_cr67_plan_dates_reach_the_task_on_the_same_day(self):
        self._send_plan(user=self.planner)
        task = self._task('01.02')
        start_field, end_field = self.Stage._task_date_fields()
        self.assertTrue(end_field)
        self.assertEqual(self.company._construction_site_date(task[end_field]),
                         date(2026, 7, 26))
        if self.env['project.task']._fields[end_field].type == 'datetime':
            self.assertEqual(task[end_field], datetime(2026, 7, 26, 22, 0))
        if start_field:
            self.assertEqual(self.company._construction_site_date(task[start_field]),
                             date(2026, 7, 13))
            if self.env['project.task']._fields[start_field].type == 'datetime':
                self.assertEqual(task[start_field], datetime(2026, 7, 13, 13, 0))
                # «Tareas del día» del portal: el día de la obra.
                low, high = self.company._construction_site_day_bounds(date(2026, 7, 13))
                self.assertTrue(low <= task[start_field] < high)

    # ------------------------------------------------------------------
    # CR-68
    # ------------------------------------------------------------------
    def test_cr68_stages_and_titles_follow_plan(self):
        plan = self._send_plan(user=self.planner)
        task = self._task('01.02')
        other = self._task('01.01')
        stages = task.construction_stage_ids
        self.assertTrue(stages)
        self.assertEqual(min(stages.mapped('date_start')), date(2026, 7, 13))
        self.assertEqual(max(stages.mapped('date_end')), date(2026, 7, 26))
        # La partida sin fechas en PLAN conserva las propuestas y cuenta para
        # su título.
        proposed = other.construction_stage_ids
        self.assertTrue(proposed)
        start_field, end_field = self.Stage._task_date_fields()
        title = task.parent_id
        self.assertTrue(title.construction_level)
        starts = (stages | proposed).mapped('date_start')
        ends = (stages | proposed).mapped('date_end')
        if start_field:
            self.assertEqual(self.company._construction_site_date(title[start_field]),
                             min(starts))
        self.assertEqual(self.company._construction_site_date(title[end_field]), max(ends))
        titles = 0
        node = title
        while node:
            titles += 1
            node = node.parent_id.filtered('construction_level')
        self.assertTrue(plan.message_ids.filtered(
            lambda m: 'Fechas de la pestaña PLAN aplicadas: 1 partidas, %s títulos' % titles
            in (m.body or '')))
        # Corregir PLAN y volver a enviar recalcula.
        self._send_plan('2026-07-20', '2026-08-17')
        stages = task.construction_stage_ids
        self.assertEqual(min(stages.mapped('date_start')), date(2026, 7, 20))
        self.assertEqual(max(stages.mapped('date_end')), date(2026, 8, 17))

    def test_cr68_stages_share_the_site_days(self):
        self._send_plan()
        task = self._task('01.02')
        second = self.env['construction.stage'].create({
            'name': 'Acabado (test paquete 8)', 'code': 'book_test_stage_2', 'sequence': 940})
        first = task.construction_stage_ids
        self.Stage.create({'space_task_id': task.id, 'stage': second.code,
                           'date_start': '2026-09-01', 'date_end': '2026-09-05'})
        # 7 al 18 de setiembre (sin feriados): diez días hábiles, cinco por
        # etapa.
        moved = self.Stage._fit_to_dates({task: (date(2026, 9, 7), date(2026, 9, 18))})
        self.assertEqual(len(moved), 2)
        last = task.construction_stage_ids - first
        self.assertEqual((first.date_start, first.date_end),
                         (date(2026, 9, 7), date(2026, 9, 11)))
        self.assertEqual((last.date_start, last.date_end),
                         (date(2026, 9, 14), date(2026, 9, 18)))
        # Un plazo de un día: las dos etapas en ese día.
        self.Stage._fit_to_dates({task: (date(2026, 7, 13), date(2026, 7, 13))})
        self.assertEqual(set(task.construction_stage_ids.mapped('date_start')),
                         {date(2026, 7, 13)})
        self.assertEqual(set(task.construction_stage_ids.mapped('date_end')),
                         {date(2026, 7, 13)})

    # ------------------------------------------------------------------
    # CR-70
    # ------------------------------------------------------------------
    def test_cr70_schedule_stages_use_the_template_names(self):
        Stage = self.Stage.with_user(self.planner).with_context(
            construction_project_id=self.project.id)
        names = Stage.fields_get(['floor_task_id', 'space_task_id', 'apartment_task_id'],
                                 ['string'])
        self.assertEqual(names['floor_task_id']['string'], 'Sub-especialidad')
        self.assertEqual(names['space_task_id']['string'], 'Partida')
        from lxml import etree
        arch = etree.fromstring(Stage.get_view(view_type='list')['arch'])
        apartment = arch.xpath("//field[@name='apartment_task_id']")[0]
        self.assertEqual(apartment.get('column_invisible'), '1')
        self.assertNotEqual(arch.xpath("//field[@name='floor_task_id']")[0]
                            .get('column_invisible'), '1')

    def test_cr70_task_level_shows_the_template_name(self):
        self._send_plan()
        task = self._task('01.02')
        self.assertEqual(task.construction_level, 'space')
        self.assertEqual(task.with_user(self.planner).construction_level_label, 'Partida')
        task.construction_level_line_id.name = 'Partida (N3)'
        task.invalidate_recordset()
        self.assertEqual(task.construction_level_label, 'Partida')

    def test_cr70_request_wizard_groups_by_template_levels(self):
        plan = self._send_plan()
        plan.action_request_approval()
        self.assertEqual(plan.state, 'approved')
        Wizard = self.env['construction.plan.request.wizard'].with_user(
            self.planner).with_context(default_plan_id=plan.id)
        selection = Wizard.fields_get(['group_by'])['group_by']['selection']
        self.assertEqual(selection, [('space', 'Partida'), ('floor', 'Sub-especialidad')])
        wizard = Wizard.create({})
        self.assertEqual(wizard.group_by, 'floor')
        self.assertEqual(wizard.group_by_functions.split(), ['space', 'floor'])
        names = self.env['construction.plan.request.wizard.line'].with_context(
            default_plan_id=plan.id).fields_get(
            ['space_task_id', 'floor_task_id'], ['string'])
        self.assertEqual(names['space_task_id']['string'], 'Partida')
        self.assertEqual(names['floor_task_id']['string'], 'Sub-especialidad')
        # Sin plantilla (ni de la obra ni de la compañía), los nombres del
        # planificador.
        self.company.construction_level_template_id = False
        plain = self.env['construction.plan.request.wizard'].with_context(
            default_plan_id=False).fields_get(['group_by'])['group_by']['selection']
        self.assertEqual(plain, [('space', 'Ambiente'), ('apartment', 'Departamento'),
                                 ('floor', 'Piso')])

    # ------------------------------------------------------------------
    # CR-71
    # ------------------------------------------------------------------
    def test_cr71_plan_list_from_the_menu(self):
        plan = self._send_plan()
        plan.action_request_approval()
        Wizard = self.env['construction.plan.contract.wizard'].with_user(self.planner)
        wizard = Wizard.new({})
        # Sin plan, la compañía activa: el dominio de compañía del campo
        # «Plan» ya no queda en «ninguna».
        self.assertEqual(wizard.company_id, self.company)
        Plan = self.env['construction.resource.plan'].with_user(self.planner)
        domain = [('state', 'in', ('approved', 'in_progress')),
                  ('company_id', 'in', [wizard.company_id.id])]
        self.assertIn(plan.id, [res[0] for res in Plan.name_search('', domain)])
        wizard.plan_id = plan
        self.assertEqual(wizard.company_id, plan.company_id)

    def test_cr71_whole_project_follows_the_selection(self):
        plan = self._send_plan()
        plan.action_request_approval()
        task = self._task('01.02')
        Wizard = self.env['construction.plan.request.wizard'].with_user(
            self.planner).with_context(default_plan_id=plan.id)
        with Form(Wizard) as form:
            self.assertTrue(form.whole_project)
            form.task_ids.add(task)
            self.assertFalse(form.whole_project)
            form.task_ids.clear()
            self.assertTrue(form.whole_project)
            # Marcar «Toda la obra» con partidas elegidas las quita.
            form.task_ids.add(task)
            form.whole_project = True
            self.assertFalse(form.task_ids)
        # Desde el cronograma con partidas marcadas, como antes.
        wizard = Wizard.with_context(construction_selection_task_ids=task.ids).create({})
        self.assertFalse(wizard.whole_project)
        self.assertEqual(wizard.task_ids, task)
        self.assertEqual(wizard.line_ids.plan_line_ids.task_id, task)
        whole = Wizard.create({})
        self.assertTrue(whole.whole_project)
        self.assertGreater(sum(whole.line_ids.mapped('qty_planned')),
                           sum(wizard.line_ids.mapped('qty_planned')))


@tagged('post_install', '-at_install')
class TestCrevalPackage8Tours(TestBudgetBook, HttpCase):
    """Recorridos de pantalla con usuarios sin permisos de administrador."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.partner_id.tz = 'America/Lima'
        cls.company.construction_site_calendar_id = False
        # Las listas que mezclan obras usan la plantilla de la compañía.
        cls.company.construction_level_template_id = cls.project.construction_level_template_id
        cls.seller = new_test_user(
            cls.env, 'ventas_p8_tour', name='Comercial (test paquete 8)',
            groups='sales_team.group_sale_salesman_all_leads', tz='America/Lima')
        grp = 'al_construction_planner.group_planner_'
        cls.planner = new_test_user(
            cls.env, 'planificador_p8_tour', name='Planificador (test paquete 8)',
            groups=f'{grp}planner,{grp}amounts,project.group_project_user',
            tz='America/Lima')
        for user in cls.seller | cls.planner:
            user.write({'company_ids': [Command.link(cls.company.id)],
                        'company_id': cls.company.id})

    def _plan(self):
        def edit(book):
            sheet = book['PLAN']
            sheet.cell(row=2, column=5, value='2026-07-13')
            sheet.cell(row=2, column=6, value='2026-07-26')
        self._send(self._edited_book(edit), target='plan').action_import()
        plan = self.env['construction.resource.plan'].search(
            [('project_id', '=', self.project.id)], order='id desc', limit=1)
        plan.action_request_approval()
        self.assertEqual(plan.state, 'approved')
        plan.name = 'PLR-P8'
        return plan

    def test_cr66_tour_confirm_and_contract_order(self):
        self._send(self._book()).action_import()
        self.start_tour('/odoo/action-sale.action_quotations/%s' % self.order.id,
                        'al_construction_package8_confirm', login='ventas_p8_tour')
        self.assertEqual(self.project.construction_sale_order_id, self.order)
        self.start_tour(
            '/odoo/action-al_construction_planner.action_planner_construction_sites/%s'
            % self.project.id, 'al_construction_package8_contract_order',
            login='planificador_p8_tour')

    def test_cr67_cr68_cr70_tour_schedule(self):
        self._plan()
        self.start_tour('/odoo', 'al_construction_package8_schedule',
                        login='planificador_p8_tour')

    def test_cr70_tour_request_wizard(self):
        self._plan()
        self.start_tour('/odoo', 'al_construction_package8_request_wizard',
                        login='planificador_p8_tour')

    def test_cr71_tour_contract_wizard_from_the_menu(self):
        self._plan()
        self.start_tour('/odoo', 'al_construction_package8_contract_wizard',
                        login='planificador_p8_tour')

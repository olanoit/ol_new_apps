# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import ConstructionRequestCommon

REPORT = 'al_construction_material_request.action_report_construction_request'


@tagged('post_install', '-at_install')
class TestReport(ConstructionRequestCommon):

    def _render(self, request, user=None):
        Report = self.env['ir.actions.report']
        if user:
            Report = Report.with_user(user)
        html, _ = Report._render_qweb_html(REPORT, request.ids)
        return html.decode()

    def test_vale_draft_shows_availability(self):
        plan = self.env['account.analytic.plan'].create({'name': 'Partida (test)'})
        account = self.env['account.analytic.account'].create(
            {'name': '02.01 Concreto (test)', 'plan_id': plan.id})
        self._set_stock(self.cement, self.stock, 60)
        request = self._new_request(user=self.requester)
        request.line_ids.analytic_distribution = {str(account.id): 100}
        # el residente imprime su propio vale (sin acceso a la analítica)
        html = self._render(request, user=self.requester)
        self.assertIn('Vale de requerimiento de obra', html)
        self.assertIn(request.name, html)
        self.assertIn('Disponible en central', html)
        self.assertIn('02.01 Concreto (test)', html)
        self.assertIn('Sin aprobaciones registradas', html)
        self.assertIn('Recibido en obra', html)  # firma

    def test_vale_processed_shows_split_and_approver(self):
        self._set_stock(self.cement, self.stock, 60)
        request = self._new_request(user=self.requester)
        request.action_request_approval()
        request.with_user(self.approver).validate_tier()
        request = request.with_env(self.env)
        request.with_user(self.logistics).action_process()
        html = self._render(request)
        self.assertIn('A despachar', html)
        self.assertIn('Nivel 1: jefe de proyecto (test)', html)
        self.assertIn('Aprobado', html)
        self.assertIn(self.approver.name, html)
        self.assertIn(request.purchase_request_ids.name, html)

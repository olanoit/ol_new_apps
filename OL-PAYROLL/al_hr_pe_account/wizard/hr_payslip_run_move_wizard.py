# -*- coding: utf-8 -*-
"""Asistente de previsualización y generación del asiento de lote.

Fusiona los dos wizards v18 de ``hr_payslip_run_move``:

* «Analisis Asiento Planilla»: reescribía al vuelo la vista SQL
  ``hr_payslip_run_move`` y la mostraba en una lista. Aquí la
  previsualización son líneas transitorias (``One2many``) calculadas
  por ORM dentro del propio formulario.
* «Generar Asiento Contable»: totales debe/haber, diferencia y cuenta
  de ajuste por redondeo antes de crear el ``account.move``.

La exportación a Excel del análisis v18 no se porta (los exportadores
van a la Fase 7 como ``ir.attachment``).
"""
from odoo import api, fields, models

from odoo.addons.al_hr_pe.tools import custom_round


class HrPayslipRunMoveWizard(models.TransientModel):
    _name = 'hr.payslip.run.move.wizard'
    _description = 'Asistente de asiento de planilla por lote'

    payslip_run_id = fields.Many2one(
        'hr.payslip.run', string='Lote de nómina', required=True)
    company_id = fields.Many2one(
        related='payslip_run_id.company_id', string='Compañía')
    with_analytic = fields.Boolean(
        string='Con distribución analítica',
        help='Por defecto toma el flag «Asiento de lote con analítica» '
             'de los Parámetros Principales; puede forzarse aquí para '
             'previsualizar ambos modos.')
    line_ids = fields.One2many(
        'hr.payslip.run.move.wizard.line', 'wizard_id',
        string='Líneas del asiento', readonly=True)
    debit = fields.Float(
        string='Total debe', compute='_compute_totals', digits='Account')
    credit = fields.Float(
        string='Total haber', compute='_compute_totals', digits='Account')
    difference = fields.Float(
        string='Diferencia', compute='_compute_totals', digits='Account')
    account_id = fields.Many2one(
        'account.account', string='Cuenta de ajuste', check_company=True,
        help='Cuenta de la línea «Ajuste por Redondeo» cuando debe y '
             'haber no cuadran.')

    @api.depends('line_ids.debit', 'line_ids.credit')
    def _compute_totals(self):
        for wizard in self:
            wizard.debit = custom_round(
                sum(wizard.line_ids.mapped('debit')))
            wizard.credit = custom_round(
                sum(wizard.line_ids.mapped('credit')))
            wizard.difference = custom_round(
                abs(wizard.debit - wizard.credit))

    @api.onchange('payslip_run_id')
    def _onchange_payslip_run_id(self):
        """Toma el flag analítico de la compañía y refresca la vista."""
        if self.payslip_run_id:
            param = self.env['hr.main.parameter'].search(
                [('company_id', '=', self.payslip_run_id.company_id.id)],
                limit=1)
            if param:
                self.with_analytic = param.detail_analytic
        self._pe_refresh_lines()

    @api.onchange('with_analytic')
    def _onchange_with_analytic(self):
        self._pe_refresh_lines()

    def _pe_refresh_lines(self):
        """Recalcula la previsualización desde ``hr.payslip.line``."""
        self.line_ids = [fields.Command.clear()]
        if not self.payslip_run_id:
            return
        lines = self.payslip_run_id._pe_prepare_batch_move_lines(
            with_analytic=self.with_analytic)
        self.line_ids = [fields.Command.create({
            'sequence': line['sequence'],
            'salary_rule_id': line['salary_rule_id'],
            'name': line['name'],
            'account_id': line['account_id'],
            'partner_id': line['partner_id'],
            'analytic_distribution': line['analytic_distribution'],
            'debit': line['debit'],
            'credit': line['credit'],
        }) for line in lines]

    def generate_move(self):
        """Genera y publica el asiento del lote y lo abre en pantalla.

        Las líneas se recalculan en el momento de generar (no se
        reutiliza la previsualización) para no contabilizar datos
        obsoletos si las boletas cambiaron con el wizard abierto.
        """
        self.ensure_one()
        self.payslip_run_id._pe_generate_batch_move(
            adjust_account=self.account_id,
            with_analytic=self.with_analytic)
        return self.payslip_run_id.action_open_move()


class HrPayslipRunMoveWizardLine(models.TransientModel):
    """Línea de previsualización (sustituye a la vista SQL
    ``hr_payslip_run_move`` reescrita al vuelo en v18)."""
    _name = 'hr.payslip.run.move.wizard.line'
    _inherit = 'analytic.mixin'
    _description = 'Línea de previsualización del asiento de lote'
    _order = 'sequence, id'

    wizard_id = fields.Many2one(
        'hr.payslip.run.move.wizard', string='Asistente',
        required=True, ondelete='cascade')
    sequence = fields.Integer(string='Secuencia')
    salary_rule_id = fields.Many2one(
        'hr.salary.rule', string='Regla salarial')
    name = fields.Char(string='Descripción')
    account_id = fields.Many2one(
        'account.account', string='Cuenta contable')
    partner_id = fields.Many2one('res.partner', string='Partner')
    # analytic_distribution (Json) viene de analytic.mixin.
    debit = fields.Float(string='Debe', digits='Account')
    credit = fields.Float(string='Haber', digits='Account')

# -*- coding: utf-8 -*-
"""Wizard único de generación de asientos de BBSS.

En v18 existían 4 wizards byte-idénticos salvo el registro destino
(``hr.cts.move.wizard``, ``hr.gratification.move.wizard``,
``hr.liquidation.move.wizard`` y ``hr.provisions.wizard``): mostraban
los totales debe/haber, permitían elegir una cuenta de ajuste por
redondeo y creaban/contabilizaban el ``account.move``. Aquí se
unifican en un solo modelo transitorio: el registro origen viaja en el
contexto (``benefits_model`` + ``benefits_id``) y los hooks
``_benefits_move_date_ref`` / ``_register_benefits_move`` del mixin
resuelven lo específico de cada flujo.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_hr_pe.tools import custom_round
from odoo.addons.al_hr_pe_benefits.models.hr_benefits_engine import \
    notify_success


class HrBenefitsMoveWizard(models.TransientModel):
    _name = 'hr.benefits.move.wizard'
    _description = 'Generación de asiento contable de BBSS'

    debit = fields.Float(string='Total debe', readonly=True)
    credit = fields.Float(string='Total haber', readonly=True)
    difference = fields.Float(
        string='Diferencia', compute='_compute_difference')
    account_id = fields.Many2one(
        'account.account', string='Cuenta de ajuste',
        help='Cuenta contra la que se registra la línea «Ajuste por '
             'redondeo» cuando debe y haber no cuadran al céntimo.')

    @api.depends('debit', 'credit')
    def _compute_difference(self):
        for record in self:
            record.difference = abs(record.debit - record.credit)

    @api.model
    def default_get(self, fields_list):
        """Propone la cuenta de ajuste configurada en los Parámetros
        Principales de la compañía del registro origen."""
        res = super().default_get(fields_list)
        if 'account_id' in fields_list and not res.get('account_id'):
            record = self._get_benefits_record()
            if record:
                param = self.env['hr.main.parameter'].get_main_parameter(
                    record.company_id)
                res['account_id'] = param.benefits_adjust_account_id.id
        return res

    def _get_benefits_record(self):
        """Registro de BBSS origen (viaja en el contexto)."""
        model = self.env.context.get('benefits_model')
        res_id = self.env.context.get('benefits_id')
        if not model or not res_id or model not in self.env:
            return None
        return self.env[model].browse(res_id).exists()

    def generate_move(self):
        """Crea y contabiliza el ``account.move`` con las líneas
        precalculadas por ``_get_move_lines`` (más el ajuste por
        redondeo si hay diferencia), y lo cuelga del registro origen.
        """
        self.ensure_one()
        record = self._get_benefits_record()
        if not record:
            raise UserError(self.env._(
                'No se encontró el registro de beneficios sociales de '
                'origen: vuelva a abrir el wizard desde el documento.'))
        if record.account_move_id:
            raise UserError(self.env._(
                'Elimine el asiento actual para generar uno nuevo.'))
        param = self.env['hr.main.parameter'].get_main_parameter(
            record.company_id)
        journal, partner = param.get_benefits_move_config()

        move_lines = list(self.env.context.get('move_lines') or [])
        if not move_lines:
            raise UserError(self.env._(
                'No hay líneas que contabilizar.'))
        difference = custom_round(self.difference, 2)
        if difference:
            if not self.account_id:
                raise UserError(self.env._(
                    'Seleccione la cuenta de ajuste para registrar la '
                    'diferencia por redondeo.'))
            debit, credit = (0.0, difference) \
                if self.debit > self.credit else (difference, 0.0)
            move_lines.append({
                'account_id': self.account_id.id,
                'name': self.env._('Ajuste por redondeo'),
                'debit': debit,
                'credit': credit,
                'partner_id': partner.id,
                'analytic_distribution': False,
            })

        move_date, ref = record._benefits_move_date_ref()
        move = self.env['account.move'].create({
            'journal_id': journal.id,
            'company_id': record.company_id.id,
            'date': move_date,
            'ref': ref,
            'line_ids': [(0, 0, {
                'account_id': line['account_id'],
                'debit': line['debit'],
                'credit': line['credit'],
                'name': line.get('name') or False,
                'partner_id': line.get('partner_id') or partner.id,
                'analytic_distribution':
                    line.get('analytic_distribution') or False,
            }) for line in move_lines],
        })
        move.action_post()
        record._register_benefits_move(move)
        return notify_success(self.env._(
            'Generación de asiento exitosa.'))

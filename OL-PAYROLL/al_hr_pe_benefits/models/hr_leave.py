# -*- coding: utf-8 -*-
"""Ausencias nativas (``hr.leave``) → suspensiones PE (T21).

La liquidación vacacional, los subsidios y el .snl del PLAME leen las
suspensiones ``hr.work.suspension``. Antes había que registrar la
vacación o el descanso médico dos veces: en ``hr.leave`` (calendario y
work entries) y como suspensión. Ahora el tipo de ausencia lleva su
código T21 y, al aprobarse, la ausencia crea sus suspensiones (una por
mes, con los días naturales de ese mes); si se rechaza, se cancela o se
borra, desaparecen.
"""
import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    l10n_pe_suspension_type_id = fields.Many2one(
        'hr.suspension.type', string='Suspensión PLAME (T21)',
        help='Con valor, cada ausencia aprobada de este tipo crea su '
             'suspensión de labores (vacaciones 23, descanso médico 20/21, '
             'maternidad 22…), de la que leen la liquidación vacacional, '
             'los subsidios y el .snl del PLAME.')

    @api.model
    def _l10n_pe_set_default_suspensions(self):
        """Vacaciones pagadas → T21 «23», si aún no tiene código."""
        # v19 lo llama leave_type_paid_time_off; las bases que vienen de
        # versiones anteriores conservan holiday_status_cl.
        leave_type = self.env.ref('hr_holidays.leave_type_paid_time_off',
                                  raise_if_not_found=False) \
            or self.env.ref('hr_holidays.holiday_status_cl',
                            raise_if_not_found=False)
        suspension = self.env.ref('al_hr_pe.suspension_23',
                                  raise_if_not_found=False)
        if leave_type and suspension \
                and not leave_type.l10n_pe_suspension_type_id:
            leave_type.l10n_pe_suspension_type_id = suspension


class HrWorkSuspension(models.Model):
    _inherit = 'hr.work.suspension'

    leave_id = fields.Many2one(
        'hr.leave', string='Ausencia', index='btree_not_null',
        ondelete='cascade', readonly=True,
        help='Ausencia aprobada que generó esta suspensión.',
        check_company=True)


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    l10n_pe_suspension_ids = fields.One2many(
        'hr.work.suspension', 'leave_id', string='Suspensiones PLAME')

    @api.model_create_multi
    def create(self, vals_list):
        leaves = super().create(vals_list)
        leaves.filtered(lambda leave: leave.state == 'validate') \
            ._l10n_pe_sync_suspensions()
        return leaves

    def write(self, vals):
        res = super().write(vals)
        if {'state', 'request_date_from', 'request_date_to',
                'holiday_status_id', 'employee_id'} & set(vals):
            self._l10n_pe_sync_suspensions()
        return res

    def _l10n_pe_sync_suspensions(self):
        """Rehace las suspensiones de las ausencias: una por mes para las
        aprobadas con tipo T21; ninguna para las demás."""
        Suspension = self.env['hr.work.suspension'].sudo()
        Period = self.env['hr.period'].sudo()
        # sudo: el aprobador de ausencias no tiene por qué tener acceso a
        # las suspensiones de nómina; se escriben solo las de estas
        # ausencias.
        Suspension.search([('leave_id', 'in', self.ids)]).unlink()
        for leave in self:
            suspension_type = \
                leave.holiday_status_id.l10n_pe_suspension_type_id
            if leave.state != 'validate' or not suspension_type \
                    or not leave.employee_id \
                    or not leave.request_date_from \
                    or not leave.request_date_to:
                continue
            company = leave.employee_id.company_id
            day = leave.request_date_from
            while day <= leave.request_date_to:
                period = Period.search([
                    ('company_id', '=', company.id),
                    ('period_type', '=', 'monthly'),
                    ('date_start', '<=', day),
                    ('date_end', '>=', day),
                ], limit=1)
                if not period:
                    _logger.warning(
                        'al_hr_pe_benefits: sin periodo de nómina para %s; '
                        'la ausencia %s no genera su suspensión de ese mes.',
                        day, leave.id)
                    month_end = (day.replace(day=28) + timedelta(days=4))
                    day = month_end - timedelta(days=month_end.day - 1)
                    continue
                last = min(period.date_end, leave.request_date_to)
                Suspension.create({
                    'employee_id': leave.employee_id.id,
                    'version_id': leave.employee_id._get_version(day).id,
                    'periodo_id': period.id,
                    'suspension_type_id': suspension_type.id,
                    'date_from': day,
                    'date_to': last,
                    'days': (last - day).days + 1,
                    'company_id': company.id,
                    'leave_id': leave.id,
                })
                day = last + timedelta(days=1)

# -*- coding: utf-8 -*-
"""Requerimiento de producción al jefe de producción (paquete 1.7 parte 2,
M17-18). Cada orden que crea el asistente del plan lleva la actividad
«Revisar y confirmar fecha» para el jefe de producción. La fecha que confirma
queda en la orden (también como fecha límite nativa) y mueve el fin de la
etapa de producción de sus ambientes en el cronograma, con el arrastre de las
etapas siguientes como en el Gantt."""
from datetime import datetime, time

from odoo import fields, models

DATE_REVIEW_ACTIVITY = 'al_construction_planner_mrp.mail_activity_production_date_review'


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_production_date_review = fields.Boolean(
        string='El jefe de producción confirma la fecha de cada orden', default=True)
    construction_production_head_id = fields.Many2one(
        'res.users', string='Jefe de producción', domain=[('share', '=', False)],
        help='Recibe la actividad «Revisar y confirmar fecha». Vacío: el responsable de la '
             'orden.')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_production_date_review = fields.Boolean(
        related='company_id.construction_production_date_review', readonly=False)
    construction_production_head_id = fields.Many2one(
        related='company_id.construction_production_head_id', readonly=False)


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    construction_date_confirmed = fields.Date(
        string='Fecha confirmada', tracking=True, copy=False,
        help='La que confirma el jefe de producción: queda como fecha límite de la orden y '
             'como fin de la etapa de producción de sus ambientes en el cronograma.')

    def write(self, vals):
        res = super().write(vals)
        if vals.get('construction_date_confirmed') \
                and not self.env.context.get('construction_date_confirming'):
            self._construction_apply_confirmed_date()
        return res

    def _construction_production_stages(self):
        """Etapas del cronograma de los ambientes de la orden que ella fabrica."""
        self.ensure_one()
        codes = self._construction_order_stages()
        # El jefe de producción no edita el cronograma: solo se leen las
        # etapas de los ambientes de su orden.
        return self.sudo().construction_space_task_ids.construction_stage_ids.filtered(
            lambda s: s.stage in codes)

    def _construction_schedule_date_review(self):
        """Actividad «Revisar y confirmar fecha» al jefe de producción."""
        for production in self:
            company = production.company_id
            if not company.construction_production_date_review:
                continue
            user = company.construction_production_head_id or production.user_id \
                or self.env.user
            stages = production._construction_production_stages()
            proposed = max(stages.mapped('date_end')) if stages else False
            note = self.env._('Fecha del cronograma: %s.', proposed) if proposed else \
                self.env._('Los ambientes de la orden no tienen etapa de producción en el '
                           'cronograma.')
            production.activity_schedule(
                DATE_REVIEW_ACTIVITY, user_id=user.id, note=note,
                date_deadline=fields.Date.context_today(production))

    def _construction_apply_confirmed_date(self):
        for production in self.filtered('construction_date_confirmed'):
            date = production.construction_date_confirmed
            production.with_context(construction_date_confirming=True).write({
                'date_deadline': datetime.combine(date, time(12, 0))})
            # El cronograma lo mantiene el sistema: el jefe de producción solo
            # confirma la fecha de su orden.
            for stage_sudo in production._construction_production_stages():
                if stage_sudo.date_end == date:
                    continue
                start = date - (stage_sudo.date_end - stage_sudo.date_start)
                stage_sudo.action_gantt_reschedule(start, date, chain=True)
            production.activity_feedback(
                [DATE_REVIEW_ACTIVITY],
                feedback=self.env._('Fecha confirmada: %s.', date))

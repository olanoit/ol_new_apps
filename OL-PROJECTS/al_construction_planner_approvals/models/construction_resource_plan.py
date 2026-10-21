# -*- coding: utf-8 -*-
from odoo import models


class ConstructionResourcePlan(models.Model):
    _name = 'construction.resource.plan'
    _inherit = ['construction.resource.plan', 'construction.approval.mixin']

    _construction_approval_document_type = 'plan'

    def _compute_need_validation(self):
        # Con Aprobaciones no se piden revisiones por niveles.
        approvals = self._construction_uses_approvals()
        super(ConstructionResourcePlan, self - approvals)._compute_need_validation()
        approvals.need_validation = False

    def action_request_approval(self):
        self.filtered(lambda p: p.state == 'draft')._construction_set_approval_engine()
        return super().action_request_approval()

    def _write_approved(self):
        if self.env.context.get('construction_approval_granted'):
            return super()._write_approved()
        submitted = self._construction_uses_approvals()._construction_submit_approval()
        return super(ConstructionResourcePlan, self - submitted)._write_approved()

    def _construction_approval_info(self):
        """El plan se aprueba completo: el monto es su total y el porcentaje,
        lo que sube frente a la versión vigente que reemplaza."""
        self.ensure_one()
        previous = self._get_previous_open_version()
        percent = 0.0
        if previous.amount_total:
            percent = (self.amount_total - previous.amount_total) / previous.amount_total * 100
        return {
            'values': {'all': {'percent': percent, 'amount': self.amount_total}},
            'lines': [],
            'amount': self.amount_total,
            # La subida frente a la versión anterior elige los tramos, pero no
            # es un exceso: la solicitud muestra 0 % (decisión del 21-oct-2026).
            'percent': 0.0,
            'reason': self.replan_reason or '',
        }

    def action_draft(self):
        self.filtered(lambda p: p.state == 'to_approve')._construction_cancel_open_approvals()
        return super().action_draft()

    def action_cancel(self):
        self.filtered(lambda p: p.state == 'to_approve')._construction_cancel_open_approvals()
        return super().action_cancel()

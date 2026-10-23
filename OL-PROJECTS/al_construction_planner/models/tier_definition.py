# -*- coding: utf-8 -*-
from odoo import api, models


class TierDefinition(models.Model):
    _inherit = 'tier.definition'

    @api.model
    def _get_tier_validation_model_names(self):
        res = super()._get_tier_validation_model_names()
        res.append('construction.resource.plan')
        res.append('construction.measurement')
        return res


# Grupos de los dos ejes (CREVAL v1.0, capítulo 5) que pueden revisar: cuentan
# también quienes los tienen por otro grupo (la jefatura de proyectos, el
# administrador), no solo los miembros directos.
AXIS_REVIEW_GROUPS = (
    'al_construction_planner.group_planner_plan_planner',
    'al_construction_planner.group_planner_plan_approver',
    'al_construction_planner.group_planner_exec_validator',
    'al_construction_planner.group_planner_exec_approver',
)


class TierReview(models.Model):
    _inherit = 'tier.review'

    def _get_reviewers(self):
        reviewers = super()._get_reviewers()
        group = self.reviewer_group_id
        if group and group.get_external_id().get(group.id) in AXIS_REVIEW_GROUPS:
            extra = group.all_user_ids.filtered(lambda user: not user.share)
            if self.definition_id.exclude_requester and self.requested_by:
                extra -= self.requested_by
            reviewers |= extra
        return reviewers

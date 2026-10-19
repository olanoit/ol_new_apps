# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    pharmacy_treatment_ids = fields.One2many('pharmacy.treatment', 'patient_id',
                                             string='Tratamientos crónicos')
    pharmacy_treatment_count = fields.Integer(compute='_compute_pharmacy_treatment_count',
                                              groups='al_pharmacy_base.group_pharmacy_technician')

    def _compute_pharmacy_treatment_count(self):
        counts = dict(self.env['pharmacy.treatment']._read_group(
            [('patient_id', 'in', self.ids)], ['patient_id'], ['__count']))
        for partner in self:
            partner.pharmacy_treatment_count = counts.get(partner, 0)

    def action_view_pharmacy_treatments(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_pharmacy_care.pharmacy_treatment_action')
        action['domain'] = [('patient_id', '=', self.id)]
        action['context'] = {'default_patient_id': self.id}
        return action

# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError


class PharmacyPrescription(models.Model):
    _inherit = 'pharmacy.prescription'

    treatment_ids = fields.One2many('pharmacy.treatment', 'prescription_id',
                                    string='Tratamientos crónicos')
    treatment_count = fields.Integer(compute='_compute_treatment_count')

    def _compute_treatment_count(self):
        for prescription in self:
            prescription.treatment_count = len(prescription.treatment_ids)

    def action_create_treatments(self):
        """Un tratamiento crónico por medicamento de la receta (los que tienen
        producto y aún no están en un tratamiento activo del paciente)."""
        self.ensure_one()
        if not self.patient_id:
            raise UserError(self.env._('La receta %s no tiene paciente.', self.name))
        Treatment = self.env['pharmacy.treatment']
        active_products = Treatment.search([
            ('patient_id', '=', self.patient_id.id), ('state', '=', 'active'),
            ('company_id', '=', self.company_id.id)]).product_id
        vals_list = []
        for line in self.line_ids.filtered('product_id'):
            if line.product_id in active_products:
                continue
            active_products |= line.product_id
            vals_list.append({
                'patient_id': self.patient_id.id,
                'product_id': line.product_id.id,
                'posology': line.posology,
                'date_start': self.date,
                'prescription_id': self.id,
                'warehouse_id': self.warehouse_id.id,
                'company_id': self.company_id.id,
            })
        if not vals_list and not self.treatment_ids:
            raise UserError(self.env._(
                'No hay medicamentos nuevos para un tratamiento: la receta solo indica principios '
                'activos o el paciente ya los tiene en tratamiento.'))
        Treatment.create(vals_list)
        return self.action_view_treatments()

    def action_view_treatments(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_pharmacy_care.pharmacy_treatment_action')
        action['domain'] = [('prescription_id', '=', self.id)]
        action['context'] = {'default_prescription_id': self.id,
                             'default_patient_id': self.patient_id.id}
        return action

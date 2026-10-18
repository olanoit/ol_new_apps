# -*- coding: utf-8 -*-
"""Receta especial (DS 023-2001-SA, arts. 23, 30 y 36): datos obligatorios,
vigencia de tres días, retención con folio y datos del adquiriente."""
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

SPECIAL_VALIDITY_DAYS = 3


class PharmacyPrescription(models.Model):
    _inherit = 'pharmacy.prescription'

    @api.onchange('prescription_type')
    def _onchange_prescription_type_special(self):
        if self.prescription_type == 'special':
            self.validity_days = SPECIAL_VALIDITY_DAYS

    @api.constrains('prescription_type', 'validity_days')
    def _check_special_validity(self):
        for prescription in self.filtered(lambda p: p.prescription_type == 'special'):
            if prescription.validity_days > SPECIAL_VALIDITY_DAYS:
                raise ValidationError(self.env._(
                    'La receta especial vale %s días desde su emisión.', SPECIAL_VALIDITY_DAYS))

    def _check_validity(self):
        super()._check_validity()
        # Lectura interna de datos restringidos (diagnóstico) solo para
        # comprobar que existen.
        for prescription in self.sudo().filtered(lambda p: p.prescription_type == 'special'):
            patient = prescription.patient_id
            missing = []
            if not patient.vat:
                missing.append(self.env._('documento de identidad del paciente'))
            if not (patient.street or patient.city):
                missing.append(self.env._('dirección del paciente'))
            if not patient.phone:
                missing.append(self.env._('teléfono del paciente'))
            if not prescription.diagnosis:
                missing.append(self.env._('diagnóstico'))
            if any(not line.posology for line in prescription.line_ids):
                missing.append(self.env._('posología de cada medicamento'))
            if missing:
                raise ValidationError(self.env._(
                    'Receta especial %(name)s incompleta (art. 23 del DS 023-2001-SA): %(missing)s.',
                    name=prescription.name, missing=', '.join(missing)))

    def _check_can_dispense(self, product, quantity):
        line = super()._check_can_dispense(product, quantity)
        template = product.product_tmpl_id
        if template._pharmacy_needs_special_prescription() and self.prescription_type != 'special':
            raise UserError(self.env._('%(product)s (lista %(list)s) se dispensa solo con receta '
                                       'especial.', product=product.display_name,
                                       list=template.pharmacy_control_list))
        return line

    def _dispense(self, product, quantity, lot=None, source=False, pharmacist=None,
                  purchaser_name=False, purchaser_vat=False):
        template = product.product_tmpl_id
        if template._pharmacy_needs_special_prescription() and not (purchaser_name and purchaser_vat):
            raise UserError(self.env._(
                'Registre el nombre y el documento de quien recibe %s (art. 30 del DS 023-2001-SA).',
                product.display_name))
        dispensation = super()._dispense(product, quantity, lot=lot, source=source,
                                         pharmacist=pharmacist, purchaser_name=purchaser_name,
                                         purchaser_vat=purchaser_vat)
        if template._pharmacy_retains_prescription() and not self.retained:
            self.write({
                'retained': True,
                'retention_folio': self.retention_folio or self.env['ir.sequence'].with_company(
                    self.company_id).next_by_code('pharmacy.prescription.retained'),
            })
        return dispensation

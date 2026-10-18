# -*- coding: utf-8 -*-
from odoo import fields, models

PROFESSIONS = [
    ('physician', 'Médico'),
    ('dentist', 'Cirujano dentista'),
    ('obstetrician', 'Obstetra'),
    ('other', 'Otro profesional autorizado'),
]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Prescriptor (BPOF 7.5.2.9: nombre y colegiatura en la receta)
    pharmacy_is_prescriber = fields.Boolean(string='Prescriptor')
    pharmacy_profession = fields.Selection(PROFESSIONS, string='Profesión')
    pharmacy_prescriber_license = fields.Char(
        string='Colegiatura', index='btree_not_null',
        help='Número de colegiatura: CMP (médicos), COP (cirujanos dentistas), COP (obstetras).')
    pharmacy_specialty = fields.Char(string='Especialidad')
    pharmacy_prescriber_status = fields.Selection([
        ('enabled', 'Hábil'),
        ('disabled', 'Inhábil'),
    ], string='Estado de la colegiatura', help='Según la última consulta al colegio profesional.')
    pharmacy_prescriber_checked = fields.Datetime(string='Consultado el', readonly=True)

    # Paciente: datos de salud, solo para el químico farmacéutico (Ley 29733).
    pharmacy_birthdate = fields.Date(string='Fecha de nacimiento',
                                     groups='al_pharmacy_base.group_pharmacy_pharmacist')
    pharmacy_allergy_ids = fields.Many2many(
        'pharmacy.ingredient', 'res_partner_pharmacy_allergy_rel', 'partner_id', 'ingredient_id',
        string='Alergias', groups='al_pharmacy_base.group_pharmacy_pharmacist',
        help='Principios activos a los que el paciente es alérgico: se avisa al dispensarlos.')
    pharmacy_chronic_conditions = fields.Text(
        string='Condiciones crónicas', groups='al_pharmacy_base.group_pharmacy_pharmacist')
    pharmacy_prescription_ids = fields.One2many('pharmacy.prescription', 'patient_id',
                                                string='Recetas')

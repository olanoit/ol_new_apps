# -*- coding: utf-8 -*-
"""Parámetros del régimen que la norma puede mover.

Van a la compañía y no a constantes en el código por lo mismo que la
tabla salarial: son cifras que cambian por convenio o por ley, y el
cliente debe poder ajustarlas sin esperar una versión del módulo.
"""
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_construction_grat_bonus_rate = fields.Float(
        string='Bonif. extraordinaria sobre gratificación (%)',
        digits=(5, 2), default=9.0,
        help='Ley 30334: la gratificación no aporta a EsSalud y ese 9 % se '
             'entrega al trabajador como bonificación extraordinaria.')
    l10n_pe_construction_school_age = fields.Integer(
        string='Edad tope de la asignación escolar', default=18,
        help='Hasta esta edad el hijo genera asignación escolar.')
    l10n_pe_conafovicer_rate = fields.Float(
        string='CONAFOVICER (%)', digits=(5, 2), default=2.0,
        help='Retención al trabajador para el Comité Nacional de '
             'Administración del Fondo para la Construcción de Viviendas '
             'y Centros Recreacionales (D.L. 21067). Se calcula sobre el '
             'jornal básico más el descanso semanal obligatorio.')
    l10n_pe_construction_essalud_rate = fields.Float(
        string='EsSalud (%)', digits=(5, 2), default=9.0,
        help='Aporte del empleador sobre la remuneración computable.')
    l10n_pe_sctr_health_rate = fields.Float(
        string='SCTR salud (%)', digits=(5, 2),
        help='Seguro Complementario de Trabajo de Riesgo, cobertura de '
             'salud (D.S. 003-98-SA). La tasa la fija la entidad '
             'aseguradora en el contrato, no la norma: hay que ponerla.')
    l10n_pe_sctr_pension_rate = fields.Float(
        string='SCTR pensión (%)', digits=(5, 2),
        help='Cobertura de invalidez y sepelio del SCTR. La tasa la fija '
             'la ONP o la compañía de seguros contratada.')
    l10n_pe_conafovicer_account = fields.Char(
        string='Cuenta CONAFOVICER (Banco de la Nación)',
        help='Cuenta en la que se deposita la retención, hasta el día 15 '
             'del mes siguiente.')
    l10n_pe_construction_school_age_study = fields.Integer(
        string='Edad tope cursando estudios superiores', default=21,
        help='Prolongación del derecho para el hijo que cursa estudios '
             'superiores.')

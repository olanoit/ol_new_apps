# -*- coding: utf-8 -*-
"""SCTR (D.S. 003-98-SA): tasas y entidades contratadas por la compañía.

La tasa la fija la aseguradora en el contrato, no la norma: vienen en
cero y hay que ponerlas. La entidad decide el código PLAME del aporte
(tabla 22): salud 0806 EsSalud / 0810 EPS, pensión 0813 ONP / 0814
compañía de seguros.
"""
from odoo import fields, models

#: Código PLAME del SCTR según la entidad contratada.
SCTR_SUNAT_CODES = {
    ('health', 'essalud'): '0806',
    ('health', 'eps'): '0810',
    ('pension', 'onp'): '0813',
    ('pension', 'insurer'): '0814',
}


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_sctr_health_rate = fields.Float(
        string='SCTR salud (%)', digits=(5, 2),
        help='Seguro Complementario de Trabajo de Riesgo, cobertura de '
             'salud (D.S. 003-98-SA). La tasa la fija la entidad '
             'aseguradora en el contrato, no la norma: hay que ponerla.')
    l10n_pe_sctr_pension_rate = fields.Float(
        string='SCTR pensión (%)', digits=(5, 2),
        help='Cobertura de invalidez y sepelio del SCTR. La tasa la fija '
             'la ONP o la compañía de seguros contratada.')
    l10n_pe_sctr_health_entity = fields.Selection(
        [('essalud', 'EsSalud'), ('eps', 'EPS')],
        string='SCTR salud con', default='essalud', required=True,
        help='Define el código PLAME del aporte: 0806 EsSalud, 0810 EPS.')
    l10n_pe_sctr_pension_entity = fields.Selection(
        [('onp', 'ONP'), ('insurer', 'Compañía de seguros')],
        string='SCTR pensión con', default='insurer', required=True,
        help='Define el código PLAME del aporte: 0813 ONP, 0814 compañía '
             'de seguros.')

    def _l10n_pe_sctr_sunat_code(self, coverage):
        self.ensure_one()
        entity = self['l10n_pe_sctr_%s_entity' % coverage]
        return SCTR_SUNAT_CODES.get((coverage, entity), '')

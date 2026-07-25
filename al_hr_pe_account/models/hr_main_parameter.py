# -*- coding: utf-8 -*-
"""Parámetros del asiento contable de planilla por lote.

Portado de ``hr_payslip_run_move/models/hr_main_parameter.py`` (v18).
Cambios v19:

* ``type_doc_pla`` (l10n_latam.document.type) NO se porta: en v18 solo
  se validaba su existencia en el wizard pero nunca se escribía en el
  asiento (las líneas que lo usaban estaban comentadas).
* Se añade ``detail_analytic``: interruptor por compañía que decide si
  las líneas del asiento de lote llevan ``analytic_distribution`` JSON
  nativo (regla salarial o ``hr.version``). Sustituye al par de módulos
  v18 ``hr_payslip_run_move`` / ``hr_payslip_run_move_analytic`` (se
  instalaba uno u otro según la compañía).
* Se añade ``afp_rule_ids``: en v18 los códigos de aportes AFP estaban
  hardcodeados en el SQL (``COMFI/COMMIX/SEGI/A_JUB``); por convención
  del proyecto ahora son configurables.
"""
from odoo import fields, models
from odoo.exceptions import UserError


class HrMainParameter(models.Model):
    _inherit = 'hr.main.parameter'

    # --- Asiento de planilla por lote ---
    move_journal_id = fields.Many2one(
        'account.journal', string='Diario del asiento de planilla',
        check_company=True,
        help='Diario en el que se registra el asiento único del lote de '
             'planilla. El flujo nativo por boleta usa el diario de la '
             'estructura salarial; este diario solo aplica al asiento '
             'de lote peruano.')
    move_partner_id = fields.Many2one(
        'res.partner', string='Partner para planillas',
        check_company=True,
        help='Contacto por defecto de las líneas del asiento de lote '
             '(típicamente un partner interno "Planillas").')
    detail_analytic = fields.Boolean(
        string='Asiento de lote con analítica', default=False,
        help='Si está activo, las líneas del asiento de lote llevan la '
             'distribución analítica nativa (JSON) tomada de la regla '
             'salarial o, en su defecto, de la ficha del trabajador '
             '(hr.version). Apagado: comportamiento contable puro sin '
             'analítica (v18: módulo sin sufijo _analytic).')
    afp_rule_ids = fields.Many2many(
        'hr.salary.rule', 'afp_rule_main_parameter_rel',
        'main_parameter_id', 'rule_id',
        string='R.S. aportes AFP (cuenta por afiliación)',
        help='Reglas cuyo abono se imputa a la cuenta contable de la '
             'afiliación (hr.membership) del trabajador en lugar de la '
             'cuenta de crédito de la regla, con una línea por AFP. '
             'En v18 eran los códigos fijos COMFI, COMMIX, SEGI y '
             'A_JUB.')

    def check_batch_move_values(self):
        """Valida la configuración mínima del asiento de lote.

        Equivalente a las validaciones del wizard v18 (``generate_move``)
        menos el tipo de comprobante, que nunca se usaba.
        """
        self.ensure_one()
        if not self.move_journal_id:
            raise UserError(self.env._(
                'No se ha configurado el diario contable del asiento de '
                'planilla en los Parámetros Principales (pestaña '
                'Contabilidad).'))
        if not self.move_partner_id:
            raise UserError(self.env._(
                'No se ha configurado el partner para planillas en los '
                'Parámetros Principales (pestaña Contabilidad).'))

# -*- coding: utf-8 -*-
"""Cuentas contables de beneficios sociales en los Parámetros Principales.

Unifica en un solo lugar la configuración contable que en v18 estaba
dispersa entre ``hr.main.parameter`` (``cts_debe/haber``,
``grati_debe/haber``, ``boni_debe/haber``, ``vaca_debe/haber``,
``detallar_provision`` — módulo ``hr_provisions``) y las cuentas
``account_debit``/``account_credit`` de reglas salariales localizadas
por código SQL (``CTS``, ``ADE_CTS``, ``GRA``, ``ADE_GRA``,
``GRA_TRU``, ``CTS_TRU``, ``VATRU``, ... — módulos
``hr_social_benefits_move`` y ``hr_social_benefits_move_analytic``).

En v19 los códigos hardcodeados están prohibidos y las cuentas son
``company_dependent`` (patrón de ``hr.membership.account_id``): el
registro de parámetros es único por compañía, pero el atributo permite
sobrescribir por compañía sin duplicar configuración si algún día los
parámetros se comparten.

Los campos del asiento de lote (``journal_id``, ``partner_id``,
``detail_analytic``) los declara la otra rama de esta misma Fase 5
(asiento del lote de nómina); aquí solo se CONSUMEN vía ``getattr``
con guardas (ver :meth:`get_benefits_move_config`).
"""
from odoo import fields, models
from odoo.exceptions import UserError


class HrMainParameter(models.Model):
    _inherit = 'hr.main.parameter'

    # --- Gasto (debe) y provisión (haber) por concepto — v18
    #     hr_provisions/models/hr_main_parameter.py -------------------
    cts_debe_account_id = fields.Many2one(
        'account.account', string='Gasto CTS (debe)',
        company_dependent=True, ondelete='restrict',
        help='Cuenta de gasto de la CTS (v18: «CTS Debe» / '
             'account_debit de la regla CTS). Se usa en la provisión '
             'mensual, en el depósito semestral y en la CTS trunca de '
             'la liquidación de cese.')
    cts_haber_account_id = fields.Many2one(
        'account.account', string='Provisión CTS (haber)',
        company_dependent=True, ondelete='restrict',
        help='Pasivo de la provisión de CTS (v18: «CTS Haber»). Se '
             'abona al provisionar cada mes y se carga al revertir la '
             'provisión en el depósito o en la liquidación.')
    grati_debe_account_id = fields.Many2one(
        'account.account', string='Gasto gratificación (debe)',
        company_dependent=True, ondelete='restrict',
        help='Cuenta de gasto de la gratificación legal (v18: '
             '«Gratificacion Debe» / account_debit de la regla GRA).')
    grati_haber_account_id = fields.Many2one(
        'account.account', string='Provisión gratificación (haber)',
        company_dependent=True, ondelete='restrict',
        help='Pasivo de la provisión de gratificación (v18: '
             '«Gratificacion Haber»).')
    boni_debe_account_id = fields.Many2one(
        'account.account', string='Gasto bono extraordinario (debe)',
        company_dependent=True, ondelete='restrict',
        help='Cuenta de gasto del Bono Extraordinario Ley 29351 en la '
             'provisión mensual (v18: «Bono Debe»).')
    boni_haber_account_id = fields.Many2one(
        'account.account', string='Provisión bono extraordinario (haber)',
        company_dependent=True, ondelete='restrict',
        help='Pasivo de la provisión del Bono Extraordinario Ley '
             '29351 (v18: «Bono Haber»).')
    vaca_debe_account_id = fields.Many2one(
        'account.account', string='Gasto vacaciones (debe)',
        company_dependent=True, ondelete='restrict',
        help='Cuenta de gasto de vacaciones (v18: «Vacaciones Debe» / '
             'account_debit de la regla VATRU en la liquidación).')
    vaca_haber_account_id = fields.Many2one(
        'account.account', string='Provisión vacaciones (haber)',
        company_dependent=True, ondelete='restrict',
        help='Pasivo de la provisión de vacaciones (v18: «Vacaciones '
             'Haber»).')

    # --- Pasivos por pagar de los asientos de pago/depósito — v18
    #     account_credit de reglas localizadas por código -------------
    cts_payable_account_id = fields.Many2one(
        'account.account', string='CTS por pagar (haber)',
        company_dependent=True, ondelete='restrict',
        help='Cuenta por pagar del depósito semestral de CTS (v18: '
             'account_credit de la regla ADE_CTS/CTS según variante).')
    grati_payable_account_id = fields.Many2one(
        'account.account', string='Gratificación por pagar (haber)',
        company_dependent=True, ondelete='restrict',
        help='Cuenta por pagar de la gratificación semestral (v18: '
             'account_credit de la regla ADE_GRA/GRA según variante).')
    liquidation_payable_account_id = fields.Many2one(
        'account.account', string='Liquidaciones por pagar (haber)',
        company_dependent=True, ondelete='restrict',
        help='Cuenta por pagar de la liquidación de cese (v18: '
             'account_credit de las reglas truncas GRA_TRU / BON9_TRU '
             '/ CTS_TRU / VATRU, normalmente la misma 41x).')

    # --- Conceptos extra de la liquidación ---------------------------
    liq_concept_in_account_id = fields.Many2one(
        'account.account', string='Conceptos extra ingreso (debe)',
        company_dependent=True, ondelete='restrict',
        help='Cuenta de cargo de los conceptos extra tipo «ingreso» de '
             'la liquidación de cese. En v18 la cuenta salía de la '
             'regla salarial homónima al input de cada concepto; en '
             'v19 se unifica en esta cuenta configurable.')
    liq_concept_out_account_id = fields.Many2one(
        'account.account', string='Conceptos extra descuento (haber)',
        company_dependent=True, ondelete='restrict',
        help='Cuenta de abono de los conceptos extra tipo «descuento» '
             'de la liquidación de cese (v18: account_credit de la '
             'regla homónima al input).')

    # --- Ajuste por redondeo -----------------------------------------
    benefits_adjust_account_id = fields.Many2one(
        'account.account', string='Cuenta de ajuste por redondeo',
        company_dependent=True, ondelete='restrict',
        help='Default de la «Cuenta de ajuste» del wizard de '
             'generación de asientos de BBSS (en v18 se elegía a mano '
             'en cada wizard).')

    # --- Comportamiento de la provisión mensual ----------------------
    detallar_provision = fields.Boolean(
        string='Detallar provisión por trabajador', default=True,
        help='Si está activo, las líneas al haber del asiento de '
             'provisión mensual se generan una por trabajador (con su '
             'tercero); si no, se agrupan por cuenta contable.')

    # ------------------------------------------------------------------
    # Helpers para los asientos de BBSS
    # ------------------------------------------------------------------
    def check_benefits_account_values(self, field_names):
        """Valida que las cuentas requeridas por un asiento estén
        configuradas; lista los nombres faltantes en el error."""
        self.ensure_one()
        missing = [self._fields[name].string
                   for name in field_names if not self[name]]
        if missing:
            raise UserError(self.env._(
                'Faltan cuentas contables de beneficios sociales en '
                'los Parámetros Principales (pestaña Contabilidad '
                'BBSS): %(fields)s.', fields=', '.join(missing)))

    def get_benefits_move_config(self):
        """(diario, partner de planillas) para crear el asiento.

        Ambos campos (``move_journal_id`` / ``move_partner_id``) los
        declara la rama del asiento de lote de esta misma Fase 5 sobre
        ``hr.main.parameter``; se leen con ``getattr`` para no acoplar
        la carga de este archivo a la existencia de esos campos.
        """
        self.ensure_one()
        journal = getattr(self, 'move_journal_id', False)
        if not journal:
            raise UserError(self.env._(
                'No se ha configurado el diario contable de planillas '
                'en los Parámetros Principales (pestaña '
                'Contabilidad).'))
        partner = getattr(self, 'move_partner_id', False)
        if not partner:
            raise UserError(self.env._(
                'No se ha configurado el partner de planillas en los '
                'Parámetros Principales (pestaña Contabilidad).'))
        return journal, partner

    # TODO(fase5-revisar): la variante analítica v18 permitía además una
    # CUENTA de gasto distinta por cuenta analítica (hr_salary_rule_line:
    # cuenta contable por centro de costo); eso no es representable con
    # una cuenta + analytic_distribution JSON y no se porta: v19 usa una
    # sola cuenta de gasto por concepto y prorratea solo la analítica.
    def _benefits_analytic_distribution(self, version):
        """Distribución analítica JSON para las líneas de gasto.

        Devuelve el ``analytic_distribution`` nativo de la versión de
        contrato (``hr.version`` + ``analytic.mixin`` vía
        ``hr_payroll_account``) solo cuando el flag por compañía
        ``detail_analytic`` está activo. Sustituye al desdoble por
        ``hr.analytic.distribution.line`` de v18: el prorrateo por
        porcentaje lo resuelve el JSON nativo dentro de una sola
        línea contable.
        """
        self.ensure_one()
        if not getattr(self, 'detail_analytic', False):
            return False
        return getattr(version, 'analytic_distribution', False) or False

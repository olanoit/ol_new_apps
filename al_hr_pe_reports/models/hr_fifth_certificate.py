# -*- coding: utf-8 -*-
"""Certificado de rentas y retenciones de 5ta categoría.

Documento anual que el empleador entrega al trabajador con las rentas
de 5ta pagadas en el ejercicio y el impuesto retenido (Art. 45 del
Reglamento de la LIR, D.S. 122-94-EF; R.S. 010-2006/SUNAT).

Portado de ``hr_fifth_category_certificate`` (v18). Cambios v19:

* PDF por QWeb — desaparecen reportlab, ``dir_create_file`` y
  ``popup.it``.
* ``account.fiscal.year`` no existe: el ejercicio es un entero y la UIT
  sale del catálogo ``l10n_pe.hr.uit`` (``al_hr_pe``).
* Los SQL con ``.format()`` del v18 se sustituyen por los helpers ORM
  de ``hr.fifth.category.line`` (``al_hr_pe_benefits``):
  ``_sum_payslip_rule_totals`` y ``_get_quinta_rule``.
* Desviación del plan documentada: el plan destinaba este certificado a
  ``al_hr_pe_benefits``; se ubica aquí (``al_hr_pe_reports`` ya depende
  de benefits) para no mezclar reportes con el módulo de cálculo.
* No portado: envío por correo con PDF cifrado con el DNI
  (``send_quinta_by_email``) — reportlab permitía ``encrypt=``; QWeb
  no. TODO(fase7-revisar): decidir si se repone con pikepdf/qpdf.

Paridad v18 conservada a propósito: el punto «3. Impuesto a la renta»
del certificado muestra el mismo importe que «4. Total retención
efectuada» (la suma retenida por la regla QUINTA en el año), por lo que
el «Saldo por regularizar» siempre es 0.
"""
from datetime import date

from odoo import api, fields, models
from odoo.exceptions import UserError


class HrFifthCertificateWizard(models.TransientModel):
    """Asistente del certificado de retenciones de 5ta categoría.

    Multi-empleado: lanzado desde la lista de empleados imprime un
    certificado por página para cada seleccionado.
    """
    _name = 'hr.fifth.certificate.wizard'
    _inherit = ['l10n_pe.hr.doc.mixin']
    _description = 'Asistente de certificado de renta de 5ta categoría'

    year = fields.Integer(
        string='Ejercicio gravable', required=True,
        default=lambda self: fields.Date.context_today(self).year - 1,
        help='Año fiscal certificado (el certificado se entrega antes '
             'del 1 de marzo del año siguiente).')
    date = fields.Date(
        string='Fecha de emisión', required=True,
        default=fields.Date.context_today)
    employee_ids = fields.Many2many(
        'hr.employee', 'hr_fifth_certificate_wizard_employee_rel',
        'wizard_id', 'employee_id', string='Empleados', required=True,
        check_company=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company)
    main_parameter_id = fields.Many2one(
        'hr.main.parameter', string='Parámetros',
        compute='_compute_main_parameter_id')

    @api.depends('company_id')
    def _compute_main_parameter_id(self):
        Param = self.env['hr.main.parameter']
        for wizard in self:
            wizard.main_parameter_id = Param.search(
                [('company_id', '=', wizard.company_id.id)], limit=1)

    @api.model
    def default_get(self, fields_list):
        """Pre-selecciona los empleados activos de la vista de origen."""
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'hr.employee' \
                and self.env.context.get('active_ids') \
                and 'employee_ids' in fields_list:
            res.setdefault(
                'employee_ids',
                [(6, 0, self.env.context['active_ids'])])
        return res

    def action_print(self):
        """Valida la configuración de quinta y lanza el reporte QWeb."""
        self.ensure_one()
        if self.year <= 0:
            raise UserError(self.env._('Ingrese un ejercicio válido.'))
        param = self.env['hr.main.parameter'].get_main_parameter(
            self.company_id)
        param.check_fifth_values()
        # Valida temprano que exista la UIT del ejercicio.
        self.env['l10n_pe.hr.uit'].get_uit(self.year)
        return self.env.ref(
            'al_hr_pe_reports.action_report_fifth_certificate'
        ).report_action(self)

    # ------------------------------------------------------------------
    # Datos del certificado (uno por empleado)
    # ------------------------------------------------------------------
    def _get_certificate_values(self, employee):
        """Importes del certificado del ejercicio para ``employee``.

        Paridad de fórmulas v18 (``get_past_rem`` /
        ``get_past_months_ret`` de todo el año):

        * ``rem_bruta``: reglas afectas ordinaria + extraordinaria de
          las boletas de lote del año, más las gratificaciones reales
          de julio y diciembre (total + bono EsSalud, Ley 29351).
        * ``other_emp_rem``: rentas de otros empleadores declaradas en
          las quintas mensuales del año.
        * ``deduccion``: 7 UIT del ejercicio.
        * ``retencion``: total retenido por la regla QUINTA en el año
          (0 si negativo).
        """
        self.ensure_one()
        company = self.company_id
        param = self.env['hr.main.parameter'].get_main_parameter(company)
        param.check_fifth_values()
        Line = self.env['hr.fifth.category.line']
        GratLine = self.env['hr.gratification.line']
        year = self.year
        date_from = date(year, 1, 1)
        date_before = date(year + 1, 1, 1)

        rem = Line._sum_payslip_rule_totals(
            employee, company,
            param.fifth_afect_sr_id + param.fifth_extr_sr_id,
            date_from, date_before)
        grats = GratLine.search([
            ('gratification_id.type', 'in', ('07', '12')),
            ('gratification_id.year', '=', year),
            ('gratification_id.company_id', '=', company.id),
            ('employee_id', '=', employee.id),
        ])
        rem_bruta = rem + sum(grats.mapped('total_grat')) \
            + sum(grats.mapped('bonus_essalud'))

        fifth_lines = Line.search([
            ('slip_id.date_to', '>=', date_from),
            ('slip_id.date_to', '<', date_before),
            ('employee_id', '=', employee.id),
            ('company_id', '=', company.id),
        ])
        other_emp_rem = sum(fifth_lines.mapped('other_emp_proy_rem'))

        uit = self.env['l10n_pe.hr.uit'].get_uit(year)
        rem_total = rem_bruta + other_emp_rem
        seven_uit = 7 * uit
        retencion = Line._sum_payslip_rule_totals(
            employee, company, Line._get_quinta_rule(company),
            date_from, date_before)
        retencion = max(retencion, 0.0)
        return {
            'rem_bruta': rem_bruta,
            'other_emp_rem': other_emp_rem,
            'rem_total': rem_total,
            'seven_uit': seven_uit,
            'renta_imponible': rem_total - seven_uit,
            'impuesto': retencion,
            'retencion': retencion,
            'saldo': 0.0,
        }

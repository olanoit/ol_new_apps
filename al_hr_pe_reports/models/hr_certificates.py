# -*- coding: utf-8 -*-
"""Certificado de trabajo y carta de retiro de CTS.

* **Certificado de trabajo**: documento que el empleador está obligado
  a entregar al cese del trabajador (D.S. 001-96-TR Art. 42), con las
  fechas de inicio y fin de la relación laboral y el cargo desempeñado.
* **Carta de retiro CTS**: comunicación al banco depositario para que
  libere al trabajador cesado el íntegro de su Compensación por Tiempo
  de Servicios (D.S. 001-97-TR TUO de la Ley de CTS, Art. 44 y ss.).

Portado de ``hr_certificate_letter`` (v18). Cambios v19:

* ``hr.contract`` → ``hr.version``: el rango laboral sale de la primera
  versión con ``contract_date_start`` y de la versión de baja
  (``situation_id.code = '0'``, T15 PLAME) o del ``departure_date``.
* ``employee.gender`` → ``employee.sex`` (renombrado en v19).
* Los PDF se generan con QWeb (sin reportlab ni directorio en disco).
* ``main_parameter_id`` ya no bloquea el ``default_get`` si falta la
  configuración: se resuelve como compute y se exige recién al imprimir.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError

TREATMENT_SELECTION = [
    ('el Sr.', 'Señor'),
    ('la Sra.', 'Señora'),
    ('la Srta.', 'Señorita'),
]


class L10nPeHrDocMixin(models.AbstractModel):
    """Helpers compartidos por los documentos laborales peruanos."""
    _name = 'l10n_pe.hr.doc.mixin'
    _description = 'Mixin de documentos laborales PE'

    @api.model
    def format_date_letters(self, value):
        """Fecha con el mes en letras: «07 de Marzo del 2026».

        Usa ``hr.main.parameter.get_month_name`` (fuente única de los
        meses en español) en vez de depender de que el idioma es_PE
        esté instalado.
        """
        if not value:
            return ''
        month = self.env['hr.main.parameter'].get_month_name(value.month)
        return '%02d de %s del %d' % (value.day, month, value.year)

    @api.model
    def _default_treatment(self, employee):
        """Tratamiento según el sexo del empleado (paridad v18: masculino
        → «el Sr.», resto → «la Srta.»)."""
        return 'el Sr.' if employee.sex == 'male' else 'la Srta.'

    @api.model
    def _get_cese_dates(self, employee):
        """(fecha de ingreso, fecha de cese) del empleado.

        * Ingreso: ``contract_date_start`` más antiguo entre sus
          versiones (v18: primer contrato).
        * Cese: ``contract_date_end`` de la versión con situación de
          baja (código '0' de la T15) o, en su defecto, el
          ``departure_date`` nativo.
        """
        date_ini = date_fin = False
        if employee:
            versions = employee.version_ids.filtered('contract_date_start')
            if versions:
                date_ini = min(versions.mapped('contract_date_start'))
            baja = self.env['hr.version'].search([
                ('employee_id', '=', employee.id),
                ('situation_id.code', '=', '0'),
            ], order='date_version desc', limit=1)
            date_fin = baja.contract_date_end or employee.departure_date
        return date_ini, date_fin


class HrCertificateWizard(models.TransientModel):
    """Asistente del Certificado de Trabajo en PDF.

    Pre-rellena el rango laboral (primera versión → versión de baja),
    el tratamiento según el sexo y la ciudad de la compañía emisora.
    """
    _name = 'hr.certificate.wizard'
    _inherit = ['l10n_pe.hr.doc.mixin']
    _description = 'Asistente de certificado de trabajo'

    employee_id = fields.Many2one(
        'hr.employee', string='Empleado a certificar', required=True)
    des_empl = fields.Selection(
        TREATMENT_SELECTION, string='Tratamiento', default='el Sr.')
    date_ini = fields.Date(string='Fecha de ingreso')
    date_fin = fields.Date(string='Fecha de cese')
    city = fields.Char(string='Ciudad')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company)
    main_parameter_id = fields.Many2one(
        'hr.main.parameter', string='Parámetros',
        compute='_compute_main_parameter_id',
        help='Aporta la firma escaneada y el representante legal que '
             'suscribe el certificado.')

    @api.depends('company_id')
    def _compute_main_parameter_id(self):
        Param = self.env['hr.main.parameter']
        for wizard in self:
            wizard.main_parameter_id = Param.search(
                [('company_id', '=', wizard.company_id.id)], limit=1)

    @api.model
    def default_get(self, fields_list):
        """Pre-rellena tratamiento, ciudad y rango laboral del empleado."""
        res = super().default_get(fields_list)
        employee = self.env['hr.employee'].browse(
            res.get('employee_id')) if res.get('employee_id') else False
        if employee:
            date_ini, date_fin = self._get_cese_dates(employee)
            res.update({
                'date_ini': date_ini,
                'date_fin': date_fin,
                'des_empl': self._default_treatment(employee),
            })
        res.setdefault('city', self.env.company.city)
        return res

    def export_certificate(self):
        """Valida los datos y lanza el reporte QWeb-PDF.

        :raises ValidationError: si falta algún dato del certificado.
        """
        self.ensure_one()
        if not self.des_empl:
            raise ValidationError(self.env._('Ingrese el tratamiento.'))
        if not self.city:
            raise ValidationError(self.env._('Ingrese la ciudad.'))
        if not self.date_ini:
            raise ValidationError(self.env._('Ingrese la fecha de ingreso.'))
        if not self.date_fin:
            raise ValidationError(self.env._('Ingrese la fecha de cese.'))
        # Exigir la configuración recién aquí (con su mensaje guiado).
        self.env['hr.main.parameter'].get_main_parameter(self.company_id)
        return self.env.ref(
            'al_hr_pe_reports.action_report_certificate').report_action(self)


class HrLetterWizard(models.TransientModel):
    """Asistente de la Carta de Retiro CTS en PDF.

    Carta dirigida al banco donde el empleador depositó la CTS para
    autorizar la entrega del íntegro al trabajador cesado
    (D.S. 001-97-TR). La cuenta sale de ``employee.cts_bank_account_id``
    (campo de ``al_hr_pe``).
    """
    _name = 'hr.letter.wizard'
    _inherit = ['l10n_pe.hr.doc.mixin']
    _description = 'Asistente de carta de retiro CTS'

    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', required=True)
    des_empl = fields.Selection(
        TREATMENT_SELECTION, string='Tratamiento', default='el Sr.')
    date_fin = fields.Date(string='Fecha de cese')
    city = fields.Char(string='Ciudad')
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
        """Pre-rellena fecha de cese, ciudad y tratamiento del empleado."""
        res = super().default_get(fields_list)
        employee = self.env['hr.employee'].browse(
            res.get('employee_id')) if res.get('employee_id') else False
        if employee:
            res.update({
                'date_fin': self._get_cese_dates(employee)[1],
                'des_empl': self._default_treatment(employee),
            })
        res.setdefault('city', self.env.company.city)
        return res

    def export_letter(self):
        """Valida los datos y lanza el reporte QWeb-PDF.

        :raises ValidationError: si falta algún dato o el empleado no
            tiene cuenta CTS configurada.
        """
        self.ensure_one()
        if not self.des_empl:
            raise ValidationError(self.env._('Ingrese el tratamiento.'))
        if not self.city:
            raise ValidationError(self.env._('Ingrese la ciudad.'))
        if not self.date_fin:
            raise ValidationError(self.env._('Ingrese la fecha de cese.'))
        if not self.employee_id.cts_bank_account_id:
            raise ValidationError(self.env._(
                'El empleado %(employee)s no tiene cuenta CTS configurada '
                '(ficha del empleado → Perú — Identificación).',
                employee=self.employee_id.display_name))
        self.env['hr.main.parameter'].get_main_parameter(self.company_id)
        return self.env.ref(
            'al_hr_pe_reports.action_report_letter').report_action(self)

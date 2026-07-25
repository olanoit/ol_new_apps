# -*- coding: utf-8 -*-
"""Contratos de trabajo desde plantilla HTML.

Plantillas de contrato con placeholders ``{{nombre}}`` que se rellenan
con los datos de la versión (v19: el «contrato» es ``hr.version``), el
empleado, la compañía y los parámetros de nómina, y se imprimen como
PDF QWeb.

Portado de ``hr_print_contract`` (v18) con estos veredictos:

* **hr.contract → hr.version**: los datos del contrato (fechas, sueldo,
  tipo, cargo) viven en la versión del empleado.
* **hr.contract.history NO se porta**: el histórico que modelaba la
  vista SQL v18 lo da el versionado nativo de ``hr.version``.
* La plantilla deja de colgar de ``hr.contract.type`` (catálogo nativo
  compartido) y pasa a un modelo propio ``l10n_pe.hr.contract.template``
  multicompañía (global o de la compañía), para que cada empresa tenga
  sus propios textos sin duplicar tipos de contrato.
* **Bug de `sanitize` corregido**: el cuerpo usa ``sanitize=False`` — el
  saneado por defecto reescribía el HTML pegado desde Word (estilos,
  entidades) y podía romper los placeholders. El campo solo lo editan
  gestores de nómina y los valores sustituidos se escapan al renderizar,
  así que no se re-inyecta contenido de usuario sin escapar.
* **Bug de `&nbsp;` corregido**: el editor HTML inserta ``&nbsp;`` /
  ``\\xa0`` dentro de ``{{ placeholder }}`` y la sustitución fallaba;
  ahora se normalizan a espacio antes de sustituir.
* **Sin Jinja2**: la sustitución es por diccionario controlado con una
  expresión regular (mismos nombres de placeholder que v18) — sin
  evaluación de código en la plantilla (el ``Template(...)`` de Jinja
  del v18 era una superficie de SSTI).
* El período de prueba (LPCL D.S. 003-97-TR Art. 10) se conserva:
  régimen en la versión y cálculo del ``trial_date_end`` nativo.
* No portados: envío por correo (``send_contract_email``) y la vista
  previa HTML en el form (``contract_html_preview``) — el PDF cumple
  ese rol. TODO(fase7-revisar): decidir si se repone el envío por
  correo con plantilla ``mail.template``.
"""
import logging
import re

from dateutil.relativedelta import relativedelta
from markupsafe import Markup, escape as markup_escape

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Placeholder v18: {{nombre_empleador}} — se admite espacio/nbsp interno.
PLACEHOLDER_RE = re.compile(r'\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}')


class L10nPeHrContractTemplate(models.Model):
    """Plantilla de contrato de trabajo (texto HTML con placeholders).

    Global (``company_id`` vacío, visible por todas las compañías) o
    propia de una compañía — mismo patrón «global-or-own» que los
    catálogos PLAME de ``al_hr_pe``.
    """
    _name = 'l10n_pe.hr.contract.template'
    _description = 'Plantilla de contrato de trabajo (PE)'
    _order = 'sequence, name'

    name = fields.Char(string='Nombre', required=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(string='Activo', default=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', index=True,
        help='Vacío = plantilla global visible por todas las compañías.')
    body = fields.Html(
        string='Cuerpo del contrato', sanitize=False,
        help='Texto del contrato con placeholders {{nombre_empleador}}, '
             '{{nombre_trabajador}}, {{salario}}, {{fecha_inicio}}, etc. '
             'Ver la lista completa en el formulario.')

    _name_company_uniq = models.Constraint(
        'UNIQUE(name, company_id)',
        'Ya existe una plantilla de contrato con ese nombre en la '
        'compañía.')

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------
    def _render_body(self, version):
        """Renderiza el cuerpo con los datos de ``version``.

        Correcciones sobre v18: normaliza ``&nbsp;``/``\\xa0`` antes de
        sustituir y reemplaza por diccionario controlado (sin Jinja).
        Los valores se escapan (``markupsafe.escape``); los placeholders
        desconocidos se sustituyen por vacío y se registran en el log.
        """
        self.ensure_one()
        body = str(self.body or '')
        body = body.replace('&nbsp;', ' ').replace('\xa0', ' ')
        values = self._get_placeholder_values(version)
        missing = set()

        def _replace(match):
            key = match.group(1)
            if key in values:
                return str(markup_escape(values[key]))
            missing.add(key)
            return ''

        rendered = PLACEHOLDER_RE.sub(_replace, body)
        if missing:
            _logger.warning(
                "Plantilla de contrato %s: placeholders desconocidos %s "
                "(versión %s).", self.display_name, sorted(missing),
                version.id)
        return Markup(rendered)

    @api.model
    def _selection_label(self, record, field_name):
        """Etiqueta traducida del valor de un campo selection."""
        if not record:
            return ''
        field = record._fields.get(field_name)
        if field is None:
            return ''
        labels = dict(field._description_selection(record.env))
        return labels.get(record[field_name], '') or ''

    @api.model
    def _duration_string(self, date_start, date_end):
        """Duración entre dos fechas en letras («11 meses, 29 días»);
        «indefinido» si falta alguna (paridad v18)."""
        if not date_start or not date_end:
            return 'indefinido'
        delta = relativedelta(date_end, date_start)
        parts = []
        if delta.years > 0:
            parts.append('%d año%s' % (delta.years,
                                       's' if delta.years > 1 else ''))
        if delta.months > 0:
            parts.append('%d mes%s' % (delta.months,
                                       'es' if delta.months > 1 else ''))
        if delta.days > 0 or not parts:
            parts.append('%d día%s' % (delta.days,
                                       's' if delta.days != 1 else ''))
        return ', '.join(parts)

    def _get_placeholder_values(self, version):
        """Diccionario controlado de placeholders (nombres v18).

        Cambios v19: el apoderado sale de
        ``hr.main.parameter.reprentante_legal_id`` (res.partner: nombre,
        cargo en ``function``, documento en ``vat``) — v18 usaba
        ``employee_in_charge_id`` — para firmar igual que certificados y
        cartas; ``distrito``/``provincia`` se añaden porque las
        plantillas reales v18 ya los usaban.
        """
        version.ensure_one()
        employee = version.employee_id
        company = version.company_id or employee.company_id
        partner = company.partner_id
        Param = self.env['hr.main.parameter']
        param = Param.get_main_parameter(company)
        legal_rep = param.reprentante_legal_id
        date_letters = self.env['l10n_pe.hr.doc.mixin'].format_date_letters
        district = getattr(partner, 'l10n_pe_district', False)
        return {
            # Datos de la empresa
            'nombre_empleador': company.name or '',
            'ruc_empleador': company.vat or '',
            'direccion_empleador': company.street or '',
            'distrito': district.name if district else '',
            'provincia': partner.city or '',
            'departamento': partner.state_id.name or '',
            'cargo_RL': legal_rep.function or '',
            'apoderado': legal_rep.name or '',
            'dni_apoderado': legal_rep.vat or '',

            # Datos del trabajador
            'nombre_trabajador': employee.name or '',
            'estado_civil_trabajador':
                self._selection_label(version, 'marital'),
            'sexo_trabajador': self._selection_label(version, 'sex'),
            'td_trabajador':
                employee.l10n_latam_identification_type_id.name or '',
            'dni_trabajador': version.identification_id or '',
            'nacionalidad_trabajador': version.country_id.name or '',
            'direccion_trabajador': version.private_street or '',

            # Datos del puesto
            'titulo_trabajo': version.job_id.name
                or version.job_title or '',
            'area': version.department_id.name or '',
            'funciones_empleado': version.job_id.description or '',

            # Remuneración
            'salario': '%.2f' % version.wage if version.wage else '0.00',
            'salario_letras': Param.number_to_letter(version.wage)
                if version.wage else '',
            'moneda': 'Soles',

            # Duración
            'meses': self._duration_string(
                version.contract_date_start, version.contract_date_end),
            'fecha_inicio': date_letters(version.contract_date_start),
            'fecha_fin': date_letters(version.contract_date_end),
            'fecha_prueba_fin': self._duration_string(
                version.contract_date_start,
                version.trial_date_end or version.contract_date_start),

            # Jornada y firma
            'horas_jornada': ('%g' % version.resource_calendar_id
                              .hours_per_day)
                if version.resource_calendar_id.hours_per_day else '8',
            'lugar_contrato': partner.state_id.name or 'Lima',
            'fecha_firma': date_letters(fields.Date.context_today(self)),
        }


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_pe_contract_template_id = fields.Many2one(
        'l10n_pe.hr.contract.template', string='Plantilla de contrato',
        tracking=True,
        domain="['|', ('company_id', '=', False),"
               " ('company_id', '=', company_id)]",
        help='Plantilla HTML con la que se imprime el contrato de '
             'trabajo de esta versión.')
    # LPCL (D.S. 003-97-TR) Art. 10 — Período de prueba: 3 meses el
    # régimen general; hasta 6 (confianza) o 12 (dirección) por pacto
    # escrito (Art. 43).
    l10n_pe_trial_period_regime = fields.Selection(
        selection=[
            ('regular', '3 meses (régimen general)'),
            ('confianza', '6 meses (personal de confianza)'),
            ('direccion', '12 meses (personal de dirección)'),
        ],
        string='Régimen de período de prueba (PE)', default='regular',
        tracking=True,
        help='Duración del período de prueba según LPCL Art. 10. Los '
             'regímenes de 6 y 12 meses requieren pacto escrito en el '
             'contrato (Art. 43 LPCL).')
    # TODO(fase7-revisar): trial_date_end nativo pasa de campo plano a
    # compute almacenado editable; verificar en la BD de prueba que los
    # valores existentes se conservan tras el -u.
    trial_date_end = fields.Date(
        compute='_compute_l10n_pe_trial_date_end', store=True,
        readonly=False,
        help='Fin del período de prueba, calculado del régimen peruano '
             '(LPCL Art. 10). Editable para casos excepcionales '
             '(suspensiones, mutuo acuerdo).')

    @api.depends('contract_date_start', 'l10n_pe_trial_period_regime')
    def _compute_l10n_pe_trial_date_end(self):
        """Fin del período de prueba según el régimen (LPCL Art. 10).

        ``readonly=False``: un valor escrito a mano se conserva mientras
        no cambien la fecha de inicio o el régimen.
        """
        months_by_regime = {'regular': 3, 'confianza': 6, 'direccion': 12}
        for version in self:
            if not version.contract_date_start:
                version.trial_date_end = False
                continue
            months = months_by_regime.get(
                version.l10n_pe_trial_period_regime or 'regular', 3)
            version.trial_date_end = version.contract_date_start \
                + relativedelta(months=months)

    def action_export_contract(self):
        """Imprime el contrato de la versión desde su plantilla.

        Valida antes los datos mínimos (paridad con el checklist v18,
        adaptado a ``hr.version``) con mensajes que indican dónde
        completar cada dato.
        """
        self.ensure_one()
        template = self.l10n_pe_contract_template_id
        if not template:
            raise UserError(self.env._(
                'Seleccione una plantilla de contrato en la pestaña '
                'Nómina del empleado.'))
        if not template.body:
            raise UserError(self.env._(
                'La plantilla de contrato %(template)s no tiene contenido.',
                template=template.display_name))
        company = self.company_id or self.employee_id.company_id
        checks = [
            (company.name, 'Nombre de la empresa (Compañía)'),
            (company.vat, 'RUC de la empresa (Compañía)'),
            (company.street, 'Dirección fiscal (Compañía)'),
            (company.partner_id.state_id,
             'Departamento (Compañía → Contacto)'),
            (self.employee_id.name, 'Nombre del empleado'),
            (self.identification_id,
             'Número de documento (Empleado → Personal)'),
            (self.employee_id.l10n_latam_identification_type_id,
             'Tipo de documento (Empleado → Personal)'),
            (self.private_street,
             'Dirección domiciliaria (Empleado → Personal)'),
            (self.country_id, 'Nacionalidad (Empleado → Personal)'),
            (self.contract_date_start,
             'Fecha de inicio de contrato (Empleado → Nómina)'),
            (self.wage, 'Sueldo (Empleado → Nómina)'),
            (self.job_id, 'Puesto de trabajo (Empleado → Trabajo)'),
            (self.department_id, 'Departamento (Empleado → Trabajo)'),
        ]
        missing = [label for value, label in checks if not value]
        if missing:
            raise UserError(self.env._(
                'No se puede generar el contrato. Faltan estos datos:'
                '\n\n%(missing)s\n\nComplete la información y vuelva a '
                'intentarlo.',
                missing='\n'.join('• %s' % item for item in missing)))
        return self.env.ref(
            'al_hr_pe_reports.action_report_contract').report_action(self)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def action_print_pe_contract(self):
        """Imprime el contrato de la versión vigente del empleado."""
        self.ensure_one()
        return self.version_id.action_export_contract()

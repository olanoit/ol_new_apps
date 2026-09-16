# -*- coding: utf-8 -*-
"""Importación de la tabla salarial del convenio desde su PDF.

La tabla se crea **archivada**: un error de lectura cambiaría el jornal de
toda la planilla, así que la activa una persona tras revisarla. Antes de
crearla se recalculan, con las mismas fórmulas de la boleta, los importes
semanales que publica el propio convenio (CONAFOVICER, pensión y neto de
cada categoría); si uno solo no coincide al céntimo, no se importa nada.
"""
import logging
from decimal import Decimal

import requests
from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command

from odoo.addons.al_hr_pe.tools import custom_round

from ..tools import wage_table_pdf
from .hr_construction_masters import round_percent

_logger = logging.getLogger(__name__)

URLS_PARAM = 'al_hr_pe_construction.wage_table_urls'
CATEGORY_XMLIDS = {
    'operario': 'al_hr_pe_construction.category_operario',
    'oficial': 'al_hr_pe_construction.category_oficial',
    'peon': 'al_hr_pe_construction.category_peon',
}
# Tabla 2026. Cuando se publique el convenio siguiente basta con añadir su
# dirección desde el asistente de importación.
DEFAULT_URLS = (
    'https://www.capeco.org/descargas/CC2026/CAPECO_FTCCP_Remuneraciones%202026_%20FV.pdf',
    'https://www.ftccperu.com/media/attachments/2025/12/30/tablas-salariales-2026-construccion-civil.pdf',
)
# El PDF de CAPECO pesa unos 8 MB.
MAX_PDF_SIZE = 30 * 1024 * 1024
WEEK_DAYS = 6


class L10nPeHrConstructionWageTable(models.Model):
    _inherit = 'l10n_pe.hr.construction.wage.table'

    # ------------------------------------------------------------------
    # Fuente
    # ------------------------------------------------------------------
    @api.model
    def _l10n_pe_watched_urls(self):
        """Direcciones que revisa la acción planificada, una por línea."""
        value = self.env['ir.config_parameter'].sudo().get_param(URLS_PARAM)
        if value is False:
            # Nunca configurado: las direcciones conocidas. Un valor vacío,
            # en cambio, es que el usuario las quitó todas.
            return list(DEFAULT_URLS)
        return [line.strip() for line in value.splitlines()
                if line.strip() and not line.strip().startswith('#')]

    @api.model
    def _l10n_pe_download_pdf(self, url):
        try:
            # Sin un User-Agent de navegador, CAPECO responde 406.
            response = requests.get(url, timeout=60, stream=True, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; Odoo)'})
            response.raise_for_status()
            content = b''
            for chunk in response.iter_content(chunk_size=65536):
                content += chunk
                if len(content) > MAX_PDF_SIZE:
                    raise UserError(_('El PDF de %(url)s supera los 30 MB.', url=url))
        except requests.RequestException as error:
            raise UserError(_('No se pudo descargar %(url)s: %(error)s',
                              url=url, error=error)) from error
        return content

    # ------------------------------------------------------------------
    # Lectura y comprobación
    # ------------------------------------------------------------------
    @api.model
    def _l10n_pe_check_parsed(self, data):
        """Errores entre lo que publica el convenio y lo que calcula Odoo."""
        Line = self.env['l10n_pe.hr.construction.wage.line']
        errors = []
        for key, values in data['categories'].items():
            category = self.env.ref(CATEGORY_XMLIDS[key])
            line = Line.new({
                'category_id': category.id,
                'daily_wage': values['daily_wage'],
                'mobility_amount': values['mobility'],
                'buc_percent': values['buc_percent'],
            })
            amounts = line._period_amounts(WEEK_DAYS)
            conafovicer = round_percent(amounts['jornal'] + amounts['dso'],
                                        values['conafovicer_rate'])
            pension = round_percent(
                amounts['jornal'] + amounts['dso'] + amounts['buc'],
                values['pension_rate'])
            net = self._l10n_pe_published_net(values)
            for label, computed, published in (
                    (_('CONAFOVICER'), conafovicer, values['conafovicer']),
                    (_('pensión'), pension, values['pension']),
                    (_('neto semanal'), net, values['net'])):
                if abs(computed - published) > 0.005:
                    errors.append(_(
                        '%(category)s: %(label)s calculado %(computed).2f, '
                        'el convenio publica %(published).2f.',
                        category=category.name, label=label,
                        computed=computed, published=published))
        return errors

    @api.model
    def _l10n_pe_published_net(self, values):
        """Neto semanal como lo calcula el convenio.

        El convenio redondea el neto **una sola vez**, sobre los componentes
        sin redondear: con las líneas ya redondeadas el operario 2026 daría
        732.11 y el peón 523.61, y la tabla publica 732.10 y 523.60.
        """
        base = Decimal(str(values['daily_wage'])) * WEEK_DAYS
        dso = base / WEEK_DAYS
        buc = base * Decimal(str(values['buc_percent'])) / 100
        mobility = Decimal(str(values['mobility'])) * WEEK_DAYS
        conafovicer = (base + dso) * Decimal(str(values['conafovicer_rate'])) / 100
        pension = (base + dso + buc) * Decimal(str(values['pension_rate'])) / 100
        return custom_round(base + dso + buc + mobility - conafovicer - pension)

    @api.model
    def _l10n_pe_create_from_pdf(self, content, source):
        """Crea la tabla archivada desde el PDF.

        Devuelve ``(tabla, creada)``. Si ya hay una tabla nacional con la
        misma vigencia —activa o archivada— la devuelve sin tocarla.
        """
        try:
            data = wage_table_pdf.parse_pdf(content)
        except wage_table_pdf.WageTablePdfError as error:
            raise UserError(_('%(source)s no trae una tabla salarial '
                              'reconocible: %(error)s',
                              source=source, error=error)) from error
        errors = self._l10n_pe_check_parsed(data)
        if errors:
            raise UserError(_(
                'La tabla de %(source)s no cuadra con los cálculos del '
                'módulo; no se importó:\n%(errors)s',
                source=source, errors='\n'.join(errors)))

        existing = self.with_context(active_test=False).search([
            ('company_id', '=', False),
            ('date_from', '=', data['date_from']),
            ('date_to', '=', data['date_to']),
        ], limit=1)
        if existing:
            return existing, False

        years = sorted({data['date_from'].year, data['date_to'].year})
        lines = []
        for key, values in data['categories'].items():
            category = self.env.ref(CATEGORY_XMLIDS[key])
            lines.append(Command.create({
                'category_id': category.id,
                'daily_wage': values['daily_wage'],
                'mobility_amount': values['mobility'],
                # Vacío = el de la categoría; solo se fija si el convenio
                # lo cambia.
                'buc_percent': (0.0 if values['buc_percent'] == category.buc_percent
                                else values['buc_percent']),
            }))
        table = self.create({
            'name': _('Convención colectiva %s', '-'.join(map(str, years))),
            'resolution': data['resolution'],
            'date_from': data['date_from'],
            'date_to': data['date_to'],
            'source_url': source,
            'active': False,
            'line_ids': lines,
            'note': _('Importada del PDF del convenio. Revise los jornales '
                      'y active la tabla para que la planilla la use.'),
        })
        table._l10n_pe_post_import_message(data)
        return table, True

    def _l10n_pe_post_import_message(self, data):
        self.ensure_one()
        rate = data['categories']['operario']['conafovicer_rate']
        rows = Markup('').join(
            Markup('<li>%s: jornal %.2f, movilidad %.2f, BUC %s %%</li>') % (
                self.env.ref(CATEGORY_XMLIDS[key]).name, values['daily_wage'],
                values['mobility'], values['buc_percent'])
            for key, values in data['categories'].items())
        body = Markup('<p>%s</p><ul>%s</ul>') % (
            _('Tabla importada de %s. Los importes semanales del convenio '
              'cuadran con los del módulo.', self.source_url), rows)
        companies = self.env['res.company'].sudo().search([
            ('partner_id.country_id.code', '=', 'PE')])
        different = companies.filtered(
            lambda company: abs(company.l10n_pe_conafovicer_rate - rate) > 0.001)
        if different:
            body += Markup('<p><strong>%s</strong></p>') % _(
                'El convenio aplica un CONAFOVICER de %(rate)s %% y estas '
                'compañías tienen otra tasa: %(companies)s.',
                rate=rate, companies=', '.join(different.mapped('name')))
        self.message_post(body=body)

    # ------------------------------------------------------------------
    # Acción planificada
    # ------------------------------------------------------------------
    def _l10n_pe_schedule_review(self):
        group = self.env.ref('hr_payroll.group_hr_payroll_manager')
        managers = self.env['res.users'].search([
            ('all_group_ids', 'in', group.id), ('share', '=', False)])
        for table in self:
            for user in managers:
                table.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=user.id,
                    summary=_('Revisar y activar la tabla salarial'),
                    note=escape(_('Se importó %(table)s desde %(source)s. '
                                  'Compruebe los jornales y actívela.',
                                  table=table.name, source=table.source_url)))

    @api.model
    def _l10n_pe_check_watched_urls(self):
        """Revisa las direcciones configuradas; devuelve las tablas nuevas."""
        created_tables = self.browse()
        for url in self._l10n_pe_watched_urls():
            try:
                with self.env.cr.savepoint():
                    content = self._l10n_pe_download_pdf(url)
                    table, created = self._l10n_pe_create_from_pdf(content, url)
            except UserError as error:
                _logger.warning('Tabla salarial de construcción civil: %s', error)
                continue
            if created:
                created_tables |= table
        created_tables._l10n_pe_schedule_review()
        return created_tables

    @api.model
    def _cron_l10n_pe_check_wage_tables(self):
        self._l10n_pe_check_watched_urls()

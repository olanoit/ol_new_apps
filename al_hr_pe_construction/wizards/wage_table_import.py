# -*- coding: utf-8 -*-
import base64

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.hr_construction_wage_import import URLS_PARAM


class L10nPeHrConstructionWageImport(models.TransientModel):
    _name = 'l10n_pe.hr.construction.wage.import'
    _description = 'Importar tabla salarial del convenio'

    source = fields.Selection(
        [('file', 'Archivo PDF'), ('url', 'Dirección web')],
        string='Origen', default='file', required=True)
    pdf_file = fields.Binary(string='PDF del convenio')
    pdf_filename = fields.Char(string='Nombre del archivo')
    url = fields.Char(
        string='Dirección del PDF',
        help='Enlace directo al PDF de la tabla salarial de CAPECO o de la '
             'FTCCP.')
    watch_url = fields.Boolean(
        string='Revisar esta dirección cada mes', default=True,
        help='La añade a las direcciones que revisa la acción planificada.')
    watched_urls = fields.Text(
        string='Direcciones que se revisan cada mes',
        default=lambda self: '\n'.join(
            self.env['l10n_pe.hr.construction.wage.table']._l10n_pe_watched_urls()),
        help='Una por línea. Cada mes se descargan y, si publican un convenio '
             'con una vigencia que aún no está cargada, se importa archivado '
             'y se crea una actividad para los responsables de planillas.')

    @api.onchange('source')
    def _onchange_source(self):
        if self.source == 'file':
            self.url = False
        else:
            self.pdf_file = False

    def _save_watched_urls(self, extra=None):
        urls = [line.strip() for line in (self.watched_urls or '').splitlines()
                if line.strip()]
        if extra and extra not in urls:
            urls.append(extra)
        self.env['ir.config_parameter'].sudo().set_param(URLS_PARAM, '\n'.join(urls))

    def action_import(self):
        self.ensure_one()
        Table = self.env['l10n_pe.hr.construction.wage.table']
        if self.source == 'url':
            if not self.url:
                raise UserError(_('Indique la dirección del PDF.'))
            url = self.url.strip()
            content, source = Table._l10n_pe_download_pdf(url), url
        else:
            if not self.pdf_file:
                raise UserError(_('Adjunte el PDF del convenio.'))
            content = base64.b64decode(self.pdf_file)
            source = self.pdf_filename or _('archivo subido')
        table, created = Table._l10n_pe_create_from_pdf(content, source)
        self._save_watched_urls(
            url if self.source == 'url' and self.watch_url else None)
        if not created:
            raise UserError(_(
                'Ya existe la tabla %(table)s con la vigencia del %(date_from)s '
                'al %(date_to)s (activa o archivada); no se importó otra.',
                table=table.name, date_from=table.date_from, date_to=table.date_to))
        return {
            'type': 'ir.actions.act_window',
            'res_model': table._name,
            'res_id': table.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_check_now(self):
        """Guarda las direcciones y las revisa en el acto."""
        self.ensure_one()
        self._save_watched_urls()
        tables = self.env['l10n_pe.hr.construction.wage.table']._l10n_pe_check_watched_urls()
        message = (_('Se importaron %s tabla(s) nueva(s), archivadas para revisión.', len(tables))
                   if tables else
                   _('No hay convenios nuevos en las direcciones configuradas.'))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Tablas salariales'),
                'message': message,
                'type': 'success' if tables else 'info',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

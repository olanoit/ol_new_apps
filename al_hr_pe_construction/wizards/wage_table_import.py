# -*- coding: utf-8 -*-
import base64

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.hr_construction_wage_import import URLS_PARAM


class L10nPeHrConstructionWageImport(models.TransientModel):
    _name = 'l10n_pe.hr.construction.wage.import'
    _description = 'Importar tabla salarial del convenio'

    state = fields.Selection(
        [('upload', 'Origen'), ('confirm', 'Actualizar')],
        default='upload', required=True)
    source = fields.Selection(
        [('file', 'Archivo PDF'), ('url', 'Dirección web')],
        string='Origen', default='file', required=True)
    pdf_file = fields.Binary(string='PDF del convenio')
    pdf_filename = fields.Char(string='Nombre del archivo')
    url = fields.Char(
        string='Dirección del PDF',
        help='Enlace directo al PDF de la tabla salarial de CAPECO o de la '
             'FTCCP. Al elegir «Dirección web» se propone la primera de las '
             'que se revisan cada mes.')
    watch_url = fields.Boolean(
        string='Revisar esta dirección cada mes', default=True,
        help='La añade a las direcciones que revisa la acción planificada.')
    watched_urls = fields.Text(
        string='Direcciones que se revisan cada mes',
        default=lambda self: '\n'.join(self._watched_url_list()),
        help='Una por línea. Cada mes se descargan y, si publican un convenio '
             'con una vigencia que aún no está cargada, se importa archivado '
             'y se crea una actividad para los responsables de planillas.')

    # Segundo paso: la vigencia ya existe y se pide confirmar la
    # actualización. El PDF se guarda para no descargarlo dos veces.
    pdf_content = fields.Binary(attachment=False)
    source_label = fields.Char()
    existing_table_id = fields.Many2one(
        'l10n_pe.hr.construction.wage.table', string='Tabla existente',
        readonly=True)
    changes_html = fields.Html(string='Cambios', readonly=True, sanitize=False)
    has_changes = fields.Boolean(readonly=True)

    @api.model
    def _watched_url_list(self):
        return self.env['l10n_pe.hr.construction.wage.table']._l10n_pe_watched_urls()

    @api.onchange('source')
    def _onchange_source(self):
        if self.source == 'file':
            self.url = False
        else:
            self.pdf_file = False
            if not self.url:
                urls = [line.strip() for line in (self.watched_urls or '').splitlines()
                        if line.strip()] or self._watched_url_list()
                self.url = urls[0] if urls else False

    def _save_watched_urls(self, extra=None):
        urls = [line.strip() for line in (self.watched_urls or '').splitlines()
                if line.strip()]
        if extra and extra not in urls:
            urls.append(extra)
        self.env['ir.config_parameter'].sudo().set_param(URLS_PARAM, '\n'.join(urls))

    def _read_source(self):
        """Contenido del PDF y cómo se cita en el historial."""
        Table = self.env['l10n_pe.hr.construction.wage.table']
        if self.source == 'url':
            if not self.url:
                raise UserError(_('Indique la dirección del PDF.'))
            url = self.url.strip()
            return Table._l10n_pe_download_pdf(url), url
        if not self.pdf_file:
            raise UserError(_('Adjunte el PDF del convenio.'))
        return (base64.b64decode(self.pdf_file),
                self.pdf_filename or _('archivo subido'))

    @staticmethod
    def _open(record):
        return {
            'type': 'ir.actions.act_window',
            'res_model': record._name,
            'res_id': record.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'name': _('Importar tabla del convenio'),
        }

    @staticmethod
    def _changes_table(changes):
        if not changes:
            return Markup('')
        rows = Markup('').join(
            Markup('<tr><td>%s</td><td>%s</td><td class="text-end">%s</td>'
                   '<td class="text-end"><strong>%s</strong></td></tr>') % (
                category, label, '—' if current in (None, '') else current, new)
            for category, label, current, new in changes)
        return Markup(
            '<table class="table table-sm"><thead><tr><th>Categoría</th>'
            '<th>Concepto</th><th class="text-end">Actual</th>'
            '<th class="text-end">Nuevo</th></tr></thead><tbody>%s</tbody></table>'
        ) % rows

    def action_import(self):
        self.ensure_one()
        Table = self.env['l10n_pe.hr.construction.wage.table']
        content, source = self._read_source()
        data = Table._l10n_pe_read_pdf(content, source)
        self._save_watched_urls(
            source if self.source == 'url' and self.watch_url else None)
        existing = Table._l10n_pe_find_existing(data)
        if not existing:
            return self._open(Table._l10n_pe_create_from_data(data, source))
        changes = existing._l10n_pe_diff(data)
        self.write({
            'state': 'confirm',
            'pdf_content': base64.b64encode(content),
            'source_label': source,
            'existing_table_id': existing.id,
            'has_changes': bool(changes),
            'changes_html': self._changes_table(changes),
        })
        return self._reopen()

    def action_update_existing(self):
        self.ensure_one()
        Table = self.env['l10n_pe.hr.construction.wage.table']
        if not (self.existing_table_id and self.pdf_content):
            raise UserError(_('Vuelva a importar el PDF.'))
        data = Table._l10n_pe_read_pdf(base64.b64decode(self.pdf_content),
                                       self.source_label)
        table = self.existing_table_id
        if Table._l10n_pe_find_existing(data) != table:
            raise UserError(_('El PDF ya no corresponde a %s.', table.display_name))
        table._l10n_pe_update_from_data(data, self.source_label)
        return self._open(table)

    def action_back(self):
        self.ensure_one()
        self.write({'state': 'upload', 'pdf_content': False,
                    'existing_table_id': False, 'changes_html': False})
        return self._reopen()

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

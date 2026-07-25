# -*- coding: utf-8 -*-
"""Modelo persistente de progreso para importaciones de planillas.

El registro se crea desde el wizard antes de lanzar el hilo de importación
y se va actualizando fila a fila desde un cursor independiente, para que
el widget OWL haga polling y muestre la barra de progreso en tiempo real.

v19: se añade ``company_id`` (multicompañía; el historial se acota con
una ir.rule por compañía).
"""
from odoo import fields, models
from odoo.exceptions import UserError


class ImportPayrollProgress(models.Model):
    _name = 'al.import.payroll.progress'
    _description = 'Progreso de importación de planillas'
    _order = 'create_date desc'

    name = fields.Char(default='Importación')

    # Identifica el wizard origen para volver a abrirlo si hace falta.
    wizard_model = fields.Char(string='Modelo del wizard', required=True)
    wizard_id = fields.Integer(string='ID del wizard', required=True)
    target_model = fields.Char(string='Modelo destino')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)

    status = fields.Selection(
        [
            ('pending', 'Pendiente'),
            ('running', 'Procesando'),
            ('done', 'Completado'),
            ('error', 'Error'),
        ],
        default='pending',
        required=True,
        string='Estado',
    )

    total = fields.Integer(string='Total', default=0)
    current = fields.Integer(string='Procesados', default=0)
    created = fields.Integer(string='Creados', default=0)
    updated = fields.Integer(string='Actualizados', default=0)
    skipped = fields.Integer(string='Omitidos', default=0)
    errors = fields.Integer(string='Errores', default=0)

    message = fields.Char(
        string='Mensaje', default='Preparando importación...')
    error_detail = fields.Text(string='Detalle del error')
    log = fields.Text(string='Log de procesamiento')

    date_start = fields.Datetime(readonly=True)
    date_end = fields.Datetime(readonly=True)

    report_file = fields.Binary(
        string='Reporte Excel',
        attachment=True,
        readonly=True,
    )
    report_filename = fields.Char(readonly=True)

    # IDs de los registros creados/actualizados (target_model). Se llena
    # al final del hilo. Se guarda como CSV simple para evitar Many2many
    # con un modelo genérico.
    created_res_ids_csv = fields.Char(
        string='IDs creados/actualizados',
        readonly=True,
    )

    # === API para el widget OWL =========================================== #

    def get_progress_data(self):
        """Llamado vía RPC por el widget OWL cada segundo."""
        self.ensure_one()
        percent = round(self.current / self.total * 100) if self.total else 0
        return {
            'total': self.total,
            'current': self.current,
            'created': self.created,
            'updated': self.updated,
            'skipped': self.skipped,
            'errors': self.errors,
            'status': self.status,
            'message': self.message or '',
            'percent': min(percent, 100),
            'error_detail': self.error_detail or '',
            'has_report': bool(self.report_file),
            'has_records': bool(self._created_ids_list()),
            'wizard_model': self.wizard_model,
            'wizard_id': self.wizard_id,
            'target_model': self.target_model,
        }

    def _created_ids_list(self):
        self.ensure_one()
        if not self.created_res_ids_csv:
            return []
        try:
            return [
                int(x) for x in self.created_res_ids_csv.split(',')
                if x.strip().isdigit()
            ]
        except Exception:
            return []

    def action_download_report(self):
        self.ensure_one()
        if not self.report_file:
            raise UserError(self.env._('Aún no hay reporte disponible.'))
        return {
            'type': 'ir.actions.act_url',
            'url': (
                '/web/content/?model=%s&id=%s&field=report_file'
                '&filename_field=report_filename&download=true'
            ) % (self._name, self.id),
            'target': 'self',
        }

    def action_view_target_records(self):
        """Abre la list view del target_model filtrada por los IDs
        procesados."""
        self.ensure_one()
        if not self.target_model:
            raise UserError(self.env._('No hay modelo destino registrado.'))
        ids = self._created_ids_list()
        if not ids:
            raise UserError(self.env._(
                'No se registraron IDs creados o actualizados durante la '
                'importación.'))
        # ``views`` debe ser explícito: cuando el action viene de una
        # llamada RPC directa (no de _for_xml_id) el cliente web no lo
        # auto-completa y _preprocessAction falla.
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Registros procesados'),
            'res_model': self.target_model,
            'views': [(False, 'list'), (False, 'form')],
            'view_mode': 'list,form',
            'domain': [('id', 'in', ids)],
            'target': 'current',
        }

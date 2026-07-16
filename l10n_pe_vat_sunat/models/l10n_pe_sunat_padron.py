# -*- coding: utf-8 -*-
"""Caché en BD del padrón SUNAT (buenos contribuyentes / agentes de retención).

Antes de este modelo, cada apertura de un form de ``res.partner``
desencadenaba la descarga completa del ZIP (~5-50 MB) desde SUNAT
para verificar si el RUC estaba listado. A escala (cientos de
partners + varios usuarios) esto provocaba:

  * Saturación del ancho de banda de SUNAT (con bloqueos por abuso).
  * Latencia de varios segundos en cada form.open.
  * Re-trabajo masivo (el padrón cambia con frecuencia mensual).

Solución: descargar el padrón una vez al día mediante un
``ir.cron``, persistir los RUCs en este modelo y dejar las consultas
del partner como un simple ``search_count`` indexado (~ms).
"""
from odoo import _, api, fields, models


class L10nPeSunatPadron(models.Model):
    _name = 'l10n_pe.sunat.padron'
    _description = 'Padrón SUNAT (buenos contribuyentes y agentes de retención)'
    _order = 'kind, vat'
    _rec_name = 'vat'

    kind = fields.Selection(
        [
            ('good_taxpayer', 'Buen contribuyente'),
            ('retention_agent', 'Agente de retención'),
        ],
        string='Tipo de padrón',
        required=True,
        index=True,
    )
    vat = fields.Char(
        string='RUC',
        required=True,
        index=True,
        size=11,
    )
    last_sync = fields.Datetime(
        string='Última sincronización',
        default=fields.Datetime.now,
        readonly=True,
    )

    _sql_constraints = [
        ('uniq_kind_vat',
         'unique(kind, vat)',
         'Ya existe una entrada para este RUC en este padrón.'),
    ]

    # ------------------------------------------------------------------ #
    # Acciones (botón Run Manually en el cron)                            #
    # ------------------------------------------------------------------ #

    @api.model
    def cron_sync_padron(self):
        """Llamado por el ``ir.cron`` diario. Sincroniza ambos padrones."""
        # Import diferido — evita ciclo con services/__init__.py.
        from ..services import sunat_padron
        return sunat_padron.sync(self.env)

    @api.model
    def action_sync_now(self):
        """Acción manual desde la list view."""
        from ..services import sunat_padron
        counts = sunat_padron.sync(self.env)
        message = _(
            'Padrón sincronizado:\n'
            '  • Buenos contribuyentes: %(g)d\n'
            '  • Agentes de retención: %(r)d'
        ) % {
            'g': counts.get('good_taxpayer', 0),
            'r': counts.get('retention_agent', 0),
        }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Padrón SUNAT'),
                'message': message,
                'type': 'success',
                'sticky': False,
            },
        }

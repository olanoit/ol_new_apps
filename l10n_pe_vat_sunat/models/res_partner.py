# -*- coding: utf-8 -*-
"""Thin model: sólo fields, onchanges y entry points.

Toda la lógica de red/scraping/parsing vive en ``services/`` y se
invoca aquí. El objetivo es que este archivo sea menor a 300 líneas
y fácil de auditar.

Compatibilidad: se preservan los nombres de campos públicos del
módulo legacy (``state``, ``sunat_condition``, ``is_good_taxpayer``,
``is_retention_agent``, ``commercial_name``, ``alert_warning_vat``)
para no romper vistas/reportes/datos existentes.
"""
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services import (
    http as http_service,
    sunat_padron,
)

_logger = logging.getLogger(__name__)


REGEX_RUC = re.compile(r'^(10|15|17|20)\d{9}$')
REGEX_DNI = re.compile(r'^\d{8}$')


# Selecciones (compatibilidad con datos existentes — no renombrar).
SUNAT_STATE = [
    ('ACTIVO', 'ACTIVO'),
    ('BAJA DE OFICIO', 'BAJA DE OFICIO'),
    ('BAJA DEFINITIVA', 'BAJA DEFINITIVA'),
    ('BAJA PROVISIONAL', 'BAJA PROVISIONAL'),
    ('SUSPENSION TEMPORAL', 'SUSPENSION TEMPORAL'),
    ('INHABILITADO-VENT.UN', 'INHABILITADO-VENT.UN'),
    ('BAJA MULT.INSCR. Y O', 'BAJA MULT.INSCR. Y O'),
    ('PENDIENTE DE INI. DE', 'PENDIENTE DE INI. DE'),
    ('OTROS OBLIGADOS', 'OTROS OBLIGADOS'),
    ('NUM. INTERNO IDENTIF', 'NUM. INTERNO IDENTIF'),
    ('ANUL.PROVI.-ACTO ILI', 'ANUL.PROVI.-ACTO ILI'),
    ('ANULACION - ACTO ILI', 'ANULACION - ACTO ILI'),
    ('BAJA PROV. POR OFICIO', 'BAJA PROV. POR OFICIO'),
    ('ANULACION - ERROR SU', 'ANULACION - ERROR SU'),
    ('', 'NO ACTIVO'),
]

SUNAT_CONDITION = [
    ('HABIDO', 'HABIDO'),
    ('NO HABIDO', 'NO HABIDO'),
    ('NO HALLADO', 'NO HALLADO'),
    ('PENDIENTE', 'PENDIENTE'),
    ('NO HALLADO SE MUDO D', 'NO HALLADO SE MUDO D'),
    ('NO HALLADO NO EXISTE', 'NO HALLADO NO EXISTE'),
    ('NO HALLADO FALLECIO', 'NO HALLADO FALLECIO'),
    ('NO HALLADO OTROS MOT', 'NO HALLADO OTROS MOT'),
    ('NO APLICABLE', 'NO APLICABLE'),
    ('NO HALLADO NRO.PUERT', 'NO HALLADO NRO.PUERT'),
    ('NO HALLADO CERRADO', 'NO HALLADO CERRADO'),
    ('POR VERIFICAR', 'POR VERIFICAR'),
    ('NO HALLADO DESTINATA', 'NO HALLADO DESTINATA'),
    ('NO HALLADO RECHAZADO', 'NO HALLADO RECHAZADO'),
    ('-', 'NO HABIDO'),
    ('', 'NO HABIDO'),
]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # === Campos SUNAT ============================================ #
    # NOTA: el nombre del campo ``state`` colisiona con el patrón de
    # Odoo pero se conserva por compatibilidad con instalaciones
    # legacy del módulo. Internamente sólo se usa con ``write/read``,
    # no afecta a ``state_id`` (geográfico) ni al campo computado de
    # otros módulos.
    state = fields.Selection(
        SUNAT_STATE,
        string='Estado SUNAT',
        default='ACTIVO',
    )
    sunat_condition = fields.Selection(
        SUNAT_CONDITION,
        string='Condición SUNAT',
    )
    commercial_name = fields.Char(string='Nombre comercial')
    alert_warning_vat = fields.Boolean(
        string='Alerta API',
        default=False,
        help='Se marca cuando la última consulta a SUNAT/API falló. '
             'El usuario debe completar los datos manualmente.',
    )
    is_good_taxpayer = fields.Boolean(
        string='Buen contribuyente',
        help='Verificado contra el padrón SUNAT (caché diaria).',
    )
    is_retention_agent = fields.Boolean(
        string='Agente de retención',
        help='Verificado contra el padrón SUNAT (caché diaria).',
    )

    # `ref` con default del VAT; `country_id` con default de la compañía.
    ref = fields.Char(
        string='Reference',
        index=True,
        default=lambda self: self.vat or False,
    )
    country_id = fields.Many2one(
        default=lambda self: self.env.company.country_id.id,
    )

    # ============================================================ #
    # Onchange / entry point                                        #
    # ============================================================ #

    @api.onchange('company_type')
    def _onchange_company_type_sunat(self):
        """Setea el tipo de documento por defecto según company_type."""
        if self.vat:
            return
        IdType = self.env['l10n_latam.identification.type']
        if self.company_type == 'person':
            rec = self.env.ref('l10n_pe.it_DNI', raise_if_not_found=False)
        else:
            rec = self.env.ref('l10n_pe.it_RUC', raise_if_not_found=False)
        if rec:
            self.l10n_latam_identification_type_id = rec.id

    @api.onchange('parent_id')
    def _onchange_parent_id_address(self):
        """Hereda dirección del partner padre (caso contactos)."""
        if self.parent_id:
            self.city_id = self.parent_id.city_id.id
            self.l10n_pe_district = self.parent_id.l10n_pe_district.id

    @api.onchange('vat', 'l10n_latam_identification_type_id')
    def _doc_number_change(self):
        """Consulta automática al escribir (onchange): silenciosa, solo marca
        alerta si falla — no interrumpe la edición."""
        self._run_document_lookup(raise_on_fail=False)

    def _run_document_lookup(self, raise_on_fail=False):
        if not self.vat or not self.l10n_latam_identification_type_id:
            return
        # Sólo si la compañía habilitó validación.
        company = self.env.company
        vat = (self.vat or '').strip()
        vat_code = self.l10n_latam_identification_type_id.l10n_pe_vat_code
        if vat_code == '1' and company.l10n_pe_dni_validation:
            self._validate_dni(vat)
            self._fetch_document('dni', raise_on_fail=raise_on_fail)
        elif vat_code == '6' and company.l10n_pe_ruc_validation:
            self._validate_ruc(vat)
            self._fetch_document('ruc', raise_on_fail=raise_on_fail)

    def btn_update_document(self):
        """Botón "Actualizar RUC/DNI": si falla, muestra el motivo real."""
        for partner in self:
            partner._run_document_lookup(raise_on_fail=True)

    # ============================================================ #
    # Validación de formato                                         #
    # ============================================================ #

    @staticmethod
    def _validate_dni(vat):
        if not REGEX_DNI.match(vat):
            raise UserError(_('El DNI ingresado no es válido (8 dígitos).'))

    @staticmethod
    def _validate_ruc(vat):
        if not REGEX_RUC.match(vat):
            raise UserError(_(
                'El RUC ingresado no es válido (11 dígitos, '
                'inicia con 10/15/17/20).'
            ))

    # ============================================================ #
    # Despacho a conexiones configuradas (config-driven)           #
    # ============================================================ #

    def _fetch_document(self, doc_type, raise_on_fail=False):
        """Consulta el documento recorriendo las conexiones de la compañía
        por prioridad; usa la primera que responda (fallback en cascada).

        Si todas fallan y ``raise_on_fail`` (botón manual), lanza un
        ``UserError`` con el motivo real de la última conexión; si no
        (onchange automático), solo marca la alerta sin interrumpir.
        """
        self.ensure_one()
        company = self.env.company
        connections = company._get_pe_api_connections(doc_type)
        if not connections:
            self.alert_warning_vat = True
            msg = self.env._(
                'No hay ninguna conexión de %(doc)s activa y utilizable. '
                'Configúrala en Ajustes ▸ Conexiones RUC/DNI.',
                doc=doc_type.upper())
            _logger.warning(msg)
            if raise_on_fail:
                raise UserError(msg)
            return
        document = (self.vat or '').strip()
        last_exc = None
        for connection in connections:
            try:
                vals, extra = connection.run(document, doc_type)
            except (http_service.HttpError, UserError, ValueError) as exc:
                last_exc = exc
                _logger.warning('[%s] Consulta %s %s falló: %s',
                                connection.name, doc_type.upper(), document, exc)
                continue
            self._apply_api_result(doc_type, vals, extra)
            return
        # Todas las conexiones fallaron.
        self.alert_warning_vat = True
        _logger.warning('Todas las conexiones de %s fallaron para %s.',
                        doc_type.upper(), document)
        if raise_on_fail and last_exc:
            raise UserError(self.env._(
                'No se pudo consultar el %(doc)s %(num)s:\n\n%(err)s',
                doc=doc_type.upper(), num=document, err=str(last_exc)))

    # Compatibilidad con llamadas previas.
    def _fetch_ruc(self):
        return self._fetch_document('ruc')

    def _fetch_dni(self):
        return self._fetch_document('dni')

    # ============================================================ #
    # Aplicar resultado de la API al partner                        #
    # ============================================================ #

    def _apply_api_result(self, doc_type, vals, extra):
        """Escribe el dict mapeado y post-procesa estructuras especiales."""
        self.ensure_one()
        vals = dict(vals or {})
        vals.setdefault('company_type', 'person' if doc_type == 'dni' else 'company')
        vals['alert_warning_vat'] = False
        # No sobrescribir el nombre con vacío.
        if not (vals.get('name') or '').strip():
            vals.pop('name', None)
        self.write(vals)

        if doc_type == 'ruc':
            if extra.get('legal_representatives') and self.is_company:
                self._sync_legal_representatives(extra['legal_representatives'])
            if extra.get('annexed_locals') and self.is_company:
                self._sync_annexed_locals(extra['annexed_locals'])
            # Padrón SUNAT (caché diaria).
            self.is_good_taxpayer = sunat_padron.is_good_taxpayer(self.env, self.vat)
            self.is_retention_agent = sunat_padron.is_retention_agent(self.env, self.vat)

    def _sync_legal_representatives(self, reps):
        """Crea como child_ids los representantes con cargos relevantes."""
        relevant = {'GERENTE GENERAL', 'TITULAR-GERENTE', 'GERENTE', 'APODERADO'}
        existing_names = set(self.child_ids.mapped('name'))
        creates = []
        for rep in reps:
            position = (rep.get('position') or '').upper()
            name = (rep.get('name') or '').strip()
            if not name or position not in relevant or name in existing_names:
                continue
            creates.append({
                'name': name,
                'function': position,
                'type': 'contact',
                'parent_id': self.id,
                'is_company': False,
            })
        if creates:
            self.env['res.partner'].create(creates)

    def _sync_annexed_locals(self, locals_):
        """Crea como child_ids los locales anexos."""
        existing_names = set(self.child_ids.mapped('name'))
        creates = []
        for local in locals_:
            label = '%s - %s' % (local.get('code', ''), local.get('type', ''))
            if label in existing_names:
                continue
            creates.append({
                'name': label,
                'street': local.get('address', ''),
                'type': 'delivery',
                'parent_id': self.id,
                'is_company': False,
            })
        if creates:
            self.env['res.partner'].create(creates)

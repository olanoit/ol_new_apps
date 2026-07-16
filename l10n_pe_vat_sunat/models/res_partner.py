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
    providers,
    sunat_padron,
    ubigeo,
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
        """Dispara la consulta automática a la API si está habilitada."""
        if not self.vat or not self.l10n_latam_identification_type_id:
            return
        # Sólo si la compañía habilitó validación.
        company = self.env.company
        vat = (self.vat or '').strip()
        vat_code = self.l10n_latam_identification_type_id.l10n_pe_vat_code
        if vat_code == '1' and company.l10n_pe_dni_validation:
            self._validate_dni(vat)
            self._fetch_dni()
        elif vat_code == '6' and company.l10n_pe_ruc_validation:
            self._validate_ruc(vat)
            self._fetch_ruc()

    def btn_update_document(self):
        """Botón "Update RUC/DNI" del form."""
        for partner in self:
            partner._doc_number_change()

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
    # Despacho a proveedor (Strategy pattern)                       #
    # ============================================================ #

    def _fetch_ruc(self):
        """Consulta el RUC en el proveedor configurado en la compañía."""
        company = self.env.company
        provider_code = company.l10n_pe_api_ruc_connection or 'api_peru'
        try:
            provider = providers.get_ruc_provider(self.env, provider_code)
            result = provider.fetch((self.vat or '').strip())
        except (http_service.HttpError, ValueError) as exc:
            _logger.warning(
                '[%s] Consulta RUC %s falló: %s',
                provider_code, self.vat, exc,
            )
            self.alert_warning_vat = True
            return

        self._apply_ruc_result(result)
        # Padrón SUNAT (caché diaria, no descarga ZIP en este momento).
        self.is_good_taxpayer = sunat_padron.is_good_taxpayer(
            self.env, self.vat,
        )
        self.is_retention_agent = sunat_padron.is_retention_agent(
            self.env, self.vat,
        )

    def _fetch_dni(self):
        """Consulta el DNI en el proveedor configurado en la compañía."""
        company = self.env.company
        provider_code = company.l10n_pe_api_dni_connection or 'api_peru'
        try:
            provider = providers.get_dni_provider(self.env, provider_code)
            result = provider.fetch((self.vat or '').strip())
        except (http_service.HttpError, ValueError) as exc:
            _logger.warning(
                '[%s] Consulta DNI %s falló: %s',
                provider_code, self.vat, exc,
            )
            self.alert_warning_vat = True
            return

        if result.full_name:
            self.name = result.full_name
            self.company_type = 'person'
            self.alert_warning_vat = False

    # ============================================================ #
    # Aplicar resultado RUC al partner                              #
    # ============================================================ #

    def _apply_ruc_result(self, result):
        """Vuelca un ``RucResult`` sobre el partner.

        - Resuelve el ubigeo (preferentemente por código).
        - Crea contactos hijos para representantes legales y locales
          anexos cuando vienen poblados.
        """
        vals = {
            'name': result.name or self.name,
            'commercial_name': result.commercial_name or self.commercial_name,
            'state': result.state or self.state,
            'sunat_condition': result.condition or self.sunat_condition,
            'company_type': 'company',
            'alert_warning_vat': False,
        }
        if result.address:
            vals['street'] = result.address

        # Ubigeo
        ubi_vals = ubigeo.resolve(
            self.env,
            ubigeo_code=result.ubigeo,
            district=result.district,
            city=result.province,
            state=result.department,
        )
        vals.update(ubi_vals)
        self.write(vals)

        # Representantes legales
        if result.legal_representatives and self.is_company:
            self._sync_legal_representatives(result.legal_representatives)
        # Locales anexos
        if result.annexed_locals and self.is_company:
            self._sync_annexed_locals(result.annexed_locals)

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
            ubi = ubigeo.resolve_by_names(
                self.env,
                district='', city='', state='',  # sin info estructurada
            )
            creates.append({
                'name': label,
                'street': local.get('address', ''),
                'type': 'delivery',
                'parent_id': self.id,
                'is_company': False,
                **ubi,
            })
        if creates:
            self.env['res.partner'].create(creates)

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
    engine,
    http as http_service,
    sunat_padron,
)
from .l10n_pe_economic_activity import activity_commands

_logger = logging.getLogger(__name__)


# Datos de la ficha RUC que solo traen algunas fuentes (portal SUNAT, planes
# completos de las API): si la primera conexión que responde no los trae, el
# botón «Actualizar» los completa con las siguientes.
FICHA_FIELDS = (
    'l10n_pe_taxpayer_type', 'l10n_pe_registration_date', 'l10n_pe_activity_start_date',
    'l10n_pe_invoice_system', 'l10n_pe_accounting_system', 'l10n_pe_einvoice_systems',
    'l10n_pe_electronic_documents',
)

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
    # Sin valor por defecto: un contacto que nunca se consultó no es
    # «ACTIVO» (antes lo parecía, junto a la alerta de consulta fallida).
    state = fields.Selection(
        SUNAT_STATE,
        string='Estado SUNAT',
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
    l10n_pe_lookup_state = fields.Selection(
        [('na', 'Sin consulta'), ('ready', 'Lista'), ('missing', 'Sin configurar')],
        string='Consulta RUC/DNI', compute='_compute_l10n_pe_lookup_state',
        help='Lista: el tipo de documento se consulta en la API. Sin configurar: la compañía '
             'valida ese documento, pero ninguna conexión habilitada tiene su token.')
    l10n_pe_lookup_message = fields.Char(
        string='Aviso de la consulta', compute='_compute_l10n_pe_lookup_state')
    is_good_taxpayer = fields.Boolean(
        string='Buen contribuyente',
        help='Verificado contra el padrón SUNAT (caché diaria).',
    )
    is_retention_agent = fields.Boolean(
        string='Agente de retención',
        help='Verificado contra el padrón SUNAT (caché diaria).',
    )
    l10n_pe_padron_manual = fields.Boolean(
        string='Padrón corregido a mano', copy=False,
        help='Buen contribuyente o agente de retención se marcaron a mano en '
             'contra del padrón (que puede ir por detrás de la designación de '
             'SUNAT): la actualización diaria no los cambia. Se desmarca solo '
             'cuando el valor vuelve a coincidir con el padrón.')

    # === Ficha RUC (consulta SUNAT) ================================ #
    # Datos informativos que SUNAT publica en la consulta RUC; se llenan al
    # consultar y se muestran en la pestaña «SUNAT» del contacto.
    l10n_pe_taxpayer_type = fields.Char(string='Tipo de contribuyente')
    l10n_pe_registration_date = fields.Date(string='Fecha de inscripción')
    l10n_pe_activity_start_date = fields.Date(string='Inicio de actividades')
    l10n_pe_deregistration_date = fields.Date(string='Fecha de baja')
    l10n_pe_invoice_system = fields.Char(string='Sistema de emisión de comprobantes')
    l10n_pe_foreign_trade = fields.Char(string='Actividad de comercio exterior')
    l10n_pe_accounting_system = fields.Char(string='Sistema de contabilidad')
    l10n_pe_printed_documents = fields.Text(
        string='Comprobantes con autorización de impresión',
        help='Comprobantes de pago físicos autorizados (formularios 806 u 816).')
    l10n_pe_einvoice_systems = fields.Text(string='Sistemas de emisión electrónica')
    l10n_pe_einvoice_since = fields.Date(string='Emisor electrónico desde')
    l10n_pe_electronic_documents = fields.Text(string='Comprobantes electrónicos')
    l10n_pe_ple_since = fields.Date(string='Afiliado al PLE desde')
    l10n_pe_padrones = fields.Text(
        string='Padrones', help='Padrones de SUNAT en los que figura (agentes de retención, '
                                'percepción, buenos contribuyentes…) con su fecha.')
    l10n_pe_economic_activity_ids = fields.One2many(
        'l10n_pe.partner.economic.activity', 'partner_id', string='Actividades económicas')
    l10n_pe_main_activity_id = fields.Many2one(
        'l10n_pe.economic.activity', string='Actividad principal',
        compute='_compute_l10n_pe_main_activity', store=True, index='btree_not_null')

    # Representante legal (contacto hijo creado desde la consulta RUC).
    l10n_pe_is_legal_rep = fields.Boolean(string='Representante legal')
    l10n_pe_legal_rep_doc_type = fields.Char(string='Tipo de documento')
    l10n_pe_legal_rep_doc_number = fields.Char(string='Número de documento')
    l10n_pe_legal_rep_since = fields.Date(string='Fecha desde')
    # Local anexo (contacto hijo; el código va en l10n_pe_annex_code).
    l10n_pe_annex_type = fields.Char(string='Tipo de establecimiento')
    l10n_pe_annex_activity = fields.Char(string='Actividad del establecimiento')
    # Los locales anexos son direcciones hijas con código de establecimiento:
    # la pestaña «SUNAT» los lista aparte de los demás contactos.
    l10n_pe_annex_ids = fields.One2many(
        'res.partner', 'parent_id', string='Locales anexos',
        domain=[('l10n_pe_annex_code', '!=', False)])

    # `country_id` con default de la compañía.
    country_id = fields.Many2one(
        default=lambda self: self.env.company.country_id.id,
    )

    @api.depends('l10n_pe_economic_activity_ids.kind', 'l10n_pe_economic_activity_ids.activity_id')
    def _compute_l10n_pe_main_activity(self):
        for partner in self:
            main = partner.l10n_pe_economic_activity_ids.filtered(lambda l: l.kind == 'principal')[:1]
            partner.l10n_pe_main_activity_id = main.activity_id

    @api.depends('l10n_latam_identification_type_id')
    @api.depends_context('company')
    def _compute_l10n_pe_lookup_state(self):
        company = self.env.company
        for partner in self:
            doc_type = partner._l10n_pe_lookup_doc_type()
            if not doc_type:
                partner.l10n_pe_lookup_state = 'na'
                partner.l10n_pe_lookup_message = False
            elif company._l10n_pe_lookup_ready(doc_type):
                partner.l10n_pe_lookup_state = 'ready'
                partner.l10n_pe_lookup_message = False
            else:
                partner.l10n_pe_lookup_state = 'missing'
                partner.l10n_pe_lookup_message = company._l10n_pe_lookup_not_ready_message(doc_type)

    def _l10n_pe_lookup_doc_type(self):
        """'ruc' o 'dni' si la compañía consulta el tipo de documento del
        contacto; vacío si no."""
        self.ensure_one()
        company = self.env.company
        vat_code = self.l10n_latam_identification_type_id.l10n_pe_vat_code
        if vat_code == '1' and company.l10n_pe_dni_validation:
            return 'dni'
        if vat_code == '6' and company.l10n_pe_ruc_validation:
            return 'ruc'
        return ''

    @api.model
    def default_get(self, fields_list):
        """En compañías peruanas, un contacto nuevo nace con RUC como tipo de
        identificación (el más usado al registrar proveedores y clientes)."""
        res = super().default_get(fields_list)
        if ('l10n_latam_identification_type_id' in fields_list
                and not self.env.context.get('default_l10n_latam_identification_type_id')
                and self.env.company.country_id.code == 'PE'):
            ruc = self.env.ref('l10n_pe.it_RUC', raise_if_not_found=False)
            if ruc and not (res.get('company_type') == 'person' or self.env.context.get('default_parent_id')):
                res['l10n_latam_identification_type_id'] = ruc.id
        return res

    @api.onchange('l10n_latam_identification_type_id')
    def _onchange_identification_type_company_type(self):
        """Contacto nuevo: RUC → empresa, DNI → persona. En un contacto ya
        guardado no se cambia lo que el usuario eligió."""
        if self._origin.id or self.parent_id:
            return
        code = self.l10n_latam_identification_type_id.l10n_pe_vat_code
        if code == '6' and not (self.vat or '').startswith('10'):
            self.company_type = 'company'
        elif code == '1':
            self.company_type = 'person'

    # ============================================================ #
    # Onchange / entry point                                        #
    # ============================================================ #

    @api.onchange('company_type')
    def _onchange_company_type_sunat(self):
        """Setea el tipo de documento por defecto según company_type."""
        if self.vat:
            return
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
        if (self.vat or '') != (self._origin.vat or ''):
            # Otro documento: el estado, la condición y los padrones del
            # anterior ya no valen (quedaban «ACTIVO/Habido» si la consulta
            # del nuevo fallaba).
            self.state = False
            self.sunat_condition = False
            if not self.l10n_pe_padron_manual:
                self.is_good_taxpayer = False
                self.is_retention_agent = False
        self._run_document_lookup(raise_on_fail=False)

    def _run_document_lookup(self, raise_on_fail=False):
        """``raise_on_fail`` distingue el botón (espera, reintenta y avisa)
        de la consulta automática al escribir (rápida y silenciosa)."""
        if not self.vat or not self.l10n_latam_identification_type_id:
            return
        # Sólo si la compañía habilitó validación.
        company = self.env.company
        vat = (self.vat or '').strip()
        vat_code = self.l10n_latam_identification_type_id.l10n_pe_vat_code
        if vat_code == '1' and company.l10n_pe_dni_validation:
            self._validate_dni(vat)
            return self._fetch_document('dni', raise_on_fail=raise_on_fail)
        if vat_code == '6' and company.l10n_pe_ruc_validation:
            self._validate_ruc(vat)
            return self._fetch_document('ruc', raise_on_fail=raise_on_fail)
        return None

    # Datos que devuelve ``_l10n_pe_lookup_document``: los que la consulta
    # escribe en el contacto y sirven para llenar un formulario.
    _L10N_PE_LOOKUP_FIELDS = (
        'name', 'company_type', 'street', 'city', 'city_id', 'state_id',
        'country_id', 'zip', 'l10n_pe_district',
    )

    @api.model
    def _l10n_pe_lookup_document(self, number, identification_type):
        """Consulta un RUC o DNI sin crear el contacto, como el onchange del
        formulario: la usan el TPV y la tienda en línea.

        :param str number: número de documento.
        :param identification_type: ``l10n_latam.identification.type``.
        :return: ``{campo: valor}`` (Many2one como id) o ``{}`` si el número
            no es válido, la consulta está desactivada o ninguna conexión
            respondió.
        """
        partner = self.new({
            'vat': (number or '').strip(),
            'l10n_latam_identification_type_id': identification_type.id,
        })
        try:
            partner._run_document_lookup(raise_on_fail=False)
        except UserError:
            return {}  # Formato o dígito verificador no válido.
        if partner.alert_warning_vat or not partner.name:
            return {}
        if partner.city_id and not partner.city:
            partner.city = partner.city_id.name
        values = {}
        for field_name in self._L10N_PE_LOOKUP_FIELDS:
            value = partner[field_name]
            if isinstance(value, models.BaseModel):
                value = value.id
            elif isinstance(value, str):
                value = value.strip()
            values[field_name] = value
        return values

    def write(self, vals):
        """Una casilla del padrón escrita a mano que contradice al padrón
        queda como corrección manual (el cron no la toca); si coincide, deja
        de serlo. La API y el cron escriben con ``l10n_pe_padron_auto``."""
        fields_ = set(sunat_padron.PARTNER_FIELDS) & set(vals)
        if (not fields_ or self.env.context.get('l10n_pe_padron_auto')
                or 'l10n_pe_padron_manual' in vals):
            return super().write(vals)
        for partner in self:
            manual = False
            for field_name in sunat_padron.PARTNER_FIELDS:
                kind = sunat_padron.PARTNER_FIELDS[field_name]
                value = vals[field_name] if field_name in vals else partner[field_name]
                padron = (sunat_padron.has_ruc(self.env, kind, (partner.vat or '').strip())
                          if sunat_padron.has_data(self.env, kind) else False)
                if bool(value) != padron:
                    manual = True
            super(ResPartner, partner).write(dict(vals, l10n_pe_padron_manual=manual))
        return True

    def action_update_document(self):
        """Botón "Actualizar RUC/DNI": si falla, muestra el motivo real; si
        los datos básicos llegaron pero ninguna fuente trajo la ficha RUC
        completa, lo avisa sin cancelar la actualización."""
        incomplete = {}
        for partner in self:
            result = partner._run_document_lookup(raise_on_fail=True) or {}
            if result.get('ficha_missing'):
                incomplete[partner] = result.get('errors') or '—'
        if not incomplete:
            return True
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'warning',
                'sticky': True,
                'title': self.env._('Ficha RUC incompleta'),
                'message': self.env._(
                    'Se actualizaron los datos básicos de %(partners)s, pero ninguna conexión '
                    'devolvió la ficha RUC (tipo de contribuyente, actividades, sistemas de '
                    'emisión…). El portal SUNAT solo responde a direcciones del Perú y las '
                    'API básicas no traen esos datos: active una conexión con la consulta '
                    'completa (por ejemplo Decolecta «ruc/full») en Ajustes ▸ Conexiones '
                    'RUC/DNI.\n\nDetalle: %(detail)s',
                    partners=', '.join(p.display_name for p in incomplete),
                    detail='; '.join(incomplete.values())),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    # ============================================================ #
    # Validación de formato                                         #
    # ============================================================ #

    @staticmethod
    def _validate_dni(vat):
        if not REGEX_DNI.match(vat):
            raise UserError(_('El DNI ingresado no es válido (8 dígitos).'))

    def _validate_ruc(self, vat):
        if not REGEX_RUC.match(vat):
            raise UserError(self.env._(
                'El RUC ingresado no es válido (11 dígitos, '
                'inicia con 10/15/17/20).'
            ))
        # Dígito verificador (módulo 11): un RUC mal tipeado no se consulta
        # (gastaba una consulta de pago y luego base_vat lo rechazaba).
        from stdnum.pe import ruc as stdnum_ruc
        if not stdnum_ruc.is_valid(vat):
            raise UserError(self.env._(
                'El RUC %s no es válido: el dígito verificador no corresponde.', vat))

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
            # Sin conexión utilizable no hubo consulta: no se marca la alerta
            # de «el servicio no respondió»; el formulario ya muestra qué falta
            # (l10n_pe_lookup_state).
            msg = company._l10n_pe_lookup_not_ready_message(doc_type)
            _logger.info(msg)
            if raise_on_fail:
                raise UserError(msg)
            return
        document = (self.vat or '').strip()
        last_exc = None
        result = {}
        for index, connection in enumerate(connections):
            try:
                vals, extra = connection.run(
                    document, doc_type, quick=not raise_on_fail)
            except (http_service.HttpError, UserError, ValueError) as exc:
                last_exc = exc
                _logger.warning('[%s] Consulta %s %s falló: %s',
                                connection.name, doc_type.upper(), document, exc)
                continue
            if doc_type == 'ruc' and raise_on_fail:
                vals, extra, result = self._l10n_pe_complete_ficha(
                    document, vals, extra, company, after=connections[:index + 1])
            self._apply_api_result(doc_type, vals, extra)
            return result
        # Todas las conexiones fallaron.
        self.alert_warning_vat = True
        _logger.warning('Todas las conexiones de %s fallaron para %s.',
                        doc_type.upper(), document)
        if raise_on_fail and last_exc:
            raise UserError(self.env._(
                'No se pudo consultar el %(doc)s %(num)s:\n\n%(err)s',
                doc=doc_type.upper(), num=document, err=str(last_exc)))

    def _l10n_pe_complete_ficha(self, document, vals, extra, company, after):
        """Si la conexión que respondió no trajo la ficha RUC, la completa con
        las demás conexiones activas (aunque el fallback esté apagado: no es
        un reintento, es otra fuente de datos). Solo agrega lo que falta: lo
        que trajo la primera conexión manda. Devuelve ``(vals, extra,
        resultado)``; ``resultado['ficha_missing']`` si ninguna la trajo."""
        def missing():
            return not any(vals.get(name) for name in FICHA_FIELDS)

        if not missing():
            return vals, extra, {}
        others = company._get_pe_api_connections('ruc', all_connections=True) - after
        errors = []
        for connection in others:
            try:
                more_vals, more_extra = connection.run(document, 'ruc', quick=False)
            except (http_service.HttpError, UserError, ValueError) as exc:
                errors.append('%s: %s' % (connection.name, exc))
                _logger.info('[%s] Ficha RUC %s no disponible: %s', connection.name, document, exc)
                continue
            for key, value in (more_vals or {}).items():
                if value not in (False, None, '') and not vals.get(key):
                    vals[key] = value
            for key, value in (more_extra or {}).items():
                if value and not extra.get(key):
                    extra[key] = value
            if not missing():
                break
        return vals, extra, {'ficha_missing': missing(), 'errors': '; '.join(errors)}

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
        if doc_type == 'ruc':
            # Padrón SUNAT (caché diaria): solo completa lo que la API no
            # trajo, y solo si el padrón está cargado. Con el padrón vacío
            # (recién instalado o descarga fallida) no se pisa nada.
            for field_name, kind in sunat_padron.PARTNER_FIELDS.items():
                if field_name not in vals and sunat_padron.has_data(self.env, kind):
                    vals[field_name] = sunat_padron.has_ruc(self.env, kind, self.vat)
            if self.l10n_pe_padron_manual:
                # lo corregido a mano manda sobre la API y el padrón
                for field_name in sunat_padron.PARTNER_FIELDS:
                    vals.pop(field_name, None)
        if doc_type == 'ruc' and extra.get('economic_activities'):
            vals['l10n_pe_economic_activity_ids'] = activity_commands(
                self.env, extra['economic_activities'])
        self.with_context(l10n_pe_padron_auto=True).write(vals)

        # Los contactos hijos solo se crean en un contacto ya guardado (botón):
        # desde el onchange quedarían creados aunque se descarte el formulario.
        if doc_type == 'ruc' and self.is_company and isinstance(self.id, int):
            if extra.get('legal_representatives'):
                self._sync_legal_representatives(extra['legal_representatives'])
            if extra.get('annexed_locals'):
                self._sync_annexed_locals(extra['annexed_locals'])

    # Cargos que se registran como contacto: los que representan a la empresa.
    _LEGAL_REP_POSITIONS = ('GERENTE', 'APODERADO', 'REPRESENTANTE', 'TITULAR', 'PRESIDENTE')

    def _sync_legal_representatives(self, reps):
        """Representantes legales como contactos hijos, con su documento y la
        fecha desde la que figuran. Al reconsultar se actualizan (por número
        de documento o, si no lo hay, por nombre) en lugar de duplicarse."""
        children = self.with_context(active_test=False).child_ids
        for rep in reps:
            position = ' '.join((rep.get('position') or '').upper().split())
            name = ' '.join((rep.get('name') or '').split())
            if not name or not position.startswith(self._LEGAL_REP_POSITIONS):
                continue
            doc_number = (rep.get('doc_number') or '').strip()
            values = {
                'name': name,
                'function': position,
                'l10n_pe_is_legal_rep': True,
                'l10n_pe_legal_rep_doc_type': (rep.get('doc_type') or '').strip(),
                'l10n_pe_legal_rep_doc_number': doc_number,
                'l10n_pe_legal_rep_since': engine.parse_date(rep.get('from_date')),
            }
            existing = children.filtered(
                lambda c: (doc_number and c.l10n_pe_legal_rep_doc_number == doc_number)
                or (c.name or '').strip().upper() == name.upper())[:1]
            if existing:
                existing.write(values)
            else:
                children |= self.env['res.partner'].create(dict(
                    values, type='contact', parent_id=self.id, is_company=False))

    def _sync_annexed_locals(self, locals_):
        """Locales anexos como direcciones hijas con su código de
        establecimiento (``l10n_pe_annex_code``, el que usan los libros y las
        guías), tipo y actividad. Al reconsultar se actualizan por código."""
        children = self.with_context(active_test=False).child_ids
        for local in locals_:
            code = (local.get('code') or '').strip()
            kind = ' '.join((local.get('type') or '').split())
            label = ('%s - %s' % (code, kind)).strip(' -')
            if not label:
                continue
            values = {
                'name': label,
                'street': (local.get('address') or '').strip(),
                'l10n_pe_annex_type': kind,
                'l10n_pe_annex_activity': ' '.join((local.get('activity') or '').split()),
            }
            if code.isdigit() and len(code) == 4:
                values['l10n_pe_annex_code'] = code
            existing = children.filtered(
                lambda c: (code and c.l10n_pe_annex_code == code) or c.name == label)[:1]
            if existing:
                existing.write(values)
            else:
                children |= self.env['res.partner'].create(dict(
                    values, type='delivery', parent_id=self.id, is_company=False))

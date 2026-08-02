# -*- coding: utf-8 -*-
"""Exportador de la carga masiva del T-Registro (prestadores).

Genera los tres archivos que SUNAT pide para dar de alta, modificar o dar
de baja a un trabajador:

===========  ==============================  ====================
Estructura   Contenido                        Archivo
===========  ==============================  ====================
E04          Datos personales y domicilio     ``RP_<RUC>.ide``
E05          Datos del trabajador             ``RP_<RUC>.tra``
E11          Períodos (vínculo, tipo de
             trabajador, salud, pensión)      ``RP_<RUC>.per``
===========  ==============================  ====================

Reglas de formato del manual del PVS (§7.3.1), que es donde se rompe la
carga si uno improvisa:

* separador ``|`` **y también al final de cada línea**;
* nada de espacios entre campos ni al final de la línea;
* campo opcional que no aplica: dos palotes juntos (``||``), es decir,
  cadena vacía entre separadores;
* fechas ``dd/mm/aaaa``;
* si el tipo de documento es 01, 04 o 09, el país emisor es ``604``.

Los archivos salen como adjuntos en un ZIP, que es lo que el PVS espera
antes de subirlos a SOL.
"""
import base64
import io
import re
import unicodedata
import zipfile

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .l10n_pe_hr_tregistro_extra import HIGHER_EDUCATION_CODES

#: Perú en la tabla 26 (país emisor del documento).
COUNTRY_PE = '604'
#: Tipos de documento que obligan a informar el país emisor (§7.3.1).
DOC_TYPES_NEED_COUNTRY = ('07', '24')
#: Categoría del prestador en la estructura 11.
CATEGORY_WORKER = '1'
#: Tipos de registro de la estructura 11.
REGISTRY_LINK = '1'          # vínculo laboral
REGISTRY_WORKER_TYPE = '2'   # tipo de trabajador
REGISTRY_HEALTH = '3'        # régimen de salud
REGISTRY_PENSION = '4'       # régimen pensionario


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_pe_country_emitter = fields.Char(
        string='País emisor del documento (T26)', size=4,
        help='Solo para carné de extranjería o pasaporte: código de la '
             'tabla 26 del Anexo 2. Para documentos peruanos SUNAT exige '
             '604 y se pone solo.')
    l10n_pe_nationality_code = fields.Char(
        string='Nacionalidad (T04)', size=4,
        help='Código de la tabla 4. Obligatorio para los tipos de '
             'documento 04 y 07 (extranjeros).')

    # ------------------------------------------------------------------
    # Utilidades de formato
    # ------------------------------------------------------------------
    @staticmethod
    def _l10n_pe_txt_clean(value):
        """Texto apto para el archivo plano: sin tildes, palotes ni saltos.

        Un palote dentro de un nombre partiría la línea en dos columnas y
        el PVS devolvería un error de estructura.
        """
        if not value:
            return ''
        text = unicodedata.normalize('NFKD', str(value))
        text = ''.join(c for c in text if not unicodedata.combining(c))
        text = text.replace('|', ' ')
        return re.sub(r'\s+', ' ', text).strip().upper()

    @staticmethod
    def _l10n_pe_txt_date(value):
        return value.strftime('%d/%m/%Y') if value else ''

    @staticmethod
    def _l10n_pe_txt_line(values):
        """Une los campos con palote, **incluido el del final**."""
        return '|'.join(str(v or '') for v in values) + '|'

    def _l10n_pe_doc_pair(self):
        """(tipo de documento con 2 dígitos, número, país emisor).

        El catálogo guarda el código SUNAT con un dígito, como lo usan los
        exportadores PLAME; el T-Registro lo exige de dos. El país emisor
        solo se informa para pasaporte y carné del país de residencia; en
        los demás documentos SUNAT obliga a poner 604.
        """
        self.ensure_one()
        code = (self.l10n_latam_identification_type_id
                .l10n_pe_hr_sunat_code or '').strip()
        doc_type = code.zfill(2) if code.isdigit() else code
        if not doc_type:
            country = ''
        elif doc_type in DOC_TYPES_NEED_COUNTRY:
            country = self.l10n_pe_country_emitter or ''
        else:
            country = COUNTRY_PE
        return doc_type, self.identification_id or '', country

    # ------------------------------------------------------------------
    # Estructuras
    # ------------------------------------------------------------------
    def _l10n_pe_e04_row(self):
        """Estructura 04 — datos personales y domiciliarios (41 campos)."""
        self.ensure_one()
        doc_type, doc_number, country = self._l10n_pe_doc_pair()
        phone = re.sub(r'\D', '', self.private_phone or self.mobile_phone or '')
        # SUNAT separa el código de larga distancia del número.
        phone_cld, phone_number = '', phone
        if len(phone) > 9:
            phone_cld, phone_number = phone[:-9] or '', phone[-9:]
        values = [
            doc_type, doc_number, country,
            self._l10n_pe_txt_date(self.birthday),
            self._l10n_pe_txt_clean(self.last_name),
            self._l10n_pe_txt_clean(self.m_last_name),
            self._l10n_pe_txt_clean(self.names),
            # v19: el campo legal del empleado es `sex`, no `gender`.
            '1' if self.sex == 'male'
            else '2' if self.sex == 'female' else '',
            # 9 — Nacionalidad (T04): obligatoria solo para extranjeros.
            self.l10n_pe_nationality_code or '',
            phone_cld, phone_number,
            (self.private_email or self.work_email or '').strip(),
        ]
        values += self._l10n_pe_address_values()
        values += self._l10n_pe_address_values(second=True)
        values.append(self.l10n_pe_health_center_indicator or '1')
        return values

    def _l10n_pe_e05_row(self):
        """Estructura 05 — datos del trabajador (23 campos)."""
        self.ensure_one()
        version = self.version_id
        doc_type, doc_number, country = self._l10n_pe_doc_pair()
        return [
            doc_type, doc_number, country,
            version.l10n_pe_labor_regime_id.code or '',
            version.l10n_pe_education_level_id.code or '',
            version.l10n_pe_occupation_id.code or '',
            '1' if version.l10n_pe_disability else '0',
            version.l10n_pe_cuspp or '',
            '1' if version.l10n_pe_sctr_pension else '',
            version.l10n_pe_contract_type_id.code or '',
            '1' if version.l10n_pe_alternative_schedule else '',
            '1' if version.l10n_pe_max_working_day else '0',
            '1' if version.l10n_pe_night_shift else '',
            '1' if version.l10n_pe_unionized else '0',
            version.l10n_pe_pay_periodicity or '',
            '%.2f' % (version.wage or 0.0),
            version.situation_id.code or '',
            '1' if version.l10n_pe_fifth_income else '0',
            version.l10n_pe_special_situation or '0',
            version.l10n_pe_payment_type or '',
            version.l10n_pe_occupational_category_id.code or '',
            version.l10n_pe_double_taxation or '0',
            version.l10n_pe_cas_vat or '',
        ]

    def _l10n_pe_e11_rows(self, operation='alta'):
        """Estructura 11 — períodos.

        El alta declara cuatro renglones (vínculo, tipo de trabajador,
        régimen de salud y régimen pensionario) y la baja **solo uno**: el
        vínculo con su fecha de fin y el motivo de la tabla 17 en la
        columna «indicador del tipo de registro».
        """
        self.ensure_one()
        version = self.version_id
        doc_type, doc_number, country = self._l10n_pe_doc_pair()
        head = [doc_type, doc_number, country, CATEGORY_WORKER]

        if operation == 'baja':
            reason = version.situation_reason_id.code or ''
            return [head + [REGISTRY_LINK, '',
                            self._l10n_pe_txt_date(version.contract_date_end),
                            reason, '']]

        start = self._l10n_pe_txt_date(version.contract_date_start)
        health = version.social_insurance_id
        rows = [
            head + [REGISTRY_LINK, start, '', '', ''],
            head + [REGISTRY_WORKER_TYPE, start, '',
                    version.worker_type_id.code or '', ''],
            head + [REGISTRY_HEALTH, start, '',
                    health.l10n_pe_tregistro_code or '',
                    health.l10n_pe_eps_code or ''],
            head + [REGISTRY_PENSION, start, '',
                    version.membership_id.l10n_pe_tregistro_code or '', ''],
        ]
        return rows

    # ------------------------------------------------------------------
    # Validaciones previas
    # ------------------------------------------------------------------
    def _l10n_pe_tregistro_issues(self, operation='alta'):
        """Lo que el PVS rechazaría, dicho antes de generar el archivo."""
        issues = []
        for employee in self:
            name = employee.display_name
            doc_type, doc_number, dummy = employee._l10n_pe_doc_pair()
            if not doc_type:
                issues.append(_('%s: sin tipo de documento con código SUNAT.',
                                name))
            if not doc_number:
                issues.append(_('%s: sin número de documento.', name))
            if not (employee.last_name or employee.m_last_name):
                issues.append(_('%s: falta al menos un apellido.', name))
            if not employee.names:
                issues.append(_('%s: falta el nombre.', name))
            version = employee.version_id
            if operation == 'baja':
                if not version.contract_date_end:
                    issues.append(_('%s: sin fecha de cese.', name))
                # El motivo va en la columna «indicador del tipo de
                # registro» de la E11; sin él SUNAT rechaza la baja.
                if not version.situation_reason_id:
                    issues.append(_('%s: sin motivo de baja (T17).', name))
                continue
            if not employee.birthday:
                issues.append(_('%s: sin fecha de nacimiento.', name))
            if not employee.sex:
                issues.append(_('%s: sin sexo.', name))
            if not version.contract_date_start:
                issues.append(_('%s: sin fecha de inicio del vínculo.', name))
            for field, label in (
                    ('l10n_pe_labor_regime_id', _('régimen laboral (T33)')),
                    ('l10n_pe_education_level_id', _('situación educativa (T09)')),
                    ('l10n_pe_occupation_id', _('ocupación (T30)')),
                    ('l10n_pe_occupational_category_id',
                     _('categoría ocupacional (T24)')),
                    ('l10n_pe_contract_type_id', _('tipo de contrato (T12)')),
                    ('worker_type_id', _('tipo de trabajador (T08)')),
                    ('situation_id', _('situación (T15)'))):
                if not version[field]:
                    issues.append(_('%(name)s: falta %(label)s.',
                                    name=name, label=label))
            # E17: el establecimiento es obligatorio en el alta.
            if not employee._l10n_pe_establishments():
                issues.append(_(
                    '%s: sin establecimiento con código SUNAT (E17).', name))
            # E29: si declaró superior completa, SUNAT espera los estudios.
            level = version.l10n_pe_education_level_id.code
            if level in HIGHER_EDUCATION_CODES \
                    and not employee.l10n_pe_education_ids:
                issues.append(_(
                    '%(name)s: con situación educativa %(level)s hay que '
                    'declarar los estudios concluidos (E29).',
                    name=name, level=level))
            # E30: solo si cobra por depósito en cuenta.
            if version.l10n_pe_payment_type == '2':
                issues += employee._l10n_pe_bank_account_issues()
        return issues

    # ------------------------------------------------------------------
    # Generación
    # ------------------------------------------------------------------
    def _l10n_pe_tregistro_files(self, operation='alta'):
        """``{nombre de archivo: contenido}`` de la carga masiva."""
        company = self.company_id
        if len(company) != 1:
            raise UserError(_(
                'Seleccione trabajadores de una sola compañía: los archivos '
                'se cargan con el RUC del empleador.'))
        ruc = (company.vat or '').strip()
        if not ruc:
            raise UserError(_('La compañía %s no tiene RUC.',
                              company.display_name))

        issues = self._l10n_pe_tregistro_issues(operation)
        if issues:
            raise UserError(_(
                'Corrija estos datos antes de generar la carga masiva:\n%s',
                '\n'.join('· %s' % issue for issue in issues[:25])))

        files = {}
        # La baja solo remite la estructura 11 (manual del PVS, §II).
        if operation != 'baja':
            files['RP_%s.ide' % ruc] = '\n'.join(
                self._l10n_pe_txt_line(employee._l10n_pe_e04_row())
                for employee in self)
            files['RP_%s.tra' % ruc] = '\n'.join(
                self._l10n_pe_txt_line(employee._l10n_pe_e05_row())
                for employee in self)
            # E17, E29 y E30 solo se envían si hay algo que declarar:
            # un archivo vacío es un error de estructura para el PVS.
            for extension, method in (('est', '_l10n_pe_e17_rows'),
                                      ('edu', '_l10n_pe_e29_rows'),
                                      ('cta', '_l10n_pe_e30_rows')):
                rows = []
                for employee in self:
                    rows += [self._l10n_pe_txt_line(row)
                             for row in getattr(employee, method)()]
                if rows:
                    files['RP_%s.%s' % (ruc, extension)] = '\n'.join(rows)
        rows = []
        for employee in self:
            rows += [self._l10n_pe_txt_line(row)
                     for row in employee._l10n_pe_e11_rows(operation)]
        files['RP_%s.per' % ruc] = '\n'.join(rows)
        return files

    def action_l10n_pe_export_tregistro(self):
        """Descarga el ZIP con los archivos de alta del T-Registro."""
        return self._l10n_pe_export_tregistro_zip('alta')

    def action_l10n_pe_export_tregistro_baja(self):
        return self._l10n_pe_export_tregistro_zip('baja')

    def _l10n_pe_export_tregistro_zip(self, operation):
        employees = self or self.search(
            [('company_id', '=', self.env.company.id)])
        if not employees:
            raise UserError(_('No hay trabajadores que exportar.'))
        files = employees._l10n_pe_tregistro_files(operation)

        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
            for filename, content in files.items():
                # El PVS lee los planos en latin-1; las tildes ya se
                # quitaron en `_l10n_pe_txt_clean`.
                archive.writestr(filename, content.encode('latin-1', 'replace'))

        company = employees.company_id
        name = 'tregistro_%s_%s_%s.zip' % (
            operation, company.vat, fields.Date.context_today(self))
        attachment = self.env['ir.attachment'].create({
            'name': name,
            'type': 'binary',
            'datas': base64.b64encode(stream.getvalue()),
            'res_model': 'res.company',
            'res_id': company.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }


class HrMembership(models.Model):
    _inherit = 'hr.membership'

    l10n_pe_tregistro_code = fields.Char(
        string='Código T-Registro (T11)', size=2,
        help='Código del régimen pensionario en la tabla 11 del Anexo 2 '
             '(02 SNP-ONP, 21 SPP-AFP…).')


class HrSocialInsurance(models.Model):
    _inherit = 'hr.social.insurance'

    l10n_pe_tregistro_code = fields.Char(
        string='Código T-Registro (T32)', size=2,
        help='Código del régimen de aseguramiento en salud en la tabla 32 '
             'del Anexo 2 (p. ej. 01 EsSalud, 02 EPS).')
    l10n_pe_eps_code = fields.Char(
        string='Código EPS / servicios propios (T14)', size=1,
        help='Solo cuando el régimen de salud es una EPS o el empleador '
             'presta servicios propios.')

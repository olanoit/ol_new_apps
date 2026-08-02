# -*- coding: utf-8 -*-
"""Exportación de derechohabientes para la carga masiva del T-Registro.

SUNAT publica la carga masiva de derechohabientes (estructuras 13 alta y
24 baja) como un módulo aparte del de prestadores, y su especificación
campo a campo no está en el manual del PVS T-Registro. Por eso aquí se
genera la **hoja Excel** con las columnas del registro, que es lo que
consume la macro oficial de carga masiva para producir el TXT.

Las columnas siguen el orden del formulario de SUNAT: primero el
trabajador que genera el vínculo, luego el derechohabiente y por último
la vigencia. Cada fila es un alta o una baja según la hoja.
"""
import base64
import io

from odoo import _, fields, models
from odoo.exceptions import UserError

#: Cabeceras de la hoja de altas, en el orden del registro de SUNAT.
COLUMNS_ALTA = [
    'Tipo doc. trabajador', 'N° doc. trabajador', 'Trabajador',
    'Tipo derechohabiente', 'Cód. tipo', 'Tipo doc. derechohabiente',
    'N° doc. derechohabiente', 'País emisor', 'Apellido paterno',
    'Apellido materno', 'Nombres', 'Fecha de nacimiento', 'Sexo',
    'Fecha de inicio del vínculo', 'Cód. doc. que acredita',
    'Documento que acredita', 'Resolución de incapacidad',
    'Fecha probable de parto',
]

#: La baja solo necesita identificar al vínculo y decir cuándo termina.
COLUMNS_BAJA = [
    'Tipo doc. trabajador', 'N° doc. trabajador', 'Trabajador',
    'Tipo derechohabiente', 'Cód. tipo', 'Tipo doc. derechohabiente',
    'N° doc. derechohabiente', 'Derechohabiente',
    'Fecha de fin del vínculo', 'Cód. motivo', 'Motivo de baja',
]

SEX_CODE = {'male': '1', 'female': '2'}


class L10nPeHrDependent(models.Model):
    _inherit = 'l10n_pe.hr.dependent'

    # ------------------------------------------------------------------
    # Datos de una fila
    # ------------------------------------------------------------------
    @staticmethod
    def _l10n_pe_doc_code(identification_type):
        """Código SUNAT del tipo de documento con los 2 dígitos del T-Registro.

        El catálogo guarda el código en la forma corta que usan los
        exportadores PLAME ('1' = DNI); el T-Registro lo exige de longitud
        2 ('01'), así que se rellena aquí en vez de tocar el catálogo.
        """
        code = (identification_type.l10n_pe_hr_sunat_code or '').strip()
        return code.zfill(2) if code.isdigit() else code

    def _l10n_pe_worker_doc(self):
        """(código SUNAT del tipo de documento, número) del trabajador."""
        self.ensure_one()
        employee = self.employee_id
        return (self._l10n_pe_doc_code(
                    employee.l10n_latam_identification_type_id),
                employee.identification_id or '')

    def _l10n_pe_dependent_doc(self):
        self.ensure_one()
        return (self._l10n_pe_doc_code(
                    self.l10n_latam_identification_type_id),
                self.identification_id or '')

    @staticmethod
    def _l10n_pe_fmt_date(value):
        return value.strftime('%d/%m/%Y') if value else ''

    def _l10n_pe_alta_row(self):
        self.ensure_one()
        worker_type, worker_number = self._l10n_pe_worker_doc()
        dep_type, dep_number = self._l10n_pe_dependent_doc()
        return [
            worker_type, worker_number, self.employee_id.name or '',
            self.type_id.name or '', self.type_id.code or '',
            dep_type, dep_number, self.country_id.code or '',
            self.last_name or '', self.m_last_name or '', self.names or '',
            self._l10n_pe_fmt_date(self.birthday),
            SEX_CODE.get(self.gender, ''),
            self._l10n_pe_fmt_date(self.date_start),
            self.proof_type_id.code or '', self.proof_document or '',
            self.disability_resolution or '',
            self._l10n_pe_fmt_date(self.gestation_due_date),
        ]

    def _l10n_pe_baja_row(self):
        self.ensure_one()
        worker_type, worker_number = self._l10n_pe_worker_doc()
        dep_type, dep_number = self._l10n_pe_dependent_doc()
        return [
            worker_type, worker_number, self.employee_id.name or '',
            self.type_id.name or '', self.type_id.code or '',
            dep_type, dep_number, self.name or '',
            self._l10n_pe_fmt_date(self.date_end),
            self.end_reason_id.code or '', self.end_reason_id.name or '',
        ]

    # ------------------------------------------------------------------
    # Libro Excel
    # ------------------------------------------------------------------
    def _l10n_pe_check_exportable(self):
        """Avisa de lo que SUNAT rechazaría antes de generar el archivo."""
        issues = []
        for dependent in self:
            if not dependent.employee_id.identification_id:
                issues.append(_(
                    '%(name)s: el trabajador %(employee)s no tiene documento '
                    'de identidad.', name=dependent.name,
                    employee=dependent.employee_id.display_name))
            if not dependent.type_id.is_unborn and not dependent.identification_id:
                issues.append(_('%(name)s: sin documento de identidad.',
                                name=dependent.name))
            if not dependent.date_start:
                issues.append(_('%(name)s: sin fecha de inicio del vínculo.',
                                name=dependent.name))
        return issues

    def action_export_tregistro_xlsx(self):
        """Genera la hoja de altas y bajas para la macro de SUNAT."""
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Alignment, Font, PatternFill
        except ImportError as exc:  # pragma: no cover — entorno sin openpyxl
            raise UserError(_(
                'Falta la librería openpyxl para generar el Excel.')) from exc

        records = self or self.search([])
        if not records:
            raise UserError(_('No hay derechohabientes que exportar.'))
        companies = records.company_id
        if len(companies) > 1:
            raise UserError(_(
                'Seleccione derechohabientes de una sola compañía: el '
                'archivo se carga con el RUC del empleador.'))

        issues = records._l10n_pe_check_exportable()
        if issues:
            raise UserError(_(
                'Corrija estos datos antes de exportar:\n%s',
                '\n'.join('· %s' % issue for issue in issues[:20])))

        altas = records.filtered(lambda d: not d.date_end)
        bajas = records.filtered(lambda d: d.date_end)

        workbook = Workbook()
        header_font = Font(bold=True, color='FFFFFF')
        header_fill = PatternFill('solid', fgColor='4F6228')

        def add_sheet(title, columns, rows):
            sheet = workbook.create_sheet(title)
            sheet.append(columns)
            for cell in sheet[1]:
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal='center', wrap_text=True)
            for row in rows:
                sheet.append(row)
            for index, column in enumerate(columns, start=1):
                sheet.column_dimensions[
                    sheet.cell(row=1, column=index).column_letter
                ].width = max(14, min(34, len(column) + 4))
            sheet.freeze_panes = 'A2'
            return sheet

        workbook.remove(workbook.active)
        add_sheet(_('Altas'), COLUMNS_ALTA,
                  [dependent._l10n_pe_alta_row() for dependent in altas])
        add_sheet(_('Bajas'), COLUMNS_BAJA,
                  [dependent._l10n_pe_baja_row() for dependent in bajas])

        stream = io.BytesIO()
        workbook.save(stream)
        content = stream.getvalue()

        company = companies[:1]
        filename = 'derechohabientes_%s_%s.xlsx' % (
            company.vat or company.id, fields.Date.context_today(self))
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(content),
            'res_model': 'res.company',
            'res_id': company.id,
        })
        # Marcar lo exportado evita volver a declarar altas ya cargadas.
        altas.is_declared = True
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

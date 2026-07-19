# -*- coding: utf-8 -*-
"""Exportación Excel de los libros PLE.

El FORMATO visual replica el del módulo v18 ``al_l10n_pe_ple`` (ce18):
título de compañía (fondo #b5b4b4, tamaño 22), fila RUC/Período/Mes,
numeración de columnas, banda de encabezados celeste (#afebff) combinada en
dos filas, columna «Nº» y datos texto/número. Los DATOS provienen de la
lógica actual del wizard (las mismas líneas del TXT).
"""
from io import BytesIO

import xlsxwriter

from odoo import models

# Títulos de hoja (máx. 31 caracteres, restricción de Excel)
PLE_XLSX_TITLES = {
    '070100': 'PLE 7.1 Activos Fijos',
    '070300': 'PLE 7.3 Dif. de cambio',
    '070400': 'PLE 7.4 Leasing',
    '040100': 'PLE 4.1 Retenciones',
    '090100': 'PLE 9.1 Consignador',
    '090200': 'PLE 9.2 Consignatario',
    '030800': 'PLE 3.8 Inversiones',
    '030900': 'PLE 3.9 Intangibles',
    '031900': 'PLE 3.19 Patrimonio',
    '100100': 'PLE 10.1 Costo de ventas',
    '100200': 'PLE 10.2 Elementos del costo',
    '100300': 'PLE 10.3 Costo de producción',
    '100400': 'PLE 10.4 Centros de costos',
    '050200': 'PLE 5.2 Diario Simplificado',
    '050400': 'PLE 5.4 Plan Contable',
    '080300': 'PLE 8.3 Compras Simplificado',
    '140200': 'PLE 14.2 Ventas Simplificado',
}

# Encabezados de columna. Los de 5.2/5.4/8.3/14.2 reproducen textualmente
# los del módulo v18 (ple_headers.py); el resto sigue los nombres de campo
# del Anexo 2 de SUNAT.
PLE_XLSX_HEADERS = {
    '070100': [
        'Periodo', 'Código Único de la Operación (CUO)',
        'Número correlativo del asiento contable',
        'Código del catálogo utilizado', 'Código propio del activo fijo',
        'Código del catálogo UNSPSC/GTIN',
        'Código de la existencia según el catálogo',
        'Tipo de activo fijo', 'Cuenta contable del activo fijo',
        'Estado del activo fijo', 'Descripción del activo fijo',
        'Marca del activo fijo', 'Modelo del activo fijo',
        'Número de serie y/o placa del activo fijo',
        'Saldo inicial', 'Adquisiciones y adiciones', 'Mejoras',
        'Retiros y/o bajas', 'Otros ajustes', 'Revaluación voluntaria',
        'Revaluación por reorganización de sociedades',
        'Otras revaluaciones', 'Ajuste por inflación',
        'Fecha de adquisición', 'Fecha de inicio del uso del activo fijo',
        'Método de depreciación aplicado',
        'Nº de documento de autorización del cambio de método',
        'Porcentaje de depreciación',
        'Depreciación acumulada al cierre del ejercicio anterior',
        'Depreciación del ejercicio',
        'Depreciación del ejercicio relacionada con retiros y/o bajas',
        'Depreciación relacionada con otros ajustes',
        'Depreciación de la revaluación voluntaria',
        'Depreciación de la revaluación por reorganización de sociedades',
        'Depreciación de otras revaluaciones',
        'Ajuste por inflación de la depreciación',
        'Indica el estado de la operación',
    ],
    '070300': [
        'Periodo', 'Código Único de la Operación (CUO)',
        'Número correlativo del asiento contable',
        'Código del catálogo utilizado', 'Código propio del activo fijo',
        'Fecha de adquisición',
        'Valor de adquisición en moneda extranjera',
        'Tipo de cambio a la fecha de adquisición',
        'Valor de adquisición en moneda nacional',
        'Tipo de cambio al cierre del ejercicio',
        'Ajuste por diferencia de cambio',
        'Depreciación del ejercicio',
        'Depreciación de retiros y/o bajas',
        'Depreciación de otros ajustes',
        'Indica el estado de la operación',
    ],
    '070400': [
        'Periodo', 'Código Único de la Operación (CUO)',
        'Número correlativo del asiento contable',
        'Código del catálogo utilizado',
        'Número del contrato de arrendamiento financiero',
        'Fecha del contrato', 'Código propio del activo fijo',
        'Fecha de inicio del arrendamiento',
        'Número de cuotas pactadas', 'Monto total del contrato',
        'Indica el estado de la operación',
    ],
    '040100': [
        'Periodo', 'Código Único de la Operación (CUO)',
        'Número correlativo del asiento contable',
        'Fecha de pago o retención',
        'Tipo de documento de identidad del prestador del servicio',
        'Número de documento de identidad del prestador del servicio',
        'Apellidos y nombres del prestador del servicio',
        'Monto bruto pagado o puesto a disposición',
        'Retención efectuada',
        'Indica el estado de la operación',
    ],
    '090100': [
        'Periodo', 'Código del catálogo utilizado',
        'Tipo de existencia', 'Código propio de la existencia',
        'Código Único de la Operación (CUO)',
        'Nombre de la existencia', 'Código de la unidad de medida',
        'Fecha de la guía de remisión',
        'Serie de la guía de remisión', 'Número de la guía de remisión',
        'Tipo de comprobante de pago del consignador',
        'Fecha de emisión del comprobante de pago',
        'Serie del comprobante de pago', 'Número del comprobante de pago',
        'Fecha de entrega o devolución del bien',
        'Tipo de documento de identidad del consignatario',
        'Número de documento de identidad del consignatario',
        'Apellidos y nombres o razón social del consignatario',
        'Cantidad de bienes entregados en consignación',
        'Cantidad de bienes devueltos por el consignatario',
        'Cantidad de bienes vendidos',
        'Indica el estado de la operación',
    ],
    '090200': [
        'Periodo', 'Código del catálogo utilizado',
        'Tipo de existencia', 'Código propio de la existencia',
        'Código Único de la Operación (CUO)',
        'Nombre de la existencia', 'Código de la unidad de medida',
        'Fecha de la guía de remisión',
        'Serie de la guía de remisión', 'Número de la guía de remisión',
        'Tipo de comprobante de pago',
        'Fecha de emisión del comprobante de pago',
        'Serie del comprobante de pago', 'Número del comprobante de pago',
        'Fecha de recepción o devolución del bien',
        'Número de RUC del consignador',
        'Apellidos y nombres o razón social del consignador',
        'Cantidad de bienes recibidos en consignación',
        'Cantidad de bienes devueltos al consignador',
        'Cantidad de bienes vendidos',
        'Indica el estado de la operación',
    ],
    '030800': [
        'Periodo', 'Código Único de la Operación (CUO)',
        'Número correlativo del asiento contable',
        'Tipo de documento de identidad del emisor',
        'Número de documento de identidad del emisor',
        'Apellidos y nombres o razón social del emisor',
        'Código del título', 'Valor nominal unitario del título',
        'Cantidad de títulos', 'Costo total en libros',
        'Provisión total', 'Indica el estado de la operación',
    ],
    '030900': [
        'Periodo', 'Código Único de la Operación (CUO)',
        'Número correlativo del asiento contable',
        'Fecha de inicio de la operación',
        'Código de la cuenta contable', 'Descripción del intangible',
        'Valor contable del intangible', 'Amortización acumulada',
        'Indica el estado de la operación',
    ],
    '031900': [
        'Periodo', 'Código del catálogo utilizado',
        'Código del rubro del Estado de Cambios en el Patrimonio Neto',
        'Capital', 'Acciones de inversión', 'Capital adicional',
        'Resultados no realizados', 'Reservas legales', 'Otras reservas',
        'Resultados acumulados', 'Diferencia de conversión',
        'Ajustes al patrimonio', 'Resultado neto del ejercicio',
        'Excedente de revaluación', 'Resultado del ejercicio',
        'Indica el estado de la operación',
    ],
    '100100': [
        'Ejercicio',
        'Inventario inicial de productos terminados',
        'Costo de producción de productos terminados',
        'Inventario final de productos terminados',
        'Ajustes diversos', 'Indica el estado de la operación',
    ],
    '100200': [
        'Periodo', 'Materiales y suministros directos',
        'Mano de obra directa', 'Otros costos directos',
        'Gastos de producción indirectos: materiales y suministros indirectos',
        'Gastos de producción indirectos: mano de obra indirecta',
        'Gastos de producción indirectos: otros gastos',
        'Indica el estado de la operación',
    ],
    '100300': [
        'Ejercicio', 'Código del proceso productivo',
        'Descripción del proceso productivo',
        'Materiales y suministros directos', 'Mano de obra directa',
        'Otros costos directos',
        'Gastos de producción indirectos: materiales y suministros indirectos',
        'Gastos de producción indirectos: mano de obra indirecta',
        'Gastos de producción indirectos: otros gastos',
        'Inventario inicial de productos en proceso',
        'Inventario final de productos en proceso',
        'Código de agrupamiento', 'Indica el estado de la operación',
    ],
    '100400': [
        'Periodo', 'Número correlativo',
        'Código de la unidad de operación',
        'Descripción de la unidad de operación',
        'Código del centro de costos',
        'Descripción del centro de costos',
        'Indica el estado de la operación',
    ],
    '050200': [
        'Periodo', 'Código Único de la Operación (CUO)',
        'Número correlativo del asiento contable',
        'Código de la cuenta contable desagregado en subcuentas al nivel '
        'máximo de dígitos utilizado',
        'Código de la Unidad de Operación, de la Unidad Económica '
        'Administrativa, de la Unidad de Negocio, de la Unidad de '
        'Producción, de la Línea, de la Concesión, del Local o del Lote',
        'Código del Centro de Costos, Centro de Utilidades o Centro de '
        'Inversión',
        'Tipo de Moneda de origen',
        'Tipo de documento de identidad del emisor',
        'Número de documento de identidad del emisor',
        'Tipo de Comprobante de Pago o Documento asociada a la operación',
        'Número de serie del comprobante de pago o documento asociada a la '
        'operación',
        'Número del comprobante de pago o documento asociada a la operación',
        'Fecha contable', 'Fecha de vencimiento',
        'Fecha de la operación o emisión',
        'Glosa o descripción de la naturaleza de la operación registrada',
        'Glosa referencial',
        'Movimientos del Debe', 'Movimientos del Haber',
        'Código del libro, campo 1, campo 2 y campo 3 del Registro de '
        'Ventas e Ingresos o del Registro de Compras',
        'Indica el estado de la operación',
    ],
    '050400': [
        'Periodo',
        'Código de la Cuenta Contable desagregada hasta el nivel máximo de '
        'dígitos utilizado',
        'Descripción de la Cuenta Contable desagregada al nivel máximo de '
        'dígitos utilizado',
        'Código del Plan de Cuentas utilizado por el deudor tributario',
        'Descripción del Plan de Cuentas utilizado por el deudor tributario',
        'Código de la Cuenta Contable Corporativa desagregada hasta el '
        'nivel máximo de dígitos utilizado',
        'Descripción de la Cuenta Contable Corporativa desagregada al '
        'nivel máximo de dígitos utilizado',
        'Indica el estado de la operación',
    ],
    '080300': [
        'Periodo',
        'Número correlativo del mes o Código Único de la Operación (CUO)',
        'Número correlativo del asiento contable',
        'Fecha de emisión del comprobante de pago o documento',
        'Fecha de Vencimiento o Fecha de Pago',
        'Tipo de Comprobante de Pago o Documento',
        'Serie del comprobante de pago o documento o código de la '
        'dependencia Aduanera',
        'Número del comprobante de pago o documento o número de orden del '
        'formulario físico o virtual o número final',
        'Nº Final',
        'Tipo de Documento de Identidad del proveedor',
        'Número de RUC del proveedor o número de documento de Identidad',
        'Apellidos y nombres, denominación o razón social del proveedor',
        'Base imponible de las adquisiciones gravadas que dan derecho a '
        'crédito fiscal y/o saldo a favor por exportación, destinadas '
        'exclusivamente a operaciones gravadas y/o de exportación',
        'Monto del Impuesto General a las Ventas y/o Impuesto de Promoción '
        'Municipal',
        'Impuesto al Consumo de las Bolsas de Plástico',
        'Otros conceptos, tributos y cargos que no formen parte de la base '
        'imponible',
        'Importe total de las adquisiciones registradas según comprobante '
        'de pago',
        'Código de la Moneda', 'Tipo de cambio',
        'Fecha de emisión del comprobante de pago que se modifica',
        'Tipo de comprobante de pago que se modifica',
        'Número de serie del comprobante de pago que se modifica',
        'Número del comprobante de pago que se modifica',
        'Fecha de emisión de la Constancia de Depósito de Detracción',
        'Número de la Constancia de Depósito de Detracción',
        'Marca del comprobante de pago sujeto a retención',
        'Clasificación de los bienes y servicios adquiridos',
        'Error tipo 1: inconsistencia en el tipo de cambio',
        'Error tipo 2: inconsistencia por proveedores no habidos',
        'Error tipo 3: inconsistencia por proveedores que renunciaron a la '
        'exoneración del Apéndice I del IGV',
        'Indicador de Comprobantes de pago cancelados con medios de pago',
        'Estado que identifica la oportunidad de la anotación o indicación '
        'si ésta corresponde a un ajuste',
    ],
    '140200': [
        'Periodo',
        'Número correlativo del mes o Código Único de la Operación (CUO)',
        'Número correlativo del asiento contable',
        'Fecha de emisión del Comprobante de Pago',
        'Fecha de Vencimiento o Fecha de Pago',
        'Tipo de Comprobante de Pago o Documento',
        'Número serie del comprobante de pago o documento o número de '
        'serie de la maquina registradora',
        'Número del comprobante de pago o documento o número inicial o '
        'constancia de depósito',
        'Número final',
        'Tipo de Documento de Identidad del cliente',
        'Número de Documento de Identidad del cliente',
        'Apellidos y nombres, denominación o razón social del cliente',
        'Base imponible', 'IGV', 'ICBPER', 'Otros conceptos',
        'Importe total del comprobante de pago',
        'Código de la Moneda', 'Tipo de cambio',
        'Fecha de emisión del comprobante de pago o documento original que '
        'se modifica o documento referencial al documento que sustenta el '
        'crédito fiscal',
        'Tipo del comprobante de pago que se modifica',
        'Número de serie del comprobante de pago que se modifica o Código '
        'de la Dependencia Aduanera',
        'Número del comprobante de pago que se modifica o Número de la DUA',
        'Error tipo 1: inconsistencia en el tipo de cambio',
        'Indicador de Comprobantes de pago cancelados con medios de pago',
        'Estado que identifica la oportunidad de la anotación o indicación',
    ],
}


class L10nPePleMixinXlsx(models.AbstractModel):
    _inherit = 'l10n_pe.ple.mixin'

    def _ple_xlsx(self, book_code, lines, company, year, month='00'):
        """Genera el XLSX (bytes) con el formato del módulo v18: los datos
        son exactamente los campos del TXT (``lines``)."""
        headers = PLE_XLSX_HEADERS[book_code]
        sheet_name = PLE_XLSX_TITLES.get(book_code, 'PLE %s' % book_code)
        num_columns = len(headers)

        output = BytesIO()
        workbook = xlsxwriter.Workbook(
            output, {'in_memory': True, 'strings_to_numbers': False})
        sheet = workbook.add_worksheet(sheet_name)

        fmt_title = workbook.add_format({
            'border': 1, 'align': 'center', 'valign': 'vcenter',
            'font_size': 10, 'text_wrap': True, 'bg_color': '#afebff'})
        fmt_gray = workbook.add_format({
            'border': 0, 'align': 'center', 'valign': 'vcenter',
            'font_size': 10, 'text_wrap': True, 'bg_color': '#b5b4b4',
            'font_color': 'white'})
        fmt_string = workbook.add_format({
            'border': 0, 'font_size': 10, 'valign': 'vcenter',
            'num_format': '@'})
        fmt_number = workbook.add_format({
            'bold': 0, 'valign': 'vcenter', 'num_format': '#,##0.00',
            'font_size': 10})
        fmt_company = workbook.add_format({
            'border': 0, 'valign': 'vcenter', 'font_size': 22,
            'text_wrap': True, 'bg_color': '#b5b4b4'})
        fmt_label = workbook.add_format({
            'border': 0, 'align': 'center', 'valign': 'vcenter',
            'font_size': 12, 'text_wrap': True, 'bg_color': '#b5b4b4'})

        # Fila 1: título de la compañía
        sheet.merge_range(0, 0, 0, num_columns,
                          '%s - %s' % (company.name, sheet_name), fmt_company)
        sheet.set_row(0, 30)

        # Fila 2: RUC / Período / Mes
        sheet.write(1, 0, 'RUC', fmt_label)
        sheet.merge_range(1, 1, 1, 2, company.partner_id.vat or '', fmt_string)
        sheet.write(1, 3, 'Período', fmt_label)
        sheet.write(1, 4, '%s' % year)
        sheet.write(1, 5, 'Mes', fmt_label)
        sheet.write(1, 6, '%s' % str(month).zfill(2))
        if num_columns > 7:
            sheet.merge_range(1, 7, 1, num_columns, '', fmt_gray)

        # Fila 3: numeración de columnas · Filas 4-5: encabezados
        sheet.write(2, 0, '', fmt_gray)
        sheet.set_column(0, 0, 7)
        sheet.merge_range(3, 0, 4, 0, 'Nº', fmt_gray)
        sheet.set_row(4, 40)
        for index, head in enumerate(headers):
            column = index + 1
            sheet.set_column(column, column, 15)
            sheet.write(2, column, column, fmt_gray)
            sheet.merge_range(3, column, 4, column, head, fmt_title)

        # Datos (desde la fila 6)
        row = 5
        for number, values in enumerate(lines, start=1):
            sheet.write(row, 0, number, fmt_gray)
            for index, value in enumerate(values[:num_columns]):
                text = str(value) if value not in (False, None) else ''
                fmt = fmt_number if text.isdecimal() else fmt_string
                sheet.write(row, index + 1, text, fmt)
            row += 1

        workbook.close()
        return output.getvalue()

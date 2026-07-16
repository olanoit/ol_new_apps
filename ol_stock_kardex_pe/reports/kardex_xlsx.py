"""Generación del XLSX de los formatos SUNAT 13.1 / 12.1.

Réplica de la plantilla oficial `234_formato131.xls` (SUNAT): bloque de
cabecera por producto + tabla de movimientos con grupos ENTRADAS / SALIDAS /
SALDO FINAL y fila de TOTALES. Todo se construye en memoria (BytesIO).
"""
import io

import xlsxwriter

FONT = 'Arial'


def _sheet_name(name, used):
    clean = ''.join(c for c in name if c not in '[]:*?/\\')[:31] or 'HOJA'
    candidate, i = clean, 1
    while candidate.lower() in used:
        suffix = ' (%d)' % i
        candidate = clean[:31 - len(suffix)] + suffix
        i += 1
    used.add(candidate.lower())
    return candidate


def build_kardex_xlsx(wizard):
    header = wizard._get_report_header()
    valued = header['valued']
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})

    def fmt(props):
        base = {'font_name': FONT, 'font_size': 9}
        base.update(props)
        return workbook.add_format(base)

    fmt_title = fmt({'bold': True, 'font_size': 11, 'align': 'center',
                     'valign': 'vcenter'})
    fmt_lbl = fmt({'bold': True, 'align': 'right', 'valign': 'vcenter',
                   'text_wrap': True})
    fmt_val = fmt({'align': 'left', 'valign': 'vcenter', 'text_wrap': True})
    fmt_head = fmt({'bold': True, 'align': 'center', 'valign': 'vcenter',
                    'text_wrap': True, 'border': 1, 'bg_color': '#D9D9D9'})
    fmt_ctr = fmt({'border': 1, 'align': 'center', 'valign': 'vcenter'})
    fmt_date = fmt({'border': 1, 'align': 'center', 'valign': 'vcenter',
                    'num_format': 'dd/mm/yyyy'})
    fmt_qty = fmt({'border': 1, 'align': 'right', 'num_format': '#,##0.00'})
    fmt_cost = fmt({'border': 1, 'align': 'right', 'num_format': '#,##0.0000'})
    fmt_t_lbl = fmt({'bold': True, 'border': 1, 'align': 'center',
                     'valign': 'vcenter', 'bg_color': '#F2F2F2'})
    fmt_t_qty = fmt({'bold': True, 'border': 1, 'align': 'right',
                     'num_format': '#,##0.00', 'bg_color': '#F2F2F2'})
    fmt_t_cost = fmt({'bold': True, 'border': 1, 'align': 'right',
                      'num_format': '#,##0.0000', 'bg_color': '#F2F2F2'})
    fmt_t_empty = fmt({'border': 1, 'bg_color': '#F2F2F2'})
    fmt_foot = fmt({'font_size': 8, 'italic': True, 'font_color': '#555555'})

    # Columnas: doc (0-3) + operación (4) + grupos de cantidades/costos
    group_cols = 9 if valued else 3
    last_col = 4 + group_cols
    # Anchos por columna (índice de columna del grupo → ancho)
    col_widths = [10, 7, 9, 12, 10] + [11] * group_cols

    used_names = set()
    for scope in wizard._get_report_data():
        sheet = workbook.add_worksheet(_sheet_name(scope['name'], used_names))
        sheet.set_landscape()
        sheet.set_paper(9)  # A4
        sheet.set_margins(0.3, 0.3, 0.4, 0.4)
        sheet.fit_to_pages(1, 0)
        sheet.set_column(0, last_col, None)
        for idx, width in enumerate(col_widths):
            sheet.set_column(idx, idx, width)

        row = 0
        for block in scope['products']:
            sheet.merge_range(row, 0, row, last_col, header['title'], fmt_title)
            sheet.set_row(row, 26)
            row += 1

            # Bloque de cabecera: etiqueta (col 0-2) + valor (col 3-last)
            head_pairs = [
                ('PERÍODO:', '%s - %s' % (header['date_from'].strftime('%d/%m/%Y'),
                                          header['date_to'].strftime('%d/%m/%Y'))),
                ('RUC:', header['ruc']),
                ('APELLIDOS Y NOMBRES, DENOMINACIÓN O RAZÓN SOCIAL:',
                 header['company_name']),
                ('ESTABLECIMIENTO (1):', scope['establishment']),
                ('CÓDIGO DE LA EXISTENCIA:', block['code']),
                ('TIPO (TABLA 5):', block['existence_type']),
                ('DESCRIPCIÓN:', block['description']),
                ('CÓDIGO DE LA UNIDAD DE MEDIDA (TABLA 6):',
                 '%s - %s' % (block['uom_code'], block['uom_name'])),
            ]
            if valued:
                head_pairs.append(('MÉTODO DE VALUACIÓN:', block['valuation_method']))
            for label, value in head_pairs:
                sheet.merge_range(row, 0, row, 2, label, fmt_lbl)
                sheet.merge_range(row, 3, row, last_col, value, fmt_val)
                row += 1
            row += 1

            # Cabecera de la tabla de movimientos
            sheet.merge_range(
                row, 0, row, 3,
                'DOCUMENTO DE TRASLADO, COMPROBANTE DE PAGO, '
                'DOCUMENTO INTERNO O SIMILAR', fmt_head)
            sheet.merge_range(row, 4, row + 1, 4,
                              'TIPO DE OPERACIÓN (TABLA 12)', fmt_head)
            if valued:
                sheet.merge_range(row, 5, row, 7, 'ENTRADAS', fmt_head)
                sheet.merge_range(row, 8, row, 10, 'SALIDAS', fmt_head)
                sheet.merge_range(row, 11, row, 13, 'SALDO FINAL', fmt_head)
            else:
                sheet.write(row, 5, 'ENTRADAS', fmt_head)
                sheet.write(row, 6, 'SALIDAS', fmt_head)
                sheet.write(row, 7, 'SALDO FINAL', fmt_head)
            row += 1
            for col, label in enumerate(
                    ['FECHA', 'TIPO (TABLA 10)', 'SERIE', 'NÚMERO']):
                sheet.write(row, col, label, fmt_head)
            if valued:
                for base in (5, 8, 11):
                    sheet.write(row, base, 'CANTIDAD', fmt_head)
                    sheet.write(row, base + 1, 'COSTO UNITARIO', fmt_head)
                    sheet.write(row, base + 2, 'COSTO TOTAL', fmt_head)
            else:
                for col in (5, 6, 7):
                    sheet.write(row, col, 'CANTIDAD', fmt_head)
            sheet.set_row(row, 24)
            row += 1

            for line in block['lines']:
                if line.line_type == 'opening':
                    sheet.write(row, 0, line.date and line.date.date() or '', fmt_date)
                    sheet.write(row, 1, line.document_type_code or '00', fmt_ctr)
                    sheet.write(row, 2, '-', fmt_ctr)
                    sheet.write(row, 3, 'SALDO INICIAL', fmt_ctr)
                else:
                    sheet.write(row, 0, line.date and line.date.date() or '', fmt_date)
                    sheet.write(row, 1, line.document_type_code or '', fmt_ctr)
                    sheet.write(row, 2, line.serie or '', fmt_ctr)
                    sheet.write(row, 3, line.folio or '', fmt_ctr)
                sheet.write(row, 4, line.operation_type or '', fmt_ctr)
                if valued:
                    sheet.write_number(row, 5, line.qty_in, fmt_qty)
                    sheet.write_number(row, 6, line.cost_unit_in, fmt_cost)
                    sheet.write_number(row, 7, line.cost_total_in, fmt_qty)
                    sheet.write_number(row, 8, line.qty_out, fmt_qty)
                    sheet.write_number(row, 9, line.cost_unit_out, fmt_cost)
                    sheet.write_number(row, 10, line.cost_total_out, fmt_qty)
                    sheet.write_number(row, 11, line.balance_qty, fmt_qty)
                    sheet.write_number(row, 12, line.balance_unit_cost, fmt_cost)
                    sheet.write_number(row, 13, line.balance_value, fmt_qty)
                else:
                    sheet.write_number(row, 5, line.qty_in, fmt_qty)
                    sheet.write_number(row, 6, line.qty_out, fmt_qty)
                    sheet.write_number(row, 7, line.balance_qty, fmt_qty)
                row += 1

            total = block['total_line']
            if total:
                sheet.merge_range(row, 0, row, 4, 'TOTALES', fmt_t_lbl)
                if valued:
                    sheet.write_number(row, 5, total.qty_in, fmt_t_qty)
                    sheet.write_blank(row, 6, None, fmt_t_empty)
                    sheet.write_number(row, 7, total.cost_total_in, fmt_t_qty)
                    sheet.write_number(row, 8, total.qty_out, fmt_t_qty)
                    sheet.write_blank(row, 9, None, fmt_t_empty)
                    sheet.write_number(row, 10, total.cost_total_out, fmt_t_qty)
                    sheet.write_number(row, 11, total.balance_qty, fmt_t_qty)
                    sheet.write_number(row, 12, total.balance_unit_cost, fmt_t_cost)
                    sheet.write_number(row, 13, total.balance_value, fmt_t_qty)
                else:
                    sheet.write_number(row, 5, total.qty_in, fmt_t_qty)
                    sheet.write_number(row, 6, total.qty_out, fmt_t_qty)
                    sheet.write_number(row, 7, total.balance_qty, fmt_t_qty)
                row += 1

            sheet.write(
                row, 0,
                '(1) Dirección del establecimiento o código según el '
                'Registro Único de Contribuyentes.', fmt_foot)
            row += 3  # separación entre productos

    workbook.close()
    output.seek(0)
    return output.read()

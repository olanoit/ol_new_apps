import re
from collections import defaultdict
from datetime import datetime, time

import pytz
from dateutil.relativedelta import relativedelta

from odoo import api, models

PE_TZ = pytz.timezone('America/Lima')
#: Texto del PLE: la norma prohíbe «|», «/» y «\» (y el «"» hacía que el CSV
#: de Enterprise entrecomillara el campo).
TEXT_FORBIDDEN = re.compile(r'[|/\\"\r\n]')


class L10nPeStockPleWizard(models.TransientModel):
    """PLE 12.1 / 13.1 de Enterprise corregido.

    ``l10n_pe_reports_stock`` arma el TXT en un único método y toma siempre la
    primera factura de la línea de pedido (no ve las entregas en partes, las
    notas de crédito de las devoluciones, el punto de venta ni las
    correcciones manuales). En vez de copiar ese método, se corrige su
    resultado: en cada fila de movimiento el CUO es el id del movimiento, y
    se reemplazan la fecha, el tipo, la serie, el número y la unidad.

    Además se corrigen sus entradas:

    * el periodo y los saldos iniciales se cortan en hora de Lima (Enterprise
      compara ``stock.move.date``, en UTC, con la fecha: un movimiento del 31
      a las 20:00 caía en el mes siguiente y el último día del mes quedaba
      fuera, porque ``date <= date_to`` es «hasta las 00:00 UTC»);
    * la compañía es la raíz con sus sucursales, y el RUC del nombre del
      archivo, el de la raíz;
    * el código y el nombre del producto cumplen la norma (código obligatorio,
      texto sin «|», «/» ni «\\»).
    """
    _inherit = 'l10n_pe.stock.ple.wizard'

    # ------------------------------------------------------------------
    # Periodo y compañía
    # ------------------------------------------------------------------
    def _l10n_pe_kardex_utc(self, day):
        local = PE_TZ.localize(datetime.combine(day, time.min))
        return local.astimezone(pytz.utc).replace(tzinfo=None)

    def _l10n_pe_kardex_bounds(self):
        """[inicio, fin) del periodo en hora de Lima, en UTC sin zona."""
        return (self._l10n_pe_kardex_utc(self.date_from),
                self._l10n_pe_kardex_utc(self.date_to + relativedelta(days=1)))

    def _l10n_pe_kardex_company_domain(self):
        return [('company_id', 'child_of', self.env.company.root_id.id)]

    def _get_ple_reports_data(self):
        dt_from, dt_to = self._l10n_pe_kardex_bounds()
        domain = self._l10n_pe_kardex_company_domain() + [
            ('state', '=', 'done'),
            ('date', '>=', dt_from),
            ('date', '<', dt_to),
            ('product_id.is_storable', '=', True),
            '|',
            ('location_id.usage', 'in', ('supplier', 'customer', 'inventory', 'production')),
            ('location_dest_id.usage', 'in', ('supplier', 'customer', 'inventory', 'production')),
        ]
        return self.env['stock.move'].search(domain, order='product_id, date, id')

    def _l10n_pe_kardex_balances(self, products=None, exclude=False):
        """``{producto: [cantidad, valor]}`` al inicio del periodo (hora de Lima)."""
        dt_from = self._l10n_pe_kardex_bounds()[0]
        domain = self._l10n_pe_kardex_company_domain() + [
            ('product_id.is_storable', '=', True),
            ('state', '=', 'done'),
            ('date', '<', dt_from),
        ]
        if products is not None:
            domain.append(('product_id', 'not in' if exclude else 'in', list(products)))
        balances = defaultdict(lambda: [0.0, 0.0])
        for flag, sign in (('is_in', 1), ('is_out', -1)):
            groups = self.env['stock.move']._read_group(
                domain + [(flag, '=', True)], ['product_id', 'product_uom'],
                ['value:sum', 'quantity:sum'])
            for product, uom, value, qty in groups:
                balances[product][0] += sign * uom._compute_quantity(qty, product.uom_id)
                balances[product][1] += sign * value
        return balances

    def _l10n_pe_kardex_opening_row(self, product, quantity, value, period, report,
                                    establishment='0000'):
        values = {
            'period': period,
            'cuo': f'{product.id}A1'.zfill(6),
            'number': 'A1',
            'establishment': establishment,
            # El tipo de existencia real: es parte de la llave del producto
            # (Enterprise ponía «99» y el saldo no enlazaba con sus filas).
            **self._product_row_values(product),
            'date': self.date_from.strftime('%d/%m/%Y'),
            'document_type': '00',
            'serie': '0',
            'folio': '0',
            'operation_type': '16',
            'product': self._product_name(product),
            'uom': product.uom_id.l10n_pe_edi_measure_unit_code,
        }
        if report == '1201':
            values.update({'qty_in': quantity if quantity > 0 else 0, 'qty_out': 0,
                           'state': '1'})
            return values
        values.update({
            'valuation': self._get_stock_valuation(product.categ_id.id),
            **self._valuation_columns(quantity, value, quantity, value, is_balance=True),
            'state': '1',
        })
        return values

    def _append_valuation_line(self, move, period, report):
        product = move.product_id
        quantity, value = self._l10n_pe_kardex_balances([product.id])[product]
        if not quantity:
            return {}
        return self._l10n_pe_kardex_opening_row(
            product, quantity, value, period, report,
            move.warehouse_id.l10n_pe_anexo_establishment_code or '0000')

    def _append_historic_valuation_lines(self, products, period, report):
        balances = self._l10n_pe_kardex_balances(products, exclude=True) if products \
            else self._l10n_pe_kardex_balances()
        return [
            self._l10n_pe_kardex_opening_row(product, quantity, value, period, report)
            for product, (quantity, value) in balances.items() if quantity
        ]

    def get_ple_report(self, report_number):
        action = super().get_ple_report(report_number)
        # El libro es del RUC: el de la compañía raíz (una sucursal puede no
        # tener RUC propio).
        root_vat = self.env.company.root_id.vat or ''
        if self.report_filename and root_vat:
            self.report_filename = 'LE%s%s' % (
                root_vat, self.report_filename[2 + len(self.env.company.vat or ''):])
        return action

    # ------------------------------------------------------------------
    # Campos del producto
    # ------------------------------------------------------------------
    @api.model
    def _product_row_values(self, product):
        values = super()._product_row_values(product)
        if product and not values.get('default_code'):
            # Campo 7: obligatorio y sin valor por defecto en la norma; sin
            # código interno se usa uno estable derivado del id.
            values['default_code'] = 'P%06d' % product.id
        return values

    @api.model
    def _product_name(self, product):
        return ' '.join(TEXT_FORBIDDEN.sub(' ', product.name or '').split())[:80]

    # ------------------------------------------------------------------
    # Posproceso de las filas
    # ------------------------------------------------------------------
    def _get_ple_report_content(self, report):
        content = super()._get_ple_report_content(report)
        return self._l10n_pe_kardex_apply_documents(content) if content else content

    def _l10n_pe_kardex_columns(self):
        """Posiciones de fecha, tipo, serie y número en la fila del TXT.

        Orden de las claves de la fila en Enterprise: periodo, CUO, número
        correlativo, establecimiento, columnas del producto, fecha, tipo,
        serie, número, tipo de operación, descripción, unidad…
        """
        offset = 4 + len(self._product_row_values(self.env['product.product']))
        return offset, offset + 1, offset + 2, offset + 3

    def _l10n_pe_kardex_apply_documents(self, content):
        i_date, i_type, i_serie, i_folio = self._l10n_pe_kardex_columns()
        i_uom = i_folio + 3
        lines = content.split('\n')

        def is_move_row(cols):
            # Filas de movimiento: CUO numérico (id del movimiento) y correlativo M1.
            # Las de saldo inicial llevan «<producto>A1».
            return len(cols) > i_uom and cols[2] == 'M1' and cols[1].isdigit()

        rows = [line.split('|') if '"' not in line else None for line in lines]
        ids = {int(cols[1]) for cols in rows if cols and is_move_row(cols)}
        moves = {str(m.id).zfill(6): m
                 for m in self.env['stock.move'].browse(ids).exists()}
        result = []
        for line, cols in zip(lines, rows):
            move = moves.get(cols[1]) if cols and is_move_row(cols) else None
            if move:
                local_date = pytz.utc.localize(move.date).astimezone(PE_TZ).date()
                stored = move.l10n_pe_kardex_doc_type and move.l10n_pe_kardex_number
                # Campo 10: la fecha del comprobante (el guardado o, sin él, el
                # que eligió Enterprise), salvo que caiga después del periodo
                # (factura de febrero por una entrega de enero) o no haya
                # comprobante (guía, corrección manual): la del movimiento.
                if stored:
                    doc_date = move.l10n_pe_kardex_invoice_id.invoice_date
                else:
                    try:
                        doc_date = datetime.strptime(cols[i_date], '%d/%m/%Y').date()
                    except ValueError:
                        doc_date = None
                if not doc_date or doc_date > self.date_to:
                    doc_date = local_date
                cols[i_date] = doc_date.strftime('%d/%m/%Y')
                if stored:
                    cols[i_type] = move.l10n_pe_kardex_doc_type
                    cols[i_serie] = move.l10n_pe_kardex_serie or '0'
                    cols[i_folio] = move.l10n_pe_kardex_number
                # Campo 16: la unidad del producto, la misma en que se expresa
                # la cantidad (Enterprise ponía la del movimiento: 120 «BX»
                # por 120 unidades).
                cols[i_uom] = move.product_id.uom_id.l10n_pe_edi_measure_unit_code or cols[i_uom]
                line = '|'.join(cols)
            result.append(line)
        return '\n'.join(result)

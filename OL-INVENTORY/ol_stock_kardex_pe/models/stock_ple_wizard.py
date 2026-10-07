import re
from collections import defaultdict
from datetime import datetime, time

import pytz
from dateutil.relativedelta import relativedelta

from odoo import api, models
from odoo.tools import float_repr

PE_TZ = pytz.timezone('America/Lima')
#: Texto del PLE: la norma prohíbe «|», «/» y «\» (y el «"» hacía que el CSV
#: de Enterprise entrecomillara el campo).
#: Columnas numéricas del 13.1 (las que Enterprise formatea con 2 decimales).
KARDEX_FLOAT_FIELDS = ('qty_in', 'cost_in', 'value_in', 'qty_out', 'cost_out',
                       'value_out', 'remaining', 'unit_cost_final', 'value')
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
        # El valor del movimiento ya incluye los costos en destino validados
        # después: los fechados en este periodo o en uno posterior no son
        # saldo inicial (van como fila en su periodo).
        for landed in self._l10n_pe_kardex_landed_costs([
                ('move_id.date', '<', dt_from), ('cost_id.date', '>=', self.date_from)]):
            product = landed['move'].product_id
            if products is not None and (product.id in products) == exclude:
                continue
            balances[product][1] -= landed['value']
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
    def _get_stock_valuation(self, category_id):
        """Campo 17 del 13.1, tabla 14 del Anexo 3: 1 promedio ponderado,
        2 PEPS, 3 existencias básicas, 9 otros. Enterprise ponía «3» al costo
        estándar, que no es el método de existencias básicas: va como «9»."""
        code = super()._get_stock_valuation(category_id)
        cost_method = self.env['product.category'].browse(category_id).property_cost_method
        return '9' if cost_method == 'standard' else code

    @api.model
    def _product_name(self, product):
        return ' '.join(TEXT_FORBIDDEN.sub(' ', product.name or '').split())[:80]

    # ------------------------------------------------------------------
    # Posproceso de las filas
    # ------------------------------------------------------------------
    def _get_ple_report_content(self, report):
        content = super()._get_ple_report_content(report)
        if content:
            content = self._l10n_pe_kardex_apply_documents(content)
            if report == '1301':
                content = self._l10n_pe_kardex_landed_by_period(content)
        return content

    # ------------------------------------------------------------------
    # Costos en destino por periodo
    # ------------------------------------------------------------------
    def _l10n_pe_kardex_landed_costs(self, domain):
        """Costos en destino validados (``stock_landed_costs``), si está
        instalado: ``[{id, move, value, date, name}]``."""
        if 'stock.valuation.adjustment.lines' not in self.env:
            return []
        # sudo: el libro lo genera quien ve inventario aunque no gestione los
        # costos en destino (Enterprise también los lee con sudo).
        lines_sudo = self.env['stock.valuation.adjustment.lines'].sudo().search(
            [('cost_id.state', '=', 'done'),
             ('move_id.company_id', 'child_of', self.env.company.root_id.id)] + domain)
        return [{'id': line.id, 'move': line.move_id.sudo(False),
                 'value': line.additional_landed_cost, 'date': line.cost_id.date,
                 'name': line.cost_id.name or ''} for line in lines_sudo]

    def _l10n_pe_kardex_landed_by_period(self, content):
        """Cada costo en destino en el periodo de su fecha, no en el del
        movimiento que encarece.

        Enterprise (``l10n_pe_reports_stock_landed_costs``) cuelga el ajuste
        del movimiento: uno validado en febrero para una compra de enero
        salía en el TXT de enero (con fecha de febrero) y en el de febrero
        quedaba dentro del saldo inicial. Aquí:

        * se quitan las filas de costos fechados después del periodo
          (Enterprise ya los descuenta de la fila del movimiento);
        * se añaden las de costos del periodo sobre movimientos anteriores;
        * se rehace el saldo acumulado de los productos tocados.
        """
        i_date = self._l10n_pe_kardex_columns()[0]
        i_value_in = self._l10n_pe_kardex_columns()[3] + 7
        lines = content.split('\n')
        rows = [line.split('|') if line and '"' not in line else None for line in lines]
        valued = [cols for cols in rows if cols and len(cols) > i_value_in + 7]
        if not valued:
            return content
        dt_from, dt_to = self._l10n_pe_kardex_bounds()
        period_moves = self._get_ple_reports_data()
        later = {
            landed['id']: landed for landed in self._l10n_pe_kardex_landed_costs([
                ('move_id', 'in', period_moves.ids), ('cost_id.date', '>', self.date_to)])}
        earlier = self._l10n_pe_kardex_landed_costs([
            ('move_id.date', '<', dt_from),
            ('cost_id.date', '>=', self.date_from), ('cost_id.date', '<=', self.date_to)])
        if not later and not earlier:
            return content

        def product_key(cols):
            return tuple(cols[4:i_date])

        touched = set()
        keep = []
        for line, cols in zip(lines, rows):
            landed_id = cols and cols[1].endswith('LC') and cols[1][:-2].lstrip('0')
            if landed_id and landed_id.isdigit() and int(landed_id) in later:
                # Enterprise ya lo descontó de la fila del movimiento: basta
                # con quitar su fila y rehacer el saldo.
                touched.add(product_key(cols))
                continue
            keep.append((line, cols))
        period = '%s%s00' % (self.date_from.year, str(self.date_from.month).zfill(2))
        for landed in sorted(earlier, key=lambda l: (l['date'], l['id'])):
            move = landed['move']
            serie_folio = self._get_serie_folio(landed['name'])
            row = self._build_adjustment_line(move, move.product_id, period, {
                'cuo': f"{landed['id']}LC".zfill(6),
                'value': landed['value'],
                'operation_type': '26',
                'date': landed['date'].strftime('%d/%m/%Y'),
                'document_type': '00',
                'serie': serie_folio['serie'].replace(' ', '').replace('/', '') or '0',
                'folio': serie_folio['folio'].replace(' ', '') or '0',
            }, [0.0, 0.0])
            row['uom'] = move.product_id.uom_id.l10n_pe_edi_measure_unit_code or row['uom']
            # Mismo formato que Enterprise (importes con 2 decimales y palote final).
            cols = [float_repr(round(float(v or 0.0), 2), precision_digits=2)
                    if k in KARDEX_FLOAT_FIELDS else str(v) for k, v in row.items()] + ['']
            key = product_key(cols)
            touched.add(key)
            # Tras el saldo inicial del producto y antes de sus filas de fecha posterior.
            position = None
            for index, (_line, other) in enumerate(keep):
                if not other or product_key(other) != key:
                    if position is not None:
                        break
                    continue
                position = index + 1
                if other[2] != 'A1' and self._l10n_pe_kardex_date(other[i_date]) > landed['date']:
                    position = index
                    break
            if position is None:
                position = len(keep)
            keep.insert(position, ('|'.join(cols), cols))
        # Saldo acumulado de los productos tocados.
        running = {}
        result = []
        for line, cols in keep:
            if cols and len(cols) > i_value_in + 7 and product_key(cols) in touched:
                key = product_key(cols)
                qty_in, value_in = float(cols[i_value_in - 2] or 0), float(cols[i_value_in] or 0)
                qty_out, value_out = float(cols[i_value_in + 1] or 0), float(cols[i_value_in + 3] or 0)
                if cols[2] == 'A1':
                    qty, value = float(cols[i_value_in + 4] or 0), float(cols[i_value_in + 6] or 0)
                else:
                    qty, value = running.get(key, (0.0, 0.0))
                    qty += qty_in + qty_out
                    value += value_in + value_out
                running[key] = (qty, value)
                cols[i_value_in + 4] = float_repr(round(qty, 2), precision_digits=2)
                cols[i_value_in + 5] = float_repr(round(abs(value / (qty or 1)), 2), precision_digits=2)
                cols[i_value_in + 6] = float_repr(round(value, 2), precision_digits=2)
                line = '|'.join(cols)
            result.append(line)
        return '\n'.join(result)

    @api.model
    def _l10n_pe_kardex_date(self, text):
        try:
            return datetime.strptime(text, '%d/%m/%Y').date()
        except ValueError:
            return datetime.max.date()

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

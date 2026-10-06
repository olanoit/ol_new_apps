from odoo import models


class L10nPeStockPleWizard(models.TransientModel):
    """PLE 12.1 / 13.1 de Enterprise con el documento guardado en el movimiento.

    ``l10n_pe_reports_stock`` arma el TXT en un único método y toma siempre la
    primera factura de la línea de pedido (no ve las entregas en partes, las
    notas de crédito de las devoluciones, el punto de venta ni las
    correcciones manuales). En vez de copiar ese método, se corrige su
    resultado: en cada fila de movimiento el CUO es el id del movimiento, y
    se reemplazan la fecha, el tipo, la serie y el número del documento.
    """
    _inherit = 'l10n_pe.stock.ple.wizard'

    def _get_ple_report_content(self, report):
        content = super()._get_ple_report_content(report)
        return self._l10n_pe_kardex_apply_documents(content) if content else content

    def _l10n_pe_kardex_columns(self):
        """Posiciones de fecha, tipo, serie y número en la fila del TXT.

        Orden de las claves de la fila en Enterprise: periodo, CUO, número
        correlativo, establecimiento, columnas del producto, fecha, tipo,
        serie, número…
        """
        offset = 4 + len(self._product_row_values(self.env['product.product']))
        return offset, offset + 1, offset + 2, offset + 3

    def _l10n_pe_kardex_apply_documents(self, content):
        i_date, i_type, i_serie, i_folio = self._l10n_pe_kardex_columns()
        lines = content.split('\n')

        def is_move_row(cols):
            # Filas de movimiento: CUO numérico (id del movimiento) y correlativo M1.
            # Las de saldo inicial llevan «<producto>A1»; una fila con comillas
            # (un campo con «|») no se toca.
            return len(cols) > i_folio and cols[2] == 'M1' and cols[1].isdigit()

        rows = [line.split('|') if '"' not in line else None for line in lines]
        ids = {int(cols[1]) for cols in rows if cols and is_move_row(cols)}
        moves = self.env['stock.move'].browse(ids).exists().filtered(
            lambda m: m.l10n_pe_kardex_doc_type and m.l10n_pe_kardex_number)
        by_cuo = {str(m.id).zfill(6): m for m in moves}
        if not by_cuo:
            return content
        result = []
        for line, cols in zip(lines, rows):
            move = by_cuo.get(cols[1]) if cols and is_move_row(cols) else None
            if move:
                invoice_date = move.l10n_pe_kardex_invoice_id.invoice_date
                if invoice_date:
                    cols[i_date] = invoice_date.strftime('%d/%m/%Y')
                cols[i_type] = move.l10n_pe_kardex_doc_type
                cols[i_serie] = move.l10n_pe_kardex_serie or '0'
                cols[i_folio] = move.l10n_pe_kardex_number
                line = '|'.join(cols)
            result.append(line)
        return '\n'.join(result)

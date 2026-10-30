from odoo import _, models

from .statement_parser import StatementParseError, parse_statement


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def _l10n_pe_parse_statement(self, raw):
        """Movimientos del archivo si es un extracto reconocible, o ``None``."""
        if not raw:
            return None
        # Odoo 20: los binarios llegan como BinaryValue.
        raw = getattr(raw, 'content', raw)
        try:
            return parse_statement(raw)
        except StatementParseError:
            return None
        except Exception:  # noqa: BLE001 - un archivo de otro formato: lo resuelve el importador nativo
            return None

    def _import_bank_statement(self, attachments):
        # Un extracto reconocido se importa directo, sin el mapeo de columnas
        # del importador CSV/Excel nativo.
        if len(attachments) == 1 and self._l10n_pe_parse_statement(attachments.raw):
            return super(AccountJournal, self.with_context(l10n_pe_bank_statement=True)) \
                ._import_bank_statement(attachments)
        return super()._import_bank_statement(attachments)

    def _check_file_format(self, filename):
        # Con el extracto ya reconocido, el importador CSV no debe tomarlo.
        if self.env.context.get('l10n_pe_bank_statement'):
            return False
        return super()._check_file_format(filename)

    def _parse_bank_statement_file(self, raw_file):
        if not self.env.context.get('l10n_pe_bank_statement'):
            return super()._parse_bank_statement_file(raw_file)
        data = self._l10n_pe_parse_statement(raw_file)
        if not data:
            return super()._parse_bank_statement_file(raw_file)
        transactions = [{
            'date': line['date'],
            'amount': line['amount'],
            'payment_ref': line['payment_ref'],
            'ref': line['ref'] or False,
            'unique_import_id': line['unique_import_id'],
        } for line in data['transactions']]
        statement = {
            'name': _('%(journal)s %(start)s al %(end)s', journal=self.name,
                      start=data['date_from'].strftime('%d/%m/%Y'), end=data['date_to'].strftime('%d/%m/%Y')),
            'date': data['date_to'],
            'transactions': transactions,
        }
        if 'balance_start' in data:
            statement['balance_start'] = data['balance_start']
            statement['balance_end_real'] = data['balance_end_real']
        # Moneda y cuenta: las del diario desde el que se importa.
        return [(None, None, [statement])]

# -*- coding: utf-8 -*-
"""El número de operación del banco pasa a la referencia nativa del pago
(payment_reference): se copia donde la referencia está vacía."""


def migrate(cr, version):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'account_payment' AND column_name = 'bank_operation_number'
    """)
    if not cr.fetchone():
        return
    cr.execute("""
        UPDATE account_payment
           SET payment_reference = bank_operation_number
         WHERE COALESCE(bank_operation_number, '') != ''
           AND COALESCE(payment_reference, '') = ''
    """)

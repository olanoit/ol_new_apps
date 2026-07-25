# -*- coding: utf-8 -*-
"""Fase 7: formatos puros de los TXT bancarios de pago masivo.

Las expectativas (anchos de campo, padding, montos sin separador,
checksums, tabs literales heredados) están extraídas del generador v18
``hr_automate_multipayment/models/hr_automate_multipayment.py``.
Las funciones bajo prueba son puras (dicts → str): no requieren datos
en BD.
"""
from datetime import date, datetime

from odoo.tests import TransactionCase, tagged

from odoo.addons.al_hr_pe_reports.models.hr_multipayment import (
    banbif_cts_txt,
    banbif_haberes_txt,
    bbva_cts_txt,
    bbva_haberes_txt,
    bcp_cts_txt,
    bcp_haberes_txt,
    clean_text,
    interbank_cts_txt,
    interbank_haberes_txt,
    scotiabank_cts_txt,
    scotiabank_haberes_txt,
    txt_field,
)


def make_header(**overrides):
    """Cabecera tipo: cuenta de cargo BCP corriente en soles."""
    header = {
        'charge_acc': '1912345678901',
        'charge_acc_type': '0',
        'charge_branch': '0170',
        'currency': 'PEN',
        'payment_date': date(2026, 7, 24),
        'now': datetime(2026, 7, 24, 14, 30, 9),
        'glosa': 'JUL 2026',
        'company_name': 'ALTA LATAM SAC',
        'company_vat': '20123456789',
        'process_type': 'A',
        'process_hour': ' ',
        'owner_validation': 'S',
        'alert_indicator': '',
        'idc_flag': True,
        'subtype': 'O',
        'person_type': 'P',
        'payment_way': '3',
        'subtype_banbif': '5',
        'cts_dollars': False,
        'cts_name': 'CTS Mayo - Octubre 2026',
        'cts_checksum_accs': [],
    }
    header.update(overrides)
    return header


def make_line(**overrides):
    """Línea tipo: cuenta de ahorros con abono de S/ 1500.50."""
    line = {
        'doc_bbva': 'L',
        'doc_bcp': '1',
        'doc_interbank': '01',
        'doc_banbif': '1',
        'doc_sunat': '1',
        'doc_number': '12345678',
        'name': 'PEREZ QUISPE JUAN',
        'last_name': 'PEREZ',
        'm_last_name': 'QUISPE',
        'names': 'JUAN',
        'acc_number': '01230000009876543210',
        'acc_type': '1',
        'acc_bic': '038',
        'amount': 1500.50,
        'amount_soles': 1500.50,
        'computable_base': 4000.0,
        'reference': 'SLIP001',
        'email': 'jperez@empresa.pe',
        'phone': '999888777',
        'street': 'AV SIEMPRE VIVA 123',
        'mobile': '999888777',
    }
    line.update(overrides)
    return line


def rows(content):
    """Divide el TXT en filas; toda fila debe terminar en CRLF."""
    assert content == '' or content.endswith('\r\n')
    return content.split('\r\n')[:-1]


@tagged('post_install', '-at_install')
class TestFase7MultipaymentFormats(TransactionCase):
    """Formatos puros por banco (paridad con el generador v18)."""

    # ------------------------------------------------------------------
    # Helpers de bajo nivel
    # ------------------------------------------------------------------
    def test_txt_field_str(self):
        """'str': limpia caracteres, trunca y rellena con espacios."""
        self.assertEqual(txt_field('ABC', 'str', 6), 'ABC   ')
        self.assertEqual(txt_field('ABC', 'str', 6, left=False), '   ABC')
        self.assertEqual(txt_field('ABCDEFGH', 'str', 4), 'ABCD')
        self.assertEqual(txt_field('ÑOÑO SAC', 'str', 10), 'NONO SAC  ')

    def test_txt_field_int(self):
        """'int': relleno con ceros."""
        self.assertEqual(txt_field(7, 'int', 6, left=False), '000007')
        self.assertEqual(txt_field(7, 'int', 6), '700000')  # rareza v18

    def test_txt_field_float(self):
        """'float': 2 decimales, con/sin punto, relleno de ceros."""
        self.assertEqual(txt_field(1500.5, 'float', 15, left=False),
                         '000000000150050')
        self.assertEqual(
            txt_field(1500.5, 'float', 17, left=False, decimal_point=True),
            '00000000001500.50')
        self.assertEqual(txt_field(1500, 'float', 15, left=False),
                         '000000000150000')
        # left=True rellena ceros a la DERECHA (rareza v18 conservada,
        # usada en el total USD de Interbank).
        self.assertEqual(txt_field(2000.25, 'float', 15), '200025000000000')

    def test_txt_field_dates(self):
        self.assertEqual(txt_field(date(2026, 7, 5), 'date'), '20260705')
        self.assertEqual(
            txt_field(datetime(2026, 7, 5, 14, 30, 9), 'datetime'),
            '20260705143009')

    def test_clean_text(self):
        self.assertEqual(clean_text('ÑANDÚ PÉREZ'), 'NANDU PEREZ')
        self.assertEqual(clean_text('J.R.R. / TOLKIEN-2'), 'JRR  TOLKIEN2')
        self.assertEqual(clean_text('a@b:c'), 'aabc')
        self.assertEqual(clean_text(None), '')

    # ------------------------------------------------------------------
    # BBVA
    # ------------------------------------------------------------------
    def test_bbva_haberes(self):
        """Cabecera '700' de 155 posiciones y detalle '002' de 233; la
        cabecera cuenta TODAS las líneas pero el detalle omite ≤ 0."""
        header = make_header(charge_acc='01230000001234567890')
        lines = [make_line(), make_line(amount=0.0)]
        result = rows(bbva_haberes_txt(header, lines))
        self.assertEqual(len(result), 2)  # cabecera + 1 detalle
        head = result[0]
        self.assertEqual(len(head), 155)
        self.assertEqual(head[0:3], '700')
        # Cuenta de cargo con la sucursal insertada tras la posición 8.
        self.assertEqual(head[3:27], '012300000170001234567890')
        self.assertEqual(head[27:30], 'PEN')
        self.assertEqual(head[30:45], '000000000150050')  # total sin punto
        self.assertEqual(head[45], 'A')
        self.assertEqual(head[46:54], ' ' * 8)  # fecha solo si proceso F
        self.assertEqual(head[55:80], 'JUL 2026'.ljust(25))
        self.assertEqual(head[80:86], '000002')  # cuenta la línea en 0
        self.assertEqual(head[86], 'S')
        self.assertEqual(head[87:105], '0' * 18)
        detail = result[1]
        self.assertEqual(len(detail), 233)
        self.assertEqual(detail[0:3], '002')
        self.assertEqual(detail[3], 'L')
        self.assertEqual(detail[4:16], '12345678    ')
        self.assertEqual(detail[16], 'P')  # 'I' solo para CCI
        self.assertEqual(detail[17:37], '01230000009876543210')
        self.assertEqual(detail[37:77], 'PEREZ QUISPE JUAN'.ljust(40))
        self.assertEqual(detail[77:92], '000000000150050')
        self.assertEqual(detail[92:132], 'SLIP001'.ljust(40))
        self.assertEqual(detail[132], ' ')  # sin indicador de aviso

    def test_bbva_haberes_cci(self):
        """Cuenta CCI: tipo de abono 'I'."""
        header = make_header(charge_acc='01230000001234567890')
        lines = [make_line(acc_type='3',
                           acc_number='00212345678901234567')]
        detail = rows(bbva_haberes_txt(header, lines))[1]
        self.assertEqual(detail[16], 'I')

    def test_bbva_cts(self):
        """Cabecera 600/610 y TAB literal v18 entre monto y referencia."""
        header = make_header(charge_acc='01230000001234567890',
                             process_type='F')
        lines = [make_line()]
        result = rows(bbva_cts_txt(header, lines))
        head = result[0]
        self.assertEqual(head[0:3], '600')  # 610 en dólares
        self.assertEqual(head[27:30], 'PEN')
        self.assertEqual(head[45], 'F')
        self.assertEqual(head[46:54], '20260724')  # process_type == 'F'
        self.assertEqual(head[54], 'D')  # hora fija v18
        self.assertEqual(head[80:86], '000001')
        self.assertEqual(len(head), 155)  # 87 + 68 espacios
        detail = result[1]
        self.assertEqual(detail[92], '\t')  # tab heredado del v18
        # La referencia pasa por la limpieza de caracteres ('-' cae),
        # igual que en el parse_to_txt del v18.
        self.assertEqual(detail[93:133],
                         'CTS Mayo  Octubre 2026'.ljust(40))
        self.assertEqual(detail[184:237], ' ' * 53)
        self.assertEqual(detail[252:255], 'PEN')
        self.assertEqual(len(detail), 273)
        # En dólares: cabecera 610 y moneda USD.
        usd = rows(bbva_cts_txt(
            make_header(charge_acc='01230000001234567890',
                        cts_dollars=True),
            [make_line(amount=500.0)]))
        self.assertEqual(usd[0][0:3], '610')
        self.assertEqual(usd[0][27:30], 'USD')

    # ------------------------------------------------------------------
    # BCP
    # ------------------------------------------------------------------
    def test_bcp_haberes(self):
        """Cabecera de 113 con checksum de cuentas y detalle de 195 con
        monto de 17 posiciones CON punto decimal."""
        header = make_header()
        lines = [
            make_line(acc_number='19187654321098', amount=1200.0),
            make_line(acc_number='00219100112233445566', acc_type='3',
                      amount=800.25),
            make_line(amount=0.0),
        ]
        result = rows(bcp_haberes_txt(header, lines))
        self.assertEqual(len(result), 3)
        head = result[0]
        self.assertEqual(len(head), 113)
        self.assertEqual(head[0], '1')
        self.assertEqual(head[1:7], '000002')  # solo montos > 0
        self.assertEqual(head[7:15], '20260724')
        self.assertEqual(head[15], 'O')   # subtipo de planilla
        self.assertEqual(head[16], 'C')   # cargo en cuenta
        self.assertEqual(head[17:21], '0001')  # soles
        self.assertEqual(head[21:41], '1912345678901'.ljust(20))
        self.assertEqual(head[41:58], '00000000002000.25')
        # Checksum: ahorro desde posición 3, CCI desde posición 10,
        # más la cuenta de cargo desde posición 3, a 15 con ceros.
        expected = str(int('87654321098') + int('2233445566')
                       + int('2345678901')).rjust(15, '0')
        self.assertEqual(head[98:113], expected)
        detail = result[1]
        self.assertEqual(len(detail), 195)
        self.assertEqual(detail[0], '2')
        self.assertEqual(detail[1], 'A')  # ahorros
        self.assertEqual(detail[2:22], '19187654321098'.ljust(20))
        self.assertEqual(detail[22], '1')  # código BCP del DNI
        self.assertEqual(detail[23:35], '12345678'.ljust(12))
        self.assertEqual(detail[35:38], '   ')
        self.assertEqual(detail[38:113], 'PEREZ QUISPE JUAN'.ljust(75))
        self.assertEqual(detail[113:153], 'SLIP001'.ljust(40))
        self.assertEqual(detail[153:173], 'ALTA LATAM SAC'.ljust(20))
        self.assertEqual(detail[173:177], '0001')
        self.assertEqual(detail[177:194], '00000000001200.00')
        self.assertEqual(detail[194], 'S')  # idc_flag
        self.assertEqual(result[2][1], 'B')  # CCI → tipo B

    def test_bcp_cts(self):
        """Cabecera con RUC y detalle cuyo campo de monto concatena
        monto + moneda + base computable ×4."""
        header = make_header(
            cts_checksum_accs=['19187654321098', '19112223334445'])
        lines = [make_line(acc_number='19187654321098')]
        result = rows(bcp_cts_txt(header, lines))
        head = result[0]
        self.assertEqual(len(head), 125)
        self.assertEqual(head[1:7], '000001')
        self.assertEqual(head[15], 'C')
        self.assertEqual(head[16:20], '0001')
        self.assertEqual(head[40], '6')  # tipo de doc de la empresa: RUC
        self.assertEqual(head[41:53], '20123456789'.ljust(12))
        expected = str(int('2345678901') + int('87654321098')
                       + int('12223334445')).rjust(15, '0')
        self.assertEqual(head[110:125], expected)
        detail = result[1]
        self.assertEqual(len(detail), 214)
        self.assertEqual(detail[176:193], '00000000001500.50')
        self.assertEqual(detail[193:197], '0001')
        self.assertEqual(detail[197:214], '00000000004000.00')

    # ------------------------------------------------------------------
    # Interbank
    # ------------------------------------------------------------------
    def test_interbank_haberes(self):
        """Cabecera '0104' de 104 y detalle de 380 con el nombre
        descompuesto en 20+20+20 para persona natural."""
        header = make_header(charge_acc='1231234567890')
        lines = [make_line(acc_number='1239876543210', acc_type='0'),
                 make_line(amount=0.0)]
        result = rows(interbank_haberes_txt(header, lines))
        self.assertEqual(len(result), 2)
        head = result[0]
        self.assertEqual(len(head), 104)
        self.assertEqual(head[0:4], '0104')
        self.assertEqual(head[4:40], ' ' * 36)
        self.assertEqual(head[40:54], '20260724143009')
        self.assertEqual(head[54:63], ' ' * 9)
        self.assertEqual(head[63:69], '000002')  # cuenta la línea en 0
        self.assertEqual(head[69:84], '000000000150050')  # soles
        self.assertEqual(head[84:99], '0' * 15)  # sin USD
        self.assertEqual(head[99:104], 'MC001')
        detail = result[1]
        self.assertEqual(len(detail), 380)
        self.assertEqual(detail[0:2], '02')
        self.assertEqual(detail[2:4], '01')
        self.assertEqual(detail[4:24], '12345678'.ljust(20))
        self.assertEqual(detail[51:53], '01')  # moneda de cargo
        self.assertEqual(detail[53:68], '000000000150050')
        self.assertEqual(detail[68], ' ')
        self.assertEqual(detail[69:71], '09')  # no CCI
        self.assertEqual(detail[71:74], '001')  # corriente
        self.assertEqual(detail[74:76], '01')
        self.assertEqual(detail[76:99], '1239876543210'.ljust(23))
        self.assertEqual(detail[99], 'P')
        self.assertEqual(detail[100:102], '01')
        self.assertEqual(detail[102:117], '12345678'.ljust(15))
        self.assertEqual(detail[117:177], 'PEREZ'.ljust(20)
                         + 'QUISPE'.ljust(20) + 'JUAN'.ljust(20))
        self.assertEqual(detail[177:179], '  ')
        self.assertEqual(detail[179:194], '0' * 15)
        self.assertEqual(detail[194:380], ' ' * 186)

    def test_interbank_haberes_usd_pad_derecha(self):
        """Total USD de cabecera: relleno de ceros a la DERECHA (rareza
        v18 conservada)."""
        header = make_header(charge_acc='1231234567890', currency='USD')
        head = rows(interbank_haberes_txt(
            header, [make_line(amount=2000.25)]))[0]
        self.assertEqual(head[69:84], '0' * 15)
        self.assertEqual(head[84:99], '200025000000000')

    def test_interbank_cts(self):
        """Cabecera '0106' y 7 TABs literales heredados en el detalle;
        el tipo de cuenta de ahorros pasa a '007'."""
        header = make_header(charge_acc='1231234567890')
        lines = [make_line(acc_number='1239876543210')]
        result = rows(interbank_cts_txt(header, lines))
        self.assertEqual(result[0][0:4], '0106')
        detail = result[1]
        self.assertEqual(detail[69:71], '09')
        self.assertEqual(detail[71:74], '007')  # ahorros CTS
        self.assertEqual(detail[74:81], '\t' * 7)  # tabs heredados v18
        self.assertEqual(detail[81:83], '01')
        # Base computable ×4 como «monto CTS» de 15 posiciones.
        self.assertEqual(detail[184:201], '01' + '000000000400000')

    # ------------------------------------------------------------------
    # Scotiabank
    # ------------------------------------------------------------------
    def test_scotiabank_haberes(self):
        """Sin cabecera; fila de 140 con monto de 11 posiciones sin
        punto y concepto fijo HABERES."""
        header = make_header(charge_acc='12345678901234')
        lines = [make_line(acc_number='1234567890'),
                 make_line(amount=0.0)]
        result = rows(scotiabank_haberes_txt(header, lines))
        self.assertEqual(len(result), 1)  # sin cabecera, omite ≤ 0
        row = result[0]
        self.assertEqual(len(row), 140)
        self.assertEqual(row[0], '1')  # DNI (sunat 1 → 1)
        self.assertEqual(row[1:13], '12345678'.ljust(12))
        self.assertEqual(row[13:73], 'PEREZ QUISPE JUAN'.ljust(60))
        self.assertEqual(row[73], '3')  # forma de pago
        self.assertEqual(row[74:84], '1234567890')
        self.assertEqual(row[84:104], ' ' * 20)  # sin CCI
        self.assertEqual(row[104:115], '00000150050')
        self.assertEqual(row[115], '1')  # régimen laboral
        self.assertEqual(row[116:118], '00')  # soles
        self.assertEqual(row[118:138], 'HABERES'.ljust(20))
        self.assertEqual(row[138:140], '02')

    def test_scotiabank_cts(self):
        """rem_amount: 2 decimales sin punto a 11 con ceros, SIEMPRE del
        monto en soles; concepto = slice crudo de 20 del nombre CTS."""
        header = make_header(charge_acc='12345678901234')
        lines = [make_line(acc_number='1234567890')]
        row = rows(scotiabank_cts_txt(header, lines))[0]
        self.assertEqual(row[0], '1')
        self.assertEqual(row[1:13], '12345678'.ljust(12))
        self.assertEqual(row[73], '1')  # abono en cuenta CTS
        self.assertEqual(row[74:84], '1234567890')  # 10 primeras
        self.assertEqual(row[84:104], ' ' * 20)
        self.assertEqual(row[104:115], '00000150050')
        self.assertEqual(row[115:117], '00')
        self.assertEqual(row[117:137], 'CTS Mayo - Octubre 2026'[0:20])
        self.assertEqual(row[137:139], '05')

    # ------------------------------------------------------------------
    # BanBif
    # ------------------------------------------------------------------
    def test_banbif_haberes(self):
        """Correlativo a 7 con espacios (solo filas emitidas), monto de
        14 sin punto con espacios y cuenta a 20 con espacios."""
        header = make_header()
        lines = [make_line(amount=0.0), make_line()]
        result = rows(banbif_haberes_txt(header, lines))
        self.assertEqual(len(result), 1)  # omite la línea en 0
        row = result[0]
        self.assertEqual(row[0:7], '      1')  # correlativo reinicia
        self.assertEqual(row[7], '1')  # código BanBif del DNI
        self.assertEqual(row[8:19], '12345678'.ljust(11))
        self.assertEqual(row[19:39], 'PEREZ'.ljust(20))
        self.assertEqual(row[39:59], 'QUISPE'.ljust(20))
        self.assertEqual(row[59:103], 'JUAN'.ljust(44))
        self.assertEqual(row[103:163], 'AV SIEMPRE VIVA 123'.ljust(60))
        self.assertEqual(row[163:173], '999888777 ')
        self.assertEqual(row[173], 'H')
        self.assertEqual(row[174:177], '038')
        self.assertEqual(row[177:197], '01230000009876543210')
        self.assertEqual(row[197], '1')  # soles
        self.assertEqual(row[198:212], '        150050')
        self.assertEqual(row[212], '5')  # quinta categoría
        self.assertEqual(len(row), 213)

    def test_banbif_haberes_defaults(self):
        """Sin dirección/celular: SIN DIRECCION / SINTELEFON."""
        header = make_header()
        row = rows(banbif_haberes_txt(
            header, [make_line(street='', mobile='')]))[0]
        self.assertEqual(row[103:163], 'SIN DIRECCION'.ljust(60))
        self.assertEqual(row[163:173], 'SINTELEFON')

    def test_banbif_cts(self):
        """CTS: planilla 'C', motivo '0', SIN filtro de monto > 0
        (rareza v18 conservada) y moneda 2 en dólares."""
        header = make_header()
        lines = [make_line(), make_line(amount=0.0)]
        result = rows(banbif_cts_txt(header, lines))
        self.assertEqual(len(result), 2)  # también la línea en 0
        row = result[0]
        self.assertEqual(row[0:7], '      1')
        self.assertEqual(result[1][0:7], '      2')
        self.assertEqual(row[173], 'C')
        self.assertEqual(row[197], '1')
        self.assertEqual(row[212], '0')
        usd = rows(banbif_cts_txt(
            make_header(cts_dollars=True), [make_line(amount=500.0)]))[0]
        self.assertEqual(usd[197], '2')
        self.assertEqual(usd[198:212], '         50000')

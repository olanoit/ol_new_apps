{
    'name': 'PE - Extractos de bancos peruanos (AL)',
    'summary': 'Importa los extractos que descargan los bancos peruanos (Excel, Excel en HTML, CSV '
               'o TXT) sin mapear columnas: reconoce la tabla por sus encabezados.',
    'description': """
Extractos de bancos peruanos
============================
* El botón **Importar** del diario de banco reconoce el archivo de movimientos que
  descarga la banca por internet: Excel (XLSX o XLS), «Excel» que en realidad es una
  tabla HTML, CSV o TXT con separador.
* Ubica la fila de encabezados aunque arriba haya títulos y datos de la cuenta, y
  reconoce las columnas por su nombre: fecha de operación, descripción o concepto, número
  de operación, monto o cargo y abono, y saldo.
* Importes con «S/», separador de miles, negativos con signo o entre paréntesis; fechas
  dd/mm/aaaa. Ordena los movimientos y calcula los saldos inicial y final.
* Un movimiento ya importado no se duplica al volver a importar el archivo.
* Si el archivo no se reconoce, sigue el importador nativo (mapeo de columnas).
""",
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    'icon': '/account/static/description/icon.png',
    'version': '1.20261021',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['al_account_base', 'account_bank_statement_import_csv'],
    'external_dependencies': {'python': ['openpyxl', 'xlrd']},
    'data': [],
    'installable': True,
    'application': False,
}

{
    'name': 'Recaudación bancaria (AL)',
    'summary': 'Recaudación por ventanilla, agentes y banca por internet: archivo de deudores para el '
               'banco, importación de la respuesta, pagos y conciliación automática. Formato BCP (CREP) '
               'incluido y configurable.',
    'description': """
Recaudación bancaria
====================
El banco cobra a los clientes con su código de depositante (RUC, DNI o código
propio) y devuelve un archivo con lo cobrado:

* **Convenios** de recaudación: banco, cuenta recaudadora, moneda, diario y cómo se
  forma el código del depositante.
* **Archivo de deudores**: las cuotas abiertas del convenio en el formato del banco,
  completo (reemplazo) o de actualización.
* **Respuesta del banco**: importa lo cobrado, identifica cliente y documento, crea
  los pagos y los concilia con las facturas; no procesa dos veces la misma operación.
* **Formatos configurables**: posición, longitud y tipo de cada campo, como datos.
  Incluye el CREP del BCP (validación completa); se ajusta a la ficha técnica que el
  banco entrega al afiliar sin programar.
""",
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    'icon': '/al_l10n_pe_bank_collection/static/description/icon.svg',
    'version': '1.20261022',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['al_l10n_pe_collection'],
    'data': [
        'security/bank_collection_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/bcp_layout_data.xml',
        'views/bank_collection_layout_views.xml',
        'views/bank_collection_agreement_views.xml',
        'views/bank_collection_batch_views.xml',
        'views/bank_collection_response_views.xml',
        'views/res_partner_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}

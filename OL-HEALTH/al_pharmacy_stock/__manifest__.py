# -*- coding: utf-8 -*-
{
    'name': 'Farmacia: buenas prácticas de almacenamiento (AL)',
    'summary': 'Recepción con inspección y registro sanitario vigente, lotes en cuarentena o '
               'bloqueados que no se venden, vencimientos, bonificaciones de compra, control de '
               'temperatura, alertas sanitarias y actas de baja.',
    'description': """
Farmacia: buenas prácticas de almacenamiento
============================================
Entrega E1 del plan (docs/farmacia/PLAN_FARMACIA.md), según el Manual de
Buenas Prácticas de Oficina Farmacéutica (RM 554-2022/MINSA, 7.5.1):

* Recepción: inspección conforme o no conforme, lote, vencimiento y registro
  sanitario vigente obligatorios en los productos farmacéuticos.
* Estado sanitario del lote (disponible, cuarentena, bloqueado, vencido): solo
  los disponibles se reservan; cron diario de vencidos; aviso de lotes por
  vencer con los días de la compañía.
* Bonificaciones de compra (12+1) como línea hermana a precio cero: el costo
  se prorratea solo.
* Control de temperatura y humedad por punto (ambiente, cadena de frío) con
  acción correctiva obligatoria fuera de rango y recordatorio diario.
* Alertas sanitarias: bloqueo de lotes, stock afectado y clientes que los
  recibieron.
* Acta de baja y destrucción con PDF y baja de inventario.

Precio por vencer y canje (mejora E11, docs/farmacia/MEJORAS_PROCESOS.md):

* Escalas de descuento por días al vencimiento, por compañía y opcionalmente
  por categoría (por ejemplo, -20 % hasta 90 días y -40 % hasta 30). La caja
  las aplica al vender el lote (al_pharmacy_pos).
* Lotes por vencer con los días que les quedan, el descuento y el precio
  sugerido.
* Canje o devolución a la droguería: lotes por vencer, vencidos o dañados del
  proveedor (asistente que los carga desde sus recepciones o sus productos),
  estados borrador, enviado, aceptado y hecho; al aceptarlo se prepara la
  salida del stock al proveedor con los lotes y luego se registra su nota de
  crédito en borrador con el costo. Acta de canje en PDF.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-HEALTH/Apps',
    'icon': '/al_pharmacy_base/static/description/icon.png',
    'version': '3.20261019',
    'license': 'OPL-1',
    'depends': ['al_pharmacy_base', 'purchase_stock', 'product_expiry', 'al_report_base'],
    'data': [
        'security/ir.model.access.csv',
        'security/pharmacy_stock_security.xml',
        'data/pharmacy_stock_data.xml',
        'views/stock_views.xml',
        'views/pharmacy_stock_views.xml',
        'report/pharmacy_destruction_report.xml',
        'views/pharmacy_expiry_views.xml',
        'report/pharmacy_supplier_return_report.xml',
    ],
    'demo': ['demo/pharmacy_stock_demo.xml'],
    'installable': True,
    'application': False,
}

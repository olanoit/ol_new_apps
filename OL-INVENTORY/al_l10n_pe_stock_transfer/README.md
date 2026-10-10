# PE - Traslados internos y bienes de terceros (AL)

Módulo `al_l10n_pe_stock_transfer`. Completa la guía de remisión electrónica
remitente de Odoo 19 (`l10n_pe_edi_stock`) con dos casos que el estándar no
cubre: los traslados entre establecimientos de la empresa y los bienes de
terceros.

## Traslados entre establecimientos (motivo 04)

El estándar solo emite la guía en **salidas**. Con este módulo también se emite
en **transferencias internas hechas** cuando el origen y el destino son
establecimientos distintos.

| Dato | De dónde sale |
|---|---|
| Punto de partida | Dirección del almacén de la ubicación de origen (o la de la compañía) |
| Punto de llegada | Dirección del almacén de la ubicación de destino; al emitir se copia en el contacto de la transferencia |
| Establecimiento distinto | Código de establecimiento anexo distinto o, sin código, distinta calle o distrito |
| Motivo | 04 «Traslado entre establecimientos de la misma empresa», propuesto al elegir la modalidad |
| Destinatario | La propia empresa (destinatario = remitente) |
| Código de establecimiento | `cbc:AddressTypeCode` de partida y llegada con el RUC de la empresa y el «Establecimiento anexo» de cada dirección (`al_account_base`); sin código, `0` como el estándar |

Una transferencia dentro del mismo establecimiento (p. ej. de un estante a
otro) no muestra el botón y, si se intenta, da error. Con los demás motivos el
XML queda igual que el estándar.

## Bienes de terceros

Odoo los maneja con el **propietario** (`owner_id`, «Consignación» en Ajustes de
Inventario): están en el almacén y se mueven, pero **no se valorizan** ni generan
asientos, y el kardex de la suite (`ol_stock_kardex_pe`) ya los deja fuera. El
módulo no cambia nada de eso; solo los hace visibles:

- **Transferencia ▸ Logística PE ▸ Bienes de terceros**: propietarios de los
  bienes (el de la transferencia y el de cada línea) y el aviso.
- **Filtros**: «De terceros» y «Propios» en existencias; «De terceros» en
  movimientos; «Con bienes de terceros» en transferencias. El contacto de una
  compañía de la base nunca cuenta como tercero
  (`res.partner.l10n_pe_is_company_partner`).
- **Guía de remisión**: el XML de la GRE no tiene un campo para el propietario
  de los bienes, así que va en las **observaciones** (`cbc:Note`): «Bienes de
  propiedad de …». La representación impresa
  (`al_l10n_pe_delivery_guide_report`) añade el recuadro «Propietario de los
  bienes».

El motivo lo elige el usuario según la operación: 04 entre establecimientos
propios, 05 consignación, 13 otros (p. ej. devolución de un equipo alquilado a
su dueño). El módulo no añade motivos al catálogo del estándar.

## Pruebas

`tests/test_stock_transfer.py` (sin enviar nada a SUNAT): guía con motivo 04
entre dos almacenes (destinatario, códigos de establecimiento, punto de
partida), ninguna guía dentro del mismo establecimiento, propietario en el XML
y en el PDF, filtros de terceros y salida estándar sin cambios.

## Límites

- Las reglas de validación de SUNAT de la GRE no se pudieron descargar al
  desarrollar (cpe.sunat.gob.pe respondía 403): el XML usa solo los campos que
  ya emite el estándar. Validar el primer envío real con motivo 04 en el
  ambiente de pruebas de SUNAT.
- Los traslados entre almacenes por rutas de reabastecimiento (salida a
  tránsito) son salidas: ya tenían el botón del estándar; el motivo 04 se
  elige a mano en ellas.

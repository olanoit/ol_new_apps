# PE - Traslados internos y bienes de terceros (AL)

Guía funcional: [GUIA_FUNCIONAL.md](GUIA_FUNCIONAL.md)

Módulo `al_l10n_pe_stock_transfer`. Completa la guía de remisión electrónica
remitente de Odoo 19 (`l10n_pe_edi_stock`) para todos los traslados que hace la
empresa: entre sus establecimientos, compras que recoge, devoluciones,
importación y exportación, y el control de los bienes de terceros.

## Motivos de traslado (catálogo 20)

El estándar trae 01, 03, 04, 05, 13, 14, 17 y 18. El módulo añade los que faltan
del catálogo 20 vigente (anexo de la R.S. 240-2024/SUNAT) para la empresa:
**02 Compra, 06 Devolución, 07 Recojo de bienes transformados, 08 Importación y
09 Exportación**. El 19 (traslado de mercancía extranjera) queda fuera: exige
datos del terminal portuario y del almacén aduanero que Odoo no registra.

| Motivo | Dónde se usa | Reglas del módulo |
|---|---|---|
| 04 | Transferencia interna entre establecimientos distintos | Destinatario = la empresa; partida y llegada con su código anexo |
| 02, 07, 08 | Recepción que la empresa traslada con su transporte | Parte del proveedor (transformador, puerto), llega al almacén; destinatario = la empresa |
| 06 | Devolución al proveedor o al dueño de bienes de terceros | Se propone solo |
| 08, 09 | Importación / exportación | Exigen la DAM o DS (documento relacionado 50 o 52) y su número |
| 13 | Otros | «Descripción del motivo» obligatoria; va en `cbc:HandlingInstructions` y en la guía impresa |

**Motivo propuesto** al elegir la modalidad de transporte: el del tipo de
operación (campo «Motivo de traslado (guía)»); si no tiene, 04 en internas, 06
en devoluciones y al dueño de bienes de terceros, 02 en recepciones y el 01
del estándar en las demás salidas. Reemplaza el 01 que el estándar pone al
crear la transferencia; el usuario puede cambiarlo.

## Establecimientos

| Dato | De dónde sale |
|---|---|
| Punto de partida | Almacén de la ubicación de origen; en un ingreso, el proveedor |
| Punto de llegada | Almacén de destino (interna o ingreso) o el contacto de la entrega |
| Establecimiento distinto | Código de establecimiento anexo distinto o, sin código, distinta calle o distrito |
| `cbc:AddressTypeCode` | Dirección propia: RUC de la empresa y su «Establecimiento anexo» (`al_account_base`), `0` sin código; dirección de un tercero con RUC: su RUC y `0`, como el estándar |

Una transferencia dentro del mismo establecimiento no lleva guía. Una recepción
solo lleva guía de la empresa con los motivos 02, 07 u 08: si el proveedor trae
los bienes, la guía la emite él.

La guía impresa (`al_l10n_pe_delivery_guide_report`) usa el mismo destinatario,
punto de llegada y motivo que el XML, y el motivo en el idioma de la compañía.

## Bienes de terceros

Odoo los maneja con el **propietario** (`owner_id`, «Consignación» en Ajustes de
Inventario): están en el almacén y se mueven, pero **no se valorizan** ni generan
asientos, y el kardex de la suite (`ol_stock_kardex_pe`) los deja fuera de las
cantidades valorizadas. El módulo los hace visibles:

- **Transferencia ▸ Logística PE ▸ Bienes de terceros**: propietarios de los
  bienes (el de la transferencia y el de cada línea) y el aviso.
- **Filtros**: «De terceros» y «Propios» en existencias; «De terceros» en
  movimientos; «Con bienes de terceros» en transferencias. El contacto de una
  compañía de la base nunca cuenta como tercero
  (`res.partner.l10n_pe_is_company_partner`).
- **Guía de remisión**: el XML de la GRE no tiene un campo para el propietario,
  así que va en las **observaciones** (`cbc:Note`): «Bienes de propiedad de …».
  La guía impresa añade el recuadro «Propietario de los bienes».

## Datos de demostración

`tools/stock_transfer_demo_data.py` (con `odoo shell`, prefijo «DEMO TRAS»):
dos almacenes con códigos anexos 0001 y 0002, andamios propios y alquilados,
traslados internos (04), una compra recogida (02) y la devolución al dueño (06).
No envía nada a SUNAT. Capturas: `docs/fichas/capturas/al_l10n_pe_stock_transfer.py`.

## Pruebas

`tests/test_stock_transfer.py` (sin enviar nada a SUNAT): guía con motivo 04
entre dos almacenes, ninguna guía dentro del mismo establecimiento, propietario
en el XML y en el PDF, filtros de terceros, salida con el establecimiento anexo,
catálogo 20, compra recogida (XML y PDF), recepción sin motivo de ingreso,
devolución al dueño (06), motivo del tipo de operación, 13 con descripción e
importación con DAM.

## Límites

- Las reglas de validación de la GRE de SUNAT no se pudieron descargar
  (cpe.sunat.gob.pe responde 403 a clientes automáticos). Validar el primer
  envío real de cada motivo nuevo (02, 04, 06, 07, 08, 09) en el ambiente de
  pruebas de SUNAT.
- Motivo 19 (mercancía extranjera) fuera del alcance.
- Los traslados entre almacenes por rutas de reabastecimiento (salida a
  tránsito) son salidas: ya tenían el botón del estándar; el motivo 04 se
  elige a mano en ellas.
- La traducción al español del motivo 04 del estándar dice «Translados»
  (errata de `l10n_pe_edi_stock`).

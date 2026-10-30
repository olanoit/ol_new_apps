# Anexo · Casos validados en Odoo 20

Generado por `generar_anexo.py` desde `resultados/*.json`. Cada caso es una
ejecución real sobre `ce20_db_ol`; los registros listados quedaron en la base
(nombres con prefijo `QA20`).

| Bloque | Módulos | Casos | Resultado |
|---|---:|---:|---|
| Fase 0 · Cliente web en navegador | 14 | 21 | ✅ 21 · 21 comprobaciones |
| Fase 1A · Contabilidad: base, impuestos y reportes | 16 | 33 | ⚠️ 3 · ✅ 30 · 236 comprobaciones |
| Fase 1B · Contabilidad: cobros, pagos, bancos y cierre | 31 | 48 | ⚠️ 1 · ✅ 47 · 472 comprobaciones |
| Fases 2 y 3 · Facturación electrónica y TPV | 19 | 31 | ⚠️ 3 · ❌ 1 · ✅ 27 · 267 comprobaciones |
| Fases 4 y 7 · Inventario, farmacia e industrias | 26 | 38 | ⚠️ 2 · ❌ 1 · ✅ 35 · 313 comprobaciones |
| Fase 5 · Proyectos y construcción | 28 | 34 | ✅ 34 · 181 comprobaciones |
| Fases 6 y 8 · Planillas y herramientas | 16 | 27 | ⚠️ 7 · ❌ 2 · ✅ 18 · 286 comprobaciones |

## Fase 0 · Cliente web en navegador


### `web (sonda)`

#### ✅ El detector capta excepciones no controladas

**Pasos en pantalla:** Lanzar un error a propósito en la consola

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | La excepción aparece en la consola y en el diálogo «¡Vaya!» | sonda 12:13:49 |


### `al_construction_planner`

#### ✅ Pantalla: Inicio del planificador (action-540)

**Pasos en pantalla:** Abrir la pantalla con qa20_admin, esperar 5 s y revisar la consola y los diálogos

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Carga sin excepciones en consola ni diálogo de error | Chrome, recarga completa |

#### ✅ Pantalla: Árbol de recursos (action-544)

**Pasos en pantalla:** Abrir la pantalla con qa20_admin, esperar 5 s y revisar la consola y los diálogos

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Carga sin excepciones en consola ni diálogo de error | Chrome, recarga completa |

#### ✅ Pantalla: Cronograma de obra (action-545)

**Pasos en pantalla:** Abrir la pantalla con qa20_admin, esperar 5 s y revisar la consola y los diálogos

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Carga sin excepciones en consola ni diálogo de error | Chrome, recarga completa |


### `al_construction_planner_purchase`

#### ✅ Pantalla: Tablero de abastecimiento (action-1028)

**Pasos en pantalla:** Abrir la pantalla con qa20_admin, esperar 5 s y revisar la consola y los diálogos

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Carga sin excepciones en consola ni diálogo de error | Chrome, recarga completa |


### `al_construction_planner_sale`

#### ✅ Pantalla: Reporte de programación (action-1215)

**Pasos en pantalla:** Abrir la pantalla con qa20_admin, esperar 5 s y revisar la consola y los diálogos

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Carga sin excepciones en consola ni diálogo de error | Chrome, recarga completa |


### `al_l10n_pe_collection`

#### ✅ Pantalla: Tablero de cobranza (action-1483)

**Pasos en pantalla:** Abrir la pantalla con qa20_admin, esperar 5 s y revisar la consola y los diálogos

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Carga sin excepciones en consola ni diálogo de error | Chrome, recarga completa |


### `al_l10n_pe_dashboard`

#### ✅ Pantalla: Tablero Perú (action-1547)

**Pasos en pantalla:** Abrir la pantalla con qa20_admin, esperar 5 s y revisar la consola y los diálogos

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Carga sin excepciones en consola ni diálogo de error | Chrome, recarga completa |


### `al_l10n_pe_financial_reports`

#### ✅ Pantalla: 3.19 Cambios en el patrimonio (action-1586)

**Pasos en pantalla:** Abrir la pantalla con qa20_admin, esperar 5 s y revisar la consola y los diálogos

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Carga sin excepciones en consola ni diálogo de error | Chrome, recarga completa |

#### ✅ Pantalla: Hoja de trabajo formato 1 (action-1587)

**Pasos en pantalla:** Abrir la pantalla con qa20_admin, esperar 5 s y revisar la consola y los diálogos

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Carga sin excepciones en consola ni diálogo de error | Chrome, recarga completa |

#### ✅ Pantalla: Hoja de trabajo formato 2 (action-1588)

**Pasos en pantalla:** Abrir la pantalla con qa20_admin, esperar 5 s y revisar la consola y los diálogos

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Carga sin excepciones en consola ni diálogo de error | Chrome, recarga completa |


### `al_l10n_pe_ple`

#### ✅ Pantalla: PLE 7.1 activos fijos (action-1634)

**Pasos en pantalla:** Abrir la pantalla con qa20_admin, esperar 5 s y revisar la consola y los diálogos

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Carga sin excepciones en consola ni diálogo de error | Chrome, recarga completa |

#### ✅ Pantalla: PLE 8.1 compras (action-1631)

**Pasos en pantalla:** Abrir la pantalla con qa20_admin, esperar 5 s y revisar la consola y los diálogos

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Carga sin excepciones en consola ni diálogo de error | Chrome, recarga completa |

#### ✅ Pantalla: PLE 8.2 no domiciliados (action-1632)

**Pasos en pantalla:** Abrir la pantalla con qa20_admin, esperar 5 s y revisar la consola y los diálogos

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Carga sin excepciones en consola ni diálogo de error | Chrome, recarga completa |

#### ✅ Pantalla: PLE 14.1 ventas (action-1630)

**Pasos en pantalla:** Abrir la pantalla con qa20_admin, esperar 5 s y revisar la consola y los diálogos

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Carga sin excepciones en consola ni diálogo de error | Chrome, recarga completa |


### `al_project_gantt_backend`

#### ✅ Pantalla: Gantt de proyectos (action-513)

**Pasos en pantalla:** Abrir la pantalla con qa20_admin, esperar 5 s y revisar la consola y los diálogos

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Carga sin excepciones en consola ni diálogo de error | Chrome, recarga completa |


### `al_l10n_pe_invoice`

#### ✅ Pantalla: Lista de facturas de cliente

**Pasos en pantalla:** Abrir la pantalla con qa20_admin, esperar 5 s y revisar la consola y los diálogos

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Carga sin excepciones en consola ni diálogo de error | Chrome, recarga completa |


### `queue_job`

#### ✅ Pantalla: Trabajos en cola

**Pasos en pantalla:** Abrir la pantalla con qa20_admin, esperar 5 s y revisar la consola y los diálogos

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Carga sin excepciones en consola ni diálogo de error | Chrome, recarga completa |


### `al_pos_theme`

#### ✅ Pantalla: Tablero de puntos de venta

**Pasos en pantalla:** Abrir la pantalla con qa20_admin, esperar 5 s y revisar la consola y los diálogos

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Carga sin excepciones en consola ni diálogo de error | Chrome, recarga completa |


### `al_account_payments`

#### ✅ Pantalla: Pagos a proveedores

**Pasos en pantalla:** Abrir la pantalla con qa20_admin, esperar 5 s y revisar la consola y los diálogos

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Carga sin excepciones en consola ni diálogo de error | Chrome, recarga completa |


### `purchase_request`

#### ✅ Pantalla: Solicitudes de compra

**Pasos en pantalla:** Abrir la pantalla con qa20_admin, esperar 5 s y revisar la consola y los diálogos

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Carga sin excepciones en consola ni diálogo de error | Chrome, recarga completa |


## Fase 1A · Contabilidad: base, impuestos y reportes


### `al_account_base`

#### ⚠️ Código SUNAT del banco = clearing_number nativo (ambos sentidos)

**Pasos en pantalla:** Contactos ▸ cuenta bancaria: elegir el banco del catálogo y escribir el código SUNAT; luego cambiar el «clearing number» y ver que el código SUNAT lo sigue.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | nombre del banco tomado del catálogo | esperado 'Banco de Crédito del Perú', obtenido 'Banco de Crédito del Perú' |
| ✅ | BIC tomado del catálogo | esperado 'BCPLPEPL', obtenido 'BCPLPEPL' |
| ✅ | l10n_pe_bank_code → clearing_number | esperado '02', obtenido '02' |
| ✅ | clearing_number → l10n_pe_bank_code | esperado '11', obtenido '11' |
| ✅ | código de 3 dígitos rechazado (sin truncar a otro banco) |  |
| ⚠️ | El clearing_number nativo acepta un código SUNAT inválido | escribir clearing_number=«AB» no dispara _check_l10n_pe_bank_code (la restricción es sobre el related l10n_pe_bank_code); el PLE 1.2 lo leería tal cual |
| ✅ | cuenta del Banco de la Nación: código SUNAT 18 | esperado '18', obtenido '18' |
| ✅ | se reconoce como Banco de la Nación (BANCPEPL) |  |

**Registros:** `res.partner.bank/139` 19316000010001 - Banco de Crédito del Perú, `res.partner.bank/140` 0007131600002 - Banco de la Nación

#### ✅ Glosa del asiento y de la línea, anexo y naturaleza del diario

**Pasos en pantalla:** Contabilidad ▸ Asientos ▸ Nuevo: escribir la glosa, publicar y duplicar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | asiento publicado | esperado 'posted', obtenido 'posted' |
| ✅ | glosa conservada al publicar | esperado 'QA20 Provisión de servicios de octubre', obtenido 'QA20 Provisión de servicios de octubre' |
| ✅ | glosa de la línea | esperado 'Glosa de la línea', obtenido 'Glosa de la línea' |
| ✅ | la glosa es buscable |  |
| ✅ | duplicar no arrastra la glosa |  |
| ✅ | l10n_pe_is_pe() en compañía peruana |  |
| ✅ | código de anexo de 4 dígitos aceptado | esperado '0001', obtenido '0001' |
| ✅ | código de anexo con letras rechazado |  |
| ✅ | naturaleza del diario por defecto: movimiento | esperado 'movement', obtenido 'movement' |
| ✅ | diario de apertura excluido de libros |  |

**Registros:** `account.move/28811` Borrador de asiento, `account.journal/5891` QA20 Apertura


### `l10n_pe_vat_sunat`

#### ✅ Consulta de RUC (simulada) actualiza el contacto

**Pasos en pantalla:** Contactos ▸ nuevo contacto con RUC ▸ botón «Actualizar RUC/DNI».

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | el RUC es el vat del contacto peruano | ('ruc', '20609920107') |
| ✅ | se consultó el RUC | call('20609920107', 'ruc', quick=False) |
| ✅ | razón social actualizada | esperado 'QA20 EMPRESA CONSULTADA S.A.C.', obtenido 'QA20 EMPRESA CONSULTADA S.A.C.' |
| ✅ | dirección actualizada | esperado 'AV. QA 123', obtenido 'AV. QA 123' |
| ✅ | distrito (ubigeo) actualizado | esperado l10n_pe.res.city.district(251,), obtenido l10n_pe.res.city.district(251,) |
| ✅ | sin alerta de consulta |  |
| ✅ | RUC con dígito verificador inválido no se consulta |  |
| ⏭️ | Consulta real a SUNAT/APIs | sin credenciales de prueba: conexión simulada |

**Registros:** `res.partner/9095` QA20 Empresa por consultar

#### ✅ DNI en identificadores adicionales (Odoo 20) y consulta simulada

**Pasos en pantalla:** Contactos ▸ persona con DNI en «Identificadores adicionales» ▸ «Actualizar RUC/DNI».

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | DNI guardado en additional_identifiers | esperado '45678912', obtenido '45678912' |
| ✅ | objetivo de la consulta: DNI | esperado ('dni', '45678912'), obtenido ('dni', '45678912') |
| ✅ | tipo consultable con la validación de DNI activa | esperado 'dni', obtenido 'dni' |
| ✅ | se consultó el DNI | call('45678912', 'dni', quick=False) |
| ✅ | nombre actualizado desde la consulta de DNI | esperado 'QA20 PEREZ GOMEZ JUAN', obtenido 'QA20 PEREZ GOMEZ JUAN' |
| ✅ | DNI de 4 dígitos rechazado al consultar |  |

**Registros:** `res.partner/9096` QA20 Persona con DNI


### `al_l10n_pe_currency`

#### ✅ Tipo de cambio compra/venta manual

**Pasos en pantalla:** Contabilidad ▸ Configuración ▸ Monedas ▸ USD ▸ nueva tasa con compra 3.360 y venta 3.370.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | tasa nativa = 1/venta | esperado 0.29673590504451036, obtenido 0.29673590504451036 |
| ✅ | compra conservada | esperado 3.36, obtenido 3.36 |
| ✅ | tocar la tasa nativa recalcula la venta | esperado 4.0, obtenido 4.0 |
| ✅ | y la venta vuelve a fijar la nativa | esperado 0.29673590504451036, obtenido 0.29673590504451036 |
| ✅ | tipo de cambio negativo rechazado |  |

**Registros:** `res.currency.rate/881` 2026-02-02

#### ✅ Descarga BCRP simulada: el cierre de un día es el TC SUNAT del siguiente (fin de semana)

**Pasos en pantalla:** Monedas ▸ «Actualizar tipo de cambio» (BCRP) para 05/02–10/02/2026.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | se llamó a la descarga (simulada) | call(datetime.date(2026, 1, 26), datetime.date(2026, 2, 9)) |
| ✅ | fechas cargadas 05..10/02 | esperado 6, obtenido 6 |
| ✅ | TC SUNAT 05/02 = cierre anterior | 3.351/3.358 esperado 3.351/3.358 |
| ✅ | TC SUNAT 06/02 = cierre anterior | 3.362/3.369 esperado 3.362/3.369 |
| ✅ | TC SUNAT 07/02 = cierre anterior (fin de semana) | 3.371/3.377 esperado 3.371/3.377 |
| ✅ | TC SUNAT 08/02 = cierre anterior (fin de semana) | 3.371/3.377 esperado 3.371/3.377 |
| ✅ | TC SUNAT 09/02 = cierre anterior | 3.371/3.377 esperado 3.371/3.377 |
| ✅ | TC SUNAT 10/02 = cierre anterior | 3.38/3.386 esperado 3.38/3.386 |
| ✅ | recargar no duplica | esperado 1, obtenido 1 |
| ⏭️ | Descarga real del BCRP/SUNAT | sin red: respuesta simulada |

**Registros:** `res.currency.rate/882` 2026-02-05, `res.currency.rate/883` 2026-02-06, `res.currency.rate/884` 2026-02-07, `res.currency.rate/885` 2026-02-08, `res.currency.rate/886` 2026-02-09, `res.currency.rate/887` 2026-02-10

#### ✅ Factura en USD con TC compra vs venta

**Pasos en pantalla:** Ventas ▸ factura en dólares del 09/02/2026 ▸ campo «Tipo de cambio»: compra o venta.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | por defecto se usa la venta | esperado 'sale', obtenido 'sale' |
| ✅ | tasa = 1/venta del 09/02 | esperado 0.29612081729345574, obtenido 0.29612081729345574 |
| ✅ | total en soles con venta | esperado 337.7, obtenido 337.7 |
| ✅ | tasa = 1/compra del 09/02 | esperado 0.29664787896766537, obtenido 0.29664787896766537 |
| ✅ | total en soles con compra | esperado 337.1, obtenido 337.1 |

**Registros:** `account.move/28813` FQ20-31600003, `account.move/28814` Borrador de factura FQ20-31600004


### `al_account_move_name_sequence`

#### ✅ Numeración por secuencia del diario

**Pasos en pantalla:** Contabilidad ▸ Diarios ▸ marcar «Usar secuencia» con prefijos QSV-/QSN- y publicar facturas.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | secuencia de facturas creada con el prefijo | esperado 'QSV-', obtenido 'QSV-' |
| ✅ | secuencia de NC creada con el prefijo | esperado 'QSN-', obtenido 'QSN-' |
| ✅ | secuencia sin huecos | esperado 'no_gap', obtenido 'no_gap' |
| ✅ | nombre tomado de la secuencia | QSV-00000001, QSV-00000002 |
| ✅ | numeración correlativa |  |
| ✅ | NC con la secuencia rectificativa | QSN-00000001 |

**Registros:** `account.journal/5892` QA20 Ventas por secuencia, `account.move/28815` QSV-00000001, `account.move/28816` QSV-00000002, `account.move/28817` Borrador de nota de crédito

#### ✅ Serie CPE: publicar crea las 3 secuencias; factura y NC

**Pasos en pantalla:** Contabilidad ▸ Series CPE ▸ nueva serie FQ21 ▸ Publicar; asignarla a un diario y facturar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | serie publicada | esperado 'publish', obtenido 'publish' |
| ✅ | secuencias de factura, NC y ND | esperado ('FQ21-', 'FQ2C-', 'FQ2D-'), obtenido ('FQ21-', 'FQ2C-', 'FQ2D-') |
| ✅ | serie «B001» rechazada para facturas |  |
| ✅ | serie asignada a la factura | esperado edi.invoice.series(21,), obtenido edi.invoice.series(21,) |
| ✅ | numerada con la serie | FQ21-00000001 |
| ✅ | NC numerada con la serie rectificativa | FQ2C-00000001 |

**Registros:** `edi.invoice.series/21` FQ21, `account.journal/5893` QA20 Ventas serie CPE, `account.move/28818` FQ21-00000001, `account.move/28819` FQ2C-00000001 (Reversión de: FQ21-00000001, QA20 anulación [


### `al_account_destinations`

#### ✅ Gasto clase 6 → asiento de destino 9 / 79

**Pasos en pantalla:** Plan contable ▸ cuenta 63 con destinos 94 (60 %) y 95 (40 %) y cuenta 79; publicar un gasto.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | compañía con destinos 6 → 9 | esperado '6a9', obtenido '6a9' |
| ✅ | destinos que no suman 100 % rechazados |  |
| ✅ | la cuenta 6 trabaja con destinos |  |
| ✅ | destino generado y publicado |  |
| ✅ | en el diario de destinos de Ajustes | esperado account.journal(5888,), obtenido account.journal(5888,) |
| ✅ | 94: 60 % al debe | esperado 600.0, obtenido 600.0 |
| ✅ | 95: 40 % al debe | esperado 400.0, obtenido 400.0 |
| ✅ | 79: 100 % al haber | esperado 1000.0, obtenido 1000.0 |
| ✅ | el destino no genera otro destino |  |
| ✅ | factura: 94 = 300 | esperado 300.0, obtenido 300.0 |
| ✅ | factura: 79 = 500 (sin IGV) | esperado 500.0, obtenido 500.0 |

**Registros:** `account.move/28821` Borrador de asiento, `account.move/28822` QAD20/2026/10/0001 (Destino: QAG20/2026/10/0002), `account.move/28823` F FQ20-31600008, `account.move/28824` QAD20/2026/10/0002 (Destino: F FQ20-31600008)


### `al_l10n_pe_detraction`

#### ✅ Factura de venta con detracción y reparto de la cuenta 12

**Pasos en pantalla:** Ventas ▸ factura de servicio SPOT 12 % por S/ 1 180 ▸ Publicar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | el producto sincroniza el código y % nativos del catálogo 54 | esperado ('037', 12.0), obtenido ('037', 12.0) |
| ✅ | aplica detracción (> S/ 700) |  |
| ✅ | detracción 12 % de 1 180 redondeada a 142 | esperado 142.0, obtenido 142.0 |
| ✅ | neto a cobrar 1 038 | esperado 1038.0, obtenido 1038.0 |
| ✅ | tipo de operación 1001 (sujeta a detracción) | esperado '1001', obtenido '1001' |
| ✅ | dos líneas de cobro (neto + detracción) | esperado 2, obtenido 2 |
| ✅ | detracción a la 12 propia | esperado 142.0, obtenido 142.0 |
| ✅ | el XML UBL lleva el bloque de detracción | Detraccion/142.00 |

**Registros:** `account.move/28825` FQ20-31600009

#### ✅ Depósito de la detracción de una compra

**Pasos en pantalla:** Compras ▸ factura SPOT ▸ «Depositar detracción» con número de constancia.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | detracción 12 % de 2 360 = 283 | esperado 283.0, obtenido 283.0 |
| ✅ | el asistente propone el importe de la detracción | esperado 283.0, obtenido 283.0 |
| ✅ | constancia registrada en la factura | esperado 'QA31600011', obtenido 'QA31600011' |
| ✅ | pago de 283 vinculado | [{'id': 1275, 'amount': 283.0, 'state': 'paid'}] |
| ✅ | solo se paga la detracción: queda el neto 2 077 | esperado 2077.0, obtenido 2077.0 |

**Registros:** `account.move/28826` F FQ20-31600010, `account.payment/1275` PQAB20/2026/00001

#### ✅ TXT de depósito masivo del Banco de la Nación

**Pasos en pantalla:** Perú ▸ Detracciones ▸ «Generar TXT BN» (adquirente) para setiembre 2026.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | estructura válida para el banco | esperado [], obtenido [] |
| ✅ | cabecera de 68 posiciones | esperado 68, obtenido 68 |
| ✅ | cabecera de adquirente | esperado '*', obtenido '*' |
| ✅ | detalle del proveedor de 107 posiciones | ['620609920034                                            037000712345670000000000708000120260901FQ2031600012'] |
| ✅ | importe de la detracción en el detalle | 708.0 |
| ⏭️ | Envío del TXT al Banco de la Nación | sin credenciales bancarias |

**Registros:** `account.move/28828` F FQ20-31600012, `l10n_pe.detraction.txt.wizard/40` l10n_pe.detraction.txt.wizard,40


### `al_l10n_pe_retention`

#### ⚠️ Pago con retención 3 %: CRE numerado y XML generado sin enviar

**Pasos en pantalla:** Compras ▸ factura de S/ 1 180 ▸ Registrar pago ▸ retención 3 % ▸ «Generar XML del CRE».

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | impuesto de retención = el nativo de l10n_pe_edi_withholding | 3% IGV Withholding |
| ✅ | aplica retención |  |
| ✅ | estimación 3 % de 1 180 | esperado 35.4, obtenido 35.4 |
| ✅ | impuesto de retención inyectado al publicar |  |
| ✅ | sin alterar el total | esperado 1180.0, obtenido 1180.0 |
| ✅ | línea de retención del asistente | esperado 35.4, obtenido 35.4 |
| ✅ | retención en el pago | esperado 35.4, obtenido 35.4 |
| ✅ | CRE numerado con serie R___ | RRR1-00000010 |
| ⚠️ | La serie del CRE no es R001 | número RRR1-00000010: la secuencia nativa (account.1_l10n_pe_edi_withholding_sunat_sequence) conserva el prefijo «RRR1-»; el R001- del módulo solo se aplica al cargar el plan en compañías nuevas |
| ✅ | factura pagada (neto + retención) | esperado True, obtenido True |
| ✅ | XML: RUC del agente | 20557912879 |
| ✅ | XML: RUC del proveedor | 20609920026 |
| ✅ | XML: número del CRE | RRR1-00000010 |
| ✅ | XML: tasa 3 % | <sac:SUNATRetentionPercent>3 |
| ✅ | XML: importe retenido | 35.40 |
| ✅ | XML: factura referenciada | FQ20-31600013 |
| ✅ | raíz del UBL: Retention | esperado 'Retention', obtenido 'Retention' |
| ⏭️ | Envío del CRE a SUNAT/OSE | sin credenciales de prueba |
| ✅ | PDT 626: fila del proveedor con 35.40 | [['20609920026', 'QA20 Proveedor Servicios SAC', 'F FQ20-31600013', '2026-10-30', '1180.00', 'RRR1-00000010', '35.40']] |

**Registros:** `account.move/28829` Borrador de factura F FQ20-31600013, `account.payment/1276` PQAB20/2026/00002, `ir.attachment/68601` 20557912879-20-RRR1-00000010.xml, `l10n_pe.retention.summary.wizard/45` l10n_pe.retention.summary.wizard,45

#### ✅ Anulación del CRE (resumen RR): reversing → cancelled (servicio simulado)

**Pasos en pantalla:** Pagos ▸ CRE aceptado ▸ «Revertir retención» con motivo ▸ «Consultar reversión».

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | retención 3 % de 2 360 | esperado 70.8, obtenido 70.8 |
| ✅ | un CRE aceptado bloquea pasar el pago a borrador |  |
| ✅ | tras enviar el resumen: reversing | esperado 'reversing', obtenido 'reversing' |
| ✅ | tras consultar el ticket: cancelled | esperado 'cancelled', obtenido 'cancelled' |
| ✅ | nombre del resumen RR | 20557912879-RR-20261030-67 |
| ✅ | XML de reversión: SummaryDocuments | esperado 'SummaryDocuments', obtenido 'SummaryDocuments' |
| ✅ | el resumen referencia el CRE anulado (serie y número) | RRR1-00000011 |
| ✅ | al volver a publicar recibe un número nuevo | RRR1-00000012 |
| ⏭️ | Envío real del resumen RR a SUNAT | sin credenciales de prueba |

**Registros:** `account.move/28831` F FQ20-31600014, `account.payment/1277` PQAB20/2026/00003

#### ✅ Excepciones: monto mínimo y buen contribuyente

**Pasos en pantalla:** Compras ▸ facturas por S/ 590 y de un buen contribuyente: no muestran retención.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | no aplica por debajo de S/ 700 |  |
| ✅ | no aplica a buen contribuyente |  |
| ✅ | no aplica si la compañía no es agente |  |

**Registros:** `account.move/28833` Borrador de factura F FQ20-31600015, `account.move/28834` Borrador de factura F FQ20-31600016


### `al_l10n_pe_perception`

#### ✅ Factura con percepción 2 % y XML de la factura

**Pasos en pantalla:** Ventas ▸ factura de 10 bolsas de cemento ▸ Publicar: percepción 51 al 2 %.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | régimen 51 (venta interna) | esperado '51', obtenido '51' |
| ✅ | tasa 2 % | esperado 2.0, obtenido 2.0 |
| ✅ | percepción 2 % de 1 180 | esperado 23.6, obtenido 23.6 |
| ✅ | operación 2001 (sujeta a percepción) | esperado '2001', obtenido '2001' |
| ✅ | XML: cargo 51 de 23.60 sobre 1 180.00 |  |
| ✅ | XML: total con percepción 1 203.60 |  |

**Registros:** `account.move/28836` FQ20-31600018

#### ✅ Comprobante de percepción (tipo 40) desde el cobro

**Pasos en pantalla:** Ventas ▸ cobrar 1 203.60 ▸ en el pago «Crear comprobante de percepción» ▸ Publicar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | percepción calculada con el factor (1 203.60) | esperado 23.6, obtenido 23.6 |
| ✅ | comprobante publicado | esperado 'posted', obtenido 'posted' |
| ✅ | número P___ | P001-00000001 |
| ✅ | asiento: percepción por pagar al haber | esperado 23.6, obtenido 23.6 |
| ✅ | la factura registra la percepción cobrada | esperado 23.6, obtenido 23.6 |
| ✅ | XML: raíz Perception | esperado 'Perception', obtenido 'Perception' |
| ✅ | XML: total percibido | esperado '23.60', obtenido '23.60' |
| ✅ | XML: total cobrado | esperado '1203.60', obtenido '1203.60' |
| ✅ | nombre del archivo tipo 40 | 20557912879-40-P001-00000001 |
| ⏭️ | Envío del comprobante de percepción a SUNAT | sin credenciales de prueba |

**Registros:** `account.move/28837` FQ20-31600019, `account.payment/1278` PQAB20/2026/00004, `l10n_pe.perception/44` Borrador


### `al_l10n_pe_fourth_category`

#### ✅ Recibos por honorarios: retención 8 % sobre S/ 1 500

**Pasos en pantalla:** Compras ▸ recibo por honorarios E001 de S/ 2 000 y otro de S/ 1 200 ▸ Publicar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | estado: retenido | esperado 'withheld', obtenido 'withheld' |
| ✅ | retención 8 % = 160 | esperado 160.0, obtenido 160.0 |
| ✅ | se paga el neto 1 840 | esperado 1840.0, obtenido 1840.0 |
| ✅ | retención a la 40172 | 4017200 |
| ✅ | S/ 1 200: no se retiene | esperado 'under_threshold', obtenido 'under_threshold' |

**Registros:** `account.move/28840` R E001-31600020, `account.move/28841` R E001-31600021

#### ✅ Reporte mensual (PDT 601) y TXT .4ta

**Pasos en pantalla:** Perú ▸ Cuarta categoría ▸ reporte de octubre 2026 ▸ Calcular ▸ Exportar TXT.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | los dos recibos pagados en el reporte | esperado 2, obtenido 2 |
| ✅ | retenido del prestador: 160 | esperado 160.0, obtenido 160.0 |
| ✅ | nombre del archivo PDT 601 | esperado '060120261020557912879.4ta', obtenido '060120261020557912879.4ta' |
| ✅ | fila del recibo: tipo 06, RUC, R, E001, 2000.00 | [['06', '10473920013', 'R', 'E001', '31600020', '2000.00', '15/10/2026', '15/10/2026', '1', '3', '', '']] |
| ✅ | indicador de retención = 1 | 1 |

**Registros:** `l10n_pe.fourth.category.report/8` l10n_pe.fourth.category.report,8


### `al_l10n_pe_itf`

#### ✅ ITF al confirmar pagos y cobros en un banco afecto

**Pasos en pantalla:** Contabilidad ▸ Pagos ▸ pago de S/ 2 000 y cobro de S/ 5 000 desde el banco con ITF ▸ Confirmar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | redondeo del art. 13 (12 345.67 → 0.60) | esperado 0.6, obtenido 0.6 |
| ✅ | ITF 0.005 % de 2 000 = 0.10 | esperado 0.1, obtenido 0.1 |
| ✅ | asiento del ITF publicado en el banco |  |
| ✅ | gasto ITF en la 6412000 | esperado 0.1, obtenido 0.1 |
| ✅ | cobro de 5 000: ITF 0.25 | esperado 0.25, obtenido 0.25 |
| ✅ | pago marcado exonerado: sin ITF |  |
| ✅ | menos de S/ 1 000: sin ITF |  |
| ✅ | al pasar el pago a borrador se anula el ITF | esperado 'cancel', obtenido 'cancel' |
| ✅ | al republicar vuelve el ITF |  |

**Registros:** `account.payment/1281` PQAI20/2026/00001, `account.move/28846` QAI20/2026/00001 (ITF PQAI20/2026/00001), `account.payment/1282` PQAI20/2026/00002, `account.payment/1283` PQAI20/2026/00003, `account.payment/1284` PQAI20/2026/00004


### `al_l10n_pe_monthly_tax`

#### ✅ UIT desde el parámetro de reglas nativo l10n_pe_uit

**Pasos en pantalla:** Ajustes ▸ Perú ▸ UIT: con la planilla instalada se usa el parámetro del año.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | parámetro l10n_pe_uit con valores | {2026: 5500.0, 2025: 5350.0, 2024: 5150.0} |
| ✅ | UIT 2024 = parámetro nativo | esperado 5150.0, obtenido 5150.0 |
| ✅ | UIT 2025 = parámetro nativo | esperado 5350.0, obtenido 5350.0 |
| ✅ | UIT 2026 = parámetro nativo | esperado 5500.0, obtenido 5500.0 |
| ✅ | para 2025 no usa el valor fijo de la compañía (5500.0) |  |

#### ✅ Resumen 621 de setiembre: IGV y pago a cuenta (variación por mis comprobantes)

**Pasos en pantalla:** Perú ▸ Declaraciones ▸ 621 setiembre 2026 ▸ Calcular; registrar facturas y recalcular.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | periodo calculado | esperado 'calculated', obtenido 'calculated' |
| ✅ | base de ventas +10 000 | esperado 10000.0, obtenido 10000.0 |
| ✅ | IGV de ventas +1 800 | esperado 1800.0, obtenido 1800.0 |
| ✅ | IGV de compras +720 | esperado 720.0, obtenido 720.0 |
| ✅ | resultado del IGV +1 080 | esperado 1080.0, obtenido 1080.0 |
| ✅ | ingresos netos +10 000 | esperado 10000.0, obtenido 10000.0 |
| ✅ | pago a cuenta = max(coeficiente, 1.5 %) × ingresos | coef 0.0, ingresos 10000.0, renta 150.0 |
| ✅ | total = IGV + renta | esperado 330.0, obtenido 330.0 |

**Registros:** `l10n_pe.tax.regime/7` l10n_pe.tax.regime,7, `l10n_pe.monthly.tax/34` 621 09/2026, `account.move/28852` FQ20-31600022, `account.move/28853` F FQ20-31600023


### `al_l10n_pe_ple`

#### ⚠️ PLE 5.1 Libro Diario (TXT oficial + XLSX del módulo)

**Pasos en pantalla:** Contabilidad ▸ Libro mayor ▸ setiembre 2026 ▸ botones «PLE 5.1» y «XLSX 5.1».

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | nombre del TXT 5.1 | LE2055791287920260900050100001111 |
| ✅ | dos líneas del asiento (CUO = id) | esperado 2, obtenido 2 |
| ✅ | 21 campos por línea (cierra con «\|») | esperado 21, obtenido 21 |
| ✅ | periodo AAAAMM00 | esperado '20260900', obtenido '20260900' |
| ✅ | cuentas del asiento | ['6599920', '4699920'] |
| ✅ | debe y haber 321.00 |  |
| ⚠️ | La glosa peruana (l10n_pe_gloss) no llega al 5.1 oficial | campo 16 = 'QAG20/2026/09/0001': el exportador nativo usa el nombre del asiento |
| ✅ | XLSX 5.1 con las mismas líneas del TXT |  |

**Registros:** `account.move/28854` QAG20/2026/09/0001

#### ✅ PLE 6.1 Libro Mayor

**Pasos en pantalla:** Libro mayor ▸ setiembre 2026 ▸ «PLE 6.1».

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | nombre del TXT 6.1 | LE2055791287920260900060100001111 |
| ✅ | líneas del asiento en el mayor | esperado 2, obtenido 2 |
| ✅ | 21 campos por línea | esperado 21, obtenido 21 |
| ✅ | el 6.1 no lleva la referencia del libro (campo 20) | esperado '', obtenido '' |
| ✅ | XLSX 6.1 generado | esperado 'xlsx', obtenido 'xlsx' |

#### ✅ PLE 8.1 → RCE 8.4 (Registro de Compras)

**Pasos en pantalla:** Informes ▸ RCE Registro de Compras 8.4 ▸ setiembre 2026 ▸ «TXT».

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | nombre oficial LE…080400 | LE2055791287920260900080400021112 |
| ✅ | la compra está en el 8.4 | esperado 1, obtenido 1 |
| ✅ | 37 campos | esperado 37, obtenido 37 |
| ✅ | campo 13: RUC del proveedor | esperado '20609920026', obtenido '20609920026' |
| ✅ | campo 5: fecha de emisión | esperado '15/09/2026', obtenido '15/09/2026' |
| ✅ | base e IGV de la adquisición gravada | esperado ('4000.00', '720.00'), obtenido ('4000.00', '720.00') |
| ✅ | campo 25: total | esperado '4720.00', obtenido '4720.00' |

**Registros:** `account.move/28853` F FQ20-31600023

#### ✅ PLE 14.1 → RVIE 14.4 (Registro de Ventas)

**Pasos en pantalla:** Informes ▸ RVIE Registro de Ventas 14.4 ▸ setiembre 2026 ▸ «TXT».

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | nombre oficial LE…140400…2 | LE2055791287920260900140400021112 |
| ✅ | la venta está en el 14.4 | esperado 1, obtenido 1 |
| ✅ | 33 campos (sin los 34-40) | esperado 33, obtenido 33 |
| ✅ | campo 12: RUC del cliente | esperado '20609920018', obtenido '20609920018' |
| ✅ | base, IGV y total | esperado ('10000.00', '1800.00', '11800.00'), obtenido ('10000.00', '1800.00', '11800.00') |

**Registros:** `account.move/28852` FQ20-31600022


### `al_l10n_pe_sire`

#### ✅ RVIE setiembre: comprobantes del sistema

**Pasos en pantalla:** Perú ▸ SIRE ▸ RVIE setiembre 2026 ▸ «Cargar del sistema».

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | la venta aparece en la propuesta del sistema | esperado 1, obtenido 1 |
| ✅ | cliente con RUC | esperado ('6', '20609920018'), obtenido ('6', '20609920018') |
| ✅ | importes | esperado (10000.0, 1800.0, 11800.0), obtenido (10000.0, 1800.0, 11800.0) |
| ✅ | CAR de 27 caracteres | 2055791287901FQ200031600022 |
| ⏭️ | Descarga de la propuesta y envío al SIRE | sin credenciales SOL de prueba |

**Registros:** `l10n_pe.sire.rvie/39` RVIE-09-2026

#### ✅ RCE con proveedor no domiciliado (8.5): país, modalidad y tipo de renta nativos

**Pasos en pantalla:** Compras ▸ factura tipo 91 de proveedor de EE. UU. con tipo de renta 18 y modalidad 3 ▸ SIRE ▸ RCE setiembre ▸ «Cargar no domiciliados».

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | tipo de renta guardado en l10n_pe_usage_type_id nativo | esperado '18', obtenido '18' |
| ✅ | modalidad = l10n_pe_service_modality nativo | esperado '3', obtenido '3' |
| ✅ | marcado como no domiciliado |  |
| ✅ | sale del RCE y va al registro de no domiciliados |  |
| ✅ | la compra doméstica sí está en el RCE |  |
| ✅ | línea del no domiciliado desplegada | esperado 1, obtenido 1 |
| ✅ | sin observaciones | False |
| ✅ | 35 campos del anexo 9 | esperado 35, obtenido 35 |
| ✅ | campo 17: país desde res.country.l10n_pe_code (9249) | esperado '9249', obtenido '9249' |
| ✅ | campo 32: tipo de renta | esperado '18', obtenido '18' |
| ✅ | campo 33: modalidad del servicio | esperado '3', obtenido '3' |
| ✅ | campo 25: renta bruta | esperado '500.00', obtenido '500.00' |
| ✅ | campo 29: impuesto retenido 30 % | esperado '150.00', obtenido '150.00' |
| ✅ | no se envía sin aceptar la propuesta |  |
| ⏭️ | Carga del 8.5 al SIRE | sin credenciales SOL de prueba |

**Registros:** `res.partner/9104` QA20 Cloud Services Inc, `account.move/28855` Borrador de factura C INV-31600024, `l10n_pe.sire.rce/24` RCE-09-2026


### `al_l10n_pe_cpe_validation`

#### ✅ Consulta integrada de comprobantes (SUNAT simulada)

**Pasos en pantalla:** Compras ▸ factura de proveedor ▸ «Validar en SUNAT»: válido, observado y no válido.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | datos de la consulta según el manual | esperado ('20609920026', '01', 'FQ20'), obtenido ('20609920026', '01', 'FQ20') |
| ✅ | resultado: válido | esperado ('valid', '1'), obtenido ('valid', '1') |
| ✅ | se pidió token OAuth2 (simulado) |  |
| ✅ | domicilio no habido: observado | esperado 'observed', obtenido 'observed' |
| ✅ | no informado: no válido | esperado 'invalid', obtenido 'invalid' |
| ✅ | mensaje de SUNAT guardado |  |
| ⏭️ | Consulta real a la API de SUNAT | sin credenciales de prueba |

**Registros:** `account.move/28856` Borrador de factura F FQ20-31600025, `account.move/28858` Borrador de factura F FQ20-31600026, `account.move/28859` Borrador de factura F FQ20-31600027


### `al_l10n_pe_financial_reports`

#### ✅ Hoja de trabajo (formato 1) 2026 con mis cuentas

**Pasos en pantalla:** Contabilidad ▸ Informes ▸ Perú ▸ Hoja de trabajo ▸ 2026.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | fila de la cuenta 94 de destino | ['1049920 QA20 Pagos pendientes', '1213000 Facturas, boletas y otros comprobantes por cobrar - En cobranza', '1219920 QA20 Detracciones por cobrar'] |
| ✅ | sumas del debe de la 94 = mayor | esperado 900.0, obtenido 900.0 |
| ✅ | la 94 va a pérdidas por función | esperado 900.0, obtenido 900.0 |
| ✅ | totales cuadrados: sum_debit = sum_credit | esperado 65528.35, obtenido 65528.35 |
| ✅ | totales cuadrados: balance_debit = balance_credit | esperado 31526.149999999998, obtenido 31526.15 |

#### ✅ Estado de cambios en el patrimonio (3.19) = patrimonio del balance

**Pasos en pantalla:** Informes ▸ Perú ▸ Estado de cambios en el patrimonio neto ▸ 2026.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | columnas del formato 3.19 | esperado ['movement_note', 'opening', 'movement', 'closing'], obtenido ['movement_note', 'opening', 'movement', 'closing'] |
| ✅ | saldo final del 3.19 = patrimonio del balance | esperado -5946.55, obtenido -5946.55 |


### `al_l10n_pe_dashboard`

#### ✅ Tablero Perú: vista de IGV y armado de la hoja

**Pasos en pantalla:** Tableros ▸ Perú: ventas, compras e IGV del mes.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | venta: base 10 000, IGV 1 800 | esperado ('sale', 10000.0, 1800.0), obtenido ('sale', 10000.0, 1800.0) |
| ✅ | compra: base 4 000, IGV 720 | esperado ('purchase', 4000.0, 720.0), obtenido ('purchase', 4000.0, 720.0) |
| ✅ | sección «Ventas, compras e IGV» en la hoja |  |
| ✅ | todas las fuentes del tablero se pueden consultar (28) |  |


## Fase 1B · Contabilidad: cobros, pagos, bancos y cierre


### `al_l10n_pe_bank_loan`

#### ✅ Préstamo francés: desembolso con comisión e ITF, devengo y pago de la 1.ª cuota

**Pasos en pantalla:** Tesorería ▸ Préstamos ▸ Nuevo (S/ 120 000, TEA 12 %, 12 cuotas) ▸ Calcular cronograma ▸ Confirmar; Devengar al 31/01 y Pagar cuota desde el asistente.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | secuencia PRE/ | PRE/2026/0079 |
| ✅ | cuenta de capital 4511 | 4511000 |
| ✅ | intereses por pagar 45511 | 4551100 |
| ✅ | cronograma de 12 cuotas | esperado 12, obtenido 12 |
| ✅ | capital del cronograma = préstamo | esperado 120000.0, obtenido 120000.0 |
| ✅ | cuota fija (método francés) | esperado 1, obtenido 1 |
| ✅ | interés 1.ª cuota (TEA, 31 días, base 360) | esperado 1176.8, obtenido 1176.8 |
| ✅ | préstamo en curso | esperado 'running', obtenido 'running' |
| ✅ | desembolso: capital al haber 4511 | esperado -120000.0, obtenido -120000.0 |
| ✅ | comisión de desembolso al gasto | esperado 500.0, obtenido 500.0 |
| ✅ | banco recibe el neto de comisión menos ITF (5.95) | esperado 119494.05, obtenido 119494.05 |
| ✅ | ITF calculado sobre el desembolso | ITF 6.0 (tasa 0.005 %) |
| ✅ | TCEA > TEA por la comisión | TCEA 12.8700 |
| ✅ | devengo de 16/31 días (idempotente) | esperado 607.38, obtenido 607.38 |
| ✅ | interés por pagar devengado | esperado -607.38, obtenido -607.38 |
| ✅ | asistente propone el total de la cuota | esperado 10633.68, obtenido 10633.68 |
| ✅ | cuota 1 pagada | esperado 'paid', obtenido 'paid' |
| ✅ | devengo cancelado al pagar | esperado 0.0, obtenido 0.0 |
| ✅ | gasto financiero = interés | esperado 1176.8, obtenido 1176.8 |
| ✅ | saldo de capital tras la cuota | esperado 110543.12, obtenido 110543.12 |
| ✅ | todos los asientos cuadran | 4 asientos |
| ✅ | impide pagar cuotas fuera de orden | Pague las cuotas en orden: la siguiente es la 2. |

**Registros:** `l10n_pe.bank.loan/79` PRE/2026/0079, `account.move/30804` Q4BK/2026/00001 (Desembolso PRE/2026/0079 QA20 P4 BANCO [..., `account.move/30805` Q4MS/2026/01/0001 (Intereses PRE/2026/0079 al 2026-01-31), `account.move/30806` Q4MS/2026/02/0001 (Intereses PRE/2026/0079 al 2026-02-15), `account.move/30807` Q4BK/2026/00002 (Cuota 1 PRE/2026/0079)

#### ✅ Prepago con reducción de cuota y línea de crédito

**Pasos en pantalla:** Tesorería ▸ Líneas de crédito ▸ Nueva (S/ 150 000); préstamo ligado ▸ Confirmar ▸ Prepagar capital S/ 30 000.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | línea: usado | esperado 120000.0, obtenido 120000.0 |
| ✅ | línea: disponible | esperado 30000.0, obtenido 30000.0 |
| ✅ | bloquea exceder la línea de crédito | El préstamo supera el disponible de la línea QA20 P4 Línea préstamos (30000.0). |
| ✅ | mantiene 11 cuotas pendientes | esperado 11, obtenido 11 |
| ✅ | capital pendiente = saldo − prepago | esperado 80543.12, obtenido 80543.12 |
| ✅ | la cuota baja tras el prepago | 10633.68 → 7713.76 |
| ✅ | asientos cuadrados |  |

**Registros:** `l10n_pe.treasury.credit.line/20` QA20 P4 Línea préstamos, `l10n_pe.bank.loan/80` PRE/2026/0080, `account.move/30811` Q4MS/2026/03/0001 (Intereses PRE/2026/0080 al 2026-03-01), `account.move/30812` Q4BK/2026/00005 (Prepago PRE/2026/0080), `account.move/30809` Q4MS/2026/02/0002 (Intereses PRE/2026/0080 al 2026-02-15), `account.move/30810` Q4BK/2026/00004 (Cuota 1 PRE/2026/0080), `account.move/30808` Q4BK/2026/00003 (Desembolso PRE/2026/0080 QA20 P4 BANCO [...


### `al_l10n_pe_bank_guarantee`

#### ✅ Carta fianza emitida: comisión por trimestre, activación, renovación y ejecución

**Pasos en pantalla:** Tesorería ▸ Cartas fianza ▸ Nueva (S/ 50 000, 0,5 % trimestral) ▸ Activar ▸ Renovar ▸ Ejecutar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | comisión 3 trimestres × 0,5 % × 50 000 | esperado 750.0, obtenido 750.0 |
| ✅ | comisión mínima | esperado 100.0, obtenido 100.0 |
| ✅ | fianza activa | esperado 'active', obtenido 'active' |
| ✅ | gasto de comisión | esperado 750.0, obtenido 750.0 |
| ✅ | salida de banco por la comisión | esperado -750.0, obtenido -750.0 |
| ✅ | original queda renovada | esperado 'renewed', obtenido 'renewed' |
| ✅ | renovación activa | esperado 'active', obtenido 'active' |
| ✅ | renovación desde el vencimiento anterior | esperado datetime.date(2026, 7, 10), obtenido datetime.date(2026, 7, 10) |
| ✅ | comisión de la renovación | esperado 750.0, obtenido 750.0 |
| ✅ | fianza ejecutada | esperado 'executed', obtenido 'executed' |
| ✅ | ejecución al gasto (6591000) | esperado 20000.0, obtenido 20000.0 |

**Registros:** `l10n_pe.bank.guarantee/53` CF/2026/0053, `l10n_pe.bank.guarantee/55` CF/2026/0055, `account.move/30813` Q4BK/2026/00006 (Comisión Carta fianza QA20-CF-123657 Fiel [, `account.move/30814` Q4BK/2026/00007 (Comisión Renovación carta fianza QA20-CF-12, `account.move/30815` Q4BK/2026/00008 (Ejecución carta fianza QA20-CF-123657)

#### ✅ Carta fianza recibida: sin comisión, plazo de reclamo y aviso por cron

**Pasos en pantalla:** Tesorería ▸ Cartas fianza ▸ Nueva (recibida del contratista) ▸ Activar; el cron avisa antes del vencimiento.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | sin comisión | esperado 0.0, obtenido 0.0 |
| ✅ | plazo de reclamo (art. 1898 CC: +15 días) | esperado datetime.date(2026, 7, 25), obtenido datetime.date(2026, 7, 25) |
| ✅ | no genera asientos |  |
| ✅ | cron crea actividad de aviso |  |
| ✅ | actividad vence con el plazo de reclamo | esperado datetime.date(2026, 7, 25), obtenido datetime.date(2026, 7, 25) |

**Registros:** `l10n_pe.bank.guarantee/56` CF/2026/0056


### `al_l10n_pe_term_deposit`

#### ✅ Depósito a plazo: apertura, devengo mensual y cancelación al vencimiento

**Pasos en pantalla:** Tesorería ▸ Depósitos a plazo ▸ Nuevo (S/ 100 000, TEA 6 %, 180 días) ▸ Abrir ▸ Devengar ▸ Cancelar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | secuencia DEP/ | DEP/2026/0083 |
| ✅ | vencimiento a 180 días | esperado datetime.date(2026, 6, 30), obtenido datetime.date(2026, 6, 30) |
| ✅ | cuenta 1062 | 1062000 |
| ✅ | interés esperado 100 000 × (1,06^(180/360) − 1) | esperado 2956.3, obtenido 2956.3 |
| ✅ | depósito abierto | esperado 'open', obtenido 'open' |
| ✅ | cargo a 1062 | esperado 100000.0, obtenido 100000.0 |
| ✅ | abono al banco | esperado -100000.0, obtenido -100000.0 |
| ✅ | devengo a marzo (idempotente) | esperado 1450.96, obtenido 1450.96 |
| ✅ | apertura + 3 devengos | esperado 4, obtenido 4 |
| ✅ | ingreso financiero devengado | esperado -1450.96, obtenido -1450.96 |
| ✅ | depósito cancelado | esperado 'closed', obtenido 'closed' |
| ✅ | saldo 1062 en cero | esperado 0.0, obtenido 0.0 |
| ✅ | intereses por cobrar en cero | esperado 0.0, obtenido -0.0 |
| ✅ | el banco recibe capital + intereses | esperado 2956.3, obtenido 2956.3 |
| ✅ | asientos cuadrados |  |

**Registros:** `l10n_pe.term.deposit/83` DEP/2026/0083, `account.move/30816` Q4BK/2026/00009 (Apertura DEP/2026/0083 Depósito a plazo), `account.move/30817` Q4MS/2026/01/0002 (Intereses DEP/2026/0083 al 2026-01-31), `account.move/30818` Q4MS/2026/02/0003 (Intereses DEP/2026/0083 al 2026-02-28), `account.move/30819` Q4MS/2026/03/0002 (Intereses DEP/2026/0083 al 2026-03-31), `account.move/30820` Q4MS/2026/06/0001 (Intereses DEP/2026/0083 al 2026-06-30), `account.move/30821` Q4BK/2026/00010 (Cancelación DEP/2026/0083)

#### ✅ Renovación con capitalización y garantía de alquiler con liberación parcial

**Pasos en pantalla:** Depósito ▸ Renovar (capitaliza intereses); Depósito de garantía ▸ Abrir ▸ Liberar S/ 2 000 y luego el saldo.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | original renovado | esperado 'renewed', obtenido 'renewed' |
| ✅ | renovación abierta | esperado 'open', obtenido 'open' |
| ✅ | capital nuevo = capital + intereses | esperado 102956.3, obtenido 102956.3 |
| ✅ | intereses capitalizados (sin saldo por cobrar) | esperado 0.0, obtenido 0.0 |
| ✅ | garantía en 1643 | 1643000 |
| ✅ | saldo tras liberación parcial | esperado 4000.0, obtenido 4000.0 |
| ✅ | no libera más del saldo | El importe a liberar debe ser mayor que cero y no superar el saldo (4000.0). |
| ✅ | garantía cerrada | esperado 'closed', obtenido 'closed' |
| ✅ | saldo 1643 en cero | esperado 0.0, obtenido 0.0 |

**Registros:** `l10n_pe.term.deposit/84` DEP/2026/0084, `l10n_pe.term.deposit/85` DEP/2026/0085, `l10n_pe.term.deposit/86` DEP/2026/0086


### `al_l10n_pe_lease`

#### ✅ Reconocimiento NIIF 16: derecho de uso, pasivo, activo, préstamo y cuotas

**Pasos en pantalla:** Contabilidad ▸ Arrendamientos ▸ Nuevo (36 meses, S/ 1 000 adelantado, TEA 12 %) ▸ Crear subcuentas ▸ Confirmar ▸ Registrar cuota (factura del arrendador).

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | pasivo = VP de 35 cuotas (la 1.ª es adelantada) | esperado 29662.97, obtenido 29662.97 |
| ✅ | derecho de uso = pasivo + cuota adelantada + costos | esperado 31162.97, obtenido 31162.97 |
| ✅ | subcuenta pasivo LP 4521 | 4521000 |
| ✅ | subcuenta pasivo CP 4522 | 4522000 |
| ✅ | contrato en curso | esperado 'running', obtenido 'running' |
| ✅ | asiento inicial publicado | esperado 'posted', obtenido 'posted' |
| ✅ | transitoria: cuota adelantada + costos | esperado 1500.0, obtenido 1500.0 |
| ✅ | activo lineal a 36 meses | esperado ('linear', 36), obtenido ('linear', 36.0) |
| ✅ | valor del activo = derecho de uso | esperado 31162.97, obtenido 31162.97 |
| ✅ | préstamo (account_loans) de 35 cuotas | esperado 35, obtenido 35 |
| ✅ | préstamo = pasivo | esperado 29662.97, obtenido 29662.97 |
| ✅ | activo y pasivo enlazados por grupo |  |
| ✅ | cuota 1 salda la transitoria | esperado account.account(14183,), obtenido account.account(14183,) |
| ✅ | cuota 2 al pasivo CP | esperado account.account(282203,), obtenido account.account(282203,) |
| ✅ | cuota 2 fechada 01/02 | esperado datetime.date(2026, 2, 1), obtenido datetime.date(2026, 2, 1) |

**Registros:** `l10n_pe.lease/217` ARR/2026/0217, `account.move/30970` Q4AP/2026/01/0001 (ARR/2026/0217 1/36), `account.move/30973` Q4AP/2026/02/0001 (ARR/2026/0217 2/36), `account.move/30829` Q4AR/2026/01/0001 (Reconocimiento inicial ARR/2026/0217)

#### ✅ Remedición (aumento de renta) tras publicar la depreciación del mes

**Pasos en pantalla:** Arrendamiento ▸ Contabilizar depreciación de octubre ▸ Remedir desde 01/11/2026 (renta S/ 1 100, 26 meses).

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | rechaza remedir un mes ya contabilizado (01/10) | Ya hay asientos contabilizados desde 2026-10-01 (Q4AR/2026/10/0004 (ARR/2026/0218 - QA20 P4 Oficina remedición |
| ✅ | depreciación de octubre publicada | MISC/2026/10/0002 |
| ✅ | nuevo pasivo (incluye la cuota adelantada de noviembre) | esperado 25479.22, obtenido 25479.22 |
| ✅ | diferencia positiva (aumento) | 2534.01 |
| ✅ | préstamo anterior cerrado | esperado 'closed', obtenido 'closed' |
| ✅ | nuevo préstamo = nuevo pasivo | esperado 25479.22, obtenido 25479.22 |
| ✅ | aumento bruto del derecho de uso | esperado 2534.01, obtenido 2534.01 |
| ✅ | valor en libros + diferencia | esperado 24679.489999999998, obtenido 24679.49 |
| ✅ | evento de remedición | esperado ['remeasurement'], obtenido ['remeasurement'] |
| ✅ | libro cuadra con la tabla | esperado 0.0, obtenido 0.0 |

**Registros:** `l10n_pe.lease/218` ARR/2026/0218, `account.move/31208` MISC/2026/11/0001 (Remedición ARR/2026/0218: aumento del [..


### `al_l10n_pe_import_dua`

#### ⚠️ DUA: número de la DAM, liquidación (derechos + IGV) y publicación

**Pasos en pantalla:** Compras ▸ Facturas ▸ Nueva con tipo 50 (DUA), Aduana 118, régimen 10 ▸ Generar líneas de la liquidación ▸ Confirmar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ⚠️ | compañía sin socio Aduanas / cuenta puente de DUA | se configuraron al inicio de la fase |
| ✅ | reconocida como DUA |  |
| ✅ | número DAM aduana-año-régimen-correlativo | esperado '118-2026-10-023657', obtenido '118-2026-10-023657' |
| ✅ | base del IGV = valor + derechos | esperado 10700.0, obtenido 10700.0 |
| ✅ | IGV 18 % de 10 700 | esperado 1926.0, obtenido 1926.0 |
| ✅ | total a pagar a Aduanas: derechos 700 + IGV 1 926 | esperado 2626.0, obtenido 2626.0 |
| ✅ | regenerar no duplica líneas | esperado 4, obtenido 4 |
| ✅ | DUA publicada | esperado 'posted', obtenido 'posted' |
| ✅ | costos en destino exigen recepciones | Indique las recepciones de la importación. |

**Registros:** `account.move/31261` Borrador de factura D 118-2026-10-023657 (QA20 P4 DUA)


### `al_l10n_pe_exchange_closure`

#### ✅ Cierre mensual de T.C.: activo a compra, pasivo a venta, detalle por socio

**Pasos en pantalla:** Contabilidad ▸ Cierre ▸ Cierre de tipo de cambio ▸ Nuevo (setiembre 2026, compra 3,80 / venta 3,82) ▸ Calcular ▸ Contabilizar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | fecha de asiento fin de mes | esperado datetime.date(2026, 9, 30), obtenido datetime.date(2026, 9, 30) |
| ✅ | T.C. de cierre SBS publicado al día siguiente | esperado datetime.date(2026, 10, 1), obtenido datetime.date(2026, 10, 1) |
| ✅ | T.C. tomado del registro (sin red) | esperado (3.8, 3.82), obtenido (3.8, 3.82) |
| ✅ | activo usa T.C. compra | esperado 'purchase', obtenido 'purchase' |
| ✅ | ajuste banco 1 000 × (3,80 − 3,70) | esperado 100.0, obtenido 100.0 |
| ✅ | pasivo usa T.C. venta | esperado 'sale', obtenido 'sale' |
| ✅ | ajuste préstamo −1 000 × (3,82 − 3,70) | esperado -120.0, obtenido -120.0 |
| ✅ | detalle socio A | esperado 100.0, obtenido 100.0 |
| ✅ | detalle socio B (1 900 − 1 855) | esperado 45.0, obtenido 45.0 |
| ✅ | ganancia total | esperado 245.0, obtenido 245.0 |
| ✅ | pérdida total (no se netea) | esperado 120.0, obtenido 120.0 |
| ✅ | cierre contabilizado | esperado 'posted', obtenido 'posted' |
| ✅ | abono a ganancia por diferencia de cambio | esperado 245.0, obtenido 245.0 |
| ✅ | cargo a pérdida por diferencia de cambio | esperado 120.0, obtenido 120.0 |
| ✅ | el ajuste no mueve moneda extranjera | 4 líneas en USD |
| ✅ | T.C. citado en la línea | esperado 3.8, obtenido 3.8 |

**Registros:** `res.company/1043` QA20 P4 Cierre TC 123657 S.A.C., `l10n_pe.exchange.closure/197` Septiembre 2026, `account.move/31265` Q4TC/2026/09/0004 (Cierre de tipo de cambio Septiembre 2026)


### `al_l10n_pe_multicurrency_revaluation`

#### ✅ Informe de G/P no realizadas con T.C. compra/venta por cuenta y asiento

**Pasos en pantalla:** Contabilidad ▸ Informes ▸ Ganancias/pérdidas no realizadas al 30/09/2026 ▸ ver columna T.C. ▸ Ajuste ▸ asiento de provisión.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | campo T.C. visible solo en cuentas de balance |  |
| ✅ | columna T.C. presente |  |
| ✅ | líneas de las cuentas en el informe |  |
| ✅ | por pagar revaluada a T.C. compra | esperado 'S/ 3.720', obtenido 'S/ 3.720' |
| ✅ | ajuste por pagar −100 × (3,72 − 3,70) | esperado -2.0, obtenido -2.000000000000026 |
| ✅ | por cobrar revaluada a T.C. venta | esperado 'S/ 3.700', obtenido 'S/ 3.700' |
| ✅ | por cobrar sin ajuste | esperado 0.0, obtenido 1.3783e-13 |
| ✅ | línea total de la moneda |  |
| ✅ | cabecera con el T.C. | esperado 'USD (1 USD = S/ 3.700)', obtenido 'USD (1 USD = S/ 3.700)' |
| ✅ | T.C. en blanco al mezclar tasas | esperado '', obtenido '' |
| ✅ | ajuste total | esperado -2.0, obtenido -1.9999999999998883 |
| ✅ | línea del asiento cita el T.C. aplicado | Provisión de USD (T.C. S/ 3.720) |
| ✅ | abono de 2,00 a por pagar | esperado 2.0, obtenido 2.000000000000026 |
| ✅ | asiento de ajuste publicado | Q4VR/2026/09/0003 |

**Registros:** `res.company/1044` QA20 P4 Revaluación 123657 S.A.C., `account.move/31268` Q4VR/2026/09/0003 (Asiento de ajuste de divisas extranjeras 


### `al_account_payments`

#### ✅ N.º de operación = payment_reference nativo y medio de pago SUNAT

**Pasos en pantalla:** Contabilidad → Clientes → Pagos → Nuevo: medio «003 Transferencia», N.º de operación; Confirmar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | bank_operation_number es related a payment_reference | payment_reference |
| ✅ | Diario con «Exigir número de operación» bloquea sin n.º | Indique el número de operación del banco en: Borrador de pago. |
| ✅ | escribir bank_operation_number llena payment_reference | esperado 'OP-QA20-0001', obtenido 'OP-QA20-0001' |
| ✅ | escribir payment_reference se refleja en bank_operation_number | esperado 'OP-QA20-0002', obtenido 'OP-QA20-0002' |
| ✅ | pago publicado con n.º de operación | paid |
| ✅ | el n.º se guarda en la columna nativa payment_reference | esperado 'OP-QA20-0002', obtenido 'OP-QA20-0002' |
| ✅ | bank_operation_number no es columna propia (no store) |  |
| ✅ | medio de pago SUNAT en el pago | esperado '003', obtenido '003' |
| ✅ | búsqueda por n.º de operación funciona sobre el related |  |

**Registros:** `account.journal/6057` QA20 P1 Banco exige operación, `res.partner/9403` QA20 P1 Cliente pagos SAC, `account.payment/1333` PQ1BOP/2026/00001

#### ✅ Asistente de registro traslada medio y n.º de operación (agrupado)

**Pasos en pantalla:** Factura de cliente → Registrar pago (2 facturas, agrupar): medio 001, n.º LOTE; Crear pago.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | un solo pago agrupado | esperado 1, obtenido 1 |
| ✅ | importe del pago | esperado 1000.0, obtenido 1000.0 |
| ✅ | n.º de operación trasladado | esperado 'LOTE-QA20-01', obtenido 'LOTE-QA20-01' |
| ✅ | payment_reference nativo poblado por el asistente | esperado 'LOTE-QA20-01', obtenido 'LOTE-QA20-01' |
| ✅ | medio de pago trasladado | esperado pe.catalog.payment(1,), obtenido pe.catalog.payment(1,) |
| ✅ | facturas pagadas | ['in_payment', 'in_payment'] |

**Registros:** `res.partner/9404` QA20 P1 Cliente registro SAC, `account.move/31271` Q1VT/2026/00001, `account.move/31272` Q1VT/2026/00002, `account.payment/1334` PQ1BK/2026/00001

#### ✅ Compra de dólares al T.C. del banco (asistente de cambio)

**Pasos en pantalla:** Contabilidad → Bancos → Compra/venta de moneda: de Banco soles a Banco dólares, S/ 3 800 a 3,80; Confirmar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | US$ recibidos = 3 800 / 3,80 | esperado 1000.0, obtenido 1000.0 |
| ✅ | T.C. del sistema | esperado 3.75, obtenido 3.75 |
| ✅ | diferencia frente al T.C. del sistema | esperado -50.0, obtenido -50.0 |
| ✅ | salida en soles y entrada en dólares | esperado ['inbound', 'outbound'], obtenido ['inbound', 'outbound'] |
| ✅ | n.º de operación en ambos pagos | esperado {'CAMB-QA20-1'}, obtenido {'CAMB-QA20-1'} |
| ✅ | cuenta de transferencias conciliada | 1051001 |
| ✅ | asiento de diferencia de cambio en 6760000 por 50.0 |  |

**Registros:** `account.journal/6059` QA20 P1 Banco dólares (USD), `account.payment/1335` PQ1BK/2026/00002, `account.payment/1336` PQ1BKU/2026/00001, `account.move/31276` CAMBIO/2026/10/0001 (Diferencia de cambio en la compra y ven


### `al_l10n_pe_payment_multi`

#### ✅ Un pago para facturas de dos proveedores + anticipo + comisión

**Pasos en pantalla:** Contabilidad → Proveedores → Pago múltiple → Nuevo: cargar facturas de 2 proveedores, línea de anticipo y de comisión; Validar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | carga las facturas abiertas de ambos proveedores | esperado account.move(31277, 31278), obtenido account.move(31278, 31277) |
| ✅ | total = 1000 + 500 + 250 + 15 | esperado 1765.0, obtenido 1765.0 |
| ✅ | dos socios | esperado 2, obtenido 2 |
| ✅ | pago múltiple validado | esperado 'posted', obtenido 'posted' |
| ✅ | importe del pago | esperado 1765.0, obtenido 1765.0 |
| ✅ | varios socios: el pago no lleva socio |  |
| ✅ | facturas pagadas | ('in_payment', 'in_payment') |
| ✅ | anticipo al debe en 422 (4220000) | esperado 250.0, obtenido 250.0 |
| ✅ | anticipo con el socio | esperado res.partner(9406,), obtenido res.partner(9406,) |
| ✅ | comisión al gasto | esperado 15.0, obtenido 15.0 |
| ✅ | comprobante de egreso numerado | RE-Q1PM-000001 |
| ✅ | comprobante PDF lista a cada socio |  |
| ✅ | anular reabre las facturas | ('canceled', 1000.0) |
| ✅ | revalidar crea un pago nuevo |  |

**Registros:** `res.partner/9405` QA20 P1 Proveedor Uno SAC, `res.partner/9406` QA20 P1 Proveedor Dos SAC, `account.move/31277` Q1CP/2026/10/0001, `account.move/31278` Q1CP/2026/10/0002, `l10n_pe.payment.multi/51` PM/2026/00051, `account.payment/1337` PQ1PM/2026/00001, `account.payment/1338` PQ1PM/2026/00002

#### ✅ Factura en US$ pagada desde banco en soles: diferencia de cambio

**Pasos en pantalla:** Pago múltiple desde banco en soles con factura en dólares; Validar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | US$ 100 a pagar | esperado 100.0, obtenido 100.0 |
| ✅ | en soles al T.C. del pago | esperado 380.0, obtenido 380.0 |
| ✅ | diferencia de cambio registrada | esperado 10.0, obtenido 10.0 |

**Registros:** `res.partner/9407` QA20 P1 Proveedor dólares SAC, `account.move/31281` Q1CP/2026/10/0003, `l10n_pe.payment.multi/52` PM/2026/00052, `account.move/31283` CAMBIO/2026/10/0002 (PQ1PM/2026/00003)


### `al_l10n_pe_payment_application`

#### ✅ Anticipo de proveedor (422) aplicado a factura y reversión

**Pasos en pantalla:** Pago a proveedor marcado «Anticipo»; desde la factura → Aplicar anticipos → Distribuir → Validar; luego Anular.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | el anticipo va a la 422 (4220000) | esperado account.account(14744,), obtenido account.account(14744,) |
| ✅ | la factura ve 1 anticipo pendiente | esperado 1, obtenido 1 |
| ✅ | aplicación validada | esperado 'posted', obtenido 'posted' |
| ✅ | asiento en el diario de aplicaciones | esperado account.journal(1366,), obtenido account.journal(1366,) |
| ✅ | factura cancelada con el anticipo | paid |
| ✅ | saldo del anticipo por aplicar | esperado 400.0, obtenido 400.0 |
| ✅ | aplicación anulada | esperado 'cancel', obtenido 'cancel' |
| ✅ | asiento de reversión creado |  |
| ✅ | la factura vuelve a quedar pendiente | esperado 600.0, obtenido 600.0 |
| ✅ | compensación carga cobrar y pagar del socio |  |
| ✅ | factura de compra compensada por 500 | esperado 100.0, obtenido 100.0 |
| ✅ | factura de venta cancelada por compensación | paid |

**Registros:** `res.partner/9408` QA20 P1 Socio anticipos SAC, `account.payment/1340` PQ1AN/2026/00001, `account.move/31285` Q1CP/2026/10/0004, `l10n_pe.payment.application/29` APL/2026/00029, `account.move/31288` Q1VT/2026/00003, `l10n_pe.payment.application/30` APL/2026/00030


### `al_l10n_pe_payment_receipt`

#### ✅ Comprobante de ingreso/egreso numerado por diario y PDF

**Pasos en pantalla:** Caja con «Comprobante de pago» → Registrar pago parcial de una factura → Imprimir comprobante.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | secuencia de ingresos por diario | esperado 'RI-Q1CJ-', obtenido 'RI-Q1CJ-' |
| ✅ | secuencia de egresos por diario | esperado 'RE-Q1CJ-', obtenido 'RE-Q1CJ-' |
| ✅ | n.º de recibo de ingreso | RI-Q1CJ-000001 |
| ✅ | el comprobante detalla la factura aplicada |  |
| ✅ | aplicado | esperado 118.5, obtenido 118.5 |
| ✅ | saldo de la factura | esperado 181.5, obtenido 181.5 |
| ✅ | importe en letras | esperado 'CIENTO DIECIOCHO Y 50/100 SOLES', obtenido 'CIENTO DIECIOCHO Y 50/100 SOLES' |
| ✅ | PDF con número, importe en letras y factura |  |
| ✅ | el número se conserva al volver a borrador | esperado 'RI-Q1CJ-000001', obtenido 'RI-Q1CJ-000001' |
| ✅ | n.º de recibo de egreso | RE-Q1CJ-000001 |
| ✅ | acción Imprimir comprobante | ir.actions.act_window (sin diseño: Odoo abre antes el asistente de diseño) |

**Registros:** `account.journal/6062` QA20 P1 Caja recibos, `res.partner/9409` QA20 P1 Cliente recibo SAC, `account.move/31290` Q1VT/2026/00004, `account.payment/1341` PAY00100, `account.payment/1342` PAY00101


### `al_l10n_pe_payment_term_currency`

#### ✅ Cuota fija en soles en factura en dólares

**Pasos en pantalla:** Configuración → Términos de pago: cuota fija S/ 750 «Importe en soles» + saldo a 30 días; factura en US$ 1 000 con ese término; Confirmar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | primera cuota = S/ 750 exactos | esperado 750.0, obtenido 750.0 |
| ✅ | primera cuota en US$ al T.C. de la factura (3.75) | esperado 200.0, obtenido 200.0 |
| ✅ | cuotas en US$ suman el total | esperado 1000.0, obtenido 1000.0 |
| ✅ | cuotas en S/ suman el total | esperado 3750.0, obtenido 3750.0 |
| ✅ | en soles el término funciona como el nativo | esperado [750.0, 250.0], obtenido [750.0, 250.0] |

**Registros:** `account.payment.term/359` QA20 P1 S/ 750 a la firma y saldo 30 días, `res.partner/9410` QA20 P1 Cliente cuotas SAC, `account.move/31291` Q1VT/2026/00005, `account.move/31292` Q1VT/2026/00006


### `al_l10n_pe_bank_statement_import`

#### ✅ Importar extracto XLSX y CSV de banca por internet (archivos de sus tests)

**Pasos en pantalla:** Contabilidad → Tablero → Banco → Importar archivo: movimientos.xlsx y estado.csv; reimportar no duplica.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | XLSX reconocido sin mapeo manual de columnas |  |
| ✅ | importes en orden cronológico | esperado [-10.5, 2350.5, -1500.0], obtenido [-10.5, 2350.5, -1500.0] |
| ✅ | descripción | esperado 'COMISION MANTENIMIENTO', obtenido 'COMISION MANTENIMIENTO' |
| ✅ | un extracto | esperado 1, obtenido 1 |
| ✅ | saldos inicial y final del banco | esperado (7510.0, 8350.0), obtenido (7510.0, 8350.0) |
| ✅ | extracto completo (saldos cuadran) |  |
| ✅ | CSV cargo/abono añade 3 movimientos | esperado 6, obtenido 6 |
| ✅ | importes del CSV (coma decimal) | esperado [-800.0, -0.05, 1250.0], obtenido [-800.0, -0.05, 1250.0] |
| ✅ | reimportar el mismo archivo no duplica | esperado 6, obtenido 6 |
| ✅ | CSV no reconocido pasa al importador nativo | esperado 'import_bank_stmt', obtenido 'import_bank_stmt' |

**Registros:** `account.journal/6063` QA20 P1 Banco extractos, `account.bank.statement/385` QA20 P1 Banco extractos 21/10/2026 al 23/10/2026, `account.bank.statement/386` QA20 P1 Banco extractos 01/10/2026 al 02/10/2026


### `al_l10n_pe_batch_payment`

#### ✅ Lote de pagos a 3 proveedores → TXT del BCP

**Pasos en pantalla:** Proveedores → Pagos: 3 pagos con método «TXT banco» → Crear lote → Validar → Descargar archivo.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | el diario ofrece el método de pago masivo pe_bank_txt |  |
| ✅ | archivo TXT generado | BCP_PEN_Q1BCP_BATCH-OUT-2026-0001.txt |
| ✅ | cabecera + 3 abonos | esperado 4, obtenido 4 |
| ✅ | cabecera: tipo 1 y 3 abonos | esperado '1000003', obtenido '1000003' |
| ✅ | total 1 330,50 en la cabecera | 100000320261030C00011919912345071       00000000001330.50BAT |
| ✅ | longitud de cabecera BCP proveedores | esperado 113, obtenido 113 |
| ✅ | mismo banco: abono a cuenta BCP | 2C1937654321022      |
| ✅ | otro banco: abono por CCI | 2B01145600020009876512162 |
| ✅ | longitud de detalle BCP | esperado 196, obtenido 196 |
| ✅ | conteo y total del lote | esperado (3, 1330.5), obtenido (3, 1330.5) |
| ✅ | nombre del archivo | BCP_PEN_Q1BCP_BATCH-OUT-2026-0001.txt |
| ✅ | proveedor de otro banco sin CCI se rechaza | RedirectWarning: ('Cuentas de otro banco sin CCI de 20 dígitos.\nUn proveedor con cuenta en otro ban |

**Registros:** `account.journal/6064` QA20 P1 BCP soles masivo, `account.payment/1343` PQ1BCP/2026/00001, `account.payment/1344` PQ1BCP/2026/00002, `account.payment/1345` PQ1BCP/2026/00003, `account.batch.payment/45` BATCH/OUT/2026/0001 (Enviado)


### `al_l10n_pe_treasury`

#### ✅ Posición diaria: saldo contable, en tránsito y disponible

**Pasos en pantalla:** Tesorería → Posición diaria → Nuevo (fecha, banco); revisar saldo, tránsito y disponible.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | saldo contable | esperado 10000.0, obtenido 10000.0 |
| ✅ | pago confirmado sin conciliar en tránsito | esperado -1500.0, obtenido -1500.0 |
| ✅ | saldo proyectado | esperado 8500.0, obtenido 8500.0 |
| ✅ | disponible = proyectado − mínimo + sobregiro | esperado 10000.0, obtenido 10000.0 |

**Registros:** `account.move/31303` MISC/2026/10/0003 (QA20 P1 saldo inicial), `res.partner/9414` QA20 P1 Proveedor tesorería SAC, `account.payment/1347` PQ1TP/2026/00001, `l10n_pe.treasury.position/34` Posición al 16/10/2026

#### ✅ Transferencia entre bancos y compra de US$ a T.C. oficial (pérdida)

**Pasos en pantalla:** Tesorería → Transferencias → Nuevo: de soles a soles S/ 5 000; otra de soles a dólares a 3,75 valorizada oficial; Confirmar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | misma moneda: no es cambio |  |
| ✅ | transferencia realizada (sin umbral de aprobación) | esperado 'done', obtenido 'done' |
| ✅ | por la cuenta de transferencias | esperado account.account(15323,), obtenido account.account(15323,) |
| ✅ | cuenta de transferencias conciliada |  |
| ✅ | compra de dólares | esperado 'buy', obtenido 'buy' |
| ✅ | US$ recibidos | esperado 1000.0, obtenido 1000.0 |
| ✅ | diferencia de cambio (T.C. oficial 3.7) | esperado -50.0, obtenido -50.0 |
| ✅ | asiento de diferencia de cambio |  |
| ✅ | cuenta de transferencias saldada | esperado 0.0, obtenido 0.0 |

**Registros:** `l10n_pe.treasury.transfer/49` TRF/2026/0049, `l10n_pe.treasury.transfer/50` TRF/2026/0050, `account.move/31309` CAMBIO/2026/10/0003 (Diferencia de cambio TRF/2026/0050)

#### ✅ Programación de pagos: proponer, aprobar y pagar

**Pasos en pantalla:** Tesorería → Programación de pagos → Nuevo → Proponer (vence al 31/10, proveedores) → Enviar → Aprobar → Pagar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | propone lo vencido al 31/10, no la de diciembre | esperado account.move(31310, 31311, 31312), obtenido account.move(31312, 31310, 31311) |
| ✅ | total programado | esperado 2100.0, obtenido 2100.0 |
| ✅ | dos proveedores | esperado 2, obtenido 2 |
| ✅ | días de atraso al 16/10 | esperado 6, obtenido 6 |
| ✅ | sin umbral configurado requiere aprobación | esperado 'to_approve', obtenido 'to_approve' |
| ✅ | quien prepara no puede aprobar | Quien prepara la programación no puede aprobarla. |
| ✅ | aprobada | esperado 'approved', obtenido 'approved' |
| ✅ | la posición refleja lo programado aprobado | esperado 2100.0, obtenido 2100.0 |
| ✅ | programación pagada | esperado 'paid', obtenido 'paid' |
| ✅ | un pago por proveedor | esperado 2, obtenido 2 |
| ✅ | facturas pagadas |  |

**Registros:** `res.partner/9415` QA20 P1 Proveedor plan Uno, `res.partner/9416` QA20 P1 Proveedor plan Dos, `account.move/31310` Q1CP/2026/10/0005, `account.move/31311` Q1CP/2026/10/0006, `account.move/31312` Q1CP/2026/10/0007, `account.move/31313` Q1CP/2026/10/0008, `l10n_pe.treasury.payment.plan/70` PRG/2026/0070, `account.payment/1352` PQ1TP/2026/00004, `account.payment/1353` PQ1TP/2026/00005


### `al_l10n_pe_treasury_batch_payment`

#### ✅ Programación pagada con método TXT genera lote y archivo del banco

**Pasos en pantalla:** Programación de pagos en banco BCP con método «TXT banco» → Pagar → Abrir lote → Validar → Descargar TXT.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | propone las dos facturas | esperado account.move(31316, 31317), obtenido account.move(31317, 31316) |
| ✅ | se creó el lote bancario |  |
| ✅ | el lote contiene los pagos de la programación | esperado account.payment(1354, 1355), obtenido account.payment(1354, 1355) |
| ✅ | pagos con el método TXT | esperado account.payment.method.line(10096,), obtenido account.payment.method.line(10096,) |
| ✅ | TXT BCP con cabecera de 2 abonos | ['100000220261030C00011919912345071       00000000001250.00BATCHOUT20260003                        N000013245678104'] |
| ✅ | total S/ 1 250,00 en el TXT |  |

**Registros:** `res.partner/9417` QA20 P1 Proveedor lote Uno, `res.partner/9418` QA20 P1 Proveedor lote Dos, `account.move/31316` Q1CP/2026/10/0009, `account.move/31317` Q1CP/2026/10/0010, `l10n_pe.treasury.payment.plan/71` PRG/2026/0071, `account.batch.payment/47` BATCH/OUT/2026/0003 (Enviado)


### `al_l10n_pe_check`

#### ✅ Cheque de terceros: recepción en cartera, aviso de plazo y depósito

**Pasos en pantalla:** Contabilidad → Clientes → Pagos: nuevo cobro en «Cheques de terceros» con método «Nuevos cheques de terceros»; luego Cheques → seleccionar → Transferir al banco.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | el cheque queda en el diario de cartera | esperado 'CHQT', obtenido 'CHQT' |
| ✅ | RUC del girador tomado del cliente | esperado '20612090310', obtenido '20612090310' |
| ✅ | débito en 1033001 Cheques de terceros en cartera | esperado 1180.0, obtenido 1180.0 |
| ✅ | plazo de presentación = 30 días | esperado datetime.date(2026, 11, 19), obtenido datetime.date(2026, 11, 19) |
| ✅ | aviso de plazo vencido solo para el cheque viejo | El cheque 00912346 venció su plazo de presentación el 10/10/2026 (30 días): el banco puede rechazarlo. |
| ✅ | depositado: el cheque pasa al banco | esperado account.journal(6069,), obtenido account.journal(6069,) |
| ✅ | operaciones del cheque: recepción + depósito | esperado 2, obtenido 2 |
| ✅ | RUC de girador inválido rechazado | El documento del emisor del cheque 00912345 no es válido: RUC de 11 dígitos, DNI de 8 o carné de extranjería. |

**Registros:** `res.partner/9419` QA20 P2 Cliente cheques, `account.payment/1356` PCHQT/2026/00001, `l10n_latam.check/50` 00912345, `l10n_latam.check/51` 00912346

#### ✅ Cheque propio girado a proveedor

**Pasos en pantalla:** Contabilidad → Proveedores → Pagos: nuevo pago desde el banco con método «Cheques propios».

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | el banco QA tiene el método «Cheques propios» | ['Cheques propios'] |
| ✅ | cuenta de cheques girados 1049001 | esperado '1049001', obtenido '1049001' |
| ✅ | cheque entregado | esperado 'handed', obtenido 'handed' |
| ✅ | pendiente en 1049001 hasta el cobro | esperado '1049001', obtenido '1049001' |

**Registros:** `res.partner/9420` QA20 P2 Proveedor cheques, `account.payment/1360` PQ2BK/2026/00002, `l10n_latam.check/52` 00001021


### `al_l10n_pe_check_printing`

#### ✅ Formato de chequera e impresión del cheque propio

**Pasos en pantalla:** Contabilidad → Configuración → Formatos de cheque: crear formato, asignarlo al banco; en el pago con cheque propio → Imprimir cheque.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | formato de papel = tamaño de la chequera | esperado ('custom', 170, 75), obtenido ('custom', 170, 75) |
| ✅ | importe en letras | esperado 'MIL DOSCIENTOS CINCUENTA Y 00/100 SOLES', obtenido 'MIL DOSCIENTOS CINCUENTA Y 00/100 SOLES' |
| ✅ | importe con relleno | esperado 'S/ ******1,250.00', obtenido 'S/ ******1,250.00' |
| ✅ | acción de impresión | esperado 'al_l10n_pe_check_printing.report_check', obtenido 'al_l10n_pe_check_printing.report_check' |
| ✅ | el cheque impreso contiene «QA20 P2 PROVEEDOR IMPRESION SAC» |  |
| ✅ | el cheque impreso contiene «S/ ******1,250.00» |  |
| ✅ | el cheque impreso contiene «MIL DOSCIENTOS CINCUENTA Y 00/100 SOLES» |  |
| ✅ | el cheque impreso contiene «Lima, 21 de octubre de 2026» |  |
| ✅ | el cheque impreso contiene «Pagar desde: 20 de noviembre de 2026» |  |
| ✅ | hoja de prueba de alineación |  |
| ⏭️ | PDF del cheque (wkhtmltopdf) | el shell corre con --no-http; se valida el HTML del reporte |

**Registros:** `l10n_pe.check.layout/7` QA20 P2 Chequera, `res.partner/9421` QA20 P2 PROVEEDOR IMPRESION, `account.payment/1361` PQ2BK/2026/00003


### `al_l10n_pe_collection`

#### ✅ Cartera vencida, gestión con compromiso de pago y cumplimiento

**Pasos en pantalla:** Cobranza → Cartera: ver la factura vencida; Registrar gestión (llamada, «Promete pagar»); registrar el cobro y evaluar el compromiso.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | días de atraso en la cartera | esperado 40, obtenido 40 |
| ✅ | tramo de antigüedad | esperado '31 a 60 días', obtenido '31 a 60 días' |
| ✅ | saldo en cartera | esperado 1000.0, obtenido 1000.0 |
| ✅ | compromiso pendiente por 600 | esperado (600.0, 'pending'), obtenido (600.0, 'pending') |
| ✅ | actividad de seguimiento programada |  |
| ✅ | compromiso cumplido antes de su fecha | esperado 'kept', obtenido 'kept' |
| ✅ | importe cobrado del compromiso | esperado 600.0, obtenido 600.0 |

**Registros:** `res.partner/9422` QA20 P2 Cliente cobranza, `account.move/31326` Q2VT/2026/00001, `l10n_pe.collection.action/129` Llamada · QA20 P2 Cliente cobranza · 30/10/2026, `l10n_pe.collection.promise/145` CP/2026/00145, `account.payment/1362` PQ2BK/2026/00004

#### ✅ Interés moratorio y nota de débito

**Pasos en pantalla:** Cobranza → Intereses: asistente de intereses para el cliente → crear nota de débito.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | días de mora | esperado 36, obtenido 36 |
| ✅ | interés 1000 × (1.12^(36/360) − 1) | esperado 11.4, obtenido 11.4 |
| ✅ | una línea de interés | esperado 1, obtenido 1 |
| ✅ | nota de débito en borrador | esperado 'draft', obtenido 'draft' |
| ✅ | nota de débito referida a la factura | esperado account.move(31328,), obtenido account.move(31328,) |
| ✅ | base de la nota de débito | esperado 11.4, obtenido 11.4 |
| ✅ | facturado el interés, no se vuelve a calcular | esperado 0.0, obtenido 0.0 |

**Registros:** `res.partner/9423` QA20 P2 Cliente intereses, `account.move/31328` Q2VT/2026/00002, `account.move/31329` Borrador de factura (Intereses moratorios de Q2VT/2026/00002

#### ✅ Calificación del deudor y bloqueo automático por mora

**Pasos en pantalla:** Cobranza → Clientes: recalcular calificación; el cliente moroso queda bloqueado; el jefe lo libera.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | compromiso incumplido | esperado 'broken', obtenido 'broken' |
| ✅ | calificación C/D | D |
| ✅ | máximo atraso | esperado 130, obtenido 130 |
| ✅ | bloqueo automático | esperado 'auto', obtenido 'auto' |
| ✅ | cliente bloqueado |  |
| ✅ | liberado por el jefe de cobranza | esperado 'released', obtenido 'released' |

**Registros:** `res.partner/9424` QA20 P2 Cliente moroso, `account.move/31330` Q2VT/2026/00003, `l10n_pe.collection.promise/146` CP/2026/00146, `l10n_pe.collection.promise/147` CP/2026/00147, `l10n_pe.collection.promise/148` CP/2026/00148


### `al_l10n_pe_collection_sale`

#### ✅ Pedido de venta bloqueado por crédito y liberado

**Pasos en pantalla:** Cobranza → Clientes → Bloquear crédito; Ventas → pedido → Confirmar (rechazado); liberar y confirmar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | aviso de bloqueo en el pedido | QA20 P2 Cliente bloqueado venta tiene el crédito bloqueado por cobranza: no se puede confirmar el pedido hasta que regularice su deuda o el administrador de cobranza lo libere. |
| ✅ | confirmación rechazada por bloqueo | No se puede confirmar S00280: QA20 P2 Cliente bloqueado venta tiene el crédito bloqueado por cobranza. |
| ✅ | sin aviso tras liberar |  |
| ✅ | pedido confirmado tras liberar | esperado 'sale', obtenido 'sale' |

**Registros:** `res.partner/9425` QA20 P2 Cliente bloqueado venta, `product.product/13825` QA20 P2 Producto venta, `sale.order/280` S00280


### `al_l10n_pe_bank_collection`

#### ✅ Archivo de deudores BCP (CREP)

**Pasos en pantalla:** Tesorería → Recaudación → Lotes de deudores: nuevo lote, Cargar documentos → Generar archivo.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | documentos en el lote (excluye el que vence después) | esperado 2, obtenido 2 |
| ✅ | total del lote | esperado 1334.56, obtenido 1334.56 |
| ✅ | lote generado | esperado 'generated', obtenido 'generated' |
| ✅ | nombre del archivo CREP | CREP_0_20261030.txt |
| ✅ | cabecera + 2 detalles | esperado 3, obtenido 3 |
| ✅ | registros de 250 posiciones |  |
| ✅ | cabecera: sucursal/moneda/cuenta | esperado 'CC19101234567', obtenido 'CC19101234567' |
| ✅ | cabecera: cantidad de registros | esperado '000000002', obtenido '000000002' |
| ✅ | cabecera: importe total | esperado '000000000133456', obtenido '000000000133456' |
| ✅ | detalle: código de depositante = RUC | esperado '20612090387', obtenido '20612090387' |
| ✅ | detalle: nombre en ASCII | esperado 'QA20 P2 COMPANIA NANDU SAC', obtenido 'QA20 P2 COMPANIA NANDU SAC' |
| ✅ | detalle: número de documento | esperado 'Q2VT/2026/00004', obtenido 'Q2VT/2026/00004' |
| ✅ | detalle: importe | esperado '000000000123456', obtenido '000000000123456' |

**Registros:** `l10n_pe.bank.collection.agreement/14` QA20 P2 BCP soles, `res.partner/9426` QA20 P2 CLIENTE ÑANDÚ, `res.partner/9427` QA20 P2 Cliente recaudo 2, `account.move/31331` Q2VT/2026/00004, `account.move/31332` Q2VT/2026/00005, `account.move/31333` Q2VT/2026/00006, `l10n_pe.bank.collection.batch/31` REC/ENV/2026/0031

#### ✅ Importar respuesta del banco y aplicar cobros

**Pasos en pantalla:** Tesorería → Recaudación → Respuestas: subir el archivo de abonos → Importar → Procesar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | abono 1 casado con el documento | esperado ('matched', res.partner(9428,)), obtenido ('matched', res.partner(9428,)) |
| ✅ | abono 2 casado por cliente (ceros a la izquierda) | esperado 'partner', obtenido 'partner' |
| ✅ | respuesta procesada | esperado 'done', obtenido 'done' |
| ✅ | factura con documento cobrada | in_payment |
| ✅ | memo del cobro lleva la operación | Recaudación QA20 P2 Banco op. 552001 |
| ✅ | abono sin documento paga primero la más antigua |  |
| ✅ | saldo de la reciente | esperado 200.0, obtenido 200.0 |
| ✅ | reimportar el mismo archivo: duplicados | esperado {'duplicate'}, obtenido {'duplicate'} |

**Registros:** `l10n_pe.bank.collection.agreement/14` QA20 P2 BCP soles, `res.partner/9428` QA20 P2 Cliente abono 1, `res.partner/9429` QA20 P2 Cliente abono 2, `account.move/31334` Q2VT/2026/00007, `account.move/31335` Q2VT/2026/00008, `account.move/31336` Q2VT/2026/00009, `l10n_pe.bank.collection.response/34` REC/RSP/2026/0034, `account.payment/1363` PQ2BK/2026/00005, `account.payment/1364` PQ2BK/2026/00006


### `al_l10n_pe_account_letter`

#### ✅ Canje de factura en 2 letras y descuento bancario

**Pasos en pantalla:** Contabilidad → Letras → Canjes: nuevo canje, Verificar, Crear letras, Canjear; Enviar al banco (descuento); Liquidar descuento; Cobro del banco.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | cuentas de letras de la compañía | 4511000 / 6734000 / 6391000 |
| ✅ | canje en estado Canjeado | esperado 'redeemed', obtenido 'redeemed' |
| ✅ | dos letras | esperado 2, obtenido 2 |
| ✅ | las letras suman la factura | esperado 1000.0, obtenido 1000.0 |
| ✅ | el canje carga las letras en cartera | 1232000 → ['1232000'] |
| ✅ | canje Bancarizado al enviar todas las letras | esperado 'banked', obtenido 'banked' |
| ✅ | asiento del envío con la fecha del envío | esperado datetime.date(2026, 10, 10), obtenido datetime.date(2026, 10, 10) |
| ✅ | neto abonado por el banco | esperado 965.0, obtenido 965.0 |
| ✅ | banco neto | esperado 965.0, obtenido 965.0 |
| ✅ | interés 6734 | esperado 30.0, obtenido 30.0 |
| ✅ | comisión 6391 | esperado 5.0, obtenido 5.0 |
| ✅ | préstamo 4511 | esperado -1000.0, obtenido -1000.0 |
| ✅ | descontada sigue pendiente | esperado {'pending'}, obtenido {'pending'} |
| ✅ | letras cobradas | esperado {'paid'}, obtenido {'paid'} |
| ✅ | préstamo cancelado | esperado 0.0, obtenido 0.0 |

**Registros:** `res.partner/9430` QA20 P2 Cliente letras, `account.move/31339` Q2VT/2026/00010, `l10n_pe.letter/123` CLC00129, `l10n_pe.letter.line/192` QA20-P2-123-001, `l10n_pe.letter.line/193` QA20-P2-123-002, `account.move/31342` Q2BK/2026/00001 (Liquidación del descuento CLC00129), `account.move/31343` Q2BK/2026/00002 (Cobro de la letra QA20-P2-123-001), `account.move/31344` Q2BK/2026/00003 (Cobro de la letra QA20-P2-123-002)

#### ✅ Letra en cobranza libre cobrada por el banco

**Pasos en pantalla:** Canje → Enviar al banco (cobranza libre) → Operación bancaria «Cobrada» con comisión.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | letra en cobranza libre | esperado {'billing'}, obtenido {'billing'} |
| ✅ | letra en el banco: el pago directo se bloquea |  |
| ✅ | neto cobrado | esperado 993.0, obtenido 993.0 |
| ✅ | banco | esperado 993.0, obtenido 993.0 |
| ✅ | letra cobrada | esperado 'paid', obtenido 'paid' |
| ✅ | restablecer a borrador bloqueado con operaciones |  |

**Registros:** `res.partner/9431` QA20 P2 Cliente letras cobranza, `account.move/31345` Q2VT/2026/00011, `l10n_pe.letter/124` CLC00130, `account.move/31348` Q2BK/2026/00004 (Cobro de la letra QA20-P2-124-001)


### `al_l10n_pe_factoring`

#### ✅ Factoring sin recurso: cesión, desembolso y liquidación

**Pasos en pantalla:** Contabilidad → Factoring → Operaciones: nueva operación con la factura, Ceder → Desembolsar → Liquidar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | adelanto 90 % y retenido 10 % | esperado (900.0, 100.0), obtenido (900.0, 100.0) |
| ✅ | cedida | esperado 'assigned', obtenido 'assigned' |
| ✅ | sin recurso la factura se da de baja | paid |
| ✅ | deuda pasa al factor | esperado 1000.0, obtenido 1000.0 |
| ✅ | neto desembolsado | esperado 865.0, obtenido 865.0 |
| ✅ | banco recibe el neto | esperado 865.0, obtenido 865.0 |
| ✅ | interés | esperado 20.0, obtenido 20.0 |
| ✅ | operación liquidada | esperado 'done', obtenido 'done' |
| ✅ | cuenta del factor saldada | esperado 0.0, obtenido 0.0 |
| ✅ | banco total (neto + retenido) | esperado 965.0, obtenido 965.0 |
| ✅ | asiento Cesión de facturas FAC/2026/0194 cuadra |  |
| ✅ | asiento Desembolso del factor FAC/2026/0194 cuadra |  |
| ✅ | asiento Cobro del factor FAC/2026/0194 cuadra |  |

**Registros:** `res.partner/9432` QA20 P2 Cliente factoring, `res.partner/9433` QA20 P2 Factor capital, `account.move/31349` Q2VT/2026/00012, `l10n_pe.factoring/194` FAC/2026/0194, `account.move/31350` Q2FG/2026/10/0001 (Cesión de facturas FAC/2026/0194), `account.move/31351` Q2BK/2026/00005 (Desembolso del factor FAC/2026/0194), `account.move/31352` Q2BK/2026/00006 (Cobro del factor FAC/2026/0194)

#### ✅ Factoring con recurso y anotación en CAVALI (servicio simulado)

**Pasos en pantalla:** Factura → Registrar en CAVALI; Factoring con recurso: Ceder (transferencia CAVALI) → Desembolsar → Liquidar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | URL de registro CAVALI | esperado 'https://cavali.test/api/facturas/registro', obtenido 'https://cavali.test/api/facturas/registro' |
| ✅ | payload: monto neto pendiente | esperado 2000.0, obtenido 2000.0 |
| ✅ | payload: RUC del adquirente | esperado '20612090468', obtenido '20612090468' |
| ✅ | factura negociable anotada | esperado ('registered', 'AN-QA20'), obtenido ('registered', 'AN-QA20') |
| ✅ | credenciales fuera del log |  |
| ✅ | transferencia CAVALI | esperado 'https://cavali.test/api/facturas/transferencia', obtenido 'https://cavali.test/api/facturas/transferencia' |
| ✅ | factura transferida | esperado 'transferred', obtenido 'transferred' |
| ✅ | con recurso no se da de baja (NIIF 9) | esperado 'not_paid', obtenido 'not_paid' |
| ✅ | obligación con el factor | esperado -1600.0, obtenido -1600.0 |
| ✅ | pago informado a CAVALI | esperado 2000.0, obtenido 2000.0 |
| ✅ | operación liquidada | esperado 'done', obtenido 'done' |
| ✅ | el cobro del factor cancela la factura |  |
| ✅ | banco: adelanto 1570 + retenido 400 | esperado 1970.0, obtenido 1970.0 |
| ⏭️ | CAVALI real | sin credenciales de prueba: servicio simulado con mock |

**Registros:** `res.partner/9434` QA20 P2 Cliente factoring recurso, `res.partner/9435` QA20 P2 Factor recurso, `account.move/31353` Q2VT/2026/00013, `l10n_pe.cavali.log/39` l10n_pe.cavali.log,39, `l10n_pe.factoring/195` FAC/2026/0195, `account.move/31354` Q2BK/2026/00007 (Desembolso del factor FAC/2026/0195), `account.move/31355` Q2BK/2026/00008 (Cobro del factor FAC/2026/0195), `account.move/31356` Q2FG/2026/10/0002 (Devengo de intereses FAC/2026/0195)


### `al_l10n_pe_cash_fund`

#### ✅ Entrega a rendir: rendición con movilidad, devolución y cierre

**Pasos en pantalla:** Contabilidad → Entregas a rendir → Nuevo: aprobar, entregar, registrar rendición con factura y planilla de movilidad, registrar la devolución del saldo y cerrar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Número con prefijo ER/ | ER/2026/0017 |
| ✅ | Fondo abierto y entregado | esperado ('open', 500.0, 500.0), obtenido ('open', 500.0, 500.0) |
| ✅ | Exceso de movilidad sobre el tope 4 % RMV (45,20/día) | esperado 9.8, obtenido 9.8 |
| ✅ | La factura queda pagada con la rendición | esperado 'paid', obtenido 'paid' |
| ✅ | Planilla de movilidad numerada | PM/2026/00008 |
| ✅ | Asiento de rendición publicado | esperado 'posted', obtenido 'posted' |
| ✅ | Saldo por devolver 500 − 300 − 55 | esperado 145.0, obtenido 145.0 |
| ✅ | No permite cerrar con saldo pendiente | El fondo ER/2026/0017 · QA20 P3 Trabajador ER tiene un saldo de S/ 145.00: registre la dev |
| ✅ | Saldo cero tras la devolución | esperado 0.0, obtenido 0.0 |
| ✅ | Fondo cerrado | esperado 'closed', obtenido 'closed' |
| ✅ | Cuenta del fondo conciliada al cerrar |  |
| ✅ | PDF de planilla de movilidad generado |  |

**Registros:** `res.partner/9436` QA20 P3 Trabajador ER, `res.partner/9437` QA20 P3 Grifo ER, `l10n_pe.cash.fund/29` ER/2026/0017 · QA20 P3 Trabajador ER, `account.move/31358` F F001-00930001, `l10n_pe.cash.settlement/27` Rendición de ER/2026/0017 · QA20 P3 Trabajador ER, `account.move/31359` MISC/2026/10/0004 (Rendición de ER/2026/0017 · Visita a obra, `account.payment/1366` PBNK1/2026/00002

#### ✅ Caja chica: gasto y reposición; reembolso de entrega excedida

**Pasos en pantalla:** Contabilidad → Caja chica → Nuevo: rendir una factura y reponer el fondo; en una entrega a rendir con gasto mayor, registrar el reembolso al trabajador.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Número con prefijo CCH/ | CCH/013 |
| ✅ | Saldo de caja chica tras el gasto | esperado 600.0, obtenido 600.0 |
| ✅ | Reposición por lo gastado | esperado (400.0, 'replenishment'), obtenido (400.0, 'replenishment') |
| ✅ | Caja chica repuesta al monto fijo | esperado 1000.0, obtenido 1000.0 |
| ✅ | Saldo a favor del trabajador | esperado -50.0, obtenido -50.0 |
| ✅ | Reembolso de salida por 50 | esperado ('outbound', 50.0), obtenido ('outbound', 50.0) |
| ✅ | Entrega con reembolso cerrada | esperado 'closed', obtenido 'closed' |

**Registros:** `res.partner/9438` QA20 P3 Cajera CCH, `res.partner/9439` QA20 P3 Librería CCH, `l10n_pe.cash.fund/30` CCH/013 · QA20 P3 Cajera CCH, `l10n_pe.cash.settlement/28` REN/2026/0026, `account.payment/1368` PBNK1/2026/00004, `l10n_pe.cash.fund/31` ER/2026/0018 · QA20 P3 Cajera CCH, `account.payment/1370` PBNK1/2026/00006


### `al_l10n_pe_cash_fund_expense`

#### ✅ Gasto de empleado pagado con caja chica → factura de proveedor

**Pasos en pantalla:** Gastos → Nuevo gasto con comprobante (boleta) y caja chica; enviar, aprobar y contabilizar: se genera la factura del proveedor pagada con la rendición del fondo.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Diario de compras con documentos para gastos | Compras |
| ✅ | El gasto se contabiliza como factura de proveedor | esperado 'in_invoice', obtenido 'in_invoice' |
| ✅ | Proveedor del comprobante | esperado res.partner(9441,), obtenido res.partner(9441,) |
| ✅ | Tipo de documento boleta (03) | esperado l10n_latam.document.type(2,), obtenido l10n_latam.document.type(2,) |
| ✅ | Número del comprobante en la factura | R B010-00095725 |
| ✅ | Importe de la factura | esperado 32.0, obtenido 32.0 |
| ✅ | Factura pagada por la caja chica | esperado 'paid', obtenido 'paid' |
| ✅ | Gasto pagado | esperado 'paid', obtenido 'paid' |
| ✅ | Saldo de caja chica descontado | esperado 443.35, obtenido 443.35 |
| ✅ | Una rendición publicada para ambos gastos | esperado (1, 'posted'), obtenido (1, 'posted') |
| ✅ | Exige número de comprobante | El gasto «Almuerzo del personal» se paga con el fondo CCH/014 · QA20 P3 Empleado gastos: l |

**Registros:** `res.partner/9440` QA20 P3 Empleado gastos, `res.partner/9441` QA20 P3 Restaurante gastos, `hr.employee/931` QA20 P3 Empleado gastos, `product.product/13826` QA20 P3 Almuerzo del personal, `l10n_pe.cash.fund/32` CCH/014 · QA20 P3 Empleado gastos, `hr.expense/16` Almuerzo del personal, `hr.expense/17` Almuerzo del personal, `account.move/31371` R B010-00095725 (Almuerzo del personal), `account.move/31372` R B010-00095726 (Almuerzo del personal), `l10n_pe.cash.settlement/30` REN/2026/0028


### `al_l10n_pe_cash_closing`

#### ✅ Cierre de caja con faltante: saldo según libros, arqueo y asiento de diferencia

**Pasos en pantalla:** Contabilidad → Cierres de caja → Nuevo (caja, día): revisar ingresos/egresos del día, registrar el arqueo por denominaciones y cerrar; imprimir el PDF.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Saldo inicial según libros | esperado 1000.0, obtenido 1000.0 |
| ✅ | Ingresos del día (contado 500 + cobranza 200) | esperado 700.0, obtenido 700.0 |
| ✅ | Egresos del día | esperado 100.0, obtenido 100.0 |
| ✅ | Saldo final según libros | esperado 1600.0, obtenido 1600.0 |
| ✅ | Venta al contado clasificada | esperado ('collection', 'cash'), obtenido ('collection', 'cash') |
| ✅ | Cobranza de venta al crédito clasificada | esperado ('collection', 'credit'), obtenido ('collection', 'credit') |
| ✅ | Denominaciones vigentes precargadas | [0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0] |
| ✅ | Exige arqueo antes de cerrar | Registre el arqueo: cuente los billetes y monedas de la caja. |
| ✅ | Faltante de 10 en el arqueo | esperado -10.0, obtenido -10.0 |
| ✅ | Caja cerrada | esperado 'closed', obtenido 'closed' |
| ✅ | Asiento de diferencia publicado | esperado 'posted', obtenido 'posted' |
| ✅ | Faltante a la cuenta de pérdida de la caja | esperado 10.0, obtenido 10.0 |
| ✅ | Día cerrado bloquea nuevos pagos | La caja QA20 P3 Caja tienda está cerrada hasta el 20/10/2026 (CC/2026/00041): no |
| ✅ | El día siguiente parte de lo arqueado | esperado 1590.0, obtenido 1590.0 |
| ✅ | PDF de cierre con faltante y resumen por categoría |  |

**Registros:** `account.journal/6072` QA20 P3 Caja tienda, `account.journal/6073` QA20 P3 Ventas caja, `res.partner/9442` QA20 P3 Cliente caja, `account.payment/1372` PQ3CJ/2026/00001, `account.payment/1375` PQ3CJ/2026/00004, `account.move/31376` Q3VC/2026/00001, `account.move/31377` Q3VC/2026/00002, `l10n_pe.cash.closing/41` CC/2026/00041, `account.move/31381` Q3CJ/2026/00001 (Faltante de caja CC/2026/00041), `l10n_pe.cash.closing/42` CC/2026/00042

#### ✅ Reapertura del cierre: anula la diferencia y desbloquea el día

**Pasos en pantalla:** Cierres de caja → abrir el cierre posterior → Reabrir: el asiento de diferencia se anula y se puede volver a registrar movimientos.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Faltante del día 2 contabilizado |  |
| ✅ | Cierre reabierto | esperado 'open', obtenido 'open' |
| ✅ | Asiento de diferencia anulado al reabrir | esperado 'cancel', obtenido 'cancel' |
| ✅ | Libros recalculados tras la reapertura | esperado 1650.0, obtenido 1650.0 |

**Registros:** `account.payment/1377` PQ3CJ/2026/00005, `account.payment/1378` PQ3CJ/2026/00006, `l10n_pe.cash.closing/42` CC/2026/00042, `account.move/31384` Q3CJ/2026/00002 (Faltante de caja CC/2026/00042)


### `al_payment_culqi`

#### ✅ Proveedor Culqi en prueba: valores del checkout, payload del cargo y cargo simulado

**Pasos en pantalla:** Contabilidad → Configuración → Proveedores de pago → Culqi: llaves de prueba; el cliente paga con tarjeta en el portal (cargo simulado con mock).

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Monedas PEN/USD | esperado ['PEN', 'USD'], obtenido ['PEN', 'USD'] |
| ✅ | Soporta devolución parcial | esperado 'partial', obtenido 'partial' |
| ✅ | Cabecera con la llave secreta | esperado 'Bearer sk_test_qa2000000000', obtenido 'Bearer sk_test_qa2000000000' |
| ✅ | Llaves de prueba no sirven en producción | La llave pública de Culqi debe empezar con «pk_live_» en este modo. |
| ✅ | Valores del checkout en céntimos | esperado (12050, 'PEN', 'tarjeta'), obtenido (12050, 'PEN', 'tarjeta') |
| ✅ | La llave secreta no llega al navegador |  |
| ✅ | Payload del cargo | esperado (12050, 'PEN', 'tkn_test_QA20P3', 'PE'), obtenido (12050, 'PEN', 'tkn_test_QA20P3', 'PE') |
| ✅ | Solo campos 3DS permitidos | {'eci': '05', 'xid': 'X'} |
| ✅ | Llamada al endpoint charges (mock) | esperado ('POST', 'charges'), obtenido ('POST', 'charges') |
| ✅ | Transacción confirmada | esperado ('done', 'chr_test_QA20P3'), obtenido ('done', 'chr_test_QA20P3') |
| ✅ | Cargo con importe distinto se rechaza | esperado 'error', obtenido 'error' |
| ⏭️ | Cargo real contra api.culqi.com | sin credenciales de prueba |

**Registros:** `payment.provider/4691` QA20 P3 Culqi, `res.partner/9443` QA20 P3 Cliente pasarela, `payment.transaction/303` QA20-P3-CULQI-124107000000, `payment.transaction/304` QA20-P3-CULQI2-124107000000


### `al_payment_izipay`

#### ✅ Proveedor Izipay en prueba: formToken, firma de la IPN y confirmación

**Pasos en pantalla:** Proveedores de pago → Izipay: tienda y contraseña de prueba; el cliente paga en el formulario incrustado y llega la IPN firmada (simulada).

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Autenticación básica tienda/contraseña | esperado ('89289758', 'testpassword_qa2000000000'), obtenido ('89289758', 'testpassword_qa2000000000') |
| ✅ | URL de IPN | http://127.0.0.1:20003/payment/izipay/webhook |
| ✅ | Payload CreatePayment | esperado (12050, 'PEN', {'odoo_reference': 'QA20-P3-IZI-124107000000'}), obtenido (12050, 'PEN', {'odoo_reference': 'QA20-P3-IZI-124107000000'}) |
| ✅ | RUC del cliente en el payload | esperado '20131312955', obtenido '20131312955' |
| ✅ | formToken al navegador | esperado 'QA20FORMTOKEN', obtenido 'QA20FORMTOKEN' |
| ✅ | La contraseña no llega al navegador |  |
| ✅ | Firma HMAC-SHA256 de la IPN válida |  |
| ✅ | IPN con firma alterada rechazada |  |
| ✅ | La IPN ubica la transacción por metadata | esperado 'QA20-P3-IZI-124107000000', obtenido 'QA20-P3-IZI-124107000000' |
| ✅ | Transacción confirmada por la IPN | esperado ('done', 'qa20p3uuid0000000000000000000001'), obtenido ('done', 'qa20p3uuid0000000000000000000001') |
| ⏭️ | Llamada real a api.micuentaweb.pe | sin credenciales de prueba |

**Registros:** `payment.provider/4692` QA20 P3 Izipay, `res.partner/9444` QA20 P3 Cliente pasarela, `payment.transaction/305` QA20-P3-IZI-124107000000


### `al_payment_niubiz`

#### ✅ Proveedor Niubiz en prueba: autorización aprobada y rechazada (mock)

**Pasos en pantalla:** Proveedores de pago → Niubiz: comercio y llaves de integración; el cliente paga con tarjeta en el botón de pago (autorización simulada).

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Monedas PEN/USD | esperado ['PEN', 'USD'], obtenido ['PEN', 'USD'] |
| ✅ | Sesión sin teléfono usa 000000000 | esperado '000000000', obtenido '000000000' |
| ✅ | Autorización aprobada confirma la transacción | esperado ('done', '173424', '75'), obtenido ('done', '173424', '75') |
| ✅ | Autorización rechazada → error | esperado 'error', obtenido 'error' |
| ✅ | Mensaje de código 116 traducido | Fondos insuficientes. Por favor use otra tarjeta o intente con otro monto. |
| ⏭️ | Llamada real a la API de Niubiz | sin credenciales de prueba |

**Registros:** `payment.provider/4693` QA20 P3 Niubiz, `res.partner/9445` QA20 P3 Cliente pasarela, `payment.transaction/306` QA20-P3-NBZ-124108000000, `payment.transaction/307` QA20-P3-NBZ2-124108000000


### `al_payment_pagoefectivo`

#### ✅ Proveedor PagoEfectivo en prueba: firma de autorización, CIP y notificación firmada

**Pasos en pantalla:** Proveedores de pago → PagoEfectivo: servicio y claves de prueba; el cliente genera un CIP en el portal y llega la notificación de pago firmada (simulada).

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | URL del entorno de pruebas | esperado 'https://pre1a.services.pagoefectivo.pe/v1/cips', obtenido 'https://pre1a.services.pagoefectivo.pe/v1/cips' |
| ✅ | Token de autorización | esperado 'eyJ.qa20', obtenido 'eyJ.qa20' |
| ✅ | hashString SHA-256 de servicio.clave.secreto.fecha | esperado 'e1a831a2926fded392b238ae21c82cb1cfa2808cc96ae4b111fc866710fbcd43', obtenido 'e1a831a2926fded392b238ae21c82cb1cfa2808cc96ae4b111fc866710fbcd43' |
| ✅ | El secreto no viaja en el payload |  |
| ✅ | Autoriza y genera el CIP | esperado ['authorizations', 'cips'], obtenido ['authorizations', 'cips'] |
| ✅ | Payload del CIP | esperado (120.5, 'PEN', 'QA20-P3-PEF-124108000000', '987654321', '+51'), obtenido (120.5, 'PEN', 'QA20-P3-PEF-124108000000', '987654321', '+51') |
| ✅ | DNI como documento | esperado ('DNI', '45678912'), obtenido ('DNI', '45678912') |
| ✅ | Transacción pendiente con el CIP | esperado ('pending', '2834561'), obtenido ('pending', '2834561') |
| ✅ | Redirección a la URL del CIP | esperado 'https://pre1a.payment.pagoefectivo.pe/PE/Checkout/Cip?token=qa20&lang=es', obtenido 'https://pre1a.payment.pagoefectivo.pe/PE/Checkout/Cip?token=qa20&lang=es' |
| ✅ | Firma PE-Signature sobre JSON compacto aceptada |  |
| ✅ | Notificación con firma inválida rechazada |  |
| ✅ | La notificación ubica la transacción por el CIP | esperado payment.transaction(308,), obtenido payment.transaction(308,) |
| ✅ | CIP pagado confirma la transacción | esperado 'done', obtenido 'done' |
| ⏭️ | Llamada real a services.pagoefectivo.pe | sin credenciales de prueba |

**Registros:** `payment.provider/4694` QA20 P3 PagoEfectivo, `res.partner/9446` QA20 P3 Cliente pasarela, `payment.transaction/308` QA20-P3-PEF-124108000000


### `al_l10n_pe_cash_forecast`

#### ✅ Flujo de caja proyectado: saldo inicial, partidas por vencimiento, escenario y XLSX

**Pasos en pantalla:** Contabilidad → Flujo de caja proyectado → Nuevo: 12 semanas; revisar cobranzas/pagos por semana, mover una partida, agregar una manual y exportar a Excel.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Saldo inicial suma el banco disponible | esperado 10000.0, obtenido 10000.0 |
| ✅ | Fondos restringidos (detracciones) excluidos | esperado 500.0, obtenido 500.0 |
| ✅ | 12 semanas y «Desde…» | esperado 13, obtenido 13 |
| ✅ | Cobranza proyectada | esperado ('receivable', 1200.0), obtenido ('receivable', 1200.0) |
| ✅ | Pago proyectado | esperado ('payable', -800.0), obtenido ('payable', -800.0) |
| ✅ | Vencido se proyecta en el primer periodo |  |
| ✅ | Partida en el periodo de su vencimiento |  |
| ✅ | Saldo final encadenado | esperado -241781.61000000002, obtenido -241781.61 |
| ✅ | Partida editada marcada como escenario |  |
| ✅ | El escenario sobrevive al refrescar | esperado (datetime.date(2026, 12, 14), 600.0, True), obtenido (datetime.date(2026, 12, 14), 600.0, True) |
| ✅ | Partida manual se conserva con periodo |  |
| ✅ | Exporta el flujo a XLSX | QA20 P3 Flujo 12 semanas 2026-10-30.xlsx (12393 bytes) |

**Registros:** `res.partner/9447` QA20 P3 Socio flujo, `account.journal/6074` QA20 P3 Banco flujo, `account.journal/6075` QA20 P3 Detracciones BN, `account.journal/6076` QA20 P3 Ventas flujo, `account.journal/6077` QA20 P3 Compras flujo, `account.move/31386` MISC/2026/10/0008, `account.move/31387` MISC/2026/10/0009, `account.move/31388` Q3VF/2026/00001, `account.move/31389` Q3CF/2026/09/0001, `account.move/31390` Q3VF/2026/00002, `l10n_pe.cash.forecast/33` QA20 P3 Flujo 12 semanas, `ir.attachment/70344` QA20 P3 Flujo 12 semanas 2026-10-30.xlsx


## Fases 2 y 3 · Facturación electrónica y TPV


### `preparacion`

#### ✅ Datos maestros QA20 de la fase (contactos, productos, diarios)

**Pasos en pantalla:** Crear clientes con RUC y DNI, productos y diarios propios para la fase.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | IGV 18 % de ventas del plan pe | IGV 18% |
| ✅ | Cliente RUC: código SUNAT 6 | esperado '6', obtenido '6' |
| ✅ | Cliente DNI (identificador adicional PE_DNI): código SUNAT 1 | esperado ('1', '46027897'), obtenido ('1', '46027897') |
| ✅ | Diario de ventas QV20 con documentos LATAM |  |

**Registros:** `res.partner/9557` QA20 Cliente RUC SAC, `res.partner/9558` QA20 Cliente DNI Rosa Quispe, `product.product/13176` QA20 Servicio de consultoría, `product.product/14000` [QA20-IBU] QA20 Ibuprofeno 400 mg, `account.journal/6113` QA20 Ventas facturación


### `al_l10n_pe_invoice`

#### ✅ Factura electrónica a crédito a cliente RUC: XML, PDF A4/ticket y envío

**Pasos en pantalla:** Crear una factura a 30 días para un cliente con RUC, confirmarla, imprimir A4 y ticket y enviarla a SUNAT.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Tipo de documento 01 (factura) por cliente RUC | esperado '01', obtenido '01' |
| ✅ | Numeración de factura serie F | F FQV-00000001 |
| ✅ | Detalle tributario: base gravada | esperado 1000.0, obtenido 1000.0 |
| ✅ | Detalle tributario: IGV | esperado 180.0, obtenido 180.0 |
| ✅ | Total de la factura | esperado 1180.0, obtenido 1180.0 |
| ✅ | Plazo 30 días: es crédito |  |
| ✅ | Forma de pago impresa CRÉDITO | esperado 'CRÉDITO', obtenido 'CRÉDITO' |
| ✅ | Una cuota de crédito | esperado 1, obtenido 1 |
| ✅ | Importe de la cuota = neto pendiente | esperado 1180.0, obtenido 1180.0 |
| ✅ | Etiqueta del IGV con la tasa aplicada | esperado 'IGV (18%)', obtenido 'IGV (18%)' |
| ✅ | Moneda en letras | esperado 'SOLES', obtenido 'SOLES' |
| ✅ | Monto en letras | MIL CIENTO OCHENTA Y 00/100 SOL |
| ✅ | Dirección del cliente en una línea | Av. Javier Prado Este 123, San Isidro, Lima |
| ✅ | XML UBL generado sin errores | 7391 bytes |
| ✅ | XML: InvoiceTypeCode 01 | esperado '01', obtenido '01' |
| ✅ | XML: serie-número | esperado 'FFQV-00000001', obtenido 'FFQV-00000001' |
| ✅ | XML: RUC del adquirente | esperado '20100070970', obtenido '20100070970' |
| ✅ | XML: schemeID 6 (RUC) | esperado '6', obtenido '6' |
| ✅ | XML: IGV total | esperado '180.00', obtenido '180.00' |
| ✅ | XML: importe a pagar | esperado '1180.00', obtenido '1180.00' |
| ✅ | XML: forma de pago Credito con cuota | ['Credito', 'Cuota001'] |
| ✅ | PDF A4 de la factura renderizado | 27780 bytes |
| ✅ | PDF ticket 80 mm de la factura renderizado | 26202 bytes |
| ✅ | HTML A4: forma de pago e importe impresos |  |
| ✅ | Envío a SUNAT pasa por el operador (IAP simulado) |  |
| ✅ | Sin respuesta real el comprobante no queda aceptado | to_send |
| ⏭️ | Envío a OSE/SUNAT real | sin credenciales de prueba (IAP simulado) |

**Registros:** `account.move/31483` F FQV-00000001

#### ✅ Boleta a cliente con DNI (identificador adicional): XML y PDF

**Pasos en pantalla:** Crear una factura para un cliente con DNI, que el sistema emite como boleta, confirmarla e imprimirla.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Cliente con DNI → boleta (03) por defecto |  |
| ✅ | Numeración de boleta serie B | B BQV-00000001 |
| ✅ | Total de la boleta | esperado 177.0, obtenido 177.0 |
| ✅ | Forma de pago CONTADO | esperado 'CONTADO', obtenido 'CONTADO' |
| ✅ | XML UBL generado sin errores | 6480 bytes |
| ✅ | XML: InvoiceTypeCode 03 | esperado '03', obtenido '03' |
| ✅ | XML: DNI del adquirente desde PE_DNI | esperado '46027897', obtenido '46027897' |
| ✅ | XML: schemeID 1 (DNI) | esperado '1', obtenido '1' |
| ✅ | PDF A4 de la boleta renderizado | 27231 bytes |
| ✅ | Ticket: imprime el DNI del cliente |  |

**Registros:** `account.move/31484` B BQV-00000001

#### ✅ Nota de crédito y nota de débito de la factura: XML y PDF

**Pasos en pantalla:** Desde la factura, emitir una nota de crédito (anulación) y una nota de débito (intereses).

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | NC: tipo 07 | esperado '07', obtenido '07' |
| ✅ | NC: documento que modifica | esperado account.move(31483,), obtenido account.move(31483,) |
| ✅ | NC: sin forma de pago impresa | esperado '', obtenido '' |
| ✅ | XML UBL generado sin errores | 7243 bytes |
| ✅ | XML raíz CreditNote |  |
| ✅ | XML NC: referencia a la factura | esperado 'FFQV-00000001', obtenido 'FFQV-00000001' |
| ✅ | XML NC: motivo 01 | esperado '01', obtenido '01' |
| ✅ | PDF A4 de la NC renderizado | 27607 bytes |
| ✅ | ND: tipo 08 | esperado '08', obtenido '08' |
| ✅ | ND: documento que modifica | esperado account.move(31483,), obtenido account.move(31483,) |
| ✅ | ND: total | esperado 59.0, obtenido 59.0 |
| ✅ | XML UBL generado sin errores | 7207 bytes |
| ✅ | XML raíz DebitNote |  |
| ✅ | XML ND: motivo 01 | esperado '01', obtenido '01' |
| ✅ | PDF A4 de la ND renderizado | 27821 bytes |

**Registros:** `account.move/31485` F CQV-00000001 (Reversión de: F FQV-00000001, QA20 Anulación, `account.move/31486` F NQV-00000001 (F FQV-00000001, QA20 Intereses por mora)


### `al_l10n_pe_edi_downpayment_discount`

#### ✅ Anticipo y factura final desde el pedido de venta

**Pasos en pantalla:** Confirmar un pedido, facturar un anticipo de S/ 118 y luego la factura final que lo descuenta.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | XML exportado sin errores | set() |
| ✅ | Reglas de validación SUNAT sin observaciones | [] |
| ✅ | PayableAmount = total del asiento | esperado 118.0, obtenido 118.0 |
| ✅ | al_l10n_pe_invoice: la factura enlaza el pedido (sale_id) | esperado sale.order(305,), obtenido sale.order(305,) |
| ✅ | al_l10n_pe_invoice: OC externa del pedido | esperado 'QA20 OC-ANT-001', obtenido 'QA20 OC-ANT-001' |
| ✅ | XML exportado sin errores | set() |
| ✅ | Reglas de validación SUNAT sin observaciones | [] |
| ✅ | PayableAmount = total del asiento | esperado 1062.0, obtenido 1062.0 |
| ✅ | Cargo/descuento global 04 (anticipo) | esperado ['04'], obtenido ['04'] |
| ✅ | XML: PrepaidPayment del anticipo |  |
| ✅ | Factura final: 1180 − 118 | esperado 1062.0, obtenido 1062.0 |

**Registros:** `sale.order/305` S00305, `account.move/31487` F FFI-00000002 (S00305), `account.move/31488` F FFI-00000003 (S00305)

#### ✅ Descuento por línea y descuento global

**Pasos en pantalla:** Facturar con 10 % de descuento en una línea y una línea de descuento global negativa.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | XML exportado sin errores | set() |
| ✅ | Reglas de validación SUNAT sin observaciones | [] |
| ✅ | PayableAmount = total del asiento | esperado 3186.0, obtenido 3186.0 |
| ✅ | Descuento global código 02 | ['02'] |
| ✅ | Descuento por línea código 00 |  |
| ✅ | al_l10n_pe_invoice: descuento total impreso (300 + 100) | esperado 400.0, obtenido 400.0 |

**Registros:** `account.move/31489` F FQV-00000002


### `al_l10n_pe_edi_free`

#### ✅ Convertir factura en transferencia gratuita (botón)

**Pasos en pantalla:** En una factura borrador con ítem gravado e inafecto pulsar «Transferencia gratuita» y confirmar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Afectaciones 11 (retiro gravado) y 37 (inafecto gratuito) | esperado ['11', '37'], obtenido ['11', '37'] |
| ✅ | No se cobra | esperado 0.0, obtenido 0.0 |
| ✅ | Leyenda 1002 | esperado '1002', obtenido '1002' |
| ✅ | XML exportado sin errores | set() |
| ✅ | Reglas de validación SUNAT sin observaciones | [] |
| ✅ | PayableAmount = total del asiento | esperado 0.0, obtenido 0.0 |
| ✅ | IGV gratuito del retiro (18.00) en el XML |  |

**Registros:** `account.move/31490` F FQV-00000003

#### ✅ Bloqueo de ítem gratuito con valor referencial 0

**Pasos en pantalla:** Intentar confirmar una factura con ítem gratuito a precio 0.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | No se confirma: regla SUNAT 2641 | SUNAT rechazaría los ítems gratuitos de Borrador de factura: · [QA20-IBU] QA20 Ibuprofeno 400 mg: el precio unitario de un ítem gratuito es su valor referencial y no puede ser 0 (2641, 3224). |


### `al_l10n_pe_edi_purchase_settlement`

#### ✅ Liquidación de compra: retenciones, XML anexo 6 y envío

**Pasos en pantalla:** Registrar una liquidación de compra de café a un productor con DNI por S/ 1,000, confirmarla y enviarla.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Diario LCE: es liquidación de compra |  |
| ✅ | Tipo de documento 04 | esperado '04', obtenido '04' |
| ✅ | IGV retenido | esperado 180.0, obtenido 180.0 |
| ✅ | Retención de renta 1,5 % | esperado 15.0, obtenido 15.0 |
| ✅ | Importe neto a pagar | esperado 985.0, obtenido 985.0 |
| ✅ | Estado por enviar | esperado 'to_send', obtenido 'to_send' |
| ✅ | XML: SelfBilledInvoice | esperado 'SelfBilledInvoice', obtenido 'SelfBilledInvoice' |
| ✅ | XML: tipo 04 | esperado '04', obtenido '04' |
| ✅ | XML: vendedor con DNI | esperado ('41020304', '1'), obtenido ('41020304', '1') |
| ✅ | XML: neto 985.00 | esperado '985.00', obtenido '985.00' |
| ✅ | XML: retención de renta (3000) 15.00 | esperado '15.00', obtenido '15.00' |
| ✅ | XML: placa del vehículo | esperado 'QA2-020', obtenido 'QA2-020' |
| ✅ | PDF de la liquidación de compra renderizado | 30751 bytes |
| ✅ | al_l10n_pe_edi_service: sendBill IAP con tipo 04 | https://l10n-pe-edi.api.odoo.com/iap/l10n_pe_edi/1/send_bill |
| ✅ | Liquidación aceptada (CDR simulado) | esperado 'sent', obtenido 'sent' |
| ✅ | ZIP con XML y CDR adjunto |  |
| ⏭️ | Envío real a SUNAT | sin credenciales de prueba (IAP simulado) |

**Registros:** `res.partner/9559` QA20 Productor Juana Quispe, `product.product/14001` [QA20-CAFE] QA20 Café pergamino, `account.move/31492` L L001-00000001

#### ✅ UIT desde el parámetro de nómina l10n_pe_uit y tope de renta

**Pasos en pantalla:** Revisar que el aviso de 75 UIT usa la UIT del año de la nómina y que hasta S/ 700 no se retiene renta.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Parámetro de reglas nativo l10n_pe_uit con valores | [('2026-01-01', '5500'), ('2025-01-01', '5350'), ('2024-01-01', '5150')] |
| ✅ | UIT 2026 desde hr.rule.parameter | esperado 5500.0, obtenido 5500.0 |
| ✅ | UIT 2025 = 5,350 del parámetro (no el 5,500 de ajustes): lee la nómina | esperado 5350.0, obtenido 5350.0 |
| ✅ | Aviso del vendedor sobre 75 UIT | Las liquidaciones de compra a QA20 Productor Juana Quispe en 2026 suman S/ 413600.00 y pasan de 75 UIT (S/ 412500.00). Si sus ventas del año superan ese límite ya no corresponde emitirle liquidaciones: consúltelo en SUNAT Operaciones en Línea. |
| ✅ | Hasta S/ 700 no se retiene renta | esperado 0.0, obtenido 0.0 |
| ✅ | Neto = 700 (IGV retenido) | esperado 700.0, obtenido 700.0 |

**Registros:** `account.move/31494` L L001-00000002


### `al_l10n_pe_delivery_guide_report`

#### ✅ Guía de remisión: entrega validada y representación impresa

**Pasos en pantalla:** Crear una entrega con transporte privado, validarla e imprimir la guía de remisión.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Entrega validada | esperado 'done', obtenido 'done' |
| ✅ | Líneas agrupadas por producto | esperado [(product.product(14000,), 5.0)], obtenido [(product.product(14000,), 5.0)] |
| ✅ | Peso bruto calculado (5 × 0,5 kg) | esperado 2.5, obtenido 2.5 |
| ✅ | Remitente = compañía (RUC y razón social) |  |
| ✅ | Licencia y DNI del conductor impresos |  |
| ✅ | Unidad de peso no fija |  |
| ✅ | Placa del vehículo impresa |  |
| ✅ | PDF de la guía renderizado | 26821 bytes |
| ✅ | Aparece en Perú ▸ Guías de remisión ▸ Por enviar |  |
| ⏭️ | Envío de la guía a SUNAT (GRE) | sin credenciales de prueba; el botón de imprimir exige estado sent |

**Registros:** `res.partner/9560` QA20 Conductor Pedro Ramos, `l10n_pe_edi.vehicle/14` [QA2-020] QA20 Camión, `stock.picking/1888` WH/OUT/00094


### `al_l10n_pe_complaints_book`

#### ✅ Libro de reclamaciones: registro, constancia, plazo y respuesta

**Pasos en pantalla:** Registrar un reclamo de una consumidora con DNI, revisar el plazo de 15 días hábiles, atenderlo y cerrarlo.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Correlativo por libro y año | 000000001-2026 |
| ✅ | Plazo de 15 días hábiles | esperado datetime.date(2026, 11, 20), obtenido datetime.date(2026, 11, 20) |
| ✅ | Constancia por correo con la hoja en PDF | ['Hoja de reclamación 000000001-2026 - OLANO IT S.A.C. (dev)'] |
| ✅ | Fecha de constancia registrada |  |
| ✅ | DNI de 7 dígitos rechazado | El DNI debe tener 8 dígitos. |
| ✅ | En atención | esperado 'in_progress', obtenido 'in_progress' |
| ✅ | Sin observaciones no se responde | Escriba las observaciones y acciones adoptadas antes de responder. |
| ✅ | Respondido | esperado 'answered', obtenido 'answered' |
| ✅ | Cerrado | esperado 'closed', obtenido 'closed' |
| ✅ | PDF de la hoja de reclamación | 29539 bytes |

**Registros:** `l10n_pe.complaint.book/16` QA20 Libro tienda virtual, `l10n_pe.complaint/82` 000000001-2026 - QA20 Consumidora Rosa Quispe


### `al_website_sale_pe`

#### ✅ Checkout: boleta/factura y consulta RUC/DNI (consulta simulada)

**Pasos en pantalla:** En la dirección de facturación de la tienda elegir boleta o factura y consultar el documento.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Cliente con DNI: boleta marcada | esperado 'boleta', obtenido 'boleta' |
| ✅ | Cliente con RUC: factura marcada | esperado 'factura', obtenido 'factura' |
| ✅ | Consulta RUC devuelve datos | {'found': True, 'values': {'name': 'QA20 EMPRESA CONSULTADA SAC', 'street': 'AV. 1'}, 'message': ''} |
| ✅ | Pasaporte: no se consulta |  |
| ✅ | Límite de consultas por sesión | Alcanzó el límite de consultas. Complete sus datos a mano. |
| ✅ | Formulario de dirección muestra el selector y el botón de consulta |  |
| ⏭️ | Interfaz del checkout | requiere navegador; cubierto por tests HttpCase del módulo |


### `al_l10n_pe_edi_pos`

#### ✅ Configurar TPV QA20 con diarios de boletas y facturas

**Pasos en pantalla:** Crear el punto de venta QA20 con diario de boletas, diario de facturas, efectivo y Yape.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | CPE en el TPV activo (ambos diarios configurados) |  |
| ✅ | TPV sin diarios CPE: flujo estándar |  |
| ✅ | El TPV carga el código SUNAT del cliente |  |
| ✅ | El TPV carga QR, importe en letras y totales del comprobante |  |

**Registros:** `account.journal/6114` QA20 Boletas TPV, `account.journal/6115` QA20 Facturas TPV, `account.journal/6116` QA20 Caja TPV CPE, `account.journal/6117` QA20 Caja TPV Lotes, `account.journal/6118` QA20 Yape, `res.partner.bank/185` QA20-YAPE-987654321, `pos.payment.method/834` QA20 Efectivo CPE, `pos.payment.method/835` QA20 Efectivo Lotes, `pos.payment.method/836` QA20 Yape, `pos.config/221` QA20 TPV CPE, `pos.config/222` QA20 TPV Lotes


### `al_pos_pe_wallet_qr`

#### ✅ Método Yape: QR de la billetera en la pantalla de pago

**Pasos en pantalla:** Configurar Yape con la imagen del QR de la cuenta y pedir el QR de un cobro en soles.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Método QR «billetera» ofrecido |  |
| ✅ | QR en data URI PNG |  |
| ✅ | Es la imagen de la cuenta | esperado 'iVBORw0KGgoAAAANSUhEUgAAACgAAAAoCAIAAAADnC86AAAAMklEQVR4nO3NAQ0AMAgAoPtAhrOpjYzh5qAAUdlvw19ZxWKxWCwWi8VisVgsFovFR+MBRhEBwWJ0EjUAAAAASUVORK5CYII=', obtenido 'iVBORw0KGgoAAAANSUhEUgAAACgAAAAoCAIAAAADnC86AAAAMklEQVR4nO3NAQ0AMAgAoPtAhrOpjYzh5qAAUdlvw19ZxWKxWCwWi8VisVgsFovFR+MBRhEBwWJ0EjUAAAAAS |
| ✅ | Mismo QR sin conexión (default_qr) | esperado 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACgAAAAoCAIAAAADnC86AAAAMklEQVR4nO3NAQ0AMAgAoPtAhrOpjYzh5qAAUdlvw19ZxWKxWCwWi8VisVgsFovFR+MBRhEBwWJ0EjUAAAAASUVORK5CYII=', obtenido 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACgAAAAoCAIAAAADnC86AAAAMklEQVR4nO3NAQ0AMAgAoPtAhrOpjYzh5qAAUdlvw |
| ✅ | Solo en soles | El siguiente error impidió generar el código QR de QR de billetera (Yape, Plin) aunque se detectó que es elegible:Yape y Plin solo cobran en soles. |
| ✅ | Cuenta sin imagen de QR rechazada | Suba la imagen del QR de billetera en la cuenta bancaria QA20-SIN-QR. |


### `al_pos_network_printer`

#### ✅ Impresora ESC/POS de red: lista blanca y ticket de prueba (simulado)

**Pasos en pantalla:** Activar la impresora de red del TPV, pulsar «Probar impresora» y revisar los destinos permitidos.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Destino de la caja permitido |  |
| ✅ | Destino de la impresora de cocina permitido |  |
| ✅ | IP no configurada rechazada (anti-SSRF) |  |
| ✅ | Puerto distinto rechazado |  |
| ✅ | Ticket de prueba enviado con el nombre de la caja |  |
| ✅ | Notificación de éxito | esperado 'success', obtenido 'success' |
| ✅ | Modo agente: la prueba no se hace en el servidor | El método de impresión está en 'Agente local' — use el botón 'Probar agente' de más abajo para confirmar que el agente responde. El backend de Odoo no tiene ruta de red directa a la impresora en ese m |
| ✅ | Imprimir al pagar activa iface_print_auto |  |
| ⏭️ | Impresión física | sin impresora; conexión TCP simulada |

**Registros:** `pos.printer/79` QA20 Cocina ESC/POS


### `al_pos_theme`

#### ✅ Tema del TPV: marca, colores y variables CSS

**Pasos en pantalla:** En Ajustes del TPV poner nombre de marca y color primario y revisar que la caja los use.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Título de la pestaña | esperado 'QA20 Botica · QA20 TPV CPE', obtenido 'QA20 Botica · QA20 TPV CPE' |
| ✅ | Color primario en las variables CSS |  |
| ✅ | Marca en las variables CSS |  |
| ✅ | Color inválido rechazado (red) | Color primario debe ser un color hexadecimal como #2563EB (se recibió red). |
| ✅ | Color inválido rechazado (#0F766E; } b) | Color primario debe ser un color hexadecimal como #2563EB (se recibió #0F766E; } body { display:none). |
| ✅ | Variables del modo oscuro |  |
| ✅ | El TPV recibe el botón de categorías, no las imágenes del tema |  |
| ✅ | Pantalla del cliente con título y variables sin comillas |  |


### `al_pos_product_view`

#### ⚠️ Vista de productos: stock del almacén del TPV y preferencia del cajero

**Pasos en pantalla:** Cambiar a vista de lista en la caja: el cajero guarda su preferencia y ve el stock del almacén.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | qty_available viaja al TPV |  |
| ✅ | Stock del almacén del TPV (WH/Existencias) | esperado 95.0, obtenido 95.0 |
| ⚠️ | Un solo almacén en la base | no se compara contra otro almacén |
| ✅ | Etiquetas filtro en el TPV |  |
| ✅ | El cajero guarda su vista (sin sudo) |  |
| ✅ | Preferencia guardada | esperado 'list', obtenido 'list' |
| ✅ | No cambia la preferencia de otro usuario | Solo puedes cambiar tu propia preferencia de vista del TPV. |
| ✅ | Preferencia cargada en el TPV |  |

**Registros:** `product.tag/29` QA20 Analgésicos


### `al_pos_vendedor`

#### ✅ Vendedores autorizados de la caja (sin PIN ni inicio de sesión)

**Pasos en pantalla:** Activar «Vendedor autorizado» en el TPV y elegir los vendedores que se pueden asignar a la orden.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | El TPV carga empleados (vendedores) |  |

**Registros:** `hr.employee/955` QA20 Ana Vendedora, `hr.employee/956` QA20 Carlos Almacén


### `al_pos_payment_gateway`

#### ❌ Pasarelas en línea: método por pasarela y logo

**Pasos en pantalla:** Desde la pasarela Niubiz crear su método de pago del TPV y agregar dos métodos en línea a la caja.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Tarjeta 240 × 160 de Niubiz para el TPV | esperado (240, 160), obtenido (240, 160) |
| ❌ | Crear el método del TPV desde Niubiz (botón de la pasarela) | TypeError: pos.payment.method.image: use BinaryValue instead of bytes |
| ✅ | Método creado desde la pasarela | esperado payment.provider(4702,), obtenido payment.provider(4702,) |
| ✅ | El método lleva el logo de la pasarela |  |
| ✅ | Dos métodos en línea en la misma caja | esperado 2, obtenido 2 |
| ✅ | Una pasarela no puede estar en dos métodos de la caja | La pasarela QA20 Pasarela A está en dos métodos de pago en línea de la caja QA20 TPV CPE: cada pasarela va en un solo método. |
| ✅ | El pago de la pasarela B va a su método | esperado pos.payment.method(840,), obtenido pos.payment.method(840,) |

**Registros:** `payment.provider/4702` QA20 Pasarela A, `payment.provider/4703` QA20 Pasarela B, `pos.payment.method/839` QA20 Pasarela A, `pos.payment.method/840` QA20 Pasarela B


### `al_l10n_pe_edi_pos`

#### ✅ Venta en caja con boleta a cliente DNI (CPE desde el TPV)

**Pasos en pantalla:** Abrir la caja, vender 2 ibuprofenos a una clienta con DNI eligiendo «Boleta», cobrar en efectivo.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Orden pagada | esperado 'paid', obtenido 'paid' |
| ✅ | La orden generó su comprobante | B BQB-00000001 |
| ✅ | Comprobante en el diario de boletas del TPV | esperado account.journal(6114,), obtenido account.journal(6114,) |
| ✅ | Tipo 03 (boleta) | esperado '03', obtenido '03' |
| ✅ | Total de la boleta | esperado 118.0, obtenido 118.0 |
| ✅ | Boleta pagada con el cobro de caja | paid |
| ✅ | QR de la representación impresa (RUC\|03\|serie\|folio\|igv\|total\|fecha\|1\|DNI) | 20557912879\|03\|BQB\|00000001\|18.00\|118.00\|2026-10-30\|1\|46027897 |
| ✅ | Importe en letras del ticket | CIENTO DIECIOCHO Y 00/100 SOL |
| ✅ | Etiqueta del IGV del ticket | esperado 'IGV (18%)', obtenido 'IGV (18%)' |
| ✅ | El TPV intentó enviar el CPE a SUNAT (IAP simulado) |  |
| ✅ | XML UBL generado sin errores | 6503 bytes |
| ✅ | XML de la boleta del TPV: 03 | esperado '03', obtenido '03' |
| ✅ | Ticket 80 mm de la boleta del TPV | 25767 bytes |
| ✅ | al_pos_vendedor: vendedor guardado en la orden | esperado hr.employee(955,), obtenido hr.employee(955,) |
| ⏭️ | Envío a OSE | sin credenciales de prueba (IAP simulado) |

**Registros:** `pos.session/400` QA20 TPV CPE/00382, `pos.order/431` QA20 TPV CPE - 000001, `account.move/31495` B BQB-00000001 (Customer invoice from QA20 TPV CPE - 000001)

#### ✅ Factura desde la caja a cliente RUC, retenida («Emitir a SUNAT: No») y NC por devolución

**Pasos en pantalla:** Vender con «Factura» a un cliente con RUC; otra venta con «Emitir a SUNAT: No»; devolver la primera.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Factura en el diario de facturas del TPV | esperado account.journal(6115,), obtenido account.journal(6115,) |
| ✅ | Tipo 01 (factura) | esperado '01', obtenido '01' |
| ✅ | Factura marcada «Emisión SUNAT retenida» |  |
| ✅ | El envío de la retenida no se hace | Emisión SUNAT retenida desde el TPV: desmarque «Emisión SUNAT retenida» en F FQF-00000002 (Customer invoice from QA20 TPV CPE - 000003) para enviarla. |
| ✅ | La devolución enlaza la orden original | esperado pos.order(432,), obtenido pos.order(432,) |
| ✅ | NC de factura en el diario de facturas (aunque la caja marque boleta) | esperado account.journal(6115,), obtenido account.journal(6115,) |
| ✅ | NC tipo 07 | esperado '07', obtenido '07' |
| ✅ | NC enlazada a la factura | esperado account.move(31497,), obtenido account.move(31497,) |
| ✅ | Factura a cliente sin RUC rechazada | La factura electrónica requiere un cliente con RUC (tipo de documento RUC y 11 dígitos). Seleccione el cliente o emita una boleta. |

**Registros:** `pos.order/432` QA20 TPV CPE - 000002, `account.move/31497` F FQF-00000001 (Customer invoice from QA20 TPV CPE - 000002), `account.move/31499` F FQF-00000002 (Customer invoice from QA20 TPV CPE - 000003), `pos.order/434` REEMBOLSO DE QA20 TPV CPE - 000002, `account.move/31501` F CQF-00000001 (Reversión de: F FQF-00000001)


### `al_l10n_pe_pos_loyalty`

#### ✅ Tarjeta de regalo: venta sola sin comprobante y venta mixta

**Pasos en pantalla:** Vender solo una tarjeta de regalo (sale recibo) y luego ibuprofeno + tarjeta con boleta.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Producto tarjeta de regalo marcado como vale |  |
| ✅ | Producto normal no es vale |  |
| ✅ | Cuenta 496 de vales configurada | 4960000 |
| ✅ | Venta solo de tarjeta: sin comprobante |  |
| ✅ | Queda como recibo | esperado 'recibo', obtenido 'recibo' |
| ✅ | La boleta no incluye la tarjeta (59.00) | esperado 59.0, obtenido 59.0 |
| ✅ | Solo el producto en la boleta | esperado product.product(14000,), obtenido product.product(14000,) |
| ✅ | Boleta saldada |  |
| ✅ | Pasivo con el cliente por la tarjeta (−50.00) | esperado -50.0, obtenido -50.0 |

**Registros:** `pos.order/436` QA20 TPV CPE - 000006, `pos.order/437` QA20 TPV CPE - 000007, `account.move/31503` B BQB-00000002 (Customer invoice from QA20 TPV CPE - 000007), `account.move/31505` MISC/2026/10/0010 (Tarjeta de regalo y monedero: B BQB-00000


### `al_pos_pe_wallet_qr`

#### ✅ Cobro con Yape en caja

**Pasos en pantalla:** Vender un ibuprofeno a una clienta y cobrar con Yape.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Pago registrado con Yape | esperado pos.payment.method(836,), obtenido pos.payment.method(836,) |
| ✅ | El TPV carga los datos del QR del método |  |

**Registros:** `pos.order/438` QA20 TPV CPE - 000008


### `al_pos_payment_gateway`

#### ✅ Revisión del comprobante antes del QR de la pasarela

**Pasos en pantalla:** Con una venta a facturar, antes de mostrar el QR de la pasarela el sistema revisa que el comprobante se pueda emitir.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Boleta emitible: se puede cobrar |  |
| ✅ | La factura de prueba se deshace | esperado 533, obtenido 533 |
| ✅ | Factura a cliente sin RUC: el cajero ve el motivo antes del QR | No se puede emitir el comprobante de esta venta; corrija esto antes de cobrar:  La factura electrónica requiere un cliente con RUC (tipo de documento RUC y 11 dígitos). Seleccione el cliente o emita una boleta. |
| ✅ | El cajero elige el método B para el QR | esperado pos.payment.method(840,), obtenido pos.payment.method(840,) |
| ✅ | El pago que llega por la pasarela B va a su método | esperado pos.payment.method(840,), obtenido pos.payment.method(840,) |
| ⏭️ | Cobro real en la pasarela | requiere navegador y credenciales de la pasarela |


### `al_pos_vendedor`

#### ✅ Vendedor en la orden y en el análisis de ventas; cierre de caja

**Pasos en pantalla:** Cerrar la caja y revisar el análisis del TPV agrupado por vendedor.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Sin pos_hr solo viajan los vendedores de la lista |  |
| ✅ | Vendedor sin PIN ni código de barras, marcado solo-vendedor |  |
| ✅ | Cierre de caja sin errores | {'status': True} |
| ✅ | Sesión cerrada | esperado 'closed', obtenido 'closed' |
| ✅ | Asientos de cierre de la sesión | ['POSC/2026/00001'] |
| ✅ | Análisis del TPV: ventas por vendedor | 1 |


### `al_pos_product_view`

#### ⚠️ Cajero QA20 (no admin) vende producto con lote: sin y con grupo Inventario/Usuario

**Pasos en pantalla:** Como cajero sin permisos de Inventario abrir la caja, elegir el lote del producto, cobrar y cerrar; repetir con el grupo.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Cajero sin grupo Inventario/Usuario |  |
| ⚠️ | Sin grupo Inventario/Usuario el cajero NO completa la venta con lote | AccessError: No puede acceder a los registros 'Número de serie/lote' (stock.lot). \| en pos_stock/models/stock_picking.py:139 _create_move_from_pos_order_lines > pos_stock/models/stock_move.py:100 _add_mls_related_to_order > pos_stock/models/stock_move.py:44 _create_production_lots_for_pos_order > / |
| ✅ | Con grupo Inventario/Usuario: lotes visibles, venta con lote y caja cerrada | ['QA20-LOTE-A1'] |
| ⚠️ | Cierre de caja del cajero | cierre por el cajero bloqueado por una cuenta bancaria ajena no confiable; se cierra como sistema |

**Registros:** `res.users/3831` QA20 Cajero TPV, `product.product/14006` QA20 Amoxicilina 500 mg (lote), `stock.lot/299` QA20-LOTE-A1, `pos.session/402` QA20 TPV Lotes/00384, `pos.order/441` QA20 TPV Lotes - 000001


### `al_pos_pe_partner_lookup`

#### ✅ Crear cliente en caja desde RUC o DNI (consulta simulada)

**Pasos en pantalla:** En la lista de clientes del TPV escribir un RUC o un DNI y crear el cliente con los datos consultados.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Consulta como RUC (código 6) | esperado '6', obtenido '6' |
| ✅ | Cliente RUC creado | esperado ('20600009002', '6', True), obtenido ('20600009002', '6', True) |
| ✅ | Cliente DNI creado (identificador adicional) | esperado ('1', '70123456'), obtenido ('1', '70123456') |
| ✅ | DNI existente: devuelve el cliente sin consultar | esperado 9558, obtenido 9558 |
| ✅ | Sin consulta para cliente existente |  |
| ✅ | Formato inválido rechazado | Escriba un RUC (11 dígitos) o un DNI (8 dígitos). |
| ✅ | Usuario sin permiso de crear contactos rechazado | No puede crear registros 'Contacto' (res.partner).  Esta operación está permitida para los siguientes grupos: 	- Ventas / Administrador 	- Manufactura / Administrador 	- Compras / Administrador 	- Pun |
| ⏭️ | Consulta real SUNAT/RENIEC | sin token de consulta; respuesta simulada |

**Registros:** `res.partner/9572` QA20 EMPRESA CONSULTADA SAC, `res.partner/9573` QA20 LUIS HUAMAN CCORI


### `al_pos_theme`

#### ✅ Assets del TPV: los bundles compilan e incluyen los módulos QA

**Pasos en pantalla:** Abrir la caja en el navegador (aquí: generar los bundles JS/CSS del TPV).

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Bundle JS point_of_sale.assets_prod generado | 961 archivos |
| ✅ | Bundle CSS/SCSS point_of_sale.assets_prod compilado | 306 hojas |
| ✅ | Bundle CSS/SCSS point_of_sale.assets_prod_dark compilado | 339 hojas |
| ✅ | Bundle JS point_of_sale.customer_display_assets generado | 254 archivos |
| ✅ | Bundle CSS/SCSS point_of_sale.customer_display_assets compilado | 127 hojas |
| ✅ | Todos los módulos OL-POS presentes en los bundles del TPV | 3849 |
| ⏭️ | Interfaz al_pos_theme | requiere navegador; cubierto por tours/estático |
| ⏭️ | Interfaz al_pos_product_view | requiere navegador; cubierto por tours/estático |
| ⏭️ | Interfaz al_pos_online_payment | requiere navegador; cubierto por tours/estático |
| ⏭️ | Interfaz al_pos_network_printer | requiere navegador; cubierto por tours/estático |


### `al_sale_approval`

#### ⚠️ Pedido con producto que exige aprobación: pendiente hasta aprobar

**Pasos en pantalla:** Cotizar un producto marcado «Requiere aprobación», solicitar la aprobación, aprobarla como gerente y confirmar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Cotización: aprobación por solicitar | esperado 'to_request', obtenido 'to_request' |
| ✅ | No se confirma sin aprobación | La orden S00307 necesita una solicitud aprobada en Aprobaciones («Solicitar aprobación») antes de confirmarse. |
| ✅ | Solicitud enlazada al pedido | esperado (sale.order(307,), 'S00307'), obtenido (sale.order(307,), 'S00307') |
| ✅ | Pendiente de aprobación | esperado 'pending', obtenido 'pending' |
| ✅ | Pendiente: no se confirma | La orden S00307 necesita una solicitud aprobada en Aprobaciones («Solicitar aprobación») antes de confirmarse. |
| ✅ | Aprobada por el gerente | esperado 'approved', obtenido 'approved' |
| ✅ | Pedido confirmado tras aprobar | esperado 'sale', obtenido 'sale' |
| ✅ | Producto sin marca: no requiere aprobación | esperado 'not_required', obtenido 'not_required' |
| ⚠️ | El módulo aprueba por producto marcado, no por límite de importe | no hay regla de monto en al_sale_approval (approvals nativo) |

**Registros:** `res.partner/9574` QA20 Cliente RUC Aprobaciones SAC, `product.product/14009` QA20 Servicio HKA, `account.journal/6123` QA20 Ventas OSE HKA, `res.users/3832` QA20 Gerente aprobador, `approval.category/23` QA20 Aprobación de orden de venta, `product.product/14010` QA20 Muebles de melamina, `sale.order/307` S00307, `approval.request/141` Aprobación de S00307, `sale.order/308` S00308


### `al_ose_factory_hka`

#### ✅ Operador Factory HKA: envío, consulta CDR y baja (OSE simulado)

**Pasos en pantalla:** Con el operador «The Factory HKA» y sus credenciales, enviar una factura, consultar su CDR y darla de baja.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Operador Factory HKA disponible |  |
| ✅ | Entorno de prueba usa el WSDL demo de HKA | esperado 'https://demoose.thefactoryhka.com.pe/ol-ti-itcpfegem/billService?wsdl', obtenido 'https://demoose.thefactoryhka.com.pe/ol-ti-itcpfegem/billService?wsdl' |
| ✅ | Nombre de archivo con número en 8 dígitos | 20557912879-01-FFQH-00000001 |
| ✅ | Envío sin errores | None |
| ✅ | Aceptada (CDR simulado) | esperado 'sent', obtenido 'sent' |
| ✅ | sendBill con el usuario de HKA | esperado ('sendBill', 'QA20HKA'), obtenido ('sendBill', 'QA20HKA') |
| ✅ | ZIP enviado con el nombre HKA | 20557912879-01-FFQH-00000001.zip |
| ✅ | XML firmado con el certificado (SignatureValue) |  |
| ✅ | Consulta de CDR (getStatusCdr) | esperado '0004', obtenido '0004' |
| ✅ | Baja por comunicación (sendSummary + getStatus) | esperado 'cancelled', obtenido 'cancelled' |
| ✅ | Operaciones de baja | esperado ['sendSummary', 'getStatus'], obtenido ['sendSummary', 'getStatus'] |
| ✅ | Factura: baja por RA, no por resumen |  |
| ✅ | Sin contraseña: queda pendiente y no llama al OSE |  |
| ✅ | Configuración de la compañía restaurada | esperado 'iap', obtenido 'iap' |
| ⏭️ | Envío real a Factory HKA | sin credenciales de prueba; cliente SOAP simulado |

**Registros:** `res.partner/9574` QA20 Cliente RUC Aprobaciones SAC, `product.product/14009` QA20 Servicio HKA, `account.journal/6123` QA20 Ventas OSE HKA, `certificate.certificate/18` QA20 Certificado demo (pruebas), `account.move/31514` F FQH-00000001, `account.move/31515` F FQH-00000002


## Fases 4 y 7 · Inventario, farmacia e industrias


### `preparacion`

#### ✅ Datos maestros QA20 de la fase

**Pasos en pantalla:** Crear almacenes, categorías y contactos de prueba.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | almacenes QA20 disponibles | Q20TA, Q20TB, Q20FA |

**Registros:** `stock.warehouse/897` QA20 Inv Central, `stock.warehouse/898` QA20 Inv Obra, `stock.warehouse/899` QA20 Botica, `res.partner/9636` QA20 Droguería Andina S.A.C., `res.partner/9637` QA20 Clínica San Juan S.A.C., `res.partner/9638` QA20 Alquileres del Sur S.A.C., `res.partner/9639` QA20 Mario Cárdenas Ríos, `res.partner/9640` QA20 Dra. Elena Vargas

#### ✅ Caja «QA20 Botica» del local Q20FA

**Pasos en pantalla:** Crear el diario de caja, el método Efectivo y el punto de venta del local y abrir la sesión.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | el administrador es responsable del TPV |  |
| ✅ | sesión del TPV abierta | opened |

**Registros:** `pos.config/225` QA20 Botica, `pos.session/405` QA20 Botica/00387


### `al_stock_base`

#### ✅ Tipo de operación SUNAT (tabla 12) y página «Logística PE»

**Pasos en pantalla:** Abrir una recepción, una salida y un traslado: la página Logística PE muestra el tipo de operación de la tabla 12 (02 compra / 01 venta / 21 traslado).

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | recepción validada | esperado 'done', obtenido 'done' |
| ✅ | recepción: tabla 12 = 02 (compra) | esperado '2', obtenido '2' |
| ✅ | salida: tabla 12 = 01 (venta) | esperado '1', obtenido '1' |
| ✅ | traslado interno: tabla 12 = 21 | esperado '21', obtenido '21' |
| ✅ | página «Logística PE» en el formulario |  |
| ✅ | el tipo de operación (tabla 12) vive en la página Logística PE |  |
| ✅ | el campo aparece una sola vez en el formulario | esperado 1, obtenido 1 |

**Registros:** `product.product/14157` QA20 Tornillo T12, `stock.picking/1987` Q20TA/IN/00001, `stock.picking/1988` Q20TA/OUT/00001, `stock.picking/1989` Q20TA/INT/00001

#### ✅ Planchas enteras: producto indivisible y redondeo

**Pasos en pantalla:** Crear la unidad «Plancha 2.44×2.15» marcada «Plancha entera» y un tablero con esa unidad: queda indivisible y una necesidad de 7.3 planchas se entrega como 8.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | el tablero con unidad «Plancha entera» es indivisible |  |
| ✅ | área de la plancha en m² desde el factor | esperado 5.246, obtenido 5.246 |
| ✅ | necesidad 7.3 → planchas enteras (tolerancia 0.0) | esperado 8.0, obtenido 8.0 |
| ✅ | 7.000001 no sube a 8 (redondeo de la UdM) | esperado 7.0, obtenido 7.0 |
| ✅ | forzado «No» en el producto anula la regla de la unidad |  |
| ✅ | resumen de inventario sin la etiqueta «Late» en inglés |  |

**Registros:** `uom.uom/180` QA20 Plancha 2.44x2.15, `product.product/14158` QA20 Tablero melamina 18 mm


### `al_l10n_pe_stock_transfer`

#### ✅ Traslado interno entre establecimientos con GRE motivo 04

**Pasos en pantalla:** Trasladar 4 andamios de «Inv Central» (anexo 0091) a «Inv Obra» (anexo 0092) y emitir la guía de remisión: motivo 04, destinatario = remitente.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | el traslado admite guía de remisión |  |
| ✅ | punto de partida = dirección del almacén origen | esperado res.partner(9633,), obtenido res.partner(9633,) |
| ✅ | punto de llegada = dirección del almacén destino | esperado res.partner(9634,), obtenido res.partner(9634,) |
| ✅ | motivo propuesto 04 | esperado '04', obtenido '04' |
| ✅ | GRE marcada como enviada (firma simulada) | esperado 'sent', obtenido 'sent' |
| ✅ | XML: HandlingCode 04 | esperado '04', obtenido '04' |
| ✅ | XML: destinatario = RUC de la empresa | esperado '20557912879', obtenido '20557912879' |
| ✅ | XML: partida con anexo 0091 y RUC | esperado ('0091', '20557912879'), obtenido ('0091', '20557912879') |
| ✅ | XML: llegada con anexo 0092 y RUC | esperado ('0092', '20557912879'), obtenido ('0092', '20557912879') |
| ⏭️ | Envío real de la GRE a SUNAT/OSE | sin credenciales: firma y envío simulados como en los tests |
| ✅ | traslado dentro del mismo establecimiento no admite guía |  |
| ✅ | enviar la guía de un traslado sin salida del local se bloquea |  |

**Registros:** `product.product/14159` QA20 Andamio, `stock.picking/1990` Q20TA/INT/00002, `stock.picking/1991` Q20TA/INT/00003

#### ✅ Bienes de terceros: guía con propietario y sin valorizar

**Pasos en pantalla:** Recibir 5 andamios en consignación de «Alquileres del Sur» y trasladarlos a la obra: la guía lleva el propietario en observaciones y los bienes no entran a la valorización ni al kardex.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | recepción de terceros validada | esperado 'done', obtenido 'done' |
| ✅ | la recepción se marca «Con bienes de terceros» |  |
| ✅ | la recepción de bienes de terceros no se valoriza (value = 0) | esperado 0.0, obtenido 0.0 |
| ✅ | existencias de terceros separadas por propietario | esperado 5.0, obtenido 5.0 |
| ✅ | los bienes de terceros no entran al kardex valorizado |  |
| ✅ | traslado con bienes de terceros |  |
| ✅ | propietario detectado en la transferencia | esperado res.partner(9638,), obtenido res.partner(9638,) |
| ✅ | XML de la GRE: propietario en las observaciones | Bienes de propiedad de QA20 Alquileres del Sur S.A.C. (20601234565). |
| ✅ | PDF de la guía con el propietario |  |
| ✅ | la propia compañía no cuenta como tercero |  |

**Registros:** `stock.picking/1992` Q20TA/IN/00002, `stock.picking/1993` Q20TA/INT/00004, `stock.picking/1994` Q20TA/INT/00005


### `ol_stock_kardex_pe`

#### ✅ Kardex 13.1 valorizado (AVCO) cuadra con el valor de inventario

**Pasos en pantalla:** Comprar 10 u a S/10 y 10 u a S/20, facturar la primera compra (F001), vender 5 y abrir «Kardex SUNAT» 13.1 de octubre 2026: saldo 15 u × 15 = S/225.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | filas: saldo inicial + 3 movimientos | esperado ['opening', 'move', 'move', 'move'], obtenido ['opening', 'move', 'move', 'move'] |
| ✅ | saldo inicial con operación 16 | esperado '16', obtenido '16' |
| ✅ | compra: operación 02 (tabla 12) | esperado '02', obtenido '02' |
| ✅ | compra: comprobante de la factura (tabla 10) | esperado ('01', 'F001', '00020123'), obtenido ('01', 'F001', '00020123') |
| ✅ | costo promedio tras la 2.ª compra | esperado 15.0, obtenido 15.0 |
| ✅ | venta: operación 01 | esperado '01', obtenido '01' |
| ✅ | salida 5 × 15 = 75 (AVCO) | esperado 75.0, obtenido 75.0 |
| ✅ | venta sin comprobante → guía (09) | esperado '09', obtenido '09' |
| ✅ | saldo final 15 u | esperado 15.0, obtenido 15.0 |
| ✅ | saldo final S/ 225 | esperado 225.0, obtenido 225.0 |
| ✅ | saldo del kardex = valor de inventario de Odoo | esperado 225.0, obtenido 225.0 |
| ✅ | saldo del kardex = cantidad a mano | esperado 15.0, obtenido 15.0 |
| ✅ | XLSX 13.1 generado | esperado b'PK', obtenido b'PK' |
| ✅ | PDF formato 13.1 con el producto |  |

**Registros:** `product.product/14160` [QA20-KDX-001] QA20 Producto Kardex, `purchase.order/958` P00958, `purchase.order/959` P00959, `sale.order/323` S00323, `account.move/31534` F F001-00020123, `l10n_pe.kardex.report/24` Kardex 13.1 · 2026-10-01 a 2026-10-31

#### ✅ Kardex 12.1 en unidades físicas por almacén

**Pasos en pantalla:** Generar el formato 12.1 agrupado por almacén: solo cantidades, sin costos.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | hay bloques por almacén |  |
| ✅ | saldo físico sumado por almacén = 15 | esperado 15.0, obtenido 15.0 |
| ✅ | 12.1 sin costos |  |
| ✅ | vista SQL del kardex interactivo: 3 movimientos | esperado 3, obtenido 3 |
| ✅ | saldo corrido en el kardex interactivo | esperado 225.0, obtenido 225.0 |

#### ✅ TXT del PLE 13.1 con el comprobante del kardex

**Pasos en pantalla:** Generar el libro electrónico 13.1 (PLE) de octubre 2026: la fila de la compra lleva tipo 01, serie F001 y número 00020123; la unidad es la del producto.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | fila de la compra en el TXT (CUO = id del movimiento) |  |
| ✅ | TXT: comprobante de la compra | esperado ('01', 'F001', '00020123'), obtenido ('01', 'F001', '00020123') |
| ✅ | TXT: fecha del periodo en hora de Lima | esperado '10/2026', obtenido '10/2026' |
| ✅ | TXT: unidad del producto (campo 16) | esperado 'NIU', obtenido 'NIU' |
| ✅ | TXT: 3 filas de movimientos del producto QA20 | esperado 3, obtenido 3 |
| ✅ | TXT: código del producto saneado (campo 7) |  |
| ✅ | campo 17 (tabla 14): promedio = 1 | esperado '1', obtenido '1' |
| ✅ | nombre del archivo PLE con el RUC | LE2055791287920261000130100001111.txt |
| ⏭️ | Presentación del PLE en SUNAT | se valida el TXT generado; la carga al PLE es manual/externa |


### `al_l10n_pe_mrp_cost`

#### ⚠️ Costo de OF: materiales + MO + CIF con cierre del periodo

**Pasos en pantalla:** Fabricar 2 mesas (4 tableros a S/10, 2 h de corte con un operario a S/10/h), aplicar el costo hora real del mes (S/15) y repartir una bolsa de CIF de S/300 con el cierre de costos.

| Estado | Comprobación | Detalle |
|---|---|---|
| ⚠️ | Contrapartida de MO no configurada en la compañía (Ajustes de Fabricación) | se simula 7111000 durante el cierre, sin escribir en res.company |
| ✅ | OF terminada | esperado 'done', obtenido 'done' |
| ✅ | costo hora del mes aplicado | esperado 'applied', obtenido 'applied' |
| ✅ | ajuste de MO: 2 h × (15 − 10) = 10 | esperado 10.0, obtenido 10.0 |
| ✅ | CIF repartido a la OF: 300 | esperado 300.0, obtenido 300.0 |
| ✅ | cierre validado | esperado 'done', obtenido 'done' |
| ✅ | costo en destino validado | esperado 'done', obtenido 'done' |
| ✅ | valor del producto terminado + 310 | esperado 430.0, obtenido 430.0 |
| ✅ | asiento: abono a la 71 por 310 | esperado 310.0, obtenido 310.0 |
| ✅ | análisis: materiales 40 | esperado 40.0, obtenido 40.0 |
| ✅ | análisis: mano de obra 20 | esperado 20.0, obtenido 20.0 |
| ✅ | análisis: ajuste de MO 10 | esperado 10.0, obtenido 10.0 |
| ✅ | análisis: CIF 300 | esperado 300.0, obtenido 300.0 |
| ✅ | análisis: costo de máquina | 60.0 |

**Registros:** `product.product/14161` QA20 Tablero MRP, `product.product/14162` QA20 Mesa de centro, `mrp.workcenter/29` QA20 Seccionadora, `mrp.bom/1542` QA20 Mesa de centro, `hr.employee/963` QA20 Juan Pérez MRP, `mrp.production/550` Q20TA/MO/00001, `l10n_pe.mrp.labor.rate/23` Costo hora 2026-10-01 – 2026-10-31, `l10n_pe.mrp.cost.pool/23` QA20 Gastos de planta, `account.move/31535` MISC/2026/10/0011 (QA20 CIF del mes), `l10n_pe.mrp.cost.close/25` Cierre de costos 2026-10-30 – 2026-10-30


### `al_mrp_piece_costing`

#### ✅ Orden de corte: costo por área, tablero y tapacanto

**Pasos en pantalla:** Fabricar una orden de corte con dos tableros (S/100 y S/200), 3 m de tapacanto y S/10 de costo extra: cada pieza sale con su costo (lateral 72.37, repisa 35.19, puerta 204.70).

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | orden de corte terminada | esperado 'done', obtenido 'done' |
| ✅ | lateral: 66.67 tablero + 2 tapacanto + 3.70 general | esperado 72.37, obtenido 72.37 |
| ✅ | repisa | esperado 35.19, obtenido 35.19 |
| ✅ | puerta (roble) | esperado 204.7, obtenido 204.7 |
| ✅ | producto principal (área 0.1) ≈ 0.74 (redondeo) | 0.75 |
| ✅ | costo total de la orden 313 | esperado 313.0, obtenido 313.0 |
| ✅ | cuadre de piezas vs. consumo | 0.01 |
| ✅ | no se puede desmontar una orden de corte |  |

**Registros:** `mrp.bom/1543` QA20 Corte OP 999, `mrp.production/551` Q20TA/MO/00002

#### ✅ Importar despiece desde XLSX

**Pasos en pantalla:** Importar el despiece de la obra QA20MC (2 piezas) desde Excel: crea las piezas con área, tablero y tapacanto.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | importación terminada | esperado 'done', obtenido 'done' |
| ✅ | resumen: 2 piezas creadas | Importación terminada. Piezas creadas: 2 · actualizadas: 0 Obras: QA20MC Área: 1.0340 m² · tapacanto: 2.52 m · unidades: 3 Avisos (1): - Fila 3: area_m2 (0.25) difiere más de 2 % de largo × ancho (0.210000); se usa area_m2. |
| ✅ | la pieza queda marcada como pieza de corte |  |
| ✅ | área calculada 0.7 × 0.56 | esperado 0.392, obtenido 0.392 |
| ✅ | tablero de la pieza | esperado product.product(14163,), obtenido product.product(14163,) |

**Registros:** `product.product/14170` [QA20MC-1] Pieza QA20MC 1 700x560


### `preparacion`

#### ✅ Usuarios y ajustes de farmacia QA20

**Pasos en pantalla:** Crear el técnico y la Q.F. de prueba; categoría Farmacia con salida FEFO.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | estrategia de salida FEFO disponible (product_expiry) |  |

**Registros:** `res.users/3845` QA20 qa20_tecnico_farmacia, `res.users/3846` QA20 qa20_qf_farmacia, `hr.employee/964` QA20 Q.F. Rosa Quispe


### `al_pharmacy_base`

#### ✅ Maestro de medicamentos: composición, equivalentes y alternativas

**Pasos en pantalla:** Registrar Apronax (innovador) y tres genéricos de naproxeno 550 mg: el sistema propone primero los genéricos DCI más baratos y vincula bioequivalentes en ambos sentidos.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | composición rotulada | esperado 'Qa20 paracetamol 500 mg + Qa20 cafeína 65 mg', obtenido 'Qa20 paracetamol 500 mg + Qa20 cafeína 65 mg' |
| ✅ | mismo principio, concentración y forma = equivalente |  |
| ✅ | otra forma farmacéutica no es equivalente |  |
| ✅ | alternativas: genéricos DCI por precio y luego genérico de marca | esperado [14115, 14116, 14117], obtenido [14115, 14116, 14117] |
| ✅ | bioequivalencia recíproca | esperado product.template(14114,), obtenido product.template(14114,) |
| ✅ | el bioequivalente cuenta como equivalente |  |

**Registros:** `product.product/14172` QA20 Panadol Extra, `product.product/14173` QA20 Apronax 550, `product.product/14174` QA20 Naproxeno Genfar 550, `product.product/14175` QA20 Naproxeno Portugal 550, `product.product/14176` QA20 Naprox 550, `product.product/14177` QA20 Naproxeno suspensión, `product.product/14178` QA20 Naproxeno 500 base

#### ✅ Presentaciones, cuaderno de ocurrencias y turnos del Q.F.

**Pasos en pantalla:** Crear la presentación «Caja x 100» de paracetamol, anotar una ocurrencia en el cuaderno y registrar un turno de reemplazo del Q.F.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | nombre de la presentación | esperado 'Caja x 100', obtenido 'Caja x 100' |
| ✅ | la presentación crea su unidad de 100 | esperado 100, obtenido 100.0 |
| ✅ | la unidad queda en las unidades del producto |  |
| ✅ | precio unitario de la caja | esperado 0.12, obtenido 0.12 |
| ✅ | 300 unidades = 3 cajas | esperado 3, obtenido 3 |
| ✅ | una presentación de 1 unidad se rechaza |  |
| ✅ | ocurrencia numerada | OC/2026/00097 |
| ✅ | el cuaderno no se edita |  |
| ✅ | el cuaderno no se borra |  |
| ✅ | el turno de reemplazo queda en el cuaderno |  |
| ✅ | Q.F. de turno en el local |  |
| ✅ | reporte del cuaderno de ocurrencias |  |

**Registros:** `product.product/14179` QA20 Paracetamol 500 caja, `pharmacy.presentation/131` Caja x 100, `pharmacy.logbook.entry/97` OC/2026/00097, `pharmacy.shift/20` QA20 Q.F. Rosa Quispe · QA20 Botica


### `al_l10n_pe_pharmacy_edi`

#### ✅ Presentación en el comprobante electrónico (código SUNAT de la caja)

**Pasos en pantalla:** Facturar 1 «Caja x 100» de amoxicilina: el XML UBL lleva unitCode BX y el precio de la caja.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Caja → BX (catálogo 03) | esperado 'BX', obtenido 'BX' |
| ✅ | Frasco → BO | esperado 'BO', obtenido 'BO' |
| ✅ | Blíster → código de la unidad del producto (NIU) | esperado 'NIU', obtenido 'NIU' |
| ✅ | XML UBL sin errores | [] |
| ✅ | XML: unitCode BX | esperado 'BX', obtenido 'BX' |
| ✅ | XML: cantidad 1 caja | esperado 1.0, obtenido 1.0 |
| ✅ | XML: valor de la línea 12.00 | esperado 12.0, obtenido 12.0 |
| ⏭️ | Envío del CPE a SUNAT/OSE | sin credenciales: solo se arma el XML |

**Registros:** `product.product/14180` QA20 Amoxicilina 500 EDI, `pharmacy.presentation/133` Caja x 100, `account.move/31537` F FFI-00000004


### `al_pharmacy_stock`

#### ✅ Recepción con inspección, cuarentena y salida FEFO

**Pasos en pantalla:** Recibir cetirizina por lote: sin inspección no se valida; con inspección no conforme el lote queda en cuarentena; al despachar se toma primero el lote que vence antes y nunca el de cuarentena.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | sin inspección técnica la recepción no se valida |  |
| ✅ | recepción conforme validada | esperado 'done', obtenido 'done' |
| ✅ | recepción no conforme → lote en cuarentena | esperado 'quarantine', obtenido 'quarantine' |
| ✅ | FEFO: primero el lote que vence antes | esperado ['QA20-CTZ03', 'QA20-CTZ01'], obtenido ['QA20-CTZ03', 'QA20-CTZ01'] |
| ✅ | el lote en cuarentena no se reserva (aunque vence antes) |  |
| ✅ | reserva de 15 en lotes disponibles | esperado 15.0, obtenido 15.0 |
| ✅ | el técnico no libera la cuarentena |  |
| ✅ | el Q.F. libera el lote | esperado 'available', obtenido 'available' |
| ✅ | registro sanitario vencido: la recepción se bloquea |  |

**Registros:** `product.product/14181` QA20 Cetirizina 10 mg, `stock.picking/1998` Q20FA/IN/00001, `stock.picking/1999` Q20FA/IN/00002, `stock.picking/2000` Q20FA/IN/00003, `stock.picking/2001` Q20FA/OUT/00001

#### ✅ Alerta sanitaria, baja de lote y canje por vencer

**Pasos en pantalla:** Registrar la alerta DIGEMID de un lote vendido: se bloquea y lista los clientes; dar de baja el lote bloqueado; cargar al canje con la droguería los lotes por vencer y emitir la nota de crédito.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | el lote alertado queda bloqueado | esperado 'blocked', obtenido 'blocked' |
| ✅ | la alerta identifica a los clientes que lo compraron |  |
| ✅ | el lote bloqueado no se reserva |  |
| ✅ | baja validada | esperado 'done', obtenido 'done' |
| ✅ | desecho de inventario hecho | esperado 'done', obtenido 'done' |
| ✅ | el lote dado de baja queda en 0 | esperado 0.0, obtenido 0 |
| ✅ | descuento por vencer a 45 días: 20 % | esperado 20, obtenido 20.0 |
| ✅ | a 20 días: 40 % | esperado 40, obtenido 40.0 |
| ✅ | el cron marca el lote vencido | esperado 'expired', obtenido 'expired' |
| ✅ | canje: lotes por vencer y vencidos | esperado {'QA20-LOR45', 'QA20-LORVEN'}, obtenido {'QA20-LOR45', 'QA20-LORVEN'} |
| ✅ | canje valorizado a costo de compra | esperado 5.6000000000000005, obtenido 5.6 |
| ✅ | devolución a la droguería despachada | esperado 'done', obtenido 'done' |
| ✅ | nota de crédito de proveedor en borrador | esperado ('in_refund', 'draft'), obtenido ('in_refund', 'draft') |
| ✅ | importe de la nota de crédito | esperado 5.6, obtenido 5.6 |

**Registros:** `product.product/14182` QA20 Loratadina 10 mg, `stock.picking/2003` Q20FA/OUT/00002, `pharmacy.alert/18` QA20 ALERTA 105-2026, `pharmacy.destruction/20` ABD/2026/0020, `pharmacy.supplier.return/24` CJD/2026/0024, `account.move/31538` Borrador de nota de crédito de proveedor (Canje CJD/2026/002


### `al_pharmacy_prescription`

#### ✅ Receta: validación, dispensación parcial con genérico y tope

**Pasos en pantalla:** Registrar la receta de Zitromax 500 mg × 6, dispensar 3 del genérico (alternativa) y 3 de la marca; una 7.ª unidad se rechaza y la dispensación no se puede borrar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | sin prescriptor ni paciente la receta no se valida |  |
| ✅ | receta validada | esperado 'valid', obtenido 'valid' |
| ✅ | el genérico se registra como alternativa |  |
| ✅ | dispensación parcial | esperado 'partial', obtenido 'partial' |
| ✅ | receta dispensada por completo | esperado 'dispensed', obtenido 'dispensed' |
| ✅ | no se dispensa más de lo recetado |  |
| ✅ | la dispensación no se puede borrar |  |
| ✅ | libro de recetas imprime |  |
| ✅ | alerta de alergia del paciente al principio activo | esperado pharmacy.ingredient(135,), obtenido pharmacy.ingredient(135,) |
| ✅ | receta vencida no se dispensa |  |
| ✅ | el cron marca la receta vencida | esperado 'expired', obtenido 'expired' |

**Registros:** `product.product/14183` QA20 Zitromax 500, `product.product/14184` QA20 Azitromicina 500 tableta, `pharmacy.prescription/142` RX/2026/00142, `pharmacy.prescription/144` RX/2026/00144


### `al_l10n_pe_prescriber_cmp`

#### ❌ Verificación del médico en el CMP

**Pasos en pantalla:** Abrir «Consultar CMP» del médico (portal Conoce a tu médico) y registrar el resultado: solo el Q.F. puede marcarlo; un médico inhabilitado bloquea la receta.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | acción abre el portal del CMP | https://conoceatumedico.cmp.org.pe/ |
| ⏭️ | Consulta real al portal del CMP | servicio externo sin API: se verifica la URL generada |
| ✅ | el técnico no puede verificar al médico |  |
| ❌ | un Q.F. (grupo Químico farmacéutico, sin «Contactos: creación») registra la verificación | AccessError: Estos registros están restringidos.  QA20 qa20_qf_farmacia (id=3846) no tiene acceso 'escribir' a: - Contacto (res.partner)  Si necesita acceso, pregúntele a un administrador. — _pharmacy_set_cmp_status escribe el contacto con los permisos del usuario |
| ✅ | Q.F. registra «Habilitado» | esperado 'enabled', obtenido 'enabled' |
| ✅ | queda quién verificó | esperado res.users(3847,), obtenido res.users(3847,) |
| ✅ | médico inhabilitado: la receta no se valida |  |
| ✅ | sin colegiatura no se consulta el CMP |  |

**Registros:** `res.partner/9644` QA20 Dr. Jorge Salazar, `res.users/3847` QA20 qa20_qf_contactos, `pharmacy.prescription/145` RX/2026/00145


### `al_l10n_pe_pharmacy_controlled`

#### ✅ Controlados: lista, receta especial y folio de retención

**Pasos en pantalla:** Registrar clonazepam (lista IVA) y morfina (lista IIA): la lista fija la condición y el libro; la morfina exige receta especial de 3 días y datos del comprador; la receta queda retenida con folio.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | lista IIA → libro de estupefacientes | esperado 'narcotic', obtenido 'narcotic' |
| ✅ | lista IVA → libro de psicotrópicos | esperado 'psychotropic', obtenido 'psychotropic' |
| ✅ | la lista fija la condición de venta |  |
| ✅ | receta especial: vigencia máxima 3 días |  |
| ✅ | lista IIA no se dispensa con receta común |  |
| ✅ | receta especial exige datos del comprador |  |
| ✅ | receta retenida con folio | F-2026-00025 |
| ✅ | archivo de la receta retenida por 2 años | esperado datetime.date(2028, 10, 30), obtenido datetime.date(2028, 10, 30) |

**Registros:** `product.product/14185` QA20 Clonazepam 2 mg, `product.product/14186` QA20 Morfina 10 mg/mL, `pharmacy.prescription/147` RX/2026/00147, `pharmacy.prescription/148` RX/2026/00148

#### ✅ Libro de psicotrópicos y balance trimestral

**Pasos en pantalla:** Comprar 100 clonazepam y 50 metilfenidato, vender 10 y 5 con receta; imprimir el libro del 4.º trimestre y presentar el balance trimestral justificando una diferencia de stock.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | trimestre 4 de 2026 | esperado (datetime.date(2026, 10, 1), datetime.date(2026, 12, 31)), obtenido (datetime.date(2026, 10, 1), datetime.date(2026, 12, 31)) |
| ✅ | libro: ingreso 100 y salida 10, saldo 90 | esperado [(100.0, 0.0, 100.0), (0.0, 10.0, 90.0)], obtenido [(100.0, 0.0, 100.0), (0.0, 10.0, 90.0)] |
| ✅ | la salida lleva el folio de la receta | esperado 'F-2026-00026', obtenido 'F-2026-00026' |
| ✅ | libro de control impreso |  |
| ✅ | libro exportado a XLSX |  |
| ✅ | plazo de presentación: 15 días tras el trimestre | esperado datetime.date(2027, 1, 15), obtenido datetime.date(2027, 1, 15) |
| ✅ | balance del metilfenidato (IIIA) | esperado (0.0, 50.0, 5.0, 45.0, 45.0), obtenido (0.0, 50.0, 5.0, 45.0, 45.0) |
| ✅ | la lista IVA no va al balance |  |
| ✅ | diferencia con el stock detectada | esperado 1, obtenido 1 |
| ✅ | sin justificar la diferencia no se presenta |  |
| ✅ | balance presentado | esperado 'submitted', obtenido 'submitted' |
| ⏭️ | Presentación del balance ante DIGEMID/DIRIS | trámite externo; se valida el acta impresa |

**Registros:** `product.product/14187` QA20 Metilfenidato 10 mg, `stock.picking/2006` Q20FA/IN/00005, `pharmacy.prescription/149` RX/2026/00149, `stock.picking/2007` Q20FA/OUT/00005, `stock.picking/2008` Q20FA/IN/00006, `stock.picking/2009` Q20FA/OUT/00006, `pharmacy.controlled.report/26` pharmacy.controlled.report,26, `pharmacy.controlled.balance/13` Psicotrópicos T4 2026 · QA20 Botica


### `al_l10n_pe_pharmacy_digemid`

#### ✅ Observatorio de precios: pendientes y archivo de carga

**Pasos en pantalla:** Cambiar el precio de un medicamento con código DIGEMID y exportar el archivo del Observatorio del local (código 0099920): primera carga completa con precios con IGV.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | precio pendiente de reportar | esperado ('pending', 10.0), obtenido ('pending', 10.0) |
| ✅ | el cambio actualiza el mismo pendiente | esperado (1, 12.0), obtenido (1, 12.0) |
| ✅ | primera carga del mes: completa |  |
| ✅ | cabecera del formato del Observatorio | esperado ['CodEstab', 'CodProd', 'Precio 1', 'Precio 2'], obtenido ['CodEstab', 'CodProd', 'Precio 1', 'Precio 2'] |
| ✅ | fila con precio con IGV (12 × 1.18) | esperado [['0099920', 'QA20-DIG-0100', 14.16, 14.16]], obtenido [['0099920', 'QA20-DIG-0100', 14.16, 14.16]] |
| ✅ | el precio pasa a reportado | esperado 'reported', obtenido 'reported' |
| ✅ | envío registrado como carga completa | esperado ('sent', 'full'), obtenido ('sent', 'full') |
| ✅ | plazo de rectificación 7 días hábiles | esperado datetime.date(2026, 11, 10), obtenido datetime.date(2026, 11, 10) |
| ⏭️ | Carga real en el Observatorio de DIGEMID | portal externo sin credenciales; se valida el archivo |
| ✅ | sin código de establecimiento no se exporta |  |

**Registros:** `product.product/14188` QA20 Sitagliptina 50 mg, `pharmacy.observatory.submission/19` 10/2026 · QA20 Botica

#### ✅ Genéricos esenciales y reacción adversa

**Pasos en pantalla:** Calcular el cumplimiento de genéricos del petitorio en el local y registrar una sospecha de reacción adversa grave (plazo 24 h, queda en el cuaderno).

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | con stock del genérico DCI el ítem cumple |  |
| ✅ | el genérico se lista |  |
| ✅ | sin stock del genérico: incumple |  |
| ✅ | grave: notificar en 24 h | esperado datetime.datetime(2026, 10, 31, 12, 51, 1), obtenido datetime.datetime(2026, 10, 31, 12, 51, 1) |
| ✅ | la sospecha queda en el cuaderno | esperado 'adverse_event', obtenido 'adverse_event' |
| ✅ | marcada como notificada | esperado 'notified', obtenido 'notified' |
| ⏭️ | Notificación a DIGEMID (e-reporting) | servicio externo |

**Registros:** `pharmacy.essential.medicine/13` pharmacy.essential.medicine,13, `product.product/14189` QA20 Glucophage 850, `product.product/14190` QA20 Metformina 850 tableta, `pharmacy.generic.compliance/13` pharmacy.generic.compliance,13, `pharmacy.adverse.event/15` SRA/2026/0015


### `al_pharmacy_pos`

#### ✅ Dispensación en caja: receta, lote FEFO y rótulo fraccionado

**Pasos en pantalla:** Vender en el TPV 10 cápsulas de amoxicilina (venta con receta) indicando receta 000123, prescriptor y lote: se crea la receta dispensada; la caja solo ofrece lotes disponibles, el que vence antes primero.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | lotes ofrecidos: FEFO y sin el bloqueado | esperado ['QA20-AMX-SOON', 'QA20-AMX-LATE'], obtenido ['QA20-AMX-SOON', 'QA20-AMX-LATE'] |
| ✅ | precio por vencer sugerido en caja (lote a 30 días) | esperado 40, obtenido 40.0 |
| ✅ | venta pagada | paid |
| ✅ | receta registrada y dispensada | esperado 'dispensed', obtenido 'dispensed' |
| ✅ | prescriptor reconocido por su colegiatura | esperado res.partner(9640,), obtenido res.partner(9640,) |
| ✅ | paciente = cliente de la venta | esperado res.partner(9639,), obtenido res.partner(9639,) |
| ✅ | la dispensación guarda el lote | esperado stock.lot(344,), obtenido stock.lot(344,) |
| ✅ | origen de la dispensación = pedido del TPV | esperado 'QA20 Botica - 000001', obtenido 'QA20 Botica - 000001' |
| ✅ | receta incompleta: la venta se guarda y el cuaderno lo anota |  |
| ✅ | venta por blíster completo no lleva rótulo |  |
| ✅ | venta de unidades sueltas genera un rótulo | esperado 1, obtenido 1 |
| ✅ | rótulo con la cantidad | esperado 3, obtenido 3.0 |
| ✅ | rótulo impreso con lote y vencimiento |  |
| ⏭️ | Interfaz del TPV (popup de receta, selección de lote, descuento por vencer) | sin navegador: validado en backend |

**Registros:** `product.product/14191` QA20 Amoxicilina 500 cápsula, `pos.order/462` QA20 Botica - 000001, `pharmacy.prescription/150` RX/2026/00150, `pos.order/463` QA20 Botica - 000002, `product.product/14192` QA20 Loratadina 10 fracc, `pos.order/464` QA20 Botica - 000003, `pos.order/465` QA20 Botica - 000004


### `al_pharmacy_loyalty`

#### ✅ Club de salud: puntos por DNI sin medicamentos con receta

**Pasos en pantalla:** Crear el programa «Club de Salud» (0.25 punto por sol) y vender a la paciente identificada por DNI un bloqueador (S/8) y amoxicilina con receta (S/40): solo suma 2 puntos; el 10 % de socio no alcanza a la receta.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | exclusión de medicamentos con receta activa por defecto |  |
| ✅ | la regla excluye receta y controlados |  |
| ✅ | descuento «sobre el pedido» pasa a productos específicos | esperado 'specific', obtenido 'specific' |
| ✅ | el descuento solo alcanza al producto de venta libre | esperado product.product(14193,), obtenido product.product(14193,) |
| ✅ | no se puede regalar un medicamento con receta |  |
| ✅ | cliente identificado por DNI | {'PE_DNI': '40112233'} |
| ✅ | S/ 8 × 0.25 = 2 puntos; la amoxicilina no suma | esperado 2.0, obtenido 2.0 |
| ✅ | puntos acreditados a la tarjeta del DNI 40112233 | esperado 2.0, obtenido 2.0 |
| ⏭️ | Canje de puntos en el TPV (tour) | interfaz del TPV sin navegador |

**Registros:** `product.product/14193` QA20 Bloqueador FPS 50, `product.product/14194` QA20 Amoxicilina 500 club, `product.product/14195` QA20 Clonazepam 2 club, `loyalty.program/27` QA20 Club de Salud, `sale.order/324` S00324, `loyalty.card/48` QA20 Club de Salud: 0448-7614-47da


### `al_pharmacy_insurance`

#### ✅ Convenio con aseguradora: copago en caja y factura a la EPS

**Pasos en pantalla:** Vender paracetamol (10 + IGV) y losartán (20 + IGV) a una afiliada de «Salud Andina EPS»: el convenio cubre 19.24 y la paciente paga 16.16; al cerrar la caja se liquida y factura lo cubierto a la EPS.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | método «Convenio» como cuenta de cliente | esperado 'pay_later', obtenido 'pay_later' |
| ✅ | cobertura sin error | False |
| ✅ | cubre 80 % de 11.80 + 50 % de 23.60 − copago 2 = 19.24 | esperado 19.24, obtenido 19.24 |
| ✅ | en caja: un no afiliado se rechaza | QA20 Mario Cárdenas Ríos no es afiliado vigente del convenio QA20 Salud Andina · Plan regular. |
| ✅ | la caja no acepta cubrir más de lo calculado |  |
| ✅ | pedido con la parte cubierta | esperado 19.24, obtenido 19.24 |
| ✅ | pedido con la afiliada | esperado pharmacy.insurance.affiliate(30,), obtenido pharmacy.insurance.affiliate(30,) |
| ✅ | tope mensual: quedan 30 − 19.24 | esperado 10.76, obtenido 10.76 |

**Registros:** `product.product/14197` QA20 Paracetamol 500 convenio, `product.product/14198` QA20 Losartán 50 convenio, `res.partner/9648` QA20 Salud Andina EPS S.A., `res.partner/9649` QA20 María Torres Quispe, `pharmacy.insurance.agreement/34` QA20 Salud Andina · Plan regular, `pharmacy.insurance.affiliate/30` QA20 María Torres Quispe · QA20 Salud Andina · Plan regular , `pos.order/467` QA20 Botica - 000005


### `al_pharmacy_care`

#### ✅ Tratamiento crónico: cobertura, recordatorio y WhatsApp

**Pasos en pantalla:** Registrar el tratamiento de enalapril (1 tableta/día) de la paciente; con compras del genérico hace 40 días y de la marca hace 15 (en el TPV) el tratamiento queda cubierto 20 días más y con PDC 67 %.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | sin compras: «sin compra» | esperado 'no_purchase', obtenido 'no_purchase' |
| ✅ | última compra hace 15 días | esperado datetime.date(2026, 10, 15), obtenido datetime.date(2026, 10, 15) |
| ✅ | compras encadenadas: cubierto hasta hoy + 20 | esperado datetime.date(2026, 11, 19), obtenido datetime.date(2026, 11, 19) |
| ✅ | próxima reposición (recordatorio 5 días antes) | esperado datetime.date(2026, 11, 14), obtenido datetime.date(2026, 11, 14) |
| ✅ | estado al día | esperado 'ok', obtenido 'ok' |
| ✅ | PDC 41/61 días | esperado 67.2, obtenido 67.2 |
| ✅ | PDC < 80 %: no adherente |  |
| ✅ | enlace de WhatsApp con +51 | https://wa.me/51987654321?text=Hola%20QA20%20Julia%20Ramos%20Quispe%2C%20le%20escribimos%20de%20OLANO%20IT%20S.A.C.%20%28dev%29.%20Su%20QA20%20Enalabrand%2010%20le%20alcanza%20hasta%20el%2019/11/2026.%20%C2%BFDesea%20que%20se%20lo%20separemos%3F%20Puede%20recogerlo%20o%20pedirlo%20por%20aqu%C3%AD. |
| ✅ | un solo tratamiento activo por producto |  |
| ✅ | tratamiento atrasado | esperado 'late', obtenido 'late' |
| ✅ | 10 días de atraso | esperado 10, obtenido 10 |
| ✅ | actividad de recordatorio creada | esperado 1, obtenido 1 |
| ✅ | el recordatorio no se repite | esperado 1, obtenido 1 |
| ✅ | el TPV consulta los tratamientos por reponer del cliente | [] |
| ✅ | el tratamiento toma la posología de la receta | esperado '1 tableta cada 24 horas', obtenido '1 tableta cada 24 horas' |
| ⏭️ | Envío real del recordatorio por WhatsApp/correo | canal externo; se valida enlace y actividad |

**Registros:** `product.product/14199` QA20 Enalabrand 10, `product.product/14200` QA20 Enalapril 10 tableta, `res.partner/9650` QA20 Julia Ramos Quispe, `pharmacy.treatment/34` QA20 Julia Ramos Quispe · QA20 Enalabrand 10, `pos.order/468` QA20 Botica - 000006, `pos.order/469` QA20 Botica - 000007, `res.partner/9651` QA20 Pedro Atrasado, `pharmacy.treatment/36` QA20 Pedro Atrasado · QA20 Enalapril 10 tableta, `pharmacy.treatment/37` QA20 Julia Ramos Quispe · QA20 Enalapril 10 tableta


### `al_pharmacy_replenishment`

#### ✅ Pedido sugerido por ventas del TPV y faltantes

**Pasos en pantalla:** Vender 30 losartán en caja, anotar faltantes (2 losartán y 1 insulina) y calcular el pedido sugerido a 15 días: 20 losartán (2 cajas de 10) a la Droguería; crear las órdenes de compra por proveedor.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | fórmula: 1/día × 15 + 2 − 5 = 12 → múltiplo de 10 = 20 | esperado 20, obtenido 20 |
| ✅ | cubierto por stock y lo que llega: 0 | esperado 0, obtenido 0.0 |
| ✅ | losartán: vendido 30, faltante 2, stock 5 → 20 | esperado (30.0, 1.0, 2.0, 5.0, 10.0, 20.0), obtenido (30.0, 1.0, 2.0, 5.0, 10.0, 20.0) |
| ✅ | proveedor del losartán | esperado res.partner(9636,), obtenido res.partner(9636,) |
| ✅ | insulina sin ventas: pide el faltante | esperado 1.0, obtenido 1.0 |
| ✅ | OC en la unidad de compra: 2 cajas de 10 | esperado (uom.uom(184,), 2.0), obtenido (uom.uom(184,), 2.0) |
| ✅ | OC en borrador | esperado {'draft'}, obtenido {'draft'} |
| ✅ | faltante del losartán pasa a pedido | esperado 'ordered', obtenido 'ordered' |
| ✅ | faltante sin producto sigue pendiente | esperado 'pending', obtenido 'pending' |

**Registros:** `res.partner/9652` QA20 Distribuidora del Sur, `product.product/14201` QA20 Losartán 50 reposición, `product.product/14202` QA20 Insulina NPH reposición, `pos.order/471` QA20 Botica - 000009, `pharmacy.shortage/35` QA20 Losartán 50 reposición, `pharmacy.shortage/36` QA20 Insulina NPH reposición, `pharmacy.shortage/37` QA20 Colirio lubricante 15 ml, `purchase.order/960` P00960


### `al_pharmacy_insurance`

#### ⚠️ Cierre de caja y liquidación a la aseguradora

**Pasos en pantalla:** Cerrar la caja de la botica (el «Convenio» no queda como cuenta por cobrar de la caja) y crear la liquidación del mes: factura a la EPS por 19.24 con el DNI y número de afiliado.

| Estado | Comprobación | Detalle |
|---|---|---|
| ⚠️ | Cuenta bancaria no confiable en la compañía | 191-9912345-0-71 - QA20 P1 BCP, 1917000123456 - Banco de Crédito del Perú (de otra fase) impide a un usuario real publicar el cierre de caja y las facturas; se cierra como superusuario, que la omite |
| ✅ | sesión de caja cerrada | esperado 'closed', obtenido 'closed' |
| ✅ | el cierre no registra cuenta por cobrar del convenio |  |
| ✅ | la liquidación carga el pedido cubierto | esperado pos.order(467,), obtenido pos.order(467,) |
| ⚠️ | Cuenta bancaria de la compañía no confiable en la factura | 191-9912345-0-71 - QA20 P1 BCP (creada por otra fase) bloquea la publicación; se quita de la factura |
| ✅ | factura de cliente | esperado 'out_invoice', obtenido 'out_invoice' |
| ✅ | facturada a la EPS | esperado res.partner(9648,), obtenido res.partner(9648,) |
| ✅ | importe = lo cubierto | esperado 19.24, obtenido 19.24 |
| ✅ | la línea identifica DNI y número de afiliado | QA20 Paracetamol 500 convenio · 260-225-000005 · Comprobante POSC/2026/00003 · DNI 44556677 · Paciente QA20 María Torres Quispe · Afiliado QA20-SA-001 |
| ✅ | el cierre contabiliza la parte del paciente (y otras ventas de la caja) | 16.16 |
| ✅ | un pedido se liquida una sola vez |  |
| ✅ | reporte de la liquidación |  |
| ⏭️ | Envío del CPE de la factura a la EPS a SUNAT | sin credenciales |

**Registros:** `pharmacy.insurance.liquidation/32` LIQ/2026/0032, `account.move/31541` F FFI-00000005 (Liquidación LIQ/2026/0032 · QA20 Salud [...]


### `al_pharmacy_website`

#### ✅ Tienda web: genéricos primero, receta adjunta y aprobación del Q.F.

**Pasos en pantalla:** En la tienda, la ficha de Amoxival muestra primero los genéricos; un controlado no entra al carrito; el pedido con receta queda esperando la imagen y la aprobación del Q.F.; la insulina sale con cadena de frío.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | alternativas en la web: genérico DCI y luego de marca | esperado [14145, 14146], obtenido [14145, 14146] |
| ✅ | un controlado no se agrega al carrito | QA20 Clonazepam web es un medicamento controlado: solo se vende en el local, con la receta especial. |
| ✅ | el pedido web exige receta |  |
| ✅ | estado: por subir receta | esperado 'to_upload', obtenido 'to_upload' |
| ✅ | sin receta no se paga |  |
| ✅ | receta subida: por revisar | esperado 'to_review', obtenido 'to_review' |
| ✅ | no se confirma sin la aprobación del Q.F. |  |
| ✅ | un vendedor no aprueba recetas |  |
| ✅ | receta aprobada | esperado 'approved', obtenido 'approved' |
| ✅ | queda el Q.F. que revisó | esperado res.users(3846,), obtenido res.users(3846,) |
| ✅ | pedido confirmado tras la aprobación | esperado 'sale', obtenido 'sale' |
| ✅ | pedido con cadena de frío |  |
| ✅ | el albarán hereda la cadena de frío |  |
| ✅ | el albarán impreso avisa «CADENA DE FRÍO» |  |
| ⏭️ | Páginas de la tienda y subida de receta por el portal (HTTP) | sin navegador; controladores probados en los tests HttpCase |

**Registros:** `product.product/14203` QA20 Amoxival 500, `product.product/14204` QA20 Amoxicilina 500 web, `product.product/14205` QA20 Amoxil genérico 500, `product.product/14206` QA20 Clonazepam web, `product.product/14207` QA20 Insulina NPH web, `res.partner/9653` QA20 Rosa Quispe web, `sale.order/325` S00325, `sale.order/326` S00326, `sale.order/327` S00327


### `al_industry_base`

#### ✅ Paquete de instalación: módulo y datos declarados presentes

**Pasos en pantalla:** Abrir Aplicaciones y comprobar que el paquete está instalado con sus datos y menús.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | módulo instalado | esperado 'installed', obtenido 'installed' |
| ✅ | dependencias instaladas (4) | [] |
| ✅ | registros de datos declarados presentes (4) | [] |
| ✅ | menús declarados presentes (1) |  |
| ✅ | modelo del asistente de industrias registrado | ['res.partner.industry', 'al.industry'] |
| ⏭️ | Instalación sobre base vacía y datos demo | paquete para bases nuevas: no se reinstala aquí |


### `al_industry_construction`

#### ✅ Paquete de instalación: módulo y datos declarados presentes

**Pasos en pantalla:** Abrir Aplicaciones y comprobar que el paquete está instalado con sus datos y menús.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | módulo instalado | esperado 'installed', obtenido 'installed' |
| ✅ | dependencias instaladas (9) | [] |
| ✅ | registros de datos declarados presentes (13) | [] |
| ⏭️ | Instalación sobre base vacía y datos demo | paquete para bases nuevas: no se reinstala aquí |


### `al_industry_ecommerce`

#### ✅ Paquete de instalación: módulo y datos declarados presentes

**Pasos en pantalla:** Abrir Aplicaciones y comprobar que el paquete está instalado con sus datos y menús.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | módulo instalado | esperado 'installed', obtenido 'installed' |
| ✅ | dependencias instaladas (8) | [] |
| ✅ | registros de datos declarados presentes (9) | [] |
| ⏭️ | Instalación sobre base vacía y datos demo | paquete para bases nuevas: no se reinstala aquí |


### `al_industry_furniture`

#### ✅ Paquete de instalación: módulo y datos declarados presentes

**Pasos en pantalla:** Abrir Aplicaciones y comprobar que el paquete está instalado con sus datos y menús.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | módulo instalado | esperado 'installed', obtenido 'installed' |
| ✅ | dependencias instaladas (2) | [] |
| ✅ | registros de datos declarados presentes (12) | [] |
| ⏭️ | Instalación sobre base vacía y datos demo | paquete para bases nuevas: no se reinstala aquí |


### `al_industry_pharmacy`

#### ✅ Paquete de instalación: módulo y datos declarados presentes

**Pasos en pantalla:** Abrir Aplicaciones y comprobar que el paquete está instalado con sus datos y menús.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | módulo instalado | esperado 'installed', obtenido 'installed' |
| ✅ | dependencias instaladas (30) | [] |
| ✅ | registros de datos declarados presentes (22) | [] |
| ⏭️ | Instalación sobre base vacía y datos demo | paquete para bases nuevas: no se reinstala aquí |


### `al_industry_restaurant`

#### ✅ Paquete de instalación: módulo y datos declarados presentes

**Pasos en pantalla:** Abrir Aplicaciones y comprobar que el paquete está instalado con sus datos y menús.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | módulo instalado | esperado 'installed', obtenido 'installed' |
| ✅ | dependencias instaladas (9) | [] |
| ✅ | registros de datos declarados presentes (14) | [] |
| ⏭️ | Instalación sobre base vacía y datos demo | paquete para bases nuevas: no se reinstala aquí |


### `al_industry_retail`

#### ✅ Paquete de instalación: módulo y datos declarados presentes

**Pasos en pantalla:** Abrir Aplicaciones y comprobar que el paquete está instalado con sus datos y menús.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | módulo instalado | esperado 'installed', obtenido 'installed' |
| ✅ | dependencias instaladas (11) | [] |
| ✅ | registros de datos declarados presentes (18) | [] |
| ⏭️ | Instalación sobre base vacía y datos demo | paquete para bases nuevas: no se reinstala aquí |


## Fase 5 · Proyectos y construcción


### `al_construction_planner`

#### ✅ Obra QA20: tipologías, árbol del piso 05 y generación del plan (W-01)

**Pasos en pantalla:** planner_demo_data.py con prefijo QA20: 8 tipologías, árbol Piso › Dpto › Ambiente › Módulo, asistente de generación y costo del maestro

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | material planificado | esperado 6642.91, obtenido 6642.91 |
| ✅ | contrata planificada | esperado 2301.53, obtenido 2301.53 |
| ✅ | total del plan | esperado 8944.44, obtenido 8944.44 |
| ✅ | módulos generados en el árbol | esperado 66, obtenido 66 |
| ✅ | líneas del plan generadas | 226 |

**Registros:** `project.project/1891` QA20 MOMEN-35-26, `construction.resource.plan/733` PLR/2026/00733 · v1, `project.task/19244` Piso 05, `res.partner/9382` QA20 Leandro (instalación), `res.partner/9383` QA20 Armado Gonza


### `al_construction_planner_approvals`

#### ✅ Aprobación por niveles del plan y versión 2 (replan, W-12)

**Pasos en pantalla:** planner_demo_baseline.py: reglas tier.definition (restringidas a la obra QA20), solicitar aprobación, validar tier, replanificar (v2), precio ponderado 6 meses

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | el plan generó revisiones tier | ['QA20 Nivel 1: jefatura de proyectos'] |
| ✅ | v1 aprobada tras validar el nivel 1 | esperado 'approved', obtenido 'approved' |
| ✅ | v1 con presupuesto analítico | QA20 MOMEN-35-26 · PLR/2026/00733 · v1 |
| ✅ | v2 en borrador | esperado 'draft', obtenido 'draft' |
| ✅ | v2 desciende de v1 |  |
| ✅ | v2: costo ponderado de compras aplicado a la melamina | 121.62 |

**Registros:** `construction.resource.plan/733` PLR/2026/00733 · v1, `construction.resource.plan/734` PLR/2026/00734 · v2, `tier.definition/3512` QA20 Nivel 1: jefatura de proyectos, `tier.definition/3513` QA20 Nivel 2: gerencia (más de S/ 100 000)


### `al_construction_planner_purchase`

#### ✅ Compra masiva, requerimiento de obra, exceso y OF desde el plan

**Pasos en pantalla:** planner_demo_supply.py: W-02 (purchase.request), W-03 (construction.material.request), W-10 (exceso con justificación), W-04 (mrp.production)

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | solicitud de compra con líneas | 2 |
| ✅ | requerimiento enviado a aprobación | to_approve |
| ✅ | requerimiento marca exceso sobre el plan | esperado 'exceeded', obtenido 'exceeded' |
| ✅ | OF creada | WH/MO/00390 draft |
| ✅ | el plan registra asignaciones | 38 |

**Registros:** `purchase.request/440` PR00440, `construction.material.request/762` RQO/2026/00762, `construction.material.request/763` RQO/2026/00763, `mrp.production/536` WH/MO/00390


### `al_construction_planner_subcontract`

#### ✅ Contrata (W-05), avance validado y liquidación semanal (P-08)

**Pasos en pantalla:** planner_demo_contracts.py: asignar instalación a Leandro, OC de servicio, avance con foto, liquidación del 05/11 (bruto 380.88, neto 342.79)

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | OC de servicio confirmada | esperado 'purchase', obtenido 'purchase' |
| ✅ | OC de servicio por la instalación del piso | esperado 941.17, obtenido 941.17 |
| ✅ | bruto de la liquidación | esperado 380.88, obtenido 380.88 |
| ✅ | neto de la liquidación (retención 10 %) | esperado 342.79, obtenido 342.79 |
| ✅ | liquidación enviada | submitted |

**Registros:** `purchase.order/938` P00938, `construction.contract.settlement/202` LIQ/2026/00207


### `al_construction_planner_crew`

#### ✅ Cuadrilla (W-06) y hoja de horas con costo de personal

**Pasos en pantalla:** planner_demo_control.py: actividad en horas, 2 obreros a S/ 9.50, cuadrilla 2 semanas, 6 h registradas

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | horas ejecutadas en la línea de personal propio | esperado 6.0, obtenido 6.0 |
| ✅ | costo real = 6 h × S/ 9.50 | esperado 57.0, obtenido 57.0 |
| ✅ | comprometido por la cuadrilla | 95.0 |
| ✅ | turnos de planificación de la cuadrilla | esperado 4, obtenido 4 |

**Registros:** `hr.employee/928` QA20 Obrero propio 1, `hr.employee/929` QA20 Obrero propio 2, `construction.labor.activity/4343` QA20 Instalación con personal propio, `planning.slot/68` QA20 Instalador propio - QA20 MOMEN-35-26 💬, `planning.slot/66` QA20 Instalador propio - QA20 MOMEN-35-26 💬, `planning.slot/67` QA20 Instalador propio - QA20 MOMEN-35-26 💬, `planning.slot/65` QA20 Instalador propio - QA20 MOMEN-35-26 💬


### `al_construction_planner_sale`

#### ✅ OV del contrato, entregas semanales y valorización 1 facturada

**Pasos en pantalla:** planner_demo_income.py: OV, calendario de ingresos, 3 entregas, valorización enviada/observada/confirmada con acta y factura publicada

*Resultado de la repetición proyectos_ingreso (en «proyectos» quedó FALLA).*

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | OV confirmada | esperado 'sale', obtenido 'sale' |
| ✅ | valorización facturada | esperado 'invoiced', obtenido 'invoiced' |
| ✅ | factura publicada | esperado 'posted', obtenido 'posted' |
| ✅ | fondo de garantía retenido | 2.43 |

**Registros:** `sale.order/292` S00292 (Contrato MOMEN-35-26), `construction.valuation/74` VAL/2026/00074 · Valorización 1, `account.move/31448` F FFI-00000001 (VAL/2026/00074)

#### ✅ Cronograma valorizado (plan y real) con cobro conciliado

**Pasos en pantalla:** planner_demo_schedule.py: cobro conciliado y construction.schedule.report.get_schedule

*Resultado de la repetición proyectos_ingreso (en «proyectos» quedó FALLA).*

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | cronograma: costo planificado | {'cost': 8142.38, 'revenue': 7592.47, 'valuation': 7592.47, 'invoice': 7592.47, 'collection': 7212.85, 'guarantee': 379.62, 'collection_total': 7592.47, 'margin': -549.91, 'max_gap': 8142.38, 'max_gap_week': '2026-11-26'} |
| ✅ | cronograma: ingreso real | {'cost': 52.2, 'revenue': 48.67, 'valuation': 48.67, 'invoice': 48.67, 'collection': 48.67, 'guarantee': 0.0, 'collection_total': 48.67, 'margin': -3.53, 'max_gap': 52.2, 'max_gap_week': '2026-12-10'} |
| ✅ | factura cobrada | esperado True, obtenido True |


### `al_construction_material_request`

#### ✅ Requerimiento de obra aprobado (tier), procesado y despachado a la obra

**Pasos en pantalla:** RQO del piso (W-03): validar revisión, «Procesar» (logística) → solicitud de compra del faltante, recepción en el central y despacho a la ubicación de obra

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | requerimiento aprobado tras las revisiones | esperado 'approved', obtenido 'approved' |
| ✅ | requerimiento en proceso | esperado 'in_progress', obtenido 'in_progress' |
| ✅ | el faltante generó solicitud de compra | ['PR00441'] |
| ✅ | transferencias hacia la obra creadas | ['OBRA00429'] |

**Registros:** `construction.material.request/762` RQO/2026/00762, `purchase.request/441` PR00441


### `purchase_request`

#### ✅ Solicitud de compra: aprobar y generar OC con el asistente

**Pasos en pantalla:** purchase.request (W-02 compra masiva): to_approve → approved; asistente purchase.request.line.make.purchase.order con proveedor QA20

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | solicitudes aprobadas | ['approved', 'approved'] |
| ✅ | OC generadas desde la solicitud | ['P00940'] |
| ✅ | cada línea de la solicitud enlazada a la OC |  |

**Registros:** `purchase.order/940` P00940


### `purchase_tier_validation`

#### ✅ OC con aprobación por niveles (regla QA20 por proveedor)

**Pasos en pantalla:** tier.definition sobre purchase.order con dominio del proveedor QA20: confirmar sin validar falla, request_validation, validate_tier y confirmar

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | la OC del proveedor QA20 necesita validación |  |
| ✅ | confirmar sin validar está bloqueado | Esta acción necesita ser validada para al menos un registro. Revisiones pendientes:  - QA2 |
| ✅ | revisión creada en P00940 | ['QA20 OC: jefatura de compras'] |
| ✅ | OC P00940 validada | esperado 'validated', obtenido 'validated' |
| ✅ | OC P00940 confirmada tras la validación | purchase |

**Registros:** `tier.definition/3514` QA20 OC: jefatura de compras


### `base_tier_validation`

#### ✅ Motor de revisiones: estados, revisores y bloqueo de escritura

**Pasos en pantalla:** tier.review de la OC y del plan QA20; escribir en un documento en revisión queda bloqueado

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | revisiones de OC aprobadas | ['approved', 'approved'] |
| ✅ | cada revisión registra quién la hizo | ['QA20 Jefe de obra'] |
| ✅ | requerimiento con exceso queda con revisiones pendientes | ['Exceso sobre el plan: jefatura del planificador'] |
| ✅ | escritura en documento en revisión bloqueada | No puedes editar estos campos durante la validación. - Notas  Solo estos campos  |


### `al_construction_planner_purchase`

#### ✅ Recepción de la OC y despacho a la obra; tablero de abastecimiento

**Pasos en pantalla:** validar recepción de la OC, luego la transferencia pendiente a la obra; construction.supply.board.get_board (pantalla OWL)

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | recepción WH/IN/00381 validada | esperado 'done', obtenido 'done' |
| ✅ | cantidad recibida en obra registrada en el requerimiento | 1800.0 |
| ✅ | estado del requerimiento | done |
| ✅ | obra QA20 en el selector del tablero |  |
| ✅ | tablero de abastecimiento con datos | ['alerts', 'currency_symbol', 'horizon_end', 'plan_id', 'plan_name', 'plan_state', 'project_id', 'rows'] |
| ⏭️ | render OWL del tablero de abastecimiento | sin navegador |

**Registros:** `stock.picking/1769` WH/IN/00381, `stock.picking/1768` OBRA00429


### `al_construction_planner_mrp`

#### ✅ OF desde el plan (W-04): componentes por etapa y enlace al plan

**Pasos en pantalla:** OF del Dpto 502 creada por planner_demo_supply; confirmar y revisar etapa de consumo y plan

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | OF enlazada al plan vigente | PLR/2026/00733 · v1 |
| ✅ | OF con componentes de la BOM de la tipología | 7 |
| ✅ | asignación del plan registra la OF | 115 |

**Registros:** `mrp.production/536` WH/MO/00390


### `al_construction_planner_production`

#### ✅ Accesorios de armado pedidos desde la OF

**Pasos en pantalla:** quitar la bisagra (Armado) de la OF, confirmar, «Pedir accesorios» y enviar sin cambios → el accesorio entra a la OF

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | OF confirmada | confirmed |
| ✅ | propone la bisagra del plan | [('QA20 Bisagra lateral Danco', 12.0)] |
| ✅ | pedido sin cambios aplicado a la OF | esperado 'done', obtenido 'done' |
| ✅ | bisagras agregadas a la OF | esperado 12.0, obtenido 12.0 |

**Registros:** `construction.accessory.request/28` ACC/2026/00028


### `al_construction_planner_approvals_mrp`

#### ✅ Exceso de la OF frente a lo presupuestado: aprueba el jefe de producción

**Pasos en pantalla:** OF Dpto 503, +0.2 de melamina blanca, margen del jefe 5 % (temporal en la compañía) → exceso aprobado con motivo y registrado en construction.exceed.log

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | OF marcada con exceso | esperado 'exceeded', obtenido 'exceeded' |
| ✅ | monto del exceso | 33.6 |
| ✅ | comparativo: cambio de cantidad en la melamina | esperado 'quantity', obtenido 'quantity' |
| ✅ | el jefe de producción puede aprobar (dentro del margen) | esperado 'approve', obtenido 'approve' |
| ✅ | exceso aprobado | esperado 'approved', obtenido 'approved' |
| ✅ | exceso registrado en el log | ['QA20 Melamina MDP blanco fantasía'] |

**Registros:** `mrp.production/537` WH/MO/00391


### `al_construction_planner_mrp_request`

#### ✅ Planchas enteras en el despacho del requerimiento

**Pasos en pantalla:** UdM plancha (construction_whole_sheet), 10.6 en stock, requerimiento de 13.3 → despacha 10 y compra 4 (opción de compañía activada solo durante el caso)

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | requerimiento aprobado | esperado 'approved', obtenido 'approved' |
| ✅ | despacha planchas enteras | esperado 10.0, obtenido 10.0 |
| ✅ | compra lo que falta en planchas enteras | esperado 4.0, obtenido 4.0 |
| ✅ | redondeo a plancha entera | esperado 0.7, obtenido 0.7 |

**Registros:** `product.product/13829` QA20 Melamina RH 18 mm (plancha), `construction.material.request/764` RQO/2026/00764


### `al_construction_planner_furniture`

#### ✅ Tipología de mueble: módulos, piezas y clasificación

**Pasos en pantalla:** tipología QA20-C04 con módulos de microondas y zócalo, piezas PUERTA y materiales por etapa

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | microondas es módulo especial | esperado 'special', obtenido 'special' |
| ✅ | tipo especial microondas | esperado 'microwave', obtenido 'microwave' |
| ✅ | zócalo detectado | esperado 'plinth', obtenido 'plinth' |
| ✅ | zócalo sin unión | esperado 'none', obtenido 'none' |
| ✅ | módulo con piezas y materiales |  |

**Registros:** `construction.typology/1202` QA20 COCINA 04 a medida


### `al_construction_planner_subcontract`

#### ✅ Liquidación semanal: validar, aprobar (tier), recepción en la OC y factura

**Pasos en pantalla:** LIQ del 05/11: action_validate, validate_tier de la jefatura, recepción en la OC de servicio y factura de proveedor con vencimiento el sábado 07/11

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | liquidación aprobada | esperado 'approved', obtenido 'approved' |
| ✅ | factura de proveedor | esperado 'in_invoice', obtenido 'in_invoice' |
| ✅ | base de la factura = bruto de la liquidación | esperado 380.88, obtenido 380.88 |
| ✅ | vence el sábado de pago | esperado '2026-11-07', obtenido '2026-11-07' |
| ✅ | recepción registrada en la OC de servicio | 52.85 |
| ✅ | factura enlazada a la OC de servicio |  |

**Registros:** `account.move/31393` Borrador de factura (LIQ/2026/00207)


### `al_construction_planner_subcontract_purchase`

#### ✅ Material extra descontado a la contrata en su siguiente liquidación

**Pasos en pantalla:** requerimiento extra (reposición) con «Descontar a la contrata» Leandro; liquidación del 12/11 lo toma como descuento

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | monto a descontar = estimado | 5.0 |
| ✅ | extra aprobado | esperado 'approved', obtenido 'approved' |
| ✅ | el extra entra como descuento en la liquidación | ['RQO/2026/00765'] |
| ✅ | descuento en la liquidación | esperado 5.0, obtenido 5.0 |

**Registros:** `construction.material.request/765` RQO/2026/00765, `construction.contract.settlement/203` LIQ/2026/00208


### `al_construction_planner_subcontract`

#### ✅ Valorización del contratista con condiciones (adelanto, deductivo, fondo de garantía)

**Pasos en pantalla:** obra QA20 OBR-01 tabiquería: condición de la compañía (data), adelanto, 1 000 m² + adicional 100 u, deductivo 650 → Valorizado 01 por 35 532.75 a pagar

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | plan de la obra con condiciones aprobado | esperado 'approved', obtenido 'approved' |
| ✅ | total contractual con el esquema de la condición | esperado 94121.52, obtenido 94121.52 |
| ✅ | la OC lleva condiciones copiadas |  |
| ✅ | adelanto 20 % del subtotal contractual | esperado 15952.8, obtenido 15952.8 |
| ✅ | adelanto publicado | esperado 'posted', obtenido 'posted' |
| ✅ | título de la valorización | Valorizado 01 - Arquitectura |
| ✅ | costo directo valorizado | esperado 38200.0, obtenido 38200.0 |
| ✅ | adicionales | esperado 1800.0, obtenido 1800.0 |
| ✅ | total con IGV | esperado 47377.0, obtenido 47377.0 |
| ✅ | amortización del adelanto | esperado 9475.4, obtenido 9475.4 |
| ✅ | fondo de garantía | esperado 2368.85, obtenido 2368.85 |
| ✅ | total a pagar | esperado 35532.75, obtenido 35532.75 |
| ✅ | valorización aprobada | esperado 'approved', obtenido 'approved' |
| ✅ | factura de la valorización | esperado 37901.6, obtenido 37901.6 |

**Registros:** `project.project/1892` QA20 OBR-01 Tabiquería, `construction.resource.plan/735` PLR/2026/00735 · v1, `purchase.order/941` P00941, `account.move/31394` F F001-00031394 (Adelanto P00941), `construction.contract.settlement/204` LIQ/2026/00209 · Valorizado 01 - Arquitectura, `account.move/31395` Borrador de factura (Valorizado 01 - Arquitectura)


### `al_construction_planner_subcontract_sale`

#### ✅ Adicional de obra agregado a la OC de la contrata

**Pasos en pantalla:** construction.change.order «additional» aprobado y «Agregar a la orden de contrata»

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | cambio aprobado se puede agregar a la OC |  |
| ✅ | línea agregada a la OC de la contrata | P00941 |
| ✅ | línea marcada como adicional |  |
| ✅ | cantidad del adicional | esperado 50.0, obtenido 50.0 |

**Registros:** `construction.change.order/36` CAM/2026/00036


### `al_construction_planner_budget`

#### ✅ Presupuesto analítico del plan y control de la OC contra el presupuesto

**Pasos en pantalla:** budget.analytic de la v1 con líneas; OC de material con analítica de la obra: estado del control

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | presupuesto con líneas | 1 |
| ✅ | presupuesto con montos | esperado True, obtenido True |
| ✅ | OC con estado del control de presupuesto | ok |
| ✅ | importes de la OC por línea de presupuesto calculados | 0 |

**Registros:** `budget.analytic/436` QA20 MOMEN-35-26 · PLR/2026/00733 · v1


### `al_construction_planner_sale_furniture`

#### ✅ Partida del contrato por familia de la tipología

**Pasos en pantalla:** OV del contrato con una partida «Cocinas» sin familia: el resolver de partidas asigna las líneas del plan de cocinas a esa partida; con familia «kitchen» también

*Resultado de la repetición proyectos_ingreso (en «proyectos» quedó FALLA).*

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | línea del plan asignada a la partida «Cocinas» | S00292 - Cocinas (QA20 Inmobiliaria MOMEN) |
| ✅ | con familia kitchen la partida toma las cocinas | S00292 - Cocinas (QA20 Inmobiliaria MOMEN) |


### `al_construction_planner_spreadsheet`

#### ✅ Hoja de presupuesto de la cotización (documents.spreadsheet)

**Pasos en pantalla:** action_construction_open_spreadsheet en la OV QA20: documento «budget» con sus hojas y filas Odoo

*Resultado de la repetición proyectos_ingreso (en «proyectos» quedó FALLA).*

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | un documento de hoja por cotización | esperado 1, obtenido 1 |
| ✅ | tipo de hoja presupuesto | esperado 'budget', obtenido 'budget' |
| ✅ | plantilla con las hojas del libro | ['INSTRUCCIONES', 'OBRA', 'INSUMOS', 'APU', 'APU_DETALLE', 'PRESUPUESTO', 'PLAN', 'LISTAS', 'REFERENCIAS', 'ERRORES'] |
| ✅ | filas Odoo de la hoja (RPC de la pantalla) | ['OBRA', 'INSUMOS', 'APU', 'APU_DETALLE', 'PLAN'] |
| ✅ | validación de la hoja responde | 4 |
| ⏭️ | edición visual de la hoja (o-spreadsheet) | sin navegador |

**Registros:** `documents.document/7235` Presupuesto y plan · S00292


### `al_construction_planner_spreadsheet_furniture`

#### ✅ Hoja de trabajo de la obra con el maestro de mobiliario

**Pasos en pantalla:** project.action_construction_open_spreadsheet: hojas del maestro (ARBOL, TIPOLOGIAS…) y listas Odoo

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | acción abre la hoja de la obra |  |
| ✅ | hojas del maestro de mobiliario | ['LEEME', 'RESUMEN', 'CATALOGO', 'TIPOLOGIAS', 'MUEBLES', 'MODULOS', 'ACTIVIDADES', 'BOM', 'PIEZAS', 'PRODUCTOS NUEVOS', 'TARIFAS', 'OBRA', 'CONTRATOS', 'HITOS', 'VENTA', 'MO PROPIA', 'ARBOL', 'VARIANTES', 'ETO', 'REFERENCIAS', '_LISTAS'] |
| ✅ | listas ODOO.LIST enlazadas | ['construction.labor.activity', 'construction.typology', 'product.category', 'product.product'] |

**Registros:** `documents.document/7176` Maestro de planificación · QA20 MOMEN-35-26


### `al_construction_attendance`

#### ✅ Sede de la obra, marcación de contrata y de personal propio, avance con asistencia

**Pasos en pantalla:** l10n_pe.hr.construction.site de la obra QA20, trabajador de contrata con SCTR vencido, hr.attendance con GPS → sede y distancia; avance con attendance_ok

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | distancia a la sede | esperado 0.0, obtenido 0.0 |
| ✅ | a ~400 m queda fuera del radio |  |
| ✅ | 7:55 en Lima es tardanza |  |
| ✅ | trabajador con SCTR vencido marcado (el aviso «al marcar» lo pone el quiosco) |  |
| ✅ | marcación toma la sede más cercana | esperado l10n_pe.hr.construction.site(54,), obtenido l10n_pe.hr.construction.site(54,) |
| ✅ | distancia registrada | 66.7 |
| ✅ | avance de la contrata con asistencia ese día | AVN/2026/01458 |
| ⏭️ | quiosco /obra/quiosco (HTTP) | controlador web: sin servidor de pruebas en el shell |

**Registros:** `l10n_pe.hr.construction.site/54` QA20 Sede MOMEN, `construction.contractor.worker/8` QA20 Juan Gonza, `construction.contractor.attendance/7` construction.contractor.attendance,7, `hr.attendance/347` HE - 8h


### `al_construction_portal`

#### ✅ Portal de obra: contrata reporta avance, maestro envía parte diario, valorizaciones

**Pasos en pantalla:** usuarios portal QA20 (contrata y maestro de obra) en la obra OBR-01; construction.portal.service sync/progress/daily_report/valuations

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | rol en el portal | esperado ['contractor'], obtenido ['contractor'] |
| ✅ | la contrata ve su partida |  |
| ✅ | avance del portal en borrador | esperado ('portal', 25.0, 'draft'), obtenido ('portal', 25.0, 'draft') |
| ✅ | reenvío no duplica (uuid) |  |
| ✅ | parte diario con personal | esperado 6, obtenido 6 |
| ✅ | valorizaciones visibles para la contrata | {'partner': 'QA20 Tabiquería Demo SAC', 'orders': [{'id': 941, 'name': 'P00941', 'amount_untaxed': 79100.0, 'valued': 38 |
| ⏭️ | PWA del portal (OWL/HTML) | sin navegador |

**Registros:** `res.users/3812` QA20 Supervisor de la contrata, `res.users/3813` QA20 Maestro de obra, `construction.task.progress/1446` AVN/2026/01462, `construction.daily.report/5` QA20 OBR-01 Tabiquería · 2026-10-30


### `al_project_gantt_base`

#### ✅ Gantt: tareas con dependencias, mover con reprogramación en cadena, línea base y ruta crítica

**Pasos en pantalla:** proyecto QA20 Gantt con A→B→C y una paralela; apply_gantt_changes(reschedule_chain), create_baseline, al_gantt_get_data(critical_path, baseline_id), export_xlsx

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | A, B y C en la ruta crítica |  |
| ✅ | la paralela tiene holgura | 336.0 |
| ✅ | línea base capturada | 4 |
| ✅ | cambio aplicado | [19355] |
| ✅ | la sucesora B empieza al terminar A | esperado datetime.datetime(2026, 11, 9, 8, 0), obtenido datetime.datetime(2026, 11, 9, 8, 0) |
| ✅ | B conserva su duración | esperado True, obtenido True |
| ✅ | C se empuja detrás de B (transitivo) | 2026-11-19 08:00:00 |
| ✅ | desvío contra la línea base aplicado |  |
| ✅ | desvío de A contra la línea base (días) | esperado 2.0, obtenido 2.0 |
| ✅ | vínculo creado desde el Gantt | esperado 1, obtenido 1 |
| ✅ | ciclo rechazado | ValidationError |
| ✅ | exportación a Excel | 7201 |
| ✅ | Gantt de la obra QA20 MOMEN (filas por etapa, modo por defecto del planificador) | 17 |

**Registros:** `project.project/1893` QA20 Gantt de obra, `project.task/19355` QA20 A Trazo, `project.task/19356` QA20 B Tabiquería, `project.task/19357` QA20 C Acabados, `project.task/19358` QA20 Paralela corta, `al.gantt.baseline/34` QA20 Línea base 1


### `al_project_gantt_backend`

#### ✅ Acción cliente del Gantt en el backend

**Pasos en pantalla:** ir.actions.client al_project_gantt.backend y menús restringidos a los grupos del Gantt

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | tag de la acción cliente | esperado 'al_project_gantt.backend', obtenido 'al_project_gantt.backend' |
| ✅ | menú restringido al grupo del Gantt |  |
| ✅ | RPC al_gantt_get_data que usa la pantalla devuelve tareas | 4 |
| ⏭️ | render OWL del Gantt backend | sin navegador |


### `al_project_gantt_website`

#### ✅ Página /gantt del sitio: controlador y contrato de datos

**Pasos en pantalla:** rutas /gantt, /gantt/data, /gantt/apply, /gantt/baseline delegan en el módulo base; un usuario portal no tiene acceso a los datos

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | rutas del sitio declaradas | ['/gantt', '/gantt/apply', '/gantt/baseline', '/gantt/data'] |
| ✅ | usuario portal rechazado por la capa de datos |  |
| ⏭️ | página /gantt por HTTP | el shell no levanta servidor HTTP; datos sin confirmar en el servidor del usuario |


### `al_project_gantt_ai`

#### ✅ Asistente IA del Gantt con el proveedor simulado

**Pasos en pantalla:** ai_provider.call_provider mockeado; ask() con las tareas QA20 propone mover A; la propuesta se aplica por apply_gantt_changes

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | panel IA habilitado y sin exponer la clave | anthropic |
| ✅ | se llamó al proveedor (simulado) |  |
| ✅ | respuesta del modelo | esperado 'Propongo adelantar A.', obtenido 'Propongo adelantar A.' |
| ✅ | una propuesta válida | esperado 1, obtenido 1 |
| ✅ | propuesta aplicada a la tarea | esperado '2026-11-06', obtenido '2026-11-06' |
| ✅ | propuesta sobre tarea desconocida descartada |  |


### `al_construction_planner`

#### ✅ RPC de las pantallas: inicio, árbol del plan, matriz E/S y carga del cronograma

**Pasos en pantalla:** construction.planner.home.get_home_data, plan.get_tree_nodes/get_selection_summary, get_io_matrix_options/get_io_matrix, get_schedule_load

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | tablero de inicio con datos | ['can_plan', 'has_schedule_report', 'pending', 'show_amounts', 'today', 'today_label', 'works'] |
| ✅ | árbol: nodo raíz de la obra | {'material': 6642.91, 'contract': 2685.53, 'other': 0.0, 'total': 9328.44} |
| ✅ | árbol: pisos | 1 |
| ✅ | resumen de la selección | ['contract', 'empty', 'groups', 'material', 'ml', 'modules'] |
| ✅ | matriz E/S: niveles | ['level_1_id', 'level_2_id', 'level_3_id', 'level_4_id'] |
| ✅ | matriz E/S con datos | ['cells', 'column_totals', 'columns', 'groups', 'level', 'level_name'] |
| ✅ | carga semanal del cronograma | {'weeks': ['2026-10-19', '2026-10-26', '2026-11-02'], 'rows': [{'label': 'QA20 Armado Gonza', 'stage |
| ✅ | reporte de programación lista la obra QA20 |  |
| ⏭️ | render OWL de inicio, árbol, matriz E/S, programación y cronograma | sin navegador |


### `al_construction_planner_approvals`

#### ✅ Motor «Aplicación Aprobaciones»: requerimiento con más cantidad que el saldo y plan v2

**Pasos en pantalla:** motor de la compañía en «approvals» y rutas QA20 solo durante el caso (se restauran): requerimiento que excede → solicitud en Aprobaciones → aprobada; plan v2 aprobado en Aprobaciones

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | requerimiento a la espera de Aprobaciones | esperado 'to_approve', obtenido 'to_approve' |
| ✅ | solicitud abierta en Aprobaciones | pending |
| ✅ | aprobador de la ruta |  |
| ✅ | requerimiento aprobado desde Aprobaciones | esperado 'approved', obtenido 'approved' |
| ✅ | v2 a la espera de Aprobaciones | esperado 'to_approve', obtenido 'to_approve' |
| ✅ | v2 aprobada; pasa a ser el plan vigente | approved |
| ✅ | v1 reemplazada por la v2 | esperado 'replaced', obtenido 'replaced' |

**Registros:** `res.users/3820` QA20 Jefatura de proyectos (aprobador), `construction.approval.route/80` QA20 Cantidad: jefe de obra, `construction.approval.route/81` QA20 Plan: jefe de obra, `construction.material.request/766` RQO/2026/00766, `approval.request/138` Aprobación de obra · RQO/2026/00766, `approval.request/139` Aprobación de obra · PLR/2026/00734 · v2


### `al_construction_planner_suite`

#### ✅ Suite instalada: puentes y obra QA20 de punta a punta

**Pasos en pantalla:** todos los puentes instalados; resumen de la obra QA20 (plan vigente, OC, liquidaciones, valorizaciones)

*Resultado de la repetición proyectos_ingreso (en «proyectos» quedó FALLA).*

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | puentes del planificador instalados | 18 |
| ✅ | plan vigente de la obra | PLR/2026/00734 · v2 |
| ✅ | OC de la obra (servicio) | ['P00939', 'P00938'] |
| ✅ | liquidaciones de la obra |  |
| ✅ | valorizaciones al cliente |  |


## Fases 6 y 8 · Planillas y herramientas


### `al_hr_pe`

#### ⚠️ Preparación: parámetros, periodos y trabajadores QA20

**Pasos en pantalla:** El jefe de planillas genera los periodos 2025-2026, completa la pestaña de beneficios de Parámetros Principales y registra 4 trabajadores con su contrato.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Parámetros Principales de la compañía existen | Parámetros Principales |
| ✅ | periodos mensuales 2025-07 y 2026-10 generados |  |
| ⚠️ | Parámetros Principales: se completaron campos vacíos | basic_sr_id, bonus_nine_input_id, bonus_sr_ids, commission_sr_ids, cts_input_id, extra_hours_sr_id, fifth_afect_sr_id, fifth_category_input_id, fifth_extr_sr_id, gratification_input_id, household_allowance_sr_id, insurable_remuneration, lack_wd_ids, medical_rest_wd_ids, net_to_pay_sr_id, proy_afect_ |
| ⚠️ | Estructura BASE: se quita el diario nativo para usar el asiento peruano por lote | antes: Salarios (hr_payroll_account generaría un asiento por boleta) |
| ✅ | nombre del trabajador con prefijo QA20 | QA20 Torres Ruiz Ana |

**Registros:** `hr.employee/935` QA20 Torres Ruiz Ana, `hr.employee/936` QA20 Díaz Mora Bruno, `hr.employee/937` QA20 Ríos León Carla, `hr.employee/938` QA20 Cárdenas Paz Diego

#### ✅ Planillas mensuales jul-2025 → jun-2026 (base de los beneficios)

**Pasos en pantalla:** Cada mes se crea el lote del periodo, se calculan y validan las boletas de los 4 trabajadores.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | 12 lotes mensuales jul-2025 → jun-2026 validados | QA20 Planilla 2025-07, QA20 Planilla 2025-08, QA20 Planilla 2025-09, QA20 Planilla 2025-10, QA20 Planilla 2025-11, QA20 Planilla 2025-12, QA20 Planilla 2026-01, QA20 Planilla 2026-02, QA20 Planilla 2026-03, QA20 Planilla 2026-04, QA20 Planilla 2026-05, QA20 Planilla 2026-06 |

**Registros:** `hr.payslip.run/553` QA20 Planilla 2026-06


### `al_hr_pe_benefits`

#### ✅ Gratificación de Navidad 2025 (lote dic-2025)

**Pasos en pantalla:** El usuario crea la gratificación de diciembre 2025 sobre el lote de diciembre y pulsa «Procesar».

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | línea de gratificación de QA20 Torres Ruiz Ana |  |
| ✅ | afp: meses computables jul-dic | esperado 6, obtenido 6 |
| ✅ | afp: gratificación = computable/6 × 6 meses = sueldo | esperado 6000.0, obtenido 6000.0 |
| ✅ | afp: bonificación extraordinaria 9 % (EsSalud) = sueldo × 9 % | esperado 540.0, obtenido 540.0 |
| ✅ | línea de gratificación de QA20 Díaz Mora Bruno |  |
| ✅ | onp: meses computables jul-dic | esperado 6, obtenido 6 |
| ✅ | onp: gratificación = computable/6 × 6 meses = sueldo | esperado 2500.0, obtenido 2500.0 |
| ✅ | onp: bonificación extraordinaria 9 % (EsSalud) = sueldo × 9 % | esperado 225.0, obtenido 225.0 |
| ✅ | línea de gratificación de QA20 Ríos León Carla |  |
| ✅ | rmv: meses computables jul-dic | esperado 6, obtenido 6 |
| ✅ | rmv: gratificación = computable/6 × 6 meses = sueldo | esperado 1000.0, obtenido 1000.0 |
| ✅ | rmv: bonificación extraordinaria 9 % (EsSalud) = sueldo × 9 % | esperado 90.0, obtenido 90.0 |
| ✅ | línea de gratificación de QA20 Cárdenas Paz Diego |  |
| ✅ | cese: meses computables jul-dic | esperado 6, obtenido 6 |
| ✅ | cese: gratificación = computable/6 × 6 meses = sueldo | esperado 2400.0, obtenido 2400.0 |
| ✅ | cese: bonificación extraordinaria 9 % (EsSalud) = sueldo × 9 % | esperado 216.0, obtenido 216.0 |

**Registros:** `hr.gratification/41` Gratificación Navidad 2025

#### ✅ CTS de mayo 2026 con 1/6 de la gratificación

**Pasos en pantalla:** El usuario crea la CTS semestral nov-abr sobre el lote de abril y pulsa «Procesar».

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | línea de CTS de QA20 Torres Ruiz Ana |  |
| ✅ | afp: 1/6 de la gratificación de diciembre | esperado 1000.0, obtenido 1000.0 |
| ✅ | afp: computable = sueldo + 1/6 gratificación | esperado 7000.0, obtenido 7000.0 |
| ✅ | afp: 6 meses nov-abr | esperado 6, obtenido 6 |
| ✅ | afp: CTS = computable/12 × 6 | esperado 3500.0, obtenido 3500.0 |
| ✅ | línea de CTS de QA20 Díaz Mora Bruno |  |
| ✅ | onp: 1/6 de la gratificación de diciembre | esperado 416.67, obtenido 416.67 |
| ✅ | onp: computable = sueldo + 1/6 gratificación | esperado 2916.67, obtenido 2916.67 |
| ✅ | onp: 6 meses nov-abr | esperado 6, obtenido 6 |
| ✅ | onp: CTS = computable/12 × 6 | esperado 1458.34, obtenido 1458.34 |
| ✅ | línea de CTS de QA20 Ríos León Carla |  |
| ✅ | rmv: 1/6 de la gratificación de diciembre | esperado 166.67, obtenido 166.67 |
| ✅ | rmv: computable = sueldo + 1/6 gratificación | esperado 1166.67, obtenido 1166.67 |
| ✅ | rmv: 6 meses nov-abr | esperado 6, obtenido 6 |
| ✅ | rmv: CTS = computable/12 × 6 | esperado 583.34, obtenido 583.34 |
| ✅ | línea de CTS de QA20 Cárdenas Paz Diego |  |
| ✅ | cese: 1/6 de la gratificación de diciembre | esperado 400.0, obtenido 400.0 |
| ✅ | cese: computable = sueldo + 1/6 gratificación | esperado 2800.0, obtenido 2800.0 |
| ✅ | cese: 6 meses nov-abr | esperado 6, obtenido 6 |
| ✅ | cese: CTS = computable/12 × 6 | esperado 1400.0, obtenido 1400.0 |

**Registros:** `hr.cts/54` CTS Noviembre - Abril 2026

#### ✅ Gratificación de julio 2026 con bonificación 9 %

**Pasos en pantalla:** El usuario crea la gratificación de Fiestas Patrias sobre el lote de junio y pulsa «Procesar».

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | nombre propuesto del documento | esperado 'Gratificación Fiestas Patrias 2026', obtenido 'Gratificación Fiestas Patrias 2026' |
| ✅ | línea de gratificación de QA20 Torres Ruiz Ana |  |
| ✅ | afp: computable = sueldo (sin AF ni variables) | esperado 6000.0, obtenido 6000.0 |
| ✅ | afp: 6 meses ene-jun | esperado 6, obtenido 6 |
| ✅ | afp: gratificación = computable/6 × 6 | esperado 6000.0, obtenido 6000.0 |
| ✅ | afp: total = gratificación + bono 9 % | esperado 6540.0, obtenido 6540.0 |
| ✅ | línea de gratificación de QA20 Díaz Mora Bruno |  |
| ✅ | onp: computable = sueldo (sin AF ni variables) | esperado 2500.0, obtenido 2500.0 |
| ✅ | onp: 6 meses ene-jun | esperado 6, obtenido 6 |
| ✅ | onp: gratificación = computable/6 × 6 | esperado 2500.0, obtenido 2500.0 |
| ✅ | onp: total = gratificación + bono 9 % | esperado 2725.0, obtenido 2725.0 |
| ✅ | línea de gratificación de QA20 Ríos León Carla |  |
| ✅ | rmv: computable = sueldo (sin AF ni variables) | esperado 1000.0, obtenido 1000.0 |
| ✅ | rmv: 6 meses ene-jun | esperado 6, obtenido 6 |
| ✅ | rmv: gratificación = computable/6 × 6 | esperado 1000.0, obtenido 1000.0 |
| ✅ | rmv: total = gratificación + bono 9 % | esperado 1090.0, obtenido 1090.0 |
| ✅ | línea de gratificación de QA20 Cárdenas Paz Diego |  |
| ✅ | cese: computable = sueldo (sin AF ni variables) | esperado 2400.0, obtenido 2400.0 |
| ✅ | cese: 6 meses ene-jun | esperado 6, obtenido 6 |
| ✅ | cese: gratificación = computable/6 × 6 | esperado 2400.0, obtenido 2400.0 |
| ✅ | cese: total = gratificación + bono 9 % | esperado 2616.0, obtenido 2616.0 |

**Registros:** `hr.gratification/42` Gratificación Fiestas Patrias 2026

#### ❌ Liquidación por cese (10/07/2026): CTS y vacaciones truncas

**Pasos en pantalla:** Se registra el cese en el contrato, se crea la liquidación sobre el lote de julio, se pulsa «Procesar» y «Exportar a boletas».

| Estado | Comprobación | Detalle |
|---|---|---|
| ⚠️ | días de la boleta jul-2026 del cesado (contrato hasta el 10/07) | {'DLAB': 8.0, '000.00': 15.0, 'DOM': 8.0} |
| ❌ | DLAB + DOM = 10 días de contrato en julio (1-10/07) | esperado 10.0, obtenido 16.0 |
| ❌ | básico de julio = sueldo/30 × 10 días | esperado 800.0, obtenido 1280.0 |
| ✅ | solo el trabajador cesado entra en la liquidación |  |
| ✅ | una línea de CTS trunca |  |
| ✅ | CTS trunca: meses completos (may, jun) | esperado 2, obtenido 2 |
| ❌ | CTS trunca: días de julio hasta el cese | esperado 10, obtenido 16 |
| ✅ | CTS trunca: computable = sueldo + 1/6 grati dic-2025 | esperado 2800.0, obtenido 2800.0 |
| ❌ | CTS trunca = computable/12 × 2 + computable/360 × 10 | esperado 544.45, obtenido 591.11 |
| ✅ | sin gratificación trunca ene-jun (ya incluida en la regular de julio) |  |
| ✅ | una línea de vacaciones truncas |  |
| ✅ | vacaciones: cómputo desde el último aniversario | esperado '2026-03-01', obtenido '2026-03-01' |
| ✅ | vacaciones truncas: meses mar-jun | esperado 4, obtenido 4 |
| ❌ | vacaciones truncas: días de julio | esperado 10, obtenido 16.0 |
| ❌ | vacaciones truncas = sueldo/12 × 4 + sueldo/360 × 10 | esperado 866.67, obtenido 906.67 |
| ✅ | vacaciones: neto = total − fondo 10 % − prima − comisión AFP | esperado 789.07, obtenido 789.07 |
| ✅ | exportar: input CTS_TRU en la boleta de julio | esperado 591.11, obtenido 591.11 |
| ✅ | exportar: input VATRU en la boleta de julio | esperado 906.67, obtenido 906.67 |
| ✅ | boleta de julio: línea VATRU calculada | esperado 906.67, obtenido 906.67 |
| ✅ | boleta de cese validada | validated |

**Registros:** `hr.payslip.run/554` QA20 Planilla 2026-07, `hr.liquidation/30` 


### `al_hr_pe`

#### ✅ Planillas ago → oct 2026

**Pasos en pantalla:** Se generan los lotes de agosto y setiembre (validados) y octubre (en borrador).

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | el cesado ya no tiene boleta en setiembre |  |

**Registros:** `hr.payslip.run/556` QA20 Planilla 2026-09, `hr.payslip.run/557` QA20 Planilla 2026-10

#### ✅ Parámetros nativos UIT / RMV / EsSalud con su historial

**Pasos en pantalla:** El usuario abre Nómina ▸ Configuración ▸ Parámetros de reglas y revisa los valores por fecha.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | existe el parámetro de reglas l10n_pe_uit | Perú: UIT (Unidad Impositiva Tributaria) |
| ✅ | l10n_pe_uit vigente desde 2024-01-01 | esperado 5150.0, obtenido 5150.0 |
| ✅ | l10n_pe_uit vigente desde 2025-01-01 | esperado 5350.0, obtenido 5350.0 |
| ✅ | l10n_pe_uit vigente desde 2026-01-01 | esperado 5500.0, obtenido 5500.0 |
| ✅ | existe el parámetro de reglas l10n_pe_rmv | Perú: Remuneración Mínima Vital |
| ✅ | l10n_pe_rmv vigente desde 2022-05-01 | esperado 1025.0, obtenido 1025.0 |
| ✅ | l10n_pe_rmv vigente desde 2025-01-01 | esperado 1130.0, obtenido 1130.0 |
| ✅ | l10n_pe_rmv vigente desde 2026-10-01 | esperado 1230.0, obtenido 1230.0 |
| ✅ | existe el parámetro de reglas l10n_pe_essalud_rate | Perú: tasa de EsSalud (%) |
| ✅ | l10n_pe_essalud_rate vigente desde 1997-05-01 | esperado 9.0, obtenido 9.0 |
| ✅ | _l10n_pe_get_uit(2024) | esperado 5150.0, obtenido 5150.0 |
| ✅ | _l10n_pe_get_uit(2025) | esperado 5350.0, obtenido 5350.0 |
| ✅ | _l10n_pe_get_uit(2026) | esperado 5500.0, obtenido 5500.0 |
| ✅ | _l10n_pe_get_rmv(2024-06-30) | esperado 1025.0, obtenido 1025.0 |
| ✅ | _l10n_pe_get_rmv(2026-09-30) | esperado 1130.0, obtenido 1130.0 |
| ✅ | _l10n_pe_get_rmv(2026-10-01) | esperado 1230.0, obtenido 1230.0 |
| ✅ | _l10n_pe_get_rmv(2022-01-01) | esperado 0.0, obtenido 0.0 |
| ✅ | sin UIT 2031 → UserError claro | No está registrada la UIT del año 2031 (Nómina ▸ Configuración ▸ Perú ▸ UIT). |

#### ✅ Boleta mensual: AFP, ONP y sueldo menor a la RMV

**Pasos en pantalla:** El usuario abre las boletas de setiembre y octubre 2026 y revisa cada concepto.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | afp set-2026: RMV de la boleta = 1 130 (parámetro al 30/09) | esperado 1130.0, obtenido 1130.0 |
| ✅ | afp: básico mes completo = sueldo | esperado 6000.0, obtenido 6000.0 |
| ✅ | afp: afecto AFP = básico | esperado 6000.0, obtenido 6000.0 |
| ✅ | afp: fondo AFP = afecto × 10.00 % | esperado 600.0, obtenido 600.0 |
| ✅ | afp: comisión flujo = afecto × 1.55 % | esperado 93.0, obtenido 93.0 |
| ✅ | afp: prima de seguro = min(afecto, tope 12732.70) × 1.37 % | esperado 82.2, obtenido 82.2 |
| ✅ | afp: sin ONP | esperado 0.0, obtenido 0.0 |
| ✅ | afp: EsSalud = max(afecto 6000.00, RMV 1130.00) × 9 % | esperado 540.0, obtenido 540.0 |
| ✅ | afp: neto = ingresos − aportes del trabajador | esperado 5224.8, obtenido 5224.8 |
| ✅ | onp set-2026: RMV de la boleta = 1 130 (parámetro al 30/09) | esperado 1130.0, obtenido 1130.0 |
| ✅ | onp: básico mes completo = sueldo | esperado 2500.0, obtenido 2500.0 |
| ✅ | onp: ONP = afecto × 13 % | esperado 325.0, obtenido 325.0 |
| ✅ | onp: sin aporte AFP | esperado 0.0, obtenido 0.0 |
| ✅ | onp: EsSalud = max(afecto 2500.00, RMV 1130.00) × 9 % | esperado 225.0, obtenido 225.0 |
| ✅ | onp: neto = ingresos − aportes del trabajador | esperado 2175.0, obtenido 2175.0 |
| ✅ | rmv set-2026: RMV de la boleta = 1 130 (parámetro al 30/09) | esperado 1130.0, obtenido 1130.0 |
| ✅ | rmv: básico mes completo = sueldo | esperado 1000.0, obtenido 1000.0 |
| ✅ | rmv: afecto AFP = básico | esperado 1000.0, obtenido 1000.0 |
| ✅ | rmv: fondo AFP = afecto × 10.00 % | esperado 100.0, obtenido 100.0 |
| ✅ | rmv: comisión flujo = afecto × 1.47 % | esperado 14.7, obtenido 14.7 |
| ✅ | rmv: prima de seguro = min(afecto, tope 12732.70) × 1.37 % | esperado 13.7, obtenido 13.7 |
| ✅ | rmv: sin ONP | esperado 0.0, obtenido 0.0 |
| ✅ | rmv: EsSalud = max(afecto 1000.00, RMV 1130.00) × 9 % | esperado 101.7, obtenido 101.7 |
| ✅ | rmv: neto = ingresos − aportes del trabajador | esperado 871.6, obtenido 871.6 |
| ✅ | rmv oct-2026: RMV = 1 230 | esperado 1230.0, obtenido 1230.0 |
| ✅ | rmv oct-2026: asignación familiar = 10 % RMV | esperado 123.0, obtenido 123.0 |
| ✅ | rmv oct-2026: EsSalud sobre la RMV nueva (1 230 × 9 %) | esperado 110.7, obtenido 110.7 |
| ✅ | la boleta validada de setiembre conserva RMV 1 130 | esperado 1130.0, obtenido 1130.0 |

**Registros:** `hr.payslip/1443` Recibo de nómina - QA20 Torres Ruiz Ana - setiembre 2026, `hr.payslip/1444` Recibo de nómina - QA20 Díaz Mora Bruno - setiembre 2026, `hr.payslip/1445` Recibo de nómina - QA20 Ríos León Carla - setiembre 2026

#### ⚠️ RMV con fecha futura solo afecta a las planillas posteriores

**Pasos en pantalla:** Se registra una RMV vigente desde 01/01/2027 y se calculan boletas de dic-2026 y ene-2027.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | dic-2026 (antes de la vigencia) sigue con RMV 1 230 | esperado 1230.0, obtenido 1230.0 |
| ✅ | ene-2027 toma la RMV futura 1 300 | esperado 1300.0, obtenido 1300.0 |
| ✅ | ene-2027: EsSalud = 1 300 × 9 % (sueldo 1 000 < RMV) | esperado 117.0, obtenido 117.0 |
| ✅ | la boleta de oct-2026 ya calculada no cambia | esperado 1230.0, obtenido 1230.0 |
| ⚠️ | valor RMV 2027 creado dentro de un savepoint y deshecho | no queda en la base |


### `al_hr_pe_benefits`

#### ✅ Vacaciones: récord vacacional y goce de 15 días

**Pasos en pantalla:** El usuario calcula el récord vacacional de Bruno y registra 15 días de vacaciones en el lote de agosto.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | récord vacacional del año 2025 generado |  |
| ✅ | récord 2025: 2.5 días × 12 meses = 30 días | esperado 30.0, obtenido 30.0 |
| ✅ | vacaciones 15 días = sueldo/30 × 15 | esperado 1250.0, obtenido 1250.0 |
| ✅ | ONP 13 % de la remuneración vacacional | esperado 162.5, obtenido 162.5 |
| ✅ | neto vacacional = total − ONP | esperado 1087.5, obtenido 1087.5 |

**Registros:** `hr.vacation.rest/56` QA20 Díaz Mora Bruno · 01/01/2025 – 31/12/2025, `hr.vacation/11` Vacaciones QA20 Planilla 2026-08

#### ✅ Renta de 5.ª de octubre con la UIT 2026

**Pasos en pantalla:** El usuario crea la quinta del lote de octubre, pulsa «Generar» y «Exportar a boletas».

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | Ana (6 000) queda afecta a 5.ª |  |
| ✅ | 7 UIT = 7 × 5500 (UIT 2026 del parámetro) | esperado 38500.0, obtenido 38500.0 |
| ✅ | remuneraciones ene-set (boletas validadas) | esperado 54000.0, obtenido 54000.0 |
| ✅ | renta bruta proyectada = 12 sueldos + 2 gratificaciones con bono | esperado 85080.0, obtenido 85080.0 |
| ✅ | renta neta = bruta − 7 UIT | esperado 46580.0, obtenido 46580.0 |
| ✅ | impuesto anual por tramos 8/14/17/20/30 % (calculado a mano) | esperado 4871.2, obtenido 4871.200000000001 |
| ✅ | retención de octubre = (impuesto − retenido) / 4 (art. 40) | esperado 1217.8, obtenido 1217.8 |
| ✅ | Bruno (2 500) y Carla (1 000) pasan a excluidos | QA20 Díaz Mora Bruno, QA20 Ríos León Carla |
| ✅ | la boleta de octubre descuenta la quinta exportada | esperado 1217.8, obtenido 1217.8 |
| ✅ | tramos 2031 sin UIT → mensaje claro | No está registrada la UIT del año 2031 (Nómina ▸ Configuración ▸ Perú ▸ UIT). |

**Registros:** `hr.fifth.category/25` Quinta QA20 Planilla 2026-10


### `al_hr_pe_import`

#### ✅ Importar inputs de boleta desde Excel

**Pasos en pantalla:** El usuario sube un Excel con DNI, código de input y monto al lote de octubre y lo importa.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | filas importadas (Bruno 300, Carla 150.50) | esperado 2, obtenido 2 |
| ✅ | filas con error (DNI sin boleta, input inexistente) | esperado 2, obtenido 2 |
| ✅ | cada error trae su sugerencia | [OK  ] fila 2: input BONR = 300.0 en la boleta de QA20 Díaz Mora Bruno \| [OK  ] fila 3: input BONR = 150.5 en la boleta de QA20 Ríos León Carla \| [ERR ] fila 4: no hay boleta en el lote "QA20 Planilla 2026-10" para el documento 99999999 \| [ERR ] fila 5: no existe un tipo de input con código "NOEX |
| ✅ | onp: línea BONR = input importado | esperado 300.0, obtenido 300.0 |
| ✅ | rmv: línea BONR = input importado | esperado 150.5, obtenido 150.5 |
| ✅ | onp: ONP sobre sueldo + bonificación regular | esperado 364.0, obtenido 364.0 |
| ✅ | rmv: EsSalud sigue con base RMV (1 150.50 < 1 230) | esperado 110.7, obtenido 110.7 |


### `al_hr_pe`

#### ✅ Cierre del lote de octubre

**Pasos en pantalla:** Se recalculan y validan las boletas de octubre (con quinta e inputs importados).

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | lote de octubre validado | 02_close |


### `al_hr_pe_account`

#### ⚠️ Asiento de planilla del lote de setiembre

**Pasos en pantalla:** El contador configura las cuentas de las reglas y pulsa «Asiento de planilla por lote».

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | cuentas PCGE de planilla existen | 6211000, 4111000, 4032000, 4170000, 6271000, 4031000 |
| ⚠️ | configuración contable completada (solo campos vacíos) | BAS debe 6211000; NETO haber 4111000; ONP haber 4032000; ESSALUD debe 6271000; ESSALUD haber 4031000; AFP INTEGRA → 4170000; AFP HABITAT → 4170000; AFP PRIMA → 4170000; afp_rule_ids; move_journal_id; move_partner_id |
| ✅ | el lote de setiembre tiene asiento |  |
| ✅ | asiento publicado | posted |
| ✅ | referencia PLA + MM + AAAA | esperado 'PLA092026', obtenido 'PLA092026' |
| ✅ | asiento cuadrado | esperado 10366.699999999999, obtenido 10366.7 |
| ✅ | 6211 debe = Σ básicos del lote | esperado 9500.0, obtenido 9500.0 |
| ✅ | 4111 haber = Σ netos | esperado 8271.4, obtenido 8271.4 |
| ✅ | 4032 haber = Σ ONP | esperado 325.0, obtenido 325.0 |
| ✅ | 4170 haber = Σ fondo + comisión + prima AFP (cuenta de la afiliación) | esperado 903.6, obtenido 903.6 |
| ✅ | 6271 debe = Σ EsSalud | esperado 866.7, obtenido 866.7 |
| ✅ | 4031 haber = Σ EsSalud | esperado 866.7, obtenido 866.7 |
| ✅ | sin línea de ajuste por redondeo (el lote cuadra por construcción) |  |

**Registros:** `account.journal/6087` QA20 Planillas, `res.partner/9478` QA20 Planilla OLANO IT (contrapartida), `account.move/31413` QPLA/2026/09/0001 (PLA092026)


### `al_hr_pe_reports`

#### ⚠️ Boleta PDF, PLAME .rem, AFPnet y TXT de haberes BCP del lote de octubre

**Pasos en pantalla:** El usuario imprime la boleta, exporta PLAME y AFPnet, genera el pago masivo y descarga el TXT del BCP.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | la boleta usa la cabecera común de al_report_base |  |
| ✅ | la boleta muestra DNI y RUC |  |
| ✅ | boleta PDF renderizada | 29979 bytes |
| ✅ | formato tipo\|doc\|concepto\|devengado\|pagado\| | 14 filas |
| ✅ | afp: concepto 0121 (básico) declarado |  |
| ✅ | afp: 0121 devengado = básico | esperado 6000.0, obtenido 6000.0 |
| ✅ | afp: tipo de documento DNI = 01 | esperado '01', obtenido '01' |
| ✅ | onp: concepto 0121 (básico) declarado |  |
| ✅ | onp: 0121 devengado = básico | esperado 2500.0, obtenido 2500.0 |
| ✅ | onp: tipo de documento DNI = 01 | esperado '01', obtenido '01' |
| ✅ | rmv: concepto 0121 (básico) declarado |  |
| ✅ | rmv: 0121 devengado = básico | esperado 1000.0, obtenido 1000.0 |
| ✅ | rmv: tipo de documento DNI = 01 | esperado '01', obtenido '01' |
| ✅ | afp: 0605 (renta 5.ª) declarada |  |
| ✅ | afp: 0605 = retención de octubre | esperado 1217.8, obtenido 1217.8 |
| ✅ | onp: sin comisión AFP 0601 |  |
| ✅ | EsSalud (0804) no se importa (lo calcula PLAME) |  |
| ✅ | AFPnet: solo los 2 afiliados AFP (Ana, Carla) | esperado 2, obtenido 2 |
| ✅ | correlativo 1, 2 sin huecos | esperado [1, 2], obtenido [1, 2] |
| ✅ | fila de Ana en AFPnet |  |
| ✅ | CUSPP | esperado '6000101XQA0', obtenido '6000101XQA0' |
| ✅ | apellidos y nombres | esperado ('Torres', 'Ruiz', 'Ana'), obtenido ('Torres', 'Ruiz', 'Ana') |
| ✅ | devenga S, inicio N, cese N | esperado ('S', 'N', 'N'), obtenido ('S', 'N', 'N') |
| ✅ | remuneración asegurable = AAFP | esperado 6000.0, obtenido 6000.0 |
| ✅ | tipo de labor N | esperado 'N', obtenido 'N' |
| ⚠️ | banco BCP: se configuró format_bank = bcp |  |
| ✅ | pago masivo BCP generado desde el lote |  |
| ✅ | una línea por trabajador con cuenta BCP | esperado 3, obtenido 3 |
| ✅ | afp: monto = NETO peruano | esperado 4007.0, obtenido 4007.0 |
| ✅ | onp: monto = NETO peruano | esperado 2436.0, obtenido 2436.0 |
| ✅ | rmv: monto = NETO peruano | esperado 1002.78, obtenido 1002.78 |
| ✅ | TXT BCP: cabecera + 3 detalles | esperado 4, obtenido 4 |
| ✅ | cabecera tipo 1 | esperado '1', obtenido '1' |
| ✅ | cabecera: 3 abonos | esperado '000003', obtenido '000003' |
| ✅ | tipo de cargo C | esperado 'C', obtenido 'C' |
| ✅ | moneda soles 0001 | esperado '0001', obtenido '0001' |
| ✅ | cuenta de cargo | esperado '1917000123456', obtenido '1917000123456' |
| ✅ | total de la planilla en la cabecera | esperado 7445.78, obtenido 7445.78 |
| ✅ | checksum = Σ cuentas (desde la 4.ª posición) + cargo | esperado '000007000138462', obtenido '000007000138462' |
| ✅ | detalle de Ana |  |
| ✅ | detalle: cuenta destino | esperado '19100000005001', obtenido '19100000005001' |
| ✅ | detalle: importe = neto | esperado 4007.0, obtenido 4007.0 |

**Registros:** `ir.attachment/70495` QA20 Boleta oct-2026 Ana.pdf, `ir.attachment/70496` 060120261020557912879.rem, `ir.attachment/70497` AFP_NET.xlsx, `account.journal/6088` QA20 Pagos planilla BCP, `hr.automate.multipayment/14` PM-000001, `ir.attachment/70498` BCP_Haberes.txt


### `al_hr_pe_attendance`

#### ⚠️ Turno, marcaciones importadas, tardanza y horas extra 25 %/35 %

**Pasos en pantalla:** Se define el turno, se importa el Excel de marcaciones de setiembre, se genera y aplica el tareaje y se calcula la boleta.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | promedio semanal 12 h × 4 × 7/7 = 48 h | esperado 48.0, obtenido 48.0 |
| ✅ | ciclo 6×1 de 10 h rechazado por superar 48 h | El promedio semanal del ciclo (60.00 h) supera las 48 horas permitidas por el art. 4 del D.S. 007-2002-TR. |
| ✅ | al_hr_pe_import: marcaciones creadas desde Excel | esperado 22, obtenido 22 |
| ✅ | marcación del 09/09 (08:00 Lima = 13:00 UTC) |  |
| ✅ | el día termina 20:00 Lima aunque el sobretiempo vaya en asistencia separada | esperado '2026-09-10 01:00:00', obtenido '2026-09-10 01:00:00' |
| ⚠️ | asistencias del 09/09 | 2 registro(s): 2026-09-09 13:00:00→2026-09-09 21:00:00, 2026-09-09 21:00:00→2026-09-10 01:00:00 |
| ✅ | línea de tareaje de Elena |  |
| ✅ | 08/09: tardanza 40 min (> 15 min de tolerancia) = 0.67 h | esperado 0.67, obtenido 0.67 |
| ✅ | 09/09: 3 h extra → 2 h al 25 % | esperado 2.0, obtenido 2.0 |
| ✅ | 09/09: … y 1 h al 35 % | esperado 1.0, obtenido 1.0 |
| ✅ | 10/09: 1.5 h al 25 % | esperado 1.5, obtenido 1.5 |
| ✅ | días laborados = 22 días hábiles de setiembre | esperado 22.0, obtenido 22.0 |
| ✅ | total HE 25 % = 3.5 h | esperado 3.5, obtenido 3.5 |
| ✅ | total HE 35 % = 1 h | esperado 1.0, obtenido 1.0 |
| ✅ | HE25 = sueldo/30/8 × 1.25 × 3.5 h | esperado 54.6875, obtenido 54.69 |
| ✅ | HE35 = sueldo/30/8 × 1.35 × 1 h | esperado 16.875, obtenido 16.88 |
| ✅ | TAR = horas de tardanza × sueldo/30/8 (0.67 h) | esperado 8.375, obtenido 8.38 |
| ✅ | básico completo (22 DLAB + 8 DOM = 30 días) | esperado 3000.0, obtenido 3000.0 |
| ✅ | registro de control: fila del 09/09 |  |
| ✅ | ingreso, salida e inicio/fin del sobretiempo | esperado ('08:00', '20:00', '17:00', '20:00'), obtenido ('08:00', '20:00', '17:00', '20:00') |

**Registros:** `hr.employee/942` QA20 Quispe Huamán Elena, `l10n_pe.hr.shift.cycle/11` QA20 Ciclo 4x3 (4×3), `hr.tareaje.manager/56` QA20 Tareaje setiembre 2026, `hr.payslip/1451` Recibo de nómina - QA20 Quispe Huamán Elena - setiembre 2026


### `al_hr_pe_public_holidays`

#### ❌ Feriados 2026 en calendarios sin duplicar los nativos de Odoo 20

**Pasos en pantalla:** El usuario aplica los feriados del catálogo a los calendarios y abre el asistente nativo «Cargar feriados».

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | catálogo 2026: 16 feriados nacionales | esperado 16, obtenido 16 |
| ❌ | feriados del catálogo 2026-2035 sin concepto de nómina (debería ser DOM) | esperado 0, obtenido 170 |
| ✅ | aplicar dos veces deja 16 descansos (sin duplicar) | esperado 16, obtenido 16 |
| ✅ | 28/07 00:00 Lima = 05:00 UTC | esperado '2026-07-28 05:00:00', obtenido '2026-07-28 05:00:00' |
| ❌ | el descanso usa el concepto DOM de la planilla | esperado 'DOM', obtenido False |
| ✅ | Odoo 20 (asistente nativo) no propone días que ya cubre el catálogo 2026 | 0 propuestos:  |
| ✅ | 2036 (fuera del catálogo): el nativo propone los feriados del CSV | 16 días |
| ✅ | el tareaje reconoce el 08/10 como feriado del calendario |  |
| ❌ | calcular la boleta de octubre de un trabajador con el feriado aplicado | NotNullViolation: null value in column "work_entry_type_id" of relation "hr_payslip_worked_days" violates not-null constraint |
| ⚠️ | descansos retirados de calendarios no QA20 tras la prueba | 48 |

**Registros:** `resource.calendar/1465` QA20 Calendario feriados


### `al_hr_pe_construction`

#### ✅ Boleta semanal de operario: BUC, movilidad y CONAFOVICER

**Pasos en pantalla:** Se registra al operario, se genera la semana del 12 al 18/10 con 6 días laborados y se calcula.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | semana 12-18/10/2026 generada | 202610-S03 |
| ✅ | jornal diario de la tabla del convenio (89.30) | esperado 89.3, obtenido 89.3 |
| ✅ | JOR = jornal × 6 días | esperado 535.8, obtenido 535.8 |
| ✅ | DSO = 1 jornal por 6 días trabajados | esperado 89.3, obtenido 89.3 |
| ✅ | BUC = jornal × 6 × 32 % | esperado 171.46, obtenido 171.46 |
| ✅ | movilidad = 8.60 × 6 días | esperado 51.6, obtenido 51.6 |
| ✅ | CONAFOVICER = −(JOR + DSO) × 2.0 % | esperado -12.5, obtenido -12.5 |
| ✅ | afecto (TREM) = JOR + DSO + BUC; la movilidad no está afecta | esperado 796.56, obtenido 796.56 |
| ✅ | ONP 13 % del afecto | esperado 103.55, obtenido 103.55 |

**Registros:** `hr.employee/943` QA20 Mamani Condori Julio, `hr.payslip/1453` Recibo de nómina - QA20 Mamani Condori Julio - 12/10/2026 - 


### `al_docs_help`

#### ✅ Ayuda contextual: entradas, UIT/RMV y respuesta al systray

**Pasos en pantalla:** Un usuario interno pulsa el «?» de la barra superior en la pantalla de UIT/RMV.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | entradas de ayuda cargadas | 529 |
| ✅ | entrada UIT/RMV apunta al modelo nativo hr.rule.parameter.value | UIT y Remuneración Mínima Vital |
| ✅ | sin entrada al modelo eliminado l10n_pe.hr.uit |  |
| ✅ | sin entrada al modelo eliminado hr.uit |  |
| ✅ | sin entrada al modelo eliminado l10n_pe.hr.rmv |  |
| ✅ | sin entrada al modelo eliminado hr.rmv |  |
| ✅ | get_help_map (systray) responde al usuario interno con la URL de UIT/RMV | https://docs.altalatam.com/latest/applications/hr/payroll/peru/ |
| ✅ | el usuario interno no puede editar la ayuda |  |
| ✅ | ninguna ayuda visible apunta a un modelo inexistente |  |
| ✅ | botón «?» abre la guía | https://docs.altalatam.com/latest/applications/hr/payroll/peru/ |

**Registros:** `res.users/3810` QA20 Usuario ayuda


### `al_report_base`

#### ⚠️ Página común de documentos (cabecera y pie)

**Pasos en pantalla:** Se imprime un documento con el formato común de OLANO IT.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | página común: cabecera y pie |  |
| ✅ | la cabecera muestra el RUC 20557912879 |  |
| ✅ | número del documento en la cabecera |  |
| ⚠️ | plantillas que usan la cabecera común | 35: al_construction_material_request.report_construction_request_document, al_construction_material_request.report_dispatch_slip_document, al_construction_planner_sale.report_construction_valuation_document, al_construction_planner_subcontract.report_contract_summary, al_construction_planner_subcont |
| ⏭️ | PDF de factura con cabecera común | ninguna plantilla de factura (account.move) usa al_report_base.report_pe_page; se validó el PDF de la boleta (al_hr_pe_reports) que sí la usa, ver caso de reportes |


### `al_base_module_info`

#### ⚠️ Ficha de módulo en Aplicaciones

**Pasos en pantalla:** El usuario abre Aplicaciones y pulsa «Ver la ficha completa del módulo».

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | ficha del propio módulo | esperado '/al_base_module_info/static/description/index.html', obtenido '/al_base_module_info/static/description/index.html' |
| ✅ | «base» no se considera ficha |  |
| ⚠️ | fichas de los módulos de planillas | 8/8 con ficha: al_hr_pe, al_hr_pe_account, al_hr_pe_attendance, al_hr_pe_benefits, al_hr_pe_construction, al_hr_pe_import, al_hr_pe_public_holidays, al_hr_pe_reports |
| ✅ | el kanban de Aplicaciones ofrece el enlace a la ficha |  |


### `al_mcp_server`

#### ✅ Herramienta MCP de lectura con usuario no administrador

**Pasos en pantalla:** Un asistente IA conectado con el token de un usuario interno consulta contactos y boletas.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | odoo_search_read de contactos funciona con alcance read | total 85 |
| ✅ | boletas (hr.payslip) denegadas al usuario sin permisos | AccessError |
| ✅ | odoo_create rechazado con alcance read | PermissionError: La herramienta 'odoo_create' requiere al menos el alcance 'write'. Este token está restringido al alcance 'read' (solo lectura). Contacte a su administrador para ampliar el alcance del token. |
| ✅ | odoo_count responde | {'model': 'res.partner', 'domain': [['name', '=like', 'QA20%']], 'count': 85} |

**Registros:** `res.users/3811` QA20 Lector MCP


### `ol_licencia_perpetua`

#### ✅ Constatar instalación y reemplazo del aviso de suscripción

**Pasos en pantalla:** Se verifica que el módulo está instalado y su asset reemplaza al de web_enterprise.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | ol_licencia_perpetua instalado | esperado 'installed', obtenido 'installed' |
| ✅ | el reemplazo de asset apunta a archivos existentes | web_enterprise/static/src/webclient/home_menu/enterprise_subscription_service.js ← ol_licencia_perpetua/static/src/js/subscription_manager.js |


### `prt_report_attachment_preview`

#### ✅ Vista previa de PDF en el navegador

**Pasos en pantalla:** El usuario imprime un PDF y se abre en una pestaña en lugar de descargarse.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | prt_report_attachment_preview instalado | esperado 'installed', obtenido 'installed' |
| ✅ | el controlador de vista previa extiende /report |  |
| ✅ | evalúa el nombre del PDF con «object» (abre en pestaña con su nombre) | {'object': 'report'} |


### `queue_job`

#### ✅ Encolar un job con with_delay y ejecutarlo

**Pasos en pantalla:** Un proceso encola una escritura diferida y el job runner la ejecuta.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | job encolado en queue.job (pending) | pending |
| ✅ | antes de ejecutarse el contacto no cambia |  |
| ✅ | job ejecutado con perform → done | esperado 'done', obtenido 'done' |
| ✅ | el método diferido se ejecutó (write) | esperado True, obtenido True |

**Registros:** `res.partner/9481` QA20 Contacto queue_job, `queue.job/59` QA20 Job de prueba


### `al_l10n_pe_city`

#### ✅ Módulo no instalable en Odoo 20

**Pasos en pantalla:** Solo constatar.

| Estado | Comprobación | Detalle |
|---|---|---|
| ✅ | al_l10n_pe_city no instalado | esperado 'uninstalled', obtenido 'uninstalled' |
| ⏭️ | al_l10n_pe_city | manifest 'installable': False en Odoo 20 (depende de base_address_extended); no se valida |


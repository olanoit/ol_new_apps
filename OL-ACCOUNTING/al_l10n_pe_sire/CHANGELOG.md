Historial de cambios — Perú - SIRE (RVIE / RCE)
===============================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_sire.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 8.20261007 — 07/10/2026

- Registro de compras: ya no anota compras anuladas (la norma lo prohíbe); el ISC de un ítem gravado va en su base; IVAP, exportación y líneas sin impuesto van al campo 21; DAM y DSI con aduana, año y número (antes faltaba el año y SUNAT rechazaba la fila). No domiciliados: valor de la adquisición completo y convenio «00» por defecto.
- Ventas y compras: una línea gratuita ya no aparece como «otros tributos» negativos y la retención del 3 % ya no reduce el total; tipo de cambio de la factura (y el del documento modificado en las notas); proveedor con tipo «VAT» genérico informado como RUC o DNI; sucursales incluidas con el RUC de la compañía principal; razón social sin «|», «/» ni «\».
- Envíos a SUNAT: tras un envío procesado con errores, o tras eliminar el reemplazo o el preliminar, el periodo admite un nuevo envío (antes quedaba bloqueado); el preliminar solo se registra con el envío concluido; un estado de ticket desconocido se sigue consultando en vez de darse por fallido; la propuesta se descarga como indica el manual (todos sus archivos); un token rechazado o un cambio de credenciales pide token nuevo; un periodo con error ya no detiene la consulta automática de los demás.
- La descarga manual del reemplazo valida las líneas igual que el envío por la API, y su nombre lleva el indicador de moneda de la compañía.

## 7.20261006 — 06/10/2026

- Historial de operaciones con SUNAT por periodo: ticket, archivo enviado y reportes; los tickets se consultan solos y los reportes (inconsistencias del envío, resumen, preliminar, constancia de recepción) quedan adjuntos.
- Tipo de cambio: envío masivo al RVIE y al RCE (anexo 10) e individual al RVIE.
- Registro de compras de no domiciliados (anexo 9): datos de renta en la factura, país SUNAT (tabla 16), validación, envío y exportación del preliminar.
- RCE: completar o reubicar datos de la propuesta, excluir y volver a incluir comprobantes; RVIE y RCE: nuevos comprobantes en la propuesta o en el preliminar.
- Ajustes posteriores del periodo (RVIE y RCE, también no domiciliados) y de periodos anteriores al SIRE (formato general), con su envío en el RCE.
- Eliminaciones en SUNAT (solo responsables) y reintegro, crédito fiscal especial y prorrata del RCE.
- Corregido: el ticket de las cargas TUS llega como texto plano y no se leía; el reemplazo del RVIE añadía una columna CLU vacía.

## 6.20261006 — 06/10/2026

- Validación de las líneas del sistema antes del envío: RUC con dígito verificador, tipo de comprobante, serie y número, IGV frente a la base, total, moneda y tipo de cambio, fechas y notas sin comprobante modificado. Con observaciones, el reemplazo no se envía.
- Los tickets de la propuesta y del envío se consultan solos, con espera creciente; la propuesta se descarga al terminar y, si SUNAT falla, queda una actividad para revisarlo.
- RCE: columnas DG, DGNG y DNG según el grupo del impuesto de la compra.
- Corregido: las líneas negativas (anticipos, descuentos) se sumaban a la base en vez de restar, y las líneas sin impuesto se informaban como gravadas sin IGV.

## 5.20260803 — 27/09/2026

- Las credenciales de la API SIRE (usuario y clave SOL, client ID y secret) y el token solo los ven y editan los administradores; antes cualquier usuario interno podía leerlos.
- Solo los usuarios contables pueden solicitar, aceptar o reemplazar la propuesta y registrar el preliminar; un usuario de solo lectura ya no puede enviar nada a SUNAT.
- Cada compañía ve únicamente sus periodos RVIE y RCE.
- El TXT de la propuesta cargado a mano se lee aunque SUNAT lo entregue con tildes en latin-1.
- Las líneas del sistema usan el RUC y la razón social de la empresa aunque la factura esté a nombre de una persona de contacto.
- No se informan los borradores cancelados que nunca se emitieron ni los diarios excluidos de los libros electrónicos.
- Las notas de débito de compra arrastran el comprobante que modifican, y en ventas el IVAP va a sus propias columnas.
- Mensajes claros cuando SUNAT responde algo que no es JSON; la carga del reemplazo nunca envía el token fuera de sunat.gob.pe.
- Un periodo por libro, compañía y mes garantizado también en la base de datos.

## 14/09/2026

- Menú SIRE ordenado en la app Perú y campos de comparación en Configuración ▸ Tributos SUNAT.

## 3.20260803 — 03/08/2026

- Envío a SUNAT por API: aceptar propuesta, enviar reemplazo, consultar envío y registrar preliminar.
- Resumen de la comparación en el periodo y aviso de CAR repetido.
- Comparación más rápida en periodos con miles de comprobantes.

## 2.20260719 — 19/07/2026

- Etiquetas en español en nombres, estados y campos de comparación.
- Sección propia en Ajustes ▸ Perú.

## 1.20260719 — 19/07/2026

- Propuesta RVIE y RCE por API o carga manual, comparación por CAR, XLSX y TXT de reemplazo.

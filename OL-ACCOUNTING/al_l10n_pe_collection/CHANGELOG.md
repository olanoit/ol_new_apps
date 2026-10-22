Historial de cambios — Cobranza (AL)
====================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_collection.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 9.20261022 — 22/10/2026

- Ajustes propios: Cobranza ▸ Configuración ▸ Ajustes abre la app Cobranza de Ajustes (antes, un bloque de Ajustes ▸ Perú) con toda la configuración en cuatro bloques y accesos a zonas, tramos, resultados, motivos de reclamo, niveles de seguimiento, tasas del BCRP, planes, agencias y proveedores de pago.

## 8.20261022 — 22/10/2026

- Cobranza judicial: proceso por deudor con vía, juzgado, expediente, estudio, actuaciones con plazos agendados y gastos; la demanda saca los documentos del seguimiento y sustenta la provisión sin esperar 12 meses, y el cierre como incobrable deja las acciones agotadas para castigar deudas de más de 3 UIT. El expediente PDF incluye los procesos.

## 7.20261022 — 22/10/2026

- Agencias externas de cobranza: cartera asignada por fechas (asistente desde la lista de clientes, retiro y fin automático); sus usuarios solo ven los clientes asignados y sus documentos, sin entrar a Contabilidad.
- Comisiones de gestores y agencias sobre lo recuperado, con planes por antigüedad de la deuda, cada cobro liquidado una sola vez, descuento de cobros desconciliados y factura de proveedor de la agencia en borrador.

## 6.20261022 — 22/10/2026

- Tope del BCRP para el interés moratorio: tabla de tasas máximas por periodo y moneda (precargadas mayo 2026–abril 2027), aviso en Ajustes y en el cliente cuando la tasa pactada lo supera, y liquidación de intereses recortada al tope de cada periodo.

## 5.20261022 — 22/10/2026

- Pago en línea: «Pagar en línea» con el saldo del cliente en el estado de cuenta, el recordatorio de compromiso, los niveles de seguimiento y el aviso a centrales, y un QR en el estado de cuenta en PDF. Usa las pasarelas activas (Culqi, Niubiz, Izipay…) y el pago se aplica a las facturas más antiguas.

## 4.20261022 — 22/10/2026

- Prueba funcional: un cliente sin pagos previos y con deuda antigua se califica por lo vencido abierto (antes salía B); la cola de trabajo muestra a todos al administrador; títulos «Documento» y «Vencimiento» en las listas de documentos.

## 3.20261022 — 22/10/2026

- Reclamos: los documentos discutidos salen del seguimiento, de la deuda exigible y de las centrales de riesgo hasta resolverse; el resultado «Reclamo o disconformidad» abre el reclamo.
- Protección al consumidor (art. 62 de la Ley 29571): sin gestiones por llamada, visita, WhatsApp o SMS fuera del horario, en fines de semana ni feriados, ni recordatorios antes del vencimiento sin consentimiento.
- Calificación de riesgo A–D de cada cliente y cola de trabajo del gestor ordenada por prioridad.
- Bloqueo de crédito por mora (días de atraso, calificación D o manual) con liberación del administrador; el módulo al_l10n_pe_collection_sale bloquea los pedidos de venta.
- Intereses moratorios (TEA pactada, año de 360 días) en el estado de cuenta y liquidación por nota de débito motivo 01 en borrador.
- Provisión de cobranza dudosa (68711 / 19) con gestiones como sustento, recuperación (7551), castigo hasta 3 UIT y expediente de cobranza en PDF.
- Centrales de riesgo: aviso previo, plazo, reporte, retiro cuando paga o a los 5 años (Ley 27489) y Excel.

## 2.20261021 — 21/10/2026

- Tablero de cobranza en la aplicación Tableros de Odoo (hoja de cálculo): indicadores, cartera por tramo y por gestor, vencimientos por semana, compromisos por estado, cobrado por mes y tablas de deudores y compromisos, con filtros por gestor, zona, cliente y periodo.
- El formulario de indicadores pasa a «Proyección y metas ‣ Indicadores del gestor».

## 1.20261021 — 21/10/2026

- Primera versión: cartera por gestor y zona, gestiones, compromisos evaluados solos, proyección de cobranza, metas, tablero, estado de cuenta, recordatorios, resumen diario y niveles de seguimiento en español.

# Cobranza: investigación de mercado y mejoras (v3)

Fecha: 22/10/2026. Continúa [ANALISIS_Y_PLAN_COBRANZA.md](ANALISIS_Y_PLAN_COBRANZA.md)
(v1/v2: cartera, gestiones, compromisos, proyección, metas, tablero, estado de cuenta, avisos).

## 1. Qué se usa en Perú

No hay un ranking público. En la práctica la cobranza se arma en cuatro capas:

| Capa | Productos | Qué aportan |
|---|---|---|
| ERP / facturador | Defontana (Cobranzas + Pay), Odoo, Bsale, Alegra… | Tramos de morosidad, correos masivos, estado de cuenta |
| Plataforma de cobranza y recaudo | **Kashio** (PE), **Moonflow** (Lima), **Solven** (Miraflores), Toku (CL), Intiza (AR, Mibanco) | Recordatorios por reglas, WhatsApp, conciliación bancaria, evaluación crediticia, portal de pago |
| Medios de pago | Culqi, Niubiz, Izipay, Yape Empresas, PagoEfectivo (CIP), recaudación BCP/BBVA/Interbank/Scotiabank | Links, QR, CIP, archivos de recaudación |
| Contact center / IA | Wolkvox, Mitrol, inConcert, Wati, Aurora Inbox, Bulk, Mozart | Marcador predictivo, WhatsApp, agentes de voz |

Internacionales de referencia (sin clientes peruanos verificados): Upflow, Chaser, Gaviti,
HighRadius. Lo que todos tienen y la app aún no: **segmentación/scoring**, **disputas** que
pausan la cobranza, **bloqueo de crédito**, **centrales de riesgo** (Chaser, Gaviti,
HighRadius) y priorización de la cartera de trabajo.

## 2. Marco legal peruano que afecta al módulo

| Tema | Regla | Fuente |
|---|---|---|
| Métodos abusivos (solo **consumidores**, B2C) | Ley 29571 art. 62: sin llamadas ni visitas entre **20:00 y 07:00**, ni **sábados, domingos y feriados**; no comunicar la deuda a terceros; no documentos que aparenten notificación judicial. Multas: BBVA 4.01 UIT (2025, recordatorios **antes del vencimiento**), BCP 3.78 UIT (2026, cartas a terceros) | Indecopi Res. 139-2025, 352-2026, 077-2021 |
| Centrales de riesgo | Ley 27489 art. 10 d): no difundir deudas pasados **5 años** del vencimiento o **2 años** desde su pago. Aviso previo al deudor: buena práctica (proyecto de ley en trámite). Indecopi sanciona reportar deudas no comprobadas | SBS, Indecopi 035-DPRC-2024 |
| Intereses | Tope BCRP may–oct 2026: 114.13 % (S/), 99.84 % (US$); moratorio máx. 15 % de la compensatoria máxima; solo si se pactó y sobre capital vencido; interés legal = TIPMN. Intereses moratorios: nota de débito motivo **01** (catálogo 10), inafectos al IGV | BCRP Circular 0008-2021 |
| Provisión tributaria | RLIR art. 21 f): morosidad acreditada con **gestiones de cobro** posteriores al vencimiento, proceso judicial o **más de 12 meses** vencida; discriminada en el Libro de Inventarios (PLE 3.6, cuenta 19) | Casación 15840-2025: hay que **documentar acciones concretas**, no basta un sistema automático |
| Castigo | RLIR art. 21 g): provisionada y acciones judiciales agotadas, salvo deuda por deudor **≤ 3 UIT** (S/ 16 500 en 2026) | Informe SUNAT 134-2001 |
| Títulos valores | Letra: protesto notarial, acción cambiaria 3 años. Factura negociable (Ley 29623): conformidad presunta a los 8 días hábiles → mérito ejecutivo | Ya cubiertos por al_l10n_pe_account_letter y al_l10n_pe_factoring |

## 3. Brecha y priorización

| # | Mejora | Prioridad | Estado |
|---|---|---|---|
| M1 | **Reclamos/disputas**: documentos en disputa salen del seguimiento nativo (`no_followup`), de la cartera exigible y de las centrales de riesgo hasta resolverse | P0 | v3 |
| M2 | **Guardas del art. 62** para consumidores (DNI/CE, sin RUC): horario 07:00–20:00, sin fines de semana ni feriados en llamadas, visitas, WhatsApp y SMS; recordatorio previo al vencimiento solo con consentimiento | P0 | v3 |
| M3 | **Calificación de riesgo** del cliente (A/B/C/D) por atraso promedio, mora actual, compromisos incumplidos y antigüedad; **prioridad** y **cola de trabajo** del gestor | P1 | v3 |
| M4 | **Bloqueo por mora**: automático (días de atraso o calificación D) o manual, con liberación del administrador; bloquea la confirmación de pedidos de venta | P1 | v3 (puente `al_l10n_pe_collection_sale`) |
| M5 | **Intereses moratorios**: tasa efectiva anual de la compañía o pactada con el cliente; en el estado de cuenta y **nota de débito motivo 01** en borrador por documento | P1 | v3 |
| M6 | **Provisión de cobranza dudosa y castigo** (RLIR 21 f/g): propone documentos con más de N meses vencidos, exige gestiones documentadas, asiento 68711/19x, castigo con marca ≤ 3 UIT y **expediente de cobranza en PDF** como sustento | P0 | v3 |
| M7 | **Centrales de riesgo**: aviso previo por correo, plazo de espera, reporte (Excel para Equifax/Sentinel), baja al pagar; bloquea deudas en disputa o de más de 5 años | P1 | v3 |
| M8 | Recaudación bancaria (BCP CREP, BBVA, Interbank, Scotiabank) | P0 | **Hecho** en `al_l10n_pe_bank_collection` con formatos configurables y el CREP del BCP precargado (layout más difundido; verificar con la ficha técnica). BBVA, Interbank y Scotiabank: crear su formato con la ficha de cada banco |
| M9 | Links de pago / PagoEfectivo / Yape en recordatorios | P1 | **Hecho**: botón y QR «Pagar en línea» en los avisos (v5) y PagoEfectivo (CIP) en `al_payment_pagoefectivo` |
| M10 | Comisiones de gestores, agencias externas, cobranza judicial | P2 | Hecho (v7) salvo cobranza judicial |
| M11 | Predicción de fecha de pago con IA, marcador de contact center | P2 | Pendiente |

## 4. Diseño v3

- **Reclamo** `l10n_pe.collection.dispute`: cliente, documentos (apuntes por cobrar abiertos),
  motivo, estado (abierto → resuelto a favor del cliente / a favor de la empresa / cancelado).
  Abierto: marca `no_followup` en sus apuntes; al cerrar lo restaura. La cartera muestra
  `in_dispute` y el reporte a centrales rechaza esos documentos. El resultado de gestión
  «Reclamo o disconformidad» ofrece crear el reclamo.
- **Consumidor**: `_l10n_pe_collection_is_consumer()` = tipo de documento distinto de RUC (o
  persona sin RUC). Ajustes: franja horaria (7–20) y feriados (calendario de la compañía si
  `resource` está instalado + fines de semana). La gestión por llamada, visita, WhatsApp o SMS
  fuera de franja da error (el administrador puede registrar una gestión pasada marcando
  «Registro posterior», que no valida horario porque la fecha la elige el gestor). El seguimiento
  automático no envía niveles con días negativos a consumidores sin consentimiento.
- **Calificación**: cron diario guarda en el contacto (por compañía no: es del cliente comercial)
  `score` 0–100, `rating` A–D y `priority` = vencido × (1 + (100 − score)/100). Pesos:
  atraso promedio (40), días de la deuda más antigua (30), compromisos incumplidos en 12 meses
  (20), % vencido de su cartera (10). Umbrales A ≥ 80, B ≥ 60, C ≥ 40, D < 40.
- **Bloqueo**: `hold_state` = libre / bloqueado automático / bloqueado manual / liberado hasta
  fecha. Reglas en Ajustes: días de atraso y calificación D.
- **Intereses**: `interest_rate` (TEA %) en compañía y contacto; interés = saldo × ((1+TEA)^(días/360) − 1),
  días desde el vencimiento (o desde el último interés facturado). Asistente → nota de débito en
  borrador por documento (`debit_origin_id`, motivo 01 si existe el campo, producto/cuenta de
  intereses de Ajustes, sin impuestos). Marca el apunte con la fecha hasta la que ya se facturó.
- **Provisión** `l10n_pe.collection.provision`: fecha de corte, meses mínimos (12), exige N
  gestiones (1); líneas = documento, cliente, saldo, días, gestiones, judicial; asiento debe
  68711 / haber 19x (cuentas y diario en Ajustes; la cuenta 19x sale de la cartera).
  **Castigo**: segundo asiento debe 19x / haber 12x conciliado con la factura; indica si el
  deudor supera 3 UIT (UIT de `al_account_base` si existe; si no, Ajustes).
- **Expediente** PDF por cliente: documentos, gestiones (fecha, canal, gestor, resultado,
  detalle), compromisos, estados de cuenta enviados, reclamos y reportes a centrales.
- **Central de riesgo** `l10n_pe.collection.bureau`: cliente, documentos, central
  (Equifax/Infocorp, Sentinel, Experian, Xchange, otra), aviso enviado → reportado → retirado;
  días de espera tras el aviso (Ajustes, 7). Cron: si los documentos se pagaron pasa a
  «por retirar» y avisa al gestor. Exporta Excel.

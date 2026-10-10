# Análisis de los puntos de la reunión de implementación (Odoo 19)

Revisión de los 11 puntos planteados por el cliente y del cronograma, contra:

- **Odoo 19 nativo** (Community `addons/` y Enterprise `ee19/`);
- **la suite propia** `ol_new_apps` (áreas OL-*);
- **lo instalado en el servidor**: `construccion_dev`, `newallcenter_dev` y
  `newallcenter_main` ya tienen `account_accountant`, `account_asset`,
  `account_loans`, `hr_payroll_account`, `l10n_pe_edi_stock`, `l10n_pe_reports`
  y los módulos de la suite de planillas, construcción, tareaje, letras y
  destinos.

Estado al 10/10/2026. Las estimaciones de esfuerzo son orientativas (días de
desarrollo, sin pruebas con el cliente) y deben confirmarse al cerrar el
alcance.

## Resumen

| # | Tema | ¿Lo cubre hoy? | Qué hace falta | Esfuerzo |
|---|---|---|---|---|
| 1 | Inicio el 01/12/2026 | No es técnico | Confirmar con gerencia; cronograma hacia atrás (punto 12) | — |
| 2 | Plan de cuentas | Sí (PCGE de `l10n_pe`) | Recibir el plan del contador y cargar sus subcuentas | 1–2 d (carga) |
| 3 | **Factoring** | **No** | **Módulo nuevo** `al_l10n_pe_factoring` (ver sección 3) | **10–15 d** |
| 4 | Depósitos a plazo y fondos de garantía | Parcial (cuentas y diarios) | Diarios y procedimiento; módulo solo si piden intereses y vencimientos | 1 d (config.) / 5–7 d (módulo) |
| 5 | Clasificación de materiales y su cuenta | Sí (categorías con cuentas) | Taller con el contador; plantilla de carga | 1–2 d (config. y carga) |
| 6 | Alquileres de oficina y almacén | Sí (gastos diferidos y factura recurrente) | Configurar; NIIF 16 solo si lo exigen | 0,5 d / 8–10 d (NIIF 16) |
| 7 | Activos fijos y depreciación automática | **Sí** (`account_asset`, instalado) | Configurar modelos por cuenta; carga inicial | 2–3 d |
| 8 | Activos de terceros e inventario y guías | Parcial (propietario/consignación) | Definir el tratamiento; guía para internos o con propietario | 0,5 d / 3–5 d |
| 9 | **Centro de costo del obrero por semana o día** | **Parcial** (por versión del contrato) | **Desarrollo**: obra en el tareaje y reparto en el asiento | **6–8 d** |
| 10 | **Varias cuentas por regla de nómina** | **Parcial** (por compañía, por AFP) | **Desarrollo**: mapeo de cuentas (portar el de v18) | **3–4 d** |
| 11 | Préstamos con tasas y amortización | **Sí** (`account_loans`, instalado) | Configurar; asiento del desembolso a mano | 1 d |
| 12 | Cronograma de maestros y capacitaciones | Herramienta lista (`al_project_gantt_*`) | Armar el plan en un proyecto | 1 d |

**Desarrollos nuevos a presupuestar:** factoring (3), centro de costo por
tareaje (9) y mapeo de cuentas de nómina (10). Opcionales según la respuesta
del cliente: depósitos a plazo con intereses (4), NIIF 16 (6) y guías de bienes
de terceros (8).

---

## 1. Inicio del sistema el 01/12/2026

No es una cuestión del sistema: lo confirma gerencia. Lo que sí condiciona la
fecha es tener **antes del 15/11** el plan de cuentas (punto 2), la
clasificación de materiales (punto 5) y la dinámica de factoring (punto 3),
porque el factoring es el único desarrollo grande que el cliente marcó como
urgente. Ver el cronograma propuesto en el punto 12.

## 2. Plan de cuentas

**Hay:** el PCGE completo de la localización (`l10n_pe`, más de 1 200 cuentas
en `newallcenter_dev_1`), con las cuentas que usan los módulos de la suite
(letras 1232–1234, 4511, 6734; retenciones; detracciones; destinos 9x/79).

**Falta:** el plan propio del cliente (subcuentas, nombres) para cargarlo con el
importador nativo (*Contabilidad ▸ Configuración ▸ Plan de cuentas ▸
Importar*) y asignar las cuentas por defecto de los módulos. Dependencia del
cliente: el contador aún no lo envía.

## 3. Factoring (urgente)

### Qué hay

| Pieza | Dónde | Sirve para factoring |
|---|---|---|
| Nada específico para Perú | Odoo 19 CE/EE | — |
| `l10n_cl_edi_factoring` (Chile) | `ee19/l10n_cl_edi_factoring` | Solo como patrón: marca la factura como cedida y pasa la deuda al factor con un asiento (`wizard/l10n_cl_aec_gen.py:27-59`) |
| Cuenta `1214 Facturas en descuento`, 4511/45x, 673x | Plan PCGE (`l10n_pe`) | Sí, las cuentas existen |
| Letras de cambio: descuento, cobranza, protesto, cuentas puente por tipo y moneda | `al_l10n_pe_account_letter` | **Sí, como base técnica**: asistente de operaciones bancarias (`wizards/letter_bank_wizard.py`), tabla de cuentas (`l10n_pe.letter.account.config`), liquidación neto + intereses + comisión contra la obligación |
| Requisitos de letras | `docs/letras/REQUISITOS_LETRAS.md:275-296` | Ya separa: la factura negociable **no** es una letra |

### Marco (de `docs/md/factoring_en_el_peru_y_prompt_odoo_19.md`)

- **Sin recurso** (el factor asume el riesgo): se da de baja la cuenta por
  cobrar (12); la diferencia entre nominal y desembolso es gasto financiero (67).
- **Con recurso** (el cedente mantiene el riesgo): la cuenta por cobrar **no**
  se da de baja; el adelanto es una obligación financiera (45) y los intereses
  se devengan.
- **IGV:** la cesión del crédito no está gravada; intereses y comisiones siguen
  las reglas de servicios financieros. No se emite comprobante por la cesión.
- **Factura negociable:** se anota en CAVALI; el plazo de conformidad del
  adquirente (Ley 29623 y modificatorias) debe validarse con el asesor legal
  antes de automatizar alertas.

### Pendiente del cliente (bloquea el diseño final)

1. ¿Con recurso, sin recurso o ambos?
2. ¿Qué factores usan y cómo liquidan (adelanto del 80–90 % y saldo al cobro,
   o desembolso único)? ¿Intereses por adelantado o al vencimiento?
3. ¿Comisiones y gastos con factura del factor (crédito fiscal) o solo en la
   liquidación?
4. ¿Factoring en dólares?
5. ¿Quién cobra al cliente final y cómo se entera la empresa del pago?
6. Un ejemplo real de liquidación del factor.

### Propuesta: módulo `al_l10n_pe_factoring` (OL-ACCOUNTING)

Reutiliza los flujos nativos (factura, pago, conciliación) y el patrón del
módulo de letras; no duplica la factura.

**Modelo `l10n_pe.factoring`** (operación con un factor), con líneas por
factura:

| Campo | Uso |
|---|---|
| Factor (`res.partner`), contrato, modalidad (con / sin recurso), moneda | Cabecera |
| Facturas cedidas (`account.move` de cliente publicadas, con saldo) | Líneas: nominal, % adelantado, fecha de vencimiento, número CAVALI |
| Intereses, comisiones, gastos, retenido (fondo de garantía del factor) | Liquidación |
| Asientos: cesión, desembolso, liquidación final, recompra | Trazabilidad |
| Estados: borrador → cedida → desembolsada → liquidada / recomprada | Flujo |

**Asientos (cuentas configurables por modalidad y moneda, como en letras):**

| Momento | Sin recurso | Con recurso |
|---|---|---|
| Cesión | 1214 (factor) / 1212 (concilia la factura: queda pagada) | Sin asiento: la factura sigue pendiente en 1212 (NIIF 9) y se marca «Cedida» |
| Desembolso | Banco + 673x (interés) + 639x (comisión) / 1214 (adelanto) | Banco + 373x (interés diferido) + 639x / 45x (obligación) |
| Devengo | — | 673x / 373x (mensual) |
| Cobro del factor al cliente | Banco (saldo retenido) / 1214 | 45x + banco (retenido) / 1212 (la factura queda pagada) |
| Impago (recompra) | — | 45x / banco (devuelve el adelanto); la factura sigue pendiente |

> Implementado en `al_l10n_pe_factoring` (versión 2): con recurso la factura no
> aparece pagada hasta que el cliente paga al factor (decisión del 10/10/2026).

**Integración:**

- Botón «Ceder a factoring» en la lista de facturas (selección múltiple) y
  pestaña «Factoring» en la factura (factor, estado, operación).
- Marca en la factura para que no se cobre dos veces ni se envíe a letras.
- Reportes: cartera cedida por factor, vencimientos, costo financiero.
- PLE y SIRE: la factura sigue siendo la misma; los asientos de cesión van a los
  libros como cualquier asiento.
- Multicompañía según las reglas de la suite.

**Esfuerzo:** 10–15 días (modelo y asientos 5–7, interfaz y reportes 3–4,
tests y documentación 2–4). Sin integración con la API de CAVALI, que sería
otra fase.

## 4. Depósitos a plazo y fondos de garantía

**Hay (nativo):** diarios de tipo banco/efectivo/varios y las cuentas PCGE
`1062 Depósitos a plazo`, `1071 Fondos en garantía`, `164x/174x Depósitos en
garantía`. Una transferencia entre diarios mueve el dinero; los intereses se
registran con un asiento (puede ser recurrente).

**Propuesta inmediata (configuración, 1 día):** un diario por depósito o fondo
con su cuenta, el procedimiento de apertura, interés y cancelación, y un
informe de saldos por cuenta 106/107.

**Si piden intereses automáticos, vencimientos y renovaciones:** módulo pequeño
(5–7 días): modelo de depósito con capital, tasa, plazo, devengo mensual y
alerta de vencimiento. Coordinar la dinámica con el contador antes de
presupuestarlo, como pidió el cliente.

## 5. Clasificación de materiales y suministros

**Hay:** categorías de producto (`product.category`) con su cuenta de
existencias, de ingreso y salida de stock y de gasto (`stock_account`, nativo).
La suite añade en el producto la tabla 5 del kardex SUNAT, la clasificación del
RCE (tabla 23) y el tipo de detracción.

**Propuesta:** taller con el contador para fijar el árbol de categorías y la
cuenta de cada una (60x/20x/25x/61x) **antes** de cargar los maestros; luego
plantilla Excel de productos por categoría con el importador nativo. En
`newallcenter_dev_1` ya hay 44 categorías: revisarlas en ese taller.

## 6. Alquileres de oficina y almacén

La respuesta dada («solo por diario») es correcta, y hay dos ayudas nativas ya
instaladas:

- **Factura de proveedor recurrente** (Community): se repite cada mes sola.
- **Gastos diferidos** (Enterprise, `account_accountant`): el pago adelantado o
  la garantía se reparte mes a mes con las fechas de inicio y fin en la línea.
- Si el arrendador es sujeto de detracción, la suite ya trae el tipo
  «Arrendamiento de bienes» (`al_l10n_pe_detraction`).

**No hay** NIIF 16 (derecho de uso y pasivo por arrendamiento). Si el contador
lo exige, se aproxima con `account_asset` (derecho de uso) y `account_loans`
(pasivo), o con un módulo propio (8–10 días).

## 7. Activos fijos y depreciación automática

**Sí está en el alcance técnico** y ya instalado: `account_asset` (Enterprise).

- Depreciación lineal, degresiva o degresiva y luego lineal; prorrata por días
  o periodos; valor residual.
- Los asientos de depreciación se crean al confirmar el activo y se publican
  solos en su fecha (cron estándar).
- **Modelos por cuenta**: al registrar la factura de proveedor en la cuenta 33x,
  el activo se crea solo (borrador o validado), uno por unidad si se desea.
- Venta, baja, revaluación y pausa con asistente.
- La suite añade los datos SUNAT del activo y el **libro 7.1** (y 7.3, 7.4) en
  `al_l10n_pe_ple`.

**Por hacer:** configurar los modelos de activo por clase (tasas tributarias),
cargar los activos existentes con su depreciación acumulada
(`already_depreciated_amount_import`) y capacitar. Esfuerzo: 2–3 días.

**No incluye:** inventario físico de activos (ubicación, responsable, etiquetas)
ni el vínculo activo ↔ equipo de mantenimiento. Si lo piden, desarrollo aparte.

## 8. Activos o equipos de terceros

Depende de qué quiera controlar el cliente:

- **No van al registro de activos**: un bien de terceros no es activo de la
  empresa (no se deprecia ni va al libro 7.1).
- **Control físico en inventario: sí.** Odoo maneja el **propietario**
  (consignación, `owner_id`): el bien está en el almacén, se mueve, pero **no
  entra a la valorización** ni genera asientos.
- **Guía de remisión:** `l10n_pe_edi_stock` emite la guía en salidas (motivo 05
  consignación, 13 otros, etc.), pero no en transferencias internas y no informa
  al propietario.

**Propuesta:** si los equipos de terceros salen a obra, usar una operación de
salida con el motivo adecuado (configuración, medio día). Si necesitan guía en
traslados internos o mostrar al propietario, extender `l10n_pe_edi_stock`
(3–5 días).

## 9. Centro de costo del personal obrero por semana o por día

**Hay:**

- Analítica por trabajador en su versión de contrato (`hr.version`, nativo) y en
  la regla salarial; `al_hr_pe_account` la lleva al asiento del lote
  (`hr_payslip_run_move.py:145`).
- Cambio **entre periodos**: con planilla semanal, basta crear una versión
  nueva con la otra cuenta analítica desde la fecha del cambio.
- Distribución fija por porcentaje (p. ej. 60 % obra A, 40 % obra B).

**No hay:** reparto **dentro del periodo** según dónde trabajó cada día. La
boleta toma una sola versión (`hr_payslip.py:1270`); el tareaje
(`al_hr_pe_attendance`) guarda días y horas pero no la obra; la obra de
planillas (`al_hr_pe_construction`) no está enlazada al proyecto con analítica.
Es el pedido que también hizo Think y quedó sin respuesta.

**Propuesta (6–8 días):**

1. Obra o proyecto (con su cuenta analítica) en la línea diaria del tareaje y
   en la asistencia; por defecto, la de la versión del trabajador.
2. Enlace entre la obra de planillas y el proyecto de obra (que ya tiene
   analítica en `al_construction_material_request`).
3. Al contabilizar el lote, la distribución analítica de cada boleta sale de
   las horas o días por obra del periodo (p. ej. 3 días obra A, 2 días obra B →
   60/40) y se escribe en sus líneas del asiento.
4. `al_account_destinations` ya reparte luego el gasto 6x→9x por analítica.

## 10. Varias cuentas contables por regla de nómina

**Hay en Odoo 19:** una cuenta débito y una crédito por regla, **por compañía**
(campo `company_dependent`); cuentas distintas duplicando estructuras (p. ej.
empleados y obreros). La suite añade: abono a la cuenta de **cada AFP**
(`afp_rule_ids` + cuenta en la afiliación) y detalle por trabajador.

**No hay:** cuenta según tipo de trabajador, departamento o centro de costo
dentro de una misma estructura. En v18 existía `hr_salary_rule_line` y **no se
portó** (TODO en `al_hr_pe_account/models/hr_main_parameter_accounts.py:203`).

**Propuesta (3–4 días):** tabla de mapeo por regla: condición (tipo de
trabajador, departamento, cuenta analítica o estructura) → cuenta débito y
crédito, con la cuenta de la regla como valor por defecto, aplicada al armar el
asiento del lote. Así se cubre el caso típico 62x administración / 62x obra /
9x por centro de costo, sin duplicar estructuras.

## 11. Préstamos (tasas, capital, amortización y contabilización)

**La respuesta «no hay módulo» ya no es exacta en Odoo 19:** `account_loans`
(Enterprise) está instalado.

- Cálculo de la tabla con tasa, plazo, primera cuota y base de días (cuota
  francesa con tasa, lineal sin ella), o importación de la tabla del banco.
- Al confirmar, cada cuota genera su asiento (capital a largo plazo, interés a
  gasto, cuota a corto plazo) y se publica sola en su fecha; reclasificación
  mensual largo/corto plazo; cierre anticipado.

**Límites:** el asiento del desembolso se registra a mano; una sola moneda (la de
la compañía), y la tasa variable se maneja reimportando la tabla.

**Préstamos al personal** (si también preguntan): `al_hr_pe_benefits` ya genera
cuotas y las descuenta en la boleta.

## 12. Cronograma: maestros, carga y capacitaciones

Para compartir el plan se puede usar el **Gantt de la suite**
(`al_project_gantt_backend`, ya instalado en el servidor): tareas con
dependencias, hitos, ruta crítica, línea base y exportación a Excel/PDF, también
en la web para el cliente.

**Propuesta de cronograma hacia el 01/12/2026** (a ajustar con gerencia):

| Semana | Del | Al | Actividad | Responsable |
|---|---|---|---|---|
| 1 | 13/10 | 17/10 | Envío de plantillas de maestros (plan de cuentas, contactos, productos y categorías, activos, empleados, saldos); definir factoring con el contador | Consultor / cliente |
| 2 | 20/10 | 24/10 | Taller de clasificación de materiales y cuentas; dinámica de depósitos y fondos; inicio del desarrollo de factoring | Consultor / contador |
| 3–4 | 27/10 | 07/11 | Recepción y carga de maestros; desarrollo de factoring y de nómina (puntos 9 y 10) | Cliente / desarrollo |
| 5 | 10/11 | 14/11 | Carga de activos y préstamos; pruebas de factoring y nómina | Consultor |
| 6 | 17/11 | 21/11 | Capacitaciones por área (ventas y facturación, compras e inventario, contabilidad, planillas) | Consultor |
| 7 | 24/11 | 28/11 | Saldos iniciales, pruebas finales y aprobación | Cliente / consultor |
| — | 01/12 | — | Inicio en producción | — |

## Decisiones que necesitamos del cliente

1. Confirmación de la fecha de inicio.
2. Plan de cuentas (punto 2) y respuestas de factoring (sección 3).
3. Si los depósitos a plazo requieren intereses y vencimientos automáticos.
4. Si exigen NIIF 16 para los alquileres.
5. Qué control quieren de los equipos de terceros (solo inventario o también
   guías y propietario).
6. Criterio de reparto del obrero: por días o por horas del tareaje.
7. Criterios de las cuentas de nómina (tipo de trabajador, departamento o
   centro de costo).

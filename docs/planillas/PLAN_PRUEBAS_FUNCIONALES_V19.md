# Plan de pruebas funcionales — Planillas Perú v19

**Base de datos:** `ol_pe_v19` · **Config:** `/home/och/odoo/ce19/cfg/my/pe.cfg`
**Alcance:** los 6 módulos `al_hr_pe*` migrados en las fases 0-8 del
`PLAN_MIGRACION_PLANILLAS_V19.md`, ejercitados de punta a punta sobre datos
reales de trabajo (no fixtures de test) con **10 empleados** y sus usuarios.

Los 92 tests automáticos verifican unidades y un e2e sintético. Este plan
cubre lo que los tests no ven: la **operación real por pantalla**, con la
configuración completa de una empresa peruana y las 102 reglas salariales
del cliente (`Regla salarial (hr.salary.rule).xlsx`).

## Decisiones tomadas

| Tema | Decisión |
|---|---|
| Reglas del Excel | Van a una estructura **nueva** `BASE MG`; la estructura `BASE` (64 reglas migradas, cubierta por tests) queda intacta para comparar |
| Compañías | `Comercial Demo Perú S.A.C.` (principal, 10 empleados) + 2ª compañía para aislamiento multicompañía |
| Código Python v18 | Se **sanea al importar**: `contract`→`version`, `payslip.wage`→`version.wage`, y se descarta la condición por defecto de Odoo que el export arrastra en las 102 filas |

## Método

- Cada fase tiene un script idempotente en `docs/planillas/pruebas/` que se
  ejecuta con `python3 odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http < fNN_*.py`.
- Los scripts **crean datos y verifican**: cada comprobación imprime
  `OK`/`FALLA` con el valor esperado y el obtenido. Ninguna fase se da por
  buena con fallas abiertas.
- Los hallazgos se anotan en la tabla de resultados al final de este
  documento, con el arreglo aplicado o el motivo de aplazarlo.
- Relanzar un script no duplica datos (búsqueda por clave funcional antes
  de crear).

---

## Fase 0 — Preparación ✅

- [x] **Bug bloqueante corregido**: la plantilla Excel no se podía
  descargar. `action_download_template` era un botón `type="object"`, así
  que el cliente web guardaba el asistente antes de invocarlo y el guardado
  fallaba por los campos obligatorios del paso "Configurar"
  (`struct_id`, `payslip_run_id`) — justo los que aún no se pueden llenar
  cuando lo que se busca es la plantilla. Ahora se sirve por la ruta
  `/al_hr_pe_import/template/<modelo>` desde un enlace, sin guardar nada.
- [x] **Saneo v18→v19 en el importador de reglas** (opción *Adaptar código
  v18 → v19*, activa por defecto), necesario para que el Excel del cliente
  sea utilizable.
- [x] Tests de regresión de ambos arreglos (módulo en 20/20).

## Fase 1 — Configuración maestra

Parámetros de la compañía sin los que no se calcula una boleta:

1. `hr.main.parameter`: RMV, asignación familiar, tasas de quincena,
   reglas/inputs de referencia del motor de beneficios.
2. `l10n_pe.hr.uit`: UIT del ejercicio y tramos de renta de 5ta.
3. Catálogos PLAME: tipo de trabajador, situación, régimen laboral,
   motivos de cese, tipos de suspensión.
4. `hr.membership`: AFP (Integra, Prima, Profuturo, Hábitat) con sus tasas
   de flujo/mixta y comisión, más ONP; `hr.social.insurance` (EsSalud/EPS).
5. `hr.period`: periodos mensuales del ejercicio 2026.
6. Calendarios: jornada general 48h, jornada nocturna, jornada parcial.
7. Cuentas contables y diarios de planilla (company_dependent).

**Verifica:** que un `hr.payslip` en borrador se pueda calcular sin errores
de configuración faltante.

## Fase 2 — Reglas salariales del cliente

1. Crear la estructura `BASE MG` (tipo Employee).
2. Importar las 102 filas del Excel con el asistente **por pantalla**
   (ejercita la descarga de plantilla, la detección de hoja, el progreso
   OWL y el reporte de resultados).
3. Informe de diferencias `BASE` (64 migradas) ↔ `BASE MG` (102 del
   cliente): códigos solo en una, y diferencias de código Python en los
   comunes.
4. Compilar el código Python de las 102 reglas y reportar las que no
   compilan o usan API inexistente en v19.

**Verifica:** 102 reglas creadas, 0 errores, ninguna con `contract`.

## Fase 3 — 10 empleados con usuarios

Perfiles diseñados para que entre los diez se ejerciten **todas** las
personalizaciones:

| # | Perfil | Qué ejercita |
|---|---|---|
| 1 | Sueldo fijo, 2 hijos, AFP Integra flujo | asignación familiar, AFP flujo |
| 2 | Sueldo alto, EPS, AFP Prima mixta | renta 5ta con retención, EPS 2.25%, comisión mixta |
| 3 | Turno nocturno, ONP | sobretasa nocturna, horas extra 25/35, ONP |
| 4 | Remuneración por horas (`wage_type = hourly`) | cálculo por horas del básico y de faltas |
| 5 | Préstamo + adelanto | descuentos al neto, cuotas fin de mes |
| 6 | Subsidio por enfermedad/maternidad | DMED, subsidios, base de 12 meses |
| 7 | Retención judicial + sindicalizado | `RET_JUD`, `DES_SIN`, categoría DES_NET |
| 8 | Cese a mitad del periodo | liquidación, truncos de CTS/grati/vacaciones |
| 9 | Practicante (modalidad formativa) | régimen sin aportes, subvención |
| 10 | Extranjero | tipo de documento CE, sin asignación familiar |

Cada uno con `res.users` interno propio, más dos usuarios de rol
(analista = *Payroll User*, jefe = *Payroll Manager*) para probar permisos.
Versiones (`hr.version`) con los datos PLAME completos.

**Verifica:** los 10 con documento válido y único, versión vigente,
membresía AFP/ONP y cuenta de haberes.

## Fase 4 — Asistencias y tareaje

1. Turnos y roles de planning (incluido el ciclo atípico y el turno
   nocturno).
2. Importación de asistencias del mes desde Excel (asistente).
3. Tareaje: clasificación de días, horas extra 25/35/100, nocturnas,
   faltas, feriados.
4. Monitor de asistencias.

**Verifica:** los días y horas volcados a las entradas de trabajo coinciden
con lo importado y respetan el remapeo `DLAB` peruano.

## Fase 5 — Boletas mensuales y quincena

1. Lote del periodo, generación de las 10 boletas, cálculo.
2. Importación de inputs (novedades) por Excel sobre el lote.
3. Boleta de quincena (reglas `_AQ`).
4. Cuadre manual de al menos 3 boletas contra cálculo hecho a mano.

**Verifica:** totales por categoría (ING, DES_AFE, APOR_TRA, DES_NET,
APOR_EMP), neto en letras, redondeo SUNAT.

## Fase 6 — Beneficios sociales

CTS del semestre, gratificación (con bono 9%), vacaciones (récord, goce y
liquidación vacacional), liquidación de cese del empleado 8, provisiones
mensuales, subsidios, utilidades y renta de 5ta categoría.

## Fase 7 — Contabilización

Asiento del lote de planilla (3 bloques + AFP por membresía), asientos de
beneficios sociales, distribución analítica, cuadre y validación.

## Fase 8 — Reportes, TXT y PLAME

Boleta PDF (D.S. 001-98-TR), envío por correo con enlace de confirmación,
certificados y contratos, TXT bancarios de haberes y CTS (5 bancos),
exportadores PLAME (.rem/.jor/.snl/.toc) y AFPNet.

## Fase 9 — Multicompañía, permisos y cierre

Segunda compañía con sus propios datos, aislamiento de registros, permisos
de los usuarios de rol, y elaboración del informe final de hallazgos.

---

## Resultados

| Fase | Estado | Comprobaciones | Hallazgos |
|---|---|---|---|
| 0 | ✅ | 6 tests nuevos | Descarga de plantilla rota; saneo v18→v19 inexistente |
| 1 | ✅ | 18/18 | Faltaba el input de retención extraordinaria de 5ta |
| 2 | ✅ | 20/20 | 8 APIs v18 sin traducir; quincena mezclada con la mensual; inputs no habilitados en estructuras nuevas |
| 3 | ✅ | 13/13 | — |
| 4 | ✅ | 11/11 | Turnos que cruzan medianoche mal leídos (todo el mes como "marcación incompleta") |
| 5 | ✅ | 21/21 | Faltaban los parámetros de quincena y el campo `rate` de los días trabajados; 3 reglas del cliente sin rama por defecto |
| 6 | ✅ | 24/24 | Los motores de beneficios comparan la **regla concreta** de los parámetros: con otra estructura salían vacíos |
| 7 | ✅ | 10/10 | El Excel no trae cuentas contables: se configuran por categoría |
| 8 | ✅ | 13/13 | El TXT bancario usaba `slip.number` (no existe en v19) y `slip.net_wage` (0 en Perú); el `.rem` de PLAME salía vacío sin códigos SUNAT |
| 9 | ✅ | 12/12 | — |

**145 comprobaciones funcionales en verde.**
Suite automática tras los arreglos: **135 tests, 0 fallos**
(al_hr_pe 21, benefits 13, account 5, attendance 43, reports 24, import 29).

## Hallazgos y arreglos

### En los módulos (corregidos)

1. **Plantilla Excel imposible de descargar** (`al_hr_pe_import`). El botón
   era `type="object"`: el cliente web guardaba el asistente antes de
   invocarlo y el guardado fallaba por los campos obligatorios del paso
   "Configurar" — que es justo lo que no se puede llenar sin la
   plantilla. Ahora se sirve por `/al_hr_pe_import/template/<modelo>`
   desde un enlace, sin guardar nada. `struct_id` y `payslip_run_id`
   dejaron de ser obligatorios en el modelo y se validan al importar.
2. **Sin traducción del código v18** (`al_hr_pe_import`). El Excel del
   cliente traía `contract`, `payslip.wage`, `labor_regime`,
   `retirement_fund`, `exception`, `is_older`, `commision_type`,
   `fixed/mixed_commision`, `prima_insurance`,
   `insurable_remuneration` y los valores `practice` /
   `reg_const_civil`, ninguno existente en v19. La opción *Adaptar
   código v18 → v19* los traduce y anota cada cambio en el registro.
   Además descarta la condición por defecto de Odoo, que el export
   arrastraba en las 102 filas y habría dejado la planilla sin calcular.
3. **Asistencias solo por nombre exacto** (`al_hr_pe_import`). Los
   relojes biométricos exportan el documento: ahora la columna EMPLEADO
   admite nombre o documento (y tolera que openpyxl lo entregue como
   número).
4. **Turnos que cruzan la medianoche** (`al_hr_pe_attendance`). Un
   calendario nocturno (22:00-24:00 + 00:00-06:00) se leía como jornada
   00:00-24:00 con 16 h de refrigerio, y **todos** los días del vigilante
   caían como "marcación incompleta", sin horas nocturnas. Ahora los dos
   tramos se unen en un turno continuo 22:00 → 30:00.
5. **Configuración de quincena ausente** (`al_hr_pe_benefits`). Las 33
   reglas `_AQ` del cliente leen `fortnightly_type`, `tasa`,
   `compute_af` y `compute_afiliacion`, que la migración no portó: sin
   ellos toda regla de quincena aborta. Añadidos con su sección en los
   parámetros principales.
6. **Sobretasa de los días trabajados** (`al_hr_pe`). Las reglas de horas
   extra del cliente leen `worked_days['HE25'].rate` (25, 35, 100), que
   v19 no expone. Se añade `rate` derivado del factor nativo
   `amount_rate`, y los tipos PE pasan a declararlo (HE25 = 1.25,
   HE35 = 1.35, HE100 = 2.0), que es además lo correcto para el motor
   nativo.
7. **TXT bancario con el número de boleta de la v18**
   (`al_hr_pe_reports`). `_iter_origin_lines` leía `slip.number`, campo
   que v19 eliminó: generar el TXT de haberes desde un lote reventaba
   con `AttributeError`. Ahora usa `slip.name`.
8. **TXT bancario con importes en cero** (`al_hr_pe_reports`). El abono
   salía de `slip.net_wage`, el neto **nativo** (categoría NET de Odoo),
   que la planilla peruana no usa: el neto lo calcula la regla `NETO`.
   Ahora toma la regla configurada en los parámetros
   (`net_to_pay_sr_id` / `net_fortnightly_sr_id`), con el neto nativo
   como respaldo si no hay parámetros.

### En los datos del cliente (a corregir en origen)

1. **Reglas sin rama por defecto**: `A_JUB`, `COMFI` y `SEGI` encadenan
   ramas por nombre de AFP y no contemplan la afiliación "SIN RÉGIMEN"
   de los practicantes. `result` queda sin asignar y **aborta el cálculo
   de la boleta completa**, no solo de esa línea. Las pruebas las
   completan con `result = 0`; conviene arreglarlo en el Excel.
2. **`fourth-fifth`** se compara como régimen laboral y no existe en el
   selector de v19 (tampoco en la estructura migrada): la condición
   nunca se cumple. Es deuda heredada de v18.
3. **18 reglas comunes difieren** del código migrado en `BASE`
   (`informe_diferencias_reglas.md`): las del cliente añaden el régimen
   de construcción civil y conceptos propios (BUC, BONIFC, CONAFOV,
   DES_SIN, ESC, MOV, OTRDSC, DOM).
4. **Sin cuentas contables ni códigos SUNAT**. El Excel no trae ninguna
   de las dos cosas: las cuentas se configuran por categoría (fase 7) y
   el concepto de la Tabla 22 se hereda de la regla homónima de `BASE`
   (fase 2). Quedan 35 códigos sin equivalente —subtotales, bases de
   cálculo y los conceptos propios del cliente—, que deben mapearse a
   mano si han de aparecer en PLAME.

### Configuración que v19 hace distinto (a tener en cuenta al implantar)

* Toda `hr.payroll.structure` nueva nace con 8 reglas genéricas de Odoo
  (BASIC/GROSS/NET…) que hay que retirar de una planilla peruana.
* Los `hr.payslip.input.type` están ligados a estructuras concretas
  (`struct_ids`): sin habilitarlos en la estructura nueva, toda novedad
  se rechaza al importarla.
* `primary_bank_account_id` del empleado es **calculado**: la cuenta de
  haberes se enlaza en el many2many `bank_account_ids`.
* `account.journal.bank_id` es un related de su cuenta bancaria; el
  formato de banco del TXT se toma de ahí.
* El TXT exige moneda y tipo de cuenta en cada `res.partner.bank`, y la
  cuenta de cargo BCP debe tener 13 dígitos.
* El estado confirmado de una boleta es `validated`, no `done`.
* Los parámetros principales admiten **una sola regla por concepto**: si
  se usan varias estructuras hay que decidir a cuál apuntan, o los
  motores de beneficios descartan a los trabajadores en silencio.

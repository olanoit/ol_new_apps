# Plan de migración — Planillas Perú v18 → Odoo 19

**Fuente**: `/home/och/odoo/ce18/al/montegrande/alta/al_hr_payroll` (27 módulos)
**Destino**: `/home/och/odoo/ce19/myodoo/ol_new_apps` (5 módulos `al_hr_pe_*`)
**Fecha de análisis**: 2026-07-22 · basado en lectura de código de los 27 módulos
(no de su documentación: `REFACTOR_PROGRESS.md` afirma limpiezas que el código
desmiente — ver §7.1).

---

## 1. Resumen ejecutivo

La suite v18 son **27 módulos** con un núcleo sólido de localización peruana
(PLAME, AFP/ONP, CTS, gratificaciones, renta 5ta, subsidios EsSalud,
utilidades D.L. 892) enterrado bajo tres capas de deuda:

1. **Duplicación estructural**: 4 módulos contables `_move`/`_move_analytic`
   que son el mismo código al ~90 % (wizards byte-idénticos); el método
   `refresh_from_work_entries` copiado y divergido en 3 módulos; 4 variantes
   del mismo SQL de asiento de planilla.
2. **Reimplementación de Enterprise**: `hr_assistance_planning` (~2 700
   líneas) es un clon del módulo `planning` EE (gantt, plantillas de turno,
   recurrencias, copiar-semana); `hr_importers` reinventa `base_import` con
   xlrd deprecado y auto-`pip install` en runtime.
3. **Cambio estructural de v19**: `hr.contract` ya no existe — se fusionó en
   **`hr.version`** sobre el empleado, y `hr.payslip` usa `version_id`. Todo
   el código v18 (que cuelga ~25 campos y 6 overrides de `hr.contract`) debe
   re-basarse, lo que hace inviable una migración "tal cual" y justifica el
   refactor completo.

**Propuesta**: 27 módulos → **5 módulos** (§3), reescritos sobre el core v19,
multicompañía por diseño (§5), con la lógica peruana preservada línea a línea
desde los métodos identificados en §4.

| Métrica | v18 | v19 propuesto |
|---|---|---|
| Módulos | 27 | 5 |
| Clon de planning EE | ~2 700 líneas | 0 (nativo + capa fina) |
| Módulos contables | 4 (duplicados) | 1 (flag analítica) |
| Copias de `refresh_from_work_entries` | 3 | 1 |
| Importadores | 3 frameworks (2 con xlrd) | 1 (openpyxl, mixin) |

---

## 2. Veredicto módulo a módulo (27)

Leyenda: **M** migrar (reescrito sobre v19) · **F** fusionar en un módulo
nuevo · **N** reemplazar por nativo v19 · **D** descartar.

| # | Módulo v18 | Veredicto | Destino v19 / motivo |
|---|---|---|---|
| 1 | `report_tools` | **F** | Helpers (XLSX, `custom_round` HALF_UP SUNAT) → `al_hr_pe` como mixins |
| 2 | `popup_it` | **D** | Sustituir usos por `display_notification` + `ir.attachment`/act_url nativos |
| 3 | `hr_base` | **M/F** | Tablas PLAME/AFP/periodos/UIT → `al_hr_pe` (el módulo más limpio del set) |
| 4 | `hr_fields` | **F** | Campos PE → `al_hr_pe`; `hr.contract` → **`hr.version`**; overrides de work entries re-derivados del core v19 |
| 5 | `hr_social_benefits` | **M** | Motor `compute_benefits` (CTS/grati/liquidación) → `al_hr_pe_benefits` |
| 6 | `hr_payslip_run_move` | **F** | → `al_hr_pe_account` (asiento por lote; núcleo SQL unificado) |
| 7 | `hr_fifth_category` | **M** | Renta 5ta (proyección anual/UIT/tramos) → `al_hr_pe_benefits` |
| 8 | `hr_vacations` | **M** | Récord vacacional D.L. 713 → `al_hr_pe_benefits` (fix bug `unlink` global, §7.3) |
| 9 | `hr_leave` | **F/N** | Suspensiones TABLA 21 y liquidación vacacional → `al_hr_pe_benefits`; integración ausencia↔work entry → nativo `hr_payroll_holidays` |
| 10 | `hr_assistance_planning` | **N** | `planning` + `hr_payroll_planning` EE; conservar capa PE: régimen atípico minero, monitor de asistencia, fotocheck, tipos de turno → `al_hr_pe_attendance` |
| 11 | `hr_attendance_payslip` | **F** | Clasificación PE (nocturnidad 06-22, HE 25/35/100, DOM/FER) sobre `hr_payroll_attendance` nativo → `al_hr_pe_attendance` |
| 12 | `hr_advances_and_loans` | **M** | Adelantos/préstamos con cronograma → `al_hr_pe_benefits` |
| 13 | `hr_provisions` | **M** | Provisión mensual CTS/grati/vac → `al_hr_pe_benefits` (asiento en `al_hr_pe_account`) |
| 14 | `hr_subsidies` | **M** | Subsidios EsSalud (20 días empleador, base 12 meses) → `al_hr_pe_benefits` |
| 15 | `hr_importers` | **D** | xlrd + auto-pip; sustituido por el framework de `al_hr_payroll_import` y `base_import` |
| 16 | `hr_employee_documents` | **F/N** | Vencimientos+notificaciones → capa fina en `al_hr_pe`; almacenamiento → Documents EE; `hr.salary.history` se descarta (tracking nativo de `wage`) |
| 17 | `hr_fifth_category_certificate` | **F** | Reporte del certificado → dentro de renta 5ta en `al_hr_pe_benefits` |
| 18 | `hr_certificate_letter` | **F** | Certificado de trabajo + carta CTS → `al_hr_pe_reports` |
| 19 | `hr_print_contract` | **M** | Plantillas de contrato → `al_hr_pe_reports` (re-basado en `hr.version`; fix `&nbsp;` y `sanitize`) |
| 20 | `hr_vacation_import` | **D** | Cubierto por el framework de importación (plantilla para `hr.vacation.rest`) |
| 21 | `hr_voucher` | **F** | Boleta de pago PE → `al_hr_pe_reports`; formato legal se conserva (migrar reportlab→QWeb); envío/confirmación sobre mecanismo nativo |
| 22 | `hr_utilities` | **M** | Utilidades D.L. 892 (50/50 días/remuneración) → `al_hr_pe_benefits` |
| 23 | `hr_fortnightly` | **M** | Adelanto quincenal (estructura/reglas `*_AQ`) → `al_hr_pe_benefits` |
| 24 | `hr_automate_multipayment` | **F** | TXT bancarios propietarios (BCP/BBVA/IBK/Scotia/BanBif) → `al_hr_pe_reports`; **no** sustituible por ISO 20022 (bancos PE no lo aceptan para haberes) |
| 25 | `hr_payslip_run_move_analytic` | **F** | → `al_hr_pe_account` (flag analítica, no módulo aparte) |
| 26 | `hr_social_benefits_move` | **F** | → `al_hr_pe_account` |
| 27 | `hr_social_benefits_move_analytic` | **F** | → `al_hr_pe_account` (wizards byte-idénticos al #26) |
| + | `al_hr_payroll_import` | **M** | El mejor módulo del set (mixin openpyxl, lotes en hilo, progreso OWL) → `al_hr_pe_import`, framework único |

---

## 3. Arquitectura propuesta: 5 módulos

```
al_hr_pe                    «Núcleo localización»
├── depende: hr_payroll(EE), hr_payroll_account, l10n_latam_base, hr_work_entry
├── Tablas maestras: hr.membership (AFP), hr.social.insurance, hr.contributions,
│   TABLA 08/15/17/21 SUNAT, hr.type.document (códigos SUNAT/AFP/bancos),
│   hr.period (+generador), account.fiscal.year.uit, hr.main.parameter
├── hr.version (ex hr.contract): régimen laboral, AFP/CUSPP, situación,
│   tipo comisión, EPS, régimen de prueba, suspensiones
├── hr.employee: names/apellidos PLAME, tipo doc, ctas banco haberes/CTS
├── hr.payslip: snapshot de versión, worker/net/employer totals,
│   refresh_from_work_entries ÚNICO (estrategia por work_entry_source)
├── Reglas salariales PE (65) + estructura BASE + categorías + inputs
├── Exportadores PLAME (.rem/.jor/.snl/.toc) y AFPNet → ir.attachment
└── Helpers: custom_round (HALF_UP SUNAT), número a letras, export XLSX

al_hr_pe_benefits           «Beneficios sociales y cálculos»
├── depende: al_hr_pe
├── CTS, gratificaciones (motor compute_benefits por servicios)
├── Liquidación de cese (truncos + vacaciones + conceptos extra)
├── Renta 5ta categoría (+ certificado) · Provisiones mensuales
├── Subsidios EsSalud · Utilidades D.L. 892 · Récord vacacional D.L. 713
├── Liquidación vacacional · Adelantos y préstamos · Quincena (*_AQ)
└── (la contabilización vive en al_hr_pe_account)

al_hr_pe_account            «Contabilización unificada» (4 módulos → 1)
├── depende: al_hr_pe_benefits
├── Asiento de planilla por lote — nativo hr_payroll_account como base,
│   wrapper de agrupación por lote + bloque AFP por hr.membership
├── Asiento de CTS/grati/liquidación/provisiones
└── Distribución analítica: analytic_distribution JSON nativo con flag
    por compañía (hr.main.parameter.detail_analytic) — NO módulos paralelos

al_hr_pe_attendance         «Asistencia y turnos» (capa fina)
├── depende: al_hr_pe, planning(EE), hr_payroll_attendance, hr_payroll_planning
├── Tipos de turno PE + régimen atípico minero sobre planning.slot nativo
├── Monitor de asistencia (turno vs marcación, TZ-aware) + fotocheck
└── Tareaje: clasificación nocturna/HE 25-35-100/DOM/FER como reglas

al_hr_pe_reports            «Documentos e interfaces»
├── depende: al_hr_pe_benefits
├── Boleta de pago (QWeb, formato legal PE) + envío/confirmación
├── Certificado de trabajo · carta CTS · certificado 5ta
├── Contratos desde plantilla (hr.version)
└── TXT bancarios de pago masivo (haberes/CTS/quincena por banco)

al_hr_pe_import  (opcional, 6º si se prefiere separar)
└── Framework de importación (mixin openpyxl + progreso OWL) con plantillas
    para: novedades, asistencias, reglas, saldos vacacionales, adelantos.
    Alternativa: incluirlo dentro de al_hr_pe.
```

**Por qué 5 y no 1**: un módulo único obligaría a instalar contabilidad,
planning EE y reportería en despliegues que solo necesitan nómina básica; la
partición sigue las líneas de dependencia externa (account / planning /
nada). Por qué no más: toda partición adicional en v18 (los `_move_analytic`,
el certificado de 5ta, el importador de vacaciones) demostró ser duplicación
o fragmentación sin frontera real.

---

## 4. Lógica peruana a preservar (inventario del refactor)

Estos métodos son el activo a migrar; el resto es andamiaje sustituible.

| Dominio | Fuente v18 | Regla de negocio |
|---|---|---|
| Remuneración computable | `hr_main_parameter.compute_benefits` | sueldo + asig. familiar (10 % RMV) + prom. variables (regla 3-de-6 meses ÷6) + 1/6 grati (solo CTS) |
| CTS | ídem | computable/12 (÷24 pequeña empresa); meses de 30 días; faltas; interés; semestres May-Oct/Nov-Abr |
| Gratificación | ídem | computable/6 (÷12); bono EsSalud 9 %/EPS 6.75 % |
| Liquidación | `hr_liquidation` | truncos CTS+grati+vacaciones, AFP/ONP sobre vac. truncas, conceptos extra |
| Renta 5ta | `hr_fifth_category_line.compute_fifth_line` | proyección anual + gratis proyectadas − 7 UIT → tramos 8/14/17/20/30 % (5/20/35/45 UIT) → ÷ equivalencia mensual [12..1]; reproyección por delta |
| Provisiones | `hr_provisions` | devengo mensual /12, /6, /12 con prorrateo por ingreso |
| Subsidios | `hr_subsidies` | base = prom. 12 meses; enfermedad: 20 primeros días cargo empleador (acumulado anual DMED); maternidad completa |
| Utilidades | `hr_utilities.calculate` | 50 % por días laborados + 50 % por remuneraciones (D.S. 009-98-TR), ajuste de redondeo en última línea |
| Vacaciones | `hr_vacation_rest` | devengo 2.5 días/mes, saldos arrastrados, truncas |
| Préstamos | `hr_loan.get_fees` | cuotas iguales fin de mes, exclusión de tipos BBSS del descuento mensual |
| Quincena | `hr_fortnightly` | estructura `*_AQ`, neto quincenal volcado al mensual |
| Tareaje | `hr_tareaje_manager` | nocturnidad 06:00–22:00 (parametrizar), HE 25/35/100, DOM/FER |
| Redondeo | `report_tools.custom_round` | ROUND_HALF_UP (criterio SUNAT; no usar float_round banker's) |
| Prorrateo | `hr_base.get_months_of_30_days` | mes comercial de 30 días |

**Datos maestros a portar**: 65 reglas salariales + 7 categorías + estructura
BASE + tipos MENSUAL/QUINCENAL/SEMANAL + inputs + work entry types; tablas
SUNAT (20 tipos doc, 82 tipos trabajador, 56 suspensiones, 42 motivos baja,
8 situaciones); AFP con tasas vigentes.

---

## 5. Multicompañía por diseño

Estado v18: mayormente saneado (`company_id` store+index en líneas, `ir.rule`
global-or-own en maestros). El plan lo lleva a diseño, no a parche:

1. `_check_company_auto = True` en **todo** modelo transaccional; `ir.rule`
   por compañía desde el día 1 (no como fase posterior).
2. **Cero códigos hardcodeados**: los SQL v18 filtran por códigos de regla
   (`COMFI`, `A_JUB`, `GRA_TRU`, estructura `'BASE'`…) — si una compañía
   renombra una regla, el asiento cuadra mal en silencio. En v19 toda
   referencia a regla/estructura/cuenta pasa por `hr.main.parameter`
   (uno por compañía) o por M2O en la propia regla.
3. Cuentas contables de reglas: `company_dependent=True` (v18 lo rompía a
   propósito para poder leerlas desde una vista SQL — la vista desaparece
   con el asiento nativo, ver §6.2).
4. Maestros globales con override por compañía (patrón v18 correcto:
   `company_id` opcional + regla global-or-own) se mantiene.
5. Parametrizar todo lo nacional-variable por compañía/año: RMV, asignación
   familiar (10 % RMV, no `102.5` literal), UIT por año fiscal, TZ del
   monitor de asistencia (del calendario del recurso, no `'5 hr'` literal).
6. Tests multicompañía obligatorios por fase (dos compañías con parámetros
   distintos calculando el mismo periodo).

---

## 6. Decisiones técnicas clave

### 6.1 `hr.contract` → `hr.version`
Todos los campos/overrides de contrato migran a `hr.version`. Los snapshots
del payslip (patrón v18 correcto: foto al calcular, no related) pasan a
snapshot de la versión vigente en el periodo. El histórico de cambios de
sueldo que v18 modelaba aparte (`hr.salary.history`) lo da `hr.version`
nativo gratis.

### 6.2 Asientos: nativo primero
`hr_payroll_account` v19 genera asiento por nómina con `analytic_distribution`
JSON nativo. Estrategia:
- **Asiento mensual**: usar el nativo + wrapper de agrupación por lote y el
  bloque AFP por `hr.membership`. Se elimina la vista SQL global
  `payslip_run_move` y sus 4 variantes.
- **Asientos de BBSS** (truncos, provisiones, CTS/grati): código propio (el
  nativo no los modela) pero construidos con el ORM (`account.move.create`),
  no SQL, con `analytic_distribution` JSON según flag por compañía.
- `hr.analytic.distribution` propio → **eliminado**: la distribución
  analítica nativa (en `hr.version`/regla) lo reemplaza (cierra la migración
  diferida F2-3 del refactor v18).

### 6.3 Work entries: derivar, no clonar
Los overrides v18 de `_generate_work_entries`/`_get_worked_day_lines` eran
copias parcheadas del core v18 (drift garantizado). En v19: extender los
hooks del core (`hr_payroll_attendance`, `hr_payroll_holidays`,
`hr_payroll_planning`) y encapsular lo PE (categorías DLAB/DNLAB/DSUB/DEXT/
DVAC, redondeo de días) en métodos propios llamados desde esos hooks. Un
único `refresh_from_work_entries` con estrategia por `work_entry_source`.

### 6.4 Identificación: latam nativo
`hr.type.document` → extender `l10n_latam.identification.type` con
`sunat_code`/`afp_code`/códigos de banco (cierra la migración diferida F2-2).
Script de mapeo de datos incluido en la fase 1.

### 6.5 Ficheros: attachments, no filesystem
Todos los exportadores (PLAME, AFPNet, TXT bancarios, XLSX) devuelven
`ir.attachment` + descarga; desaparece `dir_create_file` (roto en
multi-worker y despliegues cloud).

### 6.6 Prohibiciones (lecciones del análisis)
- Auto-`pip install` en runtime (aún vivo en 3 wizards v18 pese a lo que
  dice su doc) — dependencias en `external_dependencies` del manifest.
- `xlrd` → `openpyxl` en todo.
- Redeclarar campos nativos sin `compute`/`related` (los 19 bugs que el
  refactor v18 ya pagó) — auditoría campo-por-campo contra core v19.
- SQL con `.format()` → ORM o parámetros; TZ/horarios/importes hardcodeados
  → parámetros por compañía.

---

## 7. Hallazgos que condicionan el plan

### 7.1 La documentación v18 miente
`REFACTOR_PROGRESS.md` da por eliminado el auto-pip/xlrd; sigue vivo en
`hr_importers/wizard/*.py:13-22` y `hr_automate_multipayment/wizard/
hr_import_wizard.py:13-22`. **Todo veredicto de este plan sale del código,
no de los .md** — y la migración debe re-verificar, no confiar.

### 7.2 Duplicación medida (justifica la fusión contable)
`hr_social_benefits_move` vs `_analytic`: wizards **byte-idénticos**
(`diff -q` limpio), modelos con ~90 % de código común — difieren solo en el
origen de la cuenta en 4 fragmentos SQL. Ídem `hr_payslip_run_move` vs
`_analytic` (que además contiene una 3ª y 4ª variante del mismo SQL).

### 7.3 Bugs a NO portar
- `hr_vacations.get_vacation_employee`: `unlink()` **sin filtro de
  compañía** — borra saldos vacacionales de todas las compañías.
- Asignación familiar `102.5` hardcodeada; RMV default 1025 (2 años
  desactualizado).
- `_compute_*_count` sin `@api.depends` (16 casos); 17 `bare except`.
- `&nbsp;` inválido en `template_contract.xml` (parser XML).

---

## 8. Plan por fases

Cada fase termina instalada en `ol_pe_v19` con tests verdes (patrón de los
módulos AL ya migrados; convención de versión `N.AAAAMMDD`).

| Fase | Entregable | Contenido | Riesgo |
|---|---|---|---|
| **0** ✅ | Esqueleto + decisiones | Estructura de los 5 módulos, manifest, este plan versionado; PoC de `hr.version` con 3 campos PE y un payslip calculando. *Hecho 2026-07-22: 5 módulos instalados en `ol_pe_v19`, PoC validado (versionado conserva histórico; regla con `version.l10n_pe_labor_regime` calcula /24 pequeña empresa), tests 2/2.* | Bajo |
| **1** ✅ | `al_hr_pe` núcleo | Tablas maestras + datos; `hr.version` completo; empleado PLAME; periodos; `hr.main.parameter`; extensión latam identification (6.4). *Hecho 2026-07-22: 8 modelos + 9 archivos de datos (T08×41, T15×4, T17×21, T21×28, 7 AFP con tasas, UIT 2024-26, extensión latam con códigos SUNAT/AFP), menú Nómina → Configuración → Perú, reglas multicompañía global-or-own, helpers de mes comercial y número a letras portados con tests de paridad; AFP rediseñadas como globales con cuenta `company_dependent` (adiós wizard de duplicación v18); tests 11/11. Nota v19: `_sql_constraints` ya no existe — usar `models.Constraint` (corregido también en `edi.invoice.series`).* | Medio |
| **2** ✅ | Motor de nómina | Reglas salariales (65) + estructura; snapshot payslip; `refresh_from_work_entries` único; exportadores PLAME/AFPNet como attachments. *Hecho 2026-07-23 (`al_hr_pe` 3.20260722, tests 15/15): 64 reglas + estructura BASE + 7 categorías + 15 work entry types + 25 input types portados con fórmulas traducidas contract→version; snapshot PE en la boleta (RMV/asig.familiar/tasas AFP por tipo de comisión) + totales PLAME por categoría; periodo en boleta y lote; 5 exportadores PLAME/AFPNet como ir.attachment (ORM, sin SQL format ni disco) con botones en el lote; hr.work.suspension (T21). Decisiones clave: DLAB como tipo PE propio + remapeo de la asistencia nativa en la boleta (no pisar el tipo nativo — noupdate no aplica overrides en -u); línea DOM calculada como complemento a días calendario (mes comercial: DLAB+DOM+ausencias = días del mes); inputs tolerantes (ausente=0, semántica v18) vía _get_localdict; zero-lines para todos los códigos PE. Paridad verificada: BAS mes completo = sueldo, fondo/comisión/prima AFP según tasas de datos, EsSalud 9 %, NETO = ING − aportes − descuentos. Pendiente de fases siguientes: get_dlabs en payslip, detección ONP por is_afp en .rem, leave_id en suspensiones (F3).* | **Alto** (corazón) |
| **3** ✅ | `al_hr_pe_benefits` (1/2) | CTS + gratificaciones + récord vacacional + liquidación vacacional (motor por servicios). *Hecho 2026-07-23 (2.20260722, tests 4/4): hr.cts/hr.gratification con detalle y preserve_record, motor compute_benefits en hr.main.parameter (paridad v18: 1/6 grati solo CTS, divisores por régimen, bono EsSalud por % del seguro, promedios regla 3-de-6, tope 60 días descanso médico), récord vacacional D.L. 713 (devengo 2.5/mes, bug multicompañía del unlink global CORREGIDO y testeado) y liquidación vacacional con AFP/ONP. Selección de empleados vía lote mensual con periodo (los payslips deben ir en lotes con periodo_id). Sin SQL format; estructura por env.ref; unique(company,year,type) que v18 no tenía. v19: search views ya no aceptan group expand/string. Paridad verificada: CTS semestre = computable/2, grati completa = computable + bono 9 %, 30 días/año vacacional. Excel/PDF/correo → Fase 7; hr.leave→suspensiones → integración F3-bis con hr_payroll_holidays.* | Alto |
| **4** ✅ | `al_hr_pe_benefits` (2/2) | Renta 5ta (+certificado), liquidación de cese, provisiones, subsidios, utilidades, adelantos/préstamos, quincena. *Hecho 2026-07-24 (3.20260722, tests 13/13 del módulo): renta de 5ta (hr.fifth.category con paridad v18 exacta — proyección `rem×(12−mes)+mes`, gratis proyectadas por % del seguro o reales, −7 UIT, tabla escalonada por tramos generables 8/14/17/20/30 % en 5/20/35/45/∞ UIT desde `l10n_pe.hr.uit`, ventanas Art. 40, reproyección con lote anterior y saldo, excluidos + wizard); liquidación de cese (hr.liquidation: truncos CTS/grati vía `compute_benefits(liquidation=...)`, vacaciones devengadas/truncas con AFP/ONP del snapshot, conceptos extra, export a inputs truncos); provisiones mensuales (hr.provisiones: CTS /12 con 1/6 grati, grati /6 + bono por tasa, vacaciones /12, ÷2 pequeña, micro solo vacaciones, prorrateo mes de ingreso, acumulados por ventana con `_read_group`); subsidios EsSalud (base 12 meses, 20 días del empleador vía DMED, maternidad completa, lote desde suspensiones T21/22); utilidades D.L. 892 (50 % días / 50 % remuneraciones, ajuste de redondeo en última línea); adelantos/préstamos (cronograma cuotas iguales fin de mes con deuda decreciente, tipos especiales BBSS excluidos de la importación mensual); quincena (hr.fortnightly genera boletas BASE y descuenta en la mensual — TODO estructura *_AQ). Hallazgos v19: el form nativo de hr.payslip.run es un diálogo sin `<header>` → los botones de lote (PLAME de F2 incluidos, que nunca cargaron) van en el menú del kanban (`//t[@t-name='menu']`); `identification_id` vive en hr.version → la unicidad de documento del empleado pasó a constraint Python; `first_contract_date` no existe → `get_first_version()`. Paridad testeada: tramos UIT, tabla escalonada (8 % + 14 % exceso), cronograma de préstamo, provisión mensual (básico/12 y /6), utilidades un-trabajador = 100 % del reparto. Certificado 5ta/actas/Excel → Fase 7; asientos de provisión → Fase 5; reglas *_AQ quincena y subsidios desde hr.leave → pendientes marcados TODO(fase4-revisar).* | Alto |
| **5** ✅ | `al_hr_pe_account` | Asiento nativo con wrapper de lote; asientos BBSS por ORM; flag analítica por compañía. *Hecho 2026-07-24 (2.20260722, tests 3/3; suite completa 3 módulos en verde): asiento único del lote por ORM en 3 bloques (cargo por `account_debit` de la regla; abono por `account_credit` con detalle por trabajador vía `employee_move_line` nativo — sustituye a `is_detail_cta`; abono AFP a la cuenta de la afiliación `hr.membership.account_id` company_dependent, reglas configurables en `afp_rule_ids` en vez de códigos fijos COMFI/COMMIX/SEGI/A_JUB) con wizard de previsualización, ajuste por redondeo y enlace al `move_id` nativo del lote y sus boletas — la vista SQL `payslip_run_move` y sus 4 variantes desaparecen; asientos de BBSS unificados con mixin `hr.benefits.move.mixin` + wizard único (los 4 wizards v18 eran byte-idénticos): CTS (reversión de provisión + gasto diferencia + CTS por pagar), gratificación, liquidación de cese (`hr.liquidation.move`, 1 asiento por cesado con 5 bloques incl. retención AFP/ONP) y provisiones (4 parejas gasto/pasivo, haber detallado o agrupado según `detallar_provision`); 15 cuentas/config company_dependent en `hr.main.parameter` + flag `detail_analytic` con `analytic_distribution` JSON nativo (regla > `hr.version`) — `hr.analytic.distribution` v18 eliminado; diff real `_move` vs `_move_analytic` documentado: solo cambiaba el ORIGEN de las cuentas, unificado como comportamiento condicional. Gotchas v19: `account.account.deprecated` ya no existe; el menú raíz de nómina es `hr_work_entry_enterprise.menu_hr_payroll_root` (no `hr_payroll.…`). Excel «asiento planilla» (971 líneas, solo reporte) → Fase 7. Tests: lote cuadrado con bloque AFP (neto+aportes=básico), CTS por wizard completo, provisión /12 y /6.* | Medio |
| **6** ✅ | `al_hr_pe_attendance` | Capa PE sobre planning EE; monitor TZ-aware; tareaje/clasificación HE. *Hecho 2026-07-24 (2.20260722, tests 41; suite 4 módulos 60/60 en verde): el clon de ~2 700 líneas de planning v18 NO se porta — capa fina sobre planning/hr_payroll_planning EE nativos: `l10n_pe_shift_kind` en el rol, `l10n_pe_is_night` en la plantilla (22:00-06:00), ciclos atípicos N×M (`l10n_pe.hr.shift.cycle` global-or-own con validador legal: promedio semanal ≤ 48 h y tope 12 h/día — STC 4635-2004-AA/TC) y asignaciones que materializan `planning.slot` TZ-aware vía `employee._get_tz()` (corrige el `+5 h` hardcodeado v18); marcación emparejada al slot publicado más cercano (±14 h); monitor `l10n_pe.hr.attendance.monitor` como vista SQL TZ-aware (`AT TIME ZONE` del recurso, LATERAL a la versión vigente) con claves de estado v18; fotocheck con UNIQUE por compañía y carné QWeb propio; tareaje `hr.tareaje.manager` con cálculo en métodos puros testeables (`_split_night_hours` cruza medianoche, `_split_overtime_hours` 25 %→2 h/35 %, `_classify_day` descanso/feriado 100 %; D.S. 007-2002-TR arts. 8/10, D.Leg. 713), parámetros por compañía (ventana nocturna, umbral, tolerancia, redondeo, work entry types por M2O con default por código) y volcado a boleta vía `_get_worked_day_lines` con super() (respeta remapeo DLAB y zero-lines de F2); `l10n_pe_is_overtime` en hr.version. No portados (veredictos): gantt/kiosco/plantillas propias (nativo), `make_replace_vig` (lo cubre hr.version; queda rastro de reemplazo en el slot), reporte mensual Excel → F7. Dependencias nuevas instaladas: planning, hr_payroll_planning, hr_attendance, hr_payroll_attendance, hr_holidays (necesaria explícita: hr.leave.type no llega por la cadena). TODO(fase6-revisar): work entry type nocturno DLABN + regla 35 % RMV, rama monitor para work_entry_source='calendar', calendarios week_type.* | Medio |
| **7** ✅ | `al_hr_pe_reports` | Boleta QWeb + envío; certificados/cartas; contratos; TXT bancarios. *Hecho 2026-07-24 (2.20260722, tests 18; suite 5 módulos 78/78 en verde): boleta de pago QWeb legal (D.S. 001-98-TR: 3 columnas Ingresos/Descuentos/Aportes con código SUNAT por concepto, días/horas desde los W.D. clasificados de `hr.main.parameter` con fallback a xml ids de al_hr_pe, suspensiones T21, neto en letras vía `number_to_letter`, rem. básica desde `version_id.wage`) — los 3 formatos reportlab v18 colapsan en un QWeb único y `type_boleta` desaparece; envío por correo con `mail.template` + PDF por `report_template_ids` encolado (`force_send=False`) y confirmación de recepción por token HMAC-SHA256 (`odoo.tools.hmac` con `database.secret`, `consteq`) — sustituye el enlace por id pelado enumerable de v18; certificado de trabajo + carta CTS (mixin `l10n_pe.hr.doc.mixin`) y certificado de 5ta (desviación del veredicto #17: vive en reports, no en benefits; reutiliza los helpers ORM de `hr.fifth.category.line`); contratos por plantilla `l10n_pe.hr.contract.template` global-or-own sobre `hr.version` — Jinja2 ELIMINADO (SSTI) por sustitución regex `{{...}}` con escape, `&nbsp;` normalizado, `hr_contract_history` no se porta (versionado nativo), régimen de prueba LPCL Art. 10 con `trial_date_end` compute; TXT bancarios `hr.automate.multipayment` con funciones puras de formato testeables sin BD (haberes+CTS × BCP/BBVA/Interbank/Scotiabank/BanBif, paridad byte a byte incluidas rarezas v18: TABs literales BBVA/Interbank CTS, pad derecho USD Interbank, checksum BCP CTS bimoneda), líneas propias (los orígenes ya no se contaminan), orígenes lote/quincena/CTS (`cts_bank_account_id`)/grati/vacaciones, attachments en vez de disco. No portados: import xlrd → F8, TXT utilidades → TODO(fase7-revisar), Scotiabank variante 1 (código muerto), cifrado PDF con DNI (reportlab `encrypt=`; evaluar pypdf si se exige). v19: cuenta de haberes = `primary_bank_account_id`; `group_ids` (no `groups_id`) en act_window; wizards por menú Acción de empleados.* | Bajo |
| **8** ✅ | Importación + cierre | Framework `al_hr_pe_import`; plantillas por dominio; pruebas multicompañía extremo a extremo (2 compañías, 1 periodo completo: nómina → BBSS → asientos → boletas). *Hecho 2026-07-25 (1.20260722, tests 14; suite 6 módulos 92/92 en verde): 6º módulo de CIERRE (`depends` de los cinco `al_hr_pe_*` — sus plantillas cruzan dominios y es el hogar del e2e). Port de `al_hr_payroll_import` v18 (el único módulo moderno del set): mixin `al.import.payroll.mixin` con openpyxl exclusivo (sin xlrd ni auto-pip), detección de hojas (`al.import.payroll.sheet` + autoselección por keyword), fila inicial configurable, lotes con commit por lote (guard `modules.module.current_test`: en tests el commit está PROHIBIDO y el aislamiento lo da la transacción del test), savepoint por fila con contadores creado/actualizado/omitido/error, sugerencias de corrección por wizard, reporte xlsx de 3 hojas (Resultado/Errores/Omitidos) y plantilla Excel descargable generada con openpyxl (sustituye los generadores xlsxwriter-a-directorio de `hr_importers`/`hr_vacation_import`, veredictos #15/#20 = D); progreso en vivo `al.import.payroll.progress` persistente (multicompañía con ir.rule estricta) actualizado desde el hilo con cursor dedicado + widget OWL con polling RPC (`get_progress_data`); importadores: asistencias (TZ del archivo → UTC, clave empleado+check_in), reglas salariales (clave code+struct, `amount_select='code'`), inputs de boletas por lote (vía `_set_pe_input_amount` — v18 importaba definiciones, lo operativo son importes mensuales), récord vacacional (saldo inicial `internal_motive='rest'` que se REEMPLAZA, motivo por signo, paridad v18), adelantos y datos PE de `hr.version`; `_clean_code` normaliza DNIs numéricos de openpyxl (46271883.0 → '46271883'). E2E multicompañía (5 tests): 2 compañías PEN × 6 lotes mensuales (semestre CTS Nov-2025→Abr-2026, 18 boletas confirmadas), retención judicial RET_JUD en una boleta para ejercitar DES_NET de punta a punta (boleta legal + cuenta propia en el asiento), CTS por `compute_benefits` = sueldo/2, asiento de lote cuadrado con bloque AFP, `_get_voucher_report_data` + render QWeb HTML, y aislamiento cruzado (`with_user` restringido → `AccessError`, cuentas company_dependent distintas por compañía). Gotcha nuevo: `cr.commit()` dentro de tests lanza AssertionError en v19 → patrón `auto_commit = not modules.module.current_test` (igual que crm/event core).* | Medio |

**Orden de razones**: el riesgo se concentra en fases 2-4 (paridad de
cálculo). Estrategia de validación: para cada dominio, calcular un periodo
real en v18 y reproducir los mismos números en v19 (fixture comparativo por
empleado-regla) antes de dar la fase por cerrada.

**Fuera de alcance de la primera entrega** (decidir después): kiosko de
marcación, `hr.attendance.monitor` en tiempo real, API SBS de tasas AFP
(wizard de consulta se porta, el cron no).

---

## 9. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Paridad de cálculo v18↔v19 | Planillas mal pagadas | Fixtures comparativos por dominio (§8); `custom_round` idéntico |
| `hr.version` difiere de `hr.contract` en semántica de vigencia | Snapshots erróneos | PoC en fase 0; snapshot por fecha de periodo |
| Motor work entries v19 cambió internamente | Tareaje/ausencias mal contadas | Extender hooks, no copiar; tests con calendarios PE |
| Reglas EE de planning no cubren régimen atípico minero | Gap funcional | Capa propia sobre planning.slot (validador de ciclos N×M) |
| Datos legacy (BBSS históricos, saldos, préstamos vivos) | Corte de continuidad | Scripts de migración de datos por fase + importadores del framework |
```

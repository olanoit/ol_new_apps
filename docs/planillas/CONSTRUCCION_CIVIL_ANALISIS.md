# Planilla de construcción civil — análisis y plan de desarrollo

Análisis previo al desarrollo de `al_hr_pe_construction`. Fecha: 2026-08-03.

Fuentes verificadas:

* **Tabla salarial vigente**: R.M. N.° 197-2025-TR, del 01/01/2026 al
  31/12/2026, publicada por la FTCCP
  (`tablas-salariales-2026-construccion-civil.pdf`). Los importes de este
  documento salen de ahí, no de memoria.
* Convención colectiva CAPECO–FTCCP 2026, suscrita el 05/12/2025.
* D.Leg. 727, D.S. 011-79-TR y sus modificatorias; Ley 30334
  (exoneración de gratificaciones); D.L. 21067 (CONAFOVICER).

> **Ojo con la vigencia.** Históricamente el convenio corría de junio a
> mayo. El de 2026 va de **enero a diciembre**. La tabla salarial no
> puede ser un dato fijo en el código: tiene que ser un registro con
> fecha de vigencia.

---

## 1. Por qué no encaja en lo que ya existe

`al_hr_pe` calcula un régimen **mensual sobre sueldo**. Construcción civil
es otro animal:

| | Régimen general (lo que hay) | Construcción civil |
|---|---|---|
| Base de cálculo | Sueldo mensual (`version.wage`) | **Jornal diario** de una tabla por categoría |
| Periodicidad | Mensual (o quincena como adelanto) | **Semanal** |
| Quién fija la remuneración | El contrato | La **convención colectiva**, igual para todos los de la misma categoría |
| CTS | Depósito semestral (mayo/noviembre) | **15 % pagado con cada planilla** |
| Vacaciones | 30 días de descanso, récord vacacional | **10 % del básico**, pagado con la planilla |
| Gratificaciones | Sueldo completo, julio y diciembre | **40 jornales**, devengados por semanas |
| Horas extras | 25 % / 35 % | **60 % / 100 %** |
| Asignación familiar | 10 % de la RMV | **Asignación escolar**: 30 jornales/año por hijo |
| Aporte propio | — | **CONAFOVICER 2 %**, al Banco de la Nación |
| Riesgo | Opcional | **SCTR obligatorio** (actividad del Anexo 5) |

El vínculo además es **por obra**: el trabajador se contrata para una obra
determinada y su categoría puede cambiar de una obra a otra.

Conclusión: módulo aparte con estructura salarial propia, no parches sobre
la estructura BASE.

---

## 2. Los números de 2026 (R.M. 197-2025-TR)

### 2.1 Jornal y conceptos diarios

| Concepto | Operario | Oficial | Peón | Cómo se calcula |
|---|---:|---:|---:|---|
| Jornal básico | 89.30 | 69.75 | 62.80 | Tabla del convenio |
| D.S.O. (dominical) | 14.88 | 11.63 | 10.47 | Jornal ÷ 6 |
| BUC | 28.58 | 20.93 | 18.84 | **32 %** operario · **30 %** oficial y peón |
| Bonif. movilidad | 8.60 | 8.60 | 8.60 | Importe fijo, 6 pasajes urbanos |
| Indemnización (CTS) | 13.40 | 10.46 | 9.42 | **15 %** del jornal |
| Vacaciones | 8.93 | 6.98 | 6.28 | **10 %** del jornal |

La movilidad es **la misma para las tres categorías**: es un importe, no un
porcentaje.

### 2.2 Gratificaciones

Cada una equivale a **40 jornales básicos**: 3 572.00 / 2 790.00 / 2 512.00.

Lo que no es obvio: **se devengan en ventanas distintas**.

* Fiestas Patrias: enero–julio → 7 meses → diario = 40 × jornal ÷ 210.
* Navidad: agosto–diciembre → 5 meses → diario = 40 × jornal ÷ 150.

Por eso en la tabla el diario de Navidad (23.81) es mayor que el de
Fiestas Patrias (17.01) con el mismo jornal.

La **Ley 30334** exonera la gratificación de ONP/AFP, y el 9 % que el
empleador habría pagado a EsSalud se entrega al trabajador como
bonificación extraordinaria (2.14 diario en operario).

### 2.3 Horas extras y asignación escolar

| Categoría | Valor hora | 60 % | 100 % | Indem. 15 % | Asig. escolar diaria | mensual |
|---|---:|---:|---:|---:|---:|---:|
| Operario | 11.16 | 17.86 | 22.33 | 1.67 | 7.44 | 223.25 |
| Oficial | 8.72 | 13.95 | 17.44 | 1.31 | 5.81 | 174.38 |
| Peón | 7.85 | 12.56 | 15.70 | 1.18 | 5.23 | 157.00 |

Valor hora = jornal ÷ 8. Sobretasa **60 % las dos primeras horas** y
**100 % a partir de la tercera** — no 25/35 como el régimen general.

Asignación escolar = **30 jornales al año por hijo** (223.25 = 89.30 × 30 ÷ 12).

### 2.4 Bonificación por Alta Especialización (BAE)

Solo para operarios, según la especialidad:

| Especialidad | BAE | Diario (operario) |
|---|---:|---:|
| Operador de equipo mediano | 8 % | 7.14 |
| Topógrafo | 9 % | 8.04 |
| Operador de equipo pesado | 10 % | 8.93 |
| Electromecánico | 22 % | 19.65 |

### 2.5 Bonificaciones por condiciones de trabajo

Estas no salen en la tabla semanal porque dependen de la obra:

| Bonificación | Valor | Cuándo |
|---|---|---|
| Altitud | S/ 2.50 por día | Obra a más de 3 000 m s. n. m. |
| Contacto con agua | 20 % del jornal | Trabajo en agua o aguas servidas |
| Riesgo bajo cota cero | S/ 1.90 por día | Bajo el 2.º sótano o 5 m bajo el nivel del suelo |
| Altura (por piso) | ~8 % del jornal | A partir del 4.º piso, escalonada |

> **Estos cuatro importes vienen de fuentes secundarias**, no del PDF de
> la FTCCP. Por eso van a un **catálogo editable con vigencia**, no
> incrustados en las reglas: el usuario los corrige contra su convenio
> sin tocar código. Es el mismo criterio que se aplicó a los catálogos
> del Anexo 2 del T-Registro.

### 2.6 Descuentos y aportes

| Concepto | Tasa | Base | Quién |
|---|---|---|---|
| ONP | 13 % | Remuneración computable | Trabajador |
| AFP | según entidad | Remuneración computable | Trabajador |
| **CONAFOVICER** | **2 %** | **Jornal básico + D.S.O.** | Trabajador |
| EsSalud | 9 % | Remuneración computable | Empleador |
| SCTR salud y pensión | según entidad | Remuneración | Empleador |
| SENCICO | 0.2 % | Facturación de la obra | Empleador — **no es planilla**, no entra aquí |

CONAFOVICER se retiene y se paga al **Banco de la Nación hasta el día 15
del mes siguiente**: necesita su propio reporte mensual, no basta con la
línea en la boleta.

> **La base incluye el dominical.** Las fuentes secundarias dicen «2 % del
> jornal básico»; la tabla del convenio lo desmiente. El operario retiene
> 12.50 a la semana y el 2 % de 535.80 son 10.72; con el D.S.O. dentro,
> 625.10 × 2 % = 12.50. Verificado también en oficial y peón.

### La base afecta, confirmada por los descuentos de la tabla

La duda de si el BUC aporta se resuelve con la propia tabla: el operario
descuenta **103.55** de ONP, que es el **13 % de 796.56** = jornal +
D.S.O. + BUC. Cuadra igual en oficial (79.79 sobre 613.80) y peón (71.84
sobre 552.64).

Es decir: **el BUC sí está afecto** y **la bonificación por movilidad no**
—queda fuera de esos 796.56 porque es condición de trabajo—. Es
exactamente lo que calcula la regla `TREM`.

### 2.7 El redondeo: dónde se pierden los céntimos

Dos trampas que solo se ven contrastando con la tabla oficial, y que
condicionan cómo hay que escribir las reglas de la fase 2.

**1. Las sobretasas van sobre el valor hora sin redondear.** Con jornal
89.30 la hora es 11.1625. El 100 % son 22.33 en la tabla; redondeando la
hora primero (11.16 × 2) salen 22.32. Un céntimo por hora extra.

**2. El importe del periodo no es el diario multiplicado por los días.**
La tabla redondea **una sola vez, sobre el periodo**:

| Oficial, 6 días | Diario × 6 | Como lo hace el convenio |
|---|---:|---:|
| Jornal | 418.50 | 418.50 |
| D.S.O. | 69.78 | **69.75** (= 418.50 ÷ 6) |
| BUC 30 % | 125.58 | **125.55** (= 30 % de 418.50) |
| Movilidad | 51.60 | 51.60 |
| **Total** | 665.46 | **665.40** |

Seis céntimos por trabajador y semana. En el **operario los dos caminos
dan lo mismo por casualidad** —los céntimos del D.S.O. y del BUC se
compensan—, así que validar solo con esa categoría esconde el problema.
Por eso el fixture de pruebas usa las tres.

`l10n_pe.hr.construction.wage.line._period_amounts(días)` ya calcula así,
y es lo que deben usar las reglas salariales.

---

## 3. Qué se apoya en lo que ya existe

| Necesidad | Ya resuelto en | Qué falta |
|---|---|---|
| Tipo de trabajador T08 = 27 y régimen T33 = 21 | `al_hr_pe` catálogos | Nada |
| Familia de cálculo `construccion` | `hr.version.l10n_pe_labor_regime` | Que las reglas la usen |
| SCTR pensión en el T-Registro | `l10n_pe_sctr_pension` | El **aporte** SCTR en planilla |
| Boleta legal | `al_hr_pe_reports` | Que muestre jornal y días, no sueldo |
| Tareaje y horas extras | `al_hr_pe_attendance` | Sobretasas 60/100 |
| ONP/AFP, EsSalud, 5ta | `al_hr_pe` reglas | Nada |
| T-Registro | `al_hr_pe` | Nada |

Lo que **no** existe y hay que crear: tabla salarial con vigencia,
categorías, BAE, bonificaciones por condiciones, obra, periodicidad
semanal, CTS y vacaciones pagadas en planilla, gratificación por
devengo semanal, asignación escolar y CONAFOVICER.

---

## 4. Diseño propuesto

**Módulo**: `al_hr_pe_construction`, depende de `al_hr_pe_benefits`.

### 4.1 Modelos

```
l10n_pe.hr.construction.category      Operario / Oficial / Peón
  code, name, buc_percent, sequence

l10n_pe.hr.construction.wage.table    Tabla salarial de un convenio
  name, resolution, date_from, date_to, company_id, state
  └── line_ids → l10n_pe.hr.construction.wage.line
        category_id, daily_wage, mobility_amount, buc_percent

l10n_pe.hr.construction.bonus         Catálogo de bonificaciones
  code, name, computation (fixed | percent), amount,
  base (daily_wage), date_from, date_to, applies_to_category_ids

l10n_pe.hr.construction.site          Obra
  name, code, address, altitude, company_id,
  bonus_ids  (las que aplican a toda la obra)
```

En `hr.version`:

```
l10n_pe_construction_category_id      categoría del trabajador
l10n_pe_construction_site_id          obra a la que está asignado
l10n_pe_construction_bae_id           especialidad BAE (solo operarios)
l10n_pe_construction_bonus_ids        bonificaciones propias del puesto
l10n_pe_daily_wage                    jornal vigente (compute, de la tabla)
```

El jornal **no se escribe a mano**: sale de la tabla vigente a la fecha,
por categoría. Así un cambio de convenio se aplica creando la tabla nueva,
no editando a 300 trabajadores.

### 4.2 Estructura salarial

Estructura propia `CONSTRUCCION CIVIL` con estas reglas (código SUNAT de
la tabla 22 entre paréntesis):

| Código | Concepto | Cálculo |
|---|---|---|
| `JOR` | Jornal básico (0121) | jornal × días laborados |
| `DSO` | Dominical (0100) | jornal ÷ 6 × días |
| `BUC` | Bonificación unificada (0300) | % de categoría sobre el jornal |
| `MOV` | Movilidad (0904) | importe × días |
| `BAE` | Alta especialización (0300) | % de la especialidad |
| `BALTI` | Altitud | importe × días |
| `BAGUA` | Contacto con agua | 20 % del jornal × días |
| `BCOTA` | Bajo cota cero | importe × días |
| `BALTU` | Altura por piso | % del jornal × días |
| `HE60` / `HE100` | Horas extras (0105/0106) | valor hora × 1.6 / × 2 |
| `AESC` | Asignación escolar (0201) | 30 jornales ÷ 12 por hijo |
| `INDEM` | Indemnización 15 % (0916) | 15 % de (jornal + horas extras) |
| `VAC10` | Vacaciones 10 % (0400) | 10 % del básico percibido |
| `GRAT` | Gratificación proporcional (0406/0407) | 40 jornales ÷ 210 o ÷ 150 |
| `BEXT` | Bonif. extraordinaria Ley 30334 (0906) | 9 % de la gratificación |
| `CONAF` | CONAFOVICER (0703) | 2 % del jornal básico |
| ONP/AFP/EsSalud/5ta | — | Reutiliza las reglas de `al_hr_pe` |

La asignación escolar usa los derechohabientes que ya existen: hijos
menores de 18 —o hasta 21 cursando estudios superiores en este régimen—.
Conviene extender `_l10n_pe_has_family_allowance` con el límite por
régimen en vez de duplicar la lógica.

### 4.3 Periodicidad semanal

`hr.period` es mensual. Se añade un generador de **periodos semanales**
(lunes a domingo) y la estructura marca `schedule_pay = 'weekly'`. El lote
mensual sigue existiendo para la PLAME, que se declara por mes: la
planilla semanal se agrupa al cerrar el mes.

### 4.4 CONAFOVICER

Modelo `l10n_pe.hr.conafovicer` con el resumen mensual por compañía:
trabajadores, base (jornales básicos), 2 % retenido, y el archivo de pago
para el Banco de la Nación. Se genera del lote mensual y deja el asiento
de la retención.

---

## 5. Plan por fases

| Fase | Entregable | Riesgo |
|---|---|---|
| **1** | Maestros: categorías, tabla salarial con vigencia, bonificaciones, obra. Campos en `hr.version` y jornal calculado. | Bajo |
| **2** | Estructura salarial y reglas: jornal, DSO, BUC, movilidad, BAE, bonificaciones por condiciones, horas extras 60/100. | Alto — es la paridad de cálculo |
| **3** | Beneficios en planilla: indemnización 15 %, vacaciones 10 %, gratificación por devengo, bonificación Ley 30334, asignación escolar. | Alto |
| **4** | Periodicidad semanal y agrupación mensual para la PLAME. | Medio |
| **5** | CONAFOVICER: retención, reporte mensual y archivo del Banco de la Nación. | Bajo |
| **6** | Boleta por jornal (variante del QWeb) y SCTR en planilla. | Medio |

La validación de cada fase es la misma que se usó en la migración: **una
planilla semanal real reproducida contra la tabla del convenio**, empleado
por empleado y concepto por concepto. Los números de la sección 2 son el
fixture: si el motor no reproduce 848.16 / 665.40 / 604.24 de total de
salarios con 6 días —**las tres categorías**, por lo dicho en §2.7—, la
fase no está cerrada.

### Estado

**Fase 1 hecha** (2026-08-03, `al_hr_pe_construction` 1.20260803, 23
tests): categorías, tabla salarial con vigencia y control de solapamiento,
catálogo de bonificaciones, obras, campos en `hr.version` y jornal
calculado desde la tabla. Todos los importes diarios y los tres totales
semanales reproducen la tabla oficial al céntimo.

**Fase 2 hecha** (2026-08-03, versión 2.20260803, 36 tests): estructura
`CONSTRUCCIÓN CIVIL` con las reglas JOR, DSO, BUC, MOV, BAE, las cuatro de
condiciones y HE60/HE100, más el snapshot del jornal en la boleta.
Boleta semanal de 6 días verificada contra el convenio en las tres
categorías: **848.16 / 665.40 / 604.24**, y el BAE del electromecánico da
117.88, igual que la tabla de operarios especializados.

Decisiones de la fase 2:

* Las reglas **no calculan a mano**: piden los importes a
  `hr.payslip._l10n_pe_construction_*`, que aplican el redondeo del §2.7.
  Una regla que multiplicara el diario por los días volvería a perder los
  céntimos.
* El **jornal se congela en la boleta** (`l10n_pe_daily_wage`), como el
  resto de snapshots peruanos. Si se ajusta a mano, el cálculo lo sigue.
* Cada bonificación del catálogo **apunta a la regla que la paga**
  (`salary_rule_code`). Varias pueden compartir regla y se suman: añadir
  una bonificación al convenio es crear un registro, no tocar código.
* El sobretiempo tiene su propio tipo de entrada `HE60`: el del régimen
  general va a 25/35 y no se puede reutilizar.

**Fase 3 hecha** (2026-08-03, versión 3.20260803, 52 tests): indemnización
15 %, vacaciones 10 %, gratificación por devengo, bonificación de la Ley
30334 y asignación escolar. Boleta de 6 días contrastada con la **tabla
con beneficios sociales**: operario **1 163.80** y peón **826.22**,
exactos.

Decisiones de la fase 3:

* La **gratificación se devenga por 7 días cuando el jornal va por 6**
  —así lo multiplica la tabla—, y la proporción se mantiene en semanas
  incompletas. La ventana la fija el mes de fin del periodo: 210 días
  hasta julio, 150 desde agosto.
* La **indemnización incluye las horas extras a valor simple**: la tabla
  da 1.67 por hora del operario, que es el 15 % de 11.16 —la hora
  simple—, no de la hora ya recargada.
* Los porcentajes se calculan en `Decimal`. En binario, 267.90 × 0.15 da
  40.184999… y el redondeo SUNAT lo baja a 40.18 cuando el resultado
  exacto, 40.185, tiene que subir a 40.19.
* Regla `TREM` (base afecta) que **enumera lo afecto** en vez de sumar la
  categoría: los beneficios sociales y la movilidad —que es condición de
  trabajo— quedan fuera. Sumar `categories['ING']` los habría metido
  dentro sin que nadie lo notara.
* Las bonificaciones pierden su `condition`: una regla que no se evalúa
  no deja su código en el localdict y `TREM` revienta al sumarlo (patrón
  de «zero-lines» de `al_hr_pe`).

### Un céntimo que no cuadra en la fuente

La tabla del convenio publica **911.94** para el oficial, pero sus propias
columnas suman **911.95** (418.50 + 69.75 + 125.55 + 51.60 + 62.78 +
41.85 + 130.20 + 11.72). El descuadre es del documento —que suma importes
ya redondeados—, no del cálculo: cada concepto coincide uno a uno. Hay un
test que lo fija para que nadie «corrija» el motor persiguiendo el 911.94
y desajuste un concepto que sí está bien.

**Fase 4 hecha** (2026-08-03, versión 4.20260803, 66 tests): periodos
semanales colgados de su mes y agrupación mensual para la PLAME.

Decisiones de la fase 4:

* Las semanas van de **lunes a domingo pero se cortan en el fin de mes**.
  Una semana a caballo entre dos meses obligaría a prorratear sus
  importes al declarar la PLAME, que va por mes; cortándola, la suma de
  las semanas de un mes es exactamente el mes. El precio es que la
  primera y la última pueden ser más cortas —incluso de un día si el mes
  empieza en domingo—.
* La boleta cae en el **periodo más ajustado** que la contenga entera.
  Con semanas y meses conviviendo, una boleta semanal cabe en los dos y
  se queda con el más corto; una mensual no cabe en ninguna semana. Así
  el cálculo no necesita saber qué periodicidad tiene la estructura.
* `hr.payslip.run._l10n_pe_plame_slips()` toma **todas las boletas del
  mes** cuando el lote es semanal. Declarar una semana suelta dejaría
  fuera el resto del periodo que SUNAT espera en un único envío.
* El tipo de periodo y la jerarquía viven en `al_hr_pe`, no aquí:
  `hr.period` es suyo y otros regímenes podrían pagar por semana.

**Fase 5 hecha** (2026-08-03, versión 5.20260803, 80 tests): retención de
CONAFOVICER en la boleta y liquidación mensual con su detalle para el
depósito.

**La base no es la que decían las fuentes secundarias.** El análisis
recogía «2 % del jornal básico», pero la tabla lo desmiente: el operario
retiene 12.50 a la semana y el 2 % de 535.80 son 10.72. Con el **D.S.O.
dentro**, (535.80 + 89.30) × 2 % = 12.50, y cuadra igual en oficial
(9.77) y peón (8.79). Corregido en §2.6.

El resumen mensual consolida las boletas del mes y de todas sus semanas,
calcula el vencimiento —día 15 del mes siguiente— y exporta el detalle
por trabajador que acompaña al depósito. Solo entra lo confirmado, y una
vez marcado pagado queda bloqueado.

Lo que **no** se hace: el TXT de carga al Banco de la Nación. El pago se
suele hacer con formulario y el detalle en Excel; si la empresa usa un
archivo, hace falta su especificación —el mismo criterio que con las
estructuras 13/24 del T-Registro: no se inventa un formato—.

**Fase 6 hecha** (2026-08-03, versión 6.20260803, 96 tests): boleta del
régimen y aportes del empleador. Con esto el plan queda cerrado.

La boleta es una **variante `primary`** de la del régimen general: hereda
todo y solo cambia lo que en construcción no existe. Donde la general
pone «Remuneración básica» y el sueldo mensual, esta pone **jornal
básico**, y añade categoría, obra y especialidad —la obra determina qué
bonificaciones por condiciones de trabajo se pagan, así que identifica el
puesto tanto como el cargo—. El original no se toca: los dos regímenes
pueden convivir en la misma empresa. El nombre del reporte lleva `l10n_pe`
porque es lo que mira `_get_pdf_reports` para no pisar una plantilla
peruana ya elegida.

Los aportes del empleador —EsSalud y SCTR de salud y de pensión— van
sobre el `TREM`. **La base llega por parámetro desde la fórmula de la
regla**, no leyendo `line_ids`: durante `compute_sheet()` las líneas
todavía no existen y buscarlas ahí devuelve cero en silencio. El SCTR
además pide la cobertura marcada en el trabajador: es un seguro por
actividad de riesgo, y en una obra conviven expuestos y administrativos.
Las tasas son de compañía y por defecto van en cero —las negocia cada
empresa con su aseguradora—; sin tasa contratada no se inventa un aporte.

Dos huecos que solo aparecieron al mirar un PDF real y que se arreglaron
en `al_hr_pe_reports` para todos los regímenes:

* **El neto salía en cero.** El parámetro de neto apunta a *una* regla, y
  cada estructura tiene la suya. Ahora, si la regla configurada no tiene
  línea en esta boleta, se busca **por código**: identifica el mismo
  concepto sin obligar a un parámetro por estructura.
* **Las horas extras del régimen no se contaban.** La casilla de
  sobretiempo salía en 00:00 con el importe pagado a la vista, porque el
  fallback enumeraba los conceptos del régimen general (25/35/100) y las
  del 60 % son propias. Se convirtió en un punto de extensión.

De paso, el módulo pasó a depender de `al_hr_pe_reports` de forma
explícita: ya heredaba su plantilla, y sin declararlo el orden de carga
era casual —el override de la boleta se perdía—.

---

## 6. Decisiones tomadas y por qué

1. **La tabla salarial es un registro con vigencia, no una constante.**
   El convenio cambia todos los años y en 2026 hasta cambió la ventana de
   vigencia. Un importe incrustado obliga a tocar código cada enero.
2. **Las bonificaciones son un catálogo, no reglas fijas.** Cuatro de
   ellas las tengo de fuentes secundarias; el usuario debe poder
   corregirlas contra su convenio. Además cada obra activa las suyas.
3. **El jornal se calcula, no se escribe.** Evita el error de tener
   trabajadores con jornal desactualizado tras un cambio de convenio.
4. **Módulo aparte.** Meter esto en `al_hr_pe` contaminaría el régimen
   general con conceptos que solo aplican a construcción.
5. **SENCICO queda fuera.** Es 0.2 % sobre la facturación de la obra, no
   sobre la planilla: pertenece a contabilidad, no a nómina.

## 7. Lo que falta confirmar con el cliente

* Los cuatro importes de bonificaciones por condiciones (§2.5) contra su
  convenio y sus obras.
* El escalonamiento exacto de la bonificación por altura (a partir del
  4.º piso y por cada cuántos pisos sube).
* Si pagan la planilla semanal, quincenal o mensual, porque cambia el
  generador de periodos de la fase 4.
* Si tienen trabajadores con BAE fuera de las cuatro especialidades de la
  tabla.

# Planillas Perú — Construcción civil

Régimen especial de construcción civil peruano para Odoo 19: jornal
diario por convención colectiva, periodicidad semanal, beneficios
sociales pagados en cada planilla y CONAFOVICER.

> **Versión** 6.20260803 · **Depende de** `al_hr_pe_benefits`,
> `al_hr_pe_reports` · **Licencia** LGPL-3
> **Análisis completo**: `docs/planillas/CONSTRUCCION_CIVIL_ANALISIS.md`

---

## 1. Por qué existe

El régimen de construcción civil **no es el régimen general con otro
sueldo**. Cambian la unidad de pago, la periodicidad, el origen de las
cifras y hasta qué beneficios se pagan y cuándo:

| | Régimen general | Construcción civil |
|---|---|---|
| Unidad de pago | Sueldo mensual | **Jornal diario** por categoría |
| Origen del importe | Contrato individual | **Convención colectiva** CAPECO–FTCCP |
| Periodicidad | Mensual o quincenal | **Semanal** |
| CTS | Depósito semestral | **En cada planilla** (indemnización 15 %) |
| Vacaciones | Descanso de 30 días | **10 % en cada planilla** |
| Gratificación | Un sueldo | **40 jornales**, devengo diario |
| Sobretiempo | 25 % y 35 % | **60 % y 100 %** |
| Aporte propio | — | **CONAFOVICER 2 %** |
| Vínculo | Indefinido o plazo fijo | **Por obra determinada** |

Modelar esto con el régimen general obligaría a cargar a mano, cada
semana y por trabajador, importes que en realidad salen de una tabla
publicada.

## 2. Qué instala

### 2.1 Maestros

| Modelo | Qué guarda |
|---|---|
| `l10n_pe.hr.construction.category` | Operario, oficial, peón y su % de BUC |
| `l10n_pe.hr.construction.wage.table` | Tabla salarial de un convenio, **con vigencia** |
| `l10n_pe.hr.construction.wage.line` | Jornal, movilidad y BUC de cada categoría |
| `l10n_pe.hr.construction.bonus` | Catálogo de bonificaciones (BAE y por condiciones) |
| `l10n_pe.hr.construction.site` | Obras, con las bonificaciones que activan |
| `l10n_pe.hr.conafovicer` | Liquidación mensual de la retención |

**El jornal no se escribe a mano.** Es un campo calculado que sale de la
tabla vigente a la fecha, según la categoría. Cuando entra un convenio
nuevo se carga su tabla y ya está: no hay que editar trescientos
trabajadores ni queda nadie con el importe del año pasado.

### 2.2 Campos en el trabajador (`hr.version`)

```
l10n_pe_construction_category_id   Operario / oficial / peón
l10n_pe_construction_site_id       Obra a la que está asignado
l10n_pe_construction_bae_id        Especialidad BAE (solo operarios)
l10n_pe_construction_bonus_ids     Bonificaciones propias del puesto
l10n_pe_sctr_health                Cobertura SCTR de salud
l10n_pe_daily_wage                 Jornal vigente (calculado)
```

### 2.3 Estructura salarial `CONSTRUCCIÓN CIVIL`

Con su código de la tabla 22 de SUNAT entre paréntesis:

| Código | Concepto | Cálculo |
|---|---|---|
| `JOR` | Jornal básico (0121) | jornal × días |
| `DSO` | Descanso semanal obligatorio (0100) | jornal ÷ 6 × días |
| `BUC` | Bonificación unificada (0300) | 32 % operario · 30 % oficial y peón |
| `MOV` | Movilidad (0904) | importe fijo × días |
| `BAE` | Alta especialización (0300) | % según especialidad |
| `BALTI` `BAGUA` `BCOTA` `BALTU` | Bonificaciones por condiciones | del catálogo, por puesto u obra |
| `HE60` `HE100` | Horas extras (0105/0106) | valor hora × 1.6 / × 2 |
| `INDEM` | Indemnización 15 % (0916) | 15 % de jornal + extras a valor simple |
| `VAC10` | Vacaciones 10 % (0400) | 10 % del básico percibido |
| `GRAT` | Gratificación proporcional (0406/0407) | 40 jornales ÷ 210 o ÷ 150 |
| `BEXT` | Bonif. extraordinaria Ley 30334 (0906) | 9 % de la gratificación |
| `AESC` | Asignación escolar (0201) | 30 jornales al año por hijo |
| `CONAF` | CONAFOVICER (0703) | 2 % de jornal + D.S.O. |
| `TREM` | Remuneración computable | base afecta, **enumerada** |
| `ESSALUD` `SCTRS` `SCTRP` | Aportes del empleador | % sobre `TREM` |
| `TINGR` `TDES` `NETO` | Totales y neto | |

## 3. Cómo funciona, paso a paso

### Paso 1 — Cargar la tabla del convenio

**Planillas → Construcción civil → Tablas salariales.** El módulo trae
cargada la de la **R.M. N.° 197-2025-TR** (01/01/2026 – 31/12/2026):

| Categoría | Jornal | Movilidad | BUC |
|---|---:|---:|---:|
| Operario | 89.30 | 8.60 | 32 % |
| Oficial | 69.75 | 8.60 | 30 % |
| Peón | 62.80 | 8.60 | 30 % |

Cuando salga el convenio siguiente, se crea una tabla nueva con su
vigencia. Las boletas antiguas **siguen usando el jornal de su fecha**.

### Paso 2 — Revisar bonificaciones y crear las obras

**Bonificaciones** trae el catálogo: las cuatro especialidades BAE (8 %,
9 %, 10 % y 22 %) y las cuatro por condiciones de trabajo (altitud,
contacto con agua, cota cero, altura).

> Los importes de las cuatro **por condiciones** provienen de fuentes
> secundarias, no del PDF de la FTCCP. Por eso son un catálogo editable
> y no están incrustados en las reglas: contrástalos con tu convenio y
> corrígelos sin tocar código.

En **Empleados → Obras** se crea cada obra con las bonificaciones que
activa. Una obra sobre los 3 000 m s. n. m. lleva la de altitud, y todos
sus trabajadores la cobran sin marcarla uno por uno.

### Paso 3 — Configurar la compañía

**Ajustes → Compañías → pestaña «Construcción civil (PE)»**:

| Parámetro | Por defecto |
|---|---|
| EsSalud (%) | 9.00 |
| **SCTR salud (%)** | 0.00 — *la fija tu aseguradora* |
| **SCTR pensión (%)** | 0.00 — *la fija la ONP o la aseguradora* |
| CONAFOVICER (%) | 2.00 |
| Cuenta CONAFOVICER | — |
| Bonif. extraordinaria (%) | 9.00 |
| Edad tope asignación escolar | 18 (21 con estudios superiores) |

Las tasas del SCTR vienen **en cero a propósito**: no las fija la norma
sino el contrato con la aseguradora. Sin tasa no se calcula el aporte —
el módulo no inventa una cifra fiscal.

### Paso 4 — Configurar al trabajador

En la ficha del empleado: régimen laboral **Construcción civil**,
categoría, obra y —si es operario— su especialidad BAE. El jornal
aparece solo, tomado de la tabla.

Marca la **cobertura SCTR** de quienes están expuestos: en una obra
conviven expuestos y personal administrativo, y el SCTR se paga por
quien corre el riesgo, no por toda la planilla.

### Paso 5 — Generar los periodos semanales

**Planillas → Configuración → Generador de periodos**, marcando
*Generar semanales*. Las semanas van de lunes a domingo pero **se cortan
al terminar el mes**: una semana a caballo entre dos meses obligaría a
prorratear al declarar la PLAME, que va por mes. Cortándola, la suma de
las semanas de un mes es exactamente el mes.

### Paso 6 — Calcular la planilla semanal

Boleta con la estructura `CONSTRUCCIÓN CIVIL` y los días trabajados. El
motor calcula todo, incluidos los beneficios que este régimen paga
semana a semana. Con 6 días de un operario:

```
JOR    Jornal básico                        535.80
DSO    Descanso semanal obligatorio          89.30
BUC    Bonificación unificada               171.46
MOV    Bonificación por movilidad            51.60
INDEM  Indemnización 15% (CTS)               87.07
VAC10  Vacaciones 10%                        53.58
GRAT   Gratificación proporcional           119.07
BEXT   Bonificación extraordinaria           10.72
CONAF  CONAFOVICER 2%                       -12.50
```

### Paso 7 — Imprimir la boleta

El botón **Imprimir** de la boleta saca directamente la del régimen:
habla de **jornal básico, categoría, obra y especialidad** en vez de
sueldo mensual. Es una variante de la boleta legal, así que la del
régimen general no cambia y ambos pueden convivir en la misma empresa.

### Paso 8 — Liquidar el CONAFOVICER

**Planillas → Construcción civil → CONAFOVICER.** Se elige el mes y
*Calcular*: consolida las boletas confirmadas de todas sus semanas,
agrupa por trabajador y fija el vencimiento —**día 15 del mes
siguiente**—. *Exportar* genera el detalle en Excel que acompaña al
depósito. Marcado como pagado, queda bloqueado.

### Paso 9 — Declarar la PLAME

Los lotes semanales se declaran en **su mes**: el módulo agrupa todas
las boletas del periodo mensual. Declarar una semana suelta dejaría
fuera el resto del envío que SUNAT espera unido.

## 4. Decisiones que conviene conocer

**El redondeo es el del convenio: una sola vez sobre el importe del
periodo.** Multiplicar el diario ya redondeado por los días desvía seis
céntimos por semana en el oficial — y coincide por casualidad en el
operario, que es lo que hace el error difícil de ver.

**`TREM` enumera lo afecto en vez de sumar la categoría de ingresos.**
Los beneficios sociales (`INDEM`, `VAC10`) y la gratificación con su
bonificación de la Ley 30334 **no aportan**; sumar la categoría entera
los metería dentro sin que nadie lo note.

**La base del CONAFOVICER incluye el D.S.O.** Las fuentes secundarias
dicen «2 % del jornal básico», pero la tabla del convenio lo desmiente:
el operario retiene 12.50 a la semana y el 2 % de 535.80 son 10.72. Con
el dominical dentro, (535.80 + 89.30) × 2 % = 12.50, y cuadra igual en
oficial (9.77) y peón (8.79).

**El BUC está afecto y la movilidad no.** Lo prueba el mismo documento:
el ONP publicado del operario (103.55) es el 13 % de 796.56, que es
jornal + D.S.O. + BUC. La movilidad queda fuera por ser condición de
trabajo.

**Las gratificaciones se devengan en ventanas distintas**: Fiestas
Patrias en 7 meses (210 días) y Navidad en 5 (150). Por eso la diaria de
Navidad es mayor con el mismo jornal.

## 5. Validación

96 tests. La tabla oficial de la R.M. N.° 197-2025-TR es el fixture: se
reproduce concepto por concepto en las tres categorías, no solo el
total.

```bash
odoo-bin -d <bd> -u al_hr_pe_construction --test-enable \
         --test-tags /al_hr_pe_construction
```

Un test fija a propósito un descuadre **del documento oficial**: publica
911.94 para el oficial cuando sus propias columnas suman 911.95, porque
suma importes ya redondeados. Cada concepto coincide uno a uno; el test
está ahí para que nadie «corrija» el motor persiguiendo el 911.94 y
desajuste un concepto que sí está bien.

## 6. Lo que no hace

* **TXT de carga al Banco de la Nación** para el CONAFOVICER: falta la
  especificación del formato. El pago suele hacerse con formulario y el
  detalle en Excel, que sí se genera. No se inventan formatos fiscales.
* **Escalonamiento de la bonificación por altura**: se aplica un
  porcentaje único; el tramo por piso depende del convenio de cada
  empresa y se ajusta en el catálogo.

Queda por confirmar con cada cliente si los cuatro importes de las
bonificaciones por condiciones coinciden con su convenio, y si hay
especialidades BAE fuera de las cuatro de la tabla.

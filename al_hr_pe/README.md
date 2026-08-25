# Planillas Perú — Núcleo de la localización

La ficha laboral peruana, los catálogos de SUNAT, las reglas salariales y
los envíos al Estado. Es la base sobre la que se apoya el resto de la
suite.

> **Versión** 10.20260803 · **Depende de** `hr_payroll`,
> `hr_payroll_account`, `l10n_latam_base`, `l10n_pe` · **Licencia** OPL-1
> **Plan de migración**: `docs/planillas/PLAN_MIGRACION_PLANILLAS_V19.md`

---

## 1. Qué resuelve

Odoo trae un motor de nómina; lo que no trae es Perú. Este módulo pone la
norma peruana debajo de ese motor:

* **La ficha laboral peruana** — régimen laboral, situación, tipo de
  trabajador, CUSPP, tipo de comisión AFP, seguro social, dos direcciones
  estructuradas y derechohabientes. Todo en `hr.version`, que en Odoo 19
  absorbió al contrato.
* **Los catálogos de SUNAT** — las tablas paramétricas del Anexo 2 (T05,
  T06, T08, T09, T12, T15, T17, T19, T20, T21, T27, T30, T33, T34, T36)
  cargadas como datos, no escritas dentro del código.
* **Las reglas salariales** — estructura peruana completa con su código de
  la tabla 22: ONP, AFP con sus tres componentes, renta de 5ta, EsSalud,
  asignación familiar, horas extras y descuentos al neto.
* **Los envíos al Estado** — PLAME (`.rem`, `.jor`, `.snl`, `.toc`),
  AFPNet y el T-Registro.

## 2. Las piezas que hay que conocer

| Pieza | Para qué |
|---|---|
| `hr.main.parameter` | Un registro por compañía con toda la configuración: cuentas, categorías de la boleta, conceptos de días y horas, reglas de referencia |
| `hr.period` | El calendario de la planilla. Mensual por defecto; los regímenes semanales cuelgan sus periodos del mes en que se declaran |
| `hr.uit` | UIT y RMV por año fiscal — cifras fechadas, no constantes |
| Snapshot en `hr.payslip` | Al calcular, la boleta fotografía RMV, tasas y datos de la versión |

**Por qué el snapshot importa**: recalcular una boleta de hace seis meses
no debe contaminarla con la norma de hoy. La boleta guarda lo que usó.

## 3. Puesta en marcha, paso a paso

### Paso 1 — Parámetros principales de la compañía

**Planillas → Configuración → Perú → Parámetros principales.** Es el
registro que consulta el resto de la suite. Sin él, la boleta y los
exportadores se niegan a funcionar y lo dicen con un mensaje claro, en vez
de calcular mal en silencio.

### Paso 2 — UIT y remuneración mínima del año

**Configuración → Perú → UIT.** La UIT alimenta los tramos de la renta de
5ta; la RMV, la asignación familiar.

### Paso 3 — Revisar los catálogos

**Configuración → Perú.** Vienen cargados desde el Anexo 2 y se revisan,
no se rellenan: tipos de trabajador, situaciones, regímenes laborales,
ocupaciones, motivos de baja, tipos de suspensión, entidades financieras
e instituciones educativas.

### Paso 4 — Generar los periodos del ejercicio

**Configuración → Perú → Generar periodos.** Un año completo de una vez.
Si hay regímenes semanales, se marca la opción y las semanas quedan
colgadas de su mes.

### Paso 5 — Completar la ficha laboral

**Empleados → ficha → pestaña peruana.** Régimen, situación, tipo de
trabajador, afiliación pensionaria con su CUSPP, seguro social y
direcciones. Estos datos son los que viajan al T-Registro y a la PLAME.

Los **derechohabientes** se registran aquí: de ellos salen la asignación
familiar y las estructuras del T-Registro. El derecho se evalúa por edad y
por estudios **a la fecha de la boleta**, no con una marca manual que
nadie recuerda apagar.

### Paso 6 — Calcular la planilla

La estructura peruana calcula aportes, retenciones y descuentos con las
tasas vigentes a la fecha.

### Paso 7 — Exportar

PLAME genera `.rem`, `.jor`, `.snl` y `.toc`; AFPNet su archivo de
aportes; el T-Registro las estructuras de carga masiva en un ZIP.

## 4. El T-Registro

| Estructura | Qué declara |
|---|---|
| `E04` | Datos de identificación del trabajador |
| `E05` | Datos laborales: régimen, situación, jornada, ocupación |
| `E11` | Domicilio |
| `E17` | Establecimientos donde presta labores |
| `E29` | Formación: educación concluida |
| `E30` | Cuenta de abono de la remuneración |

El formato se verificó contra el instructivo oficial y está documentado en
`docs/planillas/TREGISTRO_ESTRUCTURAS.md`: separador de tuberías **con
tubería final** —su ausencia produce el error EPR1.59—, codificación
latin-1 y nombre `RP_<RUC>.<ext>`.

Los derechohabientes se exportan además en el Excel que alimenta la macro
de SUNAT. Las estructuras **13 y 24 no se generan**: no hay especificación
pública y no se inventan formatos fiscales.

## 5. Decisiones que conviene conocer

**Cero códigos dentro de la lógica.** Qué es un día laborado o qué
categoría es un ingreso se configura en los parámetros. Cambiar de
criterio no exige tocar Python.

**Multicompañía por diseño.** `check_company` en todas partes, reglas de
registro por compañía y parámetros propios: dos empresas con criterios
distintos conviven en la misma base.

**Redondeo SUNAT.** Medio hacia arriba y sobre `Decimal`, no sobre coma
flotante: 267.90 × 15 % da 40.19, no el 40.18 que sale si se confía en el
binario.

**La versión, no el contrato.** Odoo 19 fusionó `hr.contract` en
`hr.version`; toda la ficha laboral vive ahí y el histórico es nativo.

## 6. Tests

```bash
odoo-bin -d <bd> -u al_hr_pe --test-enable --test-tags /al_hr_pe
```

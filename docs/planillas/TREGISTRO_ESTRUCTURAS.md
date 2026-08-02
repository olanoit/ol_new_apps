# T-Registro — estructuras de carga masiva

Extraído del **Manual de Usuario del PVS T-Registro** (SUNAT, actualizado
al 18.09.2023) y de **Ejemplos de carga masiva al T-Registro** (06/2020).
Verificado el 2026-08-02. No inventar campos: lo que no esté aquí hay que
sacarlo del Anexo 3 de la R.M. 121-2011-TR.

## Reglas de formato (§7.3.1 del manual)

* Separador de campos: **palote `|`**, y **también al final de cada línea**.
* Sin espacios en blanco entre campos ni entre palotes.
* Al final de la línea no puede haber espacio, dígito ni carácter especial
  (error `EPR1.59`).
* Campo opcional que no aplica: dos palotes juntos `||`.
* Si `Tipo de documento` es `01`, `04` o `09` → `País emisor` = `604`.
  Si es `07`, el país sale de la tabla 26 del Anexo 2 (distinto de 604).
* Fechas: `dd/mm/aaaa`.

Ejemplos de error que da el propio manual (estructura 11):

```
01|00000999|604|2|1|01/10/2010||| ← falta una columna
01|00000999|604| |1|01/05/1995|||| ← campo vacío o con espacio
01|00000999|604|2|1|01/13/2008|||| ← fecha incorrecta
01|00000999|XXX|2|1|01/12/2004|||| ← valor de la columna 3 incorrecto
```

## Denominación de los archivos (§7.1)

`RP_<RUC>.<ext>` — p. ej. `RP_20512528458.ide`.

| Estructura | Contenido | Extensión |
|---|---|---|
| E04 | Datos personales y domiciliarios | `.ide` |
| E05 | Datos del trabajador | `.tra` |
| E06 | Datos del pensionista | `.pen` |
| E09 | Modalidad formativa laboral | `.pfl` |
| E10 | Personal de terceros | `.ter` |
| E11 | Períodos | `.per` |
| E17 | Establecimientos donde labora | `.est` |
| E23 | Lugar de formación / destaque | `.lug` |
| E29 | Estudios concluidos | `.edu` |
| E30 | Cuenta de abono de remuneraciones | `.cta` |
| E31 | Afiliación a organización sindical (sector público) | `.aos` |

El PVS valida los archivos y genera un **.zip** que es lo que se sube en
SOL → «Mi RUC y Otros Registros» → T-Registro → Carga Masiva.

## Qué estructuras se envían en cada caso

| Operación | Estructuras |
|---|---|
| Alta de trabajador | 4, 5, 11, 17 (+ 29 si tiene estudios concluidos, + 30 si cobra por cuenta) |
| Alta de pensionista | 4, 6, 11 |
| Alta de personal en formación | 4, 9, 11, 23 |
| Alta de personal de terceros | 4, 10, 11, 23 |
| **Baja de cualquiera** | **solo la 11** (fecha de fin + motivo de la Tabla 17 en «Indicador del tipo de registro») |
| Cambio de régimen de salud | 11 (tipo de trabajador vigente + fin del anterior + inicio del nuevo) |
| Cambio de tipo de trabajador | 11 |
| Cambio de régimen pensionario | 5 y 11 |
| Cambio de ocupación / tipo de contrato / tipo de pago… | 5 y 11 |

Detalle importante: al modificar el régimen de salud **hay que reenviar el
tipo de trabajador vigente sin fechas**, para que el PVS pueda validar.

## E04 — Datos personales (41 campos)

Orden verificado en los ejemplos: 1 T.Doc · 2 N.°Doc · 3 País emisor ·
4 Fecha nac. · 5 Ap. paterno · 6 Ap. materno · 7 Nombres · 8 Sexo ·
9 Nacionalidad · 10 Tel. CLD · 11 Tel. número · 12 Correo ·
13-26 Dirección 1 (Tipo vía, Nombre vía, N.° vía, Dpto, Int, Mza, Lot, Km,
Block, Etapa, T. zona, N. zona, Ref., Ubigeo) · 27-40 Dirección 2 (mismo
bloque) · 41 Indicador de centro asistencial.

Validaciones del manual: 1 obligatorio (2); 2 obligatorio (15); 3 solo
para TD 07 y 24 (3); 4 obligatorio; 5 obligatorio (40); 6 y 7 — mínimo un
apellido y un nombre (40); 8 obligatorio (1); 9 obligatorio para TD 04,
07 (4); 10 opcional (3); 11 obligatorio si hay CLD (9).

## E05 — Datos del trabajador (23 campos)

| # | Campo | Tipo | Long. | Tabla / nota |
|---|---|---|---|---|
| 1 | TD del trabajador | Texto | 2 | obligatorio |
| 2 | N.° de documento | Texto | 15 | obligatorio |
| 3 | País emisor | Texto | 3 | solo TD 07 y 24 |
| 4 | Régimen laboral | Texto | 2 | Tabla 33 |
| 5 | Situación educativa | Texto | 2 | Tabla 9 |
| 6 | Ocupación | Texto | 6 | CIUO |
| 7 | Discapacidad | Texto | 1 | obligatorio |
| 8 | CUSPP | Texto | 12 | opcional |
| 9 | SCTR Pensión | Texto | 1 | opcional |
| 10 | Tipo de contrato | Texto | 2 | Tabla 12 |
| 11 | Sujeto a régimen alternativo | Texto | 1 | opcional |
| 12 | Sujeto a jornada máxima | Texto | 1 | opcional |
| 13 | Sujeto a horario nocturno | Texto | 1 | opcional |
| 14 | Es sindicalizado | Texto | 1 | |
| 15 | Periodicidad de la remuneración | Texto | 1 | Tabla 13 |
| 16 | Monto de la remuneración básica | Numérico | 7,2 | opcional |
| 17 | Situación | Texto | 2 | obligatorio |
| 18 | Rentas de 5ta categoría | Texto | 1 | obligatorio |
| 19 | Situación especial | Texto | 1 | Tabla 35 |
| 20 | Tipo de pago | Texto | 1 | Tabla 16 |
| 21 | Categoría ocupacional | Texto | 2 | Tabla 24 |
| 22 | Convenio doble tributación | Texto | 1 | Tabla 25 |
| 23 | Número de RUC | Texto | 11 | solo CAS (TT 67) |

## E11 — Períodos (9 campos)

| # | Campo | Tipo | Long. |
|---|---|---|---|
| 1 | TD | Texto | 2 |
| 2 | N.° de documento | Texto | 15 |
| 3 | País emisor | Texto | 3 |
| 4 | Categoría | Texto | 1 |
| 5 | Tipo de registro | Texto | 1 |
| 6 | Fecha de inicio o reinicio | Fecha | dd/mm/aaaa |
| 7 | Fecha de fin | Fecha | dd/mm/aaaa |
| 8 | Indicador del tipo de registro | Texto | 2 |
| 9 | EPS / Servicios propios | Texto | 1 (Tabla 14) |

Categoría: 1 trabajador · 2 pensionista · 4 personal de terceros ·
5 personal en formación.
Tipo de registro: 1 vínculo · 2 tipo de trabajador · 3 régimen de salud ·
4 régimen pensionario · 5 actividad de riesgo SCTR.

## Otras estructuras cortas

* **E17** (`.est`): TD · N.°Doc · País emisor · RUC propio o del 3.er
  empleador · Cód. establecimiento.
* **E29** (`.edu`): TD · N.°Doc · País emisor · Formación superior
  completa · Indicador educ. completa en IE del Perú · Código de la
  institución educativa · Código de la carrera · Año de egreso.
* **E30** (`.cta`): TD · N.°Doc · País emisor · Cód. entidad bancaria ·
  N.° de cuenta.

## Derechohabientes — pendiente

Las estructuras **13 (altas)** y **24 (bajas)** pertenecen a otro módulo
del T-Registro y **no** están en el manual del PVS de prestadores ni en
los ejemplos. Hasta tener el Anexo 3, la salida de derechohabientes se
genera como **hoja Excel** (`action_export_tregistro_xlsx`), que es lo que
consume la macro oficial de carga masiva para producir el TXT.

## Estado en el código

| Pieza | Estado |
|---|---|
| Modelo de derechohabientes + catálogos | ✅ `al_hr_pe` |
| Asignación familiar derivada de los hijos | ✅ |
| Excel de derechohabientes para la macro SUNAT | ✅ |
| Campos de `hr.version` que exige E05 | ✅ los 23 campos |
| Catálogos del Anexo 2 (T09, T12, T19, T20, T24, T27, T30, T33) | ✅ cargados del xlsx oficial |
| Dirección estructurada (T05 vía, T06 zona, ubigeo) | ✅ dos direcciones en `hr.employee` |
| E04 / E05 / E11 (`.ide` / `.tra` / `.per`) | ✅ ZIP de alta y de baja |
| E17 establecimientos · E29 estudios · E30 cuenta | ✅ se emiten solo si aplican |
| E06 pensionistas · E09 formación · E10 terceros · E23 · E31 | ⬜ fuera de alcance (no son trabajadores) |

### Catálogos cargados

| Tabla | Modelo | Registros |
|---|---|---|
| T09 Situación educativa | `l10n_pe.hr.education.level` | 21 |
| T12 Tipo de contrato | `l10n_pe.hr.contract.type` | 26 |
| T19 Vínculo familiar | `l10n_pe.hr.dependent.type` | 5 |
| T20 Motivo de baja DH | `l10n_pe.hr.dependent.end.reason` | 8 |
| T24 Categoría ocupacional | `l10n_pe.hr.occupational.category` | 11 |
| T27 Documento que sustenta | `l10n_pe.hr.dependent.proof` | 11 |
| T30 Ocupación | `l10n_pe.hr.occupation` | 4 644 (CSV) |
| T33 Régimen laboral | `l10n_pe.hr.labor.regime` | 27 |
| T05 Vía | `l10n_pe.hr.road.type` | 21 |
| T06 Zona | `l10n_pe.hr.zone.type` | 12 |
| T34 Instituciones educativas | `l10n_pe.hr.education.institution` | 1 273 (CSV) |
| T34 Carreras | `l10n_pe.hr.education.career` | 5 925 (CSV) |
| T36 Entidades financieras | `l10n_pe.hr.financial.entity` | 45 |

T13 (periodicidad), T16 (tipo de pago), T25 (convenios) y T35 (situación
especial) son selecciones en `hr.version` cuya **clave es el código
SUNAT**, así que el exportador no tiene que traducir nada.

### Exportador

`hr.employee.action_l10n_pe_export_tregistro()` (alta) y
`…_baja()` generan el ZIP que espera el PVS, disponibles desde el menú
Acción de la lista de trabajadores. El **alta** emite `.ide` + `.tra` +
`.per`; la **baja**, solo `.per` con un renglón. Antes de generar valida
lo que SUNAT rechazaría —documento, apellidos, fechas, y los códigos de
las tablas— y lo dice en un solo mensaje.

Detalles que rompen la carga si se descuidan y aquí están cubiertos:

* palote al final de cada línea (error `EPR1.59`);
* el texto va sin tildes, en mayúsculas y **sin palotes** dentro de los
  nombres, que partirían la línea en columnas de más;
* los archivos se codifican en `latin-1`, que es lo que lee el PVS;
* el teléfono se parte en código de larga distancia y número;
* el ubigeo sale de `l10n_pe.res.city.district` (tabla 28);
* la **baja necesita el motivo de la tabla 17**, que viaja en la columna
  «indicador del tipo de registro».

Ejemplo real generado desde la base:

```
# RP_20512528458.tra
01|42345678|604|01|13|114001|0|345678CDEFG3||01||1||0|1|4200.00|0|1|0|2|03|0||

# RP_20512528458.per (alta: vínculo, tipo de trabajador, salud, pensión)
01|42345678|604|1|1|15/01/2024||||
01|42345678|604|1|2|15/01/2024||19||
01|42345678|604|1|3|15/01/2024||00||
01|42345678|604|1|4|15/01/2024||02||

# RP_20512528458.per (baja)
01|42345678|604|1|1||31/07/2026|09||
```

### E17, E29 y E30: cuándo se envían

Los tres archivos se generan **solo si hay algo que declarar** — un
archivo vacío es un error de estructura para el PVS:

| Estructura | Se envía cuando | De dónde salen los datos |
|---|---|---|
| **E17** `.est` | siempre en el alta | `work_location_id` + «Otros establecimientos», con su código de 4 dígitos |
| **E29** `.edu` | situación educativa 11 o 13 | `l10n_pe.hr.employee.education` (institución y carrera de la T34) |
| **E30** `.cta` | tipo de pago 2 (depósito) | `primary_bank_account_id` + código T36 del banco |

Con el indicador «estudió en el Perú» en 0, los tres campos siguientes de
la E29 van vacíos, como exige el manual.

La E30 aplica las validaciones que rechaza SUNAT: de 6 a 20 dígitos, no
todos iguales, sin contener el documento del trabajador, el largo que
admite cada banco (BCP 13/14/20, BBVA 18/20, Interbank 13/20…) y, si son
20 dígitos de una entidad con CCI, que empiece por su propio código.

Ejemplo real:

```
# RP_20512528458.est (dos locales del mismo RUC)
01|42345678|604|20512528458|0001|
01|42345678|604|20512528458|0018|

# RP_20512528458.edu
01|42345678|604|13|1|140332361|812015|2014|

# RP_20512528458.cta
01|42345678|604|002|19100000005480|
```

### Códigos que hay que llenar una vez

El régimen de salud y el pensionario no tenían código SUNAT en sus
maestros: se añadieron `l10n_pe_tregistro_code` a `hr.social.insurance`
(T32) y a `hr.membership` (T11). Sin ellos la E11 sale con esas columnas
vacías.

Igual con el **código de establecimiento** en cada `hr.work.location`
(4 dígitos, el del RUC) y la **entidad T36** en cada `res.bank`: sin
ellos no salen la E17 ni la E30.

### Dos ejes de régimen laboral

`l10n_pe_labor_regime_id` es el régimen de la T33 (27 valores) y
`l10n_pe_labor_regime` la familia de cálculo que usa el motor de
beneficios (5 valores: divisores de CTS, gratificación y vacaciones). El
primero sincroniza al segundo en `create` y `write` —no solo por
`onchange`— para que una importación masiva no deje la CTS con el divisor
de otro régimen.

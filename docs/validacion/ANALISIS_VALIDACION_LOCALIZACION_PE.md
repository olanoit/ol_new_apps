# Análisis y validación de la localización peruana

**Base:** `ol_pe_v19` (clon `ol_pe_v19_qa` para las pruebas) · **Configuración:** `cfg/my/pe.cfg` · **Odoo:** 19.0
**Fecha:** 27 de agosto de 2026 · **Alcance:** 27 módulos de localización peruana (contabilidad, comprobantes, libros, TPV, inventario y planillas)

---

## 1. Resumen ejecutivo

La validación se hizo en dos planos complementarios:

1. **Pruebas unitarias módulo a módulo** sobre un clon de la base, un
   arranque de Odoo por módulo (`-u <módulo> --test-enable --test-tags
   /<módulo>`), con log independiente.
2. **Auditoría funcional de solo lectura** sobre la base real, para
   comprobar que lo instalado está además configurado y en uso.

| Indicador | Antes | Después |
| --- | ---: | ---: |
| Módulos de localización con pruebas | 23 de 27 | **27 de 27** |
| Pruebas unitarias | 619 | **707** (+88) |
| Módulos en verde | 22 (1 en rojo, 4 sin pruebas) | **26** (+1 que exige navegador, H-08) |
| Defectos encontrados | — | **3 corregidos**, 5 documentados |
| Comprobaciones funcionales sobre la base real | — | **126** (109 OK · 17 avisos · 0 fallas) |

Los tres defectos corregidos no los detectaba la suite anterior porque
nadie probaba ese camino: dos aparecieron al escribir las pruebas que
faltaban y el tercero, el más grave, estaba tapado por un cambio de
comportamiento del propio Odoo 19.

---

## 2. Qué se ejecutó

```bash
# Clon de trabajo (el servidor parado)
psql -U odoo -d postgres -c "CREATE DATABASE ol_pe_v19_qa TEMPLATE ol_pe_v19;"

# Batería, un arranque por módulo
docs/validacion/pruebas/run_tests.sh al_account_base al_l10n_pe_ple ...

# Auditoría sobre la base real (no escribe nada)
.venv/bin/python3 odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
    < docs/validacion/pruebas/auditoria_localizacion_pe.py
```

Las pruebas **no** se ejecutan contra `ol_pe_v19`: `--test-enable` obliga
a actualizar el módulo y eso reescribiría sus datos XML sobre la base de
trabajo. El clon conserva los mismos datos y elimina el riesgo.

---

## 3. Resultado por módulo

Leyenda: **N** = pruebas ejecutadas · *(+n)* = pruebas añadidas en esta validación.

### 3.1 Base contable y comprobantes

| Módulo | Pruebas | Resultado | Qué cubre |
| --- | ---: | --- | --- |
| `al_account_base` | 12 *(+5)* | ✅ | Establecimiento anexo, código de banco, tipo de diario, glosa del asiento y de la línea (no se copia al duplicar) |
| `al_account_destinations` | 6 | ✅ | Asiento de destino 6→9: distribución al 100 %, redondeo en la última línea, sin recursión |
| `al_account_move_name_sequence` | 9 | ✅ | Numeración opt-in por diario y series CPE con correlativo sin huecos |
| `al_account_payments` | 9 *(+9)* | ✅ | Catálogo 1 de SUNAT, traslado del medio de pago desde el asistente, también en pagos agrupados |
| `al_l10n_pe_invoice` | 19 *(+16)* | ✅ | Desglose tributario por código SUNAT, factura en moneda extranjera, cuotas de crédito, descuento global, reportes A4/ticket |
| `al_l10n_pe_city` | 7 *(+7)* | ✅ | Ubigeo: 617 ciudades, ninguna huérfana de departamento, ciudad→departamento en el contacto |
| `al_l10n_pe_currency` | 63 | ✅ | Tipo de cambio compra/venta, fuente BCRP, elección del tipo en factura y en pago, diferencia de cambio |
| `al_l10n_pe_account_letter` | 17 | ✅ | Letras de cambio, canje, refinanciación masiva |
| `al_l10n_pe_detraction` | 37 | ✅ | Detracción SPOT, TXT del Banco de la Nación (longitudes y posiciones), depósito masivo |
| `al_l10n_pe_retention` | 22 | ✅ | Retención de IGV en el pago y constancia |
| `al_l10n_pe_exchange_closure` | 36 | ✅ | Ajuste por diferencia de cambio sobre saldos acumulados |
| `al_l10n_pe_delivery_guide_report` | 11 *(+8)* | ✅ | Guía de remisión: agrupación del detalle por producto/UdM, series y lotes, peso bruto |

### 3.2 Libros electrónicos y SUNAT

| Módulo | Pruebas | Resultado | Qué cubre |
| --- | ---: | --- | --- |
| `al_l10n_pe_ple` | 71 | ✅ | Formatos RCE 8.4, RVIE 14.4, exportación de los libros, Excel del SIRE |
| `al_l10n_pe_sire` | 27 | ✅ | RVIE/RCE por API: autenticación, descarga de propuesta, envío |
| `l10n_pe_vat_sunat` | 28 | ✅ | Consulta RUC/DNI, mapeo config-driven, conexión Decolecta, parser del padrón |
| `ol_stock_kardex_pe` | 8 | ✅ | Registro de inventario permanente 12.1 / 13.1, valorizado AVCO y físico por almacén |

### 3.3 Punto de venta

| Módulo | Pruebas | Resultado | Qué cubre |
| --- | ---: | --- | --- |
| `al_l10n_pe_edi_pos` | 6 | ✅ | Boleta y factura desde el TPV, diario por tipo de documento |
| `al_pos_vendedor` | 10 *(+10)* | ✅ | Lista blanca de vendedores, carga de `hr.employee` en el TPV, vendedor en la orden y en el análisis de ventas |
| `al_pos_product_view` | 1 | ⚠️ | Prueba de navegador (tour): necesita el servidor HTTP levantado, ver §5 (H-08) |

### 3.4 Planillas

| Módulo | Pruebas | Resultado | Qué cubre |
| --- | ---: | --- | --- |
| `al_hr_pe` | 91 | ✅ | Maestros, motor de cálculo, derechohabientes, T-Registro (E04/E05/E11/E17/E29/E30) |
| `al_hr_pe_account` | 17 *(+14)* | ✅ | Asiento de lote y de beneficios, asistente de previsualización, enlace con las boletas |
| `al_hr_pe_attendance` | 35 | ✅ | Tareaje: clasificación peruana de horas y sobretasas |
| `al_hr_pe_benefits` | 9 | ✅ | CTS, gratificación, récord vacacional, quinta categoría, préstamos |
| `al_hr_pe_construction` | 96 | ✅ | Convenio de construcción civil, CONAFOVICER, BUC, periodicidad semanal |
| `al_hr_pe_import` | 21 | ✅ | Importadores Excel y prueba extremo a extremo multicompañía |
| `al_hr_pe_public_holidays` | 17 *(+17)* | ✅ | Calendario 2026-2035, Semana Santa contra el cómputo de la Pascua, aplicación idempotente a los calendarios |
| `al_hr_pe_reports` | 22 *(+2)* | ✅ | TXT de pago masivo (BBVA, BCP, Interbank, Scotiabank, BanBif), certificados |

---

## 4. Pruebas añadidas

88 pruebas nuevas, repartidas en dos frentes.

**Módulos que no tenían ninguna** (4):

* `al_account_payments` — el catálogo 1 de SUNAT y, sobre todo, el
  traslado del medio de pago cuando el asistente agrupa varias facturas
  en un solo pago: ese camino (`_create_payment_vals_from_batch`) es
  distinto del normal y podría haberse quedado sin parchear.
* `al_hr_pe_public_holidays` — los 17 feriados nacionales de cada año
  (2026-2035), con Jueves y Viernes Santo cuadrados contra la Pascua
  calculada, y la aplicación a los calendarios: idempotencia, zona
  horaria, medio día, borrado en cascada y acotación multicompañía.
* `al_pos_vendedor` — la lista blanca de vendedores y su efecto en el
  selector del TPV, la carga de `hr.employee` cuando `module_pos_hr`
  está desactivado, y el vendedor en la vista SQL de análisis de ventas.
* `al_l10n_pe_city` — integridad del ubigeo: ninguna ciudad sin
  departamento, ningún departamento de otro país, capitales de control.

**Módulos con cobertura fina** (5): desglose tributario y bloques del
comprobante (`al_l10n_pe_invoice`), agrupación y peso de la guía
(`al_l10n_pe_delivery_guide_report`), asistente del asiento de planilla
(`al_hr_pe_account`), glosa peruana (`al_account_base`) y seguridad de
las plantillas de los TXT bancarios (`al_hr_pe_reports`).

---

## 5. Hallazgos

### H-01 · Crítico · El TXT de pago masivo de Interbank salía sin formatear

**Dónde:** `al_hr_pe_reports/models/hr_multipayment.py`
(`interbank_haberes_txt` y `interbank_cts_txt`)

Odoo 19 parchea `str.format` (`odoo/_monkeypatches/_cpython.py`) para
frenar la inyección por cadena de formato. Si un campo de la plantilla
contiene `__` o un atributo de la lista negra de `safe_eval`, **devuelve
la plantilla sin sustituir, en silencio, sin error ni aviso**.

El campo se llamaba `benef_code`, que contiene la subcadena `f_code`
(atributo de *frame*). Resultado: el detalle del archivo salía como

```
02{doc_type}{benef_code}{doc_number}{date_to}{charge_currency}...
```

229 caracteres de plantilla literal en lugar de los 380 del formato del
banco. Interbank habría rechazado el lote completo.

**Corrección:** campo renombrado a `beneficiary_code` y prueba de
regresión (`test_format_safety.py`) que recorre todas las plantillas del
generador y falla si alguna vuelve a usar un nombre vetado. El resto de
bancos (BBVA, BCP, Scotiabank, BanBif) estaba limpio: se revisó el
repositorio entero y solo esas dos plantillas estaban afectadas.

### H-02 · Alto · Los feriados se guardaban desplazados cinco horas

**Dónde:** `al_hr_pe_public_holidays/models/holidays.py`
(`action_apply_to_calendars`)

El módulo convierte el día del feriado al huso del calendario y lo guarda
en UTC. Pero `hr_holidays` (`_prepare_public_holidays_values`) supone que
las fechas que llegan a `create` vienen expresadas en el huso del
**usuario** y las reconvierte al del calendario: segunda conversión sobre
una fecha ya convertida.

Con un usuario sin zona horaria y un calendario en `America/Lima`, el
descanso del 28 de julio se guardaba de 10:00 a 09:59 UTC — es decir, de
las 05:00 del feriado a las 04:59 del día siguiente en hora local. Las
cinco primeras horas del feriado quedaban fuera y cinco horas del día
siguiente quedaban marcadas como descanso.

**Corrección:** tras crear el descanso se fijan las fechas con `write`,
que no reinterpreta nada. Prueba de regresión incluida. En la base real
todavía no se habían aplicado feriados a ningún calendario (§6), así que
no hay datos que rehacer.

### H-03 · Alto · El descuento global del comprobante siempre salía en cero

**Dónde:** `al_l10n_pe_invoice/models/account_move.py`
(`get_amount_discount`)

El filtro heredado de v18 era `not x.display_type and x.price_total < 0`.
En Odoo 19 las líneas de producto llevan `display_type = 'product'` (ya no
`False`), así que la condición no casaba con **ninguna** línea y el
método devolvía siempre `0.0`: el bloque de descuento del comprobante
impreso aparecía vacío aunque la factura tuviera líneas en negativo.

**Corrección:** el filtro pasa a `display_type in ('product', 'discount')`.
Prueba incluida (factura de 1 000 con descuento de 100 → 118 con IGV).

### H-04 · Medio · La ficha de los módulos salía en blanco en Apps — CORREGIDO

**Dónde:** `*/static/description/index.html` — 30 de los 31 módulos.

`ir.module.module.description_html` se calcula pasando el `index.html`
por `lxml` y `html_sanitize`. Los archivos empezaban con
`<meta charset="utf-8"/>`, y con esa etiqueta al frente lxml coloca todo
el contenido dentro del `<head>`: el sanitizador devuelve cadena vacía.
De ahí el `module <nombre>: description is empty!` que aparecía en cada
arranque, y la ficha en blanco en la vista de Aplicaciones.

**Corrección:** eliminada esa primera línea en los 30 archivos.
`al_mcp_server` no se tocó: es el único con documento HTML completo, su
`<meta charset>` va dentro de un `<head>` legítimo y ya renderizaba.

Al hacerlo apareció un segundo defecto en `al_project_gantt_base`,
`_backend` y `_website`: las tres primeras líneas estaban duplicadas, lo
que dejaba un `<section class="alc">` abierto sin cerrar (8 aperturas
frente a 7 cierres). Eliminado también.

**Verificación** con el ORM sobre `ol_pe_v19_qa`, leyendo
`description_html` de cada módulo: los 31 devuelven ahora entre 2 359 y
87 090 caracteres; antes, 30 devolvían 0. `al_l10n_pe_city` queda fuera
—no tiene `index.html`, es un módulo de datos en `tools/` cuya
descripción es la línea del manifiesto.

### H-05 · Medio · Dos campos para «buen contribuyente» y dos para «agente de retención» — CORREGIDO

`l10n_pe_vat_sunat` mantiene `is_good_taxpayer` e `is_retention_agent` en
`res.partner`, verificados automáticamente contra el padrón de SUNAT
(57 922 registros cargados en la base). `al_l10n_pe_retention` definía
`l10n_pe_good_contributor` y `l10n_pe_retention_agent`, de marcado
manual, y **era el par manual el que decidía** si se retiene
(`account_move.py`).

Consecuencia: un proveedor que el padrón marcase como buen contribuyente
seguía sufriendo retención mientras nadie replicase la marca a mano —las
dos únicas excepciones subjetivas del régimen quedaban sin efecto—, y
Odoo lo delataba en el arranque con el aviso de etiquetas duplicadas.

**Corrección:** la fuente única pasa a ser el par del padrón.

* `al_l10n_pe_retention` depende ahora de `l10n_pe_vat_sunat` y elimina
  sus dos campos, su modelo `res_partner.py` y su vista de contacto.
* `_compute_l10n_pe_retention` lee `is_retention_agent` e
  `is_good_taxpayer`, con el `@api.depends` reapuntado.
* Los dos campos dejan de ser `readonly` en la vista del padrón: se
  mantienen solos, pero el padrón puede ir por detrás de la designación
  de SUNAT y hay que poder corregirlos.
* Migración `19.0.4.20260827/post-migrate.py`: vuelca a los campos del
  padrón lo que estuviera marcado a mano —gana la marca manual— leyendo
  por SQL las columnas antiguas, que Odoo no elimina. Verificada en la
  actualización de `ol_pe_v19_qa`: «1 contactos volcados de
  `l10n_pe_retention_agent` a `is_retention_agent`».

El campo homónimo de `res.company` (la compañía **es** agente designado)
es otra cosa y no se toca.

**Verificación:** se volvió a pasar la batería entera después del
cambio —los 26 módulos que no exigen navegador, 706 pruebas, todos con
`rc=0` y ningún fallo—, porque tocar el grafo de dependencias afecta al
orden de carga de toda la suite. En particular `al_l10n_pe_retention`
22, `l10n_pe_vat_sunat` 28, `al_l10n_pe_currency` 63,
`al_l10n_pe_detraction` 37 y `al_l10n_pe_invoice` 19.

### H-06 · Bajo · Dependencia no buscable en las letras masivas

`l10n_pe.letter.massive.refinance_origin_ids` figura en el `@api.depends`
de `refinance_origin_display` pero no es un campo buscable, así que el ORM
no puede determinar qué registros recalcular cuando cambia
`l10n_pe.letter.name`. Aviso en cada arranque; el display puede quedarse
obsoleto.

### H-07 · Bajo · Un campo del core deja de precomputarse

`account.move.invoice_currency_rate` no se puede precomputar porque
depende de `l10n_pe_exchange_rate_type` (de `al_l10n_pe_currency`), que no
es precomputado. No hay error funcional; sí una escritura adicional por
factura.

### H-08 · Informativo · La prueba de `al_pos_product_view` necesita HTTP

Es un *tour* de navegador (`HttpCase`). Con `--no-http` falla en el
arranque del navegador, no en el código del módulo. Para ejecutarla hay
que lanzar el servidor con HTTP en un puerto libre:

```bash
.venv/bin/python3 odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19_qa --http-port=19760 \
    --stop-after-init -u al_pos_product_view --test-enable \
    --test-tags /al_pos_product_view
```

---

## 6. Auditoría funcional sobre la base real

126 comprobaciones sobre `ol_pe_v19`: **109 OK, 17 avisos, 0 fallas**.
Ningún módulo tiene datos maestros incompletos ni modelos que no
respondan. Los avisos son tareas de puesta en marcha, no defectos:

| Área | Aviso | Comentario |
| --- | --- | --- |
| Medios de pago | 0 de 4 pagos con medio de pago informado | El campo no es obligatorio; conviene exigirlo si se van a declarar los medios en el PLE |
| Conexiones API | 6 conexiones sin credencial | Duplicadas por compañía; solo 4 están operativas |
| Detracciones | Ninguna compañía tiene cuenta del Banco de la Nación | Bloquea el bloque de detracción del comprobante y el TXT del BN |
| Letras | 3 letras sin cuotas | `CLC00089`, `CLC00091`, `CLC00095` |
| SIRE | Credenciales incompletas en ambas compañías | Falta el par cliente API + usuario SOL |
| Kardex | Categorías con valoración `periodic` | El 13.1 valorizado se apoya en la valoración de existencias |
| Planillas | Servicios Andinos sin diario ni partner de asiento | La segunda compañía no puede contabilizar planilla |
| Planillas | 2 empleados sin documento de identidad | Bloquearía el T-Registro y los TXT bancarios |
| Planillas | 0 feriados aplicados a calendarios | Los 170 feriados están cargados pero no volcados (ver H-02) |

Lo que sí quedó verificado con datos reales: 2 compañías peruanas con RUC
de 11 dígitos, plan contable de 2 486 cuentas, 4 series CPE publicadas y
numerando sin huecos, 617 ciudades de ubigeo, 26 tipos de detracción,
tipo de cambio con compra 3,391 y venta 3,400 de origen SUNAT, retención
de IGV al 3 % con su serie de constancia `R001-`, desglose tributario
cuadrado en las 45 facturas de la muestra, 2 cierres de tipo de cambio
contabilizados, 4 estructuras salariales con reglas y 84 boletas.

---

## 7. Conclusión

Los 27 módulos de localización peruana pasan sus pruebas y la base real
está operativa. La suite creció de 619 a 707 pruebas y ya no queda ningún
módulo sin cobertura.

La validación destapó tres defectos que llegaban a producción sin ruido:
un archivo bancario que el banco habría rechazado, feriados desplazados
cinco horas y un descuento que siempre se imprimía en cero. Los tres
comparten un mismo origen —código portado de v18 que se apoya en
comportamientos que Odoo 19 cambió— y los tres quedan corregidos con su
prueba de regresión.

Después del informe inicial se corrigieron además H-04 y H-05: los 30
`index.html` afectados ya renderizan su ficha en Aplicaciones —y de paso
se cerró el `<section>` duplicado de tres módulos Gantt—, y las dos
excepciones al régimen de retenciones pasan a leerse del padrón SUNAT en
lugar de depender de un marcado manual que nadie replicaba.

**Pendiente:** completar la puesta en marcha de la base —cuenta del Banco
de la Nación, credenciales SIRE, diario de planilla de la segunda
compañía y volcado de los feriados a los calendarios—, que son los
avisos de §6 y no defectos del código.

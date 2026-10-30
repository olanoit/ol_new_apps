[← Validación](../README.md)

# Guía de la validación funcional · Migración a Odoo 20

**Base:** `ce20_db_ol` (compañía «OLANO IT S.A.C. (dev)», RUC 20557912879, plan `pe`) · **Configuración:** `cfg/ol_odoo.cfg` · **Rama:** `20.0`
**Fecha:** 30 de octubre de 2026 · **Alcance:** los 120 módulos de `OL-*`, módulo a módulo, siguiendo la ruta de pruebas del consultor funcional

Esta guía explica **cómo se validó** cada desarrollo después de migrarlo a Odoo 20: qué se hizo, con qué datos, qué se encontró, qué se corrigió y cómo repetirlo. El detalle de cada caso (pasos, comprobaciones con valor esperado y obtenido, registros creados) está en [`ANEXO_CASOS.md`](ANEXO_CASOS.md).

---

## 1. Resumen

| Indicador | Resultado |
|---|---|
| Módulos cubiertos | **118 de 120** con casos propios; `al_l10n_pe_edi_service` dentro del caso de la liquidación de compra; `al_pos_online_payment` (solo JS) en la prueba del TPV en navegador; `al_l10n_pe_city` no instalable |
| Casos ejecutados | **232** (211 sobre la base y 21 en navegador) |
| Comprobaciones | **1 776** valores comparados contra lo esperado |
| Resultado de la corrida | 212 ✅ · 16 ⚠️ · 4 ❌ (los 5 ❌ de proyectos se repitieron y pasaron; ver §5.5) |
| Defectos reales encontrados | **8** (§6), todos corregidos con su test |
| Pruebas unitarias de los módulos corregidos | ver §7 |

Ninguno de los 8 defectos lo detectaban las pruebas unitarias: aparecieron al usar el sistema como un usuario real. Hay tres motivos:
- **Permisos:** los tests corren como superusuario.
- **Datos ya cargados:** los feriados del catálogo y la secuencia nativa de retenciones existían antes del módulo.
- **El navegador:** el TPV no cargaba con la impresora de red activa, y eso solo se ve al abrirlo.

---

## 2. Método

### 2.1 Principios

1. **Registros reales y persistentes.** Cada caso crea sus datos (contactos, productos, facturas, pagos, nóminas, obras…) y **hace commit**: quedan en la base para revisarlos en pantalla. Todos llevan el prefijo **`QA20`** en el nombre.
2. **El desarrollo propio, no lo nativo.** Cada caso ejercita lo que agrega el módulo (cálculo, asiento, archivo SUNAT, bloqueo, permiso) y compara el resultado con un valor calculado a mano en el script.
3. **El usuario que lo usa.** Donde importa, el caso corre con un usuario sin privilegios: cajero, químico farmacéutico, jefe de obra, aprobador. Así salieron los defectos de permisos.
4. **Sin efectos externos.** No se envió nada a SUNAT, OSE, RENIEC, bancos ni pasarelas. Esas llamadas se **simularon** como en los tests (`unittest.mock.patch`) y se validó lo que se genera: XML UBL firmado, TXT del PLE, payload y firma HMAC. Cada envío omitido queda marcado ⏭️ con su motivo.
5. **Respaldo previo.** Antes de escribir en la base: `~/odoo/backups_db/ce20_db_ol_20261030_pre_validacion.dump`.

### 2.2 Herramientas (carpeta `docs/validacion/v20/`)

| Archivo | Para qué |
|---|---|
| `_qa.py` | Librería común: `caso()`, `check()`, `igual()`, `aviso()`, `omitido()`, `registro()` y `ejecutar()`. Cada caso corre en un *savepoint*: si revienta, se registra ❌ y se sigue con el siguiente |
| `_fin.py` | Calcula el estado de cada caso, escribe `resultados/<fase>.json` y hace commit (o rollback con `QA_ROLLBACK`) |
| `run_qa.sh <fase> [rollback]` | Ejecuta `fase_<fase>.py` en `odoo shell` sobre `ce20_db_ol`, con log en `resultados/<fase>.log` |
| `fase_*.py` | Un script por bloque de la ruta (§5) |
| `generar_anexo.py` | Arma `ANEXO_CASOS.md` desde los JSON |
| `qa20_credenciales.env` | Usuario de prueba `qa20_admin` para el navegador (contraseña generada; solo para esta base local) |

### 2.3 Estados

- ✅ **OK**: el resultado coincide con lo esperado.
- ⚠️ **AVISO**: el flujo funciona, pero hubo que completar configuración vacía de la base o el comportamiento difiere de lo documentado. No es un defecto del código.
- ❌ **FALLA**: el desarrollo no hace lo que debe.
- ⏭️ **OMITIDO**: no se puede probar aquí (servicio externo, impresora física, reinstalación en base vacía).

### 2.4 Ejecución

Los seis bloques corrieron **en paralelo** sobre la misma base, cada uno con sus propios datos `QA20` (diarios, almacenes y cajas con códigos propios). Para no chocar entre ellos:
- Los casos que escriben en la compañía confirman al terminar cada caso y reintentan si sale un error de concurrencia.
- Los procesos que leen **todos** los saldos de la compañía (cierre de tipo de cambio y revaluación) usaron dos compañías aisladas: «QA20 P4 Cierre TC» (id 1043) y «QA20 P4 Revaluación» (id 1044).

Cada script se depuró primero en modo `rollback` y al final se ejecutó **una vez con commit**. Los JSON de `resultados/` son de esa corrida final.

---

## 3. Cómo repetir la validación

```bash
cd /home/och/odoo/ce20/myapps/ol_new_apps/docs/validacion/v20

# Un bloque, sin dejar registros (para revisar el script)
./run_qa.sh contabilidad_a rollback

# Un bloque, dejando los registros en la base
./run_qa.sh contabilidad_a

# Rehacer el anexo
python3 generar_anexo.py
```

Bloques: `contabilidad_a`, `contabilidad_b`, `facturacion_tpv`, `inventario_farmacia`, `proyectos` (+ `proyectos_ingreso`), `planillas_tools`.

**Volver a ejecutar con commit duplica registros.** Algunos diarios tienen códigos fijos (`Q1*`…`Q4*`, `QV20`, `Q20CJ`), así que su creación chocaría con los existentes. Para repetir desde cero, restaurar el respaldo:

```bash
PGPASSWORD=odoo dropdb -h localhost -U odoo ce20_db_ol      # con el servidor parado
PGPASSWORD=odoo createdb -h localhost -U odoo ce20_db_ol
PGPASSWORD=odoo pg_restore -h localhost -U odoo -d ce20_db_ol --no-owner \
    ~/odoo/backups_db/ce20_db_ol_20261030_pre_validacion.dump
```

Las pruebas unitarias de un módulo se corren **en un clon**, nunca en `ce20_db_ol`. Así se hizo aquí, con `ce20_db_ol_qa` en el puerto 20013, para no detener el servidor de trabajo:

```bash
cd /home/och/odoo/ce20
./.venv/bin/python odoo-bin -c cfg/ol_odoo.cfg -d ce20_db_ol_qa --db-filter='^ce20_db_ol_qa$' \
    --http-port=20013 --gevent-port=8073 --max-cron-threads=0 \
    -u <modulo> --test-enable --test-tags /<modulo> --stop-after-init
```

---

## 4. Fase 0 · Cliente web y TPV en el navegador

Antes de los procesos se comprobó en Chrome, con `qa20_admin`, que las pantallas propias cargan sin errores. Primero se validó el detector: se lanzó una excepción a propósito y apareció en la consola y en el diálogo «¡Vaya!».

| Pantalla | Módulo | Resultado |
|---|---|---|
| Inicio del planificador, árbol de recursos, cronograma de obra | `al_construction_planner` | ✅ |
| Tablero de abastecimiento | `al_construction_planner_purchase` | ✅ |
| Reporte de programación | `al_construction_planner_sale` | ✅ |
| Tablero de cobranza / Tablero Perú | `al_l10n_pe_collection`, `al_l10n_pe_dashboard` | ✅ |
| 3.19 Patrimonio, hojas de trabajo 1 y 2 | `al_l10n_pe_financial_reports` | ✅ |
| PLE 7.1, 8.1, 8.2, 14.1 | `al_l10n_pe_ple` | ✅ |
| Gantt de proyectos | `al_project_gantt_backend` | ✅ |
| Facturas, pagos, trabajos en cola, puntos de venta, solicitudes de compra | varios | ✅ |
| **TPV** «QA20 TPV CPE» con impresora de red activa | `al_pos_network_printer` | ❌ → corregido (defecto 1) |

La prueba automática `al_docs_help/tests/test_webclient_boot.py` cubre el arranque del cliente web. Para el TPV se agregó un tour de arranque con la impresora ESC/POS activa (§6, defecto 1).

---

## 5. Resultado por bloque

| Bloque | Módulos | Casos | Resultado | Comprobaciones |
|---|---:|---:|---|---:|
| 1A · Contabilidad: base, impuestos y reportes | 16 | 33 | ✅ 30 · ⚠️ 3 | 236 |
| 1B · Contabilidad: cobros, pagos, bancos y cierre | 31 | 48 | ✅ 47 · ⚠️ 1 | 472 |
| 2–3 · Facturación electrónica y TPV | 19 | 31 | ✅ 27 · ⚠️ 3 · ❌ 1 | 267 |
| 4–7 · Inventario, farmacia e industrias | 26 | 38 | ✅ 35 · ⚠️ 2 · ❌ 1 | 313 |
| 5 · Proyectos y construcción | 28 | 34 | ✅ 34 (5 tras repetir) | 181 |
| 6–8 · Planillas y herramientas | 16 | 27 | ✅ 18 · ⚠️ 7 · ❌ 2 | 286 |

### 5.1 Contabilidad: base, impuestos y reportes

Se emitieron y revisaron:
- facturas en USD con tipo de cambio de compra y de venta;
- asientos de destino 9/79;
- detracción con depósito y TXT del Banco de la Nación;
- retención con su CRE (XML generado y flujo de anulación «En reversión» → «Anulado»);
- percepción, renta de 4.ª, ITF y declaración 621 con la UIT tomada de los parámetros de nómina;
- PLE 5.1, 6.1, 8.4 y 14.4;
- RVIE y RCE con un no domiciliado (país, modalidad y tipo de renta salen de los campos nativos);
- consulta de validez de comprobantes, estados financieros y tablero.

Se confirmaron los cambios de la migración:
- el código SUNAT del banco **es** el `clearing_number` nativo, en ambos sentidos;
- el DNI va en los identificadores adicionales;
- el sábado y el domingo toman el tipo de cambio del viernes.

### 5.2 Contabilidad: cobros, pagos, bancos y cierre

Se recorrieron:
- **Pagos y cobros:** pago múltiple, aplicación de anticipos, recibos, cuotas en soles, importación de extractos (sin duplicar al reimportar), TXT de pagos masivos BCP, programación de tesorería con lote, recaudación CREP, cobranza con bloqueo de venta por mora.
- **Instrumentos:** cheques recibidos y girados, letras, factoring, caja chica y entregas a rendir con arqueo, las cuatro pasarelas con firma simulada.
- **Financiamiento:** préstamo francés con prepago, cartas fianza, depósitos a plazo, arrendamiento NIIF 16 con remedición, DUA.
- **Cierre:** cierre de tipo de cambio y revaluación.

El número de operación **es** el `payment_reference` nativo. La remedición del arrendamiento se rechaza antes de publicar la depreciación del mes y se acepta después; es la regla de Odoo 20.

### 5.3 Facturación electrónica y TPV

Se generaron y revisaron:
- **Comprobantes:** factura, boleta a DNI, NC y ND (XML UBL y PDF A4/ticket); anticipos, descuentos y transferencias gratuitas; liquidación de compra (renta con la UIT del año); guía de remisión; libro de reclamaciones; checkout web; flujo HKA simulado.
- **TPV:** boleta, factura y nota de crédito; tarjetas de regalo; Yape/Plin; pasarelas; vendedor por orden; búsqueda por RUC/DNI.

Los bundles del TPV compilan con los 10 módulos OL-POS. El cajero que vende con lote necesita el grupo de Inventario: sin él no completa la venta (comportamiento nativo).

### 5.4 Inventario, farmacia e industrias

Se comprobó:
- **Inventario:** tabla 12 en los movimientos; traslados con guía y bienes de terceros sin valorizar; kardex 13.1, cuyo saldo es igual al valor del inventario, y 12.1 con su TXT.
- **Fabricación:** costeo de OF con materiales, MO y CIF; costeo por pieza.
- **Farmacia:** cadena completa con almacén, caja y Q.F. propios (recepción con inspección y cuarentena, FEFO, receta y dispensación, controlados con libro y balance, DIGEMID, TPV con receta y lote, fidelización por DNI, convenio EPS con copago, tratamientos crónicos, faltantes y sugerido, tienda con receta).
- **Industrias:** los paquetes están instalados y sus datos y menús presentes. No se reinstalaron, porque son para bases vacías.

### 5.5 Proyectos y construcción

Se siguió una obra de punta a punta, «QA20 MOMEN-35-26»:
1. plan y versión;
2. presupuesto;
3. requerimiento y solicitud de compra, y OC aprobada por niveles;
4. recepción y despacho;
5. contrata con adelanto, liquidación y valorización;
6. cuadrilla y marcación con costo;
7. valorización al cliente facturada y cobrada;
8. mueble a medida con OF y exceso aprobado;
9. portal y Gantt con ruta crítica e IA simulada.

En la primera corrida, 5 casos de ingresos fallaron. La causa fue externa: otro bloque dejó en la compañía una cuenta bancaria sin verificar, y Odoo 20 no publica facturas con ella. Se repitieron en `fase_proyectos_ingreso.py` y pasaron. El anexo muestra el resultado de la repetición.

### 5.6 Planillas y herramientas

Se calcularon con datos reales, de julio de 2025 a octubre de 2026:
- planillas de trabajadores AFP, ONP y con sueldo menor a la RMV;
- gratificaciones, CTS, vacaciones, renta de 5.ª y liquidación;
- turnos, tardanzas y horas extra 25 %/35 %;
- construcción civil (BUC, movilidad, CONAFOVICER);
- asiento de planilla;
- boleta PDF, PLAME, AFPnet y TXT de haberes BCP;
- importación desde Excel.

Se confirmaron los parámetros migrados:
- **UIT:** 5 150 / 5 350 / 5 500. Si falta la del año, el mensaje es claro.
- **RMV:** 1 025 → 1 130 → 1 230 desde el 01/10/2026. Una RMV con fecha futura solo afecta a las planillas posteriores.
- **EsSalud:** max(base, RMV) × 9 %.

También se validaron:
- **Herramientas:** ayuda contextual, ficha de módulos, `queue_job`.
- **Servidor MCP:** un usuario sin permisos no lee nóminas ni crea registros.

---

## 6. Defectos encontrados y corregidos

| # | Módulo | Síntoma | Causa | Corrección | Test nuevo |
|---|---|---|---|---|---|
| 1 | `al_pos_network_printer` | **El TPV no carga** con la impresora ESC/POS activa: «Cannot read properties of undefined (reading 'id')» en `EscposNetworkPrinter.setup` | En Odoo 20 la impresión es un plugin (`PosTicketPrinterPlugin`) con impresoras `pos.printer` de recibo y de preparación; ya no existen `hardwareProxy.printer` ni `PosStore.createPrinter`, y `BasePrinter.setup` espera `{printer}` | La ESC/POS de la caja se sincroniza como impresora de recibo (`pos.printer` `escpos_network`, `use_type=receipt`), con migración `20.0.6.20261030`. La instancia se crea en `createPrinterInstance`. Al desactivarla se elimina, para que su IP salga de la lista blanca. La verificación del agente lee las impresoras del plugin | `test_receipt_printer_v20.py` (sincronización, lista blanca y **tour de arranque del TPV**) |
| 2 | `al_pos_payment_gateway` | Crear el método del TPV desde Niubiz, Culqi o Izipay: `TypeError: use BinaryValue instead of bytes` | Odoo 20 no acepta bytes en base64 en campos binarios | `_al_pos_payment_logo()` devuelve `BinaryBytes` | `test_pos_card_of_peruvian_gateways` ahora crea el método |
| 3 | `al_hr_pe` | Cese o ingreso a mitad de mes: se pagan como descanso (DOM) los fines de semana fuera del contrato. Con el cese del 10/07, básico de 1 280 en lugar de 800 y CTS/vacaciones truncas de más | El complemento DOM usaba todos los días del periodo; el motor nativo solo marca «fuera de contrato» (000.00) los días hábiles | El periodo se acota a las fechas del contrato y las líneas 000.00 no cuentan | `test_dom_bounded_to_contract_on_termination` |
| 4 | `al_hr_pe_public_holidays` | Al aplicar los feriados del catálogo a los calendarios, la boleta revienta (`NotNullViolation` en `work_entry_type_id`) | Los 170 feriados 2026-2035 se cargaron sin concepto: el DOM de `al_hr_pe` es una dependencia blanda | Al aplicar se usa el concepto por defecto y nunca se escribe un tipo vacío. La migración `20.0.12.20261030` completa los feriados existentes | `test_holiday_without_concept_gets_a_type_on_apply` |
| 5 | `al_l10n_pe_prescriber_cmp` | El químico farmacéutico no puede marcar el CMP como verificado (AccessError) | En 20, editar contactos exige «Contactos: creación» | Escritura con `sudo()` después de validar el grupo Q.F. | `test_pharmacist_without_contact_rights_records_verification` |
| 6 | `al_account_base` | El `clearing_number` nativo acepta códigos SUNAT inválidos («AB») que luego salen en el PLE 1.2 | La validación estaba sobre el campo *related*, que no se dispara al escribir el nativo | Validación sobre `clearing_number`, solo en cuentas peruanas | `test_native_clearing_number_is_validated`, `test_foreign_clearing_number_not_validated` |
| 7 | `al_l10n_pe_retention` | La serie del CRE es `RRR1-` y no `R001-` en bases donde el nativo creó la secuencia primero | El hook solo fijaba la serie al crear el impuesto | Hook y migración `20.0.26.20261030` ponen `R001-` mientras no se haya emitido ningún CRE | `TestRetentionSequencePrefix` |
| 8 | `al_l10n_pe_ple` | En el PLE 5.1 y 6.1 nativos, la glosa es el número del asiento y no la descripción de la operación | `l10n_pe_reports` usa `move_name`; la glosa de `al_account_base` solo llegaba al libro propio | Se hereda `_l10n_pe_get_txt_data` y se pone la glosa del asiento cuando existe | `TestNativeGloss` |

Además se corrigieron 13 llamadas a `union(*registros)` (aviso «Since 20.0, use union() with only one iterable») en `al_construction_planner*` y `al_pharmacy_replenishment`.

**Pendiente de aplicar en `ce20_db_ol`:** las correcciones están en el código y probadas en el clon. Para que las tome la base de trabajo hay que reiniciar el servidor actualizando los módulos (§8).

---

## 7. Pruebas unitarias de los módulos corregidos (clon `ce20_db_ol_qa`)

Se corrieron con `-u <módulo> --test-enable` sobre un clon restaurado del respaldo, sin detener el servidor de trabajo.

| Módulo | Tests | Resultado |
|---|---:|---|
| `al_pos_network_printer` | 40 | ✅ |
| `al_pos_payment_gateway` | 11 | ✅ |
| `al_hr_pe` | 137 | ✅ |
| `al_hr_pe_public_holidays` | 23 | ✅ |
| `al_l10n_pe_retention` | 67 | ✅ |
| `al_account_base` | 17 | ✅ |
| `al_l10n_pe_prescriber_cmp` | 6 | ✅ |
| `al_l10n_pe_ple` | 122 | ✅ |
| `al_pharmacy_replenishment` | 11 | ✅ |
| `al_construction_planner` | 36 | ✅ |
| `al_construction_planner_subcontract` | 27 | ✅ |
| `al_construction_planner_sale` | 2 | ✅ |
| `al_construction_planner_suite` | 444 | 10 ❌ · 4 errores, **todos previos** (la línea base del 29/10 tenía 11 y 6; no hay ninguno nuevo y 3 se resolvieron) |

**Contraprueba del tour del TPV.** Se restauró temporalmente el JS anterior de `al_pos_network_printer` y el tour falló con el mismo error visto en el navegador («Cannot read properties of undefined (reading 'id')»). Con el JS nuevo, el tour pasa. Así queda comprobado que el test protege contra este defecto.

**Test ajustado:** `al_construction_planner` · `test_legacy_sites_without_company` suponía compañías sin plantilla de niveles. Desde el 29/10 la compañía 1 tiene la plantilla «Edificio», así que el test ahora lo deja explícito. No era un defecto del código.

Commits locales de las correcciones (rama `20.0`, sin push): `7289d394`, `8eac3784`, `3c1a512e`, `cdcfef9e`, `39e96ddf`, `a3360c56`, `26d6ae62`, `d3b0a1ff` y `cf96a601`.

---

## 8. Avisos, omisiones y datos que quedan en la base

### 8.1 Avisos (no son defectos del código)

- **`al_sale_approval`** aprueba por **producto marcado** y usa `approvals`, no un límite de importe con *tier validation*. La ruta funcional lo describía distinto; hay que corregir la ruta.
- **Cajero con lotes:** necesita el grupo *Inventario / Usuario* (nativo de Odoo 20).
- **Cuentas bancarias no verificadas:** Odoo 20 no deja publicar comprobantes a usuarios normales si la cuenta por defecto de la compañía no es de confianza. En la base quedaron dos cuentas de prueba así: res.partner.bank 171 «QA20 P1 BCP» y 179. Hay que marcarlas de confianza o archivarlas.
- **Configuración vacía completada** para poder probar, solo donde estaba vacía:
  - Contabilidad: socio de Aduanas y cuenta puente de la DUA.
  - Nómina: Parámetros Principales, cuentas de reglas y AFP, diario nativo retirado de la estructura BASE, `format_bank = bcp` en el BCP.
  - Proyectos: `construction_income_calendar_id`.
- **Scripts demo** de `al_construction_planner_suite/tools/` (no son código del módulo): usan campos de 19 (`stage_production`…) y la búsqueda de módulos por nivel directo.

### 8.2 Omitido

- **Envíos reales**, sin credenciales de prueba y sin red: SUNAT, OSE HKA, IAP, GRE, SIRE, RENIEC, BCRP, Banco de la Nación, CAVALI, DIGEMID, CMP y las pasarelas. Se validó lo que se genera y se simuló la respuesta.
- **Pantallas OWL** que no se abrieron en el navegador: TPV con receta, hoja de cálculo, quiosco de obra y página web del Gantt. Se validaron los métodos que llaman.
- **Reinstalación de los paquetes `al_industry_*`** y cierre del ejercicio (afectaría los saldos de todos los bloques).

### 8.3 Datos que quedan en `ce20_db_ol`

- Registros `QA20` de todos los bloques. Se buscan por nombre; las referencias exactas están en el anexo.
- Usuarios de prueba: `qa20_admin`, `qa20_obra`, `qa20_aprobador` y los cajeros, Q.F. y técnicos de cada bloque.
- Compañías 1043 y 1044 (cierre de tipo de cambio y revaluación).
- Duplicados de un intento fallido de planillas: res.partner 9451 y queue.job 58 (se pueden borrar).
- La caja «QA20 TPV CPE» tiene la ESC/POS activa (IP de documentación 203.0.113.x). Hasta actualizar `al_pos_network_printer`, esa caja no abre en el TPV.

Para aplicar las correcciones en la base de trabajo, con el servidor detenido:

```bash
cd /home/och/odoo/ce20
./.venv/bin/python odoo-bin -c cfg/ol_odoo.cfg -d ce20_db_ol --stop-after-init -u \
  al_pos_network_printer,al_pos_payment_gateway,al_hr_pe,al_hr_pe_public_holidays,\
al_l10n_pe_prescriber_cmp,al_account_base,al_l10n_pe_retention,al_l10n_pe_ple,\
al_pharmacy_replenishment,al_construction_planner_suite
```

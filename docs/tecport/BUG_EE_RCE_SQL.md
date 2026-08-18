# Bug en Odoo Enterprise 19 — los reportes RCE/RVIE fallan con error SQL

**Detectado:** 15/08/2026, base `ol_pe_v19` (Odoo 19.0, `l10n_pe_reports` 19.0.1.0).
**Alcance:** los tres reportes de la localización peruana que emiten los registros del SIRE.

---

## Síntoma

Los tres reportes fallan **tanto en pantalla como al exportar**:

| Reporte | Handler | Formato que emite | Estado |
|---|---|---|---|
| RCE Registro de Compras 8.4 | `l10n_pe.tax.ple.8.1.report.handler` | `08040002` | ❌ `UndefinedTable` |
| RCE Registro de Compras no Domiciliados 8.5 | `l10n_pe.tax.ple.8.2.report.handler` | `08050000` | ❌ `UndefinedTable` |
| RVIE Registro de Ventas 14.4 | `l10n_pe.tax.ple.14.1.report.handler` | — | ❌ `UndefinedTable` |

```
psycopg2.errors.UndefinedTable: missing FROM-clause entry for table
"account_move_line__move_id__partner_id"
```

Al eliminar esa condición del dominio, el error se desplaza al siguiente alias
(`account_move_line__tax_line_id`), lo que confirma que no es un caso aislado.

---

## Causa

`l10n_pe_reports/models/account_ple_reports.py`, método `_get_ple_report_data()`, construye
la consulta **a mano**: un `SELECT … FROM account_move_line LEFT JOIN …` con los JOIN escritos
literalmente, y luego inyecta solo el `WHERE` que genera el ORM:

```python
search_condition=query.where_clause,
```

El dominio del reporte contiene rutas de varios niveles que el ORM resuelve **con JOIN**, no con
subconsulta:

```
('tax_line_id.tax_exigibility', '!=', 'on_payment')
('move_id.fiscal_position_id.foreign_vat', '=', False)
('move_id.partner_id.country_id.code', '=', 'PE')      ← añadida por _custom_options_initializer
```

El ORM genera para ellas los alias `account_move_line__tax_line_id`,
`account_move_line__move_id__fiscal_position_id` y `account_move_line__move_id__partner_id`,
que **no existen en el FROM escrito a mano** — allí las mismas tablas están unidas con otros
alias (`rp`, `rpc`, …). El resultado es SQL inválido.

Es el mismo antipatrón que este proyecto ya identificó en `tecport/l10n_pe`: **acoplar SQL crudo a
los alias que genera el query builder del ORM**. Ver la sección 3.2.3 del
[análisis](ANALISIS_Y_PLAN_TECPORT_L10N_PE.md).

Las condiciones que el ORM resuelve con `EXISTS` (las de campos x2many, como
`tax_ids.tax_exigibility`) sí funcionan; las de many2one directo son las que rompen.

---

## Por qué no lo detectan los tests

En una base recién creada por `AccountTestInvoicingCommon` la consulta puede resolverse sin esos
JOIN, según qué condiciones acabe incluyendo el dominio. Los tests de esta suite
(`test_rce_84_export.py`) pasan en verde y aun así el reporte falla en la base real: **es un caso
en el que el test no cubre el camino de producción**, y conviene tenerlo presente al confiar en él.

---

## Consecuencia para la Fase 3

La vía elegida —extender el handler de Enterprise reutilizando su motor de consulta— **no es
viable mientras el motor esté roto**. El generador del 8.4 ya escrito
(`al_l10n_pe_ple/models/rce_report.py`) es correcto en cuanto a estructura, pero se apoya en
`_get_ple_report_data()` para obtener los datos.

Opciones:

1. **Extractor propio con el ORM** — obtener los comprobantes y sumar las bases por grupo de
   impuesto con `search` / `_read_group`, sin SQL crudo. Robusto y bajo nuestro control; deja el
   reporte de EE como está y usa su ficha de `account.report` solo para la interfaz.
2. **Parchear el método de EE** — sobreescribir `_get_ple_report_data()` completo corrigiendo los
   JOIN. Arregla los tres reportes de golpe, pero nos ata a mantener una copia de su SQL.
3. **Esperar a Odoo** — reportar el fallo y no entregar el RCE hasta que se corrija.

La opción 1 es la que sigue la línea del plan (nada de SQL crudo acoplado a alias del ORM) y la
única que no depende de código ajeno defectuoso.

---

## Resolución adoptada

**Opción 1.** La extracción se reescribió con el ORM en
`al_l10n_pe_ple/models/rce_extractor.py`, y los tres handlers sobreescriben `export_to_txt`:

| Formato | Handler heredado | Módulo |
|---|---|---|
| RCE 8.4 | `l10n_pe.tax.ple.8.1.report.handler` | `models/rce_report.py` |
| RCE 8.5 | `l10n_pe.tax.ple.8.2.report.handler` | `models/rce_report.py` |
| RVIE 14.4 | `l10n_pe.tax.ple.14.1.report.handler` | `models/rvie_report.py` |

Se conserva la ficha de `account.report` de Enterprise, de modo que el usuario sigue viendo los
mismos informes en el mismo sitio; lo único que cambia es de dónde salen los datos. **La
exportación de los tres formatos funciona en la base donde antes fallaba.**

El reporte **en pantalla** sigue usando el motor de Enterprise y, por tanto, sigue fallando:
solo se ha corregido la exportación a TXT, que es la que tiene valor legal. Corregir también la
vista exigiría reemplazar `_get_ple_report_data()` completo (opción 2).

# PE - Costeo de órdenes de fabricación

Documentación funcional: [Costeo de órdenes de fabricación](../../mkdocs/content/applications/inventory_and_mrp/mrp/production_costing.md)

## Modelos

- `l10n_pe.mrp.labor.rate` (+ `.line`): costo hora por empleado y periodo
  desde las boletas (`hr.payslip` validadas o pagadas): categorías `ING` −
  `DES_AFE` + `APOR_EMP`, más las provisiones de `hr.provisiones` del lote si
  `al_hr_pe_benefits` está instalado, entre las horas de los días laborados
  (`hr.main.parameter.wd_dlab`). «Aplicar» escribe `hr.employee.hourly_cost`
  (`hr_hourly_cost`), que `mrp_workorder` usa en `employee_cost` de cada
  registro de tiempo.
- `l10n_pe.mrp.cost.pool`: bolsa de CIF (prefijos de cuenta, centros de costo
  con su porcentaje, base de reparto, centros de producción, contrapartida).
- `l10n_pe.mrp.cost.close` (+ `.line`): cierre del mes. Ajuste de mano de obra
  por registro de tiempo y reparto de las bolsas; al validar crea un
  `stock.landed.cost` de fabricación (`mrp_landed_costs`), escribe el importe
  de cada línea de valoración según el reparto del cierre (Odoo no reparte por
  horas) y lo valida.
- `l10n_pe.mrp.cost.analysis`: vista SQL de costo por elemento.
- `l10n_pe.mrp.timesheet.import`: tareo desde Excel (todo o nada).

## Pruebas

`tests/test_mrp_cost.py`: cierre con ajuste de mano de obra y CIF (asiento
contra la 71), reparto por cantidad, aviso sin costo hora, análisis por
elemento, importación del tareo y costo hora desde una boleta real.

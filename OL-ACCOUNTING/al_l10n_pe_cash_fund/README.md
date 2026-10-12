# PE - Entregas a rendir y caja chica (AL)

Documentación funcional: [Entregas a rendir y caja chica](../../mkdocs/content/applications/finance/accounting/cash_fund.md)

Módulo `al_l10n_pe_cash_fund`. Dinero entregado a un trabajador para gastos de
la empresa (entregas a rendir) y fondos fijos (caja chica): entrega, rendición
con facturas de proveedor y planilla de movilidad, devolución, reembolso,
reposición y cierre.

Menú *Perú ▸ Tesorería ▸ Entregas a rendir* (*Fondos*, *Rendiciones*, *Gastos de
movilidad*), también en *Contabilidad ▸ Proveedores*. Ajustes en *Ajustes ▸
Perú ▸ Tesorería ▸ Entregas a rendir ▸ Entregas a rendir y caja chica*.

## Modelos

| Modelo | Qué es |
|---|---|
| `l10n_pe.cash.fund` | Fondo: entrega a rendir (ER/año/…) o caja chica (CCH/…), con su responsable, cuenta y saldo |
| `l10n_pe.cash.settlement` | Rendición (REN/año/…) con su asiento; planilla de movilidad PM/año/… |
| `l10n_pe.cash.settlement.document` | Factura de proveedor pagada con el fondo (total o parcial) |
| `l10n_pe.cash.settlement.mobility` | Desplazamiento de la planilla de movilidad (con analítica) |

`account.payment` recibe el fondo y el tipo de movimiento (entrega, reposición,
reembolso, devolución); al confirmarlo se concilia la cuenta del fondo.

## Asientos

| Paso | Debe | Haber |
|---|---|---|
| Entregar / reponer / reembolsar | 1413 (responsable) | Banco |
| Rendición: facturas | 42 (proveedor; concilia la factura) | 1413 |
| Rendición: movilidad | 63112 (o la de Ajustes) | 1413 |
| Devolución | Banco | 1413 |

La cuenta del fondo debe ser conciliable: por defecto la 1413 del PCGE. Para la
caja chica, la 102 «Fondos fijos» es de efectivo y no se concilia: use una
subcuenta conciliable de la 1413 o la 1691.

## Planilla de movilidad

Art. 37 inciso a1) del TUO de la Ley del Impuesto a la Renta y art. 21 inciso v)
de su Reglamento: tope por trabajador y por día del 4 % de la RMV (RMV y
porcentaje configurables; S/ 1 130 por el D.S. 006-2024-TR). La rendición avisa
el exceso no deducible y la planilla impresa lleva número, empresa, periodo,
fecha de emisión, trabajador y documento, fecha, motivo, destino y monto de cada
desplazamiento, y la firma del trabajador.

## Seguridad

Facturación (`account.group_account_invoice`) crea fondos y rendiciones;
contabilidad (`account.group_account_user`) aprueba, entrega, repone y cierra.
Reglas multicompañía en los cuatro modelos.

## Pruebas

`tests/test_cash_fund.py`: entrega, rendición, devolución y cierre; reembolso;
reposición de caja chica; rendición parcial, anulación y nueva confirmación con
el mismo número; validaciones de comprobantes; cuentas por defecto del PCGE.

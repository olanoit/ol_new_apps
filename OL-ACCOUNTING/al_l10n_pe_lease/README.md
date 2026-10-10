# PE - Arrendamientos NIIF 16 (AL)

Guía funcional: [GUIA_FUNCIONAL.md](GUIA_FUNCIONAL.md)

Módulo `al_l10n_pe_lease`. Alquileres de oficinas, almacenes y equipos como
**arrendatario** según NIIF 16, sobre los motores de Odoo Enterprise de activos
fijos (`account_asset`) y préstamos (`account_loans`).

## Cómo funciona

1. **Perú ▸ Arrendamientos ▸ Contratos ▸ Nuevo**: arrendador, bien, inicio,
   plazo, cuota mensual sin IGV, pago al inicio o al final del mes, tasa
   incremental de endeudamiento, costos directos e incentivos.
2. **Calcular**: valor presente y tabla del pasivo.
3. **Confirmar**:
   - asiento inicial: derecho de uso contra pasivo (y la transitoria);
   - **activo** (`account.asset`) con el débito del derecho de uso,
     depreciación lineal mensual en el plazo;
   - **pasivo** (`account.loan`) con la tabla calculada: cada cuota publica
     interés y capital en su fecha y reclasifica el corto plazo;
   - activo y préstamo enlazados por un grupo de activos.
4. **Registrar cuota**: factura del arrendador de la siguiente cuota, en
   borrador, contra el pasivo de corto plazo (la primera adelantada contra la
   transitoria). Con **Producto de la cuota** (servicio de alquiler) la factura
   toma sus impuestos (IGV) y su tipo de detracción.
5. **Remedir** (cambio de cuota, plazo o tasa desde el primer día de un mes):
   el pasivo se recalcula con las cuotas que faltan; la diferencia aumenta el
   derecho de uso («Reevaluar» del activo, contra el pasivo) o lo disminuye
   (contra el pasivo; el exceso sobre su valor en libros va a resultados). El
   préstamo anterior se cierra y uno nuevo lleva la tabla remedida.
6. **Terminación anticipada**: baja del derecho de uso a su valor en libros
   (cuenta de pérdida de activos) y del pasivo pendiente (cuenta de ganancia);
   el préstamo se cierra y el contrato queda «Terminado».
7. **Moneda extranjera**: el derecho de uso queda al tipo de cambio del
   inicio (NIC 21, no monetario); el pasivo se ajusta por **Diferencia de
   cambio** (cron de fin de mes y botón), sobre las cuentas del pasivo.
8. **Diferencias temporales** (Perú ▸ Arrendamientos): por ejercicio,
   depreciación + interés frente al alquiler de las facturas del arrendador,
   con el impuesto diferido (el derecho de uso no se deprecia tributariamente,
   Informe N.° 054-2021-SUNAT/7T0000).

Cada contrato muestra **Saldos a hoy**: pasivo según la tabla (capital
pendiente + cuotas devengadas sin factura), pasivo en el libro (cuentas del
pasivo en sus asientos) y la diferencia (cero en soles; en moneda extranjera,
la diferencia de cambio aún no registrada), y el **Historial** de
remediciones, terminación y diferencias de cambio.

**Exenciones**: con 12 meses o menos el contrato se marca «Corto plazo»; «Activo
de bajo valor» se elige a mano. Exento, no hay activo ni pasivo y las cuotas van
a gasto de alquiler.

## Cálculo

- Tasa mensual equivalente: `(1 + tasa anual) ^ (1/12) − 1`.
- Pasivo = valor presente de las cuotas no pagadas al inicio:
  `cuota × (1 − (1 + r)^−n) / r`, con `n` = plazo (pago vencido) o plazo − 1
  (pago adelantado: la primera cuota se paga al firmar y va al activo).
- Derecho de uso = pasivo + cuota adelantada + costos directos − incentivos.
- Tabla por el método del interés efectivo: interés = saldo × r (redondeado),
  capital = cuota − interés; la última cuota cierra el saldo.

Ejemplo de los tests (verificado a mano): dos cuotas vencidas de 1 000 al 1 %
mensual → pasivo 990,10 + 980,30 = 1 970,40; cuota 1: interés 19,70, capital
980,30; cuota 2: capital 990,10, interés 9,90.

## Asientos (oficina de la demostración)

36 meses, cuota adelantada 4 500, tasa 12 %, costos directos 1 200: pasivo
133 483,38 (35 cuotas) y derecho de uso 139 183,38.

| Momento | Debe | Haber |
|---|---|---|
| Reconocimiento inicial | 32331 Derecho de uso 139 183,38 | 452 Pasivo 133 483,38 · 183 Transitoria 5 700,00 |
| Cuota 2 (préstamo, 31/08) | 452 capital 3 233,40 · 6732 interés 1 266,60 | 452 cuota 4 500,00 |
| Factura del arrendador cuota 2 | 452 4 500,00 · IGV 810,00 | Proveedor 5 310,00 |
| Factura de la cuota 1 y de los costos | 183 | Proveedor |
| Depreciación mensual (activo) | 683111 | 39412 |
| Remedición al alza (depósito, +7 858,79) | 32331 | 4521 |
| Remedición a la baja | 4521 (y 683 → 4521, reclasificación) | 39412 |
| Terminación anticipada | 39412 + pérdida (valor en libros) · 4521 pasivo | 32331 · ganancia |
| Diferencia de cambio (local en USD, 30/09) | 4521 1 112,21 | 776 1 112,21 |

## Decisiones

- **Sin motores propios**: el pasivo usa `account.loan` cargándole la tabla
  calculada (sus líneas admiten capital e interés propios) en vez de su
  asistente, que calcula cuota francesa con otra convención de fechas; así el
  préstamo cuadra con el valor presente del contrato.
- **Cuenta transitoria 183** (alquileres pagados por anticipado): la
  primera cuota adelantada y los costos directos llegan como facturas; una
  cuenta por pagar (4699) no se admite en líneas de factura.
- **Subcuentas del pasivo**: el plan de Odoo solo trae la 452; «Crear
  subcuentas del pasivo» crea 4521 (largo) y 4522 (corto) con la longitud de
  los códigos del plan, y las propone en los contratos nuevos.
- **Moneda extranjera**: `account.loan` solo admite la moneda de la compañía;
  el préstamo lleva la tabla convertida al tipo de cambio de su fecha y la
  diferencia con el saldo en dólares se ajusta aparte. La cuenta del pasivo no
  necesita moneda propia.
- **Disminución del derecho de uso**: Odoo mide el valor del activo por la
  línea de gasto del asiento de disminución, así que se registra nativa y se
  reclasifica ese gasto al pasivo (efecto neto: pasivo contra derecho de uso).
- **Remedición y terminación rigen desde el primer día de un mes** sin
  asientos del préstamo ni del activo contabilizados desde esa fecha (se
  rehacen desde ahí).

## Límites y pendientes

- La **garantía entregada** es informativa: se registra aparte (p. ej. con el
  módulo de depósitos en garantía).
- **Pagos variables** (por ventas, consumo, mantenimiento) y la **opción de
  compra** no se modelan: los variables se facturan aparte a gasto; una opción
  de compra que se vuelve razonablemente cierta se registra con «Remedir».
- Remedición de contratos **en moneda extranjera**: soportada, pero el
  préstamo nuevo va al tipo de cambio de la fecha; revise la diferencia de
  cambio del mes.
- El reporte de diferencias temporales toma como gasto deducible las facturas
  del arrendador del ejercicio; no calcula el impuesto diferido acumulado ni
  genera su asiento (lo registra el contador con el resultado).
- La factura del arrendador queda en borrador: complete el número de
  documento del proveedor antes de confirmarla.

## Pruebas

`tests/test_lease.py` (7): valor presente verificado a mano, cuota adelantada
fuera del pasivo, confirmación (asiento inicial, activo y préstamo con totales
cuadrados y enlazados), facturas de cuotas, contrato exento por corto plazo,
tasa obligatoria y multicompañía.

`tests/test_lease_lifecycle.py` (9): subcuentas y reclasificación, libro
igual a la tabla tras 10 cuotas, producto de la cuota (impuestos y cuenta),
remedición al alza y a la baja (activo, préstamo, tabla, historial, sin paso
por resultados), fechas no válidas, terminación anticipada (ganancia y
pérdida), moneda extranjera (tipo de cambio del inicio, ajuste idempotente) y
diferencias temporales.

Demostración: `tools/lease_demo_data.py` (prefijo DEMO NIIF16).

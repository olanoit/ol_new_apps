# PE - Arrendamientos NIIF 16 (AL)

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
   transitoria). IGV y detracción como cualquier factura.

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

## Decisiones

- **Sin motores propios**: el pasivo usa `account.loan` cargándole la tabla
  calculada (sus líneas admiten capital e interés propios) en vez de su
  asistente, que calcula cuota francesa con otra convención de fechas; así el
  préstamo cuadra con el valor presente del contrato.
- **Cuenta transitoria 183** (alquileres pagados por anticipado): la
  primera cuota adelantada y los costos directos llegan como facturas; una
  cuenta por pagar (4699) no se admite en líneas de factura.
- **Pasivo 452** para largo y corto plazo por defecto (el PCGE no separa);
  conviene crear subcuentas 4521/4522 y elegirlas en el contrato.
- **Moneda**: la de la compañía (la de `account.loan`).

## Límites y pendientes

- **Remedición** (cambio de cuota, plazo o tasa) no está automatizada:
  termine el contrato y registre uno nuevo con el saldo; el ajuste del activo
  se hace con «Modificar» del activo.
- La **garantía entregada** es informativa: se registra aparte (p. ej. con el
  módulo de depósitos en garantía).
- Contratos en moneda extranjera: no soportados (el préstamo de Odoo usa la
  moneda de la compañía).
- La factura del arrendador queda en borrador: complete el número de
  documento del proveedor antes de confirmarla.

## Pruebas

`tests/test_lease.py` (7): valor presente verificado a mano, cuota adelantada
fuera del pasivo, confirmación (asiento inicial, activo y préstamo con totales
cuadrados y enlazados), facturas de cuotas, contrato exento por corto plazo,
tasa obligatoria y multicompañía.

Demostración: `tools/lease_demo_data.py` (prefijo DEMO NIIF16).

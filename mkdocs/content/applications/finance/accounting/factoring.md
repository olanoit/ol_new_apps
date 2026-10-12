---
modulos: [al_l10n_pe_factoring]
---

# Factoring

Una empresa que vende al crédito (30, 60 o 90 días) necesita liquidez antes de
que el cliente pague. Con el **factoring** cede esas facturas a un banco o a
una empresa de factoring, el **factor**, que le adelanta la mayor parte del
importe y cobra la factura al vencimiento. El módulo **Factoring de facturas**
(`al_l10n_pe_factoring`) registra la operación con el factor sobre las facturas
de cliente ya emitidas, sin duplicarlas, y genera los asientos de cada momento
(cesión, desembolso, intereses, cobro, recompra o pérdida) con las cuentas del
PCGE. Lo usan tesorería y contabilidad.

Quedan fuera la comunicación con CAVALI (Factrack) y con la plataforma de
conformidad de SUNAT, de las que se registran los datos que devuelven; la
factura negociable impresa (tercera copia física), y los desembolsos parciales
del factor dentro de una misma operación: se usa una operación por tramo.

## Configuración

1. Vaya a **Perú ‣ Configuración ‣ Cuentas de la localización ‣ Factoring**.
   Las cuentas se crean solas con el PCGE por modalidad (1214, 4512, 6734,
   3731, 6391 y 6741). Ajústelas al plan de la empresa y agregue filas por
   moneda si usa cuentas distintas en dólares.
2. Prepare un diario de tipo **Varios** para la cesión y el devengo, y el
   diario del banco donde abona el factor.
3. Cree el factor como contacto (empresa con RUC). Si cobra comisiones
   facturadas, registre su factura de proveedor antes del desembolso.
4. Use términos de pago con vencimiento en las facturas: la factura negociable
   nace de una venta al crédito.
5. Asigne los permisos: facturación (crear y operar), administrador contable
   (cuentas) y solo lectura (auditor).
6. Revise las cuentas de ganancia y pérdida por diferencia de cambio en los
   ajustes de Contabilidad.

## Conceptos

| Término | Significado | En Odoo |
|---|---|---|
| Factor | Banco o empresa que compra las facturas | Operación ‣ **Factor** |
| Sin recurso | El factor asume el riesgo de impago: la factura se da de baja | Operación ‣ **Modalidad** |
| Con recurso | Si el cliente no paga, la empresa devuelve el adelanto: la factura **no** se da de baja y el adelanto es una deuda | Operación ‣ **Modalidad** |
| Valor nominal | Monto neto pendiente de pago que se cede | Línea ‣ **Valor nominal** |
| Adelanto | Parte del nominal que el factor paga al inicio, por ejemplo el 90 % | Línea ‣ **% de adelanto** |
| Retenido | Resto del nominal; el factor lo paga cuando el cliente cancela | Línea ‣ **Retenido** |
| Conformidad | Aceptación de la factura por el cliente, expresa o presunta | Línea ‣ **Conformidad** |
| Anotación en cuenta | Registro de la factura negociable en CAVALI | Línea ‣ **Anotación CAVALI** |
| Recompra | Con recurso: la empresa devuelve el adelanto porque el cliente no pagó | Operación ‣ **Recompra** |

La **Ley 29623** crea la **factura negociable**, un título valor que incorpora
el derecho de cobro del saldo de la factura. El **D.U. 013-2020** exige que la
factura electrónica al crédito informe el **plazo de pago** y el **monto neto
pendiente de pago**, y regula la **conformidad**: el cliente tiene **8 días
calendario** para dar su conformidad o disconformidad y, si no se pronuncia, se
**presume conforme** (art. 7). La factura puede transferirse desde su
**anotación en cuenta** en CAVALI. Según la **R.S. 193-2020/SUNAT**, el monto
neto pendiente **excluye** la detracción y la retención del IGV (3 % de las
facturas de más de S/ 700 de un cliente agente de retención, R.S.
037-2002/SUNAT). El valor nominal propuesto usa la misma regla que el
[comprobante impreso](../fiscal_localizations/peru/electronic_invoicing/invoice_report.md#cliente-agente-de-retención):
entre agentes de retención no se retiene.

La cesión de créditos no es una venta gravada: no se emite comprobante por la
cesión. Los intereses y las comisiones del factor siguen las reglas de los
servicios financieros. La **NIIF 9** decide si la cuenta por cobrar se da de
baja según quién asume el riesgo.

```mermaid
flowchart TD
    A["Factura de cliente al crédito<br/>publicada y enviada a SUNAT"] --> B["Conformidad del cliente<br/>expresa o presunta a los 8 días"]
    B --> C["Anotación en CAVALI<br/>número y fecha"]
    C --> D["Operación de factoring en borrador<br/>factor, modalidad, % de adelanto"]
    D --> E{"¿Disconformidad?"}
    E -- Sí --> X["No se cede: subsanar con<br/>nota de crédito o débito"]
    E -- No --> F{"¿Modalidad?"}
    F -- Sin recurso --> G["Ceder: 1212 a 1214 del factor<br/>la factura queda pagada"]
    F -- Con recurso --> H["Ceder: sin asiento<br/>la factura sigue pendiente"]
    G --> I["Desembolso: banco neto,<br/>intereses, comisión y gastos"]
    H --> I
    I --> J{"¿El cliente paga al factor?"}
    J -- "Sí, todo o una parte" --> K["Cobro del factor: cubre el adelanto<br/>y libera el retenido"]
    J -- "No, con recurso" --> L["Recompra: devolver el adelanto<br/>la factura sigue pendiente"]
    J -- "No, sin recurso" --> M["Pérdida del retenido (6741)"]
    K --> N["Liquidada"]
    L --> O["Recomprada"]
    M --> N
```

## Crear la operación

1. Emita la factura al crédito en **Contabilidad ‣ Clientes ‣ Facturas**: el
   comprobante electrónico informa el monto neto pendiente.
2. Seleccione las facturas y vaya a **Acciones ‣ Ceder a factoring**, o cree la
   operación en **Perú ‣ Factoring ‣ Operaciones**. La operación queda en
   **Borrador** con el valor nominal propuesto, que se puede editar para ceder
   solo una parte (sin superar el saldo pendiente).
3. Elija el factor, la **Modalidad** que dice el contrato y el **% de
   adelanto**. Si el factor puede exigir la devolución cuando el cliente no
   paga, la modalidad es **con recurso**.
4. En **Facturas**, registre la **Conformidad** y la **Anotación CAVALI**
   (número y fecha).

![Operación de factoring en borrador con sus facturas](factoring/draft-operation.png)

!!! warning "Importante"
    Una factura con disconformidad no se puede ceder: subsánela con una nota de
    crédito o débito, o con un nuevo comprobante, y registre la conformidad.
    Una factura tampoco se puede ceder dos veces, salvo que la operación
    anterior se haya cancelado o recomprado.

### Ejemplo

Constructora SAC emite el **01/10/2026** la factura F001-125 a Inmobiliaria del
Sur SAC por **S/ 10 000 + IGV 1 800 = S/ 11 800**, al crédito con vencimiento el
**30/11/2026**. El cliente es **agente de retención**. El 10/10/2026 la cede a
Factor Capital SA con un **adelanto del 90 %**; el factor cobra **intereses de
S/ 180**, una **comisión facturada de S/ 118** (S/ 100 + IGV 18) y **gastos de
S/ 20**:

- monto neto pendiente = 11 800 − retención 3 % (354,00) = **S/ 11 446,00**,
  que es el valor nominal propuesto (la retención la sustenta el cliente con su
  comprobante de retención);
- adelanto = 11 446,00 × 90 % = **S/ 10 301,40**; retenido = **S/ 1 144,60**;
- neto en el banco = 10 301,40 − 180 − 118 − 20 = **S/ 9 983,40**;
- conformidad presunta: 01/10/2026 + 8 días = **09/10/2026**, antes de ceder.

La comisión del factor se registra como factura de proveedor:

| Cuenta | Descripción | Debe | Haber |
|---|---|---|---|
| 6391 | Comisión de factoring | 100,00 | |
| 40111 | IGV crédito fiscal | 18,00 | |
| 4212 | Factor Capital SA (por pagar) | | 118,00 |
| | **Total** | **118,00** | **118,00** |

## Ceder y recibir el desembolso

1. Haga clic en **Ceder facturas**: la operación pasa a **Cedida**.
2. Al recibir el dinero, haga clic en **Registrar desembolso** e indique los
   intereses, la comisión y los gastos: la operación pasa a **Desembolsada**.
3. Con recurso, haga clic en **Devengar intereses** en cada periodo para
   llevar el gasto financiero.

### Sin recurso

La cesión da de baja la factura por el nominal:

| Cuenta | Descripción | Debe | Haber |
|---|---|---|---|
| 1214 | Facturas cedidas — Factor Capital SA | 11 446,00 | |
| 1212 | Facturas por cobrar — Inmobiliaria del Sur SAC | | 11 446,00 |
| | **Total** | **11 446,00** | **11 446,00** |

En el desembolso, la comisión facturada se paga con el descuento:

| Cuenta | Descripción | Debe | Haber |
|---|---|---|---|
| 1041 | Banco | 9 983,40 | |
| 6734 | Intereses por documentos descontados | 180,00 | |
| 4212 | Factura de la comisión (se concilia y queda pagada) | 118,00 | |
| 6391 | Gastos | 20,00 | |
| 1214 | Adelanto — Factor Capital SA | | 10 301,40 |
| | **Total** | **10 301,40** | **10 301,40** |

### Con recurso

La cesión no genera asiento: según la NIIF 9, el riesgo sigue en la empresa y
la factura sigue pendiente a nombre del cliente, marcada como **Cedida**. El
botón **Pagar** de la factura queda bloqueado, porque la cobra el factor. El
adelanto es una obligación y los intereses se difieren:

| Cuenta | Descripción | Debe | Haber |
|---|---|---|---|
| 1041 | Banco | 9 983,40 | |
| 3731 | Intereses por devengar | 180,00 | |
| 4212 | Factura de la comisión | 118,00 | |
| 6391 | Gastos | 20,00 | |
| 4512 | Obligación con Factor Capital SA | | 10 301,40 |
| | **Total** | **10 301,40** | **10 301,40** |

El devengo de octubre y noviembre, S/ 90 cada mes, es 6734 al debe y 3731 al
haber.

!!! note "Nota"
    Una operación se puede **Cancelar** solo antes del desembolso: la factura
    vuelve al cliente. Una operación cancelada puede **Volver a borrador**.

## Registrar el cobro del factor

Cuando el cliente paga al factor, haga clic en **Cobro del factor**, con una o
varias facturas y el importe cobrado: el cobro cubre primero el adelanto y luego
libera el retenido. La operación pasa a **Liquidada** cuando todo está cobrado.

![Asistente Cobro del factor con el importe cobrado por factura](factoring/factor-collection-wizard.png)

Sin recurso, si el cliente paga en dos partes:

1. Paga S/ 6 000: cubre parte del adelanto y no libera retenido, así que no
   hay asiento (quedan por cobrar S/ 5 446).
2. Paga S/ 5 446: S/ 4 301,40 completan el adelanto y **S/ 1 144,60** liberan
   el retenido:

| Cuenta | Descripción | Debe | Haber |
|---|---|---|---|
| 1041 | Banco | 1 144,60 | |
| 1214 | Retenido liberado — Factor Capital SA | | 1 144,60 |
| | **Total** | **1 144,60** | **1 144,60** |

Con recurso, cuando el cliente paga todo al vencimiento:

| Cuenta | Descripción | Debe | Haber |
|---|---|---|---|
| 4512 | Cancelación del adelanto | 10 301,40 | |
| 1041 | Banco (retenido) | 1 144,60 | |
| 1212 | Inmobiliaria del Sur SAC (la factura queda pagada) | | 11 446,00 |
| | **Total** | **11 446,00** | **11 446,00** |

### Impago

- **Con recurso:** haga clic en **Recompra** para devolver el adelanto (4512 al
  debe por 10 301,40 y banco al haber). La operación pasa a **Recomprada** y la
  factura sigue pendiente: se gestiona como cualquier deuda del cliente, con la
  provisión o el castigo de Odoo.
- **Sin recurso:** el factor asume el impago pero no libera el retenido. Haga
  clic en **Pérdida del retenido**: 6741 al debe y 1214 al haber por
  1 144,60, y la operación pasa a **Liquidada**.

### Moneda extranjera

Una obligación de USD 800 recibida a 3,75 (S/ 3 000) y cancelada cuando el
dólar está a 3,80 se salda en la 4512 por S/ 3 000, al cambio histórico, y la
diferencia de **S/ 40** va a pérdida por diferencia de cambio.

## Reportes

- **Perú ‣ Factoring ‣ Facturas cedidas**: cartera cedida por factor, cliente y
  vencimiento; cobrado y por cobrar; vencidas en rojo.
- **Perú ‣ Factoring ‣ Análisis de factoring**: nominal y pendiente por factor
  y estado.
- **Perú ‣ Factoring ‣ Costo financiero**: intereses, comisión, gastos y
  retenido perdido por factor y mes.
- La factura sigue en el registro de ventas por su importe y la cesión no genera
  comprobante. Los asientos de cesión, desembolso y cobro van al libro diario,
  y la comisión facturada va al registro de compras como cualquier factura de
  proveedor.

![Facturas cedidas por factor, cliente y vencimiento](factoring/assigned-invoices.png)

## Casos especiales

| Situación | Qué pasa | Qué hacer |
|---|---|---|
| Factura al contado | La cesión lo advierte en el historial | Verificar con el factor: la factura negociable nace de una venta al crédito |
| Factura con detracción | El nominal propuesto excluye la detracción | Nada: el cliente deposita la detracción en el Banco de la Nación y esa parte sigue en la factura |
| Cliente agente de retención | El nominal excluye el 3 % | Registrar la retención sufrida con el comprobante del cliente |
| Nominal mayor que el saldo de la factura | Error al ceder | Corregir el valor nominal |
| Intereses y comisiones mayores que el adelanto | Error en el desembolso | Revisar la liquidación del factor |
| Se intenta **Pagar** una factura cedida | Bloqueado | Registrar el cobro desde la operación |

## Datos de demostración

Una base creada **con datos de demostración** carga, al instalar el módulo, un
ejemplo completo en la compañía **PE Company** (la compañía peruana de la demo
de Odoo, con el plan contable de Perú). Los registros llevan el prefijo **DEMO
FAC** y las fechas se calculan respecto del día de la instalación. En una base
sin datos de demostración no se carga nada.

- Factor **DEMO FAC Factor Capital S.A.** y cliente **DEMO FAC Inmobiliaria del
  Sur S.A.C.**
- Operación sin recurso de dos facturas (S/ 12 000 y S/ 8 500), cedida y
  desembolsada.
- Operación con recurso de una factura de S/ 15 000, desembolsada y con
  intereses devengados.
- Una operación en borrador.

!!! info "Ver también"
    - [Ley 29623: factura negociable](https://www.leyes.congreso.gob.pe/Documentos/Leyes/29623.pdf)
    - [D.U. 013-2020: financiamiento de la MIPYME](https://www.leyes.congreso.gob.pe/Documentos/2016_2021/Decretos/Urgencias/2020/DU-013-2020-PP.pdf)
    - [R.S. 193-2020/SUNAT](https://www.sunat.gob.pe/legislacion/superin/2020/193-2020.pdf), su [anexo de forma de pago y cuotas](https://www.sunat.gob.pe/legislacion/superin/2020/anexo4-193-2020.pdf) y su [publicación en gob.pe](https://www.gob.pe/institucion/sunat/normas-legales/1124498-193-2020-sunat)
    - [R.S. 037-2002/SUNAT: régimen de retenciones del IGV](https://www.sunat.gob.pe/legislacion/superin/2002/037.htm)
    - [TUO de la Ley del IGV](https://www.sunat.gob.pe/legislacion/igv/ley/index.html)
    - [CAVALI](https://www.cavali.com.pe/)
    - [NIIF 9: instrumentos financieros](https://www.ifrs.org/issued-standards/list-of-standards/ifrs-9-financial-instruments/) y [NIC 21: variaciones en las tasas de cambio](https://www.ifrs.org/issued-standards/list-of-standards/ias-21-the-effects-of-changes-in-foreign-exchange-rates/)
    - [Plan Contable General Empresarial (MEF)](https://www.mef.gob.pe/contenidos/conta_publ/documentac/PCGE_2019.pdf)
    - [Odoo: Contabilidad](https://www.odoo.com/documentation/19.0/es/applications/finance/accounting.html)
    - [Letras de cambio](bills_of_exchange.md)

---
modulos: [al_construction_planner_subcontract, al_construction_planner_subcontract_sale, al_construction_planner_subcontract_purchase]
---

# Condiciones y valorización de contratas

Con **condiciones de contrata**, cada orden de contrata lleva su adelanto, su
fondo de garantía, sus ajustes de precio y su periodicidad, y cada corte se
valoriza con un resumen calculado por el **esquema de cálculo**. Sin
condiciones, la orden se comporta como en [Contratas y liquidación
semanal](contractors.md).

## Configuración

1. En **Configuración ‣ Condiciones de contrata**, cree las condiciones (el
   producto trae «Contrato de obra» de ejemplo):
    - **Adelanto (%)** y **Forma de amortizar**: proporcional al total o al
      subtotal de cada valorizado, monto fijo o manual.
    - **Fondo de garantía (%)**, su base (total con IGV o subtotal), el plazo de
      devolución en días, desde cada factura o desde la liquidación, y los
      **requisitos de devolución** (vencimiento del plazo, acta de recepción,
      carta de no deuda, ninguna observación de postventa u otros).
    - **Periodicidad**: semanal, quincenal (1-15 y 16-fin), mensual (fin de mes
      o día de corte) o al término. La semanal usa la semana de la obra, la
      misma del avance: el **Día de corte semanal** de la orden fija el cierre
      de esa semana al asignar la contrata (la obra lo registra en su
      historial). Si la obra ya tiene valorizaciones con otra semana, el corte
      no se cambia. **Tolerancia de avance** y **Líneas de la orden** (por partida o
      por actividad).
    - **Documentos requeridos** para la liquidación.
    - **Esquema de cálculo**: una fila por concepto, con su tipo (ajuste de
      precio, deductivo, impuesto, amortización, retención), base, porcentaje,
      signo y reflejo en la factura.
2. En la ficha del contratista (pestaña **Compras**), las **Condiciones de
   contrata** que se le proponen; si no tiene, las de **Ajustes ‣ Planificación
   de obra**.
3. En **Ajustes ‣ Planificación de obra**: el **producto de anticipo a
   contratistas** (con la cuenta de anticipos otorgados), la cuenta y el diario
   de **deductivos a contratas** y, opcional, la **aprobación por niveles de la
   orden de contrata** (instala `purchase_tier_validation`; sin reglas rige la
   aprobación de Compras).

## Orden de contrata

**Asignar contrata** propone las condiciones, muestra el total contractual con
IGV, el adelanto y el fondo según el esquema, y crea la orden con una línea por
actividad y partida. En la pestaña **Condiciones de contrata** de la orden se
ajustan los porcentajes pactados y se ven sus saldos: contractual, valorizado,
facturado, pagado y saldo; adelanto otorgado, amortizado y por amortizar; fondo
retenido y devuelto. Con la orden confirmada, las condiciones solo las cambia el
administrador (queda en el historial).

**Registrar adelanto** crea la factura de anticipo en borrador: adelanto (%) ×
subtotal contractual sin IGV, con la analítica de la obra. Solo se amortiza con
esa factura publicada.

## Valorización

En el corte de cada orden se crea la valorización en borrador («Valorizado 01 -
especialidad») con los avances validados del periodo, los rezagados, los
deductivos pendientes y los adicionales aprobados; **Preparar valorizaciones**
en la lista lo hace para todas las órdenes de una obra; una semana sin avances no
la detiene: pasa al periodo del primer avance o deductivo pendiente. La pestaña **Resumen del
periodo** muestra cada concepto del esquema con su contractual, anterior,
actual, acumulado y saldo; la franja **Revisar antes de aprobar** avisa de
metrados escritos a mano, re-trabajos, líneas sobre lo contratado y avances sin
fotos. Un re-trabajo entra con 0 en **A liquidar**: solo se paga si quien
valida la ejecución marca **Pagar el re-trabajo** con su motivo. **Actualizar**
rehace las líneas y conserva los deductivos que ya estaban en la valorización.
Se presenta (Ejecución: ejecuta), se valida (Ejecución: valida) y se aprueba por
niveles; al aprobar se recibe en la orden y se crea la factura:

- las líneas del servicio y los ajustes de precio;
- una línea negativa por **deductivo** (o un asiento si se descuenta al pago);
- la **regularización del adelanto**: amortización ÷ (1 + IGV) con el producto
  de anticipo;
- el **fondo de garantía** como cuota propia de la cuenta por pagar, con su
  vencimiento; el neto vence el día de pago.

**Imprimir valorizado** y **Enviar por correo** dan el documento A4 horizontal
con las partidas agrupadas, los adicionales, el resumen, los pagos de la orden
y las casillas de firma.

## Deductivos y adicionales

- **Ejecución ‣ Contratas ‣ Deductivos**: tipo, monto sin IGV, sustento
  (obligatorio) y referencia. Entran a la siguiente valorización de su orden;
  aplicado, se corrige con otro de signo contrario. El material extra
  descontado entra solo como deductivo.
- En un cambio de obra aprobado con contratista, **Agregar a la orden de
  contrata** suma sus líneas como adicional. Si la orden pasa su monto aprobado,
  la diferencia espera **Aprobar ampliación**.

## Liquidación y cierre

**Liquidar orden** crea la liquidación: las cantidades finales son el acumulado
validado (se reducen con motivo), amortiza el saldo del adelanto y muestra el
alcance no ejecutado. Con la factura publicada y los documentos requeridos
adjuntos, **Cerrar orden** baja cada línea a lo recibido, libera el saldo del
plan y bloquea la orden. Con el fondo «desde la liquidación», sus vencimientos
se corren a la fecha de la liquidación más el plazo.

## Fondos de garantía y reportes

- **Informes ‣ Contratas ‣ Fondos de garantía**: cuotas por contratista, obra y
  vencimiento, con los requisitos; administración o la gerencia marca la
  devolución retenida con motivo y el ticket de postventa.
- **Resumen de valorizaciones**: por obra, contratista y orden (con IGV), con el
  filtro **Despacho semanal**, los indicadores (avance frente al plazo,
  deductivos sobre valorizado, días de aprobación) y su impreso.
- **Análisis de valorizaciones**: tabla dinámica y gráfico por obra,
  contratista, partida, especialidad, mes y estado.

## Carga inicial

**Configuración ‣ Carga inicial de órdenes de contrata**: plantilla Excel con
las hojas ORDENES, LINEAS y FONDOS. Cada orden se crea confirmada, con una
valorización de apertura sin efecto contable; la siguiente valorización parte
del día siguiente al corte.

---
modulos: [al_construction_planner]
---

# Contratos de obra e hitos de cobro

Una obra puede tener varios contratos con el cliente: el suministro en
dólares y la instalación en soles, uno por familia (cocinas, closets) o uno
por parte del edificio (pisos pares, una torre). El **contrato de obra**
guarda sus condiciones y cobra por **hitos por unidad**.

## Contrato de obra

En **Ingresos ‣ Contratos de obra** cada contrato tiene:

- **Obra, cliente, orden de venta y moneda**.
- **Alcance**: suministro, instalación, suministro e instalación, o solo
  servicio.
- **Plantilla de hitos** y **factor de descuento** (el precio de lista por el
  factor da el precio del contrato).
- **Precios por tipología**: precio por unidad, partida de la orden de venta
  que se cobra y, si cambia, su propia plantilla de hitos.
- **Condiciones**: adelanto (con o sin carta fianza), fondo de garantía y su
  base, fiel cumplimiento, detracción, periodicidad de la valorización
  (semanal, quincenal o mensual) y penalidad diaria con su tope.
- **Diferencias entre documentos**: lo que dicen distinto la cotización, la
  orden y el contrato; se ve como aviso en la ficha.
- **Documentos habilitantes**: dossier de calidad, actas, pólizas… Los
  obligatorios que no se recibieron **bloquean el envío** de la valorización.

**Marcar unidades** elige las unidades que cubre: todas, pisos pares, pisos
impares, por agrupador (una torre) o una lista.

## Plantillas de hitos

En **Configuración ‣ Cobro al cliente ‣ Plantillas de hitos de cobro** vienen
80/15/5, 40/40/15/5, 60/20/15/5, 50/10/25/15, 60/15/15/10, 90/10 y 100. Los
porcentajes de una plantilla deben sumar 100. Cada hito tiene su
**disparador**:

| Disparador | Avance del hito |
|---|---|
| Etapa terminada | Avance de la etapa elegida en los módulos de la unidad |
| Llegada a obra | Módulos de la unidad que llegaron a obra (o pasaron de ese estado) |
| Acta de entrega | Unidad entregada |
| Postventa o manual | El porcentaje que se escribe a mano |

## Hitos por unidad

**Generar hitos** crea un hito por unidad cubierta y por línea de la
plantilla, con su monto: precio de la tipología × factor de descuento × % del
hito. **Ingresos ‣ Hitos por unidad** los muestra en lista (para escribir el
avance manual) y en pivote (tipología por hito).

## Valorizar hitos

Con el contrato **Vigente**, **Valorizar hitos** prepara una valorización con
lo ganado y no cobrado de cada hito, llevado a las partidas de la orden de
venta, con el adelanto del contrato. La pestaña **Hitos** de la valorización
dice el % anterior y el de ahora de cada hito. El envío, la conformidad del
cliente y la factura son los de siempre (ver [ruta del ingreso](income.md));
un hito puede cobrarse en dos valorizaciones.

El contrato suma también los [adicionales y deductivos](changes.md) aprobados
que lo mencionan.

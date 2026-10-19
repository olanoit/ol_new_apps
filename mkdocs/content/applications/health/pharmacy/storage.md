---
modulos: [al_pharmacy_stock]
---

# Almacenamiento

Lo que pide el Manual BPOF (7.5.1) para recibir, guardar y dar de baja.

## Recepción

En las recepciones con productos farmacéuticos aparece la pestaña **Farmacia**:

1. Revise el envase, el rotulado y el transporte y marque **Conforme** o **No
   conforme** (con la observación).
2. Registre el **lote** y la **fecha de vencimiento** de cada producto.
3. Valide. Odoo no deja validar sin inspección, sin lote o vencimiento, ni con
   el registro sanitario vencido. Una recepción **no conforme** deja sus lotes
   en **cuarentena**.

Las recepciones están en **Farmacia ‣ Inventario ‣ Recepciones**.

## Lotes y vencimientos

Cada lote tiene un **estado sanitario**: disponible, cuarentena, bloqueado o
vencido. Solo los disponibles se reservan y se ofrecen en la caja, el que vence
primero arriba. Un químico farmacéutico los **libera**; un lote vencido no se
libera. Cada día Odoo marca los vencidos.

**Farmacia ‣ Inventario ‣ Lotes y vencimientos** abre los lotes **Por vencer**
según los días de los ajustes.

## Precio por vencer

Para vender antes de que venzan, defina escalas de descuento en
**Farmacia ‣ Configuración ‣ Descuentos por vencer**: días al vencimiento y
porcentaje (por ejemplo, -20 % a 90 días y -40 % a 30 días), opcionalmente
por categoría. Si un lote cae en varias escalas vale la de menos días, y una
escala con categoría manda sobre las generales.

- **En la caja**: al elegir un lote dentro de una escala, la línea recibe el
  descuento y la nota «Por vencer: vence dd/mm/aaaa». Los lotes vencidos no
  se ofrecen.
- **Farmacia ‣ Inventario ‣ Lotes por vencer**: los días que le quedan a cada
  lote, su descuento y el precio sugerido.

## Canje con la droguería

Los lotes por vencer, vencidos o dañados que el proveedor acepta canjear se
gestionan en **Farmacia ‣ Inventario ‣ Canjes con la droguería**:

1. Cree el canje con el proveedor y el local y pulse **Cargar lotes**: trae
   los lotes por vencer o vencidos recibidos de ese proveedor.
2. **Marcar como enviado** cuando mande la lista y **Aceptado por el
   proveedor** cuando la acepte: se prepara la salida al proveedor.
3. **Devolver y terminar** entrega los lotes y cierra el canje.
4. **Registrar nota de crédito** crea la nota de crédito del proveedor en
   borrador con las cantidades y el costo.

El acta de canje se imprime desde el canje.

## Bonificaciones de compra

En la orden de compra, la columna **Bonificación** agrega las unidades sin costo
(por ejemplo 1 por cada 12) como una línea a precio cero: la factura del
proveedor cuadra y el costo del producto se reparte solo.

## Temperatura y humedad

1. Cree los **puntos de control** (**Farmacia ‣ Control ambiental ‣ Puntos de
   control**): ambiente (15 °C a 30 °C) o cadena de frío (2 °C a 8 °C), con su
   equipo y calibración.
2. Registre las **lecturas** cada día; Odoo recuerda con una actividad las que
   faltan.
3. Una lectura fuera de rango exige la **acción correctiva** y queda en el libro
   de ocurrencias.

## Alertas sanitarias y retiro

En **Farmacia ‣ Inventario ‣ Alertas sanitarias** registre la alerta (por
ejemplo una de DIGEMID) con los productos y lotes y pulse **Confirmar y
bloquear lotes**: los lotes quedan bloqueados y la pestaña **Impacto** muestra
el stock afectado y los clientes que los recibieron.

## Actas de baja y destrucción

En **Farmacia ‣ Inventario ‣ Actas de baja** liste los productos vencidos,
deteriorados o retirados con su lote, ubicación y motivo. Al **Validar**, un
químico farmacéutico los da de baja del inventario; imprima el acta para las
firmas.

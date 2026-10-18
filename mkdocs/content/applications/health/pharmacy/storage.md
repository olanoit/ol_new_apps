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

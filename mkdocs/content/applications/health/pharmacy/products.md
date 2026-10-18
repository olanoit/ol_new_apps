---
modulos: [al_pharmacy_base, al_pharmacy_pos, al_l10n_pe_pharmacy_edi]
---

# Productos y presentaciones

## Producto farmacéutico

En el producto marque **Producto farmacéutico** (pestaña Información general);
aparece la pestaña **Farmacia**:

- **Registro sanitario**, su **vencimiento** y su titular; el **laboratorio**.
- **Condición de venta**: venta libre, con receta médica o receta especial.
- **Tipo de producto**: genérico en DCI, genérico de marca o innovador.
- **Empresa vinculada**: si el producto es de una empresa vinculada al
  establecimiento (se informa al cliente, Ley 32033).
- **Forma farmacéutica**, **vía**, **cadena de frío** y **ubicación en estante**.
- **Composición**: una línea por principio activo (DCI) con su concentración.

Con la composición y la forma, Odoo calcula los **equivalentes**: productos con
el mismo principio activo, concentración y forma. La caja los ofrece como
alternativas, primero los genéricos en DCI y del más barato al más caro.

Los catálogos (principios activos, formas, vías) están en **Farmacia ‣
Configuración ‣ Catálogos**. Los filtros de la lista de productos ayudan a
revisar el maestro: **Sin registro sanitario**, **Registro vencido**, **Con
receta**, **Genéricos en DCI**, **Cadena de frío**.

## Presentaciones: caja, blíster o unidad

El stock se lleva en la unidad del producto (tableta, cápsula). En la pestaña
**Presentaciones** agregue cada presentación con sus **unidades** y su
**precio**, que no tiene por qué ser proporcional al de la unidad:

| Presentación | Unidades | Precio |
|---|---|---|
| (unidad suelta) | 1 | S/ 0,20 (precio del producto) |
| Blíster | 10 | S/ 1,50 |
| Caja | 100 | S/ 12,00 |

En la caja, al tocar el producto se elige la presentación; el inventario baja
en unidades y la boleta o factura lleva la línea en la unidad de la
presentación («1 Caja x 100 a S/ 12,00»), así cuadra con el ticket. El código
de barras de la caja (empaque del producto) vende directamente la caja.

!!! note "Nota"
    En Perú, la unidad de la presentación lleva su código SUNAT: caja BX,
    frasco BO, bolsa BG, paquete PK; las demás, el de la unidad del producto
    (NIU).

La lista de precios del pedido también se aplica a la presentación: un
convenio del 10 % deja la caja de S/ 50,00 en S/ 45,00, y al elegir en la caja
un cliente con convenio se recalculan las líneas que nadie cambió a mano.

!!! note "Nota"
    Las reglas con precio fijo o calculadas sobre el costo son por unidad del
    producto, como en el resto de Odoo: con ellas la caja vale ese precio por
    sus unidades.

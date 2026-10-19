---
modulos: [al_pharmacy_loyalty]
---

# Fidelización por DNI

Las cadenas identifican al cliente por su DNI en cada compra y le dan puntos
que canjea por vales (Inkaclub, de Inkafarma: 1 punto por S/ 4 y un vale de
S/ 5 cada 1 000 puntos). La botica puede hacer lo mismo con los programas de
fidelización de Odoo, con un límite: **no se premia la compra de medicamentos
con receta ni de controlados**. La norma prohíbe promover el consumo de
medicamentos con premios, sorteos o canjes.

## Cómo funciona

Cada programa de fidelización, promoción o cupón tiene la opción **Excluir
medicamentos con receta**, activa por defecto. Con ella:

- Los productos con condición de venta **Con receta** o **Controlado** no suman
  puntos ni cuentan para el monto o la cantidad mínima del programa.
- Los descuentos no los alcanzan: un descuento **sobre el pedido** pasa a
  aplicarse solo a los demás productos.
- El programa no puede regalar un medicamento con receta.

Vale en la caja y en los pedidos de venta. Las tarjetas de regalo y los
monederos no cambian: son medios de pago y se usan en cualquier compra (vea
[Tarjetas de regalo y monedero](../../sales/point_of_sale/gift_cards.md)).

!!! example "Ejemplo"
    Rosa compra S/ 8 de bloqueador y S/ 40 de amoxicilina con receta. Con el
    programa de 1 punto por S/ 4 gana **2 puntos** (por los S/ 8), y el 10 % de
    socio le descuenta **S/ 0,80**, no S/ 4,80.

## Configuración

1. Abra **Punto de venta ‣ Productos ‣ Descuentos y programas de lealtad** y cree un
   programa de tipo **Tarjetas de lealtad**.
2. En **Reglas condicionales**, indique los puntos por sol (0,25 = 1 punto por S/ 4).
3. En **Recompensas**, el vale: por ejemplo, S/ 5 de descuento por 1 000
   puntos.
4. Deje marcada **Excluir medicamentos con receta** y agregue el programa a las
   cajas.
5. En la caja, busque al cliente por su DNI antes de cobrar: los puntos van a
   su tarjeta.

!!! note "Nota"
    La base de demostración trae el programa **Club de Salud** con estas
    reglas.
